from __future__ import annotations

import json
import uuid
from datetime import timedelta
from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, StrictBool
from sqlalchemy import or_, select

from app import approval_service as service
from app.audit import record_audit
from app.dependencies import CurrentUser, Db, SystemAdmin
from app.models import TaskApproval, TaskTemplate, Tenant, TenantDeletion, User, utcnow
from app.routers.portal import execute_task_start, prepare_task_start
from app.schemas import ApprovalConfigInput, TaskStartRequest
from app.security import decrypt_secret, encrypt_secret, user_has_role

router = APIRouter(tags=["Task-Genehmigungen"])


class ApprovalRequestInput(TaskStartRequest):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(min_length=3, max_length=2000)


class DecisionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: Literal["approved", "rejected"]
    note: str = Field(default="", max_length=2000)


class ResolutionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    confirmed_remote_checked: StrictBool


@router.get("/admin/approval-settings")
def settings(db: Db, admin: SystemAdmin):
    return {"notifications_available": service.notifications_available()}


@router.put("/admin/tenants/{tenant_id}/approval-config")
def configure(tenant_id: uuid.UUID, payload: ApprovalConfigInput, request: Request, db: Db, admin: SystemAdmin):
    tenant = db.scalar(select(Tenant).where(Tenant.id == tenant_id).with_for_update())
    if not tenant:
        raise HTTPException(404, "Tenant nicht gefunden.")
    deletion = db.get(TenantDeletion, tenant_id)
    if deletion and (deletion.execution_started_at or (deletion.progress or {}).get("started")):
        raise HTTPException(409, "Die Tenant-Bereinigung wurde bereits begonnen.")
    config = payload.model_dump(mode="json")
    if (tenant.approval_config or {}).get("revision") != payload.revision:
        raise HTTPException(409, "Genehmigungsregeln wurden geändert. Seite neu laden.")
    service.validate_config(db, config)
    config["revision"] = uuid.uuid4().hex
    tenant.approval_config = config
    record_audit(db, "approval_config_changed", actor=admin, request=request, target_type="tenant", target_id=tenant.id)
    db.commit()
    return config


@router.post("/portal/tenants/{tenant_id}/tasks/{template_id}/approvals", status_code=201)
async def create_request(tenant_id: uuid.UUID, template_id: uuid.UUID, payload: ApprovalRequestInput,
                         request: Request, db: Db, user: CurrentUser):
    tenant, template, variables = prepare_task_start(tenant_id, template_id, payload, db, user)
    if len(payload.reason.strip()) < 3:
        raise HTTPException(422, "Eine kurze Begründung der Anfrage eingeben.")
    if not service.required(tenant, template):
        raise HTTPException(409, "Dieser Task benötigt keine Genehmigung und kann regulär gestartet werden.")
    service.validate_config(db, tenant.approval_config)
    approver_id = uuid.UUID(tenant.approval_config["approver_id"])
    if approver_id == user.id:
        raise HTTPException(409, "Selbstfreigaben sind gesperrt. Einen anderen Vorgesetzten administrativ zuordnen lassen.")
    context = service.context_digest(db, tenant, template, variables)
    existing = db.scalar(select(TaskApproval).where(TaskApproval.task_template_id == template.id,
        TaskApproval.requester_id == user.id, TaskApproval.context_digest == context,
        TaskApproval.status.in_(["pending", "approved"]), TaskApproval.expires_at > utcnow()))
    if existing:
        return service.public_request(db, existing, user)
    row = TaskApproval(tenant_id=tenant.id, task_template_id=template.id, requester_id=user.id,
        approver_id=approver_id, context_digest=context, reason=payload.reason.strip(),
        encrypted_variables=encrypt_secret(json.dumps({"submitted": payload.variables, "validated": variables,
            "cost_class": template.policy.cost_class, "effort_class": template.policy.effort_class})),
        expires_at=utcnow()+timedelta(hours=24))
    db.add(row)
    db.flush()
    record_audit(db, "task_approval_requested", actor=user, request=request, target_type="task_approval", target_id=row.id,
                 details={"tenant_id": str(tenant.id), "template_id": str(template.id)})
    db.commit()
    await service.notify(db, row)
    return service.public_request(db, row, user)


