import copy
import json
import uuid

import httpx
import pytest
import respx
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from sqlalchemy import select

from app.credential_service import inventory_targets, git_target
from app.database import SessionLocal
from app.models import AuditEvent, CredentialSettings, CredentialUse, CreationJob, ProjectTemplate, SemaphoreSettings
from test_creation_jobs import seed_source

PRIVATE = Ed25519PrivateKey.generate().private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.OpenSSH,
                                                   serialization.NoEncryption()).decode()
SECOND_PRIVATE = Ed25519PrivateKey.generate().private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.OpenSSH,
                                                          serialization.NoEncryption()).decode()
CONFIG = {"base_url": "https://vault.example", "kv_mount": "kv", "namespace": "", "auth_mount": "semaphore-ansible",
          "role_id": "profile-reader-role-private", "secret_id": "profile-reader-secret-private"}
PROFILE = {"name": "CAYO Test", "purpose": "host", "login": "deploy", "vault_path": "automation-credentials/ssh/cayo-test",
           "vault_version": 1, "allowed_targets": ["10.0.0.1"], "is_active": True}


def profile(client, headers, **changes):
    response = client.put("/api/admin/credentials/config", headers=headers, json=CONFIG)
    assert response.status_code == 200, response.text
    response = client.post("/api/admin/credentials/profiles", headers=headers, json={**PROFILE, **changes})
    assert response.status_code == 201, response.text
    return response.json()


def vault(mock, private=PRIVATE):
    mock.post("https://vault.example/v1/auth/semaphore-ansible/login").respond(200, json={"auth": {"client_token": "vault-private-token"}})
    def read(request):
        version = int(request.url.params["version"])
        assert request.headers["X-Vault-Token"] == "vault-private-token"
        return httpx.Response(200, json={"data": {"data": {"private_key": private if version == 1 else SECOND_PRIVATE},
                                                 "metadata": {"version": version, "destroyed": False, "deletion_time": ""}}})
    return mock.get(url__regex=r"https://vault\.example/v1/kv/data/automation-credentials/.+").mock(side_effect=read)


def new_job(client, headers, profile_id, *, target="10.0.0.1"):
    source_id = seed_source()
    with SessionLocal() as db:
        source = db.get(ProjectTemplate, uuid.UUID(source_id))
        document = copy.deepcopy(source.backup_document)
        document["inventories"][0].update(type="static", inventory=f"[docker_test]\ncayo ansible_host={target} ansible_user=deploy")
        source.backup_document = document
        db.commit()
    response = client.post("/api/admin/creation-jobs", headers=headers, json={"idempotency_key": str(uuid.uuid4()), "project_template_id": source_id})
    job_id = response.json()["id"]
    response = client.put(f"/api/admin/creation-jobs/{job_id}", headers=headers, json={"draft_data": {
        "project_name": "SSH Tenant", "display_name": "SSH Tenant", "tenant_slug": "ssh-a", "runtime_scope_id": "ssh-scope",
        "task_template_names": ["deploy"], "environment_names": ["Semaphore-Defaults"],
        "ssh_bindings": [{"profile_id": profile_id, "resource_kind": "inventories", "resource_name": "Host"}]}})
    assert response.status_code == 200, response.text
    return job_id


def remote(mock, profile_id):
    key_name = "Semaporter-host-" + uuid.UUID(profile_id).hex
    mock.get("https://semaphore.example/api/projects").respond(200, json=[])
    restore = mock.post("https://semaphore.example/api/projects/restore").respond(201, json={"id": 77})
    key = {"id": 8, "name": key_name, "type": "ssh"}
    mock.get("https://semaphore.example/api/project/77/keys").respond(200, json=[key])
    mock.get("https://semaphore.example/api/project/77/keys/8").respond(200, json=key)
    mock.get("https://semaphore.example/api/project/77/inventory").respond(200, json=[{"id": 3, "name": "Host"}])
    inventory = mock.get("https://semaphore.example/api/project/77/inventory/3").respond(200, json={
        "id": 3, "name": "Host", "type": "static", "inventory": "[docker_test]\ncayo ansible_host=10.0.0.1 ansible_user=deploy", "ssh_key_id": 8})
    mock.get("https://semaphore.example/api/project/77/templates").respond(200, json=[])
    write = mock.put("https://semaphore.example/api/project/77/keys/8").respond(204)
    return restore, write, inventory


