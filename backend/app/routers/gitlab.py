from __future__ import annotations

import uuid
from contextlib import contextmanager

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import func, select, update

from app.audit import record_audit
from app.dependencies import Db, SystemAdmin
from app.gitlab_client import GitLabError
from app.gitlab_schemas import ActivateInput, GitLabSettingsInput, PackageCreate, PackageUpdate, PublishInput, VersionInput
from app.gitlab_service import (check_version, clone_template, configured, public_configuration, public_draft,
    publish, refresh_remote, release_evidence, require_draft, save_configuration, validate_draft)
from app.models import AuditEvent, CatalogActivation, CatalogSnapshot, ProgramPackageDraft, ProjectTemplate
from app.package_contract import PlanError
from app.package_validation import (dump_yaml, encode, generate_package, package_files, read_yaml, source_hash,
    validate_edit, validate_snapshot)
from app.vault_catalog import Catalog, load_catalog

router = APIRouter(prefix="/admin", tags=["GitLab und Programmpakete"])


@contextmanager
def repository_errors():
    try:
        yield
    except GitLabError as exc:
        raise HTTPException(502, str(exc)) from exc
    except (ValueError, PlanError) as exc:
        raise HTTPException(422, str(exc)) from exc
    except (KeyError, TypeError, AttributeError, RecursionError) as exc:
        raise HTTPException(422, "Repository-Struktur entspricht nicht dem unterstützten Paketvertrag.") from exc


@router.get("/gitlab")
def get_settings(db: Db, admin: SystemAdmin):
    return public_configuration(db)


@router.put("/gitlab")
async def put_settings(payload: GitLabSettingsInput, request: Request, db: Db, admin: SystemAdmin):
    with repository_errors():
        await save_configuration(db, payload)
    record_audit(db, "gitlab_configuration_updated", actor=admin, request=request,
                 details={"project_id": payload.project_id, "write_enabled": payload.write_enabled})
    db.commit()
    return public_configuration(db)


@router.post("/gitlab/test")
async def test_connection(db: Db, admin: SystemAdmin):
    config, client = configured(db)
    with repository_errors():
        project = await client.get_project()
        branch = await client.branch(config["base_branch"])
    return {"message": "GitLab-Projekt und Basisbranch erreichbar. Schreibrechte werden erst bei ausdrücklicher Übergabe verwendet.",
            "project_name": project.get("path_with_namespace"), "sha": branch["commit"]["id"], "protected": bool(branch.get("protected"))}


@router.get("/gitlab/repository")
async def repository(db: Db, admin: SystemAdmin):
    config, client = configured(db)
    with repository_errors():
        branch = await client.branch(config["base_branch"])
        sha = branch["commit"]["id"]
        files = await client.snapshot(sha)
        catalog = read_yaml(files["programs/catalog.yml"])
        programs = []
        for package_id, entry in catalog["programs"].items():
            manifest = read_yaml(files[f"programs/{package_id}/program.yml"])
            programs.append({"id": package_id, "name": entry["display_name"], "database_types": list(manifest["database"]["types"]),
                "release": manifest["release"]["default"], "profile": manifest["secrets"]["vault_profile"]})
        providers = read_yaml(files["database-types/catalog.yml"])["database_types"]
    return {"sha": sha, "branch": config["base_branch"], "programs": programs, "providers": providers,
            "project_name": config.get("project_name"), "web_url": config.get("web_url")}


@router.get("/program-packages")
def list_drafts(db: Db, admin: SystemAdmin):
    return [public_draft(row) for row in db.scalars(select(ProgramPackageDraft).order_by(ProgramPackageDraft.updated_at.desc()).limit(500))]


