"""Deterministic in-process services. Unknown destinations never reach a socket."""
from __future__ import annotations

import base64
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import threading
import time
from urllib.parse import unquote

import httpx

from app.demo.seed import HOSTS, backup

LOCK = threading.RLock()
STATE: dict = {}
SCENARIOS = {"normal", "task_failure", "task_http500", "vault_conflict", "vault_uncertain", "gitlab_conflict", "commit_uncertain", "monitor_stale", "monitor_degraded", "ttl_expired", "container_uncertain"}


def iso(epoch=None):
    return datetime.fromtimestamp(epoch if epoch is not None else time.time(), timezone.utc).isoformat()


def reset_state():
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    with LOCK:
        key = Ed25519PrivateKey.generate().private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.OpenSSH, serialization.NoEncryption()).decode()
        files = json.loads((Path(__file__).parent / "stack.json").read_text())
        STATE.clear()
        STATE.update(scenario="normal", used=[], projects={}, tasks={}, vault={}, vault_created={}, next_project=10, next_task=100, started=time.time(), key=key,
                     files={"a"*40: files}, branches={"main":"a"*40}, commits={"a"*40:{"id":"a"*40,"parent_ids":[],"message":"DEMO: Ausgangsstand"}}, mrs=[], last_error=None)
        for pid,name,slug in [(1,"Nordstadt","nordstadt"),(2,"Südtal","suedtal"),(3,"Internes Labor","labor")]:
            add_project(pid, backup("Demo · "+name,slug))
        for purpose in ("host","git"):
            STATE["vault"]["automation-credentials/ssh/demo-"+purpose] = {"1":{"private_key":key,"passphrase":""}}
        STATE["vault"]["automation-credentials/registries/demo-wordpress"] = {"1":{"registry_password":"demo-registry-password"}}


def ensure():
    if not STATE:
        reset_state()


def private_key():
    with LOCK:
        ensure()
        return STATE["key"]


def add_project(pid, document):
    document = copy.deepcopy(document)
    resources = {}
    for kind, plural in [("keys","keys"),("environment","environments"),("repositories","repositories"),("inventory","inventories"),("templates","templates")]:
        resources[kind] = [{**row,"id":i+1,"project_id":pid} for i,row in enumerate(document.get(plural,[]))]
    maps = {kind:{r["name"]:r["id"] for r in rows} for kind,rows in resources.items()}
    for row in resources["inventory"]+resources["repositories"]:
        row["ssh_key_id"] = maps["keys"].get(row.get("ssh_key"))
    for row in resources["templates"]:
        row.update(repository_id=maps["repositories"].get(row.get("repository")), inventory_id=maps["inventory"].get(row.get("inventory")),
                   environment_id=maps["environment"].get(row.get("environment")), type=row.get("type", ""))
    STATE["projects"][str(pid)] = {"id":pid, **document.get("meta",{}), "resources":resources}


def project_templates(pid):
    with LOCK:
        ensure()
        return copy.deepcopy(STATE["projects"][str(pid)]["resources"]["templates"])


def project_backup(project):
    result={"meta":{k:v for k,v in project.items() if k not in {"id","resources"}}}
    maps={kind:{row["id"]:row["name"] for row in rows} for kind,rows in project["resources"].items()}
    for kind,plural in [("keys","keys"),("environment","environments"),("repositories","repositories"),("inventory","inventories"),("templates","templates")]:
        result[plural]=[]
        for original in project["resources"][kind]:
            row={k:copy.deepcopy(v) for k,v in original.items() if k not in {"id","project_id","ssh","login_password"}}
            if kind in {"repositories","inventory"}:
                row["ssh_key"]=maps["keys"].get(row.pop("ssh_key_id",None))
            if kind=="templates":
                for field,target in [("repository","repositories"),("inventory","inventory"),("environment","environment")]:
                    row[field]=maps[target].get(row.pop(field+"_id",None))
            result[plural].append(row)
    return result


def once(name):
    if STATE["scenario"]==name and name not in STATE["used"]:
        STATE["used"].append(name)
        return True
    return False


def task_public(task):
    value={k:copy.deepcopy(v) for k,v in task.items() if not k.startswith("_")}
    if task.get("_stopped"):
        value.update(status="stopped",end=iso())
    else:
        age=time.time()-task["_time"]
        value["status"]="waiting" if age<1 else ("error" if task["_fail"] else "success") if age>=12 else "running"
        if age>=1:value["start"]=iso(task["_time"]+1)
        if age>=12:value["end"]=iso(task["_time"]+12)
    return value