def validate(client, headers, job_id):
    return client.post(f"/api/admin/creation-jobs/{job_id}/validate", headers=headers)


def execute(client, headers, job_id):
    return client.post(f"/api/admin/creation-jobs/{job_id}/execute", headers=headers, json={"confirm_project_creation": True})


def test_connection_secrets_encrypted_never_returned_or_audited(client, admin_headers):
    profile(client, admin_headers)
    response = client.get("/api/admin/credentials/config")
    assert response.json()["secret_id_present"]
    assert "private" not in response.text
    with SessionLocal() as db:
        stored = db.get(CredentialSettings, 1).encrypted_configuration
        assert b"private" not in stored
        assert "private" not in json.dumps([row.details for row in db.scalars(select(AuditEvent))])
    assert client.put("/api/admin/credentials/config", headers=admin_headers, json={**CONFIG, "role_id": "", "secret_id": ""}).status_code == 200


@pytest.mark.parametrize("method,path", [("get", "/config"), ("get", "/profiles"), ("get", "/uses"), ("post", "/test")])
def test_profiles_require_system_admin(client, operator_headers, method, path):
    assert getattr(client, method)("/api/admin/credentials" + path, headers=operator_headers).status_code == 403


def test_profile_test_shows_only_public_key_and_read_permission_suffices(client, admin_headers):
    item = profile(client, admin_headers)
    with respx.mock as mock:
        read = vault(mock)
        response = client.post(f"/api/admin/credentials/profiles/{item['id']}/test", headers=admin_headers)
        assert response.status_code == 200, response.text
        assert response.json()["public_key"].startswith("ssh-ed25519 ")
        assert response.json()["fingerprint"].startswith("SHA256:")
        assert PRIVATE not in response.text and "private_key" not in response.text
        assert read.call_count == 1
        assert all(call.request.method == "GET" or call.request.url.path.endswith("/login") for call in mock.calls)


def test_creation_installs_shared_key_without_persisting_material(client, admin_headers):
    item = profile(client, admin_headers)
    job_id = new_job(client, admin_headers, item["id"])
    with respx.mock as mock:
        vault(mock)
        restore, write, _ = remote(mock, item["id"])
        response = validate(client, admin_headers, job_id)
        assert response.status_code == 200, response.text
        assert PRIVATE not in response.text
        assert response.json()["credential_plan"][0]["profile"]["vault_version"] == 1
        response = execute(client, admin_headers, job_id)
        assert response.status_code == 200 and response.json()["status"] == "completed", response.text
        assert PRIVATE not in response.text
        sent = json.loads(write.calls[0].request.content)
        assert sent["ssh"]["private_key"] == PRIVATE and sent["ssh"]["login"] == "deploy"
        assert sent["override_secret"] and sent["id"] == 8
        backup = json.loads(restore.calls[0].request.content)
        assert PRIVATE not in json.dumps(backup)
        assert backup["inventories"][0]["ssh_key"].startswith("Semaporter-host-")
        assert execute(client, admin_headers, job_id).status_code == 200
        assert restore.call_count == write.call_count == 1
    with SessionLocal() as db:
        job = db.get(CreationJob, uuid.UUID(job_id))
        assert "PRIVATE KEY" not in json.dumps([job.draft_data, job.prepared_backup, job.credential_plan, job.credential_progress])
        use = db.scalar(select(CredentialUse))
        assert use.status == "installed" and use.vault_version == 1
        assert "PRIVATE KEY" not in json.dumps([row.details for row in db.scalars(select(AuditEvent))])


def test_unapproved_host_fails_before_project_restore(client, admin_headers):
    item = profile(client, admin_headers)
    job_id = new_job(client, admin_headers, item["id"], target="10.0.0.99")
    with respx.mock as mock:
        vault(mock)
        response = validate(client, admin_headers, job_id)
        assert response.status_code == 422 and "nicht freigegebenes Ziel" in response.text
        assert not any("semaphore.example" in str(call.request.url) for call in mock.calls)


def test_profile_change_requires_revalidation_and_no_remote_write(client, admin_headers):
    item = profile(client, admin_headers)
    job_id = new_job(client, admin_headers, item["id"])
    with respx.mock as mock:
        vault(mock)
        restore, _, _ = remote(mock, item["id"])
        assert validate(client, admin_headers, job_id).status_code == 200
        changed = client.put(f"/api/admin/credentials/profiles/{item['id']}", headers=admin_headers,
                             json={**PROFILE, "vault_version": 2, "revision": item["revision"]})
        assert changed.status_code == 200
        response = execute(client, admin_headers, job_id)
        assert response.status_code == 409 and "erneut validieren" in response.text
        assert restore.call_count == 0


