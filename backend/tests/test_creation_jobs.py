import json

import httpx
import respx
from sqlalchemy import select

from app.database import SessionLocal
from app.models import CreationJob, CreationStatus, ProjectTemplate, SemaphoreSettings, Tenant
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
