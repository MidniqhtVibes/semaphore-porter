import copy
import json
import uuid

import httpx
import pytest
import respx
from sqlalchemy import select

from app.database import SessionLocal
from app.models import AuditEvent, CreationJob, ProjectTemplate, Tenant, VaultSettings, utcnow
from app.security import decrypt_secret
from app.vault_catalog import Catalog, load_catalog
from app.vault_client import safe_path, safe_url
from test_creation_jobs import seed_source


CONFIG = {
    "enabled": True, "base_url": "https://vault.example", "kv_mount": "kv", "tenant_root": "semaphore/tenants",
    "namespace": "company", "writer_auth_mount": "porter", "reader_auth_mount": "semaphore-ansible",
    "writer_role_id": "writer-role-private", "writer_secret_id": "writer-secret-private",
    "reader_role_id": "reader-role-private", "reader_secret_id": "reader-secret-private",
    "registry_passwords": {"azubiorga": "azubi-registry-private", "wordpress": "wp-registry-private"},
}
INPUTS = {
    "application:azubiorga.crypto_secret": {"mode": "manual", "value": "image-fixed-crypto-private  "},
    "application:azubiorga.crypto_salt": {"mode": "manual", "value": "0123456789ABCDEF"},
    "provider:postgresql.postgres_password": {"mode": "generate"},
}
ROOT = "semaphore/tenants/new-a"
PATHS = [ROOT + "/azubiorga", ROOT + "/providers/postgresql-v1"]
CREATED_TIME = "2026-10-16T10:00:00.123456789Z"


def seed_job(client, headers, *, types=None, datasets=None, apps=None):
    source_id = seed_source()
    response = client.put("/api/admin/vault", headers=headers, json=CONFIG)
    assert response.status_code == 200, response.text
    with SessionLocal() as db:
        source = db.get(ProjectTemplate, uuid.UUID(source_id))
        backup = copy.deepcopy(source.backup_document)
        backup["environments"].append({"name": "Vault-Access", "json": json.dumps({
            "vault_url": "https://old-vault.example", "vault_program_secret_paths": {"azubiorga": "foreign/path"},
            "vault_approle_role_id": "source-reader-private"}), "env": "{}"})
        backup["templates"][0]["environments"].append("Vault-Access")
        options = {"application_id": ["azubiorga", "wordpress"], "database_type": ["postgresql", "mariadb", "mysql"],
            "dataset_id": ["none", "public-v1", "smoke-v1", "mysql-smoke-v1", "mariadb-smoke-v1"]}
        backup["templates"][0]["survey_vars"].extend([
            {"name": name, "type": "enum", "values": [{"value": value} for value in values]} for name, values in options.items()])
        source.backup_document = backup
        db.commit()
    job = client.post("/api/admin/creation-jobs", headers=headers, json={
        "idempotency_key": "vault-creation-key-1234", "project_template_id": source_id}).json()
    draft = {"project_name": "Vault Tenant", "display_name": "Vault Tenant", "tenant_slug": "new-a", "runtime_scope_id": "new-scope",
        "application_ids": apps or ["azubiorga"], "database_types": types or ["postgresql"], "dataset_ids": datasets or ["none"],
        "task_template_names": ["deploy"], "environment_names": ["Semaphore-Defaults", "Vault-Access"], "provision_vault": True}
    response = client.put(f"/api/admin/creation-jobs/{job['id']}", headers=headers, json={"draft_data": draft})
    assert response.status_code == 200, response.text
    return job["id"]


