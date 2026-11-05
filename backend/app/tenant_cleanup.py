"""Delete only recorded tenant-owned resources; never stop host workloads."""
from __future__ import annotations

import copy
import json
import uuid
from datetime import timezone

from sqlalchemy import delete, select

from app import credential_service, registry_service, vault_service
from app.models import (AuditEvent, CreationJob, CredentialProfile, CredentialUse, DeploymentSource,
    RegistryProfile, SemaphoreSettings, TaskPermission, TaskPolicy, TaskRun, TaskTemplate,
    Tenant, TenantDeletion, TenantMembership, TenantStatus, VariableRule, CreationStatus, utcnow)
from app.security import stable_digest
from app.project_backup import is_defaults, json_object
from app.semaphore_client import SemaphoreError
from app.services import semaphore_client_from_db
from app.vault_client import VaultClient, VaultError, safe_path

TERMINAL = {"success", "successful", "completed", "error", "failed", "failure", "stopped", "canceled", "cancelled"}


def digest(value):
    return stable_digest(json.dumps(value, sort_keys=True, default=str)).hex()


def vault_identity(config):
    return {name: config.get(name, "") for name in ("base_url", "namespace", "kv_mount")}


def original_vault_identity(job):
    if job.vault_plan.get("connection"):
        return job.vault_plan["connection"]
    # Older creation jobs retain the public Vault connection in their prepared
    # Semaphore-Defaults even after the encrypted execution payload is erased.
    for group in (job.prepared_backup or {}).get("environments", []):
        if is_defaults(str(group.get("name", ""))):
            values = json_object(group.get("json"))
            if values.get("vault_url") and values.get("vault_kv_mount"):
                return {"base_url": values["vault_url"], "kv_mount": values["vault_kv_mount"], "namespace": values.get("vault_namespace", "")}
    raise ValueError("Der ursprüngliche Vault-Verbindungsbeleg fehlt. Die Vault-Zuordnung muss vor einer automatischen Löschung geklärt werden.")


def shared_reference(db, identity, path):
    for config, model in ((credential_service.configuration(db), CredentialProfile), (registry_service.connection(db), RegistryProfile)):
        if vault_identity(config) != identity:
            continue
        for profile in db.scalars(select(model).where(model.vault_path == path)):
            return profile.name
    return None


def owned_metadata(metadata, receipt):
    if metadata is None:
        return True
    if receipt.get("version") != 1 or not receipt.get("created_time"):
        return False
    created = metadata.get("created_time") or (metadata.get("versions", {}).get("1") or {}).get("created_time")
    return created == receipt["created_time"]


def deployment_blockers(db, slugs):
    blockers = []
    for source in db.scalars(select(DeploymentSource)):
        snapshot = source.snapshot or {}
        for item in snapshot.get("deployments", []):
            if item.get("tenant_slug") not in slugs:
                continue
            temporary = item.get("expires_at") is not None
            # Expiry alone does not prove that cleanup has actually completed.
            if temporary or item.get("running_count") is None or item.get("running_count", 0) > 0:
                kind = "Temporäres Deployment regulär auslaufen lassen" if temporary else "Dauerhaftes Deployment zuerst bewusst beenden"
                blockers.append(f"{source.name} / {item.get('deployment_id', '?')}: {kind} und die nächste vollständige Hostmeldung abwarten.")
    return blockers


def public_state(row):
    started = row.execution_started_at
    if started and started.tzinfo is None:
        started = started.replace(tzinfo=timezone.utc)
    return {"plan": row.plan, "progress": row.progress or {}, "revision": row.revision,
            "last_error": row.last_error, "running": bool(started and (utcnow() - started).total_seconds() < 900)}


def vault_key(item):
    return digest(item["identity"]) + ":" + item["path"]


def creation_blockers(jobs):
    return ["Tenant-Erstellung zuerst vollständig abschließen oder ihren unklaren Zustand auflösen."
            for job in jobs if job.execution_started_at or job.status != CreationStatus.COMPLETED]


def destructive_progress(row):
    progress = row.progress or {}
    return bool(progress.get("project") or progress.get("vault"))


