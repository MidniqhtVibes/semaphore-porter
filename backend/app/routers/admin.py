from __future__ import annotations

import json
import uuid
from datetime import timedelta, timezone
from typing import Any

from fastapi import APIRouter, File, HTTPException, Query, Request, UploadFile
from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.orm import selectinload
from sqlalchemy.exc import IntegrityError

from app.audit import record_audit
from app.dependencies import Db, SystemAdmin
from app.config import get_settings
from app.models import (
    AuditEvent,
    CreationJob,
    CreationStatus,
    Group,
    GroupMembership,
    Preset,
    PresetVersion,
    PortalSession,
    ProjectTemplate,
    Role,
    SemaphoreProject,
    SemaphoreSettings,
    RuleType,
    TaskPermission,
    TaskPolicy,
    TaskRun,
    TaskRunStatus,
    TaskTemplate,
    Tenant,
    TenantMembership,
    TenantStatus,
    User,
    VariableRule,
    utcnow,
)
from app.project_backup import BackupValidationError, TENANT_VARIABLES, is_defaults, json_object, parse_backup, prepare_backup, public_variables, survey_catalog, validate_backup
from app.schemas import (
    CreationExecuteRequest,
    CreationJobCreate,
    CreationJobUpdate,
    GroupCreate,
    GroupMembersUpdate,
    PasswordReset,
    PresetInput,
    ProjectTemplateSave,
    SemaphoreSettingsInput,
    TaskPermissionInput,
    TaskPolicyInput,
    TenantMembershipInput,
    TenantUpdate,
    UserCreate,
    UserUpdate,
)
from app.security import encrypt_secret, hash_password
from app.semaphore_client import SemaphoreClient, SemaphoreConnection, SemaphoreError
from app.services import contains_secret, semaphore_client_from_db
from app.tenant_options import SELECTION_FIELDS, allowed_options, selected_options
from app.usernames import suggest_username
from app import vault_service
from app.vault_client import VaultError


router = APIRouter(prefix="/admin", tags=["Administration"])


def user_json(user: User) -> dict[str, Any]:
    return {
        "id": str(user.id),
        "email": user.email,
        "username": user.username,
        "display_name": user.display_name,
        "is_active": user.is_active,
        "must_change_password": user.must_change_password,
        "roles": [role.code for role in user.roles],
        "last_login_at": user.last_login_at,
        "created_at": user.created_at,
    }


def tenant_json(tenant: Tenant, *, detail: bool = False) -> dict[str, Any]:
    result: dict[str, Any] = {
        "id": str(tenant.id),
        "tenant_slug": tenant.tenant_slug,
        "display_name": tenant.display_name,
        "description": tenant.description,
        "application_id": tenant.application_id,
        "application_ids": tenant.application_ids or ([tenant.application_id] if tenant.application_id else []),
        "database_types": tenant.database_types,
        "dataset_ids": tenant.dataset_ids,
        "status": tenant.status.value,
        "configuration_complete": tenant.configuration_complete,
        "created_at": tenant.created_at,
        "updated_at": tenant.updated_at,
        "semaphore_project": None,
    }
    if tenant.semaphore_project:
        result["semaphore_project"] = {
            "id": tenant.semaphore_project.semaphore_project_id,
            "name": tenant.semaphore_project.name,
            "last_verified_at": tenant.semaphore_project.last_verified_at,
            "last_error": tenant.semaphore_project.last_error,
        }
    if detail:
        result["memberships"] = [
            {
                "id": str(item.id),
                "user_id": str(item.user_id) if item.user_id else None,
                "group_id": str(item.group_id) if item.group_id else None,
                "principal_name": item.user.display_name if item.user else item.group.name if item.group else "?",
                "role_code": item.role_code,
            }
            for item in tenant.memberships
        ]
        result["task_templates"] = [task_template_json(item) for item in tenant.task_templates]
    return result


def task_template_json(template: TaskTemplate) -> dict[str, Any]:
    return {
        "id": str(template.id),
        "semaphore_template_id": template.semaphore_template_id,
        "name": template.name,
        "description": template.description,
        "app": template.app,
        "is_enabled": template.is_enabled,
        "survey_schema": template.survey_schema,
        "has_policy": template.policy is not None,
        "policy_version": template.policy.version if template.policy else None,
    }


def creation_json(job: CreationJob) -> dict[str, Any]:
    return {
        "id": str(job.id),
        "idempotency_key": job.idempotency_key,
        "status": job.status.value,
        "project_template_id": str(job.project_template_id) if job.project_template_id else None,
        "tenant_id": str(job.tenant_id) if job.tenant_id else None,
        "draft_data": job.draft_data,
        "validation_result": job.validation_result,
        "semaphore_project_id": job.semaphore_project_id,
        "last_error": job.last_error,
        "vault_plan": job.vault_plan,
        "vault_progress": job.vault_progress,
        "vault_values_saved": bool(job.encrypted_vault_payload),
        "created_at": job.created_at,
        "updated_at": job.updated_at,
    }


@router.get("/dashboard")
async def dashboard(db: Db, admin: SystemAdmin) -> dict[str, Any]:
    del admin
    from app.routers.portal import refresh_runs
    await refresh_runs(db, list(db.scalars(select(TaskRun).where(TaskRun.status.in_([TaskRunStatus.QUEUED, TaskRunStatus.RUNNING, TaskRunStatus.UNKNOWN])))))
    latest_audit = list(db.scalars(select(AuditEvent).order_by(AuditEvent.occurred_at.desc()).limit(8)))
    semaphore = db.get(SemaphoreSettings, 1)
    return {
        "tenant_count": db.scalar(select(func.count(Tenant.id)).where(Tenant.status != TenantStatus.DELETED)) or 0,
        "active_user_count": db.scalar(select(func.count(User.id)).where(User.is_active.is_(True))) or 0,
        "project_count": db.scalar(select(func.count(SemaphoreProject.id))) or 0,
        "running_task_count": db.scalar(
            select(func.count(TaskRun.id)).where(TaskRun.status.in_([TaskRunStatus.QUEUED, TaskRunStatus.RUNNING]))
        )
        or 0,
        "failed_task_count": db.scalar(select(func.count(TaskRun.id)).where(TaskRun.status == TaskRunStatus.FAILED)) or 0,
        "incomplete_tenant_count": db.scalar(
            select(func.count(Tenant.id)).where(Tenant.configuration_complete.is_(False), Tenant.status != TenantStatus.DELETED)
        )
        or 0,
        "semaphore": {
            "configured": semaphore is not None,
            "last_tested_at": semaphore.last_tested_at if semaphore else None,
            "healthy": semaphore.last_test_success if semaphore else None,
            "message": semaphore.last_test_message if semaphore else "Noch nicht konfiguriert",
        },
        "recent_audit": [
            {
                "id": str(event.id),
                "occurred_at": event.occurred_at,
                "event_type": event.event_type,
                "target_type": event.target_type,
                "target_id": event.target_id,
                "success": event.success,
            }
            for event in latest_audit
        ],
    }


# Benutzer und Gruppen
@router.get("/users")
def list_users(db: Db, admin: SystemAdmin) -> list[dict[str, Any]]:
    del admin
    users = db.scalars(select(User).options(selectinload(User.roles)).order_by(User.display_name)).all()
    return [user_json(user) for user in users]


