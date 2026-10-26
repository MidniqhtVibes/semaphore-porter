"""Bounded declarative validation; repository Python and shell files are never executed."""
from __future__ import annotations

import argparse
import base64
import difflib
import hashlib
import json
import re
import tempfile
from pathlib import Path

import yaml

from app.catalog_export import export_catalog
from app.gitlab_client import MAX_FILES, MAX_FILE_BYTES, MAX_SNAPSHOT_BYTES, decode_file, safe_file_path
from app.package_contract import compile_plan


def encode(raw: str | bytes) -> str:
    return base64.b64encode(raw.encode() if isinstance(raw, str) else raw).decode()


def dump_yaml(value) -> str:
    return yaml.safe_dump(value, allow_unicode=True, sort_keys=False)


class ContractLoader(yaml.SafeLoader):
    def compose_node(self, parent, index):
        self.node_budget = getattr(self, "node_budget", 20000) - 1
        if self.node_budget < 0:
            raise ValueError("YAML-Struktur ist zu groß.")
        self.node_depth = getattr(self, "node_depth", 0) + 1
        try:
            if self.node_depth > 40:
                raise ValueError("YAML-Struktur ist zu tief verschachtelt.")
            return super().compose_node(parent, index)
        finally:
            self.node_depth -= 1

    def construct_mapping(self, node, deep=False):
        keys = set()
        for key_node, _ in node.value:
            key = self.construct_object(key_node, deep=deep)
            if not isinstance(key, (str, int, bool)) or key in keys:
                raise ValueError("YAML benötigt eindeutige skalare Schlüssel.")
            keys.add(key)
        return super().construct_mapping(node, deep=deep)


def read_yaml(content: str, *, mapping=True):
    try:
        value = yaml.load(decode_file(content).decode("utf-8-sig"), Loader=ContractLoader)
        # Reject cycles and alias expansion before any later traversal or compiler call.
        budget = [30000]

        def walk(item, parents):
            budget[0] -= 1
            if budget[0] < 0 or id(item) in parents:
                raise ValueError("Rekursive oder zu große YAML-Aliasstruktur.")
            if isinstance(item, (list, dict)):
                for child in item.values() if isinstance(item, dict) else item:
                    walk(child, parents | {id(item)})
        walk(value, set())
        if mapping and not isinstance(value, dict):
            raise ValueError("YAML-Wurzel muss ein Objekt sein.")
        return value
    except (yaml.YAMLError, UnicodeError, RecursionError) as exc:
        raise ValueError("Ungültiges oder zu komplexes YAML.") from exc


def check_files(files: dict[str, str]):
    if not isinstance(files, dict) or len(files) > MAX_FILES:
        raise ValueError("Maximal 400 Dateien pro Katalog.")
    size = 0
    for path, value in files.items():
        safe_file_path(path)
        size += len(decode_file(value))
        if size > MAX_SNAPSHOT_BYTES:
            raise ValueError("Katalog überschreitet 32 MB.")
        if path.endswith((".yml", ".yaml")):
            read_yaml(value, mapping=False)


def compose_safety(document, expected):
    services = document.get("services")
    if not isinstance(services, dict) or set(services) != set(expected):
        raise ValueError("Compose-Services stimmen nicht mit expected_services überein.")
    for service in services.values():
        if not isinstance(service, dict):
            raise ValueError("Ungültiger Compose-Service.")
        if (service.get("privileged") or service.get("network_mode") in {"host", "service:host"}
                or service.get("pid") or service.get("ipc") or service.get("devices")
                or service.get("cap_add") or service.get("build") or service.get("extends")
                or service.get("env_file") or service.get("volumes_from")):
            raise ValueError("Compose enthält nicht freigegebene Host-, Build- oder Privilegienoptionen.")
        image = service.get("image")
        if not isinstance(image, str) or not image:
            raise ValueError("Jeder Service benötigt ein vorhandenes Container-Image.")
        for volume in service.get("volumes", []):
            source = volume.split(":", 1)[0] if isinstance(volume, str) else volume.get("source", "")
            mount_type = volume.get("type") if isinstance(volume, dict) else None
            # Compiler materializes declared configuration next to compose.yml.
            declared_config = source.startswith("./") and "/" not in source[2:] and ".." not in source[2:]
            named = bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", source))
            if not (named or declared_config) or mount_type not in {None, "volume", "bind"}:
                raise ValueError("Compose-Volumes dürfen nur eigene Volumes oder deklarierte lokale Konfigurationen nutzen.")
        environment = service.get("environment", {})
        pairs = environment.items() if isinstance(environment, dict) else [str(v).split("=", 1) for v in environment]
        for pair in pairs:
            key, value = (list(pair) + [None])[:2]
            if re.search(r"PASSWORD|TOKEN|SECRET|SALT|PRIVATE_KEY", str(key), re.I) and value is not None:
                if not isinstance(value, str) or ("${" not in value and "{{" not in value):
                    raise ValueError("Compose darf nur Secret-Referenzen und keine festen Zugangswerte enthalten.")
    if any(key in document for key in ("include", "configs", "secrets")):
        raise ValueError("Externe Compose-Includes, Configs und Secrets gehören nicht zu diesem Paketformat.")