async def prepare(db, tenant):
    existing = db.get(TenantDeletion, tenant.id)
    if existing and (existing.execution_started_at or destructive_progress(existing)):
        return public_state(existing)
    jobs = list(db.scalars(select(CreationJob).where(CreationJob.tenant_id == tenant.id)))
    project = tenant.semaphore_project
    settings = db.get(SemaphoreSettings, 1)
    slugs = {tenant.tenant_slug, *(job.draft_data.get("tenant_slug") for job in jobs)} - {None}
    plan = {"tenant_id": str(tenant.id), "tenant_slug": tenant.tenant_slug, "name": tenant.display_name,
            "job_ids": [str(job.id) for job in jobs], "slugs": sorted(slugs), "vault": [],
            "semaphore": None, "blockers": creation_blockers(jobs),
            "preserved": ["Gemeinsame Benutzer und Gruppen", "Zentrale SSH- und Registry-Profile", "GitLab-Quellprojekte und Images"]}
    if project:
        owned = any(job.semaphore_project_id == project.semaphore_project_id for job in jobs)
        plan["semaphore"] = {"id": project.semaphore_project_id, "name": project.name, "owned": owned,
                             "base_url": settings.base_url.rstrip("/") if settings else ""}
        if not owned:
            plan["preserved"].append("Extern zugeordnetes Semaphore-Projekt ohne Semaporter-Anlagebeleg")
        for job in jobs:
            origins = [item.get("semaphore_url") for item in job.credential_plan or []]
            origins.append((job.semaphore_response or {}).get("_semaporter_base_url"))
            if any(origin and origin != plan["semaphore"]["base_url"] for origin in origins):
                plan["blockers"].append("Semaphore-Verbindung entspricht nicht dem ursprünglichen Anlageziel.")
    if any(job.semaphore_project_id and (not project or job.semaphore_project_id != project.semaphore_project_id) for job in jobs):
        plan["blockers"].append("Anlagebelege verweisen auf weitere Semaphore-Projekte. Zuordnung zuerst manuell klären.")
    seen = set()
    for job in jobs:
        if not job.vault_plan:
            continue
        config = vault_service.execution_configuration(db, job)
        identity = vault_identity(config)
        if identity != original_vault_identity(job):
            raise ValueError("Vault-Verbindung stimmt nicht mit dem ursprünglichen Anlageziel überein.")
        client = VaultClient(config)
        await client.login()
        root = safe_path(f"{config['tenant_root']}/{job.draft_data['tenant_slug']}") + "/"
        for obj in job.vault_plan.get("objects", []):
            path = safe_path(obj["path"])
            receipt = (job.vault_progress or {}).get("objects", {}).get(path, {})
            if receipt.get("state") in {"writing", "uncertain"}:
                plan["blockers"].append(f"Unklares Vault-Schreibergebnis zuerst im Erstellungsvorgang auflösen: {path}")
                continue
            if receipt.get("state") != "created":
                continue
            key = (*identity.values(), path)
            if not path.startswith(root) or key in seen:
                raise ValueError("Vault-Anlagebelege sind nicht eindeutig auf diesen Tenant begrenzt.")
            seen.add(key)
            shared = shared_reference(db, identity, path)
            if shared:
                plan["blockers"].append(f"Vault-Pfad wird vom gemeinsamen Profil „{shared}“ referenziert: {path}")
            metadata = await client.metadata(path)
            if not owned_metadata(metadata, receipt):
                plan["blockers"].append(f"Vault-Objekt passt nicht mehr zum ursprünglichen Anlagebeleg: {path}")
            plan["vault"].append({"job_id": str(job.id), "path": path, "identity": identity,
                "receipt": {name: receipt.get(name) for name in ("version", "created_time")},
                "metadata_digest": digest(metadata), "versions": metadata.get("current_version", 0) if metadata else 0})
    task_ids = list(db.scalars(select(TaskTemplate.id).where(TaskTemplate.tenant_id == tenant.id)))
    plan["portal"] = {"tasks": len(task_ids), "runs": len(list(db.scalars(select(TaskRun.id).where(TaskRun.tenant_id == tenant.id)))),
                      "memberships": len(list(db.scalars(select(TenantMembership.id).where(TenantMembership.tenant_id == tenant.id))))}
    row = existing or TenantDeletion(tenant_id=tenant.id)
    row.plan, row.revision, row.progress, row.last_error = plan, digest(plan), {}, None
    db.add(row)
    db.commit()
    result = public_state(row)
    result["deployment_blockers"] = deployment_blockers(db, slugs)
    return result


