"""Registry selection for create-only tenant onboarding; no registry provisioning."""
from __future__ import annotations

import json
import re
import uuid
from urllib.parse import urlsplit

from app.models import RegistryProfile, RegistrySettings
from app.project_backup import is_defaults, json_object
from app.security import decrypt_secret, encrypt_secret, stable_digest
from app.tenant_options import selected_options
from app.vault_catalog import load_catalog, validate_value
from app.vault_client import VaultClient, safe_path, safe_url


def connection(db):
    row = db.get(RegistrySettings, 1)
    return json.loads(decrypt_secret(row.encrypted_configuration)) if row else {}


def connection_id(config):
    return stable_digest(json.dumps({key: config.get(key, "") for key in ("base_url", "namespace", "kv_mount", "auth_mount")}, sort_keys=True)).hex()


def public_connection(db):
    config = connection(db)
    return {"configured": bool(config), **{key: config.get(key, "") for key in ("base_url", "namespace", "kv_mount", "auth_mount")},
        "role_id_present": bool(config.get("role_id")), "secret_id_present": bool(config.get("secret_id"))}


def save_connection(db, payload):
    old = connection(db)
    config = payload.model_dump(exclude={"role_id", "secret_id"})
    config["base_url"] = safe_url(config["base_url"])
    for key in ("kv_mount", "auth_mount"):
        safe_path(config[key])
    if config["namespace"]: safe_path(config["namespace"])
    same = bool(old) and connection_id(config) == connection_id(old)
    for key in ("role_id", "secret_id"):
        value = getattr(payload, key)
        config[key] = value.get_secret_value() if value and value.get_secret_value() else old.get(key) if same else None
        if not config[key]: raise ValueError("Registry-Vault-Leser benötigt eigene Role-ID und Secret-ID; bei geändertem Ziel neu eintragen.")
    row = db.get(RegistrySettings, 1) or RegistrySettings(id=1)
    row.encrypted_configuration = encrypt_secret(json.dumps(config)); db.add(row)


def reader(config):
    if not config or not config.get("role_id") or not config.get("secret_id"):
        raise ValueError("Eigenen Vault-Lesezugang für Registry-Profile zuerst konfigurieren.")
    return VaultClient({**config, "writer_auth_mount": config["auth_mount"],
        "writer_role_id": config["role_id"], "writer_secret_id": config["secret_id"]})


def registry_host(value):
    value = value.strip().lower()
    if re.search(r"[\s/@?#\\]", value) or "://" in value:
        raise ValueError("Registry-Host als Hostname oder IP mit optionalem Port angeben, ohne Protokoll/Pfad/Zugangsdaten.")
    try:
        parsed = urlsplit("https://" + value)
        if parsed.port is not None and parsed.port < 1:
            raise ValueError()
    except ValueError as exc:
        raise ValueError("Ungültiger Registry-Host oder Port; Port muss zwischen 1 und 65535 liegen.") from exc
    if not parsed.hostname or not re.fullmatch(r"[a-z0-9._:\[\]-]+", value):
        raise ValueError("Ungültiger Registry-Host.")
    return value


def variable_name(value, kind):
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,159}", value) or "registry" not in value.lower():
        raise ValueError("Expliziten öffentlichen Registry-Variablennamen des Deployment-Stacks angeben.")
    endings = ("_host", "_url") if kind == "host" else ("_username", "_user")
    if not value.lower().endswith(endings) or any(word in value.lower() for word in ("password", "token", "secret", "private", "vault")):
        raise ValueError("Registry-Zuordnung benötigt eine Host-/URL- bzw. Benutzer-Variable, keinen Secret-Schlüssel.")
    return value


def public_profile(row):
    return {"id": str(row.id), "name": row.name, "application_id": row.application_id, "host": row.host, "username": row.username,
        "host_variable": row.host_variable, "username_variable": row.username_variable, "source": row.source,
        "vault_path": row.vault_path, "vault_version": row.vault_version, "vault_field": row.vault_field,
        "is_active": row.is_active, "revision": row.revision, "password_present": row.source == "stored"}


def registry_fields(db, app_id):
    app = load_catalog(db).applications.get(app_id)
    fields = [field for field in app.fields if field.source == "registry"] if app else []
    if not app or len(fields) != 1 or (app.registry and not app.registry.login):
        raise ValueError("Die Anwendung benötigt keinen unterstützten einzelnen Registry-Zugang im aktuellen Katalog.")
    return app, fields


