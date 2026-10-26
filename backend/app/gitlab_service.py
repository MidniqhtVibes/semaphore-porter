from __future__ import annotations

import copy
import json
import uuid
from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy import or_, select, update

from app.gitlab_client import GitLabClient, GitLabError, SHA
from app.gitlab_schemas import GitLabSettingsInput
from app.models import GitLabSettings, ProgramPackageDraft, utcnow
from app.package_contract import PlanError
from app.package_validation import combined_files, diff_files, read_yaml, validate_snapshot
from app.security import decrypt_secret, encrypt_secret


def configuration(db):
    row = db.get(GitLabSettings, 1)
    return json.loads(decrypt_secret(row.encrypted_configuration)) if row else {}


def public_configuration(db):
    config = configuration(db)
    return {"configured": bool(config), "token_present": bool(config.get("token")),
            **{key: value for key, value in config.items() if key != "token"}}


def configured(db):
    config = configuration(db)
    if not config.get("token"):
        raise HTTPException(409, "GitLab zuerst unter Einstellungen → Verbindungen → GitLab konfigurieren.")
    return config, GitLabClient(config)


async def save_configuration(db, payload: GitLabSettingsInput):
    previous = configuration(db)
    config = payload.model_dump(exclude={"token"})
    identity_changed = any(config[key] != previous.get(key) for key in ("base_url", "project_id", "base_branch"))
    config["connection_id"] = uuid.uuid4().hex if identity_changed else previous["connection_id"]
    config["token"] = payload.token.get_secret_value() if payload.token and payload.token.get_secret_value() else (
        "" if identity_changed else previous.get("token", ""))
    if not config["token"]:
        raise ValueError("Für eine neue GitLab-Verbindung einen Token eintragen.")
    client = GitLabClient(config)
    project = await client.get_project()
    branch = await client.branch(config["base_branch"])
    config.update(project_name=project.get("path_with_namespace", str(config["project_id"])),
        web_url=client.web_link(project.get("web_url")), last_tested_at=utcnow().isoformat(),
        protected=bool(branch.get("protected")))
    row = db.get(GitLabSettings, 1) or GitLabSettings(id=1)
    row.encrypted_configuration = encrypt_secret(json.dumps(config))
    db.add(row)


def require_draft(db, draft_id):
    draft = db.get(ProgramPackageDraft, draft_id)
    if draft is None:
        raise HTTPException(404, "Programmpaket-Entwurf nicht gefunden.")
    config, client = configured(db)
    if draft.connection_id != config["connection_id"]:
        raise HTTPException(409, "Entwurf gehört zu einer anderen GitLab-Verbindung. Ursprüngliche Verbindung wiederherstellen oder neu entwerfen.")
    return draft, config, client


def public_draft(draft, *, details=False):
    value = {"id": str(draft.id), "package_id": draft.package_id, "name": draft.name,
        "base_sha": draft.base_sha, "base_branch": draft.base_branch, "version": draft.version,
        "status": draft.status, "branch": draft.branch, "commit_sha": draft.commit_sha,
        "merge_request_iid": draft.merge_request_iid, "remote_status": draft.remote_status,
        "validation": draft.validation, "last_error": draft.last_error,
        "created_at": draft.created_at, "updated_at": draft.updated_at,
        "connection_id": draft.connection_id, "execution_started_at": draft.execution_started_at}
    if details:
        value.update(files=draft.files, diff=diff_files(draft.original_files, draft.files))
        manifest = read_yaml(draft.files[f"programs/{draft.package_id}/program.yml"])
        value["manifest"] = manifest
        value["dataset_catalog"] = read_yaml(draft.files[f"programs/{draft.package_id}/{manifest['datasets']['catalog']}"])
    return value


def check_version(draft, version, *, editable=False):
    if draft.version != version:
        raise HTTPException(409, "Entwurf wurde parallel geändert. Neu laden und Änderungen vergleichen.")
    if editable and (draft.branch or draft.execution_started_at):
        raise HTTPException(409, "Übergebene Entwürfe sind unveränderlich. Ein neues Paket aus dem aktuellen Basisstand öffnen.")


def validate_draft(draft):
    report, _ = validate_snapshot(combined_files(draft), draft.base_sha, draft.package_id)
    report["version"] = draft.version
    if not diff_files(draft.original_files, draft.files):
        raise ValueError("Entwurf enthält keine Änderungen.")
    draft.validation, draft.status, draft.last_error = report, "validated", None
    return report


def acquire_lease(db, draft):
    started, token = utcnow(), uuid.uuid4().hex
    result = db.execute(update(ProgramPackageDraft).where(ProgramPackageDraft.id == draft.id,
        or_(ProgramPackageDraft.execution_started_at.is_(None),
            ProgramPackageDraft.execution_started_at < started - timedelta(minutes=15))).values(execution_started_at=started, execution_token=token).execution_options(synchronize_session=False))
    if result.rowcount != 1:
        db.rollback()
        raise HTTPException(409, "Ein GitLab-Vorgang läuft bereits. Hängende Ausführungen können nach 15 Minuten abgeglichen werden.")
    db.commit()
    db.refresh(draft)
    return token


