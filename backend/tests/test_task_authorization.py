import json

import httpx
import pytest
import uuid
import respx
from sqlalchemy import select

from app.database import SessionLocal
from app.models import (
    AuditEvent, RuleType, SemaphoreProject, SemaphoreSettings, TaskPermission, TaskPolicy,
    TaskRun, TaskTemplate, Tenant, TenantMembership, TenantStatus, User, VariableRule,
)
from app.security import encrypt_secret


@pytest.mark.parametrize("mail,expected", [(True, "operator@example.com"), (False, None)])
def test_mail_report_uses_authenticated_starter_not_copied_policy_or_request(client, operator_headers, mail, expected):
    tenant_id, task_id = seed_task()
    with SessionLocal() as db:
        task = db.get(TaskTemplate, uuid.UUID(task_id))
        task.policy.variable_rules.extend([
            VariableRule(variable_name="send_deployment_mail", title="Mailbericht", rule_type=RuleType.BOOLEAN, default_value=False),
            VariableRule(variable_name="mail_user", title="Alter Empfänger", rule_type=RuleType.FIXED, fixed_value="old@example.com"),
        ])
        db.commit()
    form = client.get(f"/api/portal/tenants/{tenant_id}/tasks/{task_id}/form").json()
    assert form["mail_recipient"] == "operator@example.com"
    assert "mail_user" not in [field["name"] for field in form["fields"]]
    with respx.mock as mock:
        start = mock.post("https://semaphore.example/api/project/7/tasks").respond(201, json={"id": 92, "status": "waiting"})
        response = client.post(f"/api/portal/tenants/{tenant_id}/tasks/{task_id}/runs", headers=operator_headers,
            json={"variables": {"send_deployment_mail": mail, "mail_user": "attacker@example.com"}})
        assert response.status_code == 201, response.text
        variables = json.loads(json.loads(start.calls[0].request.content)["environment"])
        assert variables.get("mail_user") == expected


def test_live_output_accepts_semaphore_null_before_first_line_and_updates(client, operator_headers):
    tenant_id, task_id = seed_task()
    with respx.mock as mock:
        mock.post("https://semaphore.example/api/project/7/tasks").respond(201, json={"id": 93, "status": "waiting"})
        run_id = client.post(f"/api/portal/tenants/{tenant_id}/tasks/{task_id}/runs", headers=operator_headers, json={"variables": {}}).json()["id"]
        state = mock.get("https://semaphore.example/api/project/7/tasks/93").respond(200, json={"id": 93, "status": "running"})
        output = mock.get("https://semaphore.example/api/project/7/tasks/93/output").respond(200, content="null")
        response = client.get(f"/api/portal/runs/{run_id}")
        assert response.status_code == 200 and response.json()["output"] == []
        state.respond(200, json={"id": 93, "status": "success"})
        output.respond(200, json=[{"output": "PLAY RECAP", "time": "2026-11-05T10:00:00Z"}])
        response = client.get(f"/api/portal/runs/{run_id}")
        assert response.json()["status"] == "success"
        assert response.json()["output"][0]["output"] == "PLAY RECAP"


def test_event_feed_recovers_after_transient_failure(client, operator_headers, monkeypatch):
    from app.routers import portal
    monkeypatch.setattr(portal, "STREAM_POLL_INTERVAL_SECONDS", 0)
    tenant_id, task_id = seed_task()
    with respx.mock as mock:
        mock.post("https://semaphore.example/api/project/7/tasks").respond(201, json={"id": 94, "status": "waiting"})
        run_id = client.post(f"/api/portal/tenants/{tenant_id}/tasks/{task_id}/runs", headers=operator_headers, json={"variables": {}}).json()["id"]
        mock.get("https://semaphore.example/api/project/7/tasks/94").mock(side_effect=[
            httpx.Response(502), httpx.Response(200, json={"id": 94, "status": "running"}),
            httpx.Response(200, json={"id": 94, "status": "success"})])
        mock.get("https://semaphore.example/api/project/7/tasks/94/output").mock(side_effect=[
            httpx.Response(200, content="null"), httpx.Response(200, json=[{"output": "Abgeschlossen", "time": "2026-11-05T10:00:00Z"}])])
        response = client.get(f"/api/portal/runs/{run_id}/events")
        assert "event: warning" in response.text and "event: complete" in response.text
        assert response.text.count("event: update") == 2 and "Abgeschlossen" in response.text


