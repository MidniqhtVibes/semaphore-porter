import hashlib
import json
import time
import subprocess

import pytest
from sqlalchemy import select

from app.database import SessionLocal
from app.integrations import deployment_collector as collector
from app.integrations import deployment_exporter as exporter
from app.models import AuditEvent, DeploymentSource, SemaphoreProject, Tenant


def source(client, headers, name="Zielhost"):
    response = client.post("/api/admin/deployments/sources", headers=headers, json={"name": name})
    assert response.status_code == 201, response.text
    assert response.headers["cache-control"] == "no-store"
    return response.json()


def deployment(**changes):
    now = int(time.time())
    return {"deployment_id": "demo-1", "application_id": "azubiorga", "tenant_slug": "demo",
            "runtime_scope_id": "azubi-test", "created_at": now - 200, "ready_at": now - 60, "expires_at": now + 3540,
            "lifecycle_status": "running", "container_count": 2, "running_count": 2,
            "unhealthy_count": 0, "starting_count": 0, **changes}


def report(client, src, *, observed=None, complete=True, items=None, warnings=None):
    return client.post("/api/monitoring/report", headers={"Authorization": f"Bearer {src['token']}"}, json={
        "schema_version": 1, "observed_at": observed or int(time.time()), "complete": complete,
        "deployments": [deployment()] if items is None else items, "warnings": warnings or []})


def test_machine_endpoint_requires_own_token_and_admin_pages_are_protected(client, operator_headers):
    assert client.get("/api/admin/deployments").status_code == 403
    assert client.get("/api/admin/deployments/collector").status_code == 403
    assert client.get("/api/admin/deployments/exporter").status_code == 403
    assert client.post("/api/admin/deployments/sources", headers=operator_headers, json={"name": "Host"}).status_code == 403
    assert client.post("/api/monitoring/report", json={}).status_code == 401
    assert client.post("/api/monitoring/report", headers={"Authorization": "Bearer " + "a" * 54}, json={}).status_code == 401


def test_snapshot_ttl_and_metadata_include_deployments_not_started_by_portal(client, admin_headers):
    src = source(client, admin_headers)
    with SessionLocal() as db:
        tenant = Tenant(tenant_slug="demo", display_name="Demo Tenant")
        db.add(tenant)
        db.flush()
        db.add(SemaphoreProject(tenant_id=tenant.id, semaphore_project_id=77, name="Demo"))
        db.commit()
    assert report(client, src).status_code == 204
    response = client.get("/api/admin/deployments")
    data = response.json()
    row = data["deployments"][0]
    assert row["tenant_name"] == "Demo Tenant" and row["semaphore_project_id"] == 77
    assert row["status"] == "running" and 3530 <= row["remaining_seconds"] <= 3540
    assert row["remaining_seconds"] == row["expires_at"] - data["server_time"]
    assert "token" not in response.text and src["token"] not in response.text
    with SessionLocal() as db:
        stored = db.scalar(select(DeploymentSource))
        assert stored.token_hash == hashlib.sha256(src["token"].encode()).hexdigest()
        assert src["token"] not in str(stored.snapshot)
        assert src["token"] not in str([e.details for e in db.scalars(select(AuditEvent))])


def test_sources_are_isolated_rotation_revokes_old_token_and_deletion_revokes_access(client, admin_headers):
    first, second = source(client, admin_headers), source(client, admin_headers, "Anderer Host")
    assert report(client, first).status_code == 204
    assert report(client, second, items=[deployment(deployment_id="another")]).status_code == 204
    assert len(client.get("/api/admin/deployments").json()["deployments"]) == 2
    rotated = client.post(f"/api/admin/deployments/sources/{first['id']}/token", headers=admin_headers).json()
    assert report(client, first).status_code == 401
    assert report(client, rotated, observed=int(time.time()) + 1).status_code == 204
    assert client.delete(f"/api/admin/deployments/sources/{first['id']}", headers=admin_headers).status_code == 204
    assert report(client, rotated).status_code == 401
    assert len(client.get("/api/admin/deployments").json()["deployments"]) == 1


def test_partial_scan_retains_last_state_and_only_complete_absence_removes_entries(client, admin_headers):
    src = source(client, admin_headers)
    now = int(time.time())
    assert report(client, src, observed=now - 2).status_code == 204
    assert report(client, src, observed=now - 1, complete=False, items=[], warnings=["root_unavailable"]).status_code == 204
    data = client.get("/api/admin/deployments").json()
    assert data["deployments"][0]["stale"] and data["deployments"][0]["status"] == "unknown"
    assert not data["sources"][0]["complete"]
    assert report(client, src, observed=now, items=[]).status_code == 204
    assert client.get("/api/admin/deployments").json()["deployments"] == []