def validate_snapshot(files: dict[str, str], sha: str, only: str | None = None):
    check_files(files)
    programs = read_yaml(files["programs/catalog.yml"])
    applications = programs.get("programs")
    if programs.get("schema_version") != 1 or not isinstance(applications, dict) or not applications:
        raise ValueError("Ungültiger Programmkatalog.")
    if only and only not in applications:
        raise ValueError("Paket fehlt im Katalog.")
    checks = []
    with tempfile.TemporaryDirectory(prefix="semaporter-contract-") as directory:
        root = Path(directory)
        for path, content in files.items():
            if not path.startswith(("programs/", "database-types/", "mail/")):
                raise ValueError("Datei liegt außerhalb des deklarativen Katalogumfangs.")
            destination = root / path
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(decode_file(content))
        for app_id in ([only] if only else applications):
            if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,62}", app_id):
                raise ValueError("Ungültige Programm-ID.")
            manifest = read_yaml(files[f"programs/{app_id}/program.yml"])
            dataset_path = safe_file_path(f"programs/{app_id}/{manifest['datasets']['catalog']}")
            datasets = read_yaml(files[dataset_path])["datasets"]
            for kind, contract in manifest["database"]["types"].items():
                choices = (["none"] if manifest["datasets"]["optional"] else []) + [
                    ds_id for ds_id, ds in datasets.items() if ds["database_type"] == kind]
                if not choices:
                    raise ValueError("Provider hat keinen nutzbaren Datensatz und erlaubt keinen Lauf ohne Datensatz.")
                for policy in contract["allowed_policies"]:
                    for ds_id in choices:
                        if len(checks) >= 300:
                            raise ValueError("Mehr als 300 Kombinationen; Katalogumfang eingrenzen.")
                        plan = compile_plan(argparse.Namespace(root=directory, application_id=app_id,
                            database_type=kind, policy=policy, dataset_id=ds_id, max_dataset_bytes=MAX_FILE_BYTES))
                        mode = plan["database"]["mode"]
                        compose_path = Path(plan["compose"]["source"]).relative_to(root).as_posix()
                        compose_safety(read_yaml(files[compose_path]), manifest["application"]["expected_services"][mode])
                        checks.append({"application_id": app_id, "database_type": kind, "policy": policy,
                            "dataset_id": ds_id, "compatibility_id": plan["application"]["compatibility_id"]})
        catalog = export_catalog(root, sha)
        profiles = [app["profile"] for app in catalog["applications"].values()]
        if len(profiles) != len(set(profiles)):
            raise ValueError("Anwendungen benötigen unterschiedliche Vault-Profile.")
    return {"valid": True, "checks": checks, "source_hash": source_hash(files),
            "compiler": "stack-contract-v1-987765cd", "note": "Struktur- und Vertragsprüfung; SQL-/Laufzeittests erfolgen in der GitLab-CI."}, catalog


