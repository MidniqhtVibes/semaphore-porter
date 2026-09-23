from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import timedelta, timezone

from cryptography.fernet import Fernet, InvalidToken
from pwdlib import PasswordHash
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import PortalSession, User, utcnow


SESSION_COOKIE = "portal_session"
password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    if len(password) < 12:
        raise ValueError("Das Passwort muss mindestens 12 Zeichen lang sein.")
    return password_hash.hash(password)


def verify_password(password: str, encoded: str) -> bool:
    try:
        return password_hash.verify(password, encoded)
    except Exception:
        return False


def digest(value: str) -> bytes:
    return hashlib.sha256(value.encode("utf-8")).digest()


def stable_digest(value: str) -> bytes:
    key = get_settings().portal_secret_key.get_secret_value().encode()
    return hmac.new(key, value.encode("utf-8"), hashlib.sha256).digest()


def encrypt_secret(value: str) -> bytes:
    key = get_settings().portal_fernet_key.get_secret_value().encode()
    return Fernet(key).encrypt(value.encode("utf-8"))


def decrypt_secret(value: bytes) -> str:
    key = get_settings().portal_fernet_key.get_secret_value().encode()
    try:
        return Fernet(key).decrypt(value).decode("utf-8")
    except InvalidToken as exc:
        raise RuntimeError("Das gespeicherte Geheimnis kann nicht entschlüsselt werden.") from exc


def create_session(db: Session, user: User, ip_address: str | None, user_agent: str | None) -> tuple[str, str]:
    settings = get_settings()
    token = secrets.token_urlsafe(48)
    csrf = secrets.token_urlsafe(32)
    db.add(
        PortalSession(
            user_id=user.id,
            token_hash=digest(token),
            csrf_hash=digest(csrf),
            expires_at=utcnow() + timedelta(hours=settings.portal_session_hours),
            ip_address=ip_address,
            user_agent=(user_agent or "")[:500] or None,
        )
    )
    return token, csrf


def get_session(db: Session, token: str | None) -> PortalSession | None:
    if not token:
        return None
    session = db.scalar(select(PortalSession).where(PortalSession.token_hash == digest(token)))
    if session is None:
        return None
    expires_at = session.expires_at
    if expires_at is not None and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at <= utcnow() or not session.user.is_active:
        db.delete(session)
        db.commit()
        return None
    session.last_seen_at = utcnow()
    return session


def revoke_session(db: Session, token: str | None) -> None:
    if token:
        db.execute(delete(PortalSession).where(PortalSession.token_hash == digest(token)))


def verify_csrf(session: PortalSession, token: str | None) -> bool:
    return bool(token) and hmac.compare_digest(session.csrf_hash, digest(token))


def user_has_role(user: User, code: str) -> bool:
    return any(role.code == code for role in user.roles)
