from __future__ import annotations

import hashlib
import json
import uuid
from datetime import timedelta, timezone
from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, SecretStr
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app import credential_service as service
from app.audit import record_audit
from app.dependencies import Db, SystemAdmin
from app.models import CredentialProfile, CredentialUse, CreationJob, CreationStatus, utcnow
from app.semaphore_client import SemaphoreError
from app.services import semaphore_client_from_db
from app.vault_client import VaultError, safe_path

router = APIRouter(prefix="/admin/credentials", tags=["Zugangsprofile"])


class ConnectionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    base_url: str = Field(max_length=1000)
    namespace: str = Field(default="", max_length=255)
    kv_mount: str = Field(default="kv", max_length=100)
    auth_mount: str = Field(default="semaphore-ansible", max_length=255)
    role_id: SecretStr | None = None
    secret_id: SecretStr | None = None


class ProfileInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=2, max_length=160)
    purpose: Literal["host", "git"]
    login: str = Field(min_length=1, max_length=100, pattern=r"^[A-Za-z_][A-Za-z0-9_.-]*[$]?$")
    vault_path: str = Field(max_length=500)
    vault_version: int = Field(default=1, ge=1)
    allowed_targets: list[str] = Field(min_length=1, max_length=100)
    is_active: bool = True
    revision: str | None = None


class SyncInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    confirm: bool
    expected_version: int = Field(ge=1)
    desired_version: int = Field(ge=1)
    profile_revision: str


def revision(profile: CredentialProfile) -> str:
    values = {**service.profile_snapshot(profile), "name": profile.name, "is_active": profile.is_active}
    return hashlib.sha256(json.dumps(values, sort_keys=True).encode()).hexdigest()


def public_profile(profile: CredentialProfile) -> dict:
    return {**service.profile_snapshot(profile), "name": profile.name, "is_active": profile.is_active,
            "fingerprint": profile.fingerprint, "public_key": profile.public_key,
            "last_tested_at": profile.last_tested_at, "revision": revision(profile)}


def public_use(use: CredentialUse) -> dict:
    return {"id": str(use.id), "profile_id": str(use.profile_id), "creation_job_id": str(use.creation_job_id),
            "semaphore_project_id": use.semaphore_project_id, "semaphore_key_id": use.semaphore_key_id,
            "vault_version": use.vault_version, "fingerprint": use.fingerprint, "bindings": use.bindings,
            "status": use.status, "last_error": use.last_error, "updated_at": use.updated_at}


@router.get("/config")
def get_config(db: Db, admin: SystemAdmin):
    return service.public_configuration(db)


@router.put("/config")
def put_config(payload: ConnectionInput, request: Request, db: Db, admin: SystemAdmin):
    values = payload.model_dump(exclude={"role_id", "secret_id"})
    for field in ("role_id", "secret_id"):
        secret = getattr(payload, field)
        if secret is not None:
            values[field] = secret.get_secret_value()
    try:
        service.save_configuration(db, values)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    record_audit(db, "ssh_store_configured", actor=admin, request=request)
    db.commit()
    return service.public_configuration(db)


@router.post("/test")
async def test_connection(db: Db, admin: SystemAdmin):
    try:
        await service.vault_client(service.configuration(db)).login()
    except (ValueError, VaultError) as exc:
        raise HTTPException(502, str(exc)) from exc
    return {"message": "Profil-Lesezugang angemeldet. Ein Profiltest prüft zusätzlich Version und Schlüssel."}


@router.get("/profiles")
def profiles(db: Db, admin: SystemAdmin):
    return [public_profile(row) for row in db.scalars(select(CredentialProfile).order_by(CredentialProfile.name))]


@router.post("/profiles", status_code=201)
def create_profile(payload: ProfileInput, request: Request, db: Db, admin: SystemAdmin):
    return save_profile(None, payload, request, db, admin)


@router.put("/profiles/{profile_id}")
def edit_profile(profile_id: uuid.UUID, payload: ProfileInput, request: Request, db: Db, admin: SystemAdmin):
    return save_profile(profile_id, payload, request, db, admin)


def save_profile(profile_id, payload, request, db, admin):
    try:
        safe_path(payload.vault_path)
        if not payload.vault_path.startswith("automation-credentials/"):
            raise ValueError("SSH-Profile verwenden den getrennten Vault-Bereich automation-credentials/…")
        service.normalize_targets(payload.purpose, payload.allowed_targets)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    profile = db.scalar(select(CredentialProfile).where(CredentialProfile.id == profile_id).with_for_update()) if profile_id else None
    if profile_id and profile is None:
        raise HTTPException(404, "Zugangsprofil nicht gefunden.")
    if profile is not None and payload.revision != revision(profile):
        raise HTTPException(409, "Das Zugangsprofil wurde geändert. Neu laden und erneut prüfen.")
    if profile is not None and (db.scalar(select(CredentialUse.id).where(CredentialUse.profile_id == profile_id).limit(1))
                               or any(item["profile"]["id"] == str(profile_id) for item in service.frozen_plans(db))):
        if any(getattr(profile, key) != getattr(payload, key) for key in ("purpose", "login", "vault_path")):
            raise HTTPException(409, "Ein verwendetes Profil behält Zweck, Benutzer und Vault-Pfad. Für andere Zugänge ein neues Profil anlegen.")
    profile = profile if profile is not None else CredentialProfile()
    for key, value in payload.model_dump(exclude={"revision"}).items():
        setattr(profile, key, value)
    profile.fingerprint = profile.public_key = profile.last_tested_at = None
    db.add(profile)
    try:
        db.flush()
        record_audit(db, "ssh_profile_saved", actor=admin, request=request, target_type="ssh_profile", target_id=profile.id,
                     details={"version": profile.vault_version, "active": profile.is_active})
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Dieser Profilname wird bereits verwendet.") from exc
    return public_profile(profile)