@router.get("/portal/approvals")
def list_requests(db: Db, user: CurrentUser):
    query = select(TaskApproval).order_by(TaskApproval.created_at.desc()).limit(200)
    if not user_has_role(user, "system_admin"):
        query = query.where(or_(TaskApproval.requester_id == user.id, TaskApproval.approver_id == user.id))
    return [service.public_request(db, row, user) for row in db.scalars(query)]


@router.get("/portal/approvals/{approval_id}")
def detail(approval_id: uuid.UUID, db: Db, user: CurrentUser):
    return service.public_request(db, service.get_visible(db, approval_id, user), user)


@router.post("/portal/approvals/{approval_id}/decision")
async def decide(approval_id: uuid.UUID, payload: DecisionInput, request: Request, db: Db, user: CurrentUser):
    row = service.get_visible(db, approval_id, user)
    db.scalar(select(Tenant).where(Tenant.id == row.tenant_id).with_for_update())
    db.refresh(row, with_for_update=True)
    if row.approver_id != user.id or row.requester_id == user.id:
        raise HTTPException(403, "Nur der zugeordnete Vorgesetzte darf entscheiden; keine Selbstfreigabe.")
    if service.visible_status(row) != "pending":
        raise HTTPException(409, "Diese Anfrage ist nicht mehr offen.")
    if payload.decision == "approved":
        requester = db.get(User, row.requester_id)
        document = json.loads(decrypt_secret(row.encrypted_variables))
        tenant, template, variables = prepare_task_start(row.tenant_id, row.task_template_id,
            TaskStartRequest(variables=document["submitted"]), db, requester)
        if not service.required(tenant, template) or row.context_digest != service.context_digest(db, tenant, template, variables):
            raise HTTPException(409, "Die Anfrage passt nicht mehr zur aktuellen Konfiguration. Neu beantragen.")
    row.status, row.decision_note, row.decided_at = payload.decision, payload.note.strip(), utcnow()
    record_audit(db, "task_approval_decided", actor=user, request=request, target_type="task_approval", target_id=row.id,
        details={"tenant_id": str(row.tenant_id), "decision": payload.decision})
    db.commit()
    await service.notify(db, row, decision=True)
    return service.public_request(db, row, user)


@router.post("/portal/approvals/{approval_id}/start", status_code=201)
async def start(approval_id: uuid.UUID, request: Request, db: Db, user: CurrentUser):
    row = service.get_visible(db, approval_id, user)
    if row.requester_id != user.id:
        raise HTTPException(403, "Nur der Antragsteller darf die genehmigte Ausführung starten.")
    document = json.loads(decrypt_secret(row.encrypted_variables))
    return await execute_task_start(row.tenant_id, row.task_template_id,
        TaskStartRequest(variables=document["submitted"]), request, db, user, approval=row)


@router.post("/portal/approvals/{approval_id}/cancel")
def cancel(approval_id: uuid.UUID, request: Request, db: Db, user: CurrentUser):
    row = service.get_visible(db, approval_id, user)
    db.scalar(select(Tenant).where(Tenant.id == row.tenant_id).with_for_update())
    db.refresh(row, with_for_update=True)
    if row.requester_id != user.id or service.visible_status(row) not in {"pending", "approved"}:
        raise HTTPException(409, "Diese Anfrage kann nicht zurückgezogen werden.")
    row.status = "cancelled"
    record_audit(db, "task_approval_cancelled", actor=user, request=request, target_type="task_approval", target_id=row.id,
        details={"tenant_id": str(row.tenant_id)})
    db.commit()
    return service.public_request(db, row, user)


@router.post("/admin/approvals/{approval_id}/resolve")
def resolve(approval_id: uuid.UUID, payload: ResolutionInput, request: Request, db: Db, admin: SystemAdmin):
    row = service.get_visible(db, approval_id, admin)
    db.scalar(select(Tenant).where(Tenant.id == row.tenant_id).with_for_update())
    db.refresh(row, with_for_update=True)
    if not payload.confirmed_remote_checked or not service.public_request(db, row, admin)["can_resolve"]:
        raise HTTPException(409, "Semaphore zuerst manuell prüfen; frühestens 15 Minuten nach dem Startversuch schließen.")
    row.status = "closed"
    record_audit(db, "task_approval_manually_closed", actor=admin, request=request, target_type="task_approval", target_id=row.id,
        details={"tenant_id": str(row.tenant_id)})
    db.commit()
    return service.public_request(db, row, admin)