def source_hash(files):
    return hashlib.sha256(json.dumps(files, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def package_files(files, package_id):
    return {path: content for path, content in files.items()
            if path == "programs/catalog.yml" or path.startswith(f"programs/{package_id}/")}


def combined_files(draft):
    result = {path: content for path, content in draft.source_files.items() if path not in draft.original_files}
    result.update(draft.files)
    return result


def validate_edit(draft, files):
    if len(files) > 100 or any(path != "programs/catalog.yml" and not path.startswith(f"programs/{draft.package_id}/") for path in files):
        raise ValueError("Nur Programmkatalog und höchstens 99 eigene Paketdateien dürfen geändert werden.")
    check_files(files)
    before = read_yaml(draft.source_files["programs/catalog.yml"])
    after = read_yaml(files["programs/catalog.yml"])
    if ({k: v for k, v in before.items() if k != "programs"} != {k: v for k, v in after.items() if k != "programs"}
            or {k: v for k, v in before["programs"].items() if k != draft.package_id}
            != {k: v for k, v in after["programs"].items() if k != draft.package_id}):
        raise ValueError("Andere Programme oder globale Katalogeigenschaften dürfen nicht verändert werden.")
    if draft.package_id not in after["programs"]:
        raise ValueError("Das eigene Paket muss im Katalog bleiben.")
    return files


def diff_files(original, current):
    result = []
    for path in sorted(set(original) | set(current)):
        old, new = original.get(path), current.get(path)
        if old == new:
            continue
        text = None
        try:
            before, after = decode_file(old).decode() if old else "", decode_file(new).decode() if new else ""
            if "\0" not in before + after:
                text = "".join(difflib.unified_diff(before.splitlines(True), after.splitlines(True), fromfile="a/" + path, tofile="b/" + path))[:100000]
        except UnicodeError:
            pass
        result.append({"path": path, "action": "create" if old is None else "delete" if new is None else "update",
            "diff": text, "sha256": hashlib.sha256(decode_file(new)).hexdigest() if new else None})
    return result


def generate_package(files, payload):
    result = dict(files)
    prefix = f"programs/{payload.package_id}/"
    catalog = read_yaml(files["programs/catalog.yml"])
    if payload.package_id in catalog["programs"]:
        if payload.source_id != payload.package_id:
            raise ValueError("Programm-ID ist bereits vorhanden. Zum Bearbeiten das bestehende Paket öffnen.")
        return package_files(result, payload.package_id)
    if any(path.startswith(prefix) for path in files):
        raise ValueError("Paketordner ist bereits vorhanden.")
    if payload.source_id:
        if payload.source_id not in catalog["programs"]:
            raise ValueError("Quellpaket fehlt im Katalog.")
        source_prefix = f"programs/{payload.source_id}/"
        for path, content in files.items():
            if path.startswith(source_prefix):
                result[prefix + path[len(source_prefix):]] = content
        manifest = read_yaml(files[source_prefix + "program.yml"])
        old_prefix, new_prefix = payload.source_id.replace("-", "_"), payload.package_id.replace("-", "_")
        for image in manifest["release"]["images"].values():
            image["repository_key"] = image["repository_key"].replace(old_prefix, new_prefix)
        registry = manifest["release"].get("registry")
        if registry:
            for key in ("prefix_variable", "username_variable"):
                if registry.get(key):
                    registry[key] = registry[key].replace(old_prefix, new_prefix)
        manifest.update(id=payload.package_id, display_name=payload.name)
        manifest["secrets"]["vault_profile"] = payload.package_id
        manifest["release"]["default"] = payload.release
        if payload.image_repository:
            primary = manifest["release"]["images"][manifest["release"]["primary_image"]]
            manifest["runtime"]["input_environment"][primary["repository_environment"]] = {
                "variable": primary["repository_key"], "default": payload.image_repository}
    else:
        if not payload.image_repository or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_./:-]*", payload.image_repository):
            raise ValueError("Für eine neue HTTP-Anwendung ohne Datenbank ein gültiges Image-Repository angeben.")
        variable = payload.package_id.replace("-", "_") + "_image_repository"
        manifest = {"schema_version": 1, "id": payload.package_id, "display_name": payload.name, "profile_version": 1,
            "release": {"default": payload.release, "primary_image": "application", "images": {"application": {
                "repository_key": variable, "tag_input": "application_release_id", "repository_environment": "APP_IMAGE", "tag_environment": "APP_TAG"}}},
            "database": {"default_type": "none", "types": {"none": {"provider_id": "none-v1", "allowed_policies": ["always_new"],
                "compose": {"none": "files/compose/no-database.yml"}, "configuration_files": [], "connection_mapping": {}}}},
            "application": {"primary_service": "application", "expected_services": {"none": ["application"]}},
            "endpoint": {"scheme": "http", "service": "application", "container_port": payload.container_port,
                "bind_address_environment": "APP_BIND_ADDRESS", "host_port_environment": "APP_HOST_PORT"},
            "runtime": {"lifecycle_environment": {"application_id": "APPLICATION_ID", "tenant_slug": "TENANT_SLUG",
                "runtime_scope_id": "RUNTIME_SCOPE_ID", "dataset_id": "DATASET_ID", "base_url": "BASE_URL"},
                "input_environment": {"APP_IMAGE": {"variable": variable, "default": payload.image_repository}}},
            "datasets": {"catalog": "testdata/catalog.yml", "optional": True},
            "readiness": [{"type": "published_tcp", "endpoint": "primary"}, {"type": "compose_services"},
                {"type": "http", "endpoint": "primary", "path": "/", "accepted_statuses": [200]}],
            "secrets": {"vault_profile": payload.package_id, "required": {}}}
        labels = {"semaphore.ttl.managed": "true", "semaphore.ttl.project": "${COMPOSE_PROJECT_NAME}",
            "semaphore.application": "${APPLICATION_ID}", "semaphore.tenant": "${TENANT_SLUG}",
            "semaphore.runtime.scope": "${RUNTIME_SCOPE_ID:?RUNTIME_SCOPE_ID fehlt}", "semaphore.dataset": "${DATASET_ID}"}
        compose = {"services": {"application": {"image": "${APP_IMAGE:?APP_IMAGE fehlt}:${APP_TAG:?APP_TAG fehlt}",
            "restart": "no", "ports": [f"${{APP_BIND_ADDRESS:-0.0.0.0}}:${{APP_HOST_PORT:?APP_HOST_PORT fehlt}}:{payload.container_port}"],
            "security_opt": ["no-new-privileges:true"], "mem_limit": "512m", "cpus": "1.0", "pids_limit": 256, "labels": labels}},
            "networks": {"default": {"labels": labels}}}
        result[prefix + "files/compose/no-database.yml"] = encode(dump_yaml(compose))
        result[prefix + "testdata/catalog.yml"] = encode(dump_yaml({"schema_version": 1, "datasets": {}}))
    result[prefix + "program.yml"] = encode(dump_yaml(manifest))
    catalog["programs"][payload.package_id] = {"display_name": payload.name}
    result["programs/catalog.yml"] = encode(dump_yaml(catalog))
    return package_files(result, payload.package_id)
