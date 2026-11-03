"""Synthetic agent protocol; no imports or access to a real Docker client."""
import copy
import hashlib
import json
import time
import httpx


def fixtures():
    rows=[]
    for index,(name,image,project,state,status) in enumerate([
        ("kundenportal-web","nginx:stable","kundenportal","running","Up (healthy)"),
        ("kundenportal-api","example/api:1.4","kundenportal","running","Up (healthy)"),
        ("kundenportal-db","postgres:17","kundenportal","running","Up (healthy)"),
        ("teamwiki","example/wiki:2.1","teamwissen","running","Up (unhealthy)"),
        ("bericht-worker","example/worker:1.0","berichte","exited","Exited (0)"),
        ("semaporter-backend","example/semaporter_backend:latest","semaporter","running","Up (healthy)"),
    ],1):
        rows.append({"id":f"{index:064x}","name":name,"image":image,"image_id":"sha256:"+f"{index+10:064x}",
            "stack":project,"state":state,"status":status,"protected":project=="semaporter",
            "ports":[{"IP":"127.0.0.1","PrivatePort":8080,"PublicPort":18000+index,"Type":"tcp"}],
            "networks":["demo-"+project],"volumes":["demo-"+name+"-data"] if index in {3,4} else [],
            "details":{"started_at":"2026-11-02T10:00:00Z","finished_at":"","exit_code":0,"restart_count":0,"restart_policy":"unless-stopped","environment_names":["APP_MODE","PASSWORD"]}})
    return rows


def public(row):
    result=copy.deepcopy(row)
    result["actions"]=[] if row["protected"] else ["start","remove"] if row["state"]=="exited" else ["resume","stop"] if row["state"]=="paused" else ["stop","restart","pause"]
    return result


def handle(request,state):
    if request.headers.get("authorization")!="Bearer demo-container-agent-token-0000000000000000": return httpx.Response(401)
    rows=state.setdefault("managed_containers",fixtures());operations=state.setdefault("container_operations",{})
    path=request.url.path.removeprefix("/v1/")
    if path=="info": return httpx.Response(200,json={"protocol":1,"name":"Demo · Dauerbetrieb","projects":["kundenportal","teamwissen","berichte","semaporter"],"allow_all":False,"container_ids":[],"actions":["start","stop","restart","pause","resume","remove"]})
    if path=="inventory": return httpx.Response(200,json={"containers":[public(row) for row in rows]})
    if path.startswith("operations/"):
        parts=path.split("/");operation=operations.get(parts[1])
        if not operation: return httpx.Response(404)
        if len(parts)==3 and parts[2]=="review": operation.update(status="reviewed",requires_review=False,message="Demo-Ergebnis geprüft. Keine Aktion wiederholt.")
        return httpx.Response(200,json={key:value for key,value in operation.items() if key!="digest"})
    parts=path.split("/")
    if len(parts)<2 or parts[0]!="containers": return httpx.Response(404)
    row=next((r for r in rows if r["id"]==parts[1]),None)
    if not row: return httpx.Response(404)
    if len(parts)==2: return httpx.Response(200,json=public(row))
    if parts[2]=="logs": return httpx.Response(200,json={"text":"[Demo] Dienst vorbereitet.\n[Demo] Status: "+row["status"]+"\n","truncated":False})
    if parts[2]=="stats":
        running=row["state"]=="running"
        return httpx.Response(200,json={"running":running,"cpu_percent":4.5 if running else None,"memory_bytes":83886080 if running else None,"memory_limit":536870912 if running else None,"network_rx":12582912 if running else None,"network_tx":4194304 if running else None,"block_read":1048576 if running else None,"block_write":2097152 if running else None})
    if parts[2]=="actions" and request.method=="POST":
        command=json.loads(request.content);action=command["action"];key=command["operation_id"]
        digest=hashlib.sha256(request.content).hexdigest()
        if key in operations:
            if operations[key]["digest"]!=digest: return httpx.Response(409)
            return httpx.Response(200,json={k:v for k,v in operations[key].items() if k!="digest"})
        expected={"image_id":row["image_id"],"state":row["state"],"started_at":row["details"]["started_at"]}
        if action not in public(row)["actions"]: return httpx.Response(403)
        if command["expected"]!=expected or command["expires_at"]<time.time(): return httpx.Response(409)
        if action=="remove": rows.remove(row)
        else:
            row["state"]="exited" if action=="stop" else "paused" if action=="pause" else "running"
            row["status"]=row["state"]
            if action in {"start","restart"}: row["details"]["started_at"]=str(time.time())
            if action=="restart": row["details"]["restart_count"]+=1
        operation={"id":key,"target":row["id"],"action":action,"status":"success","message":"Simulierter Docker-Agent hat die Aktion bestätigt.","created":time.time(),"requires_review":False,"digest":digest}
        operations[key]=operation
        if state["scenario"]=="container_uncertain" and "container_uncertain" not in state["used"]:
            state["used"].append("container_uncertain")
            raise httpx.ReadTimeout("Demo: Antwort nach ausgeführter Aktion verloren",request=request)
        return httpx.Response(200,json={k:v for k,v in operation.items() if k!="digest"})
    return httpx.Response(404)
