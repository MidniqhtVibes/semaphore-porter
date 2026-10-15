from __future__ import annotations

import copy
import json
import re
from typing import Any


TENANT_SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{1,30}$")
TENANT_VARIABLES = {"tenant_slug", "runtime_scope_id"}
PRIVATE_VARIABLE = re.compile(r"password|passwd|passwort|token|secret|private.?key|credential|role.?id|api.?key|access.?key", re.I)
PUBLIC_VAULT_CONFIG = {"vault_tenant_secret_root", "vault_provider_secret_paths", "vault_program_secret_paths", "vault_tenant_secret_paths", "secret_storage_id", "secret_storage_key_prefix"}


def is_secret_name(name: str) -> bool:
    return name.lower() not in PUBLIC_VAULT_CONFIG and bool(PRIVATE_VARIABLE.search(name))


def public_variables(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: public_variables(item) for key, item in value.items() if not is_secret_name(str(key))}
    if isinstance(value, list):
        return [public_variables(item) for item in value]
    return value


def preserve_private(old: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(incoming)
    for key, value in old.items():
        if is_secret_name(str(key)):
            result[key] = value
        elif isinstance(value, dict):
            nested = preserve_private(value, result.get(key) if isinstance(result.get(key), dict) else {})
            if nested:
                result[key] = nested
        elif isinstance(value, list) and public_variables(value) != value:
            # Lists have no stable key for merging hidden values. Preserve them atomically.
            result[key] = value
    return result


def is_defaults(name: str) -> bool:
    return name.casefold() in {"semaphore-default", "semaphore-defaults"}


def json_object(value: Any) -> dict[str, Any]:
    if value in (None, ""):
        return {}
    try:
        result = json.loads(value) if isinstance(value, str) else copy.deepcopy(value)
    except (ValueError, TypeError) as exc:
        raise BackupValidationError("Variablengruppe enthält ungültiges JSON.") from exc
    if not isinstance(result, dict):
        raise BackupValidationError("Variablen müssen ein JSON-Objekt sein.")
    return result


def validate_tenant_values(values: dict[str, Any]) -> None:
    for name in TENANT_VARIABLES:
        value = values.get(name)
        if not isinstance(value, str) or not TENANT_SLUG.fullmatch(value) or value.endswith("-"):
            raise BackupValidationError(f"{name}: 2–31 Kleinbuchstaben/Ziffern/Bindestriche erforderlich.")


class BackupValidationError(ValueError):
    pass


def parse_backup(document: Any) -> dict[str, Any]:
    if not isinstance(document, dict):
        raise BackupValidationError("Das Projektbackup muss ein JSON-Objekt sein.")
    meta = document.get("meta")
    if not isinstance(meta, dict) or not str(meta.get("name", "")).strip():
        raise BackupValidationError("Keine Semaphore-Backupdatei: meta.name fehlt.")
    return copy.deepcopy(document)


def survey_catalog(document: dict[str, Any]) -> dict[str, list[Any]]:
    catalog: dict[str, list[Any]] = {}
    for template in document.get("templates", []):
        if not isinstance(template, dict):
            continue
        for survey in template.get("survey_vars") or []:
            if not isinstance(survey, dict) or not survey.get("name"):
                continue
            values = survey.get("values") or []
            options = [item.get("value") for item in values if isinstance(item, dict) and "value" in item]
            if options:
                catalog.setdefault(str(survey["name"]), [])
                for option in options:
                    if option not in catalog[str(survey["name"])]:
                        catalog[str(survey["name"])].append(option)
    return catalog


def prepare_backup(source: dict[str, Any], draft: dict[str, Any]) -> dict[str, Any]:
    result = parse_backup(source)
    project_name = str(draft.get("project_name", "")).strip()
    tenant_slug = str(draft.get("tenant_slug", "")).strip()
    if not project_name:
        raise BackupValidationError("Projektname fehlt.")
    if not TENANT_SLUG.fullmatch(tenant_slug) or tenant_slug.endswith("-"):
        raise BackupValidationError("tenant_slug muss 2–31 Kleinbuchstaben/Ziffern/Bindestriche enthalten.")
    result["meta"]["name"] = project_name
    scope = str(draft.get("runtime_scope_id", "")).strip()
    validate_tenant_values({"tenant_slug": tenant_slug, "runtime_scope_id": scope})

    # Editable copies are resource data, never a replacement for the source backup.
    for section in ("environments", "repositories", "inventories", "templates"):
        if section in (draft.get("resource_overrides") or {}):
            items = draft["resource_overrides"][section]
            if not isinstance(items, list) or any(not isinstance(item, dict) for item in items):
                raise BackupValidationError(f"{section} muss eine Liste von Objekten sein.")
            result[section] = copy.deepcopy(items)

    chosen_templates = set(draft.get("task_template_names") or [])
    templates = [item for item in result.get("templates", []) if isinstance(item, dict)]
    if "task_template_names" in draft:
        templates = [item for item in templates if item.get("name") in chosen_templates]
    if not templates:
        raise BackupValidationError("Mindestens ein Task Template muss ausgewählt sein.")
    result["templates"] = templates

    chosen_groups = set(draft.get("environment_names") or [])
    environments = [item for item in result.get("environments", []) if isinstance(item, dict)]
    if "environment_names" in draft:
        environments = [item for item in environments if item.get("name") in chosen_groups]

    defaults = [item for item in environments if is_defaults(str(item.get("name", "")))]
    if len(defaults) > 1:
        raise BackupValidationError("Nur eine Semaphore-Defaults-Gruppe ist zulässig.")
    default_group = defaults[0] if defaults else {"name": "Semaphore-Defaults", "json": "{}", "env": "{}"}
    tenant_group_name = str(default_group["name"])
    tenant_values = json_object(default_group.get("json"))
    # Remove copied identities from every other group and the process environment.
    for group in environments:
        group.pop("password", None)
        group.pop("secrets", None)
        for field in ("json", "env"):
            values = json_object(group.get(field))
            values = public_variables({key: value for key, value in values.items() if key not in TENANT_VARIABLES})
            group[field] = _compact_json(values)
    tenant_values = public_variables(tenant_values)
    for preset in draft.get("preset_values") or []:
        if isinstance(preset, dict) and isinstance(preset.get("values"), dict):
            tenant_values.update(preset["values"])
    # Mandantenspezifische Werte gewinnen bei Konflikten immer gegen Presets.
    tenant_values["tenant_slug"] = tenant_slug
    tenant_values["runtime_scope_id"] = scope
    for key in ("application_id", "database_type", "dataset_id", "ttl_minutes"):
        if key in draft and draft[key] not in (None, ""):
            tenant_values[key] = draft[key]
    default_group["json"] = _compact_json(tenant_values)
    if not defaults:
        environments.append(default_group)
    result["environments"] = environments

    group_names = {item.get("name") for item in environments}
    for template in templates:
        template["autorun"] = False
        if "cron" in template:
            template["cron"] = ""
        if isinstance(template.get("environments"), list):
            template["environments"] = [name for name in template["environments"] if name in group_names]
            if tenant_group_name not in template["environments"]:
                template["environments"].append(tenant_group_name)
        else:
            previous = template.get("environment")
            template["environments"] = ([previous] if previous in group_names and previous != tenant_group_name else []) + [tenant_group_name]
            template["environment"] = tenant_group_name
        surveys = template.setdefault("survey_vars", [])
        if not isinstance(surveys, list):
            surveys = []
            template["survey_vars"] = surveys
        surveys = [item for item in surveys if isinstance(item, dict) and item.get("name") not in TENANT_VARIABLES]
        template["survey_vars"] = surveys
        by_name = {item.get("name"): item for item in surveys}
        for key, value in tenant_values.items():
            if key in by_name:
                by_name[key]["default_value"] = value if isinstance(value, (str, list)) else json.dumps(value)

    repositories = [item for item in result.get("repositories", []) if isinstance(item, dict)]
    if repositories:
        if draft.get("repository_url"):
            repositories[0]["git_url"] = str(draft["repository_url"]).strip()
        if draft.get("repository_branch"):
            repositories[0]["git_branch"] = str(draft["repository_branch"]).strip()

    # Sichere Defaults: neue Kopien übernehmen keine automatischen Auslöser.
    result["keys"] = [{"name": key.get("name"), "type": key.get("type", "none")} for key in result.get("keys", []) if isinstance(key, dict)]
    result["schedules"] = []
    result["integrations"] = []
    result["integration_aliases"] = []
    return result


def validate_backup(document: dict[str, Any]) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    try:
        parse_backup(document)
    except BackupValidationError as exc:
        return [str(exc)], []

    sections = ("templates", "environments", "repositories", "inventories", "keys")
    names: dict[str, set[str]] = {}
    for section in sections:
        values = document.get(section, [])
        if not isinstance(values, list):
            errors.append(f"{section} muss eine Liste sein.")
            names[section] = set()
            continue
        seen: set[str] = set()
        for item in values:
            name = str(item.get("name", "")).strip() if isinstance(item, dict) else ""
            if not name:
                errors.append(f"{section}: Eintrag ohne Namen.")
            elif name.lower() in seen:
                errors.append(f"{section}: '{name}' ist doppelt.")
            else:
                seen.add(name.lower())
        names[section] = seen

    repos = names.get("repositories", set())
    inventories = names.get("inventories", set())
    envs = names.get("environments", set())
    keys = names.get("keys", set())
    for section, fields in (("repositories", ("ssh_key",)), ("inventories", ("ssh_key", "become_key"))):
        for item in document.get(section, []) if isinstance(document.get(section, []), list) else []:
            if not isinstance(item, dict):
                continue
            for field in fields:
                ref = item.get(field)
                if ref and str(ref).casefold() not in keys:
                    errors.append(f"{section} {item.get('name', '?')}: Key '{ref}' fehlt.")
    defaults = [group for group in document.get("environments", []) if isinstance(group, dict) and is_defaults(str(group.get("name", "")))] if isinstance(document.get("environments", []), list) else []
    if len(defaults) != 1:
        errors.append("Genau eine Semaphore-Defaults-Gruppe ist erforderlich.")
    else:
        try:
            validate_tenant_values(json_object(defaults[0].get("json")))
        except BackupValidationError as exc:
            errors.append(str(exc))
    for task in document.get("templates", []):
        if not isinstance(task, dict):
            continue
        task_name = task.get("name", "?")
        if any(isinstance(field, dict) and field.get("name") in TENANT_VARIABLES for field in task.get("survey_vars") or []):
            errors.append(f"Task {task_name}: Tenant/Scope dürfen nicht in der Survey stehen.")
        if str(task.get("repository", "")).lower() not in repos:
            errors.append(f"Task {task_name}: Repository fehlt.")
        if str(task.get("inventory", "")).lower() not in inventories:
            errors.append(f"Task {task_name}: Inventory fehlt.")
        refs = task.get("environments") if isinstance(task.get("environments"), list) else [task.get("environment")]
        for ref in refs:
            if ref and str(ref).lower() not in envs:
                errors.append(f"Task {task_name}: Variablengruppe '{ref}' fehlt.")

    for key in document.get("keys", []):
        if isinstance(key, dict) and key.get("type") not in {None, "none"}:
            warnings.append(f"Key '{key.get('name', '?')}': geheime Inhalte nach dem Restore prüfen.")
    if document.get("schedules"):
        warnings.append("Zeitpläne sind enthalten und müssen geprüft werden.")
    if document.get("integrations"):
        warnings.append("Integrationen/Webhooks sind enthalten und müssen geprüft werden.")
    return errors, warnings


def _compact_json(value: dict[str, Any]) -> str:
    import json

    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
