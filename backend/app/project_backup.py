from __future__ import annotations

import copy
import re
from typing import Any


TENANT_SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{1,30}$")


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

    chosen_templates = set(draft.get("task_template_names") or [])
    templates = [item for item in result.get("templates", []) if isinstance(item, dict)]
    if chosen_templates:
        templates = [item for item in templates if item.get("name") in chosen_templates]
    if not templates:
        raise BackupValidationError("Mindestens ein Task Template muss ausgewählt sein.")
    result["templates"] = templates

    chosen_groups = set(draft.get("environment_names") or [])
    environments = [item for item in result.get("environments", []) if isinstance(item, dict)]
    if chosen_groups:
        environments = [item for item in environments if item.get("name") in chosen_groups]

    tenant_group_name = f"Tenant-{tenant_slug}"
    used_names = {str(item.get("name", "")).lower() for item in environments}
    suffix = 2
    base = tenant_group_name
    while tenant_group_name.lower() in used_names:
        tenant_group_name = f"{base}-{suffix}"
        suffix += 1
    tenant_values: dict[str, Any] = {}
    for preset in draft.get("preset_values") or []:
        if isinstance(preset, dict) and isinstance(preset.get("values"), dict):
            tenant_values.update(preset["values"])
    # Mandantenspezifische Werte gewinnen bei Konflikten immer gegen Presets.
    tenant_values["tenant_slug"] = tenant_slug
    for key in ("application_id", "database_type", "dataset_id", "ttl_minutes"):
        if key in draft and draft[key] not in (None, ""):
            tenant_values[key] = draft[key]
    environments.append({"name": tenant_group_name, "json": _compact_json(tenant_values), "env": "{}"})
    result["environments"] = environments

    group_names = {item.get("name") for item in environments}
    for template in templates:
        if isinstance(template.get("environments"), list):
            template["environments"] = [name for name in template["environments"] if name in group_names]
            if tenant_group_name not in template["environments"]:
                template["environments"].append(tenant_group_name)
        else:
            template["environment"] = tenant_group_name
        surveys = template.setdefault("survey_vars", [])
        if not isinstance(surveys, list):
            surveys = []
            template["survey_vars"] = surveys
        by_name = {item.get("name"): item for item in surveys if isinstance(item, dict)}
        for key, value in tenant_values.items():
            if key in by_name:
                by_name[key]["default_value"] = value
        if "tenant_slug" not in by_name:
            surveys.append(
                {
                    "name": "tenant_slug",
                    "title": "Tenant-ID",
                    "description": "Technische Mandantenkennung",
                    "type": "",
                    "required": True,
                    "default_value": tenant_slug,
                    "values": [],
                }
            )

    repositories = [item for item in result.get("repositories", []) if isinstance(item, dict)]
    if repositories:
        if draft.get("repository_url"):
            repositories[0]["git_url"] = str(draft["repository_url"]).strip()
        if draft.get("repository_branch"):
            repositories[0]["git_branch"] = str(draft["repository_branch"]).strip()

    # Sichere Defaults: neue Kopien übernehmen keine automatischen Auslöser.
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
    for task in document.get("templates", []):
        if not isinstance(task, dict):
            continue
        task_name = task.get("name", "?")
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
