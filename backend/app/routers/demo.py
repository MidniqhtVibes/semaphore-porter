from __future__ import annotations

import copy
from typing import Literal

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict

from app.config import get_settings
from app.dependencies import Db, SystemAdmin

router=APIRouter(prefix="/demo",tags=["Demo"])


def require_demo(db=None):
    if not get_settings().demo_mode:
        raise HTTPException(404,"Demo ist auf dieser Instanz nicht aktiviert.")
    from app.demo.seed import assert_demo
    assert_demo(db)


@router.get("/config")
def configuration(response:Response):
    settings=get_settings()
    response.headers["Cache-Control"]="no-store"
    return {"mode":"demo" if settings.demo_mode else "production", "demo_available":settings.demo_enabled,
            "return_url":"/" if settings.demo_mode else None,
            "ephemeral":settings.demo_mode}


class LoginInput(BaseModel):
    model_config=ConfigDict(extra="forbid")
    role:Literal["admin","tenant_admin","operator","viewer"]


@router.post("/login")
def login(payload:LoginInput,request:Request,response:Response,db:Db):
    require_demo(db)
    from app.demo.seed import identifier
    from app.models import User,utcnow
    from app.security import session_cookie_name,session_cookie_path,create_session,revoke_session
    from app.routers.auth import _user_payload
    from app.audit import record_audit
    user=db.get(User,identifier("user/"+payload.role))
    if not user or not user.is_active:
        raise HTTPException(403,"Dieses Demo-Konto ist deaktiviert. Demo zurücksetzen oder ein anderes Konto verwenden.")
    revoke_session(db,request.cookies.get(session_cookie_name()))
    token,csrf=create_session(db,user,request.client.host if request.client else None,request.headers.get("user-agent"))
    user.last_login_at=utcnow()
    record_audit(db,"demo_login",actor=user,request=request,details={"role":payload.role,"simulation":True})
    db.commit()
    response.set_cookie(session_cookie_name(),token,httponly=True,secure=get_settings().portal_cookie_secure,samesite="lax",path=session_cookie_path(),max_age=3600)
    return {"user":_user_payload(user),"csrf_token":csrf}


@router.get("/status")
def status(db:Db,admin:SystemAdmin):
    require_demo(db)
    from app.demo.simulator import LOCK,STATE,ensure,SCENARIOS
    with LOCK:
        ensure()
        return {"scenario":STATE["scenario"],"scenarios":sorted(SCENARIOS),"last_error":STATE["last_error"],"simulated":True}


class ScenarioInput(BaseModel):
    model_config=ConfigDict(extra="forbid")
    name:str


@router.post("/scenario")
def scenario(payload:ScenarioInput,db:Db,admin:SystemAdmin):
    require_demo(db)
    from app.demo.simulator import set_scenario
    try:set_scenario(payload.name)
    except ValueError as exc:raise HTTPException(422,str(exc))
    return {"scenario":payload.name,"simulated":True}


@router.post("/merge")
def merge_reviews(db:Db,admin:SystemAdmin):
    require_demo(db)
    from app.demo.simulator import merge_reviews
    return {"merged":merge_reviews(),"simulated":True}


class ResetInput(BaseModel):
    model_config=ConfigDict(extra="forbid")
    confirm:Literal[True]


@router.post("/reset")
def reset(payload:ResetInput,response:Response,db:Db,admin:SystemAdmin):
    require_demo(db)
    from app.database import Base
    from app.demo.seed import seed
    from app.demo.simulator import LOCK,STATE
    from app.security import session_cookie_name,session_cookie_path
    with LOCK:
        before=copy.deepcopy(STATE)
        try:
            db.expunge_all()
            for table in reversed(Base.metadata.sorted_tables):db.execute(table.delete())
            seed(db)
            db.commit()
        except Exception:
            db.rollback();STATE.clear();STATE.update(before)
            raise
    response.delete_cookie(session_cookie_name(),path=session_cookie_path())
    return {"reset":True,"simulated":True}
