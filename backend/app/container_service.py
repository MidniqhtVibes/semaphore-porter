"""Optional HTTPS agent connections. No Docker socket in the portal backend."""
from __future__ import annotations
import asyncio
import hashlib
import json
import re
import ssl
import tempfile
from pathlib import Path
import uuid
from urllib.parse import urlsplit

import httpx
from app.integration_http import integration_client
from app.models import ContainerSettings
from app.security import decrypt_secret,encrypt_secret


class AgentError(Exception):
    def __init__(self,message,status=502,uncertain=False):
        self.status,self.uncertain=status,uncertain
        super().__init__(message)


def configuration(db):
    row=db.get(ContainerSettings,1)
    return json.loads(decrypt_secret(row.encrypted_configuration)) if row else {"enabled":False,"revision":"","agents":[]}


def public_configuration(db):
    config=configuration(db)
    return {**config,"agents":[{key:value for key,value in agent.items() if key not in {"token","client_key"}}|{"token_present":bool(agent.get("token")),"client_key_present":bool(agent.get("client_key"))} for agent in config["agents"]]}


def tls_context(ca):
    context=ssl.create_default_context()
    if ca:
        if "PRIVATE KEY" in ca: raise ValueError("Nur öffentliche CA-Zertifikate, keine privaten Schlüssel eintragen.")
        try: context.load_verify_locations(cadata=ca)
        except (ValueError,ssl.SSLError) as exc: raise ValueError("Ungültiges CA-Zertifikat im PEM-Format.") from exc
    return context


def safe_url(value):
    value=value.strip().rstrip("/")
    try: parsed=urlsplit(value);port=parsed.port
    except ValueError as exc: raise ValueError("Ungültige Agent-URL.") from exc
    if (parsed.scheme!="https" or not parsed.hostname or parsed.username is not None or parsed.password is not None or port==0
        or parsed.query or parsed.fragment or re.search(r"[\s\\\x00-\x1f\x7f%]",value) or any(p in {".",".."} for p in parsed.path.split("/"))):
        raise ValueError("Agent benötigt eine HTTPS-URL ohne Zugangsdaten, Query oder Fragment.")
    return value


def client_tls(agent):
    context=tls_context(agent.get("ca_pem",""))
    certificate,key=agent.get("client_cert_pem",""),agent.get("client_key","")
    if certificate or key:
        if not certificate or not key: raise ValueError("Für mTLS sind Client-Zertifikat und privater Schlüssel erforderlich.")
        # ssl loads the key into its context; private temporary files are removed
        # before an HTTP request starts, including when PEM parsing fails.
        with tempfile.TemporaryDirectory(prefix="semaporter-agent-tls-") as folder:
            cert_file,key_file=Path(folder)/"client.pem",Path(folder)/"key.pem"
            cert_file.write_text(certificate,encoding="utf-8");key_file.write_text(key,encoding="utf-8")
            key_file.chmod(0o600)
            try: context.load_cert_chain(certfile=cert_file,keyfile=key_file,password=lambda:"")
            except (ValueError,ssl.SSLError) as exc: raise ValueError("Ungültiges Client-Zertifikat/Schlüsselpaar; unverschlüsselten PEM-Schlüssel verwenden.") from exc
    return context


def connection_id(agent):
    return hashlib.sha256((agent["id"]+"|"+agent["base_url"]).encode()).hexdigest()


def save_configuration(db,payload):
    old=configuration(db)
    if old["revision"]!=payload.revision: raise AgentError("Konfiguration wurde geändert. Neu laden.",409)
    previous={agent["id"]:agent for agent in old["agents"]};agents=[]
    for entry in payload.agents:
        agent=entry.model_dump(mode="json",exclude={"token","client_key","clear_client_certificate"})
        agent["base_url"]=safe_url(agent["base_url"])
        before=previous.get(agent["id"],{})
        token=entry.token.get_secret_value() if entry.token else ""
        agent["token"]=token or (before.get("token","") if before.get("base_url")==agent["base_url"] else "")
        if entry.clear_client_certificate:
            agent["client_cert_pem"],agent["client_key"]="",""
        else:
            private_key=entry.client_key.get_secret_value() if entry.client_key else ""
            same=before.get("base_url")==agent["base_url"] and before.get("client_cert_pem","")==agent["client_cert_pem"]
            agent["client_key"]=private_key or (before.get("client_key","") if same else "")
        if not 32<=len(agent["token"])<=500 or re.search(r"[\s\x00-\x1f\x7f]",agent["token"]): raise ValueError("Agent-Token benötigt 32–500 Zeichen ohne Leer- oder Steuerzeichen; bei geändertem Ziel neu eintragen.")
        agent["projects"]=sorted(set(agent["projects"]))
        if any(not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,99}",p) for p in agent["projects"]): raise ValueError("Exakte Compose-Projektnamen mit Kleinbuchstaben, Ziffern, Bindestrich oder Unterstrich angeben.")
        if agent["active"] and not agent["use_agent_scope"] and not agent["projects"]: raise ValueError("Pro aktivem Agenten Projekte oder ausdrücklich den gesamten Agent-Umfang freigeben.")
        client_tls(agent);agents.append(agent)
    if len({a["id"] for a in agents})!=len(agents): raise ValueError("Agent-ID darf nur einmal vorkommen.")
    if payload.enabled and not any(a["active"] for a in agents): raise ValueError("Zum Aktivieren mindestens einen Agenten freigeben.")
    row=db.get(ContainerSettings,1) or ContainerSettings(id=1)
    row.encrypted_configuration=encrypt_secret(json.dumps({"enabled":payload.enabled,"agents":agents,"revision":uuid.uuid4().hex}))
    db.add(row)