def semaphore(request, path, data):
    method=request.method
    if request.headers.get("authorization")!="Bearer demo-semaphore-token": return 401,{}
    if path=="/api/projects":
        if method=="GET": return 200,[{k:v for k,v in p.items() if k!="resources"} for p in STATE["projects"].values()]
        if method=="POST":
            pid=STATE["next_project"];STATE["next_project"]+=1
            add_project(pid,{"meta":data})
            return 201,{"id":pid,**data}
    if path=="/api/projects/restore" and method=="POST":
        pid=STATE["next_project"];STATE["next_project"]+=1
        add_project(pid,data)
        return 201,{"id":pid,"name":data["meta"]["name"]}
    parts=path.strip("/").split("/")
    if len(parts)<3 or parts[:2]!=["api","project"]: return 404,{}
    project=STATE["projects"].get(parts[2])
    if project is None:return 404,{}
    pid=project["id"]
    if len(parts)==3:
        if method=="DELETE": del STATE["projects"][str(pid)];return 204,None
        if method=="PUT":project.update({k:v for k,v in data.items() if k not in {"id","resources"}})
        return 200,{k:v for k,v in project.items() if k!="resources"}
    kind=parts[3]
    if kind=="backup" and method=="GET":return 200,project_backup(project)
    if kind=="tasks":
        if len(parts)==4:
            if method=="GET": return 200,[task_public(t) for t in STATE["tasks"].values() if t["project_id"]==pid]
            if method=="POST":
                if STATE["scenario"]=="task_http500":return 500,{}
                if not any(t["id"]==data.get("template_id") for t in project["resources"]["templates"]):return 404,{}
                tid=STATE["next_task"];STATE["next_task"]+=1
                task={"id":tid,"project_id":pid,"template_id":data["template_id"],"environment":data.get("environment","{}"),
                    "created":iso(),"_time":time.time(),"_fail":STATE["scenario"]=="task_failure"}
                STATE["tasks"][str(tid)]=task
                return 201,task_public(task)
        if parts[4]=="last":return 200,[task_public(t) for t in reversed(list(STATE["tasks"].values())) if t["project_id"]==pid][:200]
        task=STATE["tasks"].get(parts[4])
        if task is None or task["project_id"]!=pid:return 404,{}
        if len(parts)>5:
            if parts[5]=="stop" and method=="POST":task["_stopped"]=True;return 204,None
            if parts[5]=="output":
                age=time.time()-task["_time"]
                lines=["[DEMO] Simulierter Semaphore-Task – keine Hostverbindung.","[DEMO] Parameter und Inventory geprüft.","[DEMO] Deployment wird simuliert.","[DEMO] FEHLER: vorgegebenes Testszenario." if task["_fail"] else "[DEMO] Vorgang erfolgreich simuliert."]
                return 200,[{"task_id":task["id"],"time":iso(task["_time"]+i*3),"output":line} for i,line in enumerate(lines) if age>=i*3]
        return 200,task_public(task)
    rows=project["resources"].get(kind)
    if rows is None:return 404,{}
    if len(parts)==4:
        if method=="GET":return 200,[public_resource(kind,row) for row in rows]
        if method=="POST":
            row={**data,"id":max([r["id"] for r in rows],default=0)+1,"project_id":pid};rows.append(row)
            return 201,public_resource(kind,row)
    else:
        row=next((r for r in rows if str(r["id"])==parts[4]),None)
        if row is None:return 404,{}
        if method=="DELETE":rows.remove(row);return 204,None
        if method=="PUT":row.update({k:v for k,v in data.items() if k not in {"id","project_id"}})
        return 200,public_resource(kind,row)
    return 501,{}


def public_resource(kind,row):
    return {k:copy.deepcopy(v) for k,v in row.items() if kind!="keys" or k not in {"ssh","login_password"}}


