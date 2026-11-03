"""Small, deny-by-default API. No generic Docker proxy or shell commands."""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import sqlite3
import struct
import time
from typing import Literal
import uuid

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

Action = Literal["start", "stop", "restart", "pause", "resume", "remove"]
ACTIONS = {"start", "stop", "restart", "pause", "resume", "remove"}
CID = r"[a-f0-9]{64}"


class Credential(BaseModel):
    model_config = ConfigDict(extra="forbid")
    token_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    actions: list[Action] = Field(default_factory=list, max_length=6)


class Policy(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=160)
    projects: list[str] = Field(default_factory=list, max_length=100)
    container_ids: list[str] = Field(default_factory=list, max_length=500)
    allow_all: bool = False
    protected_projects: list[str] = Field(default_factory=lambda: ["semaporter"], max_length=100)
    credentials: list[Credential] = Field(min_length=1, max_length=10)

    @classmethod
    def from_file(cls, value):
        path = Path(value)
        if not path.is_absolute() or path.is_symlink() or path.stat().st_mode & 0o022:
            raise ValueError("Agent-Policy benötigt eine absolute, nicht fremd beschreibbare reguläre Datei.")
        if not path.is_file() or path.stat().st_size > 65536:
            raise ValueError("Ungültige Agent-Policy-Datei.")
        policy = cls.model_validate_json(path.read_text(encoding="utf-8"))
        if any(not re.fullmatch(CID, item) for item in policy.container_ids):
            raise ValueError("Freigaben benötigen vollständige Container-IDs.")
        if any(not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,99}", name) for name in policy.projects):
            raise ValueError("Ungültiger Compose-Projektname in der Agent-Policy.")
        return policy

    def allows(self, container_id, labels):
        return self.allow_all or container_id in self.container_ids or labels.get("com.docker.compose.project") in self.projects


class Expected(BaseModel):
    model_config = ConfigDict(extra="forbid")
    image_id: str = Field(min_length=1, max_length=100)
    state: str = Field(min_length=1, max_length=30)
    started_at: str = Field(max_length=100)


class Command(BaseModel):
    model_config = ConfigDict(extra="forbid")
    operation_id: uuid.UUID
    action: Action
    expected: Expected
    confirm: Literal[True]
    expires_at: int


class Review(BaseModel):
    model_config = ConfigDict(extra="forbid")
    confirm: Literal[True]


class DockerError(Exception):
    def __init__(self, message, status=502, uncertain=False):
        self.status, self.uncertain = status, uncertain
        super().__init__(message)


class Engine:
    def __init__(self, socket_path, transport=None):
        self.transport, self.socket_path = transport, socket_path
        self.version = None
        self.version_lock = asyncio.Lock()
        self.slots = asyncio.Semaphore(8)

    async def request(self, method, path, *, params=None, raw=False, versioned=True, deadline=None):
        try:
            if versioned and not self.version:
                async with self.version_lock:
                    if not self.version:
                        version = await self.request("GET", "/version", versioned=False)
                        parse = lambda text: tuple(int(n) for n in text.split("."))
                        chosen = min(parse(version["ApiVersion"]), (1, 45))
                        if chosen < parse(version.get("MinAPIVersion", "1.24")) or chosen < (1, 41):
                            raise DockerError("Docker-API-Version wird von diesem Agenten nicht unterstützt.")
                        self.version = ".".join(map(str, chosen))
            prefix = "/v"+self.version if versioned else ""
            async with self.slots, asyncio.timeout(25):
                if deadline is not None and time.time()>deadline:
                    raise DockerError("Auftrag vor Docker-Übertragung abgelaufen; keine Aktion ausgeführt.",409)
                async with httpx.AsyncClient(transport=self.transport or httpx.AsyncHTTPTransport(uds=self.socket_path,retries=0), trust_env=False, timeout=httpx.Timeout(20, connect=3)) as client:
                    async with client.stream(method, "http://docker"+prefix+path, params=params) as response:
                        if response.status_code >= 300:
                            code = response.status_code
                            raise DockerError(f"Docker hat die Anfrage mit HTTP {code} abgelehnt.", 404 if code == 404 else 409 if code in {304,409} else 502, method != "GET" and code >= 500)
                        chunks, size = [], 0
                        async for chunk in response.aiter_bytes():
                            size += len(chunk)
                            if size > 4 * 1024 * 1024:
                                raise DockerError("Docker-Antwort ist zu groß.", uncertain=method != "GET")
                            chunks.append(chunk)
                        data = b"".join(chunks)
            return data if raw else json.loads(data) if data else None
        except DockerError:
            raise
        except (httpx.HTTPError, TimeoutError) as exc:
            raise DockerError("Docker nicht erreichbar; bei Schreibaktionen Ergebnis zuerst prüfen.", uncertain=method != "GET") from exc
        except (ValueError, KeyError, TypeError) as exc:
            raise DockerError("Ungültige Docker-Antwort.", uncertain=method != "GET") from exc


