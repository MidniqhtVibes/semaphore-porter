import json

import respx
from sqlalchemy import select

from app.database import SessionLocal
from app.models import SemaphoreSettings, User
from app.security import encrypt_secret
from app.routers.projects import revision

ROOT = "https://semaphore.example/api"


def seed_connection():
    with SessionLocal() as db:
        db.add(SemaphoreSettings(id=1, base_url="https://semaphore.example", encrypted_token=encrypt_secret("test-token")))
        db.commit()


def test_live_project_crud_requires_admin_and_exact_confirmation(client, admin_headers):
    seed_connection()
    remote = {"id": 7, "name": "Kunde A", "alert": False, "max_parallel_tasks": 0}
    with respx.mock as mock:
        mock.get(f"{ROOT}/project/7").respond(200, json=remote)
        delete = mock.delete(f"{ROOT}/project/7").respond(204)
        response = client.request("DELETE", "/api/admin/semaphore/projects/7", headers=admin_headers, json={"revision": revision(remote), "confirm_name": "wrong"})
        assert response.status_code == 400
        assert not delete.called
        response = client.request("DELETE", "/api/admin/semaphore/projects/7", headers=admin_headers, json={"revision": revision(remote), "confirm_name": "Kunde A"})
        assert response.status_code == 200
        assert delete.call_count == 1


def test_non_admin_cannot_manage_remote_projects(client, operator_headers):
    response = client.post("/api/admin/semaphore/projects", headers=operator_headers, json={"name": "No"})
    assert response.status_code == 403


def test_environment_redacts_and_preserves_existing_private_values(client, admin_headers):
    seed_connection()
    original = {"id": 3, "project_id": 7, "name": "Vault-Access", "json": '{"vault_url":"https://vault.example","vault_approle_role_id":"private-role"}', "env": "{}", "secrets": [{"id": 8, "name": "ANSIBLE_HASHI_VAULT_SECRET_ID", "type": "env", "secret": "never-return"}]}
    with respx.mock as mock:
        mock.get(f"{ROOT}/project/7/environment", params={"sort": "name", "order": "asc"}).respond(200, json=[original])
        mock.get(f"{ROOT}/project/7/environment/3").respond(200, json=original)
        put = mock.put(f"{ROOT}/project/7/environment/3").respond(204)
        response = client.get("/api/admin/semaphore/projects/7/resources/environment")
        assert "private-role" not in response.text and "never-return" not in response.text
        item = response.json()[0]
        item["values"]["json"]["vault_url"] = "https://new.example"
        response = client.put("/api/admin/semaphore/projects/7/resources/environment/3", headers=admin_headers, json={"revision": item["revision"], "values": item["values"]})
        assert response.status_code == 200, response.text
        payload = json.loads(put.calls[0].request.content)
        assert json.loads(payload["json"])["vault_approle_role_id"] == "private-role"
        assert "secrets" not in payload


def test_stale_environment_does_not_write(client, admin_headers):
    seed_connection()
    with respx.mock as mock:
        mock.get(f"{ROOT}/project/7/environment/3").respond(200, json={"id": 3, "name": "Semaphore-Defaults", "json": "{}"})
        put = mock.put(f"{ROOT}/project/7/environment/3").respond(204)
        response = client.put("/api/admin/semaphore/projects/7/resources/environment/3", headers=admin_headers, json={"revision": "stale", "values": {"name": "Semaphore-Defaults", "json": {"tenant_slug": "new-a", "runtime_scope_id": "scope-a"}}})
        assert response.status_code == 409
        assert not put.called


def test_identity_only_allowed_in_defaults(client, admin_headers):
    seed_connection()
    with respx.mock as mock:
        route = mock.post(f"{ROOT}/project/7/environment").respond(201, json={"id": 3})
        response = client.post("/api/admin/semaphore/projects/7/resources/environment", headers=admin_headers, json={"values": {"name": "Other", "json": {"tenant_slug": "new-a"}, "env": {}}})
        assert response.status_code == 422
        assert not route.called


def test_password_change_is_enforced_by_api(client, admin_headers):
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == "admin@example.com"))
        user.must_change_password = True
        db.commit()
    assert client.get("/api/admin/dashboard").status_code == 403
    assert client.get("/api/auth/me").status_code == 200


def test_password_reset_revokes_sessions(client, admin_headers):
    with SessionLocal() as db:
        user_id = str(db.scalar(select(User.id).where(User.email == "admin@example.com")))
    response = client.post(f"/api/admin/users/{user_id}/reset-password", headers=admin_headers, json={"password": "replacement-password"})
    assert response.status_code == 200
    assert client.get("/api/auth/me").status_code == 401


def test_defaults_save_sends_both_identifiers_and_vault_paths(client, admin_headers):
    seed_connection()
    with respx.mock as mock:
        mock.get(f"{ROOT}/project/7/environment", params={"sort": "name", "order": "asc"}).respond(200, json=[])
        route = mock.post(f"{ROOT}/project/7/environment").respond(201, json={"id": 3})
        response = client.post("/api/admin/semaphore/projects/7/resources/environment", headers=admin_headers, json={"values": {"name": "Semaphore-Defaults", "json": {"tenant_slug": "new-a", "runtime_scope_id": "new-scope", "vault_tenant_secret_root": "semaphore/tenants"}, "env": {}}})
        assert response.status_code == 201, response.text
        variables = json.loads(json.loads(route.calls[0].request.content)["json"])
        assert variables == {"tenant_slug": "new-a", "runtime_scope_id": "new-scope", "vault_tenant_secret_root": "semaphore/tenants"}


def test_ssh_key_is_written_without_appearing_in_audit(client, admin_headers):
    from app.models import AuditEvent
    seed_connection()
    with respx.mock as mock:
        route = mock.post(f"{ROOT}/project/7/keys").respond(201, json={"id": 5})
        response = client.post("/api/admin/semaphore/projects/7/resources/keys", headers=admin_headers, json={"values": {"name": "SSH", "type": "ssh"}, "key_secret": "private-test-key", "key_login": "deploy", "key_passphrase": "test-passphrase"})
        assert response.status_code == 201, response.text
        assert json.loads(route.calls[0].request.content)["ssh"]["private_key"] == "private-test-key"
        assert "private-test-key" not in response.text
    with SessionLocal() as db:
        assert "private-test-key" not in str([x.details for x in db.scalars(select(AuditEvent))])


def test_live_template_change_disables_previous_portal_policy(client, admin_headers):
    from test_task_authorization import seed_task
    from app.models import TaskTemplate
    _, task_id = seed_task()
    current = {"id": 12, "project_id": 7, "name": "deploy-timed-demo", "survey_vars": []}
    with respx.mock as mock:
        mock.get(f"{ROOT}/project/7/templates/12").respond(200, json=current)
        mock.put(f"{ROOT}/project/7/templates/12").respond(204)
        response = client.put("/api/admin/semaphore/projects/7/resources/templates/12", headers=admin_headers, json={"revision": revision(current), "values": {"name": "Updated", "survey_vars": [{"name": "ttl_minutes", "type": "int"}]}})
        assert response.status_code == 200, response.text
    with SessionLocal() as db:
        import uuid
        task = db.get(TaskTemplate, uuid.UUID(task_id))
        assert task.name == "Updated" and not task.is_enabled and not task.policy.is_active