def test_failed_key_put_resumes_same_project_key_and_pinned_version(client, admin_headers):
    item = profile(client, admin_headers)
    job_id = new_job(client, admin_headers, item["id"])
    with respx.mock as mock:
        read = vault(mock)
        restore, write, _ = remote(mock, item["id"])
        assert validate(client, admin_headers, job_id).status_code == 200
        write.mock(side_effect=httpx.ReadTimeout("uncertain"))
        assert execute(client, admin_headers, job_id).status_code == 502
        assert client.put(f"/api/admin/creation-jobs/{job_id}", headers=admin_headers, json={"draft_data": {}}).status_code == 409
        assert client.post(f"/api/admin/creation-jobs/{job_id}/validate", headers=admin_headers).status_code == 409
        assert client.put(f"/api/admin/credentials/profiles/{item['id']}", headers=admin_headers,
                          json={**PROFILE, "vault_version": 2, "revision": item["revision"]}).status_code == 200
        write.respond(204)
        assert execute(client, admin_headers, job_id).status_code == 200
        assert restore.call_count == 1 and write.call_count == 2
        assert all(call.request.url.params["version"] == "1" for call in read.calls)
        uses = client.get("/api/admin/credentials/uses").json()
        assert len(uses) == 1 and uses[0]["vault_version"] == 1


def test_rotation_requires_confirmation_and_preserves_key_identity(client, admin_headers):
    item = profile(client, admin_headers)
    job_id = new_job(client, admin_headers, item["id"])
    with respx.mock as mock:
        vault(mock)
        _, write, inventory = remote(mock, item["id"])
        assert validate(client, admin_headers, job_id).status_code == 200
        assert execute(client, admin_headers, job_id).status_code == 200
        use = client.get("/api/admin/credentials/uses").json()[0]
        changed = client.put(f"/api/admin/credentials/profiles/{item['id']}", headers=admin_headers,
                             json={**PROFILE, "vault_version": 2, "revision": item["revision"]}).json()
        data = {"confirm": False, "expected_version": 1, "desired_version": 2, "profile_revision": changed["revision"]}
        assert client.post(f"/api/admin/credentials/uses/{use['id']}/sync", headers=admin_headers, json=data).status_code == 409
        response = client.post(f"/api/admin/credentials/uses/{use['id']}/sync", headers=admin_headers, json={**data, "confirm": True})
        assert response.status_code == 200 and response.json()["vault_version"] == 2, response.text
        assert json.loads(write.calls[-1].request.content)["ssh"]["private_key"] == SECOND_PRIVATE
        assert write.call_count == 2
        inventory.respond(200, json={"id": 3, "ssh_key_id": 99, "inventory": "10.0.0.1"})
        response = client.post(f"/api/admin/credentials/uses/{use['id']}/sync", headers=admin_headers,
                               json={**data, "confirm": True, "expected_version": 2})
        assert response.status_code == 502 and write.call_count == 2


@pytest.mark.parametrize("values", [
    {"vault_path": "semaphore/tenants/other/azubiorga"},
    {"vault_path": "automation-credentials/../other"},
    {"allowed_targets": ["*.example.com"]},
    {"purpose": "git", "allowed_targets": ["https://git.example/repo.git"]},
])
def test_profile_rejects_ambiguous_targets_and_paths(client, admin_headers, values):
    assert client.post("/api/admin/credentials/profiles", headers=admin_headers, json={**PROFILE, **values}).status_code == 422


def test_invalid_key_never_returned_or_sent(client, admin_headers):
    item = profile(client, admin_headers)
    with respx.mock as mock:
        vault(mock, private="private-material-must-not-echo")
        response = client.post(f"/api/admin/credentials/profiles/{item['id']}/test", headers=admin_headers)
        assert response.status_code == 502 and "private-material-must-not-echo" not in response.text


