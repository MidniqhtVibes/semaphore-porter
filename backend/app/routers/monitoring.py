"""Host snapshots, never task-duration guesses or remote command execution."""
from __future__ import annotations

import hashlib
from datetime import timezone
from pathlib import Path
import secrets
from typing import Annotated, Literal
from urllib.parse import urlsplit
import uuid

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator
from sqlalchemy import select

from app.audit import record_audit
from app.dependencies import Db, SystemAdmin
from app.models import DeploymentSource, Tenant, utcnow

router = APIRouter(tags=["Deployment-Überwachung"])
MAX_BODY = 2_000_000
STALE_AFTER = 90
Text = Annotated[str, Field(max_length=200)]
Identifier = Annotated[str, Field(min_length=1, max_length=160, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")]


class Deployment(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    deployment_id: Identifier
    application_id: Text = ""
    application_name: Text = ""
    release_id: Text = ""
    tenant_slug: Text = ""
    runtime_scope_id: Text = ""
    database_type: Text = ""
    provider_id: Text = ""
    database_mode: Text = ""
    dataset_id: Text = ""
    source_git_commit: Text = ""
    url: str = Field(default="", max_length=2000)
    host_port: int | None = Field(default=None, ge=1, le=65535)
    created_at: int | None = Field(default=None, ge=0, le=32_503_680_000)
    ready_at: int | None = Field(default=None, ge=0, le=32_503_680_000)
    expires_at: int | None = Field(default=None, ge=1, le=32_503_680_000)
    lifecycle_status: Literal["preparing", "running", "cleanup_pending", "unknown"] = "unknown"
    container_count: int | None = Field(default=None, ge=0, le=10_000)
    running_count: int | None = Field(default=None, ge=0, le=10_000)
    unhealthy_count: int | None = Field(default=None, ge=0, le=10_000)
    starting_count: int | None = Field(default=None, ge=0, le=10_000)
    metadata_error: bool = False

    @field_validator("url")
    @classmethod
    def endpoint(cls, value):
        if not value:
            return value
        try:
            parsed = urlsplit(value)
            port = parsed.port
        except ValueError:
            raise ValueError("Ungültige Deployment-URL.")
        if (parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username is not None
                or parsed.password is not None or parsed.query or parsed.fragment
                or any(ord(c) < 33 for c in value) or (port is not None and not 1 <= port <= 65535)):
            raise ValueError("Deployment-URLs dürfen keine Zugangsdaten, Abfragen oder Fragmente enthalten.")
        return value

    @model_validator(mode="after")
    def counts(self):
        counts = (self.container_count, self.running_count, self.unhealthy_count, self.starting_count)
        if any(c is None for c in counts) and not all(c is None for c in counts):
            raise ValueError("Containerzahlen müssen vollständig oder unbekannt sein.")
        if self.container_count is not None and (self.running_count > self.container_count
                or self.unhealthy_count + self.starting_count > self.running_count):
            raise ValueError("Widersprüchliche Containerzahlen.")
        return self


class Report(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    schema_version: Literal[1]
    observed_at: int
    complete: bool
    deployments: list[Deployment] = Field(max_length=1000)
    warnings: list[Literal["root_unavailable", "metadata_unreadable", "docker_unavailable", "limit_exceeded"]] = Field(default_factory=list, max_length=4)

    @model_validator(mode="after")
    def unique(self):
        if len({d.deployment_id for d in self.deployments}) != len(self.deployments):
            raise ValueError("Deployment-IDs müssen je Host eindeutig sein.")
        if self.complete and self.warnings:
            raise ValueError("Ein fehlerhafter Snapshot ist nicht vollständig.")
        return self


class SourceInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(min_length=2, max_length=160)


def timestamp(value):
    return value.replace(tzinfo=timezone.utc).timestamp() if value and value.tzinfo is None else value.timestamp() if value else None


def token():
    value = secrets.token_urlsafe(40)
    return value, hashlib.sha256(value.encode()).hexdigest()


@router.post("/admin/deployments/sources", status_code=201)
def create_source(payload: SourceInput, request: Request, response: Response, db: Db, admin: SystemAdmin):
    response.headers["Cache-Control"] = "no-store"
    value, hashed = token()
    row = DeploymentSource(name=payload.name, token_hash=hashed)
    db.add(row)
    db.flush()
    record_audit(db, "monitoring_source_created", actor=admin, request=request, target_type="deployment_source", target_id=row.id)
    db.commit()
    return {"id": str(row.id), "name": row.name, "token": value}


@router.post("/admin/deployments/sources/{source_id}/token")
def rotate_token(source_id: uuid.UUID, request: Request, response: Response, db: Db, admin: SystemAdmin):
    response.headers["Cache-Control"] = "no-store"
    row = db.get(DeploymentSource, source_id)
    if not row:
        raise HTTPException(404, "Monitoring-Quelle nicht gefunden.")
    value, row.token_hash = token()
    record_audit(db, "monitoring_token_rotated", actor=admin, request=request, target_type="deployment_source", target_id=row.id)
    db.commit()
    return {"id": str(row.id), "name": row.name, "token": value}


@router.delete("/admin/deployments/sources/{source_id}", status_code=204)
def delete_source(source_id: uuid.UUID, request: Request, db: Db, admin: SystemAdmin):
    row = db.get(DeploymentSource, source_id)
    if not row:
        raise HTTPException(404, "Monitoring-Quelle nicht gefunden.")
    record_audit(db, "monitoring_source_deleted", actor=admin, request=request, target_type="deployment_source", target_id=row.id)
    db.delete(row)
    db.commit()


@router.get("/admin/deployments/collector")
def collector(admin: SystemAdmin):
    return Response((Path(__file__).parents[1] / "integrations/deployment_collector.py").read_bytes(),
                    media_type="text/x-python", headers={"Content-Disposition": 'attachment; filename="semaporter-collector.py"'})


@router.get("/admin/deployments/exporter")
def exporter(admin: SystemAdmin):
    return Response((Path(__file__).parents[1] / "integrations/deployment_exporter.py").read_bytes(),
                    media_type="text/x-python", headers={"Content-Disposition": 'attachment; filename="semaporter-exporter.py"'})


@router.post("/monitoring/report", status_code=204)
async def receive_report(request: Request, db: Db):
    # Machine-only endpoint: no session fallback, no cookie-based authentication.
    auth = request.headers.get("authorization", "")
    if not auth.startswith("Bearer ") or not 30 <= len(auth[7:]) <= 200:
        raise HTTPException(401, "Collector-Token erforderlich.")
    row = db.scalar(select(DeploymentSource).where(DeploymentSource.token_hash == hashlib.sha256(auth[7:].encode()).hexdigest()).with_for_update())
    if row is None:
        raise HTTPException(401, "Collector-Token ungültig.")
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > MAX_BODY:
            raise HTTPException(413, "Snapshot zu groß.")
    try:
        report = Report.model_validate_json(body)
    except (ValidationError, ValueError):
        raise HTTPException(422, "Ungültiger Monitoring-Snapshot; nur den dokumentierten Metadatenvertrag senden.")
    now = utcnow()
    if not now.timestamp() - 300 <= report.observed_at <= now.timestamp() + 60:
        raise HTTPException(422, "Hostzeit oder Alter des Snapshots prüfen.")
    old = row.snapshot or {}
    if report.observed_at <= old.get("observed_at", 0):
        raise HTTPException(409, "Veralteter oder doppelter Snapshot.")
    # Preserve last known entries if any part of a scan failed. Absence is only
    # authoritative after a complete scan; otherwise it must never imply deletion.
    entries = {} if report.complete else {d["deployment_id"]: {**d, "retained": True} for d in old.get("deployments", [])}
    for deployment in report.deployments:
        entries[deployment.deployment_id] = {**deployment.model_dump(), "observed_at": report.observed_at, "retained": False}
    if len(entries) > 1000:
        raise HTTPException(422, "Zu viele Deployment-Einträge; vollständigen Snapshot nachliefern.")
    row.snapshot = {**report.model_dump(exclude={"deployments"}), "deployments": list(entries.values())}
    row.received_at = now
    db.commit()


def deployment_status(item, stale, now):
    if stale or item.get("metadata_error"):
        return "unknown"
    if item["lifecycle_status"] == "cleanup_pending":
        return "cleanup_pending"
    if item.get("expires_at") and item["expires_at"] <= now:
        return "expired"
    if item["lifecycle_status"] == "preparing":
        return "preparing"
    if item.get("container_count") is None:
        return "unknown"
    if not item["running_count"]:
        return "stopped" if item["container_count"] else "missing"
    if item["unhealthy_count"] or item["running_count"] < item["container_count"]:
        return "degraded"
    if item["starting_count"]:
        return "starting"
    return "running"


@router.get("/admin/deployments")
def deployments(response: Response, db: Db, admin: SystemAdmin):
    response.headers["Cache-Control"] = "no-store"
    now = int(utcnow().timestamp())
    tenants = {t.tenant_slug: t for t in db.scalars(select(Tenant))}
    sources, rows = [], []
    for source in db.scalars(select(DeploymentSource).order_by(DeploymentSource.name)):
        snapshot = source.snapshot or {}
        observed = snapshot.get("observed_at")
        stale = observed is None or now - observed > STALE_AFTER or now - (timestamp(source.received_at) or 0) > STALE_AFTER
        sources.append({"id": str(source.id), "name": source.name, "received_at": source.received_at,
                        "observed_at": observed, "stale": stale, "complete": snapshot.get("complete", False),
                        "warnings": snapshot.get("warnings", []), "deployment_count": len(snapshot.get("deployments", []))})
        for item in snapshot.get("deployments", []):
            item_stale = stale or item.get("retained", False) or now - item["observed_at"] > STALE_AFTER
            tenant = tenants.get(item["tenant_slug"])
            project = tenant.semaphore_project if tenant else None
            rows.append({**item, "id": f"{source.id}:{item['deployment_id']}", "source_id": str(source.id),
                         "host": source.name, "tenant_name": tenant.display_name if tenant else item["tenant_slug"],
                         "tenant_id": str(tenant.id) if tenant else None,
                         "semaphore_project_id": project.semaphore_project_id if project else None,
                         "stale": item_stale, "status": deployment_status(item, item_stale, now),
                         "remaining_seconds": max(0, item["expires_at"] - now) if item.get("expires_at") else None})
    rows.sort(key=lambda d: (d.get("expires_at") is None, d.get("expires_at") or 0, d["host"], d["deployment_id"]))
    return {"server_time": now, "stale_after_seconds": STALE_AFTER, "sources": sources, "deployments": rows}
