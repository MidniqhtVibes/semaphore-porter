from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import or_, select
from sqlalchemy.orm import selectinload

from app.audit import record_audit, sanitize
from app.database import SessionLocal
from app.dependencies import CurrentUser, Db
from app.models import (
    GroupMembership,
    RuleType,
    TaskPolicy,
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
from app.schemas import TaskStartRequest
from app.security import user_has_role
from app.semaphore_client import SemaphoreError
from app.services import semaphore_client_from_db


router = APIRouter(prefix="/portal", tags=["Benutzerportal"])


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
        "status": tenant.status.value,
    }


def _run_payload(run: TaskRun) -> dict[str, Any]:
    duration = None
    end = run.finished_at or utcnow()
    if run.started_at:
        started = run.started_at if run.started_at.tzinfo else run.started_at.replace(tzinfo=timezone.utc)
        finished = end if end.tzinfo else end.replace(tzinfo=timezone.utc)
        duration = max(0, int((finished - started).total_seconds()))
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


async def _sync_run(db: Db, run: TaskRun) -> dict[str, Any]:
    if run.tenant.semaphore_project is None:
        raise HTTPException(status_code=409, detail="Tenant besitzt kein registriertes Semaphore-Projekt.")
    project_id = run.tenant.semaphore_project.semaphore_project_id
    try:
        remote = await semaphore_client_from_db(db).get_task(project_id, run.semaphore_task_id)
    except (SemaphoreError, RuntimeError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    run.remote_snapshot = sanitize(remote)
    run.status = _map_status(remote.get("status"))
    run.last_synced_at = utcnow()
    if run.status in {TaskRunStatus.SUCCESS, TaskRunStatus.FAILED, TaskRunStatus.STOPPED} and run.finished_at is None:
        run.finished_at = utcnow()
    db.commit()
    return remote


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
def portal_dashboard(db: Db, user: CurrentUser) -> dict[str, Any]:
    tenant_ids = _tenant_ids_for_user(db, user)
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
        "running_count": sum(run.status in {TaskRunStatus.QUEUED, TaskRunStatus.RUNNING} for run in runs),
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
    return {
        "task": {"id": str(template.id), "name": template.name, "description": template.description},
        "fields": build_form_schema(template.policy.variable_rules, template.survey_schema),
        "can_start": "start" in task_actions(db, user, template.id),
    }


@router.post("/tenants/{tenant_id}/tasks/{template_id}/runs", status_code=201)
async def start_task(
    tenant_id: uuid.UUID,
    template_id: uuid.UUID,
    payload: TaskStartRequest,
    request: Request,
    db: Db,
    user: CurrentUser,
) -> dict[str, Any]:
    tenant = db.scalar(select(Tenant).where(Tenant.id == tenant_id).options(selectinload(Tenant.semaphore_project)))
    template = db.scalar(
        select(TaskTemplate)
        .where(TaskTemplate.id == template_id, TaskTemplate.tenant_id == tenant_id, TaskTemplate.is_enabled.is_(True))
        .options(selectinload(TaskTemplate.policy).selectinload(TaskPolicy.variable_rules))
    )
    if (
        tenant is None
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
        variables = enforce_policy(template.policy.variable_rules, payload.variables)
    except PolicyViolation as exc:
        raise HTTPException(status_code=422, detail={"message": str(exc), "fields": exc.errors}) from exc
    try:
        remote = await semaphore_client_from_db(db).start_task(
            tenant.semaphore_project.semaphore_project_id,
            template.semaphore_template_id,
            variables,
        )
    except (SemaphoreError, RuntimeError) as exc:
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
def list_runs(db: Db, user: CurrentUser) -> list[dict[str, Any]]:
    tenant_ids = _tenant_ids_for_user(db, user)
    rows = db.scalars(
        select(TaskRun)
        .where(TaskRun.tenant_id.in_(tenant_ids))
        .options(selectinload(TaskRun.tenant), selectinload(TaskRun.task_template), selectinload(TaskRun.started_by))
        .order_by(TaskRun.started_at.desc())
        .limit(200)
    ).all()
    return [_run_payload(run) for run in rows if "view" in task_actions(db, user, run.task_template_id)]


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
def run_events(run_id: uuid.UUID, db: Db, user: CurrentUser) -> StreamingResponse:
    _authorized_run(db, user, run_id)
    user_id = user.id

    async def stream():
        last_lines = 0
        for _ in range(900):  # maximal 30 Minuten pro Verbindung
            with SessionLocal() as poll_db:
                poll_user = poll_db.get(User, user_id)
                if poll_user is None or not poll_user.is_active:
                    yield "event: error\ndata: {\"message\":\"Zugriff beendet\"}\n\n"
                    return
                try:
                    run = _authorized_run(poll_db, poll_user, run_id)
                    remote = await _sync_run(poll_db, run)
                    assert run.tenant.semaphore_project is not None
                    output = await semaphore_client_from_db(poll_db).get_task_output(
                        run.tenant.semaphore_project.semaphore_project_id, run.semaphore_task_id
                    )
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
                except (HTTPException, SemaphoreError, RuntimeError) as exc:
                    yield f"event: error\ndata: {json.dumps({'message': str(exc)}, ensure_ascii=False)}\n\n"
                    return
            await asyncio.sleep(2)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"},
    )