@pytest.mark.parametrize("changes,expected", [
    ({"expires_at": int(time.time()) - 10}, "expired"),
    ({"lifecycle_status": "cleanup_pending"}, "cleanup_pending"),
    ({"lifecycle_status": "preparing", "expires_at": None}, "preparing"),
    ({"running_count": 0}, "stopped"),
    ({"running_count": 1}, "degraded"),
    ({"unhealthy_count": 1}, "degraded"),
    ({"starting_count": 1}, "starting"),
    ({"container_count": 0, "running_count": 0}, "missing"),
    ({"container_count": None, "running_count": None, "unhealthy_count": None, "starting_count": None}, "unknown"),
])
def test_actual_runtime_status_and_unknown_ttl(client, admin_headers, changes, expected):
    src = source(client, admin_headers)
    assert report(client, src, items=[deployment(**changes)]).status_code == 204
    row = client.get("/api/admin/deployments").json()["deployments"][0]
    assert row["status"] == expected
    if changes.get("expires_at", 1) is None:
        assert row["remaining_seconds"] is None


def test_stale_host_is_unknown_instead_of_healthy_and_restarts_keep_snapshot(client, admin_headers):
    src = source(client, admin_headers)
    assert report(client, src, observed=int(time.time()) - 120).status_code == 204
    assert client.get("/api/admin/deployments").json()["deployments"][0]["status"] == "unknown"
    with SessionLocal() as db:
        row = db.scalar(select(DeploymentSource))
        assert row.snapshot["deployments"][0]["deployment_id"] == "demo-1"


def test_replay_clock_invalid_and_secret_bearing_payload_never_replace_snapshot(client, admin_headers):
    src = source(client, admin_headers)
    now = int(time.time())
    assert report(client, src, observed=now - 2).status_code == 204
    assert report(client, src, observed=now - 2, items=[]).status_code == 409
    assert report(client, src, observed=now + 600).status_code == 422
    assert report(client, src, observed=now - 600).status_code == 422
    for changes in ({"secret": "hidden-secret"}, {"url": "https://user:hidden-secret@host.example"},
                    {"url": "https://host.example/?token=hidden-secret"}, {"running_count": 3}):
        response = report(client, src, observed=now, items=[deployment(**changes)])
        assert response.status_code == 422, response.text
        assert "hidden-secret" not in response.text
    assert len(client.get("/api/admin/deployments").json()["deployments"]) == 1


def test_large_authenticated_report_is_rejected_and_csrf_remains_required_for_admin_writes(client, admin_headers):
    src = source(client, admin_headers)
    assert client.post("/api/monitoring/report", headers={"Authorization": "Bearer " + src["token"]}, content=b"x" * 2_000_001).status_code == 413
    assert client.post(f"/api/admin/deployments/sources/{src['id']}/token").status_code == 403
    response = client.get("/api/admin/deployments/collector")
    assert response.status_code == 200 and "def read_snapshot(" in response.text
    assert "import subprocess" not in response.text
    assert src["token"] not in response.text
    response = client.get("/api/admin/deployments/exporter")
    assert response.status_code == 200 and "def collect(" in response.text
    assert "urllib.request" not in response.text and src["token"] not in response.text


def write_state(root, *, name="demo-1", **changes):
    directory = root / name
    directory.mkdir()
    state = {"schema_version": 7, "deployment_id": name, "tenant_slug": "demo", "runtime_scope_id": "scope",
             "application": {"id": "azubiorga", "display_name": "AzubiOrga", "release_id": "v1"},
             "database": {"type": "postgres", "provider_id": "pg", "mode": "shared_pool", "password": "never-send-this"},
             "dataset": {"id": "test"}, "endpoint": {"url": "http://10.0.0.1:30001", "host_port": 30001},
             "lifecycle": {"created_at": 100, "ready_at": 200, "expires_at": 400}, **changes}
    (directory / "state.json").write_text(json.dumps(state))
    (directory / "status.env").write_text("STATUS=running\nEXPIRES_AT=500\n")
    return directory