@router.post("/users", status_code=201)
def create_user(payload: UserCreate, request: Request, db: Db, admin: SystemAdmin) -> dict[str, Any]:
    email = payload.email.lower().strip()
    if db.scalar(select(User.id).where(func.lower(User.email) == email)):
        raise HTTPException(status_code=409, detail="Diese E-Mail-Adresse ist bereits vergeben.")
    username = payload.username or suggest_username(email, list(db.scalars(select(User.username).where(User.username.is_not(None)))))
    if db.scalar(select(User.id).where(func.lower(User.username) == username)):
        raise HTTPException(status_code=409, detail="Dieser Benutzername ist bereits vergeben.")
    roles = list(db.scalars(select(Role).where(Role.code.in_(payload.role_codes))))
    if len(roles) != len(set(payload.role_codes)):
        raise HTTPException(status_code=400, detail="Mindestens eine unbekannte Rolle wurde angegeben.")
    user = User(
        email=email,
        username=username,
        display_name=payload.display_name.strip(),
        password_hash=hash_password(payload.password),
        must_change_password=payload.must_change_password,
    )
    user.roles = roles
    db.add(user)
    try:
        db.flush()
        record_audit(db, "user_created", actor=admin, request=request, target_type="user", target_id=user.id, details={"roles": payload.role_codes, "username": username})
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="E-Mail-Adresse oder Benutzername ist bereits vergeben.")
    return user_json(user)


@router.patch("/users/{user_id}")
def update_user(user_id: uuid.UUID, payload: UserUpdate, request: Request, db: Db, admin: SystemAdmin) -> dict[str, Any]:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Benutzer nicht gefunden.")
    if payload.username is not None:
        if db.scalar(select(User.id).where(func.lower(User.username) == payload.username, User.id != user.id)):
            raise HTTPException(status_code=409, detail="Dieser Benutzername ist bereits vergeben.")
    if payload.display_name is not None:
        user.display_name = payload.display_name.strip()
    if payload.is_active is not None:
        if user.id == admin.id and not payload.is_active:
            raise HTTPException(status_code=400, detail="Das eigene Administratorkonto kann hier nicht deaktiviert werden.")
        user.is_active = payload.is_active
    if payload.role_codes is not None:
        roles = list(db.scalars(select(Role).where(Role.code.in_(payload.role_codes))))
        if len(roles) != len(set(payload.role_codes)):
            raise HTTPException(status_code=400, detail="Unbekannte Rolle.")
        user.roles = roles
    if payload.username is not None:
        user.username = payload.username
    record_audit(db, "user_updated", actor=admin, request=request, target_type="user", target_id=user.id, details=payload.model_dump(exclude_none=True))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Dieser Benutzername ist bereits vergeben.")
    return user_json(user)


@router.post("/users/{user_id}/reset-password")
def reset_password(user_id: uuid.UUID, payload: PasswordReset, request: Request, db: Db, admin: SystemAdmin) -> dict[str, str]:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Benutzer nicht gefunden.")
    user.password_hash = hash_password(payload.password)
    user.must_change_password = payload.must_change_password
    db.execute(delete(PortalSession).where(PortalSession.user_id == user.id))
    record_audit(db, "password_reset", actor=admin, request=request, target_type="user", target_id=user.id)
    db.commit()
    return {"message": "Passwort wurde zurückgesetzt."}


@router.get("/groups")
def list_groups(db: Db, admin: SystemAdmin) -> list[dict[str, Any]]:
    del admin
    groups = db.scalars(select(Group).options(selectinload(Group.memberships)).order_by(Group.name)).all()
    return [
        {"id": str(group.id), "name": group.name, "description": group.description, "user_ids": [str(item.user_id) for item in group.memberships]}
        for group in groups
    ]


@router.post("/groups", status_code=201)
def create_group(payload: GroupCreate, request: Request, db: Db, admin: SystemAdmin) -> dict[str, Any]:
    if db.scalar(select(Group.id).where(func.lower(Group.name) == payload.name.lower().strip())):
        raise HTTPException(status_code=409, detail="Gruppenname ist bereits vergeben.")
    group = Group(name=payload.name.strip(), description=payload.description.strip())
    db.add(group)
    db.flush()
    record_audit(db, "group_created", actor=admin, request=request, target_type="group", target_id=group.id)
    db.commit()
    return {"id": str(group.id), "name": group.name, "description": group.description, "user_ids": []}


@router.put("/groups/{group_id}/members")
def set_group_members(group_id: uuid.UUID, payload: GroupMembersUpdate, request: Request, db: Db, admin: SystemAdmin) -> dict[str, Any]:
    group = db.get(Group, group_id)
    if group is None:
        raise HTTPException(status_code=404, detail="Gruppe nicht gefunden.")
    found = set(db.scalars(select(User.id).where(User.id.in_(payload.user_ids))))
    if found != set(payload.user_ids):
        raise HTTPException(status_code=400, detail="Mindestens ein Benutzer existiert nicht.")
    db.execute(delete(GroupMembership).where(GroupMembership.group_id == group.id))
    for user_id in found:
        db.add(GroupMembership(group_id=group.id, user_id=user_id))
    record_audit(db, "group_members_changed", actor=admin, request=request, target_type="group", target_id=group.id, details={"member_count": len(found)})
    db.commit()
    return {"message": "Gruppenmitglieder wurden aktualisiert."}


# Semaphore-Verbindung
@router.get("/semaphore")
def semaphore_settings(db: Db, admin: SystemAdmin) -> dict[str, Any]:
    del admin
    item = db.get(SemaphoreSettings, 1)
    if item is None:
        return {"configured": False, "base_url": "", "proxy_url": None}
    return {
        "configured": True,
        "base_url": item.base_url,
        "proxy_url": item.proxy_url,
        "last_tested_at": item.last_tested_at,
        "last_test_success": item.last_test_success,
        "last_test_message": item.last_test_message,
    }


@router.put("/semaphore")
async def save_semaphore_settings(payload: SemaphoreSettingsInput, request: Request, db: Db, admin: SystemAdmin) -> dict[str, Any]:
    existing = db.get(SemaphoreSettings, 1)
    if payload.token is None and existing is None:
        raise HTTPException(status_code=400, detail="Beim ersten Speichern ist ein Service-Token erforderlich.")
    token = payload.token
    if token is None and existing:
        from app.security import decrypt_secret

        token = decrypt_secret(existing.encrypted_token)
    assert token is not None
    client = SemaphoreClient(SemaphoreConnection(payload.base_url, token, payload.proxy_url))
    try:
        projects = await client.test_connection()
    except SemaphoreError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    item = existing or SemaphoreSettings(id=1, base_url=payload.base_url, encrypted_token=b"")
    item.base_url = payload.base_url.rstrip("/")
    item.proxy_url = payload.proxy_url or None
    item.encrypted_token = encrypt_secret(token)
    item.last_tested_at = utcnow()
    item.last_test_success = True
    item.last_test_message = f"Verbindung erfolgreich; {len(projects)} Projekte gefunden."
    item.updated_by_id = admin.id
    db.add(item)
    record_audit(db, "semaphore_connection_changed", actor=admin, request=request, target_type="semaphore", details={"base_url": item.base_url, "proxy_url": item.proxy_url})
    db.commit()
    return {"message": item.last_test_message, "project_count": len(projects)}