def vault(request,path,data):
    if "/auth/" in path and path.endswith("/login") and request.method=="POST":
        if (data.get("role_id"),data.get("secret_id")) not in {("demo-writer","demo-writer-secret"),("demo-reader","demo-reader-secret")}:
            return 403,{}
        return 200,{"auth":{"client_token":"demo-vault-writer" if data["role_id"]=="demo-writer" else "demo-vault-reader"}}
    token=request.headers.get("x-vault-token")
    if token not in {"demo-vault-writer","demo-vault-reader"}:return 403,{}
    parts=path.strip("/").split("/",3)
    if len(parts)!=4 or parts[:2]!=["v1","kv"] or parts[2] not in {"metadata","data"}:return 404,{}
    kind,key=parts[2:]
    versions=STATE["vault"].get(key)
    if kind=="metadata" and request.method=="GET":
        if not versions and STATE["scenario"]=="vault_conflict" and key.startswith("semaphore/"):
            STATE["vault"][key]={"1":{"demo":"bereits vorhanden"}};versions=STATE["vault"][key]
        return (200,{"data":{"current_version":max(map(int,versions)),"versions":{
            version:{"created_time":STATE["vault_created"].get(key+"/"+version,iso(STATE["started"])),"destroyed":False,"deletion_time":""}
            for version in versions}}}) if versions else (404,{})
    if kind=="data" and request.method=="GET":
        version=request.url.params.get("version",str(max(map(int,versions))) if versions else "1")
        if not versions or version not in versions:return 404,{}
        return 200,{"data":{"data":versions[version],"metadata":{"version":int(version),"created_time":STATE["vault_created"].get(key+"/"+version,iso(STATE["started"])),"destroyed":False,"deletion_time":""}}}
    if kind=="data" and request.method=="POST":
        if token!="demo-vault-writer":return 403,{}
        cas=data.get("options",{}).get("cas")
        if versions and cas==0:return 400,{}
        if cas is not None and cas!=0 and cas!=(max(map(int,versions)) if versions else 0):return 400,{}
        version=str(max(map(int,versions),default=0)+1) if versions else "1"
        STATE["vault"].setdefault(key,{})[version]=copy.deepcopy(data["data"])
        created=STATE["vault_created"][key+"/"+version]=iso()
        if once("vault_uncertain"):raise httpx.ReadTimeout("Simulated Vault write timeout",request=request)
        return 200,{"data":{"version":int(version),"created_time":created}}
    return 501,{}


def gitlab(request,path,data):
    if request.headers.get("private-token")!="demo-gitlab-token":return 401,{}
    prefix="/api/v4/projects/7"
    if not path.startswith(prefix):return 404,{}
    rest=path[len(prefix):];method=request.method;params=request.url.params
    web="https://gitlab.demo.invalid/demo/stack"
    if not rest:return 200,{"id":7,"path_with_namespace":"demo/stack","web_url":web,"http_url_to_repo":web+".git","ssh_url_to_repo":"git@gitlab.demo.invalid:demo/stack.git"}
    if rest.startswith("/repository/branches/"):
        name=unquote(rest[len("/repository/branches/"):]);sha=STATE["branches"].get(name)
        return (200,{"name":name,"protected":name=="main","commit":{"id":sha}}) if sha else (404,{})
    if rest=="/repository/tree":
        sha=params.get("ref");files=STATE["files"].get(sha)
        if files is None:return 404,{}
        folder=params.get("path","")+"/"
        rows=[{"path":name,"type":"blob","mode":"100644","name":name.rsplit("/",1)[-1]} for name in sorted(files) if name.startswith(folder)]
        page=int(params.get("page",1));size=int(params.get("per_page",100))
        return 200,rows[(page-1)*size:page*size]
    if rest.startswith("/repository/files/"):
        name=unquote(rest[len("/repository/files/"):]);files=STATE["files"].get(params.get("ref"),{})
        return (200,{"file_path":name,"encoding":"base64","content":files[name]}) if name in files else (404,{})
    if rest=="/repository/commits" and method=="POST":
        if STATE["scenario"]=="gitlab_conflict" or data["branch"] in STATE["branches"]:return 409,{}
        source=data.get("start_sha");files=copy.deepcopy(STATE["files"].get(source))
        if files is None:return 400,{}
        for action in data["actions"]:
            if action["action"]=="delete":files.pop(action["file_path"],None)
            else:files[action["file_path"]]=action["content"]
        sha=hashlib.sha1(json.dumps([files,data["branch"]],sort_keys=True).encode()).hexdigest()
        commit={"id":sha,"parent_ids":[source],"message":data["commit_message"]}
        STATE["files"][sha]=files;STATE["commits"][sha]=commit;STATE["branches"][data["branch"]]=sha
        if once("commit_uncertain"):raise httpx.ReadTimeout("Simulated commit timeout",request=request)
        return 201,commit
    if rest.startswith("/repository/commits/"):
        value=STATE["commits"].get(rest.rsplit("/",1)[-1]);return (200,value) if value else (404,{})
    if rest=="/merge_requests":
        if method=="GET":return 200,[copy.deepcopy(mr) for mr in STATE["mrs"] if mr["source_branch"]==params.get("source_branch",mr["source_branch"])]
        iid=len(STATE["mrs"])+1
        mr={"id":iid,"iid":iid,"state":"opened","source_project_id":7,"target_project_id":7,"sha":STATE["branches"].get(data["source_branch"]),"web_url":web+f"/-/merge_requests/{iid}",**data}
        STATE["mrs"].append(mr);return 201,mr
    if rest.startswith("/merge_requests/"):
        mr=next((row for row in STATE["mrs"] if str(row["iid"])==rest.rsplit("/",1)[-1]),None)
        return (200,copy.deepcopy(mr)) if mr else (404,{})
    if rest=="/pipelines":
        sha=params.get("sha")
        return 200,([{"id":int(sha[:6],16),"sha":sha,"status":"success","ref":"main","web_url":web+"/-/pipelines/1"}] if sha in STATE["files"] else [])
    return 501,{}