def setup_vault(mock, objects=None):
    objects = {} if objects is None else objects
    calls = []
    mock.post("https://vault.example/v1/auth/porter/login").respond(200, json={"auth": {"client_token": "vault-token-private"}})

    def metadata(request):
        path = request.url.path.split("/metadata/", 1)[1]
        calls.append(("metadata", path))
        assert request.headers["X-Vault-Namespace"] == "company"
        assert request.headers["X-Vault-Token"] == "vault-token-private"
        return httpx.Response(200, json={"data": {"current_version": objects[path].get("version", 1),
            "versions": {"1": {"created_time": objects[path].get("created_time", CREATED_TIME), "deletion_time": objects[path].get("deletion_time", ""), "destroyed": objects[path].get("destroyed", False)}}}}) if path in objects else httpx.Response(404)

    def write(request):
        path = request.url.path.split("/data/", 1)[1]
        calls.append(("write", path))
        body = json.loads(request.content)
        assert body["options"] == {"cas": 0}
        assert path not in objects
        objects[path] = {"values": body["data"], "version": 1}
        return httpx.Response(200, json={"data": {"version": 1, "created_time": CREATED_TIME}})

    mock.get(url__regex=r"https://vault\.example/v1/kv/metadata/.+").mock(side_effect=metadata)
    writes = mock.post(url__regex=r"https://vault\.example/v1/kv/data/.+").mock(side_effect=write)
    return objects, calls, writes


def semaphore(mock):
    mock.get("https://semaphore.example/api/projects").respond(200, json=[])
    restore = mock.post("https://semaphore.example/api/projects/restore").respond(201, json={"id": 77})
    mock.get("https://semaphore.example/api/project/77/environment").respond(200, json=[{"id": 2, "name": "Vault-Access"}])
    mock.get("https://semaphore.example/api/project/77/environment/2").respond(200, json={"id": 2, "name": "Vault-Access", "json": "{}", "env": "{}"})
    access = mock.put("https://semaphore.example/api/project/77/environment/2").respond(204)
    mock.get("https://semaphore.example/api/project/77/templates").respond(200, json=[{"id": 10, "name": "deploy", "survey_vars": []}])
    return restore, access


