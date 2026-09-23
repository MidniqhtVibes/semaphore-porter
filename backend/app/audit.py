from __future__ import annotations

import re
import uuid
from typing import Any

from fastapi import Request
from sqlalchemy.orm import Session

from app.models import AuditEvent, User


SECRET_KEY = re.compile(
    r"password|passwd|passwort|token|secret|private.?key|credential|role.?id|api.?key|access.?key|csrf|cookie",
    re.IGNORECASE,
)


def sanitize(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): "[ENTFERNT]" if SECRET_KEY.search(str(k)) else sanitize(v) for k, v in value.items()}
    if isinstance(value, list):
        return [sanitize(item) for item in value]
    if isinstance(value, str) and len(value) > 2000:
        return value[:2000] + "…"
    return value


def record_audit(
    db: Session,
    event_type: str,
    *,
    actor: User | None = None,
    request: Request | None = None,
    target_type: str | None = None,
    target_id: str | uuid.UUID | int | None = None,
    details: dict[str, Any] | None = None,
    success: bool = True,
) -> None:
    db.add(
        AuditEvent(
            actor_user_id=actor.id if actor else None,
            event_type=event_type,
            target_type=target_type,
            target_id=str(target_id) if target_id is not None else None,
            ip_address=request.client.host if request and request.client else None,
            details=sanitize(details or {}),
            success=success,
        )
    )

