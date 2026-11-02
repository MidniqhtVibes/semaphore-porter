from __future__ import annotations

from typing import Literal
import uuid

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, SecretStr
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app import registry_service as service
from app.audit import record_audit
from app.dependencies import Db, SystemAdmin
from app.models import RegistryProfile
from app.security import encrypt_secret
from app.vault_client import VaultError, safe_path

router = APIRouter(prefix="/admin/registries", tags=["Registry-Zugänge"])


class ConnectionInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    base_url: str = Field(max_length=1000)
    namespace: str = Field(default="", max_length=255)
    kv_mount: str = Field(default="kv", max_length=100)
    auth_mount: str = Field(default="semaphore-ansible", max_length=255)
    role_id: SecretStr | None = None
    secret_id: SecretStr | None = None


class ProfileInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=2, max_length=160)
    application_id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{0,62}$")
    host: str = Field(min_length=1, max_length=255)
    username: str = Field(min_length=1, max_length=255, pattern=r"^[^\s\x00-\x1f\x7f]+$")
    host_variable: str = Field(min_length=1, max_length=160)
    username_variable: str = Field(min_length=1, max_length=160)
    source: Literal["stored", "vault", "legacy"] = "stored"
    password: SecretStr | None = None
    vault_path: str | None = Field(default=None, max_length=500)
    vault_version: int | None = Field(default=None, ge=1)
    vault_field: str | None = Field(default=None, max_length=100)
    is_active: bool = True
    revision: str | None = None


@router.get("/config")
def config(db: Db, admin: SystemAdmin):
    return service.public_connection(db)


@router.put("/config")
def put_config(payload: ConnectionInput, request: Request, db: Db, admin: SystemAdmin):
    try: service.save_connection(db, payload)
    except ValueError as exc: raise HTTPException(422, str(exc)) from exc
    record_audit(db, "registry_reader_configured", actor=admin, request=request)
    db.commit()
    return service.public_connection(db)


@router.post("/config/test")
async def test_config(db: Db, admin: SystemAdmin):
    try: await service.reader(service.connection(db)).login()
    except (ValueError, VaultError) as exc: raise HTTPException(502, str(exc)) from exc
    return {"message": "Registry-Vault-Leser angemeldet. Exakte Secret-Version mit einem Profil prüfen."}


@router.get("/profiles")
def profiles(db: Db, admin: SystemAdmin):
    return [service.public_profile(row) for row in db.scalars(select(RegistryProfile).order_by(RegistryProfile.name))]


def save_profile(profile_id, payload, request, db, admin):
    row = db.get(RegistryProfile, profile_id) if profile_id else None
    if profile_id and row is None: raise HTTPException(404, "Registry-Profil nicht gefunden.")
    if row and row.revision != payload.revision: raise HTTPException(409, "Registry-Profil wurde geändert. Neu laden.")
    if db.scalar(select(RegistryProfile.id).where(func.lower(RegistryProfile.name) == payload.name.strip().lower(), RegistryProfile.id != profile_id if profile_id else True)):
        raise HTTPException(409, "Profilname ist bereits vergeben.")
    row = row or RegistryProfile()
    old_source, old_identity = row.source, (row.application_id, row.host, row.username)
    try:
        app, fields = service.registry_fields(db, payload.application_id)
        if len(payload.name.strip()) < 2: raise ValueError("Profilname benötigt mindestens zwei Zeichen.")
        row.name, row.application_id = payload.name.strip(), payload.application_id
        row.host, row.username = service.registry_host(payload.host), payload.username
        row.host_variable = service.variable_name(payload.host_variable, "host")
        row.username_variable = service.variable_name(payload.username_variable, "username")
        if app.registry and (row.host_variable, row.username_variable) != (app.registry.host_variable, app.registry.username_variable):
            raise ValueError("Registry-Variablen stimmen nicht mit dem Stack-Katalog überein.")
        row.source = "stored" if payload.source == "legacy" else payload.source
        if row.source == "stored":
            password = payload.password.get_secret_value() if payload.password else ""
            if payload.source == "legacy":
                from app.vault_service import configuration
                password = configuration(db).get("registry_passwords", {}).get(payload.application_id, "")
                if not password: raise ValueError("Für diese Anwendung ist kein bisheriger Registry-Zugang hinterlegt.")
            if password:
                from app.vault_catalog import validate_value
                for field in fields: validate_value(field.model_dump(), password)
                row.encrypted_password = encrypt_secret(password)
            elif old_source != "stored" or old_identity != (row.application_id, row.host, row.username) or not row.encrypted_password:
                raise ValueError("Registry-Passwort/Token erforderlich; nur bei gleicher Anwendung, Host und Benutzer kann ein bestehender Wert erhalten bleiben.")
            row.vault_path = row.vault_version = row.vault_field = row.vault_connection_id = None
        else:
            config = service.connection(db); service.reader(config)
            if not payload.vault_path or not payload.vault_version or not payload.vault_field:
                raise ValueError("Vault-Pfad, exakte Version und Secret-Feld erforderlich.")
            row.vault_path = safe_path(payload.vault_path)
            row.vault_version = payload.vault_version
            row.vault_field = safe_path(payload.vault_field)
            if "/" in row.vault_field: raise ValueError("Vault-Feld muss ein einzelner Schlüsselname sein.")
            row.vault_connection_id = service.connection_id(config)
            row.encrypted_password = None
        row.is_active, row.revision = payload.is_active, uuid.uuid4().hex
        db.add(row); db.flush()
    except ValueError as exc: db.rollback(); raise HTTPException(422, str(exc)) from exc
    except IntegrityError: db.rollback(); raise HTTPException(409, "Profilname ist bereits vergeben.")
    record_audit(db, "registry_profile_saved", actor=admin, request=request, target_type="registry_profile", target_id=row.id,
        details={"application_id": row.application_id, "source": row.source, "is_active": row.is_active})
    db.commit()
    return service.public_profile(row)


@router.post("/profiles", status_code=201)
def create_profile(payload: ProfileInput, request: Request, db: Db, admin: SystemAdmin):
    return save_profile(None, payload, request, db, admin)


@router.put("/profiles/{profile_id}")
def update_profile(profile_id: uuid.UUID, payload: ProfileInput, request: Request, db: Db, admin: SystemAdmin):
    return save_profile(profile_id, payload, request, db, admin)


@router.post("/profiles/{profile_id}/test")
async def test_profile(profile_id: uuid.UUID, db: Db, admin: SystemAdmin):
    row = db.get(RegistryProfile, profile_id)
    if row is None: raise HTTPException(404, "Registry-Profil nicht gefunden.")
    try: await service.resolve(db, row)
    except (ValueError, VaultError) as exc: raise HTTPException(422 if isinstance(exc, ValueError) else 502, str(exc)) from exc
    return {"message": "Gespeicherter Zugang entspricht dem Secret-Vertrag. Kein Registry-Login oder Image-Pull ausgeführt."}