@router.post("/program-packages", status_code=201)
async def create_draft(payload: PackageCreate, request: Request, db: Db, admin: SystemAdmin):
    config, client = configured(db)
    if db.scalar(select(func.count()).select_from(ProgramPackageDraft)) >= 500:
        raise HTTPException(409, "Maximal 500 gespeicherte Entwürfe. Unveröffentlichte Entwürfe zuerst entfernen.")
    with repository_errors():
        branch = await client.branch(config["base_branch"])
        files = await client.snapshot(branch["commit"]["id"])
        draft = ProgramPackageDraft(connection_id=config["connection_id"], package_id=payload.package_id,
            name=payload.name, base_branch=config["base_branch"], base_sha=branch["commit"]["id"],
            source_files=files, original_files=package_files(files, payload.package_id),
            files=generate_package(files, payload), created_by_id=admin.id)
        validate_edit(draft, draft.files)
    db.add(draft)
    db.flush()
    record_audit(db, "program_package_draft_created", actor=admin, request=request,
        target_type="program_package", target_id=draft.id, details={"package_id": draft.package_id, "base_sha": draft.base_sha})
    db.commit()
    return public_draft(draft, details=True)


@router.get("/program-packages/{draft_id}")
def get_draft(draft_id: uuid.UUID, db: Db, admin: SystemAdmin):
    draft = db.get(ProgramPackageDraft, draft_id)
    if draft is None:
        raise HTTPException(404, "Entwurf nicht gefunden.")
    return public_draft(draft, details=True)


@router.put("/program-packages/{draft_id}")
def update_draft(draft_id: uuid.UUID, payload: PackageUpdate, request: Request, db: Db, admin: SystemAdmin):
    draft, _, _ = require_draft(db, draft_id)
    check_version(draft, payload.version, editable=True)
    with repository_errors():
        if payload.manifest is not None:
            payload.files[f"programs/{draft.package_id}/program.yml"] = encode(dump_yaml(payload.manifest))
        manifest = read_yaml(payload.files[f"programs/{draft.package_id}/program.yml"])
        if payload.dataset_catalog is not None:
            payload.files[f"programs/{draft.package_id}/{manifest['datasets']['catalog']}"] = encode(dump_yaml(payload.dataset_catalog))
        catalog = read_yaml(payload.files["programs/catalog.yml"])
        if draft.package_id in catalog.get("programs", {}):
            catalog["programs"][draft.package_id]["display_name"] = manifest["display_name"]
            payload.files["programs/catalog.yml"] = encode(dump_yaml(catalog))
        validate_edit(draft, payload.files)
        # An editable but incomplete contract is allowed; the file graph must stay readable.
        read_yaml(payload.files[f"programs/{draft.package_id}/{manifest['datasets']['catalog']}"])
        name = manifest["display_name"]
        if not isinstance(name, str) or not 1 <= len(name) <= 128:
            raise ValueError("Anzeigename benötigt 1–128 Zeichen.")
    result = db.execute(update(ProgramPackageDraft).where(ProgramPackageDraft.id == draft_id,
        ProgramPackageDraft.version == payload.version, ProgramPackageDraft.branch.is_(None),
        ProgramPackageDraft.execution_started_at.is_(None)).values(files=payload.files, name=name,
            validation=None, version=payload.version + 1, status="draft", last_error=None))
    if result.rowcount != 1:
        db.rollback()
        raise HTTPException(409, "Entwurf wurde parallel geändert. Neu laden.")
    record_audit(db, "program_package_draft_updated", actor=admin, request=request, target_type="program_package", target_id=draft_id)
    db.commit()
    db.refresh(draft)
    return public_draft(draft, details=True)


@router.delete("/program-packages/{draft_id}")
def delete_draft(draft_id: uuid.UUID, payload: VersionInput, request: Request, db: Db, admin: SystemAdmin):
    draft, _, _ = require_draft(db, draft_id)
    check_version(draft, payload.version, editable=True)
    from sqlalchemy import delete
    result = db.execute(delete(ProgramPackageDraft).where(ProgramPackageDraft.id == draft_id,
        ProgramPackageDraft.version == payload.version, ProgramPackageDraft.branch.is_(None),
        ProgramPackageDraft.execution_started_at.is_(None)))
    if result.rowcount != 1:
        db.rollback()
        raise HTTPException(409, "Entwurf wurde parallel geändert.")
    record_audit(db, "program_package_draft_deleted", actor=admin, request=request, target_type="program_package", target_id=draft_id)
    db.commit()
    return {"message": "Lokaler Entwurf entfernt. Keine GitLab-Dateien gelöscht."}