def seed_task():
    with SessionLocal() as db:
        operator = db.scalar(select(User).where(User.email == "operator@example.com"))
        tenant = Tenant(tenant_slug="kunde-a", display_name="Kunde A", status=TenantStatus.ACTIVE, configuration_complete=True)
        tenant.semaphore_project = SemaphoreProject(semaphore_project_id=7, name="Kunde A")
        task = TaskTemplate(semaphore_template_id=12, name="deploy-timed-demo", is_enabled=True, survey_schema=[])
        tenant.task_templates.append(task)
        policy = TaskPolicy(name="Kunde A Policy", is_active=True)
        policy.variable_rules = [
            VariableRule(variable_name="deployment_context", title="Kontext", rule_type=RuleType.HIDDEN, fixed_value="internal-secret"),
            VariableRule(variable_name="ttl_minutes", title="TTL", rule_type=RuleType.INTEGER_RANGE, minimum=15, maximum=180, default_value=60),
        ]
        task.policy = policy
        db.add(tenant)
        db.flush()
        db.add(TenantMembership(tenant_id=tenant.id, user_id=operator.id, role_code="operator"))
        db.add(TaskPermission(task_template_id=task.id, user_id=operator.id, can_view=True, can_start=True, can_stop=True))
        db.add(SemaphoreSettings(id=1, base_url="https://semaphore.example", encrypted_token=encrypt_secret("service-token")))
        db.commit()
        return str(tenant.id), str(task.id)


def test_task_start_rejects_extra_variables_before_semaphore(client, operator_headers):
    tenant_id, task_id = seed_task()
    with respx.mock(assert_all_called=False) as mock:
        route = mock.post("https://semaphore.example/api/project/7/tasks").mock(return_value=httpx.Response(201, json={"id": 91}))
        response = client.post(
            f"/api/portal/tenants/{tenant_id}/tasks/{task_id}/runs",
            headers=operator_headers,
            json={"variables": {"ttl_minutes": 60, "inventory_id": 999}},
        )
        assert response.status_code == 422
        assert route.call_count == 0


def test_task_start_uses_database_project_and_template_ids(client, operator_headers):
    tenant_id, task_id = seed_task()
    with respx.mock(assert_all_called=True) as mock:
        route = mock.post("https://semaphore.example/api/project/7/tasks").mock(
            return_value=httpx.Response(201, json={"id": 91, "status": "waiting"})
        )
        response = client.post(
            f"/api/portal/tenants/{tenant_id}/tasks/{task_id}/runs",
            headers=operator_headers,
            json={"variables": {"ttl_minutes": 60}},
        )
        assert response.status_code == 201, response.text
        payload = json.loads(route.calls[0].request.content)
        assert payload["template_id"] == 12
        assert json.loads(payload["environment"]) == {
            "deployment_context": "internal-secret",
            "ttl_minutes": 60,
        }
    with SessionLocal() as db:
        run = db.scalar(select(TaskRun))
        event = db.scalar(select(AuditEvent).where(AuditEvent.event_type == "task_started"))
        assert run is not None and run.submitted_variables["deployment_context"] == "[ENTFERNT]"
        assert event is not None and "internal-secret" not in str(event.details)


def test_manipulated_tenant_id_does_not_expose_task(client, operator_headers):
    _, task_id = seed_task()
    response = client.post(
        f"/api/portal/tenants/00000000-0000-0000-0000-000000000001/tasks/{task_id}/runs",
        headers=operator_headers,
        json={"variables": {"ttl_minutes": 60}},
    )
    assert response.status_code == 404


def test_run_list_refreshes_remote_status_without_open_detail(client, operator_headers):
    tenant_id, task_id = seed_task()
    with respx.mock as mock:
        mock.post("https://semaphore.example/api/project/7/tasks").respond(201, json={"id": 91, "status": "running"})
        mock.get("https://semaphore.example/api/project/7/tasks/91").respond(200, json={"id": 91, "status": "success"})
        assert client.post(f"/api/portal/tenants/{tenant_id}/tasks/{task_id}/runs", headers=operator_headers, json={"variables": {"ttl_minutes": 60}}).status_code == 201
        response = client.get("/api/portal/runs")
        assert response.status_code == 200
        assert response.json()[0]["status"] == "success"
        assert response.json()[0]["finished_at"] is not None
