"""Vault is the source of truth. No SSH private material is persisted here."""
from __future__ import annotations

import base64
import hashlib
import json
import re
import shlex
import uuid
from typing import Any
from urllib.parse import urlsplit

import yaml
from cryptography.exceptions import UnsupportedAlgorithm
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec, ed25519, rsa
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import CredentialProfile, CredentialSettings, CredentialUse, CreationJob, CreationStatus, SemaphoreSettings, User, utcnow
from app.audit import record_audit
from app.security import decrypt_secret, encrypt_secret
from app.semaphore_client import SemaphoreClient
from app.vault_client import VaultClient, VaultError, safe_path, safe_url


def configuration(db: Session) -> dict:
    row = db.get(CredentialSettings, 1)
    return json.loads(decrypt_secret(row.encrypted_configuration)) if row else {}


def source_identity(config: dict) -> dict:
    return {key: config.get(key, "") for key in ("base_url", "namespace", "kv_mount", "auth_mount")}


def semaphore_identity(db: Session) -> str:
    row = db.scalar(select(SemaphoreSettings).where(SemaphoreSettings.id == 1).execution_options(populate_existing=True))
    if row is None:
        raise ValueError("Semaphore zuerst konfigurieren.")
    return row.base_url.rstrip("/")


def frozen_plans(db: Session):
    for job in db.scalars(select(CreationJob).where(CreationJob.status != CreationStatus.COMPLETED)):
        if job.credential_progress:
            yield from job.credential_plan or []


def save_configuration(db: Session, values: dict) -> None:
    config = configuration(db)
    for key, value in values.items():
        if key not in {"role_id", "secret_id"} or value:
            config[key] = value
    config["base_url"] = safe_url(config["base_url"])
    if not config["base_url"].startswith("https://"):
        raise ValueError("Der zentrale Schlüsselspeicher benötigt HTTPS.")
    for key in ("kv_mount", "auth_mount"):
        safe_path(config[key])
    if config.get("namespace"):
        safe_path(config["namespace"])
    if not config.get("role_id") or not config.get("secret_id"):
        raise ValueError("Für den Profil-Lesezugang sind Role-ID und Secret-ID erforderlich.")
    old = configuration(db)
    if old and source_identity(old) != source_identity(config):
        if db.scalar(select(CredentialUse.id).limit(1)) or next(frozen_plans(db), None):
            raise ValueError("Der Schlüsselspeicher wird bereits verwendet. Zugangsdaten können erneuert werden; die Zielverbindung bleibt fest.")
        for profile in db.scalars(select(CredentialProfile)):
            profile.fingerprint = profile.public_key = profile.last_tested_at = None
    row = db.get(CredentialSettings, 1) or CredentialSettings(id=1)
    row.encrypted_configuration = encrypt_secret(json.dumps(config))
    db.add(row)


def public_configuration(db: Session) -> dict:
    config = configuration(db)
    return {"configured": bool(config), **source_identity(config),
            "role_id_present": bool(config.get("role_id")), "secret_id_present": bool(config.get("secret_id"))}


def vault_client(config: dict) -> VaultClient:
    if not config:
        raise ValueError("Den Vault-Lesezugang zuerst unter Zugangsprofile konfigurieren.")
    return VaultClient({**config, "writer_auth_mount": config["auth_mount"],
                        "writer_role_id": config["role_id"], "writer_secret_id": config["secret_id"]})


def host(value: str) -> str:
    value = value.strip().lower().strip("[]").rstrip(".")
    if not re.fullmatch(r"[a-z0-9][a-z0-9_.:-]*", value):
        raise ValueError("Zielhosts müssen konkrete DNS-Namen oder IP-Adressen sein; keine Muster oder Variablen.")
    return value


