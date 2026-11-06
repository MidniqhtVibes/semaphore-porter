from __future__ import annotations

import uuid
from typing import Literal

from fastapi import APIRouter, File, HTTPException, Request, Response, UploadFile
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from app.audit import record_audit
from app.dependencies import CurrentUser, Db, SystemAdmin
from app.models import Tenant, TenantDeletion, TenantStatus
from app.permissions import can_access_tenant
from app.profile_images import MAX_AVATAR_BYTES, validate_avatar
from app.security import user_has_role

router = APIRouter(tags=["Projektlogos"])


class ArtworkInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: Literal["auto", "selected", "custom", "none"] = "auto"
    marks: list[Literal["doxis", "postgresql", "wordpress"]] = Field(default_factory=list, max_length=3)


def editable(db, tenant_id):
    tenant = db.scalar(select(Tenant).where(Tenant.id == tenant_id).with_for_update())
    if not tenant:
        raise HTTPException(404, "Tenant nicht gefunden.")
    deletion = db.get(TenantDeletion, tenant_id)
    if deletion and (deletion.execution_started_at or (deletion.progress or {}).get("started")):
        raise HTTPException(409, "Die Tenant-Bereinigung wurde bereits begonnen.")
    return tenant


@router.put("/admin/tenants/{tenant_id}/artwork")
def select_artwork(tenant_id: uuid.UUID, payload: ArtworkInput, request: Request, db: Db, admin: SystemAdmin):
    tenant = editable(db, tenant_id)
    if payload.mode == "custom" and not tenant.project_logo_mime:
        raise HTTPException(422, "Zuerst ein eigenes Logo hochladen.")
    config = payload.model_dump()
    if (tenant.project_artwork or {}).get("image_version"):
        config["image_version"] = tenant.project_artwork["image_version"]
    tenant.project_artwork = config
    record_audit(db, "project_artwork_changed", actor=admin, request=request, target_type="tenant", target_id=tenant.id,
                 details={"mode": payload.mode, "marks": payload.marks})
    db.commit()
    return config


@router.put("/admin/tenants/{tenant_id}/logo")
async def upload(tenant_id: uuid.UUID, request: Request, db: Db, admin: SystemAdmin, file: UploadFile = File(...)):
    tenant = editable(db, tenant_id)
    try:
        data = await file.read(MAX_AVATAR_BYTES+1)
        mime = validate_avatar(data)
    except ValueError as exc:
        raise HTTPException(422, str(exc).replace("Profilbilder", "Projektlogos").replace("Profilbild", "Projektlogo")) from exc
    finally:
        await file.close()
    tenant.project_logo_data, tenant.project_logo_mime = data, mime
    tenant.project_artwork = {"mode": "custom", "marks": [], "image_version": uuid.uuid4().hex}
    record_audit(db, "project_logo_uploaded", actor=admin, request=request, target_type="tenant", target_id=tenant.id,
                 details={"mime": mime, "bytes": len(data)})
    db.commit()
    return tenant.project_artwork


@router.delete("/admin/tenants/{tenant_id}/logo")
def remove(tenant_id: uuid.UUID, request: Request, db: Db, admin: SystemAdmin):
    tenant = editable(db, tenant_id)
    tenant.project_logo_data = tenant.project_logo_mime = None
    tenant.project_artwork = {"mode": "auto", "marks": []}
    record_audit(db, "project_logo_removed", actor=admin, request=request, target_type="tenant", target_id=tenant.id)
    db.commit()
    return tenant.project_artwork


@router.get("/portal/tenants/{tenant_id}/logo")
def image(tenant_id: uuid.UUID, db: Db, user: CurrentUser):
    tenant = db.get(Tenant, tenant_id)
    if (not tenant or (not user_has_role(user, "system_admin") and
            (tenant.status != TenantStatus.ACTIVE or not tenant.configuration_complete or not can_access_tenant(db, user, tenant)))
            or not tenant.project_logo_mime or not tenant.project_logo_data):
        raise HTTPException(404, "Projektlogo nicht gefunden.")
    return Response(tenant.project_logo_data, media_type=tenant.project_logo_mime,
                    headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"})
