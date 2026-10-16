import json

import httpx
import respx
from sqlalchemy import select

from app.database import SessionLocal
from app.models import ProjectTemplate, SemaphoreSettings, Tenant, User
from app.security import encrypt_secret


def seed_source():
    with SessionLocal() as db:
        source = ProjectTemplate(name="Source", source_type="upload", backup_document={
            "meta": {"name": "Source"},
            "environments": [{"name": "Semaphore-Defaults", "json": '{"tenant_slug":"source-a","runtime_scope_id":"source-scope"}', "env": "{}"}],
            "templates": [{"name": "deploy", "repository": "Git", "inventory": "Host", "environments": ["Semaphore-Defaults"], "survey_vars": [{"name": "tenant_slug"}, {"name": "runtime_scope_id"}, {"name": "ttl_minutes", "type": "int"}]}],
            "repositories": [{"name": "Git", "git_url": "https://git.example/repo", "git_branch": "main"}],
            "inventories": [{"name": "Host", "type": "static", "inventory": "[docker_test]"}], "keys": [],
        })
        db.add(source)
        db.add(SemaphoreSettings(id=1, base_url="https://semaphore.example", encrypted_token=encrypt_secret("token")))
        db.commit()
        return str(source.id)


def make_validated(client, headers, source):
    response = client.post("/api/admin/creation-jobs", headers=headers, json={"idempotency_key": "stable-creation-key-123", "project_template_id": source})
    assert response.status_code == 201
    job_id = response.json()["id"]
    response = client.put(f"/api/admin/creation-jobs/{job_id}", headers=headers, json={"draft_data": {"project_name": "New Tenant", "display_name": "New Tenant", "tenant_slug": "new-a", "runtime_scope_id": "new-scope", "task_template_names": ["deploy"], "environment_names": ["Semaphore-Defaults"]}})
    assert response.status_code == 200, response.text
    response = client.post(f"/api/admin/creation-jobs/{job_id}/validate", headers=headers)
    assert response.status_code == 200 and response.json()["status"] == "validated", response.text
    return job_id


def test_full_restore_uses_defaults_and_is_idempotent(client, admin_headers):
    source = seed_source()
    with respx.mock as mock:
        mock.get("https://semaphore.example/api/projects").respond(200, json=[])
        restore = mock.post("https://semaphore.example/api/projects/restore").respond(201, json={"id": 77})
        mock.get("https://semaphore.example/api/project/77/templates", params={"sort": "name", "order": "asc"}).respond(200, json=[{"id": 10, "name": "deploy", "survey_vars": [{"name": "ttl_minutes", "type": "int"}]}])
        job_id = make_validated(client, admin_headers, source)
        for _ in range(2):
            response = client.post(f"/api/admin/creation-jobs/{job_id}/execute", headers=admin_headers, json={"confirm_project_creation": True})
            assert response.status_code == 200, response.text
            assert response.json()["status"] == "completed"
        assert restore.call_count == 1
        backup = json.loads(restore.calls[0].request.content)
        assert json.loads(backup["environments"][0]["json"])["runtime_scope_id"] == "new-scope"
        assert {x["name"] for x in backup["templates"][0]["survey_vars"]} == {"ttl_minutes"}
    with SessionLocal() as db:
        assert len(list(db.scalars(select(Tenant)))) == 1
    assert client.post(f"/api/admin/creation-jobs/{job_id}/validate", headers=admin_headers).status_code == 409


def test_uncertain_restore_recovers_without_second_post(client, admin_headers):
    source = seed_source()
    with respx.mock as mock:
        projects = mock.get("https://semaphore.example/api/projects").respond(200, json=[])
        restore = mock.post("https://semaphore.example/api/projects/restore").mock(side_effect=httpx.ReadTimeout("timeout"))
        job_id = make_validated(client, admin_headers, source)
        response = client.post(f"/api/admin/creation-jobs/{job_id}/execute", headers=admin_headers, json={"confirm_project_creation": True})
        assert response.status_code == 502
        assert client.get(f"/api/admin/creation-jobs/{job_id}").json()["status"] == "verification_required"
        projects.respond(200, json=[{"id": 77, "name": "New Tenant"}])
        mock.get("https://semaphore.example/api/project/77/templates", params={"sort": "name", "order": "asc"}).respond(200, json=[])
        response = client.post(f"/api/admin/creation-jobs/{job_id}/execute", headers=admin_headers, json={"confirm_project_creation": True})
        assert response.status_code == 200 and response.json()["status"] == "completed", response.text
        assert restore.call_count == 1


