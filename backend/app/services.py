from __future__ import annotations

import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import SemaphoreSettings
from app.security import decrypt_secret
from app.semaphore_client import SemaphoreClient, SemaphoreConnection


SECRET_NAME = re.compile(
    r"password|passwd|passwort|token|secret|private.?key|credential|role.?id|api.?key|access.?key",
    re.IGNORECASE,
)


def contains_secret(value: Any) -> bool:
    if isinstance(value, dict):
        return any(SECRET_NAME.search(str(key)) or contains_secret(item) for key, item in value.items())
    if isinstance(value, list):
        return any(contains_secret(item) for item in value)
    return False


def semaphore_client_from_db(db: Session) -> SemaphoreClient:
    stored = db.scalar(select(SemaphoreSettings).where(SemaphoreSettings.id == 1))
    if stored is None:
        raise RuntimeError("Semaphore ist noch nicht konfiguriert.")
    return SemaphoreClient(
        SemaphoreConnection(
            base_url=stored.base_url,
            token=decrypt_secret(stored.encrypted_token),
            proxy_url=stored.proxy_url,
            timeout_seconds=get_settings().semaphore_request_timeout_seconds,
        )
    )

