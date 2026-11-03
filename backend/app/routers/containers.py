from __future__ import annotations
from datetime import timedelta
import time
from typing import Literal
import uuid

from fastapi import APIRouter,HTTPException,Query,Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel,ConfigDict,Field,SecretStr
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from app import container_service as service
from app.audit import record_audit
from app.dependencies import Db,SystemAdmin
from app.models import ContainerOperation,utcnow

router=APIRouter(prefix="/admin/containers",tags=["Container-Verwaltung"])
Action=Literal["start","stop","restart","pause","resume","remove"]


class AgentInput(BaseModel):
    model_config=ConfigDict(extra="forbid")
    id: uuid.UUID
    name: str=Field(min_length=1,max_length=160)
    base_url: str=Field(min_length=1,max_length=1000)
    token: SecretStr|None=Field(default=None,max_length=500)
    ca_pem: str=Field(default="",max_length=64000)
    client_cert_pem: str=Field(default="",max_length=64000)
    client_key: SecretStr|None=Field(default=None,max_length=64000)
    clear_client_certificate: bool=False
    active: bool=False
    projects: list[str]=Field(default_factory=list,max_length=100)
    use_agent_scope: bool=False
    write_enabled: bool=False
    allowed_actions: list[Action]=Field(default_factory=lambda:["start","stop","restart"],max_length=6)


class ConfigInput(BaseModel):
    model_config=ConfigDict(extra="forbid")
    enabled: bool=False
    revision: str=Field(default="",max_length=64)
    agents: list[AgentInput]=Field(default_factory=list,max_length=20)


@router.get("/config")
def config(db:Db,admin:SystemAdmin): return service.public_configuration(db)


@router.put("/config")
def save_config(payload:ConfigInput,request:Request,db:Db,admin:SystemAdmin):
    try: service.save_configuration(db,payload)
    except ValueError as exc: raise HTTPException(422,str(exc)) from exc
    except service.AgentError as exc: raise HTTPException(exc.status,str(exc)) from exc
    record_audit(db,"container_agents_configured",actor=admin,request=request,details={"enabled":payload.enabled,"agent_ids":[str(a.id) for a in payload.agents]})
    db.commit()
    return service.public_configuration(db)


def get_agent(db,agent_id,test=False):
    try: return service.find_agent(service.configuration(db),agent_id,test=test)
    except service.AgentError as exc: raise HTTPException(exc.status,str(exc)) from exc


async def call(awaitable):
    try: return await awaitable
    except service.AgentError as exc: raise HTTPException(exc.status,str(exc)) from exc


@router.post("/agents/{agent_id}/test")
async def test_agent(agent_id:uuid.UUID,db:Db,admin:SystemAdmin):
    result=await call(service.AgentClient(get_agent(db,agent_id,test=True)).request("GET","/info"))
    if not isinstance(result,dict) or result.get("protocol")!=1: raise HTTPException(502,"Nicht unterstützte Agent-Protokollversion.")
    return {"message":"Agent angemeldet. Docker-Zugriff und Ressourcenfreigaben anschließend über die Containerliste prüfen.",
        "name":result.get("name"),"projects":result.get("projects",[]),"container_ids":result.get("container_ids",[]),
        "allow_all":bool(result.get("allow_all")),"actions":result.get("actions",[])}


@router.get("/agents/{agent_id}/policy")
def policy_template(agent_id:uuid.UUID,db:Db,admin:SystemAdmin):
    import hashlib
    agent=get_agent(db,agent_id,test=True)
    return JSONResponse({"name":agent["name"],"projects":agent["projects"],"container_ids":[],"allow_all":False,
        "protected_projects":["semaporter"],"credentials":[{"token_sha256":hashlib.sha256(agent["token"].encode()).hexdigest(),"actions":agent["allowed_actions"]}]},
        headers={"Content-Disposition":f'attachment; filename="agent-{agent_id}.policy.json"',"Cache-Control":"no-store"})


@router.get("/agents/{agent_id}/inventory")
async def inventory(agent_id:uuid.UUID,db:Db,admin:SystemAdmin): return await call(service.inventory(get_agent(db,agent_id)))


@router.get("/agents/{agent_id}/containers/{container_id}")
async def detail(agent_id:uuid.UUID,container_id:str,db:Db,admin:SystemAdmin): return await call(service.detail(get_agent(db,agent_id),container_id))


@router.get("/agents/{agent_id}/containers/{container_id}/logs")
async def logs(agent_id:uuid.UUID,container_id:str,db:Db,admin:SystemAdmin,tail:int=Query(default=200,ge=1,le=1000)):
    agent=get_agent(db,agent_id);await call(service.detail(agent,container_id))
    return await call(service.AgentClient(agent).request("GET",f"/containers/{container_id}/logs",params={"tail":tail}))


@router.get("/agents/{agent_id}/containers/{container_id}/stats")
async def stats(agent_id:uuid.UUID,container_id:str,db:Db,admin:SystemAdmin):
    agent=get_agent(db,agent_id);await call(service.detail(agent,container_id))
    return await call(service.AgentClient(agent).request("GET",f"/containers/{container_id}/stats"))


class ActionInput(BaseModel):
    model_config=ConfigDict(extra="forbid")
    operation_id: uuid.UUID
    action: Action
    confirm: Literal[True]
    revision: str=Field(min_length=1,max_length=64)
    expected_image_id: str=Field(min_length=1,max_length=100)
    expected_state: str=Field(min_length=1,max_length=30)
    expected_started_at: str=Field(max_length=100)


def operation_json(row):
    return {key:str(getattr(row,key)) if key=="id" else getattr(row,key) for key in ("id","agent_id","agent_name","container_id","container_name","action","status","message","created_at")} | {"requires_review":row.status in {"unknown","pending"}}


