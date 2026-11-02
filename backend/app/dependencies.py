from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.security import session_cookie_name, get_session, user_has_role


Db = Annotated[Session, Depends(get_db)]


def current_user(request: Request, db: Db) -> User:
    portal_session = get_session(db, request.cookies.get(session_cookie_name()))
    if portal_session is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Anmeldung erforderlich.")
    request.state.portal_session = portal_session
    request.state.user = portal_session.user
    path = request.url.path.removeprefix(request.scope.get("root_path", ""))
    if portal_session.user.must_change_password and path not in {
        "/api/auth/me", "/api/auth/csrf", "/api/auth/password", "/api/auth/logout"
    }:
        raise HTTPException(status_code=403, detail="Bitte zuerst das Passwort ändern.")
    return portal_session.user


CurrentUser = Annotated[User, Depends(current_user)]


def system_admin(user: CurrentUser) -> User:
    if not user_has_role(user, "system_admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Systemadministrator-Berechtigung erforderlich.")
    return user


SystemAdmin = Annotated[User, Depends(system_admin)]