@router.post("/profiles/{profile_id}/test")
async def test_profile(profile_id: uuid.UUID, request: Request, db: Db, admin: SystemAdmin):
    profile = db.scalar(select(CredentialProfile).where(CredentialProfile.id == profile_id).with_for_update())
    if profile is None:
        raise HTTPException(404, "Zugangsprofil nicht gefunden.")
    try:
        client = service.vault_client(service.configuration(db))
        await client.login()
        key = await service.read_key(client, service.profile_snapshot(profile))
    except (ValueError, VaultError) as exc:
        raise HTTPException(502, str(exc)) from exc
    profile.fingerprint, profile.public_key, profile.last_tested_at = key["fingerprint"], key["public_key"], utcnow()
    record_audit(db, "ssh_profile_tested", actor=admin, request=request, target_type="ssh_profile", target_id=profile.id,
                 details={"version": profile.vault_version, "fingerprint": key["fingerprint"]})
    db.commit()
    return public_profile(profile)


@router.get("/uses")
def uses(db: Db, admin: SystemAdmin):
    return [public_use(row) for row in db.scalars(select(CredentialUse).order_by(CredentialUse.updated_at.desc()))]


@router.post("/uses/{use_id}/sync")
async def sync_use(use_id: uuid.UUID, payload: SyncInput, request: Request, db: Db, admin: SystemAdmin):
    use = db.scalar(select(CredentialUse).where(CredentialUse.id == use_id).with_for_update())
    if use is None:
        raise HTTPException(404, "Schlüsselverwendung nicht gefunden.")
    profile = db.get(CredentialProfile, use.profile_id)
    job = db.get(CreationJob, use.creation_job_id)
    if job.status != CreationStatus.COMPLETED:
        raise HTTPException(409, "Zuerst den Erstellungsvorgang abschließen; er verwendet seine geprüfte Schlüsselversion.")
    if not payload.confirm or not profile.is_active or payload.profile_revision != revision(profile) or payload.desired_version != profile.vault_version or payload.expected_version != use.vault_version:
        raise HTTPException(409, "Aktualisierung zuerst mit den aktuellen Profil- und Projektversionen bestätigen.")
    started = use.execution_started_at
    if started and (started.replace(tzinfo=timezone.utc) if started.tzinfo is None else started) > utcnow() - timedelta(minutes=15):
        raise HTTPException(409, "Eine Aktualisierung dieses Eintrags läuft bereits.")
    config = service.configuration(db)
    source = {**service.source_identity(config), "semaphore_url": service.semaphore_identity(db),
              "vault_path": profile.vault_path, "purpose": profile.purpose, "login": profile.login}
    if use.source != source:
        raise HTTPException(409, "Die Quelle oder SSH-Identität wurde verändert. Zuordnung prüfen.")
    snapshot = service.profile_snapshot(profile)
    use.execution_started_at = utcnow()
    db.commit()
    try:
        vault = service.vault_client(config)
        await vault.login()
        key = await service.read_key(vault, snapshot)
        semaphore = semaphore_client_from_db(db)
        remote_key = await semaphore.get_resource(use.semaphore_project_id, "keys", use.semaphore_key_id)
        key_name = f"Semaporter-{profile.purpose}-{profile.id.hex}"
        if remote_key.get("name") != key_name or remote_key.get("type") != "ssh" or remote_key.get("source_storage_type"):
            raise ValueError("Der verwaltete Semaphore-Eintrag wurde verändert. Projekt prüfen.")
        for binding in use.bindings:
            kind = "inventory" if binding["kind"] == "inventories" else "repositories"
            resource = await semaphore.get_resource(use.semaphore_project_id, kind, binding["resource_id"])
            targets = service.resource_targets(binding["kind"], resource, snapshot["login"])
            if resource.get("ssh_key_id") != use.semaphore_key_id or targets != binding["targets"] or not set(targets).issubset(service.normalize_targets(snapshot["purpose"], snapshot["allowed_targets"])):
                raise ValueError("Inventory, Repository oder SSH-Zuordnung wurde geändert. Projekt prüfen.")
        await service.write_key(db, semaphore, use, key_name, key, snapshot["vault_version"])
        record_audit(db, "ssh_key_updated", actor=admin, request=request, target_type="ssh_use", target_id=use.id,
                     details={"project_id": use.semaphore_project_id, "version": use.vault_version, "fingerprint": use.fingerprint})
        db.commit()
    except (ValueError, VaultError, SemaphoreError) as exc:
        record_audit(db, "ssh_key_update_failed", actor=admin, request=request,
                     target_type="ssh_use", target_id=use.id, success=False)
        raise HTTPException(502, str(exc)) from exc
    finally:
        use.execution_started_at = None
        db.commit()
    return public_use(use)
