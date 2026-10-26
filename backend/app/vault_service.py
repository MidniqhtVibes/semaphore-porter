from __future__ import annotations

import copy
import json
import secrets
from typing import Any

from sqlalchemy.orm import Session

from app.models import CreationJob, VaultSettings, utcnow
from app.project_backup import json_object
from app.schemas import VaultFieldInput, VaultSettingsInput
from app.security import decrypt_secret, encrypt_secret, stable_digest
from app.semaphore_client import SemaphoreClient
from app.tenant_options import selected_options
from app.vault_catalog import load_catalog, validate_value
from app.vault_client import VaultClient, VaultError, safe_path, safe_url

SENSITIVE = ("writer_role_id", "writer_secret_id", "reader_role_id", "reader_secret_id")
VAULT_PUBLIC_KEYS = {"vault_url", "vault_kv_mount", "vault_auth_mount", "vault_namespace",
    "vault_tenant_secret_root", "vault_tenant_secret_paths", "vault_program_secret_paths", "vault_provider_secret_paths"}


def configuration(db: Session) -> dict[str, Any]:
    row = db.get(VaultSettings, 1)
    return json.loads(decrypt_secret(row.encrypted_configuration)) if row else {}


def public_configuration(db: Session) -> dict[str, Any]:
    config = configuration(db)
    return {"configured": bool(config), "enabled": bool(config.get("enabled")),
        **{key: value for key, value in config.items() if key not in {*SENSITIVE, "registry_passwords"}},
        "credentials_present": {key: bool(config.get(key)) for key in SENSITIVE},
        "registry_configured": {key: bool(value) for key, value in config.get("registry_passwords", {}).items()}}


def save_configuration(db: Session, payload: VaultSettingsInput) -> None:
    config = configuration(db)
    config.update(payload.model_dump(exclude={*SENSITIVE, "registry_passwords"}))
    config["base_url"] = safe_url(config["base_url"])
    for key in ("kv_mount", "tenant_root", "writer_auth_mount", "reader_auth_mount"):
        safe_path(config[key])
    if config["namespace"]:
        safe_path(config["namespace"])
    for key in SENSITIVE:
        value = getattr(payload, key)
        if value is not None and value.get_secret_value():
            config[key] = value.get_secret_value()
    registry = dict(config.get("registry_passwords", {}))
    catalog = load_catalog(db)
    for app_id, value in payload.registry_passwords.items():
        if app_id not in catalog.applications:
            raise ValueError("Unbekannte Anwendung für Registry-Zugang.")
        if value.get_secret_value():
            for field in catalog.applications[app_id].fields:
                if field.source == "registry":
                    validate_value(field.model_dump(), value.get_secret_value())
            registry[app_id] = value.get_secret_value()
    config["registry_passwords"] = registry
    if config["enabled"] and any(not config.get(key) for key in SENSITIVE):
        raise ValueError("Zum Aktivieren sind Schreib- und Lese-Role-ID sowie beide Secret-IDs erforderlich.")
    row = db.get(VaultSettings, 1) or VaultSettings(id=1)
    row.encrypted_configuration = encrypt_secret(json.dumps(config))
    db.add(row)


def config_revision(config: dict[str, Any]) -> str:
    return stable_digest(json.dumps(config, sort_keys=True)).hex()


