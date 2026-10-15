"""Explicit administrator operations on live Semaphore projects."""
from __future__ import annotations

import json
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from app.audit import record_audit
from app.dependencies import Db, SystemAdmin
from app.models import SemaphoreProject, TenantStatus
from app.project_backup import BackupValidationError, TENANT_VARIABLES, is_defaults, json_object, preserve_private, public_variables, validate_tenant_values
from app.security import stable_digest
from app.services import contains_secret, semaphore_client_from_db
from app.semaphore_client import SemaphoreError

router = APIRouter(prefix="/admin/semaphore/projects", tags=["Semaphore-Projekte"])


class ProjectInput(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    alert: bool = False
    alert_chat: str | None = None
    max_parallel_tasks: int = Field(default=0, ge=0)


class ProjectChange(ProjectInput):
    revision: str


class DeleteProject(BaseModel):
    confirm_name: str
    revision: str


class SecretInput(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    type: Literal["env", "var"] = "env"
    operation: Literal["create", "update", "delete"] = "create"
    id: int | None = None
    secret: str | None = None


class ResourceInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    revision: str | None = None
    values: dict[str, Any]
    secrets: list[SecretInput] = Field(default_factory=list)
    key_secret: str | None = None
    key_login: str | None = None
    key_passphrase: str | None = None


FIELDS = {
    "keys": {"name", "type"},
    "environment": {"name", "json", "env"},
    "repositories": {"name", "git_url", "git_branch", "ssh_key_id"},
    "inventory": {"name", "inventory", "type", "ssh_key_id", "become_key_id", "repository_id"},
    "templates": {"name", "description", "app", "playbook", "repository_id", "inventory_id", "environment_id", "environment_ids", "survey_vars", "arguments", "allow_override_args_in_task", "allow_override_branch_in_task", "git_branch", "type", "view_id", "vault_key_id", "build_template_id", "start_version", "suppress_success_alerts", "suppress_error_alerts", "autorun", "working_directory", "task_params", "runner_tag", "executor_image", "allow_parallel_tasks", "vaults", "jwt_params"},
}


def revision(value: Any) -> str:
    return stable_digest(json.dumps(value, sort_keys=True, default=str)).hex()


def public_resource(kind: str, item: dict[str, Any]) -> dict[str, Any]:
    values = {key: value for key, value in item.items() if key in FIELDS[kind]}
    if kind == "environment":
        for key in ("json", "env"):
            values[key] = public_variables(json_object(item.get(key)))
    return {"id": item.get("id"), "revision": revision(item), "values": values,
            "secrets": [{"id": x.get("id"), "name": x.get("name"), "type": x.get("type")} for x in item.get("secrets") or []]}


def check_revision(expected: str | None, actual: Any) -> None:
    if expected != revision(actual):
        raise HTTPException(409, "Das Objekt wurde geändert. Bitte neu laden und Änderungen erneut prüfen.")


@router.post("", status_code=201)
async def create_project(payload: ProjectInput, request: Request, db: Db, admin: SystemAdmin):
    try:
        remote = await semaphore_client_from_db(db).create_project(payload.model_dump())
    except (SemaphoreError, RuntimeError) as exc:
        raise HTTPException(502, str(exc)) from exc
    record_audit(db, "semaphore_project_created", actor=admin, request=request, target_id=remote["id"])
    db.commit()
    return remote


@router.get("/{project_id}")
async def project_detail(project_id: int, db: Db, admin: SystemAdmin):
    try:
        remote = await semaphore_client_from_db(db).get_project(project_id)
        return {"project": remote, "revision": revision(remote)}
    except (SemaphoreError, RuntimeError) as exc:
        raise HTTPException(502, str(exc)) from exc


@router.put("/{project_id}")
async def update_project(project_id: int, payload: ProjectChange, request: Request, db: Db, admin: SystemAdmin):
    try:
        client = semaphore_client_from_db(db)
        remote = await client.get_project(project_id)
        check_revision(payload.revision, remote)
        await client.update_project(project_id, {**remote, **payload.model_dump(exclude={"revision"}), "id": project_id})
        link = db.scalar(select(SemaphoreProject).where(SemaphoreProject.semaphore_project_id == project_id))
        if link:
            link.name = payload.name
        record_audit(db, "semaphore_project_updated", actor=admin, request=request, target_id=project_id)
        db.commit()
        return {"message": "Projekt gespeichert."}
    except (SemaphoreError, RuntimeError) as exc:
        raise HTTPException(502, str(exc)) from exc


@router.delete("/{project_id}")
async def delete_project(project_id: int, payload: DeleteProject, request: Request, db: Db, admin: SystemAdmin):
    try:
        client = semaphore_client_from_db(db)
        remote = await client.get_project(project_id)
        check_revision(payload.revision, remote)
        if payload.confirm_name != remote["name"]:
            raise HTTPException(400, "Zur Löschung den aktuellen Projektnamen exakt eingeben.")
        await client.delete_project(project_id)
        link = db.scalar(select(SemaphoreProject).where(SemaphoreProject.semaphore_project_id == project_id))
        if link:
            if link.tenant.status != TenantStatus.DELETED:
                link.tenant.status = TenantStatus.INACTIVE
            link.tenant.configuration_complete = False
            link.last_error = "Semaphore-Projekt wurde gelöscht."
        record_audit(db, "semaphore_project_deleted", actor=admin, request=request, target_id=project_id)
        db.commit()
        return {"message": "Semaphore-Projekt gelöscht. Bereits laufende Deployments werden dadurch nicht entfernt."}
    except (SemaphoreError, RuntimeError) as exc:
        raise HTTPException(502, str(exc)) from exc


@router.get("/{project_id}/resources/{kind}")
async def list_resources(project_id: int, kind: str, db: Db, admin: SystemAdmin):
    if kind not in FIELDS:
        raise HTTPException(404, "Unbekannter Ressourcentyp.")
    try:
        client = semaphore_client_from_db(db)
        items = await client.list_resources(project_id, kind)
        # Use the same detail representation for revision tokens and updates.
        return [public_resource(kind, await client.get_resource(project_id, kind, item["id"])) for item in items]
    except (SemaphoreError, RuntimeError, BackupValidationError) as exc:
        raise HTTPException(502, str(exc)) from exc


async def save_resource(project_id: int, kind: str, payload: ResourceInput, request: Request, db: Db, admin: SystemAdmin, resource_id: int | None = None):
    if kind not in FIELDS:
        raise HTTPException(404, "Unbekannter Ressourcentyp.")
    if set(payload.values) - FIELDS[kind]:
        raise HTTPException(422, "Unbekannte Ressourcenfelder.")
    try:
        client = semaphore_client_from_db(db)
        current = await client.get_resource(project_id, kind, resource_id) if resource_id else {}
        if resource_id:
            check_revision(payload.revision, current)
        values = {key: value for key, value in current.items() if key in FIELDS[kind]}
        values.update(payload.values)
        if not isinstance(values.get("name"), str) or not values["name"].strip():
            raise HTTPException(422, "Name fehlt.")
        if kind == "environment":
            for preserved in ("secret_storage_id", "secret_storage_key_prefix"):
                if preserved in current:
                    values[preserved] = current[preserved]
            for field in ("json", "env"):
                incoming = json_object(values.get(field))
                if contains_secret(incoming):
                    raise HTTPException(422, "Geheime Werte über das separate Secret-Feld setzen.")
                if is_defaults(values["name"]):
                    if field == "json":
                        validate_tenant_values(incoming)
                    elif TENANT_VARIABLES.intersection(incoming):
                        raise HTTPException(422, "Tenant und Scope gehören in die Extra Variables von Semaphore-Defaults.")
                elif TENANT_VARIABLES.intersection(incoming):
                    raise HTTPException(422, "Tenant und Scope ausschließlich in Semaphore-Defaults verwalten.")
                values[field] = json.dumps(preserve_private(json_object(current.get(field)), incoming))
            if is_defaults(str(current.get("name", ""))) and not is_defaults(values["name"]):
                raise HTTPException(422, "Semaphore-Defaults darf nicht umbenannt werden.")
            if current.get("password"):
                values["password"] = current["password"]
            if payload.secrets:
                existing_secrets = {(s.get("id"), s.get("name"), s.get("type")) for s in current.get("secrets") or []}
                for secret in payload.secrets:
                    if secret.name in TENANT_VARIABLES:
                        raise HTTPException(422, "Tenant und Scope dürfen keine geheimen Overrides sein.")
                    if secret.operation != "delete" and not secret.secret:
                        raise HTTPException(422, "Neuer Secret-Wert fehlt.")
                    if secret.operation != "create" and (secret.id, secret.name, secret.type) not in existing_secrets:
                        raise HTTPException(422, "Das Secret gehört nicht zur ausgewählten Gruppe.")
                values["secrets"] = [secret.model_dump(exclude_none=True) for secret in payload.secrets]
            peers = await client.list_resources(project_id, "environment")
            if is_defaults(values["name"]) and any(x.get("id") != resource_id and is_defaults(str(x.get("name", ""))) for x in peers):
                raise HTTPException(409, "Das Projekt besitzt bereits Semaphore-Defaults.")
            link = db.scalar(select(SemaphoreProject).where(SemaphoreProject.semaphore_project_id == project_id))
            if is_defaults(values["name"]) and link:
                slug = json.loads(values["json"])["tenant_slug"]
                from app.models import Tenant
                if db.scalar(select(Tenant.id).where(Tenant.tenant_slug == slug, Tenant.id != link.tenant_id)):
                    raise HTTPException(409, "Tenant-ID im Portal bereits vergeben.")
                link.tenant.tenant_slug = slug
        if kind == "keys":
            if values.get("type") not in {"none", "ssh", "login_password"}:
                raise HTTPException(422, "Key-Typ muss none, ssh oder login_password sein.")
            if payload.key_secret:
                values["override_secret"] = True
                if values["type"] == "ssh":
                    values["ssh"] = {"private_key": payload.key_secret, "login": payload.key_login if payload.key_login is not None else (current.get("ssh") or {}).get("login", ""), "passphrase": payload.key_passphrase or ""}
                elif values["type"] == "login_password":
                    values["login_password"] = {"password": payload.key_secret, "login": payload.key_login or ""}
            elif (not resource_id or current.get("type") != values["type"]) and values["type"] != "none":
                raise HTTPException(422, "Für einen neuen Zugang ist ein geheimer Wert erforderlich.")
            else:
                values["override_secret"] = False
        if kind == "templates":
            surveys = values.get("survey_vars") or []
            if not isinstance(surveys, list) or any(not isinstance(item, dict) for item in surveys):
                raise HTTPException(422, "survey_vars muss eine Liste von Survey-Feldern sein.")
            if any(item.get("name") in TENANT_VARIABLES for item in surveys):
                raise HTTPException(422, "Tenant und Scope dürfen nicht in der Survey stehen.")
        values["project_id"] = project_id
        if resource_id:
            values["id"] = resource_id
        await client.save_resource(project_id, kind, values, resource_id)
        if kind == "templates" and resource_id:
            from app.models import TaskTemplate
            task = db.scalar(select(TaskTemplate).join(TaskTemplate.tenant).join(SemaphoreProject).where(SemaphoreProject.semaphore_project_id == project_id, TaskTemplate.semaphore_template_id == resource_id))
            if task:
                task.name = str(values["name"])
                task.description = str(values.get("description") or "")
                task.survey_schema = values.get("survey_vars") or []
                task.is_enabled = False
                if task.policy:
                    task.policy.is_active = False
        record_audit(db, "semaphore_resource_saved", actor=admin, request=request, target_id=project_id, details={"kind": kind, "resource_id": resource_id})
        db.commit()
        return {"message": "Ressource gespeichert."}
    except BackupValidationError as exc:
        raise HTTPException(422, str(exc)) from exc
    except (SemaphoreError, RuntimeError) as exc:
        raise HTTPException(502, str(exc)) from exc


@router.post("/{project_id}/resources/{kind}", status_code=201)
async def add_resource(project_id: int, kind: str, payload: ResourceInput, request: Request, db: Db, admin: SystemAdmin):
    return await save_resource(project_id, kind, payload, request, db, admin)


@router.put("/{project_id}/resources/{kind}/{resource_id}")
async def update_resource(project_id: int, kind: str, resource_id: int, payload: ResourceInput, request: Request, db: Db, admin: SystemAdmin):
    return await save_resource(project_id, kind, payload, request, db, admin, resource_id)