def handle_request(service,request):
    from app.config import get_settings
    if not get_settings().demo_mode:raise RuntimeError("Simulator außerhalb der Demo abgelehnt.")
    with LOCK:
        ensure()
        if service not in HOSTS or request.url.scheme!="https" or request.url.host!=HOSTS[service] or request.url.port not in {None,443}:
            STATE["last_error"]="Externes Integrationsziel in der Demo blockiert. Nur vorbereitete Demo-Adressen verwenden."
            return httpx.Response(403,json={"demo":True,"error":"external destination blocked"})
        try:
            if service=="container_agent":
                from app.demo.container_agent import handle
                return handle(request,STATE)
            data=json.loads(request.content) if request.content else {}
            status,body={"semaphore":semaphore,"vault":vault,"gitlab":gitlab}[service](request,request.url.path,data)
            if status==501:STATE["last_error"]="Dieser API-Aufruf ist im Simulator noch nicht unterstützt."
            return httpx.Response(status,json=copy.deepcopy(body)) if body is not None else httpx.Response(status)
        except httpx.TransportError:raise
        except (ValueError,KeyError,TypeError,IndexError):
            STATE["last_error"]="Ungültiger oder nicht unterstützter Simulator-Aufruf."
            return httpx.Response(422,json={"demo":True,"error":"unsupported simulation request"})


def set_scenario(name):
    with LOCK:
        ensure()
        if name not in SCENARIOS:raise ValueError("Unbekanntes Demo-Szenario.")
        STATE.update(scenario=name,used=[],last_error=None)


def merge_reviews():
    with LOCK:
        ensure()
        count=0
        for mr in STATE["mrs"]:
            if mr["state"]=="opened":
                mr.update(state="merged",merge_commit_sha=mr["sha"])
                STATE["branches"][mr["target_branch"]]=mr["sha"]
                count+=1
        return count


def monitoring(db):
    from app.models import DeploymentSource, utcnow
    from app.demo.seed import identifier
    with LOCK:
        ensure()
        now=int(time.time());scenario=STATE["scenario"]
        observed=now-180 if scenario=="monitor_stale" else now
        rows=[]
        for project in STATE["projects"].values():
            env=project["resources"]["environment"]
            identity=json.loads(env[0].get("json","{}")) if env else {}
            slug=identity.get("tenant_slug", "demo")
            rows.append({"deployment_id":f"demo-{project['id']}","application_id":"azubiorga","application_name":"AzubiOrga · DEMO",
                "release_id":"demo-v1","tenant_slug":slug,"runtime_scope_id":identity.get("runtime_scope_id","demo"),
                "database_type":"postgresql","provider_id":"postgresql-v1","database_mode":"shared_pool","dataset_id":"none",
                "source_git_commit":STATE["branches"]["main"],"url":"","host_port":None,"created_at":int(STATE["started"])-120,
                "ready_at":int(STATE["started"])-60,"expires_at":now-30 if scenario=="ttl_expired" else int(STATE["started"])+3600,
                "lifecycle_status":"running","container_count":2,"running_count":1 if scenario=="monitor_degraded" else 2,
                "unhealthy_count":0,"starting_count":0,"metadata_error":False,"observed_at":observed,"retained":False})
        row=db.get(DeploymentSource,identifier("monitoring"))
        if row is None:
            row=DeploymentSource(id=identifier("monitoring"),name="Demo-Zielhost · simuliert",token_hash=hashlib.sha256(b"demo-only-not-a-real-collector-token").hexdigest())
            db.add(row)
        row.snapshot={"schema_version":1,"observed_at":observed,"complete":True,"warnings":[],"deployments":rows}
        row.received_at=utcnow()
        db.commit()
