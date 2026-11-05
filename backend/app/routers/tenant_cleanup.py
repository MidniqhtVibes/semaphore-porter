"""Explicit, resumable tenant cleanup for system administrators."""
import uuid
from datetime import timedelta

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, StrictBool
from sqlalchemy import or_, select, update

from app import tenant_cleanup as cleanup
from app.dependencies import Db, SystemAdmin
from app.models import Tenant, TenantDeletion, TenantStatus, utcnow
from app.semaphore_client import SemaphoreError
from app.vault_client import VaultError

router = APIRouter(prefix="/admin/tenants", tags=["Tenant-Bereinigung"])


def tenant_row(db, tenant_id):
    row = db.scalar(select(Tenant).where(Tenant.id == tenant_id).with_for_update())
    if row is None:
        raise HTTPException(404, "Tenant nicht gefunden.")
    return row


class Confirmation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    revision: str
    confirm_slug: str
    deployments_confirmed: StrictBool


@router.delete("/{tenant_id}/deletion")
def cancel(tenant_id: uuid.UUID, db: Db, admin: SystemAdmin):
    tenant_row(db, tenant_id)
    row = db.get(TenantDeletion, tenant_id)
    if row:
        if cleanup.public_state(row)["running"] or cleanup.destructive_progress(row):
            raise HTTPException(409, "Eine laufende oder bereits extern begonnene Löschung muss fortgesetzt werden.")
        db.delete(row)
        db.commit()
    return {"message": "Löschvorgang verworfen. Einen deaktivierten Tenant bei Bedarf ausdrücklich wieder aktivieren."}


@router.post("/{tenant_id}/deletion/preview")
async def preview(tenant_id: uuid.UUID, db: Db, admin: SystemAdmin):
    tenant = tenant_row(db, tenant_id)
    try:
        return await cleanup.prepare(db, tenant)
    except (VaultError, SemaphoreError, RuntimeError) as exc:
        raise HTTPException(502, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.post("/{tenant_id}/deletion/execute")
async def execute(tenant_id: uuid.UUID, payload: Confirmation, db: Db, admin: SystemAdmin):
    tenant = tenant_row(db, tenant_id)
    row = db.get(TenantDeletion, tenant_id)
    if row is None or payload.revision != row.revision:
        raise HTTPException(409, "Zuerst eine aktuelle Löschvorschau erstellen.")
    if payload.confirm_slug != tenant.tenant_slug or not payload.deployments_confirmed:
        raise HTTPException(422, "Tenant-Kennung und beendete Deployments müssen ausdrücklich bestätigt werden.")
    if row.plan.get("blockers"):
        raise HTTPException(409, "Hindernisse der Löschvorschau zuerst auflösen und Vorschau erneuern.")
    claimed = db.execute(update(TenantDeletion).where(TenantDeletion.tenant_id == tenant_id,
        or_(TenantDeletion.execution_started_at.is_(None), TenantDeletion.execution_started_at < utcnow() - timedelta(minutes=15)))
        .values(execution_started_at=utcnow(), last_error=None).execution_options(synchronize_session=False))
    if claimed.rowcount != 1:
        raise HTTPException(409, "Die Bereinigung läuft bereits. Eine abgebrochene Ausführung ist nach 15 Minuten wieder aufnehmbar.")
    # Same tenant lock as task start: no task can slip in after this transition.
    tenant.status, tenant.configuration_complete = TenantStatus.INACTIVE, False
    db.commit()
    try:
        await cleanup.execute(db, tenant, row)
        return {"message": "Tenant, eigene Semaphore-/Vault-Ressourcen und tenantbezogener Verlauf wurden entfernt."}
    except (ValueError, VaultError, SemaphoreError, RuntimeError) as exc:
        db.rollback()
        db.execute(update(TenantDeletion).where(TenantDeletion.tenant_id == tenant_id).values(last_error=str(exc)))
        db.commit()
        raise HTTPException(409 if isinstance(exc, ValueError) else 502, str(exc)) from exc
    finally:
        db.rollback()
        db.execute(update(TenantDeletion).where(TenantDeletion.tenant_id == tenant_id).values(execution_started_at=None))
        db.commit()