class Journal:
    def __init__(self, path):
        self.path = str(path)
        self.db = sqlite3.connect(self.path, check_same_thread=False, timeout=5)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("CREATE TABLE IF NOT EXISTS operations (id TEXT PRIMARY KEY, digest TEXT NOT NULL, target TEXT NOT NULL, project TEXT NOT NULL, action TEXT NOT NULL, status TEXT NOT NULL, message TEXT NOT NULL, active TEXT UNIQUE, created REAL NOT NULL)")
        self.db.execute("UPDATE operations SET status='unknown',message='Agent wurde während der Ausführung neu gestartet. Ergebnis prüfen.' WHERE status='pending'")
        self.db.commit()

    def get(self, key):
        row = self.db.execute("SELECT * FROM operations WHERE id=?", (str(key),)).fetchone()
        return dict(row) if row else None

    def begin(self, key, digest, target, project, action):
        try:
            self.db.execute("INSERT INTO operations VALUES (?,?,?,?,?,'pending','Aktion wird ausgeführt.',?,?)", (str(key), digest, target, project, action, target, time.time()))
            self.db.commit()
        except sqlite3.IntegrityError as exc:
            self.db.rollback()
            raise HTTPException(409, "Eine Aktion läuft bereits oder ein Ergebnis muss geprüft werden.") from exc

    def finish(self, key, status, message):
        self.db.execute("UPDATE operations SET status=?, message=?, active=CASE WHEN ? IN ('unknown','pending') THEN active ELSE NULL END WHERE id=?", (status, message, status, str(key)))
        self.db.commit()
        return self.get(key)


def public_operation(row):
    return {key: row[key] for key in ("id", "target", "action", "status", "message", "created")} | {"requires_review": bool(row["active"])}


def summary(item, policy, credential, own_id):
    labels = item.get("Labels") or {}
    name = (item.get("Names") or [item.get("Name", "")])[0].lstrip("/")
    image = item.get("Image", "")
    protected = (labels.get("com.docker.compose.project") in policy.protected_projects
        or labels.get("semaporter.management.protected") == "true"
        or bool(own_id and item["Id"].startswith(own_id))
        or bool(re.search(r"semaporter[-_](agent|backend|frontend)(:|@|$)", image)))
    state = item.get("State", "unknown")
    available = {"stop","restart","pause"} if state == "running" else {"stop","resume"} if state == "paused" else {"start","remove"} if state in {"exited","created"} else set()
    return {"id": item["Id"], "name": name, "image": image, "image_id": item.get("ImageID", ""),
        "stack": labels.get("com.docker.compose.project", ""), "state": state, "status": item.get("Status", ""),
        "ports": [{key: port.get(key) for key in ("IP","PrivatePort","PublicPort","Type")} for port in item.get("Ports", [])],
        "networks": sorted((item.get("NetworkSettings") or {}).get("Networks", {}).keys()),
        "volumes": sorted({mount["Name"] for mount in item.get("Mounts", []) if mount.get("Type") == "volume" and mount.get("Name")}),
        "protected": protected, "actions": sorted(available & set(credential.actions)) if not protected else []}


