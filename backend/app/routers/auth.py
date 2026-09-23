from __future__ import annotations

import secrets
from datetime import timedelta

from fastapi import APIRouter, HTTPException, Request, Response, status
from sqlalchemy import func, or_, select

from app.audit import record_audit
from app.config import get_settings
from app.dependencies import CurrentUser, Db
from app.models import LoginAttempt, PortalSession, User, utcnow
from app.schemas import LoginRequest, PasswordChangeRequest
from app.security import (
    SESSION_COOKIE,
    create_session,
    digest,
    hash_password,
    revoke_session,
    stable_digest,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["Authentifizierung"])


def _user_payload(user: User) -> dict:
    return {
        "id": str(user.id),
        "email": user.email,
        "display_name": user.display_name,
        "is_active": user.is_active,
        "must_change_password": user.must_change_password,
        "roles": [role.code for role in user.roles],
    }


@router.post("/login")
def login(payload: LoginRequest, request: Request, response: Response, db: Db) -> dict:
    settings = get_settings()
    email = payload.email.lower().strip()
    ip = request.client.host if request.client else "unknown"
    identity_hash = stable_digest(email)
    ip_hash = stable_digest(ip)
    cutoff = utcnow() - timedelta(minutes=15)
    failures = db.scalar(
        select(func.count(LoginAttempt.id)).where(
            LoginAttempt.occurred_at >= cutoff,
            LoginAttempt.success.is_(False),
            or_(LoginAttempt.identity_hash == identity_hash, LoginAttempt.ip_hash == ip_hash),
        )
    ) or 0
    if failures >= 8:
        record_audit(db, "login_rate_limited", request=request, details={"email": email}, success=False)
        db.commit()
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Zu viele Anmeldeversuche. Bitte später erneut versuchen.")

    user = db.scalar(select(User).where(func.lower(User.email) == email))
    valid = bool(user and user.is_active and verify_password(payload.password, user.password_hash))
    db.add(LoginAttempt(identity_hash=identity_hash, ip_hash=ip_hash, success=valid))
    if not valid:
        record_audit(db, "login_failed", request=request, details={"email": email}, success=False)
        db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="E-Mail-Adresse oder Passwort ist ungültig.")

    assert user is not None
    token, csrf = create_session(db, user, ip, request.headers.get("user-agent"))
    user.last_login_at = utcnow()
    record_audit(db, "login", actor=user, request=request)
    db.commit()
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=settings.portal_session_hours * 3600,
        httponly=True,
        secure=settings.portal_cookie_secure,
        samesite="lax",
        path="/",
    )
    return {"user": _user_payload(user), "csrf_token": csrf}


@router.post("/logout")
def logout(request: Request, response: Response, db: Db, user: CurrentUser) -> dict[str, str]:
    record_audit(db, "logout", actor=user, request=request)
    revoke_session(db, request.cookies.get(SESSION_COOKIE))
    db.commit()
    response.delete_cookie(SESSION_COOKIE, path="/", httponly=True, samesite="lax")
    return {"message": "Abgemeldet."}


@router.get("/me")
def me(user: CurrentUser) -> dict:
    return _user_payload(user)


@router.get("/csrf")
def csrf(request: Request, db: Db, user: CurrentUser) -> dict:
    portal_session: PortalSession = request.state.portal_session
    token = secrets.token_urlsafe(32)
    portal_session.csrf_hash = digest(token)
    db.commit()
    return {"csrf_token": token}


@router.post("/password")
def change_password(payload: PasswordChangeRequest, request: Request, db: Db, user: CurrentUser) -> dict:
    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Das aktuelle Passwort ist nicht korrekt.")
    if verify_password(payload.new_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Das neue Passwort muss sich vom bisherigen unterscheiden.")
    user.password_hash = hash_password(payload.new_password)
    user.must_change_password = False
    # Alle anderen Sitzungen werden ungültig; die aktuelle bleibt aktiv.
    current_session: PortalSession = request.state.portal_session
    for item in db.scalars(select(PortalSession).where(PortalSession.user_id == user.id, PortalSession.id != current_session.id)):
        db.delete(item)
    record_audit(db, "password_changed", actor=user, request=request, target_type="user", target_id=user.id)
    db.commit()
    return {"message": "Passwort wurde geändert."}