def lease_commit(db, draft, token):
    current = db.scalar(select(ProgramPackageDraft.execution_token).where(ProgramPackageDraft.id == draft.id))
    if current != token:
        db.rollback()
        raise HTTPException(409, "Ausführungssperre wurde übernommen. Vorgang erneut laden.")
    db.commit()


async def reconcile_commit(client, draft, branch):
    sha = branch["commit"]["id"]
    commit = await client.request("GET", f"{client.project}/repository/commits/{sha}")
    if (draft.commit_sha and sha != draft.commit_sha) or commit.get("parent_ids") != [draft.base_sha] or f"Semaporter {draft.id}" not in commit.get("message", ""):
        raise ValueError("Entwurfsbranch enthält fremde Änderungen. Manuell in GitLab prüfen.")
    expected = combined_files(draft)
    actual = await client.snapshot(sha)
    if actual != expected:
        raise ValueError("GitLab-Dateien entsprechen nicht exakt dem geprüften Entwurf. Keine automatische Übernahme.")
    return sha


async def publish(db, draft, config, client):
    if not config.get("write_enabled"):
        raise HTTPException(409, "GitLab ist im Lesemodus. Schreibmodus ausdrücklich in der Verbindung aktivieren.")
    lease = acquire_lease(db, draft)
    try:
        # Validate again after acquiring the lease; UI state never substitutes for server checks.
        if not draft.commit_sha:
            validate_draft(draft)
        draft.branch = draft.branch or f"semaporter/programs/{draft.package_id}/{draft.id.hex}"
        draft.status = "committing"
        lease_commit(db, draft, lease)
        if draft.commit_sha:
            # An MR may already have been merged and its source branch removed after a lost response.
            known = await client.merge_requests(draft.branch)
            if known:
                if len(known) != 1:
                    raise ValueError("Mehrere Merge Requests gefunden. Manuell prüfen.")
                mr = known[0]
                if (mr.get("source_project_id") != config["project_id"] or mr.get("target_project_id") != config["project_id"]
                        or mr.get("source_branch") != draft.branch or mr.get("target_branch") != draft.base_branch
                        or mr.get("sha") != draft.commit_sha or str(draft.id) not in mr.get("description", "")):
                    raise ValueError("Vorhandener Merge Request passt nicht zur bestätigten Entwurfsrevision.")
                draft.merge_request_iid = mr["iid"]
                await refresh_remote(draft, config, client)
                lease_commit(db, draft, lease)
                return public_draft(draft, details=True)
        remote_branch = await client.branch(draft.branch, absence_ok=True)
        if remote_branch:
            draft.commit_sha = await reconcile_commit(client, draft, remote_branch)
        else:
            if draft.commit_sha:
                raise ValueError("Bereits bestätigter Entwurfsbranch fehlt. Keine erneute Anlage.")
            target = await client.branch(draft.base_branch)
            if not target.get("protected"):
                raise ValueError("Basisbranch vor der Übergabe in GitLab schützen.")
            if target["commit"]["id"] != draft.base_sha:
                raise ValueError("Basisbranch wurde geändert. Neuen Entwurf vom aktuellen Stand anlegen und Diff übertragen.")
            actions = [{"action": change["action"], "file_path": change["path"], **({
                "encoding": "base64", "content": draft.files[change["path"]]} if change["action"] != "delete" else {})}
                for change in diff_files(draft.original_files, draft.files)]
            lease_commit(db, draft, lease)
            result = await client.commit({"branch": draft.branch, "start_sha": draft.base_sha,
                "commit_message": f"{draft.name}\n\nSemaporter {draft.id}", "actions": actions, "force": False})
            if not SHA.fullmatch(str(result.get("id", ""))):
                raise GitLabError("GitLab bestätigte den Commit nicht eindeutig.", uncertain=True)
            draft.commit_sha = result["id"]
        draft.status = "commit_created"
        lease_commit(db, draft, lease)
        requests = await client.merge_requests(draft.branch)
        if len(requests) > 1:
            raise ValueError("Mehrere Merge Requests für den Entwurf gefunden. Manuelle Prüfung erforderlich.")
        if requests:
            mr = requests[0]
            if (mr.get("source_branch") != draft.branch or mr.get("target_branch") != draft.base_branch
                    or mr.get("source_project_id") != config["project_id"] or mr.get("target_project_id") != config["project_id"]):
                raise ValueError("Merge Request gehört nicht zum erwarteten Projekt und Branch.")
        else:
            draft.status = "mr_pending"
            lease_commit(db, draft, lease)
            mr = await client.create_merge_request({"source_branch": draft.branch, "target_branch": draft.base_branch,
                "title": f"Programmpaket: {draft.name}", "description": f"Semaporter-Entwurf `{draft.id}`\n\nBasis: `{draft.base_sha}`\n\nVerträge lokal geprüft. CI und menschlicher Review sind vor Übernahme erforderlich.",
                "remove_source_branch": True})
        if type(mr.get("iid")) is not int:
            raise GitLabError("GitLab bestätigte den Merge Request nicht eindeutig.", uncertain=True)
        draft.merge_request_iid, draft.status, draft.last_error = mr["iid"], "submitted", None
        draft.remote_status = {"state": mr.get("state"), "web_url": client.web_link(mr.get("web_url")), "sha": draft.commit_sha}
        lease_commit(db, draft, lease)
    except (GitLabError, ValueError, PlanError, KeyError, TypeError) as exc:
        draft.status = "verification_required" if isinstance(exc, GitLabError) and exc.uncertain else "failed"
        draft.last_error = str(exc) if isinstance(exc, (GitLabError, ValueError, PlanError)) else "Repository-Antwort entspricht nicht dem unterstützten Vertrag."
        lease_commit(db, draft, lease)
        raise HTTPException(409 if not isinstance(exc, GitLabError) else 502, draft.last_error) from exc
    finally:
        db.execute(update(ProgramPackageDraft).where(ProgramPackageDraft.id == draft.id,
            ProgramPackageDraft.execution_token == lease).values(execution_started_at=None, execution_token=None))
        db.commit()
        db.refresh(draft)
    return public_draft(draft, details=True)