def test_inventory_parsing_checks_effective_hosts_users_and_dynamic_values():
    assert inventory_targets({"inventory": "[test]\nalias ansible_host=10.0.0.1 ansible_user=deploy"}, "deploy") == ["10.0.0.1"]
    assert inventory_targets({"inventory": "all:\n  hosts:\n    alias:\n      ansible_host: 10.0.0.1"}, "deploy") == ["10.0.0.1"]
    for raw in ("host[1:9]", "host ansible_user=root", "{{ target }}", "all:\n  vars:\n    ansible_host: elsewhere\n  hosts:\n    host: {}"):
        with pytest.raises(ValueError):
            inventory_targets({"inventory": raw}, "deploy")
    assert git_target("git@git.example:group/repo.git", "git") == git_target("ssh://git@git.example/group/repo.git", "git")


@pytest.mark.parametrize("extra_resource", [False, True])
def test_copy_from_managed_project_reuses_placeholder_but_requires_all_references_to_be_bound(client, admin_headers, extra_resource):
    item = profile(client, admin_headers)
    job_id = new_job(client, admin_headers, item["id"])
    with SessionLocal() as db:
        job = db.get(CreationJob, uuid.UUID(job_id))
        source = db.get(ProjectTemplate, job.project_template_id)
        document = copy.deepcopy(source.backup_document)
        name = "Semaporter-host-" + uuid.UUID(item["id"]).hex
        document["keys"] = [{"name": name, "type": "ssh"}]
        document["inventories"][0]["ssh_key"] = name
        if extra_resource:
            document["inventories"].append({"name": "Other", "type": "static", "inventory": "10.0.0.99", "ssh_key": name})
        source.backup_document = document
        db.commit()
    with respx.mock as mock:
        vault(mock)
        mock.get("https://semaphore.example/api/projects").respond(200, json=[])
        response = validate(client, admin_headers, job_id)
        assert response.status_code == (422 if extra_resource else 200), response.text
        if not extra_resource:
            with SessionLocal() as db:
                job = db.get(CreationJob, uuid.UUID(job_id))
                assert len([key for key in job.prepared_backup["keys"] if key["name"] == name]) == 1


def test_host_and_git_credentials_use_distinct_restored_keys_and_resource_ids(client, admin_headers):
    host_profile = profile(client, admin_headers)
    git_profile = profile(client, admin_headers, name="Git Lesen", purpose="git", login="git",
                          vault_path="automation-credentials/git/stack-read", allowed_targets=["git@git.example:group/stack.git"])
    job_id = new_job(client, admin_headers, host_profile["id"])
    with SessionLocal() as db:
        job = db.get(CreationJob, uuid.UUID(job_id))
        source = db.get(ProjectTemplate, job.project_template_id)
        document = copy.deepcopy(source.backup_document)
        document["repositories"][0]["git_url"] = "git@git.example:group/stack.git"
        source.backup_document = document
        draft = copy.deepcopy(job.draft_data)
        db.commit()
    draft["ssh_bindings"].append({"profile_id": git_profile["id"], "resource_kind": "repositories", "resource_name": "Git"})
    assert client.put(f"/api/admin/creation-jobs/{job_id}", headers=admin_headers, json={"draft_data": draft}).status_code == 200
    with respx.mock as mock:
        vault(mock)
        _, host_write, _ = remote(mock, host_profile["id"])
        git_name = "Semaporter-git-" + uuid.UUID(git_profile["id"]).hex
        mock.get("https://semaphore.example/api/project/77/keys").respond(200, json=[
            {"id": 8, "name": "Semaporter-host-" + uuid.UUID(host_profile["id"]).hex, "type": "ssh"},
            {"id": 9, "name": git_name, "type": "ssh"}])
        mock.get("https://semaphore.example/api/project/77/repositories").respond(200, json=[{"id": 4, "name": "Git"}])
        mock.get("https://semaphore.example/api/project/77/repositories/4").respond(200, json={
            "id": 4, "name": "Git", "git_url": "ssh://git@git.example/group/stack.git", "ssh_key_id": 9})
        git_write = mock.put("https://semaphore.example/api/project/77/keys/9").respond(204)
        assert validate(client, admin_headers, job_id).status_code == 200
        response = execute(client, admin_headers, job_id)
        assert response.status_code == 200, response.text
        assert json.loads(host_write.calls[0].request.content)["ssh"]["login"] == "deploy"
        assert json.loads(git_write.calls[0].request.content)["ssh"]["login"] == "git"
        assert len(client.get("/api/admin/credentials/uses").json()) == 2