@router.post("/program-packages/{draft_id}/validate")
def validate_package(draft_id: uuid.UUID, payload: VersionInput, request: Request, db: Db, admin: SystemAdmin):
    draft, _, _ = require_draft(db, draft_id)
    check_version(draft, payload.version, editable=True)
    with repository_errors():
        report = validate_draft(draft)
    result = db.execute(update(ProgramPackageDraft).where(ProgramPackageDraft.id == draft_id,
        ProgramPackageDraft.version == payload.version, ProgramPackageDraft.branch.is_(None),
        ProgramPackageDraft.execution_started_at.is_(None)).values(validation=report, status="validated", last_error=None))
    if result.rowcount != 1:
        db.rollback()
        raise HTTPException(409, "Entwurf wurde während der Prüfung geändert.")
    record_audit(db, "program_package_validated", actor=admin, request=request, target_type="program_package", target_id=draft_id)
    db.commit()
    db.refresh(draft)
    return public_draft(draft, details=True)


@router.post("/program-packages/{draft_id}/publish")
async def publish_package(draft_id: uuid.UUID, payload: PublishInput, request: Request, db: Db, admin: SystemAdmin):
    draft, config, client = require_draft(db, draft_id)
    check_version(draft, payload.version)
    if draft.merge_request_iid:
        with repository_errors():
            await refresh_remote(draft, config, client)
        db.commit()
        return public_draft(draft, details=True)
    if not draft.branch and (not draft.validation or draft.validation.get("version") != draft.version):
        raise HTTPException(409, "Entwurf zuerst speichern und erfolgreich prüfen.")
    record_audit(db, "program_package_publish_requested", actor=admin, request=request,
        target_type="program_package", target_id=draft_id, details={"base_sha": draft.base_sha})
    db.commit()
    result = await publish(db, draft, config, client)
    record_audit(db, "program_package_submitted", actor=admin, request=request, target_type="program_package",
        target_id=draft_id, details={"commit_sha": draft.commit_sha, "merge_request_iid": draft.merge_request_iid})
    db.commit()
    return result


@router.post("/program-packages/{draft_id}/refresh")
async def refresh_package(draft_id: uuid.UUID, db: Db, admin: SystemAdmin):
    draft, config, client = require_draft(db, draft_id)
    with repository_errors():
        await refresh_remote(draft, config, client)
    db.commit()
    return public_draft(draft, details=True)


def active_id(db):
    active = db.get(CatalogActivation, 1)
    return active.snapshot_id if active else None


def public_snapshot(row, active, current):
    previous, proposed = current.applications, row.catalog["applications"]
    return {"id": str(row.id), "source_sha": row.source_sha, "source_hash": row.source_hash,
        "connection_id": row.connection_id, "created_at": row.created_at,
        "active": row.id == active, "catalog": row.catalog, "validation": row.validation,
        "project_name": row.project_metadata.get("path_with_namespace"),
        "diff": {"added": sorted(set(proposed) - set(previous)), "removed": sorted(set(previous) - set(proposed)),
                 "changed": sorted(key for key in set(previous) & set(proposed) if previous[key].model_dump() != proposed[key])}}


@router.get("/gitlab/snapshots")
def snapshots(db: Db, admin: SystemAdmin):
    current, active = load_catalog(db), active_id(db)
    rows = db.scalars(select(CatalogSnapshot).order_by(CatalogSnapshot.created_at.desc()).limit(100))
    return {"active_id": str(active) if active else None, "current_catalog": current.model_dump(),
            "snapshots": [public_snapshot(row, active, current) for row in rows]}