def find_agent(config,agent_id,*,test=False):
    if not test and not config["enabled"]: raise AgentError("Container-Verwaltung ist deaktiviert. Einrichtung ist optional.",409)
    agent=next((a for a in config["agents"] if a["id"]==str(agent_id)),None)
    if not agent: raise AgentError("Agent nicht gefunden.",404)
    if not test and not agent["active"]: raise AgentError("Agent ist deaktiviert.",409)
    return agent


class AgentClient:
    def __init__(self,agent): self.agent=agent

    async def request(self,method,path,*,params=None,payload=None):
        agent=self.agent
        try:
            async with asyncio.timeout(35):
                async with integration_client("container_agent",verify=client_tls(agent),trust_env=False,follow_redirects=False,
                    timeout=httpx.Timeout(30,connect=5),headers={"Authorization":"Bearer "+agent["token"]}) as client:
                    async with client.stream(method,agent["base_url"]+"/v1"+path,params=params,json=payload) as response:
                        code=response.status_code
                        if code>=300:
                            status=403 if code in {401,403} else 404 if code==404 else 409 if code==409 else 502
                            message={403:"Agent lehnt den Zugriff ab. Token, Host-Freigaben und Aktionen prüfen.",404:"Agent-Ressource nicht gefunden. Ansicht aktualisieren.",409:"Agent meldet einen Zustandskonflikt. Zustand und offene Aufträge prüfen."}.get(status,f"Agent-Fehler HTTP {code}. Agent-Protokoll prüfen.")
                            raise AgentError(message,status,method!="GET" and code>=500)
                        chunks,size=[],0
                        async for chunk in response.aiter_bytes():
                            size+=len(chunk)
                            if size>4*1024*1024: raise AgentError("Agent-Antwort überschreitet die Größenbegrenzung.",uncertain=method!="GET")
                            chunks.append(chunk)
            return json.loads(b"".join(chunks))
        except AgentError: raise
        except (httpx.HTTPError,TimeoutError,ssl.SSLError) as exc:
            raise AgentError("Agent nicht erreichbar. URL, Zertifikat und Netzwerkweg prüfen."+(" Das Schreibergebnis ist möglicherweise unklar." if method!="GET" else ""),uncertain=method!="GET") from exc
        except (ValueError,TypeError) as exc: raise AgentError("Ungültige Agent-Antwort.",uncertain=method!="GET") from exc


def in_scope(agent,row): return agent["use_agent_scope"] or row.get("stack") in agent["projects"]


def public_container(agent,row):
    if not isinstance(row,dict) or not re.fullmatch(r"[a-f0-9]{64}",str(row.get("id",""))): raise AgentError("Ungültige Containerdaten des Agenten.")
    result={key:row.get(key,[] if key in {"ports","networks","volumes","actions"} else "") for key in ("id","name","image","image_id","stack","state","status","ports","networks","volumes","protected","actions")}
    result["actions"]=[a for a in result["actions"] if a in agent["allowed_actions"]] if agent["write_enabled"] else []
    if "details" in row: result["details"]=row["details"]
    return result


async def inventory(agent):
    data=await AgentClient(agent).request("GET","/inventory")
    if not isinstance(data,dict) or not isinstance(data.get("containers"),list): raise AgentError("Ungültige Containerliste des Agenten.")
    rows=[public_container(agent,row) for row in data["containers"] if in_scope(agent,row)]
    return {"containers":rows,"stacks":sorted({r["stack"] for r in rows if r["stack"]}),"images":sorted({r["image"] for r in rows}),
        "volumes":sorted({n for r in rows for n in r["volumes"]}),"networks":sorted({n for r in rows for n in r["networks"]})}


async def detail(agent,container_id):
    if not re.fullmatch(r"[a-f0-9]{64}",container_id): raise AgentError("Vollständige Container-ID erforderlich.",422)
    row=await AgentClient(agent).request("GET",f"/containers/{container_id}")
    if not isinstance(row,dict) or row.get("id")!=container_id: raise AgentError("Widersprüchliche Containerdaten des Agenten.")
    if not in_scope(agent,row): raise AgentError("Container ist in Semaporter nicht freigegeben.",403)
    return public_container(agent,row)