def validated(client, headers, job_id):
    response = client.post(f"/api/admin/creation-jobs/{job_id}/validate", headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "validated", response.text
    return response.json()


def execute(client, headers, job_id, inputs=INPUTS):
    return client.post(f"/api/admin/creation-jobs/{job_id}/execute", headers=headers,
        json={"confirm_project_creation": True, "vault_inputs": inputs})


def test_configuration_encrypted_redacted_and_admin_only(client, admin_headers):
    result = client.put("/api/admin/vault", headers=admin_headers, json=CONFIG)
    assert result.status_code == 200, result.text
    assert result.json()["credentials_present"]["reader_secret_id"]
    assert "private" not in result.text
    assert "private" not in client.get("/api/admin/vault").text
    with SessionLocal() as db:
        stored = db.get(VaultSettings, 1).encrypted_configuration
        assert b"private" not in stored
        assert json.loads(decrypt_secret(stored))["reader_secret_id"] == CONFIG["reader_secret_id"]
        assert "private" not in json.dumps([row.details for row in db.scalars(select(AuditEvent))])
    update = {**CONFIG, "reader_secret_id": "", "registry_passwords": {"azubiorga": ""}}
    assert client.put("/api/admin/vault", headers=admin_headers, json=update).status_code == 200
    with SessionLocal() as db:
        stored = json.loads(decrypt_secret(db.get(VaultSettings, 1).encrypted_configuration))
        assert stored["reader_secret_id"] == CONFIG["reader_secret_id"]
        assert stored["registry_passwords"] == CONFIG["registry_passwords"]
    login = client.post("/api/auth/login", json={"email": "operator@example.com", "password": "correct-horse-battery"})
    for path in ("/api/admin/vault", "/api/admin/vault/catalog"):
        assert client.get(path).status_code == 403
    assert client.put("/api/admin/vault", headers={"X-CSRF-Token": login.json()["csrf_token"]}, json=CONFIG).status_code == 403


@pytest.mark.parametrize("value", ["../kv", "a//b", "/kv", "kv/", "a?b", "a\\b", "a/%2e%2e/b"])
def test_unsafe_paths_rejected(value):
    with pytest.raises(ValueError):
        safe_path(value)


@pytest.mark.parametrize("value", ["https://user:password@example.com", "file:///tmp/vault", "https://vault.example/v1", "https://vault.example?x=y", "https://vault.example:99999"])
def test_unsafe_urls_rejected(value):
    with pytest.raises(ValueError):
        safe_url(value)


def test_full_create_preflights_all_targets_cas_and_installs_protected_access(client, admin_headers):
    with respx.mock as mock:
        restore, access = semaphore(mock)
        objects, calls, writes = setup_vault(mock)
        job_id = seed_job(client, admin_headers)
        plan = validated(client, admin_headers, job_id)["vault_plan"]
        assert [o["path"] for o in plan["objects"]] == PATHS
        response = execute(client, admin_headers, job_id)
        assert response.status_code == 200, response.text
        assert response.json()["status"] == "completed"
        assert response.json()["vault_progress"]["access_installed"]
        assert calls[:2] == [("metadata", p) for p in PATHS]
        assert writes.call_count == 2 and restore.call_count == 1
        assert objects[PATHS[0]]["values"]["crypto_secret"] == INPUTS["application:azubiorga.crypto_secret"]["value"]
        assert objects[PATHS[0]]["values"]["crypto_salt"] == "0123456789ABCDEF"
        assert objects[PATHS[0]]["values"]["registry_password"] == CONFIG["registry_passwords"]["azubiorga"]
        assert len(objects[PATHS[1]]["values"]["postgres_password"]) == 32
        backup = json.loads(restore.calls[0].request.content)
        assert "private" not in json.dumps(backup)
        group = next(g for g in backup["environments"] if g["name"] == "Vault-Access")
        assert json.loads(group["json"])["vault_tenant_secret_root"] == "semaphore/tenants"
        assert json.loads(group["json"])["vault_namespace"] == "company"
        assert "vault_program_secret_paths" not in json.loads(group["json"])
        assert json.loads(group["env"])["VAULT_NAMESPACE"] == "company"
        protected = json.loads(access.calls[0].request.content)["secrets"]
        assert {(s["name"], s["type"]) for s in protected} == {("vault_approle_role_id", "var"), ("ANSIBLE_HASHI_VAULT_SECRET_ID", "env")}
        assert protected[1]["secret"] == CONFIG["reader_secret_id"]
        assert "private" not in response.text
        assert execute(client, admin_headers, job_id, {}).status_code == 200
        assert writes.call_count == 2 and restore.call_count == 1 and access.call_count == 1
    with SessionLocal() as db:
        assert db.get(CreationJob, uuid.UUID(job_id)).encrypted_vault_payload is None
        assert db.scalar(select(Tenant)).configuration_complete
        assert "private" not in json.dumps([r.details for r in db.scalars(select(AuditEvent))])


@pytest.mark.parametrize("existing", [{}, {"deletion_time": "2026-10-16T10:00:00Z"}, {"destroyed": True}])
def test_existing_last_target_aborts_before_any_write(client, admin_headers, existing):
    with respx.mock as mock:
        restore, _ = semaphore(mock)
        _, _, writes = setup_vault(mock, {PATHS[1]: existing})
        job_id = seed_job(client, admin_headers)
        validated(client, admin_headers, job_id)
        assert execute(client, admin_headers, job_id).status_code == 409
        assert writes.call_count == 0 and restore.call_count == 0


def test_metadata_permission_error_fails_closed_without_echoing_response(client, admin_headers):
    with respx.mock as mock:
        restore, _ = semaphore(mock)
        mock.get("https://vault.example/v1/kv/metadata/" + PATHS[1]).respond(403, json={"errors": ["sensitive-private-input"]})
        _, _, writes = setup_vault(mock)
        job_id = seed_job(client, admin_headers)
        validated(client, admin_headers, job_id)
        result = execute(client, admin_headers, job_id)
        assert result.status_code == 502 and "private" not in result.text
        assert writes.call_count == 0 and restore.call_count == 0


def test_partial_failure_reuses_values_and_preserves_created_objects(client, admin_headers):
    with respx.mock as mock:
        restore, _ = semaphore(mock)
        last = mock.post("https://vault.example/v1/kv/data/" + PATHS[1]).respond(403)
        objects, _, writes = setup_vault(mock, {ROOT + "/unrelated": {}})
        job_id = seed_job(client, admin_headers)
        validated(client, admin_headers, job_id)
        assert execute(client, admin_headers, job_id).status_code == 502
        assert restore.call_count == 0 and PATHS[0] in objects
        values = copy.deepcopy(objects[PATHS[0]])
        with SessionLocal() as db:
            job = db.get(CreationJob, uuid.UUID(job_id))
            ciphertext = job.encrypted_vault_payload
            assert ciphertext and b"private" not in ciphertext
            expected_password = json.loads(decrypt_secret(ciphertext))["objects"][PATHS[1]]["postgres_password"]
        assert client.put(f"/api/admin/creation-jobs/{job_id}", headers=admin_headers, json={"draft_data": {}}).status_code == 409
        last.respond(200, json={"data": {"version": 1, "created_time": CREATED_TIME}})
        result = execute(client, admin_headers, job_id, {})
        assert result.status_code == 200, result.text
        assert json.loads(last.calls[-1].request.content)["data"]["postgres_password"] == expected_password
        assert objects[PATHS[0]] == values and ROOT + "/unrelated" in objects
        assert writes.call_count == 1


def test_timeout_requires_manual_resolution_before_resume(client, admin_headers):
    with respx.mock as mock:
        restore, _ = semaphore(mock)
        objects = {}
        def timed_out(request):
            objects[PATHS[0]] = {"version": 1}
            raise httpx.ReadTimeout("private-do-not-echo", request=request)
        uncertain = mock.post("https://vault.example/v1/kv/data/" + PATHS[0]).mock(side_effect=timed_out)
        _, _, writes = setup_vault(mock, objects)
        job_id = seed_job(client, admin_headers)
        validated(client, admin_headers, job_id)
        assert execute(client, admin_headers, job_id).status_code == 502
        assert execute(client, admin_headers, job_id, {}).status_code == 502
        assert uncertain.call_count == 1 and restore.call_count == 0
        resolution = f"/api/admin/creation-jobs/{job_id}/vault/resolve"
        assert client.post(resolution, headers=admin_headers, json={"path": PATHS[0], "decision": "absent", "confirm_checked_in_vault": True}).status_code == 409
        assert client.post(resolution, headers=admin_headers, json={"path": PATHS[0], "decision": "created_by_this_job", "confirm_checked_in_vault": False}).status_code == 409
        assert client.post(resolution, headers=admin_headers, json={"path": PATHS[0], "decision": "created_by_this_job", "confirm_checked_in_vault": True}).status_code == 200
        result = execute(client, admin_headers, job_id, {})
        assert result.status_code == 200, result.text
        assert uncertain.call_count == 1 and writes.call_count == 1


@pytest.mark.parametrize("field,value", [("application:azubiorga.crypto_salt", "odd"), ("application:azubiorga.crypto_salt", "0123456789ABCDE "), ("provider:postgresql.postgres_password", "short"), ("provider:postgresql.postgres_password", "1234567890\n")])
def test_invalid_secret_contract_never_writes(client, admin_headers, field, value):
    with respx.mock as mock:
        semaphore(mock)
        _, _, writes = setup_vault(mock)
        job_id = seed_job(client, admin_headers)
        validated(client, admin_headers, job_id)
        values = {**INPUTS, field: {"mode": "manual", "value": value}}
        result = execute(client, admin_headers, job_id, values)
        assert result.status_code == 409, result.text
        assert writes.call_count == 0 and value not in result.json()["detail"]


@pytest.mark.parametrize("apps,types,datasets", [(["azubiorga"], ["mysql"], ["none"]), (["wordpress"], ["postgresql"], ["none"]), (["azubiorga"], ["postgresql"], ["mysql-smoke-v1"])])
def test_manifest_compatibility_enforced(client, admin_headers, apps, types, datasets):
    with respx.mock as mock:
        semaphore(mock)
        job_id = seed_job(client, admin_headers, apps=apps, types=types, datasets=datasets)
        response = client.post(f"/api/admin/creation-jobs/{job_id}/validate", headers=admin_headers)
        assert response.status_code == 422


def test_all_supported_profiles_derived_once(client, admin_headers):
    with respx.mock as mock:
        semaphore(mock)
        job_id = seed_job(client, admin_headers, apps=["azubiorga", "wordpress"], types=["postgresql", "mariadb", "mysql"], datasets=["none", "public-v1", "mysql-smoke-v1", "mariadb-smoke-v1"])
        plan = validated(client, admin_headers, job_id)["vault_plan"]
        assert len(plan["objects"]) == 5
        assert len({obj["path"] for obj in plan["objects"]}) == 5


def test_concurrent_execution_lease_blocks_second_request(client, admin_headers):
    with respx.mock as mock:
        restore, _ = semaphore(mock)
        _, _, writes = setup_vault(mock)
        job_id = seed_job(client, admin_headers)
        validated(client, admin_headers, job_id)
        with SessionLocal() as db:
            db.get(CreationJob, uuid.UUID(job_id)).execution_started_at = utcnow()
            db.commit()
        assert execute(client, admin_headers, job_id).status_code == 409
        assert writes.call_count == 0 and restore.call_count == 0


def test_catalog_rejects_unknown_provider_and_unsupported_validators():
    data = load_catalog().model_dump()
    data["applications"]["azubiorga"]["database_types"]["postgresql"] = "wrong-v1"
    with pytest.raises(ValueError):
        Catalog.model_validate(data)


def test_validation_errors_do_not_echo_submitted_values(client, admin_headers):
    response = client.put("/api/admin/vault", headers=admin_headers, json={**CONFIG, "reader_secret_id": {"private": "never-return-this-value"}})
    assert response.status_code == 422
    assert "never-return-this-value" not in response.text


def test_cas_race_never_overwrites_or_restores_project(client, admin_headers):
    with respx.mock as mock:
        restore, _ = semaphore(mock)
        race = mock.post("https://vault.example/v1/kv/data/" + PATHS[1]).respond(400, json={"errors": ["check-and-set parameter did not match"]})
        objects, _, writes = setup_vault(mock)
        job_id = seed_job(client, admin_headers)
        validated(client, admin_headers, job_id)
        result = execute(client, admin_headers, job_id)
        assert result.status_code == 409
        assert writes.call_count == 1 and race.call_count == 1 and restore.call_count == 0
        assert PATHS[0] in objects
        assert json.loads(race.calls[0].request.content)["options"] == {"cas": 0}


def test_recreated_object_is_not_accepted_as_own_progress(client, admin_headers):
    with respx.mock as mock:
        restore, _ = semaphore(mock)
        mock.post("https://vault.example/v1/kv/data/" + PATHS[1]).respond(403)
        objects, _, writes = setup_vault(mock)
        job_id = seed_job(client, admin_headers)
        validated(client, admin_headers, job_id)
        assert execute(client, admin_headers, job_id).status_code == 502
        objects[PATHS[0]]["created_time"] = "2026-10-16T11:00:00Z"
        result = execute(client, admin_headers, job_id, {})
        assert result.status_code == 502
        assert "verändert oder gelöscht" in result.json()["detail"]
        assert writes.call_count == 1 and restore.call_count == 0


def test_reader_install_failure_keeps_job_incomplete_and_retries_existing_secret_ids(client, admin_headers):
    with respx.mock as mock:
        restore, access = semaphore(mock)
        access.respond(500)
        _, _, writes = setup_vault(mock)
        job_id = seed_job(client, admin_headers)
        validated(client, admin_headers, job_id)
        assert execute(client, admin_headers, job_id).status_code == 502
        with SessionLocal() as db:
            assert db.scalar(select(Tenant)) is None
        mock.get("https://semaphore.example/api/project/77/environment/2").respond(200, json={"id": 2, "name": "Vault-Access", "secrets": [
            {"id": 100, "name": "vault_approle_role_id", "type": "var"}, {"id": 101, "name": "ANSIBLE_HASHI_VAULT_SECRET_ID", "type": "env"}]})
        access.respond(204)
        result = execute(client, admin_headers, job_id, {})
        assert result.status_code == 200, result.text
        assert restore.call_count == 1 and writes.call_count == 2
        assert all(s["operation"] == "update" for s in json.loads(access.calls[-1].request.content)["secrets"])


@pytest.mark.parametrize("payload,status", [({"data": None}, 200), ({"data": {"current_version": "1"}}, 200), ({}, 500)])
def test_invalid_metadata_is_not_treated_as_absence(client, admin_headers, payload, status):
    with respx.mock as mock:
        restore, _ = semaphore(mock)
        mock.get("https://vault.example/v1/kv/metadata/" + PATHS[0]).respond(status, json=payload)
        _, _, writes = setup_vault(mock)
        job_id = seed_job(client, admin_headers)
        validated(client, admin_headers, job_id)
        assert execute(client, admin_headers, job_id).status_code == 502
        assert writes.call_count == 0 and restore.call_count == 0


def test_configuration_changes_require_revalidation_before_writing(client, admin_headers):
    with respx.mock as mock:
        semaphore(mock)
        _, _, writes = setup_vault(mock)
        job_id = seed_job(client, admin_headers)
        validated(client, admin_headers, job_id)
        assert client.put("/api/admin/vault", headers=admin_headers, json={**CONFIG, "tenant_root": "semaphore/new-root"}).status_code == 200
        assert execute(client, admin_headers, job_id).status_code == 409
        assert writes.call_count == 0


def test_login_redirect_is_not_followed_and_credentials_are_not_leaked(client, admin_headers):
    client.put("/api/admin/vault", headers=admin_headers, json=CONFIG)
    with respx.mock as mock:
        login = mock.post("https://vault.example/v1/auth/porter/login").respond(307, headers={"Location": "https://foreign.example/login"})
        foreign = mock.post("https://foreign.example/login").respond(200, json={"auth": {"client_token": "token"}})
        result = client.post("/api/admin/vault/test", headers=admin_headers)
        assert result.status_code == 502 and login.call_count == 1 and foreign.call_count == 0
        assert "private" not in result.text


def test_malformed_create_receipt_requires_manual_resolution(client, admin_headers):
    with respx.mock as mock:
        restore, _ = semaphore(mock)
        malformed = mock.post("https://vault.example/v1/kv/data/" + PATHS[0]).respond(200, json={"data": None})
        setup_vault(mock)
        job_id = seed_job(client, admin_headers)
        validated(client, admin_headers, job_id)
        assert execute(client, admin_headers, job_id).status_code == 502
        job = client.get(f"/api/admin/creation-jobs/{job_id}").json()
        assert job["vault_progress"]["objects"][PATHS[0]]["state"] == "uncertain"
        assert malformed.call_count == 1 and restore.call_count == 0


def test_replacing_expired_central_credentials_preserves_pending_values(client, admin_headers):
    with respx.mock as mock:
        semaphore(mock)
        pending = mock.post("https://vault.example/v1/kv/data/" + PATHS[1]).respond(403)
        _, _, writes = setup_vault(mock)
        job_id = seed_job(client, admin_headers)
        validated(client, admin_headers, job_id)
        assert execute(client, admin_headers, job_id).status_code == 502
        expected_values = json.loads(pending.calls[0].request.content)["data"]
        client.put("/api/admin/vault", headers=admin_headers, json={**CONFIG, "writer_secret_id": "replacement-writer-private", "reader_secret_id": "replacement-reader-private"})
        pending.respond(200, json={"data": {"version": 1, "created_time": CREATED_TIME}})
        result = execute(client, admin_headers, job_id, {})
        assert result.status_code == 200, result.text
        assert json.loads(pending.calls[-1].request.content)["data"] == expected_values
        logins = [call for call in mock.calls if call.request.url.path == "/v1/auth/porter/login"]
        assert json.loads(logins[-1].request.content)["secret_id"] == "replacement-writer-private"
        assert writes.call_count == 1