def test_collector_reads_authoritative_state_and_docker_counts_without_environments(tmp_path):
    directory = write_state(tmp_path)
    (directory / ".env").write_text("SUPER_SECRET=never-send-this")
    report = exporter.collect(tmp_path, read_docker=False, containers={"demo-1": [{"State": "running", "Status": "Up (healthy)"}, {"State": "exited", "Status": "Exited (1)"}]})
    assert report["complete"]
    row = report["deployments"][0]
    assert row["expires_at"] == 500 and row["ready_at"] == 200 and row["host_port"] == 30001
    assert row["running_count"] == 1 and row["container_count"] == 2
    assert row["provider_id"] == "pg" and row["dataset_id"] == "test"
    assert "never-send-this" not in json.dumps(report)
    from app.routers.monitoring import Report
    Report.model_validate_json(json.dumps(report))


def test_collector_unreadable_state_docker_failure_and_absence_never_claim_empty_success(tmp_path, monkeypatch):
    directory = write_state(tmp_path)
    (directory / "state.json").write_text("{partial json")
    monkeypatch.setattr(exporter, "docker_containers", lambda *args: (_ for _ in ()).throw(subprocess.TimeoutExpired("docker", 10)))
    report = exporter.collect(tmp_path)
    assert not report["complete"] and set(report["warnings"]) == {"docker_unavailable", "metadata_unreadable"}
    report = exporter.collect(tmp_path / "absent", read_docker=False, containers={})
    assert not report["complete"] and report["warnings"] == ["root_unavailable"]


def test_collector_rejects_symlink_and_never_transmits_credential_url(tmp_path):
    directory = write_state(tmp_path, endpoint={"url": "https://user:password@example.com?token=private"})
    assert exporter.collect(tmp_path, read_docker=False, containers={})["deployments"][0]["url"] == ""
    (directory / "state.json").unlink()
    outside = tmp_path / "private-file"
    outside.write_text("private")
    (directory / "state.json").symlink_to(outside)
    report = exporter.collect(tmp_path, read_docker=False, containers={})
    assert not report["complete"] and report["deployments"] == []


def test_collector_parses_legacy_metadata_and_ignores_unrelated_directories(tmp_path):
    directory = tmp_path / "legacy"
    directory.mkdir()
    (directory / "metadata.env").write_text("DEPLOYMENT_ID=legacy\nAPPLICATION_ID=wordpress\nTENANT_SLUG=demo\nREADY_AT=100\nEXPIRES_AT=200\nDB_PASSWORD=private\n")
    (directory / "status.env").write_text("STATUS=cleanup_pending\nCLEANUP_AFTER=300\n")
    (tmp_path / "unrelated-pool").mkdir()
    result = exporter.collect(tmp_path, read_docker=False, containers={})
    assert result["complete"] and len(result["deployments"]) == 1
    assert result["deployments"][0]["lifecycle_status"] == "cleanup_pending"
    assert result["deployments"][0]["expires_at"] == 200 and "private" not in json.dumps(result)


def test_collector_docker_query_is_read_only_local_and_matches_compose_projects(monkeypatch):
    def run(command, **options):
        assert command == ["/usr/bin/docker", "ps", "--all", "--format", "{{json .}}"]
        assert options["env"]["DOCKER_HOST"] == "unix:///var/run/docker.sock"
        assert "SEMAPORTER_MONITOR_TOKEN" not in options["env"] and "PYTHONPATH" not in options["env"]
        return subprocess.CompletedProcess(command, 0, stdout="\n".join(json.dumps(row) for row in [
            {"State": "running", "Status": "Up (healthy)", "Labels": "x=y,com.docker.compose.project=demo-1", "Command": "not-transmitted"},
            {"State": "exited", "Status": "Exited", "Labels": "com.docker.compose.project=demo-1"},
            {"State": "running", "Status": "Up", "Labels": "unrelated=yes"}]))
    monkeypatch.setattr(exporter.subprocess, "run", run)
    assert exporter.docker_containers() == {"demo-1": [
        {"State": "running", "Status": "Up (healthy)"}, {"State": "exited", "Status": "Exited"}]}


def test_collector_follows_no_redirects_and_never_prints_exception_details(monkeypatch, capsys):
    assert collector.NoRedirect().redirect_request(None, None, 302, "", {}, "https://other") is None
    monkeypatch.setenv("SEMAPORTER_URL", "https://semaporter.example")
    monkeypatch.setattr("sys.argv", ["collector.py", "--snapshot", "/protected/snapshot.json", "--once"])
    monkeypatch.setattr(collector, "service_account", lambda: None)
    monkeypatch.setattr(collector, "read_token", lambda: "a" * 54)
    monkeypatch.setattr(collector, "read_snapshot", lambda path: {"observed_at": 100})
    monkeypatch.setattr(collector, "send", lambda *args: (_ for _ in ()).throw(ValueError("secret-in-error")))
    assert collector.main() == 1
    assert "secret-in-error" not in capsys.readouterr().err