async def resolve(db, row):
    if not row.is_active: raise ValueError("Registry-Profil ist gesperrt.")
    _, fields = registry_fields(db, row.application_id)
    if row.source == "stored":
        if not row.encrypted_password: raise ValueError("Registry-Profil enthält keinen Zugang.")
        value = decrypt_secret(row.encrypted_password)
    else:
        config = connection(db)
        if connection_id(config) != row.vault_connection_id:
            raise ValueError("Registry-Vault-Verbindung wurde geändert. Profilquelle ausdrücklich neu zuordnen.")
        client = reader(config); await client.login()
        result = await client._request("GET", f"{safe_path(config['kv_mount'])}/data/{safe_path(row.vault_path)}", params={"version": row.vault_version})
        data = result.get("data", {}) if isinstance(result, dict) else {}
        if not isinstance(data, dict) or not isinstance(data.get("metadata"), dict) or not isinstance(data.get("data"), dict):
            raise ValueError("Registry-Vault lieferte keine gültigen KV-v2-Daten.")
        metadata = data.get("metadata", {})
        if metadata.get("version") != row.vault_version or metadata.get("destroyed") or metadata.get("deletion_time"):
            raise ValueError("Registry-Vault-Version fehlt, wurde gelöscht oder ist zerstört.")
        value = data.get("data", {}).get(row.vault_field)
        if not isinstance(value, str) or not value: raise ValueError("Registry-Secret-Feld fehlt oder enthält keinen gültigen Textwert.")
    for field in fields: validate_value(field.model_dump(), value)
    return value


async def prepare_bindings(db, draft, prepared):
    bindings = draft.get("registry_profiles") or {}
    apps = selected_options(draft, "application_id") or []
    if set(bindings) - set(apps): raise ValueError("Registry-Zuordnung enthält eine nicht ausgewählte Anwendung.")
    plans, assignments = [], {}
    catalog = load_catalog(db)
    available = {name for group in prepared.get("environments", []) for field in ("json", "env") for name in json_object(group.get(field))}
    for app_id, profile_id in bindings.items():
        if profile_id == "legacy": continue
        row = db.get(RegistryProfile, uuid.UUID(str(profile_id)))
        if row is None or row.application_id != app_id: raise ValueError("Registry-Profil fehlt oder gehört zu einer anderen Anwendung.")
        value = await resolve(db, row)
        contract = catalog.applications[app_id].registry
        if contract:
            if (row.host_variable, row.username_variable) != (contract.host_variable, contract.username_variable):
                raise ValueError(f"{app_id}: Registry-Variablen des Profils passen nicht zum aktuellen Stack-Vertrag.")
        elif not {row.host_variable, row.username_variable}.issubset(available):
            raise ValueError(f"{app_id}: Registry-Variablennamen im Profil mit der Projektvorlage abgleichen; bei altem Katalog müssen beide Variablen vorhanden sein.")
        # This installation uses one fixed registry per application. A different
        # host in the template must be corrected deliberately, never silently.
        hosts = [json_object(group.get(field)).get(row.host_variable) for group in prepared["environments"] for field in ("json", "env")]
        if any(value and registry_host(str(value)) != row.host for value in hosts):
            raise ValueError(f"{app_id}: Registry-Host in Vorlage und ausgewähltem Profil stimmt nicht überein.")
        for key, public_value in ((row.host_variable, row.host), (row.username_variable, row.username)):
            if key in assignments and assignments[key] != public_value:
                raise ValueError("Mehrere Anwendungen verwenden dieselbe Registry-Variable mit unterschiedlichen Werten. Anwendungsspezifische Variablen verwenden.")
            assignments[key] = public_value
        plan = public_profile(row)
        plan["value_revision"] = stable_digest(value).hex()
        plans.append(plan)
    if assignments:
        for task in prepared["templates"]:
            if any(field.get("name") in assignments for field in task.get("survey_vars") or []):
                raise ValueError("Registry-Host und Benutzer dürfen im verwalteten Projekt nicht über Task-Surveys überschreibbar sein.")
        defaults = next((group for group in prepared["environments"] if is_defaults(group.get("name", ""))), None)
        if defaults is None: raise ValueError("Semaphore-Defaults für Registry-Zuordnung fehlt.")
        for group in prepared["environments"]:
            for field in ("json", "env"):
                values = {key: value for key, value in json_object(group.get(field)).items() if key not in assignments}
                if group is defaults and field == "json": values.update(assignments)
                group[field] = json.dumps(values)
    return plans


async def execution_values(db, plans):
    values = {}
    for plan in plans or []:
        row = db.get(RegistryProfile, uuid.UUID(plan["id"]))
        if row is None or not row.is_active or row.revision != plan["revision"]:
            raise ValueError("Registry-Profil wurde geändert/gesperrt. Entwurf vor dem ersten Schreiben erneut validieren.")
        value = await resolve(db, row)
        if stable_digest(value).hex() != plan["value_revision"]:
            raise ValueError("Registry-Quellwert wurde geändert. Entwurf erneut validieren.")
        values[plan["application_id"]] = value
    return values