async def refresh_remote(draft, config, client):
    if not draft.merge_request_iid:
        raise HTTPException(409, "Noch kein Merge Request vorhanden. Übergabe erneut abgleichen.")
    mr = await client.merge_request(draft.merge_request_iid)
    if (mr.get("source_branch") != draft.branch or mr.get("target_branch") != draft.base_branch
            or mr.get("source_project_id") != config["project_id"] or mr.get("target_project_id") != config["project_id"]):
        raise ValueError("Merge Request gehört nicht zum gespeicherten Projekt.")
    pipelines = await client.pipelines(draft.commit_sha)
    draft.remote_status = {"state": mr.get("state"), "web_url": client.web_link(mr.get("web_url")),
        "sha": mr.get("sha"), "merge_commit_sha": mr.get("merge_commit_sha"), "squash_commit_sha": mr.get("squash_commit_sha"),
        "merge_status": mr.get("detailed_merge_status"), "review_required": True,
        "pipelines": [{"id": p["id"], "sha": p.get("sha"), "ref": p.get("ref"), "status": p.get("status"),
                       "web_url": client.web_link(p.get("web_url"))} for p in pipelines[:20]]}
    draft.status = {"merged": "merged", "closed": "closed"}.get(mr.get("state"), "submitted")
    draft.last_error = None


async def release_evidence(config, client, sha):
    branch = await client.branch(config["base_branch"])
    if branch["commit"]["id"] != sha or not branch.get("protected"):
        raise ValueError("Übernahme benötigt den aktuellen Stand eines geschützten Basisbranches.")
    pipelines = await client.pipelines(sha)
    eligible = [p for p in pipelines if p.get("sha") == sha and p.get("ref") == config["base_branch"]]
    latest = max(eligible, key=lambda p: p.get("id", 0), default=None)
    if not latest or latest.get("status") != "success":
        raise ValueError("Die neueste Pipeline der exakten Basisrevision muss erfolgreich sein; fehlende, laufende und übersprungene Prüfungen reichen nicht.")
    return {"pipeline_id": latest["id"], "sha": sha, "status": "success", "web_url": client.web_link(latest.get("web_url"))}


def clone_template(source, payload, snapshot):
    document = copy.deepcopy(source.backup_document)
    repository = next((r for r in document.get("repositories", []) if r.get("name") == payload.repository_name), None)
    project = snapshot.project_metadata
    if repository is None:
        raise ValueError("Ausgewähltes Repository fehlt in der Projektvorlage.")
    git_url = repository.get("git_url", "")
    if git_url not in {project.get("http_url_to_repo"), project.get("ssh_url_to_repo")}:
        raise ValueError("Vorlagen-Repository stimmt nicht mit dem verbundenen GitLab-Projekt überein (HTTP-/SSH-Clone-URL vergleichen).")
    # Never change live Semaphore resources. Save a separate, revision-pinned backup.
    repository["git_branch"] = snapshot.source_sha
    document["meta"]["name"] = payload.template_name
    catalog = snapshot.catalog
    options = {"application_id": list(catalog["applications"]),
        "database_type": sorted({kind for app in catalog["applications"].values() for kind in app["database_types"]}),
        "dataset_id": ["none", *sorted({ds for app in catalog["applications"].values() for ds in app["datasets"]})]}
    changed = 0
    for template in document.get("templates", []):
        if template.get("repository") != payload.repository_name:
            continue
        fields = {field.get("name"): field for field in template.get("survey_vars", []) if isinstance(field, dict)}
        if "application_id" not in fields:
            continue
        for name, values in options.items():
            if name not in fields:
                raise ValueError("Deployment-Template benötigt application_id, database_type und dataset_id als Survey-Auswahllisten.")
            fields[name]["values"] = [{"name": v, "value": v} for v in values]
            if fields[name].get("default_value") not in values:
                fields[name]["default_value"] = values[0]
        changed += 1
    if not changed:
        raise ValueError("Keine Deployment-Tasks mit application_id-Survey am gewählten Repository gefunden.")
    return document