@router.post("/gitlab/snapshots", status_code=201)
async def prepare_snapshot(request: Request, db: Db, admin: SystemAdmin):
    config, client = configured(db)
    with repository_errors():
        project = await client.get_project()
        branch = await client.branch(config["base_branch"])
        sha = branch["commit"]["id"]
        evidence = await release_evidence(config, client, sha)
        files = await client.snapshot(sha)
        validation, catalog = validate_snapshot(files, sha)
        validation["pipeline"] = evidence
    row = CatalogSnapshot(connection_id=config["connection_id"], source_sha=sha, source_hash=source_hash(files),
        catalog=catalog, validation=validation, project_metadata={key: project.get(key) for key in
            ("id", "path_with_namespace", "http_url_to_repo", "ssh_url_to_repo")}, created_by_id=admin.id)
    db.add(row)
    db.flush()
    record_audit(db, "catalog_snapshot_prepared", actor=admin, request=request, target_type="catalog_snapshot", target_id=row.id,
        details={"source_sha": sha, "source_hash": row.source_hash, "pipeline_id": evidence["pipeline_id"]})
    db.commit()
    return public_snapshot(row, active_id(db), load_catalog(db))


@router.post("/gitlab/snapshots/{snapshot_id}/activate")
async def activate_snapshot(snapshot_id: uuid.UUID, payload: ActivateInput, request: Request, db: Db, admin: SystemAdmin):
    row = db.get(CatalogSnapshot, snapshot_id)
    if row is None:
        raise HTTPException(404, "Katalogstand nicht gefunden.")
    config, client = configured(db)
    if row.connection_id != config["connection_id"]:
        raise HTTPException(409, "Katalogstand gehört zu einer anderen GitLab-Verbindung.")
    source = db.get(ProjectTemplate, payload.project_template_id)
    if source is None:
        raise HTTPException(404, "Projektvorlage nicht gefunden.")
    with repository_errors():
        Catalog.model_validate(row.catalog)
        if payload.historical:
            approved = db.scalar(select(AuditEvent.id).where(AuditEvent.event_type == "catalog_snapshot_activated",
                AuditEvent.target_id == str(row.id), AuditEvent.success.is_(True)).limit(1))
            if not approved:
                raise ValueError("Rücknahme ist nur auf einen bereits aktivierten Katalogstand möglich.")
        else:
            await release_evidence(config, client, row.source_sha)
            # Confirm content provenance again; the prepared snapshot is immutable.
            if source_hash(await client.snapshot(row.source_sha)) != row.source_hash:
                raise ValueError("Repository-Inhalt stimmt nicht mit dem vorbereiteten Katalogstand überein.")
        document = clone_template(source, payload, row)
    active = db.get(CatalogActivation, 1)
    if active is None:
        active = CatalogActivation(id=1)
        db.add(active)
        db.flush()
    result = db.execute(update(CatalogActivation).where(CatalogActivation.id == 1,
        CatalogActivation.snapshot_id == payload.expected_active_id).values(snapshot_id=row.id))
    if result.rowcount != 1:
        db.rollback()
        raise HTTPException(409, "Aktiver Katalog wurde parallel geändert. Vergleich neu laden.")
    template = ProjectTemplate(name=payload.template_name, description=f"GitLab {config['project_name']} · {row.source_sha}",
        source_type="gitlab", source_project_id=source.source_project_id, backup_document=document,
        catalog_snapshot_id=row.id, created_by_id=admin.id)
    db.add(template)
    db.flush()
    record_audit(db, "catalog_snapshot_activated", actor=admin, request=request, target_type="catalog_snapshot", target_id=row.id,
        details={"source_sha": row.source_sha, "project_template_id": str(template.id), "historical": payload.historical})
    db.commit()
    return {"message": "Katalog aktiviert und separate Projektvorlage auf die freigegebene Commit-SHA festgelegt. Bestehende Tenants bleiben unverändert.",
            "active_id": str(row.id), "project_template_id": str(template.id)}