@router.get("/operations")
def operations(db:Db,admin:SystemAdmin):
    return [operation_json(row) for row in db.scalars(select(ContainerOperation).order_by(ContainerOperation.created_at.desc()).limit(100))]


@router.post("/agents/{agent_id}/containers/{container_id}/actions")
async def action(agent_id:uuid.UUID,container_id:str,payload:ActionInput,request:Request,db:Db,admin:SystemAdmin):
    config=service.configuration(db)
    agent=get_agent(db,agent_id)
    prior=db.get(ContainerOperation,payload.operation_id)
    if prior:
        if (prior.agent_id,prior.container_id,prior.action,prior.actor_user_id)!=(str(agent_id),container_id,payload.action,admin.id):
            raise HTTPException(409,"Auftragskennung wurde bereits anders verwendet.")
        return operation_json(prior)
    if config["revision"]!=payload.revision: raise HTTPException(409,"Verbindung wurde geändert. Neu laden und erneut bestätigen.")
    row=await call(service.detail(agent,container_id))
    if payload.action not in row["actions"]: raise HTTPException(403,"Aktion für diesen Container nicht freigegeben.")
    if (row["image_id"],row["state"],row["details"]["started_at"] or "")!=(payload.expected_image_id,payload.expected_state,payload.expected_started_at):
        raise HTTPException(409,"Container wurde geändert. Erneut prüfen und bestätigen.")
    db.expire_all()
    if service.configuration(db)["revision"]!=payload.revision: raise HTTPException(409,"Verbindung während der Prüfung geändert.")
    command={"operation_id":str(payload.operation_id),"action":payload.action,"confirm":True,"expires_at":int(time.time())+60,
        "expected":{"image_id":payload.expected_image_id,"state":payload.expected_state,"started_at":payload.expected_started_at}}
    operation=ContainerOperation(id=payload.operation_id,agent_id=str(agent_id),agent_name=agent["name"],connection_id=service.connection_id(agent),
        container_id=container_id,container_name=row["name"],action=payload.action,status="pending",message="Auftrag wird an den Agenten übergeben.",actor_user_id=admin.id,payload=command)
    db.add(operation)
    try: db.commit()
    except IntegrityError:
        db.rollback();raise HTTPException(409,"Auftrag wurde bereits angelegt. Ereignisse aktualisieren.")
    try:
        result=await service.AgentClient(agent).request("POST",f"/containers/{container_id}/actions",payload=command)
        apply_result(operation,result)
    except service.AgentError as exc: operation.status,operation.message=("unknown" if exc.uncertain else "failed"),str(exc)
    except BaseException:
        operation.status,operation.message="unknown","Übertragung unterbrochen. Auftrag am Agenten abgleichen."
        db.commit();raise
    record_audit(db,"container_action",actor=admin,request=request,target_type="container",target_id=container_id,success=operation.status=="success",
        details={"agent_id":str(agent_id),"action":payload.action,"status":operation.status,"operation_id":str(operation.id)})
    db.commit();return operation_json(operation)


def apply_result(row,result):
    if not isinstance(result,dict) or result.get("id")!=str(row.id) or result.get("target")!=row.container_id or result.get("action")!=row.action or result.get("status") not in {"pending","success","failed","unknown","reviewed"}:
        raise service.AgentError("Widersprüchliches Agent-Ergebnis; Auftrag manuell abgleichen.",uncertain=True)
    row.status,row.message=result["status"],str(result.get("message",""))[:1000]


def operation_agent(db,operation_id):
    row=db.get(ContainerOperation,operation_id)
    if not row: raise HTTPException(404,"Auftrag nicht gefunden.")
    agent=get_agent(db,row.agent_id)
    if service.connection_id(agent)!=row.connection_id: raise HTTPException(409,"Agent-Ziel wurde verändert. Ursprüngliche Verbindung zum Abgleichen wiederherstellen.")
    return row,agent


@router.post("/operations/{operation_id}/sync")
async def sync(operation_id:uuid.UUID,db:Db,admin:SystemAdmin):
    row,agent=operation_agent(db,operation_id)
    try: apply_result(row,await service.AgentClient(agent).request("GET",f"/operations/{row.id}"))
    except service.AgentError as exc:
        if exc.status!=404: raise HTTPException(exc.status,str(exc)) from exc
        row.status,row.message="unknown","Agent kennt diesen Auftrag nicht. Vor Wiederholung tatsächlichen Containerzustand prüfen."
    db.commit();return operation_json(row)


class ReviewInput(BaseModel):
    model_config=ConfigDict(extra="forbid")
    confirm: Literal[True]


@router.post("/operations/{operation_id}/review")
async def review(operation_id:uuid.UUID,payload:ReviewInput,request:Request,db:Db,admin:SystemAdmin):
    row,agent=operation_agent(db,operation_id)
    if row.status in {"pending","unknown"} and utcnow().replace(tzinfo=None)-row.created_at.replace(tzinfo=None)<timedelta(minutes=2):
        raise HTTPException(409,"Auftrag läuft möglicherweise noch. Frühestens nach zwei Minuten prüfen.")
    try: apply_result(row,await service.AgentClient(agent).request("POST",f"/operations/{row.id}/review",payload={"confirm":True}))
    except service.AgentError as exc:
        if exc.status!=404: raise HTTPException(exc.status,str(exc)) from exc
        row.status,row.message="reviewed","Agent ohne Auftragseintrag; Ergebnis manuell geprüft. Keine Aktion wiederholt."
    record_audit(db,"container_action_reviewed",actor=admin,request=request,target_type="container_operation",target_id=row.id)
    db.commit();return operation_json(row)