@router.post("/semaphore/test")
async def test_semaphore(request: Request, db: Db, admin: SystemAdmin) -> dict[str, Any]:
    item = db.get(SemaphoreSettings, 1)
    if item is None:
        raise HTTPException(status_code=400, detail="Semaphore ist noch nicht konfiguriert.")
    try:
        projects = await semaphore_client_from_db(db).test_connection()
        item.last_test_success = True
        item.last_test_message = f"Verbindung erfolgreich; {len(projects)} Projekte gefunden."
    except (SemaphoreError, RuntimeError) as exc:
        item.last_test_success = False
        item.last_test_message = str(exc)
        item.last_tested_at = utcnow()
        record_audit(db, "semaphore_connection_test", actor=admin, request=request, success=False, details={"message": str(exc)})
        db.commit()
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    item.last_tested_at = utcnow()
    record_audit(db, "semaphore_connection_test", actor=admin, request=request, details={"project_count": len(projects)})
    db.commit()
    return {"message": item.last_test_message, "projects": projects}


@router.get("/semaphore/projects")
async def semaphore_projects(db: Db, admin: SystemAdmin) -> list[dict[str, Any]]:
    del admin
    try:
        return await semaphore_client_from_db(db).list_projects()
    except (SemaphoreError, RuntimeError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


# Projektvorlagen
@router.get("/project-templates")
def list_project_templates(db: Db, admin: SystemAdmin) -> list[dict[str, Any]]:
    del admin
    rows = db.scalars(select(ProjectTemplate).order_by(ProjectTemplate.updated_at.desc())).all()
    return [
        {
            "id": str(row.id),
            "name": row.name,
            "description": row.description,
            "source_type": row.source_type,
            "source_project_id": row.source_project_id,
            "survey_catalog": survey_catalog(row.backup_document),
            "task_templates": [item.get("name") for item in row.backup_document.get("templates", []) if isinstance(item, dict)],
            "environments": [item.get("name") for item in row.backup_document.get("environments", []) if isinstance(item, dict)],
            "updated_at": row.updated_at,
        }
        for row in rows
    ]


@router.post("/project-templates/from-semaphore", status_code=201)
async def save_project_template(payload: ProjectTemplateSave, request: Request, db: Db, admin: SystemAdmin) -> dict[str, Any]:
    try:
        backup = await semaphore_client_from_db(db).get_project_backup(payload.source_project_id)
        parse_backup(backup)
    except (SemaphoreError, RuntimeError, BackupValidationError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    row = ProjectTemplate(
        name=payload.name.strip(),
        description=payload.description.strip(),
        source_type="semaphore",
        source_project_id=payload.source_project_id,
        backup_document=backup,
        created_by_id=admin.id,
    )
    db.add(row)
    db.flush()
    record_audit(db, "project_imported", actor=admin, request=request, target_type="project_template", target_id=row.id, details={"source_project_id": payload.source_project_id})
    db.commit()
    return {"id": str(row.id), "name": row.name}


@router.post("/project-templates/upload", status_code=201)
async def upload_project_template(
    request: Request,
    db: Db,
    admin: SystemAdmin,
    file: UploadFile = File(...),
    name: str = Query(min_length=2, max_length=255),
) -> dict[str, Any]:
    raw = await file.read(10 * 1024 * 1024 + 1)
    if len(raw) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Die Backupdatei darf höchstens 10 MB groß sein.")
    try:
        document = parse_backup(json.loads(raw.decode("utf-8-sig")))
    except (UnicodeDecodeError, json.JSONDecodeError, BackupValidationError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    row = ProjectTemplate(name=name.strip(), description=f"Upload: {file.filename or 'backup.json'}", source_type="upload", backup_document=document, created_by_id=admin.id)
    db.add(row)
    db.flush()
    record_audit(db, "project_imported", actor=admin, request=request, target_type="project_template", target_id=row.id, details={"source": "upload"})
    db.commit()
    return {"id": str(row.id), "name": row.name}


# Tenant-Wizard und fehlertoleranter Restore
@router.get("/project-templates/{template_id}/resources")
def template_resources(template_id: uuid.UUID, db: Db, admin: SystemAdmin) -> dict[str, Any]:
    source = db.get(ProjectTemplate, template_id)
    if source is None:
        raise HTTPException(404, "Projektvorlage nicht gefunden.")
    import copy
    result = copy.deepcopy(source.backup_document)
    for group in result.get("environments", []):
        group.pop("password", None)
        group.pop("secrets", None)
        for field in ("json", "env"):
            group[field] = public_variables(json_object(group.get(field)))
    return {key: result.get(key, []) for key in ("environments", "repositories", "inventories", "templates")}


@router.post("/creation-jobs", status_code=201)
def create_creation_job(payload: CreationJobCreate, db: Db, admin: SystemAdmin) -> dict[str, Any]:
    existing = db.scalar(select(CreationJob).where(CreationJob.idempotency_key == payload.idempotency_key))
    if existing:
        if existing.project_template_id != payload.project_template_id:
            raise HTTPException(409, "Dieser Idempotency-Key gehört zu einer anderen Vorlage.")
        return creation_json(existing)
    if db.get(ProjectTemplate, payload.project_template_id) is None:
        raise HTTPException(status_code=404, detail="Projektvorlage nicht gefunden.")
    job = CreationJob(idempotency_key=payload.idempotency_key, project_template_id=payload.project_template_id, created_by_id=admin.id, draft_data={})
    db.add(job)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(select(CreationJob).where(CreationJob.idempotency_key == payload.idempotency_key))
        if existing is None or existing.project_template_id != payload.project_template_id:
            raise HTTPException(409, "Erstellungsvorgang kollidiert mit einem anderen Entwurf.")
        return creation_json(existing)
    return creation_json(job)


@router.get("/creation-jobs")
def list_creation_jobs(db: Db, admin: SystemAdmin) -> list[dict[str, Any]]:
    rows = db.scalars(select(CreationJob).where(CreationJob.created_by_id == admin.id).order_by(CreationJob.updated_at.desc())).all()
    return [creation_json(row) for row in rows]


@router.get("/creation-jobs/{job_id}")
def get_creation_job(job_id: uuid.UUID, db: Db, admin: SystemAdmin) -> dict[str, Any]:
    job = db.get(CreationJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Erstellungsvorgang nicht gefunden.")
    return creation_json(job)


@router.put("/creation-jobs/{job_id}")
def update_creation_job(job_id: uuid.UUID, payload: CreationJobUpdate, db: Db, admin: SystemAdmin) -> dict[str, Any]:
    job = db.scalar(select(CreationJob).where(CreationJob.id == job_id).with_for_update())
    if job is None:
        raise HTTPException(status_code=404, detail="Erstellungsvorgang nicht gefunden.")
    if job.encrypted_vault_payload or job.execution_started_at:
        raise HTTPException(409, "Ein gestarteter Vorgang kann nicht mehr geändert werden; gespeicherte Werte zur Wiederaufnahme verwenden.")
    if job.status not in {CreationStatus.DRAFT, CreationStatus.VALIDATED, CreationStatus.FAILED}:
        raise HTTPException(status_code=409, detail="Dieser Erstellungsvorgang kann nicht mehr bearbeitet werden.")
    # Drafts are persisted and returned to the browser; credentials belong in live secrets.
    draft_data = payload.draft_data.model_dump(mode="json", exclude_none=True)
    if contains_secret(draft_data):
        raise HTTPException(422, "Entwürfe dürfen keine Zugangsdaten enthalten. Secrets nach der Anlage im Projekteditor setzen.")
    job.draft_data = draft_data
    job.status = CreationStatus.DRAFT
    job.prepared_backup = None
    job.validation_result = None
    job.vault_plan = None
    job.vault_progress = None
    job.last_error = None
    db.commit()
    return creation_json(job)


@router.post("/creation-jobs/{job_id}/validate")
async def validate_creation_job(job_id: uuid.UUID, db: Db, admin: SystemAdmin) -> dict[str, Any]:
    job = db.scalar(select(CreationJob).where(CreationJob.id == job_id).with_for_update())
    if job is None or job.project_template_id is None:
        raise HTTPException(status_code=404, detail="Erstellungsvorgang nicht gefunden.")
    if job.encrypted_vault_payload or job.execution_started_at:
        raise HTTPException(409, "Ein gestarteter Vorgang darf nicht neu validiert werden.")
    if job.status not in {CreationStatus.DRAFT, CreationStatus.VALIDATED, CreationStatus.FAILED} or job.semaphore_project_id is not None:
        raise HTTPException(409, "Ein bereits gestarteter Restore darf nicht neu validiert werden.")
    source = db.get(ProjectTemplate, job.project_template_id)
    if source is None:
        raise HTTPException(status_code=409, detail="Die zugehörige Projektvorlage existiert nicht mehr.")
    enriched_draft = dict(job.draft_data)
    preset_values: list[dict[str, Any]] = []
    for raw_id in job.draft_data.get("preset_ids") or []:
        try:
            preset_id = uuid.UUID(str(raw_id))
        except ValueError:
            continue
        preset = db.scalar(select(Preset).where(Preset.id == preset_id).options(selectinload(Preset.versions)))
        if preset:
            version = next((item for item in preset.versions if item.version == preset.current_version), None)
            if version:
                preset_values.append({"name": preset.name, "values": version.values})
    enriched_draft["preset_values"] = preset_values
    try:
        prepared = prepare_backup(source.backup_document, enriched_draft)
        job.vault_plan = vault_service.prepare_plan(db, job.draft_data, prepared) if job.draft_data.get("provision_vault") else None
    except (BackupValidationError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    errors, warnings = validate_backup(prepared)
    for group in source.backup_document.get("environments", []):
        if is_defaults(str(group.get("name", ""))):
            old = json_object(group.get("json"))
            for key in TENANT_VARIABLES:
                if old.get(key) and old[key] == job.draft_data.get(key):
                    errors.append(f"{key} muss sich für den neuen Tenant von der Quelle unterscheiden.")
    slug = str(job.draft_data.get("tenant_slug", ""))
    if db.scalar(select(Tenant.id).where(Tenant.tenant_slug == slug)):
        errors.append("Die Tenant-ID ist im Portal bereits vergeben.")
    try:
        projects = await semaphore_client_from_db(db).list_projects()
        if any(item["name"].casefold() == prepared["meta"]["name"].casefold() for item in projects):
            errors.append("Ein Semaphore-Projekt mit diesem Namen existiert bereits.")
    except (SemaphoreError, RuntimeError) as exc:
        errors.append(f"Semaphore-Verbindung konnte nicht validiert werden: {exc}")
    job.prepared_backup = prepared
    job.validation_result = {"errors": errors, "warnings": warnings}
    job.status = CreationStatus.VALIDATED if not errors else CreationStatus.DRAFT
    db.commit()
    return creation_json(job)


@router.post("/creation-jobs/{job_id}/execute")
async def execute_creation_job(
    job_id: uuid.UUID, payload: CreationExecuteRequest, request: Request, db: Db, admin: SystemAdmin,
) -> dict[str, Any]:
    # A persisted lease spans commits around external calls and excludes a second
    # worker for this job. CAS protects targets against different creation jobs.
    job = db.get(CreationJob, job_id)
    if job is None:
        raise HTTPException(404, "Erstellungsvorgang nicht gefunden.")
    if job.status == CreationStatus.COMPLETED:
        return creation_json(job)
    claimed = db.execute(update(CreationJob).where(CreationJob.id == job_id,
        or_(CreationJob.execution_started_at.is_(None), CreationJob.execution_started_at < utcnow() - timedelta(minutes=15)))
        .values(execution_started_at=utcnow()).execution_options(synchronize_session=False))
    if claimed.rowcount != 1:
        raise HTTPException(409, "Dieser Vorgang wird bereits ausgeführt. Eine hängende Ausführung wird nach 15 Minuten freigegeben.")
    db.commit()
    try:
        return await _execute_creation_job(job_id, payload, request, db, admin)
    finally:
        db.rollback()
        db.execute(update(CreationJob).where(CreationJob.id == job_id).values(execution_started_at=None))
        db.commit()


async def _execute_creation_job(
    job_id: uuid.UUID,
    payload: CreationExecuteRequest,
    request: Request,
    db: Db,
    admin: SystemAdmin,
) -> dict[str, Any]:
    if not payload.confirm_project_creation:
        raise HTTPException(status_code=400, detail="Die ausdrückliche Bestätigung der Projektanlage fehlt.")
    job = db.scalar(select(CreationJob).where(CreationJob.id == job_id).with_for_update())
    if job is None:
        raise HTTPException(status_code=404, detail="Erstellungsvorgang nicht gefunden.")
    if job.status == CreationStatus.COMPLETED:
        return creation_json(job)
    if job.status == CreationStatus.RESTORING and job.restore_started_at:
        started = job.restore_started_at
        if started.tzinfo is None:
            started = started.replace(tzinfo=timezone.utc)
        if (utcnow()-started).total_seconds() < max(60, get_settings().semaphore_request_timeout_seconds * 2):
            raise HTTPException(409, "Der Restore läuft noch. Bitte vor einer Wiederaufnahme warten.")
    if not job.prepared_backup or not job.validation_result or job.validation_result.get("errors"):
        raise HTTPException(status_code=409, detail="Der Erstellungsvorgang wurde nicht erfolgreich validiert.")
    client = semaphore_client_from_db(db)
    project_name = str(job.prepared_backup["meta"]["name"])

    if job.draft_data.get("provision_vault"):
        try:
            if job.semaphore_project_id is None and job.status in {CreationStatus.VALIDATED, CreationStatus.FAILED}:
                if any(p["name"].casefold() == project_name.casefold() for p in await client.list_projects()):
                    raise HTTPException(409, "Das Zielprojekt existiert bereits; Vault-Anlage wird nicht gestartet.")
            await vault_service.provision(db, job, payload.vault_inputs)
            if not (job.vault_progress or {}).get("audit_recorded"):
                record_audit(db, "vault_objects_created", actor=admin, request=request,
                    target_type="creation_job", target_id=job.id,
                    details={"paths": [obj["path"] for obj in job.vault_plan["objects"]]})
                job.vault_progress = {**(job.vault_progress or {}), "audit_recorded": True}
                db.commit()
        except (VaultError, ValueError) as exc:
            job.last_error = str(exc)
            record_audit(db, "vault_provisioning_failed", actor=admin, request=request,
                target_type="creation_job", target_id=job.id, success=False, details={"message": str(exc)})
            db.commit()
            raise HTTPException(409 if isinstance(exc, ValueError) or getattr(exc, "conflict", False) else 502, str(exc)) from exc

    if job.semaphore_project_id is None and job.status in {CreationStatus.RESTORING, CreationStatus.VERIFICATION_REQUIRED}:
        try:
            matches = [item for item in await client.list_projects() if item["name"].casefold() == project_name.casefold()]
        except SemaphoreError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        if len(matches) == 1:
            job.semaphore_project_id = matches[0]["id"]
            job.status = CreationStatus.SEMAPHORE_CREATED
            db.commit()
        elif len(matches) > 1:
            job.last_error = "Mehrere Semaphore-Projekte mit dem erwarteten Namen gefunden; manuelle Klärung erforderlich."
            job.status = CreationStatus.VERIFICATION_REQUIRED
            db.commit()
            raise HTTPException(status_code=409, detail=job.last_error)
        elif not payload.allow_retry_after_verified_absence:
            job.status = CreationStatus.VERIFICATION_REQUIRED
            job.last_error = "Kein Projekt gefunden. Ein erneuter Restore benötigt eine separate Bestätigung."
            db.commit()
            raise HTTPException(status_code=409, detail=job.last_error)

    if job.semaphore_project_id is None:
        if job.status not in {CreationStatus.VALIDATED, CreationStatus.VERIFICATION_REQUIRED, CreationStatus.FAILED}:
            raise HTTPException(status_code=409, detail="Der Restore kann in diesem Zustand nicht gestartet werden.")
        try:
            existing = [item for item in await client.list_projects() if item["name"].casefold() == project_name.casefold()]
        except SemaphoreError as exc:
            raise HTTPException(502, str(exc)) from exc
        if existing:
            raise HTTPException(status_code=409, detail="Das Zielprojekt existiert bereits; Restore wird nicht erneut gesendet.")
        job.status = CreationStatus.RESTORING
        job.restore_started_at = utcnow()
        job.last_error = None
        db.commit()  # Zustand muss vor dem externen POST dauerhaft sein.
        try:
            response = await client.restore_project(job.prepared_backup)
            job.semaphore_response = response
            remote_id = response.get("id") or response.get("project_id")
            if isinstance(remote_id, int):
                job.semaphore_project_id = remote_id
            else:
                matches = [item for item in await client.list_projects() if item["name"].casefold() == project_name.casefold()]
                if len(matches) == 1:
                    job.semaphore_project_id = matches[0]["id"]
            if job.semaphore_project_id is None:
                job.status = CreationStatus.VERIFICATION_REQUIRED
                job.last_error = "Semaphore nahm den Restore an, aber die neue Projekt-ID konnte nicht eindeutig ermittelt werden."
                db.commit()
                raise HTTPException(status_code=409, detail=job.last_error)
            job.status = CreationStatus.SEMAPHORE_CREATED
            db.commit()
        except SemaphoreError as exc:
            job.status = CreationStatus.VERIFICATION_REQUIRED if exc.uncertain else CreationStatus.FAILED
            job.last_error = str(exc)
            db.commit()
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    if job.draft_data.get("provision_vault"):
        try:
            await vault_service.install_reader_access(job, client)
        except (SemaphoreError, ValueError) as exc:
            job.last_error = str(exc)
            record_audit(db, "vault_access_install_failed", actor=admin, request=request,
                target_type="creation_job", target_id=job.id, success=False)
            db.commit()
            raise HTTPException(502, str(exc)) from exc
        job.vault_progress = {**(job.vault_progress or {}), "access_installed": True}
        job.last_error = None
        db.commit()

    # Portalregistrierung ist wiederholbar und löscht niemals Semaphore-Ressourcen.
    db.refresh(job, with_for_update=True)
    if job.status == CreationStatus.COMPLETED:
        return creation_json(job)
    if job.tenant_id:
        tenant = db.get(Tenant, job.tenant_id)
    else:
        tenant = None
    if tenant is None:
        draft = job.draft_data
        catalog = survey_catalog(job.prepared_backup)
        selections = {plural: selected_options(draft, name) or catalog.get(name, []) for name, plural in SELECTION_FIELDS.items()}
        tenant = Tenant(
            tenant_slug=str(draft["tenant_slug"]),
            display_name=str(draft.get("display_name") or draft["tenant_slug"]),
            description=str(draft.get("description") or ""),
            application_id=next(iter(selections["application_ids"]), None),
            **selections,
            status=TenantStatus.DRAFT,
        )
        db.add(tenant)
        db.flush()
        job.tenant_id = tenant.id
    if tenant.semaphore_project is None:
        tenant.semaphore_project = SemaphoreProject(
            semaphore_project_id=job.semaphore_project_id,
            name=project_name,
            last_verified_at=utcnow(),
        )
    try:
        remote_templates = await client.list_templates(job.semaphore_project_id)
    except SemaphoreError as exc:
        raise HTTPException(502, str(exc)) from exc
    existing_ids = {item.semaphore_template_id: item for item in tenant.task_templates}
    for remote in remote_templates:
        remote_id = remote.get("id")
        if not isinstance(remote_id, int):
            continue
        item = existing_ids.get(remote_id) or TaskTemplate(tenant=tenant, semaphore_template_id=remote_id)
        item.name = str(remote.get("name") or f"Task {remote_id}")
        item.description = str(remote.get("description") or "")
        item.app = str(remote.get("app") or "ansible")
        item.survey_schema = remote.get("survey_vars") if isinstance(remote.get("survey_vars"), list) else []
        item.is_enabled = False
        db.add(item)
        db.flush()

        selected_names = set(job.draft_data.get("task_template_names") or [])
        if item.name in selected_names and job.draft_data.get("create_default_policies", True):
            try:
                rules = _default_policy_rules(item.survey_schema, job.draft_data)
            except BackupValidationError as exc:
                # A changed remote survey must never broaden the tenant's selection.
                result = dict(job.validation_result or {})
                result["warnings"] = [*(result.get("warnings") or []), f"Task {item.name} bleibt deaktiviert: {exc}"]
                job.validation_result = result
                continue
            if rules or not item.survey_schema:
                policy = item.policy or TaskPolicy(task_template_id=item.id, name=f"{item.name} · Tenant Policy")
                policy.variable_rules.clear()
                db.flush()
                for index, rule_data in enumerate(rules):
                    policy.variable_rules.append(
                        VariableRule(position=index, **{**rule_data, "rule_type": RuleType(rule_data["rule_type"])})
                    )
                policy.is_active = True
                item.policy = policy
                item.is_enabled = True

    assignments = job.draft_data.get("access_assignments") or []
    for assignment in assignments:
        if not isinstance(assignment, dict):
            continue
        user_id = _optional_uuid(assignment.get("user_id"))
        group_id = _optional_uuid(assignment.get("group_id"))
        if (user_id is None) == (group_id is None):
            continue
        if user_id and db.get(User, user_id) is None:
            continue
        if group_id and db.get(Group, group_id) is None:
            continue
        role_code = str(assignment.get("role_code") or "viewer")
        if role_code not in {"viewer", "operator", "tenant_admin"}:
            role_code = "viewer"
        if not db.scalar(select(TenantMembership.id).where(TenantMembership.tenant_id == tenant.id, TenantMembership.user_id == user_id if user_id else TenantMembership.group_id == group_id)):
            db.add(TenantMembership(tenant_id=tenant.id, user_id=user_id, group_id=group_id, role_code=role_code))
        for task in tenant.task_templates:
            if not task.is_enabled:
                continue
            if not db.scalar(select(TaskPermission.id).where(TaskPermission.task_template_id == task.id, TaskPermission.user_id == user_id if user_id else TaskPermission.group_id == group_id)):
                db.add(
                    TaskPermission(
                        task_template_id=task.id,
                        user_id=user_id,
                        group_id=group_id,
                        can_view=True,
                        can_start=role_code in {"operator", "tenant_admin"},
                        can_stop=role_code in {"operator", "tenant_admin"},
                    )
                )
    tenant.configuration_complete = bool(tenant.semaphore_project and any(task.is_enabled and task.policy for task in tenant.task_templates))
    if job.draft_data.get("activate_after_creation") and tenant.configuration_complete:
        tenant.status = TenantStatus.ACTIVE
    job.status = CreationStatus.COMPLETED
    job.encrypted_vault_payload = None
    record_audit(db, "tenant_created", actor=admin, request=request, target_type="tenant", target_id=tenant.id, details={"semaphore_project_id": job.semaphore_project_id})
    db.commit()
    return creation_json(job)


def _optional_uuid(value: Any) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(value)) if value else None
    except ValueError:
        return None


def _survey_allowed(field: dict[str, Any]) -> list[Any]:
    values = field.get("values") if isinstance(field.get("values"), list) else []
    return [item.get("value") for item in values if isinstance(item, dict) and "value" in item]


def _default_policy_rules(survey: list[dict[str, Any]], draft: dict[str, Any]) -> list[dict[str, Any]]:
    """Creates a deliberately narrow initial policy for known tenant controls only."""
    fields = {str(item.get("name")): item for item in survey if isinstance(item, dict) and item.get("name")}
    rules: list[dict[str, Any]] = []
    fixed = {
        "host_port": 0,
    }
    for name, value in fixed.items():
        if name in fields and value not in (None, ""):
            rules.append({"variable_name": name, "title": str(fields[name].get("title") or name), "help_text": str(fields[name].get("description") or "Serverseitig festgelegt"), "rule_type": "fixed", "fixed_value": value, "is_required": True})
    for name in ("application_id", "database_type", "dataset_id", "existing_environment_policy"):
        if name in fields:
            available = _survey_allowed(fields[name])
            allowed = allowed_options(draft, name, available)
            if selected_options(draft, name) is not None and not allowed:
                raise BackupValidationError(f"Keine freigegebene Survey-Auswahl für {name} vorhanden.")
            if allowed:
                selected = selected_options(draft, name)
                requested = selected[0] if selected else draft.get(name)
                rules.append({"variable_name": name, "title": str(fields[name].get("title") or name), "rule_type": "enum", "allowed_values": allowed, "default_value": requested if requested in allowed else fields[name].get("default_value") if fields[name].get("default_value") in allowed else allowed[0], "is_required": True})
    if "ttl_minutes" in fields:
        try:
            default_ttl = int(draft.get("ttl_minutes") or 60)
        except (TypeError, ValueError):
            default_ttl = 60
        default_ttl = min(1440, max(5, default_ttl))
        rules.append({"variable_name": "ttl_minutes", "title": str(fields["ttl_minutes"].get("title") or "Laufzeit"), "help_text": str(fields["ttl_minutes"].get("description") or "Laufzeit in Minuten"), "rule_type": "integer_range", "minimum": 5, "maximum": 1440, "default_value": default_ttl, "is_required": True})
    for name in ("application_release_id", "pdf_api_release_id"):
        if name in fields:
            allowed = _survey_allowed(fields[name])
            default = fields[name].get("default_value") or "latest"
            rule = {"variable_name": name, "title": str(fields[name].get("title") or name), "is_required": False}
            if allowed:
                rule.update(rule_type="enum", allowed_values=allowed, default_value=default if default in allowed else allowed[0])
            else:
                rule.update(rule_type="string", regex_pattern=r"^[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}$", max_length=128, default_value=default)
            rules.append(rule)
    if "send_deployment_mail" in fields:
        rules.append({"variable_name": "send_deployment_mail", "title": str(fields["send_deployment_mail"].get("title") or "Deployment-Mail senden"), "rule_type": "boolean", "default_value": False, "is_required": False})
    if "mail_user" in fields:
        rules.append({"variable_name": "mail_user", "title": str(fields["mail_user"].get("title") or "Mail-Empfänger"), "rule_type": "string", "regex_pattern": r"^$|^[^\s@]+@[^\s@]+\.[^\s@]+$", "max_length": 254, "default_value": "", "is_required": False})
    return rules


# Tenant-Verwaltung
@router.get("/tenants")
def list_tenants(db: Db, admin: SystemAdmin) -> list[dict[str, Any]]:
    del admin
    rows = db.scalars(
        select(Tenant).where(Tenant.status != TenantStatus.DELETED).options(selectinload(Tenant.semaphore_project)).order_by(Tenant.display_name)
    ).all()
    return [tenant_json(row) for row in rows]


@router.get("/tenants/{tenant_id}")
def get_tenant(tenant_id: uuid.UUID, db: Db, admin: SystemAdmin) -> dict[str, Any]:
    del admin
    tenant = db.scalar(
        select(Tenant)
        .where(Tenant.id == tenant_id, Tenant.status != TenantStatus.DELETED)
        .options(
            selectinload(Tenant.semaphore_project),
            selectinload(Tenant.memberships).selectinload(TenantMembership.user),
            selectinload(Tenant.memberships).selectinload(TenantMembership.group),
            selectinload(Tenant.task_templates).selectinload(TaskTemplate.policy),
        )
    )
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant nicht gefunden.")
    return tenant_json(tenant, detail=True)


@router.patch("/tenants/{tenant_id}")
def update_tenant(tenant_id: uuid.UUID, payload: TenantUpdate, request: Request, db: Db, admin: SystemAdmin) -> dict[str, Any]:
    tenant = db.get(Tenant, tenant_id)
    if tenant is None or tenant.status == TenantStatus.DELETED:
        raise HTTPException(status_code=404, detail="Tenant nicht gefunden.")
    changes = payload.model_dump(exclude_none=True)
    for key, value in changes.items():
        if key == "status":
            tenant.status = TenantStatus(value)
        else:
            setattr(tenant, key, value)
    if tenant.status == TenantStatus.ACTIVE:
        has_enabled_policy = any(task.is_enabled and task.policy and task.policy.is_active for task in tenant.task_templates)
        if not tenant.semaphore_project or not has_enabled_policy:
            raise HTTPException(status_code=409, detail="Aktivierung erfordert ein Semaphore-Projekt und mindestens einen freigegebenen Task mit aktiver Policy.")
        tenant.configuration_complete = True
    record_audit(db, "tenant_updated", actor=admin, request=request, target_type="tenant", target_id=tenant.id, details=changes)
    db.commit()
    return tenant_json(tenant)


@router.delete("/tenants/{tenant_id}")
def delete_tenant(tenant_id: uuid.UUID, request: Request, db: Db, admin: SystemAdmin, confirm: str = Query(...)) -> dict[str, str]:
    tenant = db.get(Tenant, tenant_id)
    if tenant is None or tenant.status == TenantStatus.DELETED:
        raise HTTPException(status_code=404, detail="Tenant nicht gefunden.")
    if confirm != tenant.tenant_slug:
        raise HTTPException(status_code=400, detail="Bestätigung muss exakt der Tenant-ID entsprechen.")
    tenant.status = TenantStatus.DELETED
    tenant.deleted_at = utcnow()
    tenant.configuration_complete = False
    record_audit(
        db,
        "tenant_deleted",
        actor=admin,
        request=request,
        target_type="tenant",
        target_id=tenant.id,
        details={"remote_project_preserved": True, "semaphore_project_id": tenant.semaphore_project.semaphore_project_id if tenant.semaphore_project else None},
    )
    db.commit()
    return {"message": "Portal-Tenant wurde entfernt; das Semaphore-Projekt blieb erhalten."}


@router.post("/tenants/{tenant_id}/memberships", status_code=201)
def add_tenant_membership(tenant_id: uuid.UUID, payload: TenantMembershipInput, request: Request, db: Db, admin: SystemAdmin) -> dict[str, Any]:
    tenant = db.get(Tenant, tenant_id)
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant nicht gefunden.")
    if payload.user_id and db.get(User, payload.user_id) is None:
        raise HTTPException(status_code=404, detail="Benutzer nicht gefunden.")
    if payload.group_id and db.get(Group, payload.group_id) is None:
        raise HTTPException(status_code=404, detail="Gruppe nicht gefunden.")
    duplicate = db.scalar(
        select(TenantMembership.id).where(
            TenantMembership.tenant_id == tenant_id,
            TenantMembership.user_id == payload.user_id if payload.user_id else TenantMembership.group_id == payload.group_id,
        )
    )
    if duplicate:
        raise HTTPException(status_code=409, detail="Diese Zuweisung existiert bereits.")
    row = TenantMembership(tenant_id=tenant_id, user_id=payload.user_id, group_id=payload.group_id, role_code=payload.role_code)
    db.add(row)
    db.flush()
    record_audit(db, "permission_changed", actor=admin, request=request, target_type="tenant", target_id=tenant_id, details=payload.model_dump(mode="json"))
    db.commit()
    return {"id": str(row.id)}


@router.delete("/tenants/{tenant_id}/memberships/{membership_id}")
def remove_tenant_membership(tenant_id: uuid.UUID, membership_id: uuid.UUID, request: Request, db: Db, admin: SystemAdmin) -> dict[str, str]:
    row = db.scalar(select(TenantMembership).where(TenantMembership.id == membership_id, TenantMembership.tenant_id == tenant_id))
    if row is None:
        raise HTTPException(status_code=404, detail="Zuweisung nicht gefunden.")
    db.delete(row)
    record_audit(db, "permission_changed", actor=admin, request=request, target_type="tenant", target_id=tenant_id, details={"removed_membership_id": str(membership_id)})
    db.commit()
    return {"message": "Zuweisung wurde entfernt."}


@router.post("/tenants/{tenant_id}/check")
async def check_tenant(tenant_id: uuid.UUID, request: Request, db: Db, admin: SystemAdmin) -> dict[str, Any]:
    tenant = db.get(Tenant, tenant_id)
    if tenant is None or tenant.semaphore_project is None:
        raise HTTPException(status_code=404, detail="Tenant oder Semaphore-Projekt nicht gefunden.")
    try:
        projects = await semaphore_client_from_db(db).list_projects()
        remote = next((item for item in projects if item["id"] == tenant.semaphore_project.semaphore_project_id), None)
        if remote is None:
            raise SemaphoreError("Die gespeicherte Semaphore-Projekt-ID existiert nicht mehr.")
        tenant.semaphore_project.name = remote["name"]
        tenant.semaphore_project.last_verified_at = utcnow()
        tenant.semaphore_project.last_error = None
    except (SemaphoreError, RuntimeError) as exc:
        tenant.semaphore_project.last_error = str(exc)
        record_audit(db, "tenant_connection_checked", actor=admin, request=request, target_type="tenant", target_id=tenant.id, success=False, details={"message": str(exc)})
        db.commit()
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    record_audit(db, "tenant_connection_checked", actor=admin, request=request, target_type="tenant", target_id=tenant.id)
    db.commit()
    return {"message": "Semaphore-Projekt ist erreichbar.", "project": remote}


@router.post("/tenants/{tenant_id}/sync-templates")
async def sync_tenant_templates(tenant_id: uuid.UUID, request: Request, db: Db, admin: SystemAdmin) -> list[dict[str, Any]]:
    tenant = db.get(Tenant, tenant_id)
    if tenant is None or tenant.semaphore_project is None:
        raise HTTPException(status_code=404, detail="Tenant oder Semaphore-Projekt nicht gefunden.")
    try:
        remote = await semaphore_client_from_db(db).list_templates(tenant.semaphore_project.semaphore_project_id)
    except (SemaphoreError, RuntimeError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    by_id = {item.semaphore_template_id: item for item in tenant.task_templates}
    remote_ids: set[int] = set()
    for source in remote:
        remote_id = source.get("id")
        if not isinstance(remote_id, int):
            continue
        remote_ids.add(remote_id)
        item = by_id.get(remote_id) or TaskTemplate(tenant_id=tenant.id, semaphore_template_id=remote_id, is_enabled=False)
        item.name = str(source.get("name") or f"Task {remote_id}")
        item.description = str(source.get("description") or "")
        item.app = str(source.get("app") or "ansible")
        item.survey_schema = source.get("survey_vars") if isinstance(source.get("survey_vars"), list) else []
        db.add(item)
    for remote_id, item in by_id.items():
        if remote_id not in remote_ids:
            item.is_enabled = False
    record_audit(db, "task_templates_synced", actor=admin, request=request, target_type="tenant", target_id=tenant.id, details={"count": len(remote_ids)})
    db.commit()
    return [task_template_json(item) for item in tenant.task_templates]


@router.get("/tenants/{tenant_id}/export")
def export_tenant(tenant_id: uuid.UUID, db: Db, admin: SystemAdmin) -> dict[str, Any]:
    del admin
    tenant = db.scalar(
        select(Tenant).where(Tenant.id == tenant_id).options(selectinload(Tenant.task_templates).selectinload(TaskTemplate.policy).selectinload(TaskPolicy.variable_rules))
    )
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant nicht gefunden.")
    return {
        "schema_version": 1,
        "tenant": tenant_json(tenant),
        "task_policies": [policy_json(task.policy) for task in tenant.task_templates if task.policy],
        "notice": "Export enthält keine Semaphore-Tokens oder geheimen Preset-Werte.",
    }


def policy_json(policy: TaskPolicy | None) -> dict[str, Any] | None:
    if policy is None:
        return None
    return {
        "id": str(policy.id),
        "name": policy.name,
        "version": policy.version,
        "is_active": policy.is_active,
        "rules": [
            {
                "id": str(rule.id),
                "variable_name": rule.variable_name,
                "title": rule.title,
                "help_text": rule.help_text,
                "rule_type": rule.rule_type.value,
                "fixed_value": rule.fixed_value,
                "default_value": rule.default_value,
                "allowed_values": rule.allowed_values,
                "minimum": rule.minimum,
                "maximum": rule.maximum,
                "regex_pattern": rule.regex_pattern,
                "max_length": rule.max_length,
                "is_required": rule.is_required,
                "position": rule.position,
            }
            for rule in policy.variable_rules
        ],
    }


@router.get("/task-templates/{template_id}/policy")
def get_policy(template_id: uuid.UUID, db: Db, admin: SystemAdmin) -> dict[str, Any] | None:
    del admin
    template = db.scalar(select(TaskTemplate).where(TaskTemplate.id == template_id).options(selectinload(TaskTemplate.policy).selectinload(TaskPolicy.variable_rules)))
    if template is None:
        raise HTTPException(status_code=404, detail="Task Template nicht gefunden.")
    return policy_json(template.policy)


@router.put("/task-templates/{template_id}/policy")
def save_policy(template_id: uuid.UUID, payload: TaskPolicyInput, request: Request, db: Db, admin: SystemAdmin) -> dict[str, Any]:
    if any(rule.variable_name in TENANT_VARIABLES for rule in payload.rules):
        raise HTTPException(422, "Tenant/Scope werden ausschließlich in Semaphore-Defaults gepflegt.")
    template = db.scalar(select(TaskTemplate).where(TaskTemplate.id == template_id).options(selectinload(TaskTemplate.policy).selectinload(TaskPolicy.variable_rules)))
    if template is None:
        raise HTTPException(status_code=404, detail="Task Template nicht gefunden.")
    survey_names = {item.get("name") for item in template.survey_schema if isinstance(item, dict)}
    unknown = [rule.variable_name for rule in payload.rules if rule.variable_name not in survey_names]
    if unknown:
        raise HTTPException(status_code=422, detail=f"Variablen fehlen im Semaphore-Survey: {', '.join(unknown)}")
    policy = template.policy or TaskPolicy(task_template_id=template.id, name=payload.name)
    if template.policy:
        policy.version += 1
        policy.variable_rules.clear()
        db.flush()
    policy.name = payload.name
    policy.is_active = payload.is_active
    for data in payload.rules:
        policy.variable_rules.append(VariableRule(**data.model_dump()))
    template.policy = policy
    template.is_enabled = payload.is_active
    db.add(policy)
    record_audit(db, "task_policy_changed", actor=admin, request=request, target_type="task_template", target_id=template.id, details={"version": policy.version, "rule_count": len(payload.rules)})
    db.commit()
    return policy_json(policy) or {}


@router.get("/task-templates/{template_id}/permissions")
def list_task_permissions(template_id: uuid.UUID, db: Db, admin: SystemAdmin) -> list[dict[str, Any]]:
    del admin
    rows = db.scalars(select(TaskPermission).where(TaskPermission.task_template_id == template_id)).all()
    return [
        {
            "id": str(row.id),
            "user_id": str(row.user_id) if row.user_id else None,
            "group_id": str(row.group_id) if row.group_id else None,
            "can_view": row.can_view,
            "can_start": row.can_start,
            "can_stop": row.can_stop,
        }
        for row in rows
    ]


@router.post("/task-templates/{template_id}/permissions", status_code=201)
def add_task_permission(template_id: uuid.UUID, payload: TaskPermissionInput, request: Request, db: Db, admin: SystemAdmin) -> dict[str, Any]:
    if db.get(TaskTemplate, template_id) is None:
        raise HTTPException(status_code=404, detail="Task Template nicht gefunden.")
    duplicate = db.scalar(
        select(TaskPermission.id).where(
            TaskPermission.task_template_id == template_id,
            TaskPermission.user_id == payload.user_id if payload.user_id else TaskPermission.group_id == payload.group_id,
        )
    )
    if duplicate:
        raise HTTPException(status_code=409, detail="Diese Task-Berechtigung existiert bereits.")
    row = TaskPermission(task_template_id=template_id, **payload.model_dump())
    db.add(row)
    db.flush()
    record_audit(db, "permission_changed", actor=admin, request=request, target_type="task_template", target_id=template_id, details=payload.model_dump(mode="json"))
    db.commit()
    return {"id": str(row.id)}


@router.delete("/task-templates/{template_id}/permissions/{permission_id}")
def remove_task_permission(template_id: uuid.UUID, permission_id: uuid.UUID, request: Request, db: Db, admin: SystemAdmin) -> dict[str, str]:
    row = db.scalar(select(TaskPermission).where(TaskPermission.id == permission_id, TaskPermission.task_template_id == template_id))
    if row is None:
        raise HTTPException(status_code=404, detail="Task-Berechtigung nicht gefunden.")
    db.delete(row)
    record_audit(db, "permission_changed", actor=admin, request=request, target_type="task_template", target_id=template_id, details={"removed_permission_id": str(permission_id)})
    db.commit()
    return {"message": "Task-Berechtigung wurde entfernt."}


# Presets, Tasks, Audit
@router.get("/presets")
def list_presets(db: Db, admin: SystemAdmin) -> list[dict[str, Any]]:
    del admin
    rows = db.scalars(select(Preset).options(selectinload(Preset.versions)).order_by(Preset.category, Preset.name)).all()
    return [
        {
            "id": str(row.id),
            "name": row.name,
            "category": row.category,
            "description": row.description,
            "current_version": row.current_version,
            "is_builtin": row.is_builtin,
            "values": next((version.values for version in row.versions if version.version == row.current_version), {}),
        }
        for row in rows
    ]


@router.post("/presets", status_code=201)
def create_preset(payload: PresetInput, request: Request, db: Db, admin: SystemAdmin) -> dict[str, Any]:
    if contains_secret(payload.values):
        raise HTTPException(status_code=422, detail="Preset enthält einen potentiellen Secret-Schlüssel. Zugangsdaten gehören in Vault/Semaphore Key Store.")
    if db.scalar(select(Preset.id).where(func.lower(Preset.name) == payload.name.lower())):
        raise HTTPException(status_code=409, detail="Presetname ist bereits vergeben.")
    preset = Preset(name=payload.name, category=payload.category, description=payload.description, is_builtin=False)
    preset.versions.append(PresetVersion(version=1, values=payload.values, created_by_id=admin.id))
    db.add(preset)
    db.flush()
    record_audit(db, "preset_created", actor=admin, request=request, target_type="preset", target_id=preset.id)
    db.commit()
    return {"id": str(preset.id), "version": 1}


@router.put("/presets/{preset_id}")
def update_preset(preset_id: uuid.UUID, payload: PresetInput, request: Request, db: Db, admin: SystemAdmin) -> dict[str, Any]:
    preset = db.get(Preset, preset_id)
    if preset is None:
        raise HTTPException(status_code=404, detail="Preset nicht gefunden.")
    if preset.is_builtin:
        raise HTTPException(status_code=409, detail="Integrierte Presets können nicht überschrieben werden; bitte eine Kopie anlegen.")
    if contains_secret(payload.values):
        raise HTTPException(status_code=422, detail="Preset enthält einen potentiellen Secret-Schlüssel.")
    preset.name = payload.name
    preset.category = payload.category
    preset.description = payload.description
    preset.current_version += 1
    preset.versions.append(PresetVersion(version=preset.current_version, values=payload.values, created_by_id=admin.id))
    record_audit(db, "preset_version_created", actor=admin, request=request, target_type="preset", target_id=preset.id, details={"version": preset.current_version})
    db.commit()
    return {"id": str(preset.id), "version": preset.current_version}


@router.get("/task-runs")
async def admin_task_runs(db: Db, admin: SystemAdmin, limit: int = Query(default=100, ge=1, le=500)) -> list[dict[str, Any]]:
    del admin
    rows = db.scalars(select(TaskRun).order_by(TaskRun.started_at.desc()).limit(limit)).all()
    from app.routers.portal import refresh_runs
    await refresh_runs(db, list(rows))
    return [
        {
            "id": str(row.id),
            "tenant": row.tenant.display_name,
            "tenant_id": str(row.tenant_id),
            "task_template": row.task_template.name,
            "started_by": row.started_by.display_name,
            "sync_error": getattr(row, "sync_error", None),
            "semaphore_task_id": row.semaphore_task_id,
            "status": row.status.value,
            "started_at": row.started_at,
            "finished_at": row.finished_at,
        }
        for row in rows
    ]


@router.get("/audit")
def audit_log(
    db: Db,
    admin: SystemAdmin,
    limit: int = Query(default=100, ge=1, le=500),
    event_type: str | None = None,
) -> list[dict[str, Any]]:
    del admin
    query = select(AuditEvent).order_by(AuditEvent.occurred_at.desc()).limit(limit)
    if event_type:
        query = query.where(AuditEvent.event_type == event_type)
    return [
        {
            "id": str(row.id),
            "occurred_at": row.occurred_at,
            "actor_user_id": str(row.actor_user_id) if row.actor_user_id else None,
            "event_type": row.event_type,
            "target_type": row.target_type,
            "target_id": row.target_id,
            "details": row.details,
            "success": row.success,
        }
        for row in db.scalars(query)
    ]
