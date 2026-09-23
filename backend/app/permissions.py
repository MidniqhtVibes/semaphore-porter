from __future__ import annotations

import uuid

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.models import GroupMembership, TaskPermission, Tenant, TenantMembership, User
from app.security import user_has_role


def _group_ids(db: Session, user_id: uuid.UUID) -> list[uuid.UUID]:
    return list(db.scalars(select(GroupMembership.group_id).where(GroupMembership.user_id == user_id)))


def can_access_tenant(db: Session, user: User, tenant: Tenant, *, administer: bool = False) -> bool:
    if user_has_role(user, "system_admin"):
        return True
    groups = _group_ids(db, user.id)
    principal = or_(TenantMembership.user_id == user.id, TenantMembership.group_id.in_(groups))
    query = select(TenantMembership.id).where(TenantMembership.tenant_id == tenant.id, principal)
    if administer:
        query = query.where(TenantMembership.role_code == "tenant_admin")
    return db.scalar(query.limit(1)) is not None


def task_actions(db: Session, user: User, task_template_id: uuid.UUID) -> set[str]:
    if user_has_role(user, "system_admin"):
        return {"view", "start", "stop"}
    groups = _group_ids(db, user.id)
    rows = db.scalars(
        select(TaskPermission).where(
            TaskPermission.task_template_id == task_template_id,
            or_(TaskPermission.user_id == user.id, TaskPermission.group_id.in_(groups)),
        )
    )
    actions: set[str] = set()
    for row in rows:
        if row.can_view:
            actions.add("view")
        if row.can_start:
            actions.add("start")
        if row.can_stop:
            actions.add("stop")
    return actions