def prepare_plan(db: Session, draft: dict[str, Any], prepared: dict[str, Any]) -> dict[str, Any]:
    config = configuration(db)
    if not config.get("enabled"):
        raise ValueError("Vault zuerst unter Administration → Vault vollständig konfigurieren und aktivieren.")
    catalog = load_catalog(db)
    apps = selected_options(draft, "application_id") or []
    types = selected_options(draft, "database_type") or []
    datasets = selected_options(draft, "dataset_id") or ["none"]
    if not apps or not types:
        raise ValueError("Vault benötigt eine ausdrückliche Anwendungs- und Providerauswahl.")
    if any(app not in catalog.applications for app in apps) or any(kind not in catalog.providers for kind in types):
        raise ValueError("Die Auswahl enthält Programme oder Provider ohne gültigen Vault-Katalog.")
    for app_id in apps:
        if not set(types).intersection(catalog.applications[app_id].database_types):
            raise ValueError(f"{app_id}: Kein ausgewählter Provider wird von der Anwendung unterstützt.")
    for kind in types:
        if not any(kind in catalog.applications[app].database_types for app in apps):
            raise ValueError(f"{kind}: Provider wird von keiner ausgewählten Anwendung unterstützt.")
    for ds in datasets:
        if ds != "none" and not any(ds in catalog.applications[a].datasets and
                catalog.applications[a].datasets[ds].database_type in types for a in apps):
            raise ValueError(f"{ds}: Dataset passt zu keiner ausgewählten Anwendungs-/Providerkombination.")
    default_app = catalog.applications[apps[0]]
    default_dataset = default_app.datasets.get(datasets[0])
    if types[0] not in default_app.database_types or (datasets[0] != "none" and
            (not default_dataset or default_dataset.database_type != types[0])):
        raise ValueError("Die Vorgaben für Anwendung, Provider und Dataset passen nicht zusammen. Die Reihenfolge in Schritt 3 anpassen.")
    objects = []
    root = safe_path(f"{config['tenant_root']}/{draft['tenant_slug']}")
    for kind, ids, profiles in (("application", apps, catalog.applications), ("provider", types, catalog.providers)):
        for identifier in ids:
            profile = profiles[identifier]
            if not profile.fields:
                continue
            fields = []
            for field in profile.fields:
                if field.source == "registry" and not config.get("registry_passwords", {}).get(identifier):
                    raise ValueError(f"{identifier}: Zentraler Registry-Zugang fehlt in der Vault-Konfiguration.")
                fields.append({**field.model_dump(), "input_id": f"{kind}:{identifier}.{field.key}"})
            objects.append({"kind": kind, "id": identifier,
                "path": f"{root}/{'providers/' if kind == 'provider' else ''}{profile.profile}", "fields": fields})
    if len({o["path"] for o in objects}) != len(objects):
        raise ValueError("Mehrere Profile ergeben denselben Vault-Pfad.")
    # Some Semaphore versions export environment-secret stubs as AccessKeys.
    # The runtime credentials are installed separately with their correct owner.
    reader_names = {"vault_approle_role_id", "ANSIBLE_HASHI_VAULT_SECRET_ID", "ANSIBLE_HASHI_VAULT_ROLE_ID"}
    prepared["keys"] = [key for key in prepared.get("keys", [])
        if key.get("name", "").removeprefix("var.").removeprefix("env.") not in reader_names]
    # Freeze one canonical configuration. Old overrides must not redirect the runner.
    for group in prepared["environments"]:
        for field in ("json", "env"):
            values = json_object(group.get(field))
            group[field] = json.dumps({k: v for k, v in values.items() if k not in VAULT_PUBLIC_KEYS | {"VAULT_NAMESPACE", "ANSIBLE_HASHI_VAULT_NAMESPACE"}})
    group = next((g for g in prepared["environments"] if str(g.get("name", "")).casefold() == "vault-access"), None)
    if group is None:
        group = {"name": "Vault-Access", "json": "{}", "env": "{}"}
        prepared["environments"].append(group)
    values = json_object(group.get("json"))
    values.update(vault_url=config["base_url"], vault_kv_mount=config["kv_mount"],
        vault_auth_mount=config["reader_auth_mount"], vault_tenant_secret_root=config["tenant_root"],
        vault_namespace=config["namespace"])
    # Pass both the explicit stack setting and the plugin's environment fallback.
    env = json_object(group.get("env"))
    env.pop("VAULT_NAMESPACE", None)
    env.pop("ANSIBLE_HASHI_VAULT_NAMESPACE", None)
    if config["namespace"]:
        env["VAULT_NAMESPACE"] = config["namespace"]
    group["json"], group["env"] = json.dumps(values), json.dumps(env)
    for task in prepared["templates"]:
        for field in task.get("survey_vars") or []:
            if field.get("name") in VAULT_PUBLIC_KEYS | {"VAULT_NAMESPACE", "ANSIBLE_HASHI_VAULT_NAMESPACE"}:
                raise ValueError("Vault-Konfiguration darf nicht über Task-Surveys überschrieben werden.")
        task["environments"] = [g for g in task.get("environments", []) if str(g).casefold() != "vault-access"] + [group["name"]]
    return {"catalog_revision": catalog.source_revision, "config_revision": config_revision(config),
        "kv_mount": config["kv_mount"], "objects": objects}


def make_payload(config: dict[str, Any], plan: dict[str, Any], inputs: dict[str, VaultFieldInput]) -> dict[str, Any]:
    expected = {f["input_id"] for o in plan["objects"] for f in o["fields"] if f["source"] == "input"}
    if set(inputs) != expected:
        raise ValueError("Secret-Eingaben müssen genau den Feldern des validierten Vault-Plans entsprechen.")
    objects = {}
    for obj in plan["objects"]:
        values = {}
        for field in obj["fields"]:
            if field["source"] == "registry":
                value = config["registry_passwords"][obj["id"]]
            else:
                choice = inputs[field["input_id"]]
                if choice.mode == "generate":
                    if not field["generate"]:
                        raise ValueError(f"{field['key']}: Generierung ist nicht freigegeben.")
                    size = max(32, field["min_length"])
                    size = min(size, field["max_length"])
                    if field.get("even_length") and size % 2:
                        size -= 1
                    value = secrets.token_hex((size + 1) // 2)[:size] if field["generate"] == "hex" else "".join(
                        secrets.choice("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_") for _ in range(size))
                else:
                    value = choice.value.get_secret_value() if choice.value else ""
            validate_value(field, value)
            values[field["key"]] = value
        objects[obj["path"]] = values
    return {"configuration": {key: value for key, value in config.items() if key != "registry_passwords"}, "objects": objects}