def test_copy_rejects_source_identity(client, admin_headers):
    source = seed_source()
    with respx.mock as mock:
        mock.get("https://semaphore.example/api/projects").respond(200, json=[])
        job = client.post("/api/admin/creation-jobs", headers=admin_headers, json={"idempotency_key": "another-stable-key-123", "project_template_id": source}).json()
        client.put(f"/api/admin/creation-jobs/{job['id']}", headers=admin_headers, json={"draft_data": {"project_name": "New", "tenant_slug": "source-a", "runtime_scope_id": "source-scope", "task_template_names": ["deploy"], "environment_names": ["Semaphore-Defaults"]}})
        response = client.post(f"/api/admin/creation-jobs/{job['id']}/validate", headers=admin_headers)
        assert len(response.json()["validation_result"]["errors"]) == 2


def test_multiple_choices_reach_tenant_policy_and_task_start(client, admin_headers):
    source_id = seed_source()
    choices = {"application_id": ["azubiorga", "wordpress", "other"], "database_type": ["postgresql", "mariadb", "mysql"], "dataset_id": ["none", "smoke-v1", "private-data"]}
    surveys = [{"name": name, "type": "enum", "values": [{"value": value} for value in values]} for name, values in choices.items()]
    with SessionLocal() as db:
        import uuid
        source = db.get(ProjectTemplate, uuid.UUID(source_id))
        source.backup_document = {**source.backup_document, "templates": [{**source.backup_document["templates"][0], "survey_vars": surveys}]}
        operator_id = str(db.scalar(select(User).where(User.email == "operator@example.com")).id)
        db.commit()
    with respx.mock as mock:
        mock.get("https://semaphore.example/api/projects").respond(200, json=[])
        restore = mock.post("https://semaphore.example/api/projects/restore").respond(201, json={"id": 77})
        # Even if a remote response returns the full catalog, policies remain restricted.
        mock.get("https://semaphore.example/api/project/77/templates").respond(200, json=[{"id": 10, "name": "deploy", "survey_vars": surveys}])
        start = mock.post("https://semaphore.example/api/project/77/tasks").respond(201, json={"id": 100, "status": "waiting"})
        job = client.post("/api/admin/creation-jobs", headers=admin_headers, json={"idempotency_key": "multiple-choices-creation", "project_template_id": source_id}).json()
        draft = {"project_name": "Multi Tenant", "display_name": "Multi Tenant", "tenant_slug": "multi-a", "runtime_scope_id": "multi-scope", "application_ids": ["wordpress", "azubiorga"], "database_types": ["mariadb", "postgresql"], "dataset_ids": ["smoke-v1", "none"], "wizard_step": 6, "task_template_names": ["deploy"], "environment_names": ["Semaphore-Defaults"], "access_assignments": [{"user_id": operator_id, "role_code": "operator"}], "activate_after_creation": True}
        response = client.put(f"/api/admin/creation-jobs/{job['id']}", headers=admin_headers, json={"draft_data": draft})
        assert response.status_code == 200, response.text
        assert response.json()["draft_data"]["wizard_step"] == 6
        validated = client.post(f"/api/admin/creation-jobs/{job['id']}/validate", headers=admin_headers)
        assert validated.json()["status"] == "validated", validated.text
        response = client.post(f"/api/admin/creation-jobs/{job['id']}/execute", headers=admin_headers, json={"confirm_project_creation": True})
        assert response.status_code == 200, response.text
        tenant_id = response.json()["tenant_id"]
        tenant = client.get(f"/api/admin/tenants/{tenant_id}").json()
        assert tenant["application_ids"] == ["wordpress", "azubiorga"]
        assert tenant["database_types"] == ["mariadb", "postgresql"]
        assert tenant["dataset_ids"] == ["smoke-v1", "none"]
        task_id = tenant["task_templates"][0]["id"]
        assert restore.call_count == 1
        login = client.post("/api/auth/login", json={"email": "operator@example.com", "password": "correct-horse-battery"})
        headers = {"X-CSRF-Token": login.json()["csrf_token"]}
        form = client.get(f"/api/portal/tenants/{tenant_id}/tasks/{task_id}/form").json()
        fields = {field["name"]: field for field in form["fields"]}
        assert fields["application_id"]["allowed_values"] == ["wordpress", "azubiorga"]
        assert fields["database_type"]["allowed_values"] == ["mariadb", "postgresql"]
        path = f"/api/portal/tenants/{tenant_id}/tasks/{task_id}/runs"
        assert client.post(path, headers=headers, json={"variables": {"database_type": "mysql"}}).status_code == 422
        assert start.call_count == 0
        assert client.post(path, headers=headers, json={"variables": {"application_id": "azubiorga", "database_type": "postgresql", "dataset_id": "none"}}).status_code == 201
        assert start.call_count == 1
