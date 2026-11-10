from __future__ import annotations

import asyncio
import json
import re
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request, Response
from fastapi.responses import StreamingResponse
from sqlalchemy import or_, select, update
from sqlalchemy.orm import selectinload

from app.audit import record_audit, sanitize
from app import approval_service
from app.database import SessionLocal, demo_database_turn
from app.dependencies import CurrentUser, Db
from app.models import (
    GroupMembership,
    RuleType,
    TaskPolicy,
    TaskApproval,
    TaskPermission,
    TaskRun,
    TaskRunStatus,
    TaskTemplate,
    Tenant,
    TenantMembership,
    TenantStatus,
    User,
    utcnow,
)
from app.permissions import can_access_tenant, task_actions
from app.policy import PolicyViolation, build_form_schema, enforce_policy
from app.project_backup import TENANT_VARIABLES
from app.schemas import TaskStartRequest
from app.security import session_cookie_name, get_session, user_has_role
from app.semaphore_client import SemaphoreError
from app.services import semaphore_client_from_db


router = APIRouter(prefix="/portal", tags=["Benutzerportal"])
STREAM_POLL_INTERVAL_SECONDS = 2
RUN_REFRESH_INTERVAL_SECONDS = 5
ACTIVE_RUN_STATUSES = (TaskRunStatus.QUEUED, TaskRunStatus.RUNNING, TaskRunStatus.UNKNOWN)


def _tenant_ids_for_user(db: Db, user: User) -> list[uuid.UUID]:
    if user_has_role(user, "system_admin"):
        return list(db.scalars(select(Tenant.id).where(Tenant.status != TenantStatus.DELETED)))
    groups = list(db.scalars(select(GroupMembership.group_id).where(GroupMembership.user_id == user.id)))
    return list(
        db.scalars(
            select(TenantMembership.tenant_id)
            .where(or_(TenantMembership.user_id == user.id, TenantMembership.group_id.in_(groups)))
            .distinct()
        )
    )


def _tenant_payload(tenant: Tenant) -> dict[str, Any]:
    return {
        "id": str(tenant.id),
        "tenant_slug": tenant.tenant_slug,
        "display_name": tenant.display_name,
        "description": tenant.description,
        "application_id": tenant.application_id,
        "application_ids": tenant.application_ids or ([tenant.application_id] if tenant.application_id else []),
        "database_types": tenant.database_types or [],
        "project_artwork": tenant.project_artwork or {},
        "status": tenant.status.value,
    }


def _run_payload(run: TaskRun) -> dict[str, Any]:
    duration = None
    end = run.finished_at or utcnow()
    if run.started_at:
        started = run.started_at if run.started_at.tzinfo else run.started_at.replace(tzinfo=timezone.utc)
        finished = end if end.tzinfo else end.replace(tzinfo=timezone.utc)
        duration = max(0, int((finished - started).total_seconds()))
    if run.status == TaskRunStatus.UNKNOWN or (run.status == TaskRunStatus.QUEUED
            and not _remote_time((run.remote_snapshot or {}).get("start"))):
        duration = None
    return {
        "id": str(run.id),
        "tenant_id": str(run.tenant_id),
        "tenant": run.tenant.display_name,
        "task_template_id": str(run.task_template_id),
        "task_template": run.task_template.name,
        "started_by": run.started_by.display_name,
        "status": run.status.value,
        "semaphore_task_id": run.semaphore_task_id,
        "started_at": run.started_at,
        "finished_at": run.finished_at,
        "duration_seconds": duration,
        "last_synced_at": run.last_synced_at,
        "sync_error": getattr(run, "sync_error", None),
    }


def _map_status(value: Any) -> TaskRunStatus:
    status = str(value or "").lower()
    if status in {"waiting", "queued", "pending"}:
        return TaskRunStatus.QUEUED
    if status in {"running", "starting"}:
        return TaskRunStatus.RUNNING
    if status in {"success", "successful", "completed"}:
        return TaskRunStatus.SUCCESS
    if status in {"error", "failed", "failure"}:
        return TaskRunStatus.FAILED
    if status in {"stopped", "canceled", "cancelled"}:
        return TaskRunStatus.STOPPED
    return TaskRunStatus.UNKNOWN