def payload_for(job: CreationJob) -> dict[str, Any]:
    if not job.encrypted_vault_payload:
        raise ValueError("Verschlüsselte Vault-Ausführungsdaten fehlen.")
    return json.loads(decrypt_secret(job.encrypted_vault_payload))


def execution_configuration(db: Session, job: CreationJob) -> dict[str, Any]:
    config = payload_for(job)["configuration"] if job.encrypted_vault_payload else configuration(db)
    if job.encrypted_vault_payload:
        current = configuration(db)
        connection_keys = ("base_url", "namespace", "kv_mount", "writer_auth_mount", "reader_auth_mount")
        if current and all(current.get(key) == config.get(key) for key in connection_keys):
            # Replacing an expired login must not change targets or KV contents.
            config.update({key: current[key] for key in SENSITIVE if current.get(key)})
    return config


def current_owned(metadata: dict[str, Any] | None, version: int, created_time: str | None = None) -> bool:
    if not metadata or metadata["current_version"] != version:
        return False
    detail = metadata.get("versions", {}).get(str(version))
    return (isinstance(detail, dict) and isinstance(detail.get("created_time"), str) and bool(detail["created_time"]) and not detail.get("destroyed")
        and not detail.get("deletion_time") and (created_time is None or detail["created_time"] == created_time))


async def provision(db: Session, job: CreationJob, inputs: dict[str, VaultFieldInput]) -> None:
    plan = job.vault_plan
    if not plan:
        raise ValueError("Der validierte Vault-Plan fehlt.")
    config = execution_configuration(db, job)
    if not job.encrypted_vault_payload and config_revision(config) != plan["config_revision"]:
        raise ValueError("Vault-Konfiguration wurde geändert. Entwurf vor der Anlage erneut validieren.")
    progress = copy.deepcopy(job.vault_progress or {"objects": {}})
    states = progress["objects"]
    if any(s["state"] in {"writing", "uncertain"} for s in states.values()):
        raise VaultError("Ein Vault-Schreibergebnis ist unklar. Das betroffene Objekt zuerst prüfen und ausdrücklich zuordnen.")
    client = VaultClient(config)
    await client.login()
    # Check every exact target before the first write. 403/5xx never mean absence.
    for obj in plan["objects"]:
        path = obj["path"]
        job.execution_started_at = utcnow()
        db.commit()
        metadata = await client.metadata(path)
        state = states.get(path)
        if state and state["state"] == "created":
            if not current_owned(metadata, state["version"], state["created_time"]):
                raise VaultError(f"Bereits angelegtes Vault-Objekt wurde verändert oder gelöscht: {path}")
        elif metadata is not None:
            raise VaultError(f"Vault-Objekt existiert bereits; keine Neuanlage: {path}", conflict=True)
    if not job.encrypted_vault_payload:
        values = make_payload(config, plan, inputs)
        job.encrypted_vault_payload = encrypt_secret(json.dumps(values))
        db.commit()  # Persist generated values before any external write.
    else:
        if inputs:
            raise ValueError("Wiederaufnahme verwendet gespeicherte Werte; neue Secret-Eingaben sind nicht zulässig.")
        values = payload_for(job)
        values["configuration"] = config
        job.encrypted_vault_payload = encrypt_secret(json.dumps(values))
        db.commit()
    for obj in plan["objects"]:
        path = obj["path"]
        if states.get(path, {}).get("state") == "created":
            continue
        states[path] = {"state": "writing"}
        job.vault_progress = copy.deepcopy(progress)
        job.execution_started_at = utcnow()
        db.commit()
        try:
            receipt = await client.create(path, values["objects"][path])
        except VaultError as exc:
            states[path] = {"state": "uncertain" if exc.uncertain else "pending"}
            job.vault_progress = copy.deepcopy(progress)
            db.commit()
            raise
        states[path] = {"state": "created", **receipt}
        job.vault_progress = copy.deepcopy(progress)
        db.commit()


async def install_reader_access(job: CreationJob, client: SemaphoreClient) -> None:
    config = payload_for(job)["configuration"]
    groups = await client.list_resources(job.semaphore_project_id, "environment")
    matches = [g for g in groups if str(g.get("name", "")).casefold() == "vault-access"]
    if len(matches) != 1:
        raise ValueError("Vault-Access fehlt oder ist im neuen Projekt nicht eindeutig.")
    group = await client.get_resource(job.semaphore_project_id, "environment", matches[0]["id"])
    existing = {(s["name"], s["type"]): s for s in group.get("secrets") or []}
    operations = []
    for name, kind, value in (("vault_approle_role_id", "var", config["reader_role_id"]),
            ("ANSIBLE_HASHI_VAULT_SECRET_ID", "env", config["reader_secret_id"])):
        secret = existing.get((name, kind))
        operations.append({"name": name, "type": kind, "secret": value,
            "operation": "update" if secret else "create", **({"id": secret["id"]} if secret else {})})
    await client.save_resource(job.semaphore_project_id, "environment", {
        "id": group["id"], "project_id": job.semaphore_project_id, "name": group["name"],
        "json": group.get("json") or "{}", "env": group.get("env") or "{}", "secrets": operations}, group["id"])