def git_target(value: str, login: str | None = None) -> str:
    parts = urlsplit(value)
    if parts.scheme == "ssh" and parts.hostname and not parts.password and not parts.query and not parts.fragment:
        user, hostname, path, port = parts.username, parts.hostname, parts.path.lstrip("/"), parts.port
    else:
        match = re.fullmatch(r"(?:(?P<user>[A-Za-z0-9_.-]+)@)?(?P<host>[A-Za-z0-9_.-]+):(?P<path>[^\s?#]+)", value)
        if not match:
            raise ValueError("Git-Profile benötigen eine konkrete SSH-Repository-URL, z. B. git@git.example:gruppe/projekt.git.")
        user, hostname, path, port = match["user"], match["host"], match["path"], None
    if login and user and user != login:
        raise ValueError("Git-URL und Zugangsprofil verwenden unterschiedliche SSH-Benutzer.")
    if not path or any(segment in {"", ".", ".."} for segment in path.split("/")):
        raise ValueError("Git-Ziel benötigt einen konkreten Repository-Pfad.")
    return f"{host(hostname)}{':' + str(port) if port and port != 22 else ''}/{path.removesuffix('.git')}"


def normalize_targets(purpose: str, values: list[str]) -> list[str]:
    return list(dict.fromkeys(host(value) if purpose == "host" else git_target(value) for value in values))


def inventory_targets(resource: dict, login: str) -> list[str]:
    if resource.get("type", "static") not in {"static", "static-yaml"}:
        raise ValueError("Automatische SSH-Zuordnung unterstützt statische INI- oder YAML-Inventories. Dynamische Inventories manuell prüfen.")
    raw = resource.get("inventory") or ""
    if not isinstance(raw, str) or "{{" in raw or "{%" in raw or len(raw) > 500_000:
        raise ValueError("Inventory-Ziele müssen statisch und eindeutig prüfbar sein.")
    targets: list[str] = []

    def check_vars(values):
        if not isinstance(values, dict):
            return
        for name in ("ansible_user", "ansible_ssh_user"):
            if name in values and str(values[name]) != login:
                raise ValueError("SSH-Benutzer im Inventory und im Zugangsprofil stimmen nicht überein.")
        if values.get("ansible_connection") == "local":
            raise ValueError("Lokale Inventories benötigen kein SSH-Profil.")

    try:
        parsed = yaml.safe_load(raw)
    except yaml.YAMLError:
        parsed = None
    if isinstance(parsed, dict):
        def walk(group, depth=0):
            if not isinstance(group, dict) or depth > 20:
                raise ValueError("Ungültige YAML-Inventory-Gruppe.")
            variables = group.get("vars") or {}
            check_vars(variables)
            if not isinstance(variables, dict) or "ansible_host" in variables or "ansible_ssh_host" in variables:
                raise ValueError("Gruppenweite Host-Overrides bitte durch konkrete Host-Zuordnungen ersetzen.")
            hosts = group.get("hosts") or {}
            if not isinstance(hosts, dict):
                raise ValueError("YAML-Inventory benötigt benannte Hosts.")
            for name, values in hosts.items():
                values = values or {}
                if not isinstance(values, dict):
                    raise ValueError("Ungültige YAML-Hostvariablen.")
                check_vars(values)
                targets.append(host(str(values.get("ansible_host", values.get("ansible_ssh_host", name)))))
            children = group.get("children") or {}
            if not isinstance(children, dict):
                raise ValueError("YAML-Inventory benötigt benannte Gruppen.")
            for child in children.values():
                walk(child, depth + 1)
        for group in parsed.values():
            walk(group)
    else:
        section = ""
        for line in raw.splitlines():
            line = line.strip()
            if not line or line.startswith(("#", ";")):
                continue
            if line.startswith("[") and line.endswith("]"):
                section = line[1:-1]
                continue
            words = shlex.split(line, comments=True)
            if not words:
                continue
            if section.endswith(":vars"):
                values = dict(word.split("=", 1) for word in words if "=" in word)
                check_vars(values)
                if "ansible_host" in values or "ansible_ssh_host" in values:
                    raise ValueError("Gruppenweite Host-Overrides bitte durch konkrete Host-Zuordnungen ersetzen.")
                continue
            if section.endswith(":children"):
                continue
            values = dict(word.split("=", 1) for word in words[1:] if "=" in word)
            check_vars(values)
            targets.append(host(values.get("ansible_host", values.get("ansible_ssh_host", words[0]))))
    if not targets:
        raise ValueError("Das Inventory enthält keine prüfbaren SSH-Zielhosts.")
    return sorted(set(targets))