def create_app(policy, *, socket_path="/var/run/docker.sock", journal_path="/var/lib/semaporter-agent/operations.sqlite3", transport=None):
    app = FastAPI(title="Semaporter Docker Agent", docs_url=None, openapi_url=None)
    engine, journal = Engine(socket_path, transport), Journal(journal_path)
    own_id = os.environ.get("HOSTNAME", "")
    if not re.fullmatch(r"[a-f0-9]{12,64}", own_id): own_id = ""
    app.state.engine, app.state.journal = engine, journal

    def authenticate(authorization: str = Header(default="")):
        if not authorization.startswith("Bearer ") or len(authorization) > 600:
            raise HTTPException(401, "Agent-Anmeldung erforderlich.")
        digest = hashlib.sha256(authorization[7:].encode()).hexdigest()
        for credential in policy.credentials:
            if hmac.compare_digest(digest, credential.token_sha256): return credential
        raise HTTPException(401, "Ungültiger Agent-Zugang.")

    @app.middleware("http")
    async def limits(request: Request, call_next):
        if request.url.path != "/healthz":
            try: authenticate(request.headers.get("authorization", ""))
            except HTTPException as exc: return JSONResponse(status_code=exc.status_code,content={"detail":exc.detail})
        if request.method not in {"GET","HEAD","OPTIONS"}:
            chunks,size=[],0
            async for chunk in request.stream():
                size+=len(chunk)
                if size>16384: return JSONResponse(status_code=413,content={"detail":"Agent-Anfrage zu groß."})
                chunks.append(chunk)
            request._body=b"".join(chunks)
        response=await call_next(request)
        response.headers["Cache-Control"]="no-store"
        response.headers["X-Content-Type-Options"]="nosniff"
        return response

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        return JSONResponse(status_code=422, content={"detail":"Ungültige Agent-Anfrage."})

    @app.exception_handler(DockerError)
    async def docker_error(request, exc):
        return JSONResponse(status_code=exc.status, content={"detail":str(exc)})

    async def inspect(container_id, credential):
        if not re.fullmatch(CID, container_id): raise HTTPException(422, "Vollständige Container-ID erforderlich.")
        item = await engine.request("GET", f"/containers/{container_id}/json")
        config, state = item.get("Config") or {}, item.get("State") or {}
        if item.get("Id") != container_id: raise DockerError("Widersprüchliche Container-ID.")
        labels = config.get("Labels") or {}
        if not policy.allows(container_id, labels): raise HTTPException(403, "Container ist am Agenten nicht freigegeben.")
        row = summary({"Id":container_id,"Names":[item.get("Name", "")],"Image":config.get("Image", ""),"ImageID":item.get("Image", ""),
            "Labels":labels,"State":state.get("Status", "unknown"),"Status":(state.get("Health") or {}).get("Status", state.get("Status", "unknown")),
            "NetworkSettings":item.get("NetworkSettings", {}),"Mounts":item.get("Mounts", [])}, policy, credential, own_id)
        ports = (item.get("NetworkSettings") or {}).get("Ports") or {}
        row["ports"] = [{"PrivatePort":int(port.split("/")[0]),"Type":port.split("/")[-1],"PublicPort":int(binding["HostPort"]),"IP":binding.get("HostIp", "")} for port, bindings in ports.items() for binding in bindings or []]
        row["details"] = {"started_at":state.get("StartedAt", ""),"finished_at":state.get("FinishedAt", ""),"exit_code":state.get("ExitCode"),
            "restart_count":item.get("RestartCount", 0),"restart_policy":(item.get("HostConfig") or {}).get("RestartPolicy", {}).get("Name", ""),
            "environment_names":[entry.split("=",1)[0] for entry in config.get("Env") or []]}
        return row

    @app.get("/healthz")
    async def health(): return {"status":"ok"}

    @app.get("/v1/info")
    async def info(credential: Credential = Depends(authenticate)):
        # Deliberately no Docker request: the agent can be configured before access is ready.
        return {"protocol":1,"name":policy.name,"projects":policy.projects,"allow_all":policy.allow_all,
            "container_ids":policy.container_ids,"actions":credential.actions,"protected_projects":policy.protected_projects}

    @app.get("/v1/inventory")
    async def inventory(credential: Credential = Depends(authenticate)):
        items = await engine.request("GET", "/containers/json", params={"all":"true"})
        if not isinstance(items, list) or len(items)>10000: raise DockerError("Zu große oder ungültige Containerliste.")
        return {"containers":sorted([summary(item,policy,credential,own_id) for item in items if policy.allows(item.get("Id"),item.get("Labels") or {})],key=lambda row:row["name"].casefold())}

    @app.get("/v1/containers/{container_id}")
    async def detail(container_id: str, credential: Credential = Depends(authenticate)): return await inspect(container_id,credential)

    @app.get("/v1/containers/{container_id}/logs")
    async def logs(container_id: str, tail: int = Query(default=200,ge=1,le=1000), credential: Credential = Depends(authenticate)):
        await inspect(container_id,credential)
        data = await engine.request("GET",f"/containers/{container_id}/logs",params={"stdout":"true","stderr":"true","timestamps":"true","tail":tail},raw=True)
        chunks, offset = [], 0
        while offset+8<=len(data) and data[offset] in (0,1,2) and data[offset+1:offset+4]==b"\0\0\0":
            size = struct.unpack(">I",data[offset+4:offset+8])[0]
            if offset+8+size>len(data): raise DockerError("Unvollständiger Docker-Logstream.")
            chunks.append(data[offset+8:offset+8+size]);offset+=8+size
        if offset and offset!=len(data): raise DockerError("Ungültiger Docker-Logstream.")
        text=(b"".join(chunks) if offset else data).decode("utf-8",errors="replace")
        text=re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]","",text)
        text=re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]","",text)
        return {"text":text[-512000:],"truncated":len(text)>512000}

    @app.get("/v1/containers/{container_id}/stats")
    async def stats(container_id: str, credential: Credential = Depends(authenticate)):
        row=await inspect(container_id,credential)
        result={"running":row["state"]=="running",**{key:None for key in ("cpu_percent","memory_bytes","memory_limit","network_rx","network_tx","block_read","block_write")}}
        if not result["running"]: return result
        data=await engine.request("GET",f"/containers/{container_id}/stats",params={"stream":"false"})
        cpu,old=data.get("cpu_stats",{}),data.get("precpu_stats",{})
        delta=cpu.get("cpu_usage",{}).get("total_usage",0)-old.get("cpu_usage",{}).get("total_usage",0)
        system=cpu.get("system_cpu_usage",0)-old.get("system_cpu_usage",0)
        cores=cpu.get("online_cpus") or len(cpu.get("cpu_usage",{}).get("percpu_usage",[]))
        memory=data.get("memory_stats",{});cache=memory.get("stats",{}).get("inactive_file",memory.get("stats",{}).get("total_inactive_file",0))
        networks=list(data.get("networks",{}).values());blocks=data.get("blkio_stats",{}).get("io_service_bytes_recursive") or []
        result.update(cpu_percent=round(delta/system*cores*100,2) if system>0 and delta>=0 and cores else None,
            memory_bytes=max(0,memory["usage"]-cache) if "usage" in memory else None,memory_limit=memory.get("limit"),
            network_rx=sum(n.get("rx_bytes",0) for n in networks) if networks else None,network_tx=sum(n.get("tx_bytes",0) for n in networks) if networks else None,
            block_read=sum(n.get("value",0) for n in blocks if n.get("op", "").lower()=="read") if blocks else None,
            block_write=sum(n.get("value",0) for n in blocks if n.get("op", "").lower()=="write") if blocks else None)
        return result

    @app.post("/v1/containers/{container_id}/actions")
    async def action(container_id: str, command: Command, credential: Credential = Depends(authenticate)):
        if command.action not in credential.actions: raise HTTPException(403,"Aktion am Agenten nicht freigegeben.")
        digest=hashlib.sha256(json.dumps({"target":container_id,**command.model_dump(mode="json")},sort_keys=True).encode()).hexdigest()
        prior=journal.get(command.operation_id)
        if prior:
            if prior["digest"]!=digest: raise HTTPException(409,"Auftragskennung bereits anders verwendet.")
            if not policy.allows(prior["target"],{"com.docker.compose.project":prior["project"]}): raise HTTPException(403,"Freigabe entzogen.")
            return public_operation(prior)
        if not time.time()<=command.expires_at<=time.time()+120: raise HTTPException(409,"Auftrag ist abgelaufen oder hat eine ungültige Ablaufzeit.")
        row=await inspect(container_id,credential)
        if command.action not in row["actions"]: raise HTTPException(403,"Aktion im aktuellen Zustand nicht freigegeben.")
        if (row["image_id"],row["state"],row["details"]["started_at"] or "")!=(command.expected.image_id,command.expected.state,command.expected.started_at):
            raise HTTPException(409,"Container wurde geändert. Erneut prüfen und bestätigen.")
        journal.begin(command.operation_id,digest,container_id,row["stack"],command.action)
        try:
            base=f"/containers/{container_id}"
            params={"force":"false","v":"false"} if command.action=="remove" else {"t":10} if command.action in {"stop","restart"} else None
            await engine.request("DELETE" if command.action=="remove" else "POST",base if command.action=="remove" else base+"/"+("unpause" if command.action=="resume" else command.action),params=params,deadline=command.expires_at)
            return public_operation(journal.finish(command.operation_id,"success","Docker hat die Aktion bestätigt; aktuellen Zustand prüfen."))
        except DockerError as exc:
            return public_operation(journal.finish(command.operation_id,"unknown" if exc.uncertain else "failed",str(exc)))
        except BaseException:
            journal.finish(command.operation_id,"unknown","Ausführung unterbrochen. Ergebnis vor weiterer Aktion prüfen.")
            raise

    def checked_operation(operation_id,credential):
        row=journal.get(operation_id)
        if not row: raise HTTPException(404,"Auftrag nicht gefunden.")
        if row["action"] not in credential.actions or not policy.allows(row["target"],{"com.docker.compose.project":row["project"]}):
            raise HTTPException(403,"Auftrag nicht freigegeben.")
        return row

    @app.get("/v1/operations/{operation_id}")
    async def operation(operation_id: uuid.UUID, credential: Credential = Depends(authenticate)):
        return public_operation(checked_operation(operation_id,credential))

    @app.post("/v1/operations/{operation_id}/review")
    async def review(operation_id: uuid.UUID, payload: Review, credential: Credential = Depends(authenticate)):
        row=checked_operation(operation_id,credential)
        if row["status"]=="pending" and time.time()-row["created"]<120: raise HTTPException(409,"Auftrag läuft möglicherweise noch.")
        if row["active"]: row=journal.finish(operation_id,"reviewed","Ergebnis manuell geprüft; Sperre aufgehoben. Keine Aktion wiederholt.")
        return public_operation(row)

    return app