async def preflight(db, tenant, row):
    plan, progress = row.plan, row.progress or {}
    jobs = list(db.scalars(select(CreationJob).where(CreationJob.tenant_id == tenant.id)))
    if {str(job.id) for job in jobs} != set(plan["job_ids"]):
        raise ValueError("Anlagebelege wurden seit der Vorschau geändert. Neue Löschvorschau erstellen.")
    blockers = plan.get("blockers", []) + creation_blockers(jobs) + deployment_blockers(db, set(plan["slugs"]))
    if blockers:
        raise ValueError(" ".join(blockers))
    project = plan.get("semaphore")
    if project and project["owned"]:
        settings = db.get(SemaphoreSettings, 1)
        if not settings or settings.base_url.rstrip("/") != project["base_url"]:
            raise ValueError("Semaphore-Verbindung wurde geändert. Löschziel zuerst prüfen.")
        if not tenant.semaphore_project or tenant.semaphore_project.semaphore_project_id != project["id"]:
            raise ValueError("Semaphore-Projektzuordnung wurde geändert.")
        client = semaphore_client_from_db(db)
        try:
            remote = await client.get_project(project["id"])
        except SemaphoreError as exc:
            if exc.status_code != 404:
                raise
            remote = None
        if remote is not None:
            if progress.get("project") == "deleted":
                raise ValueError("Ein bereits entferntes Semaphore-Projekt ist wieder vorhanden. Ziel manuell prüfen.")
            if remote.get("name") != project["name"]:
                raise ValueError("Semaphore-Projekt wurde umbenannt. Ziel vor der Löschung prüfen.")
            tasks = await client.list_project_tasks(project["id"])
            if any(str(task.get("status", "")).lower() not in TERMINAL for task in tasks):
                raise ValueError("In Semaphore laufen oder warten noch Tasks. Diese zuerst regulär abschließen lassen.")
    elif tenant.semaphore_project:
        # Imported projects survive deletion. Check their portal runs individually.
        from app.models import TaskRunStatus
        for run in db.scalars(select(TaskRun).where(TaskRun.tenant_id == tenant.id,
                TaskRun.status.in_([TaskRunStatus.QUEUED, TaskRunStatus.RUNNING, TaskRunStatus.UNKNOWN]))):
            remote = await semaphore_client_from_db(db).get_task(tenant.semaphore_project.semaphore_project_id, run.semaphore_task_id)
            if str(remote.get("status", "")).lower() not in TERMINAL:
                raise ValueError("Für diesen Tenant laufen oder warten noch Tasks.")
    clients = {}
    for item in plan["vault"]:
        row.execution_started_at = utcnow()
        db.commit()
        job = db.get(CreationJob, uuid.UUID(item["job_id"]))
        if job is None or job.tenant_id != tenant.id:
            raise ValueError("Vault-Anlagebeleg fehlt oder gehört nicht zum Tenant.")
        config = vault_service.execution_configuration(db, job)
        if vault_identity(config) != item["identity"]:
            raise ValueError("Vault-Ziel wurde geändert. Löschziel zuerst prüfen.")
        shared = shared_reference(db, item["identity"], item["path"])
        if shared:
            raise ValueError(f"Vault-Objekt wird vom gemeinsamen Profil „{shared}“ verwendet.")
        key = digest(item["identity"])
        if key not in clients:
            client = VaultClient(config)
            await client.login()
            clients[key] = client
        client = clients[key]
        metadata = await client.metadata(item["path"])
        state = progress.get("vault", {}).get(vault_key(item))
        if metadata is not None and state == "deleted":
            raise ValueError("Ein bereits entferntes Vault-Objekt wurde neu angelegt. Keine erneute automatische Löschung.")
        if metadata is not None and (not owned_metadata(metadata, item["receipt"]) or digest(metadata) != item["metadata_digest"]):
            raise ValueError("Vault-Objekt wurde seit der Löschvorschau verändert. Vor dem ersten Löschen eine neue Vorschau erstellen.")
    for key, client in clients.items():
        await client.require_delete_access([item["path"] for item in plan["vault"]
            if digest(item["identity"]) == key and progress.get("vault", {}).get(vault_key(item)) != "deleted"])
    return clients