def resource_targets(kind: str, resource: dict, login: str) -> list[str]:
    return inventory_targets(resource, login) if kind == "inventories" else [git_target(resource.get("git_url", ""), login)]


def profile_snapshot(profile: CredentialProfile) -> dict:
    return {"id": str(profile.id), "purpose": profile.purpose, "login": profile.login,
            "vault_path": profile.vault_path, "vault_version": profile.vault_version,
            "allowed_targets": profile.allowed_targets}


async def read_key(client: VaultClient, snapshot: dict) -> dict:
    result = await client._request("GET", f"{safe_path(client.config['kv_mount'])}/data/{safe_path(snapshot['vault_path'])}",
                                   params={"version": snapshot["vault_version"]})
    envelope = result.get("data", {}) if isinstance(result, dict) else {}
    if not isinstance(envelope, dict):
        raise ValueError("Vault lieferte kein gültiges KV-v2-Schlüsselobjekt.")
    metadata, data = envelope.get("metadata", {}), envelope.get("data", {})
    if not isinstance(metadata, dict) or not isinstance(data, dict):
        raise ValueError("Vault lieferte kein gültiges KV-v2-Schlüsselobjekt.")
    if metadata.get("version") != snapshot["vault_version"] or metadata.get("destroyed") or metadata.get("deletion_time"):
        raise ValueError("Die gewählte Vault-Schlüsselversion ist nicht verfügbar.")
    private, passphrase = data.get("private_key"), data.get("passphrase", "")
    if not isinstance(private, str) or not 1 <= len(private) <= 65536 or not isinstance(passphrase, str) or len(passphrase) > 4096:
        raise ValueError("Vault-SSH-Objekt benötigt private_key und optional passphrase als Text.")
    private = private.replace("\r\n", "\n")
    key = None
    for loader in (serialization.load_ssh_private_key, serialization.load_pem_private_key):
        try:
            key = loader(private.encode(), password=passphrase.encode() if passphrase else None)
            break
        except (ValueError, TypeError, UnsupportedAlgorithm):
            pass
    if not isinstance(key, (ed25519.Ed25519PrivateKey, rsa.RSAPrivateKey, ec.EllipticCurvePrivateKey)):
        raise ValueError("SSH-Schlüssel oder Passphrase ist ungültig; Ed25519, RSA oder ECDSA verwenden.")
    if isinstance(key, rsa.RSAPrivateKey) and key.key_size < 2048:
        raise ValueError("RSA-Schlüssel benötigen mindestens 2048 Bit.")
    public = key.public_key().public_bytes(serialization.Encoding.OpenSSH, serialization.PublicFormat.OpenSSH).decode()
    fingerprint = "SHA256:" + base64.b64encode(hashlib.sha256(base64.b64decode(public.split()[1])).digest()).decode().rstrip("=")
    return {"private_key": private, "passphrase": passphrase, "login": snapshot["login"],
            "fingerprint": fingerprint, "public_key": public}