def test_blocking_profile_stops_creation_before_restore(client, admin_headers):
    item = profile(client, admin_headers)
    job_id = new_job(client, admin_headers, item["id"])
    with respx.mock as mock:
        vault(mock)
        restore, _, _ = remote(mock, item["id"])
        assert validate(client, admin_headers, job_id).status_code == 200
        assert client.put(f"/api/admin/credentials/profiles/{item['id']}", headers=admin_headers,
                          json={**PROFILE, "is_active": False, "revision": item["revision"]}).status_code == 200
        response = execute(client, admin_headers, job_id)
        assert response.status_code == 409 and "gesperrt" in response.text
        assert restore.call_count == 0


def test_started_job_locks_profile_identity_and_connection_even_before_first_key_write(client, admin_headers):
    item = profile(client, admin_headers)
    job_id = new_job(client, admin_headers, item["id"])
    with respx.mock as mock:
        vault(mock)
        restore, _, _ = remote(mock, item["id"])
        assert validate(client, admin_headers, job_id).status_code == 200
        restore.mock(side_effect=httpx.ReadTimeout("outcome uncertain"))
        assert execute(client, admin_headers, job_id).status_code == 502
        assert not client.get("/api/admin/credentials/uses").json()
        changed = client.put(f"/api/admin/credentials/profiles/{item['id']}", headers=admin_headers,
                             json={**PROFILE, "login": "other", "revision": item["revision"]})
        assert changed.status_code == 409
        assert client.put("/api/admin/credentials/config", headers=admin_headers,
                          json={**CONFIG, "base_url": "https://other-vault.example"}).status_code == 422


def test_rotation_does_not_send_key_to_another_semaphore_instance(client, admin_headers):
    item = profile(client, admin_headers)
    job_id = new_job(client, admin_headers, item["id"])
    with respx.mock as mock:
        vault(mock)
        _, write, _ = remote(mock, item["id"])
        assert validate(client, admin_headers, job_id).status_code == 200
        assert execute(client, admin_headers, job_id).status_code == 200
        use = client.get("/api/admin/credentials/uses").json()[0]
        with SessionLocal() as db:
            db.get(SemaphoreSettings, 1).base_url = "https://other-semaphore.example"
            db.commit()
        response = client.post(f"/api/admin/credentials/uses/{use['id']}/sync", headers=admin_headers, json={
            "confirm": True, "expected_version": 1, "desired_version": 1, "profile_revision": item["revision"]})
        assert response.status_code == 409 and write.call_count == 1
        assert all("other-semaphore" not in str(call.request.url) for call in mock.calls)


def test_tenant_vault_preflight_failure_before_writes_allows_revalidation(client, admin_headers):
    from test_vault import CONFIG as TENANT_VAULT_CONFIG
    item = profile(client, admin_headers)
    job_id = new_job(client, admin_headers, item["id"])
    assert client.put("/api/admin/vault", headers=admin_headers, json=TENANT_VAULT_CONFIG).status_code == 200
    with SessionLocal() as db:
        job = db.get(CreationJob, uuid.UUID(job_id))
        source = db.get(ProjectTemplate, job.project_template_id)
        document = copy.deepcopy(source.backup_document)
        for name, value in (("application_id", "azubiorga"), ("database_type", "postgresql"), ("dataset_id", "none")):
            document["templates"][0]["survey_vars"].append({"name": name, "type": "enum", "values": [{"value": value}]})
        source.backup_document = document
        draft = {**job.draft_data, "provision_vault": True, "application_ids": ["azubiorga"],
                 "database_types": ["postgresql"], "dataset_ids": ["none"]}
        db.commit()
    assert client.put(f"/api/admin/creation-jobs/{job_id}", headers=admin_headers, json={"draft_data": draft}).status_code == 200
    with respx.mock as mock:
        vault(mock)
        restore, _, _ = remote(mock, item["id"])
        assert validate(client, admin_headers, job_id).status_code == 200
        changed = {**TENANT_VAULT_CONFIG, "registry_passwords": {"azubiorga": "changed-private-registry-password"}}
        assert client.put("/api/admin/vault", headers=admin_headers, json=changed).status_code == 200
        assert execute(client, admin_headers, job_id).status_code == 409
        assert restore.call_count == 0
        assert client.get(f"/api/admin/creation-jobs/{job_id}").json()["credential_progress"] is None
        assert validate(client, admin_headers, job_id).status_code == 200