def remove_local(db, tenant, row):
    tenant_id, plan = tenant.id, row.plan
    task_ids = list(db.scalars(select(TaskTemplate.id).where(TaskTemplate.tenant_id == tenant_id)))
    run_ids = list(db.scalars(select(TaskRun.id).where(TaskRun.tenant_id == tenant_id)))
    policy_ids = list(db.scalars(select(TaskPolicy.id).where(TaskPolicy.task_template_id.in_(task_ids))))
    jobs = list(db.scalars(select(CreationJob).where(CreationJob.tenant_id == tenant_id)))
    job_ids = [job.id for job in jobs]
    uses = list(db.scalars(select(CredentialUse).where(CredentialUse.creation_job_id.in_(job_ids))))
    ids = {str(value) for value in [tenant_id, *task_ids, *run_ids, *policy_ids, *job_ids, *(use.id for use in uses)]}
    def mentions(value):
        if isinstance(value, str):
            return value in ids
        if isinstance(value, dict):
            return any(mentions(item) for item in value.values())
        if isinstance(value, list):
            return any(mentions(item) for item in value)
        return False
    project = plan.get("semaphore")
    for event in list(db.scalars(select(AuditEvent))):
        project_event = project and event.target_id == str(project["id"]) and (event.target_type == "semaphore_project"
            or (event.target_type is None and event.event_type.startswith("semaphore_")))
        if event.target_id in ids or mentions(event.details) or project_event:
            db.delete(event)
    for source in db.scalars(select(DeploymentSource)):
        snapshot = source.snapshot
        if snapshot and any(item.get("tenant_slug") in plan["slugs"] for item in snapshot.get("deployments", [])):
            value = copy.deepcopy(snapshot)
            value["deployments"] = [item for item in value["deployments"] if item.get("tenant_slug") not in plan["slugs"]]
            source.snapshot = value
    # Delete RESTRICT dependents explicitly; global accounts/profiles stay intact.
    for model, condition in (
        (TaskRun, TaskRun.tenant_id == tenant_id),
        (TaskPermission, TaskPermission.task_template_id.in_(task_ids)),
        (VariableRule, VariableRule.policy_id.in_(policy_ids)),
        (TaskPolicy, TaskPolicy.task_template_id.in_(task_ids)),
        (TaskTemplate, TaskTemplate.tenant_id == tenant_id),
        (TenantMembership, TenantMembership.tenant_id == tenant_id),
        (CredentialUse, CredentialUse.creation_job_id.in_(job_ids)),
        (CreationJob, CreationJob.tenant_id == tenant_id),
    ):
        db.execute(delete(model).where(condition).execution_options(synchronize_session=False))
    from app.models import SemaphoreProject
    db.execute(delete(SemaphoreProject).where(SemaphoreProject.tenant_id == tenant_id))
    db.execute(delete(TenantDeletion).where(TenantDeletion.tenant_id == tenant_id))
    db.execute(delete(Tenant).where(Tenant.id == tenant_id).execution_options(synchronize_session=False))
    db.commit()


async def execute(db, tenant, row):
    progress = copy.deepcopy(row.progress or {})
    # Persist intent before external writes. Tasks cannot be started again while
    # a partially completed cleanup is awaiting resumption.
    tenant.status, tenant.configuration_complete = TenantStatus.INACTIVE, False
    progress["started"] = True
    row.progress = copy.deepcopy(progress)
    row.execution_started_at = utcnow()
    db.commit()
    clients = await preflight(db, tenant, row)
    project = row.plan.get("semaphore")
    if project and project["owned"] and progress.get("project") != "deleted":
        progress["project"] = "deleting"
        row.progress = copy.deepcopy(progress)
        row.execution_started_at = utcnow()
        db.commit()
        try:
            await semaphore_client_from_db(db).delete_project(project["id"])
        except SemaphoreError as exc:
            if exc.status_code != 404:
                raise
        progress["project"] = "deleted"
        row.progress = copy.deepcopy(progress)
        db.commit()
    for item in row.plan["vault"]:
        if progress.get("vault", {}).get(vault_key(item)) == "deleted":
            continue
        progress.setdefault("vault", {})[vault_key(item)] = "deleting"
        row.progress = copy.deepcopy(progress)
        row.execution_started_at = utcnow()
        db.commit()
        client = clients[digest(item["identity"])]
        metadata = await client.metadata(item["path"])
        if metadata is not None:
            if not owned_metadata(metadata, item["receipt"]) or digest(metadata) != item["metadata_digest"]:
                raise ValueError("Vault-Objekt wurde vor seiner Löschung verändert. Ziel manuell prüfen.")
            await client.delete_metadata(item["path"])
            if await client.metadata(item["path"]) is not None:
                raise ValueError("Vault-Pfad ist nach dem Löschen wieder vorhanden. Vor einer Fortsetzung manuell prüfen.")
        progress["vault"][vault_key(item)] = "deleted"
        row.progress = copy.deepcopy(progress)
        db.commit()
    remove_local(db, tenant, row)