async def prepare_plan(db: Session, draft: dict, prepared: dict) -> list[dict]:
    bindings = draft.get("ssh_bindings") or []
    if not bindings:
        return []
    config = configuration(db)
    client = vault_client(config)
    await client.login()
    plans: dict[str, dict] = {}
    seen = set()
    for binding in bindings:
        resource_kind, name = binding["resource_kind"], binding["resource_name"]
        if (resource_kind, name) in seen:
            raise ValueError("Jede Ressource darf nur einem SSH-Profil zugeordnet werden.")
        seen.add((resource_kind, name))
        profile = db.get(CredentialProfile, uuid.UUID(binding["profile_id"]))
        if not profile or not profile.is_active:
            raise ValueError("Ein gewähltes Zugangsprofil fehlt oder ist gesperrt.")
        if profile.purpose != ("host" if resource_kind == "inventories" else "git"):
            raise ValueError("Das Zugangsprofil passt nicht zum Ressourcentyp.")
        matches = [item for item in prepared.get(resource_kind, []) if item.get("name") == name]
        if len(matches) != 1:
            raise ValueError("Die zugeordnete Ressource fehlt oder ist nicht eindeutig.")
        resource = matches[0]
        targets = resource_targets(resource_kind, resource, profile.login)
        if not set(targets).issubset(normalize_targets(profile.purpose, profile.allowed_targets)):
            raise ValueError(f"{profile.name}: Ressource enthält ein nicht freigegebenes Ziel.")
        identifier = str(profile.id)
        if identifier not in plans:
            snapshot = profile_snapshot(profile)
            key = await read_key(client, snapshot)
            key_name = f"Semaporter-{profile.purpose}-{profile.id.hex}"
            existing = [k for k in prepared.get("keys", []) if k.get("name") == key_name]
            if len(existing) > 1 or existing and existing[0].get("type") != "ssh":
                raise ValueError("Der verwaltete Schlüsselname ist in der Vorlage nicht eindeutig als SSH-Zugang vorhanden.")
            plans[identifier] = {"profile": snapshot, "name": profile.name, "source": source_identity(config),
                "semaphore_url": semaphore_identity(db),
                "fingerprint": key["fingerprint"], "public_key": key["public_key"], "key_name": key_name, "bindings": []}
            if not existing:
                prepared.setdefault("keys", []).append({"name": key_name, "type": "ssh"})
        resource["ssh_key"] = plans[identifier]["key_name"]
        resource.pop("ssh_key_id", None)
        plans[identifier]["bindings"].append({"kind": resource_kind, "name": name, "targets": targets})
    for item in plans.values():
        covered = {(binding["kind"], binding["name"]) for binding in item["bindings"]}
        for kind in ("inventories", "repositories"):
            for resource in prepared.get(kind, []):
                if resource.get("ssh_key") == item["key_name"] and (kind, resource.get("name")) not in covered:
                    raise ValueError("Ein kopierter verwalteter Schlüssel wird von weiteren Ressourcen verwendet. Diesen Ressourcen ausdrücklich ein passendes Profil zuweisen.")
                if kind == "inventories" and resource.get("become_key") == item["key_name"]:
                    raise ValueError("SSH-Profile nicht zugleich als Become-Zugang verwenden. Become separat konfigurieren.")
    return list(plans.values())


async def check_plan(db: Session, job: CreationJob) -> None:
    if not job.credential_plan:
        return
    config = configuration(db)
    client = vault_client(config)
    await client.login()
    for item in job.credential_plan:
        if semaphore_identity(db) != item["semaphore_url"]:
            raise ValueError("Die Semaphore-Instanz wurde geändert. SSH-Zuordnungen gehören zur ursprünglichen Instanz.")
        profile = db.scalar(select(CredentialProfile).where(CredentialProfile.id == uuid.UUID(item["profile"]["id"]))
                            .with_for_update().execution_options(populate_existing=True))
        if not profile or not profile.is_active:
            raise ValueError("Ein Zugangsprofil wurde gesperrt oder entfernt.")
        if any(not set(binding["targets"]).issubset(normalize_targets(profile.purpose, profile.allowed_targets))
               for binding in item["bindings"]):
            raise ValueError("Ein Ziel ist nicht mehr für das Zugangsprofil freigegeben.")
        if source_identity(config) != item["source"]:
            raise ValueError("Der zentrale Schlüsselspeicher wurde geändert; Vorgang prüfen.")
        if any(getattr(profile, field) != item["profile"][field] for field in ("purpose", "login", "vault_path")):
            raise ValueError("Die SSH-Identität eines gewählten Profils wurde geändert. Entwurf erneut validieren.")
        # Once started, an unfinished job keeps its pinned version, including during rotation.
        if not job.credential_progress and profile_snapshot(profile) != item["profile"]:
            raise ValueError("Ein Zugangsprofil wurde geändert. Entwurf erneut validieren.")
        key = await read_key(client, item["profile"])
        if key["fingerprint"] != item["fingerprint"]:
            raise ValueError("Die geprüfte Schlüsselversion stimmt nicht mehr überein.")
    job.credential_progress = job.credential_progress or {"started": True}
    db.commit()


