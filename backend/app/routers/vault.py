from __future__ import annotations

import copy
import uuid
from datetime import timedelta, timezone

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import select

from app.audit import record_audit
from app.dependencies import Db, SystemAdmin
from app.models import CreationJob, utcnow
from app.schemas import VaultResolveInput, VaultSettingsInput
from app.vault_catalog import load_catalog
from app.vault_client import VaultClient, VaultError
from app.vault_service import configuration, current_owned, execution_configuration, public_configuration, save_configuration

router = APIRouter(prefix="/admin", tags=["Vault"])


@router.get("/vault")
def get_vault(db: Db, admin: SystemAdmin):
    return public_configuration(db)


@router.get("/vault/catalog")
def get_catalog(db: Db, admin: SystemAdmin):
    return load_catalog(db).model_dump()


@router.put("/vault")
def put_vault(payload: VaultSettingsInput, request: Request, db: Db, admin: SystemAdmin):
    try:
        save_configuration(db, payload)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    record_audit(db, "vault_configuration_updated", actor=admin, request=request)
    db.commit()
    return public_configuration(db)


@router.post("/vault/test")
async def test_vault(db: Db, admin: SystemAdmin):
    config = configuration(db)
    if not config or not config.get("writer_role_id") or not config.get("writer_secret_id"):
        raise HTTPException(409, "Vault-Schreibzugang zuerst konfigurieren.")
    try:
        await VaultClient(config).login()
    except (VaultError, ValueError) as exc:
        raise HTTPException(502, str(exc)) from exc
    return {"message": "Vault erreichbar; Schreib-AppRole angemeldet. Objektberechtigungen werden bei der Anlage geprüft."}


@router.post("/creation-jobs/{job_id}/vault/resolve")
async def resolve_vault(job_id: uuid.UUID, payload: VaultResolveInput, request: Request, db: Db, admin: SystemAdmin):
    job = db.scalar(select(CreationJob).where(CreationJob.id == job_id).with_for_update())
    if job is None:
        raise HTTPException(404, "Erstellungsvorgang nicht gefunden.")
    if job.execution_started_at:
        started = job.execution_started_at
        if started.tzinfo is None:
            started = started.replace(tzinfo=timezone.utc)
        if started > utcnow() - timedelta(minutes=15):
            raise HTTPException(409, "Ausführung läuft noch; eine hängende Ausführung wird nach 15 Minuten freigegeben.")
        job.execution_started_at = None
    progress = copy.deepcopy(job.vault_progress or {"objects": {}})
    state = progress["objects"].get(payload.path)
    if not payload.confirm_checked_in_vault or not state or state["state"] not in {"uncertain", "writing"}:
        raise HTTPException(409, "Eine ausdrückliche Prüfung des unklaren Vault-Objekts ist erforderlich.")
    try:
        client = VaultClient(execution_configuration(db, job))
        await client.login()
        metadata = await client.metadata(payload.path)
        if payload.decision == "absent":
            if metadata is not None:
                raise ValueError("Vault-Objekt ist vorhanden. Abwesenheit kann nicht bestätigt werden.")
            progress["objects"][payload.path] = {"state": "pending"}
        else:
            if not current_owned(metadata, 1):
                raise ValueError("Die erwartete unveränderte erste Vault-Version liegt nicht vor.")
            progress["objects"][payload.path] = {"state": "created", "version": 1,
                "created_time": metadata["versions"]["1"]["created_time"]}
    except (ValueError, VaultError) as exc:
        raise HTTPException(409, str(exc)) from exc
    job.vault_progress = progress
    job.last_error = None
    record_audit(db, "vault_outcome_manually_verified", actor=admin, request=request,
        target_type="creation_job", target_id=job.id, details={"path": payload.path, "decision": payload.decision})
    db.commit()
    return {"message": "Prüfergebnis gespeichert. Vorgang kann fortgesetzt werden."}
