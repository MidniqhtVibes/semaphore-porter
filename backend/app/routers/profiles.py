from __future__ import annotations

import hashlib
import uuid

from fastapi import APIRouter, File, HTTPException, Query, Request, Response, UploadFile
from sqlalchemy import func, or_, select
from sqlalchemy.orm import selectinload

from app.audit import record_audit
from app.dependencies import CurrentUser, Db, SystemAdmin
from app.models import Group, GroupMembership, User
from app.profile_images import MAX_AVATAR_BYTES, validate_avatar
from app.schemas import PersonalProfileInput, ProfileOrganizationInput, unique_tags
from app.security import user_has_role

router = APIRouter(prefix="/profiles", tags=["Profile und Teams"])
profile_load = selectinload(User.group_memberships).selectinload(GroupMembership.group)


def tag_match(column, needle, dialect):
    # Search decoded JSON strings, not escaped JSON source (e.g. \u00e4).
    if dialect == "postgresql":
        values = func.json_array_elements_text(column).table_valued("value").render_derived()
    else:
        values = func.json_each(column).table_valued("key", "value")
    return select(1).select_from(values).where(func.lower(values.c.value).like(needle)).exists()


def member_counts(db):
    return dict(db.execute(select(GroupMembership.group_id, func.count()).join(User)
        .where(User.is_active.is_(True)).group_by(GroupMembership.group_id)).all())


def team_json(group, counts):
    return {"id": str(group.id), "name": group.name, "description": group.description, "color": group.color,
        "responsibilities": group.responsibilities, "responsibility_notes": group.responsibility_notes,
        "member_count": counts.get(group.id, 0)}


def profile_json(user, counts):
    teams = sorted((item.group for item in user.group_memberships if item.group.is_team), key=lambda g: g.name.casefold())
    primary = user.primary_team_id if any(t.id == user.primary_team_id for t in teams) else None
    return {"id": str(user.id), "display_name": user.display_name, "email": user.email, "is_active": user.is_active,
        "bio": user.bio, "skills": user.skills, "responsibilities": user.responsibilities,
        "responsibility_notes": user.responsibility_notes, "phone": user.phone, "profile_color": user.profile_color,
        "position": user.position, "department": user.department, "location": user.location,
        "primary_team_id": str(primary) if primary else None, "avatar_version": user.avatar_version,
        "teams": [team_json(t, counts) for t in teams],
        "team_responsibilities": unique_tags([value for t in teams for value in t.responsibilities])}


def target_user(db, user_id, viewer):
    target = db.scalar(select(User).where(User.id == user_id).options(profile_load))
    if target is None or (not target.is_active and not user_has_role(viewer, "system_admin")):
        raise HTTPException(404, "Profil nicht gefunden.")
    return target


@router.get("")
def directory(db: Db, user: CurrentUser, q: str = Query(default="", max_length=160), team_id: uuid.UUID | None = None,
              offset: int = Query(default=0, ge=0, le=1_000_000), limit: int = Query(default=60, ge=1, le=100)):
    query = select(User).where(User.is_active.is_(True))
    if team_id:
        query = query.where(User.id.in_(select(GroupMembership.user_id).join(Group).where(Group.id == team_id, Group.is_team.is_(True))))
    # Keep tag matching portable across PostgreSQL and the in-memory demo.
    if q.strip():
        needle = "%" + q.strip().lower() + "%"
        dialect = db.get_bind().dialect.name
        team_matches = select(GroupMembership.user_id).join(Group).where(Group.is_team.is_(True), or_(
            func.lower(Group.name).like(needle), func.lower(Group.description).like(needle),
            func.lower(Group.responsibility_notes).like(needle), tag_match(Group.responsibilities, needle, dialect)))
        query = query.where(or_(*(func.lower(getattr(User, field)).like(needle) for field in
            ("display_name", "email", "position", "department", "location", "bio", "responsibility_notes")),
            tag_match(User.skills, needle, dialect), tag_match(User.responsibilities, needle, dialect), User.id.in_(team_matches)))
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    users = db.scalars(query.options(profile_load).order_by(func.lower(User.display_name), User.id).offset(offset).limit(limit)).all()
    counts = member_counts(db)
    return {"items": [profile_json(item, counts) for item in users], "total": total, "offset": offset, "limit": limit}


@router.get("/teams")
def teams(db: Db, user: CurrentUser):
    counts = member_counts(db)
    return [team_json(group, counts) for group in db.scalars(select(Group).where(Group.is_team.is_(True)).order_by(Group.name))]


@router.get("/me")
def own_profile(db: Db, user: CurrentUser):
    return profile_json(target_user(db, user.id, user), member_counts(db))


@router.put("/me")
def save_personal(payload: PersonalProfileInput, request: Request, db: Db, user: CurrentUser):
    changed = []
    for key, value in payload.model_dump().items():
        if getattr(user, key) != value:
            setattr(user, key, value); changed.append(key)
    record_audit(db, "profile_updated", actor=user, request=request, target_type="user", target_id=user.id, details={"fields": changed})
    db.commit()
    return profile_json(user, member_counts(db))


@router.post("/me/avatar")
async def upload_avatar(request: Request, db: Db, user: CurrentUser, file: UploadFile = File(...)):
    try:
        data = await file.read(MAX_AVATAR_BYTES + 1)
    finally:
        await file.close()
    try:
        mime = validate_avatar(data)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    user.avatar_data, user.avatar_mime = data, mime
    user.avatar_version = hashlib.sha256(data).hexdigest()
    record_audit(db, "profile_avatar_updated", actor=user, request=request, target_type="user", target_id=user.id, details={"mime": mime, "bytes": len(data)})
    db.commit()
    return {"avatar_version": user.avatar_version}


@router.delete("/me/avatar")
def remove_avatar(request: Request, db: Db, user: CurrentUser):
    user.avatar_data = user.avatar_mime = user.avatar_version = None
    record_audit(db, "profile_avatar_removed", actor=user, request=request, target_type="user", target_id=user.id)
    db.commit()
    return {"avatar_version": None}


@router.get("/{user_id}/avatar")
def avatar(user_id: uuid.UUID, db: Db, user: CurrentUser):
    target = target_user(db, user_id, user)
    if not target.avatar_data or not target.avatar_mime:
        raise HTTPException(404, "Kein Profilbild vorhanden.")
    return Response(target.avatar_data, media_type=target.avatar_mime,
        headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff", "Vary": "Cookie"})


@router.put("/{user_id}/organization")
def save_organization(user_id: uuid.UUID, payload: ProfileOrganizationInput, request: Request, db: Db, admin: SystemAdmin):
    target = target_user(db, user_id, admin)
    if payload.primary_team_id:
        membership = db.scalar(select(GroupMembership).join(Group).where(GroupMembership.user_id == target.id,
            GroupMembership.group_id == payload.primary_team_id, Group.is_team.is_(True)))
        if membership is None:
            raise HTTPException(422, "Hauptteam muss eine bestehende Mitgliedschaft in einer als Team markierten Gruppe sein.")
    for key, value in payload.model_dump().items():
        setattr(target, key, value)
    record_audit(db, "profile_organization_updated", actor=admin, request=request, target_type="user", target_id=target.id,
        details={"fields": list(payload.model_fields_set)})
    db.commit()
    return profile_json(target, member_counts(db))


@router.get("/{user_id}")
def profile(user_id: uuid.UUID, db: Db, user: CurrentUser):
    return profile_json(target_user(db, user_id, user), member_counts(db))