async def install(db: Session, job: CreationJob, semaphore: SemaphoreClient) -> None:
    if not job.credential_plan:
        return
    config = configuration(db)
    client = vault_client(config)
    await client.login()
    keys = await semaphore.list_resources(job.semaphore_project_id, "keys")
    for item in job.credential_plan:
        if semaphore_identity(db) != item["semaphore_url"] or source_identity(config) != item["source"]:
            raise ValueError("Die Zielverbindungen weichen vom geprüften SSH-Plan ab.")
        matches = [key for key in keys if key.get("name") == item["key_name"] and key.get("type") == "ssh"
                   and not key.get("source_storage_type")]
        if len(matches) != 1:
            raise ValueError("Der verwaltete SSH-Eintrag fehlt im Zielprojekt oder ist nicht eindeutig. Projekt prüfen.")
        key_id = matches[0]["id"]
        bindings = []
        for binding in item["bindings"]:
            kind = "inventory" if binding["kind"] == "inventories" else "repositories"
            resources = await semaphore.list_resources(job.semaphore_project_id, kind)
            matches = [resource for resource in resources if resource.get("name") == binding["name"]]
            if len(matches) != 1:
                raise ValueError("Eine verwaltete Ressource fehlt im Zielprojekt oder ist nicht eindeutig.")
            resource = await semaphore.get_resource(job.semaphore_project_id, kind, matches[0]["id"])
            if resource.get("ssh_key_id") != key_id or resource_targets(binding["kind"], resource, item["profile"]["login"]) != binding["targets"]:
                raise ValueError("SSH-Zuordnung oder Ziel im neuen Projekt weicht vom geprüften Plan ab.")
            bindings.append({**binding, "resource_id": resource["id"]})
        use = db.scalar(select(CredentialUse).where(CredentialUse.semaphore_project_id == job.semaphore_project_id,
                                                     CredentialUse.profile_id == uuid.UUID(item["profile"]["id"])))
        if use is None:
            use = CredentialUse(profile_id=uuid.UUID(item["profile"]["id"]), creation_job_id=job.id,
                semaphore_project_id=job.semaphore_project_id, semaphore_key_id=key_id,
                vault_version=item["profile"]["vault_version"], fingerprint=item["fingerprint"],
                bindings=bindings, source={**item["source"], "semaphore_url": item["semaphore_url"], "vault_path": item["profile"]["vault_path"],
                                           "purpose": item["profile"]["purpose"], "login": item["profile"]["login"]}, status="pending")
            db.add(use)
            db.commit()
        elif use.semaphore_key_id != key_id:
            raise ValueError("Die verwaltete Schlüssel-ID wurde verändert. Projekt prüfen.")
        if use.status == "installed":
            continue
        key = await read_key(client, item["profile"])
        if key["fingerprint"] != item["fingerprint"]:
            raise ValueError("SSH-Fingerprint weicht vom geprüften Plan ab.")
        await write_key(db, semaphore, use, item["key_name"], key, item["profile"]["vault_version"])
        record_audit(db, "ssh_profile_assigned", actor=db.get(User, job.created_by_id),
                     target_type="ssh_use", target_id=use.id,
                     details={"profile_id": str(use.profile_id), "project_id": use.semaphore_project_id,
                              "version": use.vault_version, "fingerprint": use.fingerprint})
    job.credential_progress = {"started": True, "installed": True}
    db.commit()


async def write_key(db: Session, semaphore: SemaphoreClient, use: CredentialUse, name: str, key: dict, version: int):
    # Stable PUT to a restored, known ID: retrying sends the same key; it never creates duplicates.
    try:
        await semaphore.save_resource(use.semaphore_project_id, "keys", {
            "id": use.semaphore_key_id, "project_id": use.semaphore_project_id, "name": name,
            "type": "ssh", "override_secret": True,
            "ssh": {field: key[field] for field in ("private_key", "passphrase", "login")}}, use.semaphore_key_id)
    except Exception:
        use.status = "failed"
        use.last_error = "Schlüsselübertragung nicht bestätigt; Wiederaufnahme verwendet denselben Eintrag."
        db.commit()
        raise
    use.status, use.last_error = "installed", None
    use.vault_version, use.fingerprint = version, key["fingerprint"]
    db.commit()