def _remote_time(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.year < 1970:
        return None
    return parsed.astimezone(timezone.utc) if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _apply_remote_state(run: TaskRun, remote: dict[str, Any]) -> None:
    run.remote_snapshot = sanitize(remote)
    run.status = _map_status(remote.get("status"))
    run.last_synced_at = utcnow()
    run.sync_error = None
    started, ended = _remote_time(remote.get("start")), _remote_time(remote.get("end"))
    if started:
        run.started_at = started
    if run.status in {TaskRunStatus.SUCCESS, TaskRunStatus.FAILED, TaskRunStatus.STOPPED}:
        if ended:
            run.finished_at = ended
        elif run.finished_at is None:
            run.finished_at = utcnow()
    else:
        run.finished_at = None
    if run.status == TaskRunStatus.UNKNOWN:
        run.sync_error = "Semaphore meldet einen nicht bestätigten Taskstatus."


async def _sync_run(db: Db, run: TaskRun) -> dict[str, Any]:
    if run.tenant.semaphore_project is None:
        raise HTTPException(status_code=409, detail="Tenant besitzt kein registriertes Semaphore-Projekt.")
    project_id = run.tenant.semaphore_project.semaphore_project_id
    try:
        remote = await semaphore_client_from_db(db).get_task(project_id, run.semaphore_task_id)
    except (SemaphoreError, RuntimeError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    _apply_remote_state(run, remote)
    db.commit()
    return remote


async def refresh_runs(db: Db, runs: list[TaskRun]) -> None:
    """Read remote state concurrently; apply database changes in one transaction."""
    active = []
    for run in runs:
        synced = run.last_synced_at
        if synced and synced.tzinfo is None:
            synced = synced.replace(tzinfo=timezone.utc)
        elapsed = (utcnow()-synced).total_seconds() if synced else None
        if run.status in ACTIVE_RUN_STATUSES and (elapsed is None or elapsed < 0 or elapsed >= RUN_REFRESH_INTERVAL_SECONDS):
            active.append((run, run.tenant.semaphore_project))
    if not active:
        return
    try:
        client = semaphore_client_from_db(db)
    except RuntimeError:
        for run, _ in active:
            run.status, run.sync_error = TaskRunStatus.UNKNOWN, "Semaphore-Verbindung ist nicht konfiguriert."
        db.commit()
        return
    gate = asyncio.Semaphore(6)
    async def fetch(run, project):
        if project is None:
            return None
        async with gate:
            try:
                return await client.get_task(project.semaphore_project_id, run.semaphore_task_id)
            except SemaphoreError:
                return None
    results = await asyncio.gather(*(fetch(run, project) for run, project in active))
    for (run, _), remote in zip(active, results):
        if remote is None:
            run.status = TaskRunStatus.UNKNOWN
            run.sync_error = "Semaphore-Status konnte nicht aktualisiert werden."
            continue
        _apply_remote_state(run, remote)
    db.commit()


def _authorized_run(db: Db, user: User, run_id: uuid.UUID, *, action: str = "view") -> TaskRun:
    run = db.scalar(
        select(TaskRun)
        .where(TaskRun.id == run_id)
        .options(
            selectinload(TaskRun.tenant).selectinload(Tenant.semaphore_project),
            selectinload(TaskRun.task_template),
            selectinload(TaskRun.started_by),
        )
    )
    if run is None:
        raise HTTPException(status_code=404, detail="Task-Ausführung nicht gefunden.")
    if not can_access_tenant(db, user, run.tenant) or action not in task_actions(db, user, run.task_template_id):
        # Absichtlich 404, damit fremde IDs nicht bestätigt werden.
        raise HTTPException(status_code=404, detail="Task-Ausführung nicht gefunden.")
    return run


@router.get("/dashboard")
async def portal_dashboard(db: Db, user: CurrentUser) -> dict[str, Any]:
    tenant_ids = _tenant_ids_for_user(db, user)
    active_runs = list(db.scalars(select(TaskRun).where(TaskRun.tenant_id.in_(tenant_ids), TaskRun.started_by_id == user.id, TaskRun.status.in_([TaskRunStatus.QUEUED, TaskRunStatus.RUNNING, TaskRunStatus.UNKNOWN]))))
    await refresh_runs(db, active_runs)
    runs = list(
        db.scalars(
            select(TaskRun)
            .where(TaskRun.tenant_id.in_(tenant_ids), TaskRun.started_by_id == user.id)
            .options(selectinload(TaskRun.tenant), selectinload(TaskRun.task_template), selectinload(TaskRun.started_by))
            .order_by(TaskRun.started_at.desc())
            .limit(8)
        )
    )
    return {
        "project_count": len(tenant_ids),
        "running_count": sum(run.status in {TaskRunStatus.QUEUED, TaskRunStatus.RUNNING} for run in active_runs),
        "recent_runs": [_run_payload(run) for run in runs],
    }


@router.get("/tenants")
def my_tenants(db: Db, user: CurrentUser) -> list[dict[str, Any]]:
    tenant_ids = _tenant_ids_for_user(db, user)
    rows = db.scalars(
        select(Tenant)
        .where(
            Tenant.id.in_(tenant_ids),
            Tenant.status == TenantStatus.ACTIVE,
            Tenant.configuration_complete.is_(True),
        )
        .order_by(Tenant.display_name)
    ).all()
    return [_tenant_payload(row) for row in rows]


@router.get("/tenants/{tenant_id}")
def tenant_detail(tenant_id: uuid.UUID, db: Db, user: CurrentUser) -> dict[str, Any]:
    tenant = db.scalar(
        select(Tenant)
        .where(Tenant.id == tenant_id, Tenant.status == TenantStatus.ACTIVE, Tenant.configuration_complete.is_(True))
        .options(selectinload(Tenant.task_templates).selectinload(TaskTemplate.policy))
    )
    if tenant is None or not can_access_tenant(db, user, tenant):
        raise HTTPException(status_code=404, detail="Projekt nicht gefunden.")
    tasks = []
    for template in tenant.task_templates:
        actions = task_actions(db, user, template.id)
        if template.is_enabled and template.policy and template.policy.is_active and "view" in actions:
            tasks.append(
                {
                    "id": str(template.id),
                    "name": template.name,
                    "description": template.description,
                    "app": template.app,
                    "can_start": "start" in actions,
                    "can_stop": "stop" in actions,
                }
            )
    result = _tenant_payload(tenant)
    result["task_templates"] = tasks
    return result


@router.get("/tenants/{tenant_id}/tasks/{template_id}/form")
def task_form(tenant_id: uuid.UUID, template_id: uuid.UUID, db: Db, user: CurrentUser) -> dict[str, Any]:
    tenant = db.get(Tenant, tenant_id)
    template = db.scalar(
        select(TaskTemplate)
        .where(TaskTemplate.id == template_id, TaskTemplate.tenant_id == tenant_id, TaskTemplate.is_enabled.is_(True))
        .options(selectinload(TaskTemplate.policy).selectinload(TaskPolicy.variable_rules))
    )
    if (
        tenant is None
        or tenant.status != TenantStatus.ACTIVE
        or not tenant.configuration_complete
        or not can_access_tenant(db, user, tenant)
        or template is None
        or "view" not in task_actions(db, user, template.id)
    ):
        raise HTTPException(status_code=404, detail="Task nicht gefunden.")
    if template.policy is None or not template.policy.is_active:
        raise HTTPException(status_code=409, detail="Für diesen Task ist keine aktive Policy vorhanden.")
    report_task = any(rule.variable_name == "send_deployment_mail" for rule in template.policy.variable_rules)
    approval_required = approval_service.required(tenant, template)
    return {
        "task": {"id": str(template.id), "name": template.name, "description": template.description},
        "fields": build_form_schema([rule for rule in template.policy.variable_rules if not report_task or rule.variable_name != "mail_user"], template.survey_schema),
        "mail_recipient": user.email,
        "can_start": "start" in task_actions(db, user, template.id),
        "approval_required": approval_required,
        "cost_class": template.policy.cost_class,
        "effort_class": template.policy.effort_class,
    }


def prepare_task_start(
    tenant_id: uuid.UUID,
    template_id: uuid.UUID,
    payload: TaskStartRequest,
    db: Db,
    user: CurrentUser,
):
    tenant = db.scalar(select(Tenant).where(Tenant.id == tenant_id).with_for_update().options(selectinload(Tenant.semaphore_project)))
    template = db.scalar(
        select(TaskTemplate)
        .where(TaskTemplate.id == template_id, TaskTemplate.tenant_id == tenant_id, TaskTemplate.is_enabled.is_(True))
        .options(selectinload(TaskTemplate.policy).selectinload(TaskPolicy.variable_rules))
    )
    if (
        not user.is_active
        or tenant is None
        or tenant.status != TenantStatus.ACTIVE
        or not tenant.configuration_complete
        or tenant.semaphore_project is None
        or not can_access_tenant(db, user, tenant)
        or template is None
        or "start" not in task_actions(db, user, template.id)
    ):
        raise HTTPException(status_code=404, detail="Task nicht gefunden oder nicht freigegeben.")
    if template.policy is None or not template.policy.is_active:
        raise HTTPException(status_code=409, detail="Für diesen Task ist keine aktive Policy vorhanden.")
    try:
        # The report recipient is an authenticated account attribute, never a
        # user-controlled parameter or a copied fixed/default policy value.
        report_task = any(rule.variable_name == "send_deployment_mail" for rule in template.policy.variable_rules)
        submitted = {name: value for name, value in payload.variables.items() if not report_task or name != "mail_user"}
        variables = enforce_policy([rule for rule in template.policy.variable_rules if not report_task or rule.variable_name != "mail_user"], submitted)
        if TENANT_VARIABLES.intersection(variables):
            raise HTTPException(409, "Veraltete Tenant-/Scope-Policy: Semaphore-Defaults konfigurieren und Policy aktualisieren.")
        if variables.get("send_deployment_mail") is True:
            if len(user.email) > 254 or re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", user.email) is None:
                raise HTTPException(422, "Für den Mailbericht benötigt dein Konto eine gültige E-Mail-Adresse mit maximal 254 Zeichen.")
            variables["mail_user"] = user.email
    except PolicyViolation as exc:
        raise HTTPException(status_code=422, detail={"message": str(exc), "fields": exc.errors}) from exc
    return tenant, template, variables


@router.post("/tenants/{tenant_id}/tasks/{template_id}/runs", status_code=201)
async def start_task(tenant_id: uuid.UUID, template_id: uuid.UUID, payload: TaskStartRequest,
                     request: Request, db: Db, user: CurrentUser) -> dict[str, Any]:
    return await execute_task_start(tenant_id, template_id, payload, request, db, user)


async def execute_task_start(tenant_id, template_id, payload, request, db, user, approval=None):
    tenant, template, variables = prepare_task_start(tenant_id, template_id, payload, db, user)
    needed = approval_service.required(tenant, template)
    if approval is None and needed:
        raise HTTPException(409, "Dieser Task benötigt zuerst eine Genehmigung. Genehmigung anfordern.")
    if approval is not None:
        if (approval.requester_id != user.id or approval_service.visible_status(approval) != "approved"
                or approval.tenant_id != tenant.id or approval.task_template_id != template.id):
            raise HTTPException(409, "Diese Freigabe ist nicht für einen weiteren Start verfügbar.")
        approver = db.get(User, approval.approver_id)
        if not approver or not approver.is_active or not needed or approval.context_digest != approval_service.context_digest(db, tenant, template, variables):
            raise HTTPException(409, "Konfiguration, Empfänger oder Parameter wurden geändert. Neue Genehmigung anfordern.")
        # Durable single-use claim BEFORE the external request. A timeout or
        # process crash must never return the same approval to 'approved'.
        claimed = db.execute(update(TaskApproval).where(TaskApproval.id == approval.id,
            TaskApproval.status == "approved").values(status="executing", execution_started_at=utcnow()))
        if claimed.rowcount != 1:
            raise HTTPException(409, "Die Freigabe wird bereits verwendet.")
        db.commit()
        db.expire_all()
        tenant, template, variables = prepare_task_start(tenant_id, template_id, payload, db, user)
        if approval.context_digest != approval_service.context_digest(db, tenant, template, variables):
            approval.status = "cancelled"
            db.commit()
            raise HTTPException(409, "Konfiguration wurde während des Starts geändert. Neue Genehmigung erforderlich.")
    try:
        remote = await semaphore_client_from_db(db).start_task(
            tenant.semaphore_project.semaphore_project_id,
            template.semaphore_template_id,
            variables,
        )
    except (SemaphoreError, RuntimeError) as exc:
        if approval is not None:
            approval.status = "uncertain"
        record_audit(
            db,
            "task_start_failed",
            actor=user,
            request=request,
            target_type="task_template",
            target_id=template.id,
            details={"message": str(exc), "variable_names": sorted(variables)},
            success=False,
        )
        db.commit()
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    hidden_names = {
        rule.variable_name for rule in template.policy.variable_rules if rule.rule_type == RuleType.HIDDEN
    }
    recorded_variables = sanitize(
        {name: "[ENTFERNT]" if name in hidden_names else value for name, value in variables.items()}
    )
    run = TaskRun(
        tenant_id=tenant.id,
        task_template_id=template.id,
        started_by_id=user.id,
        semaphore_task_id=remote["id"],
        status=_map_status(remote.get("status")),
        submitted_variables=recorded_variables,
        remote_snapshot=sanitize(remote),
    )
    db.add(run)
    db.flush()
    if approval is not None:
        approval.status, approval.run_id = "executed", run.id
    record_audit(
        db,
        "task_started",
        actor=user,
        request=request,
        target_type="task_run",
        target_id=run.id,
        details={
            "tenant_id": str(tenant.id),
            "template_id": str(template.id),
            "semaphore_task_id": run.semaphore_task_id,
            "variable_names": sorted(variables),
        },
    )
    db.commit()
    return _run_payload(run)


@router.get("/runs")
async def list_runs(db: Db, user: CurrentUser, response: Response, active_only: bool = Query(default=False)) -> list[dict[str, Any]]:
    response.headers["Cache-Control"] = "no-store"
    tenant_ids = _tenant_ids_for_user(db, user)
    query = (
        select(TaskRun)
        .where(TaskRun.tenant_id.in_(tenant_ids))
        .options(selectinload(TaskRun.tenant).selectinload(Tenant.semaphore_project),
                 selectinload(TaskRun.task_template), selectinload(TaskRun.started_by))
        .order_by(TaskRun.started_at.desc())
    )
    if not user_has_role(user, "system_admin"):
        groups = select(GroupMembership.group_id).where(GroupMembership.user_id == user.id)
        permitted = select(TaskPermission.task_template_id).where(TaskPermission.can_view.is_(True),
            or_(TaskPermission.user_id == user.id, TaskPermission.group_id.in_(groups)))
        query = query.where(TaskRun.task_template_id.in_(permitted))
    if active_only:
        # Apply the active filter in SQL, before any history limit. An old task
        # may still be running even after hundreds of newer completed runs.
        query = query.where(TaskRun.status.in_(ACTIVE_RUN_STATUSES))
    else:
        query = query.limit(200)
    visible = list(db.scalars(query))
    await refresh_runs(db, visible)
    if active_only:
        visible = [run for run in visible if run.status in ACTIVE_RUN_STATUSES]
    return [_run_payload(run) for run in visible]


@router.get("/runs/{run_id}")
async def run_detail(run_id: uuid.UUID, db: Db, user: CurrentUser) -> dict[str, Any]:
    run = _authorized_run(db, user, run_id)
    remote = await _sync_run(db, run)
    try:
        output = await semaphore_client_from_db(db).get_task_output(
            run.tenant.semaphore_project.semaphore_project_id, run.semaphore_task_id  # type: ignore[union-attr]
        )
    except (SemaphoreError, RuntimeError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    result = _run_payload(run)
    result["can_stop"] = "stop" in task_actions(db, user, run.task_template_id)
    result.update({"remote": {"id": remote.get("id"), "status": remote.get("status")}, "output": output})
    return result


@router.post("/runs/{run_id}/stop")
async def stop_run(run_id: uuid.UUID, request: Request, db: Db, user: CurrentUser) -> dict[str, str]:
    run = _authorized_run(db, user, run_id, action="stop")
    assert run.tenant.semaphore_project is not None
    try:
        await semaphore_client_from_db(db).stop_task(run.tenant.semaphore_project.semaphore_project_id, run.semaphore_task_id)
    except (SemaphoreError, RuntimeError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    record_audit(db, "task_stopped", actor=user, request=request, target_type="task_run", target_id=run.id)
    db.commit()
    return {"message": "Abbruch wurde an Semaphore übermittelt."}


@router.get("/runs/{run_id}/events")
def run_events(run_id: uuid.UUID, request: Request, db: Db, user: CurrentUser) -> StreamingResponse:
    _authorized_run(db, user, run_id)
    user_id = user.id
    session_cookie = request.cookies.get(session_cookie_name())

    async def stream():
        last_lines = 0
        yield ": connected\nretry: 3000\n\n"
        for _ in range(900):  # maximal 30 Minuten pro Verbindung
            if await request.is_disconnected():
                return
            async with demo_database_turn():
                with SessionLocal() as poll_db:
                    poll_session = get_session(poll_db, session_cookie)
                    poll_user = poll_session.user if poll_session else None
                    if poll_user is None or poll_user.id != user_id or not poll_user.is_active or poll_user.must_change_password:
                        yield "event: error\ndata: {\"message\":\"Zugriff beendet\"}\n\n"
                        return
                    try:
                        run = _authorized_run(poll_db, poll_user, run_id)
                        remote = await _sync_run(poll_db, run)
                        assert run.tenant.semaphore_project is not None
                        output = await semaphore_client_from_db(poll_db).get_task_output(
                            run.tenant.semaphore_project.semaphore_project_id, run.semaphore_task_id
                        )
                        if len(output) < last_lines:
                            last_lines = 0
                        new_lines = output[last_lines:]
                        last_lines = len(output)
                        data = {
                            "run": _run_payload(run),
                            "remote": {"id": remote.get("id"), "status": remote.get("status")},
                            "lines": new_lines,
                        }
                        yield f"event: update\ndata: {json.dumps(data, default=str, ensure_ascii=False)}\n\n"
                        if run.status in {TaskRunStatus.SUCCESS, TaskRunStatus.FAILED, TaskRunStatus.STOPPED}:
                            yield "event: complete\ndata: {}\n\n"
                            return
                    except HTTPException as exc:
                        if exc.status_code >= 500:
                            yield f"event: warning\ndata: {json.dumps({'message': str(exc.detail)}, ensure_ascii=False)}\n\n"
                        else:
                            yield f"event: error\ndata: {json.dumps({'message': str(exc)}, ensure_ascii=False)}\n\n"
                            return
                    except (SemaphoreError, RuntimeError) as exc:
                        yield f"event: warning\ndata: {json.dumps({'message': str(exc)}, ensure_ascii=False)}\n\n"
            await asyncio.sleep(STREAM_POLL_INTERVAL_SECONDS)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"},
    )
