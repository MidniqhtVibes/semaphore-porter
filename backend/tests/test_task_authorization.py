import json

import httpx
import respx
from sqlalchemy import select

from app.database import SessionLocal
from app.models import (
    AuditEvent, Role, RuleType, SemaphoreProject, SemaphoreSettings, TaskPermission, TaskPolicy,
    TaskRun, TaskTemplate, Tenant, TenantMembership, TenantStatus, User, VariableRule,
)
from app.security import encrypt_secret


def seed_task():
    with SessionLocal() as db:
        operator = db.scalar(select(User).where(User.email == "operator@example.com"))
        tenant = Tenant(tenant_slug="kunde-a", display_name="Kunde A", status=TenantStatus.ACTIVE, configuration_complete=True)
        tenant.semaphore_project = SemaphoreProject(semaphore_project_id=7, name="Kunde A")
        task = TaskTemplate(semaphore_template_id=12, name="deploy-timed-demo", is_enabled=True, survey_schema=[])
        tenant.task_templates.append(task)
        policy = TaskPolicy(name="Kunde A Policy", is_active=True)
        policy.variable_rules = [
            VariableRule(variable_name="tenant_slug", title="Tenant", rule_type=RuleType.FIXED, fixed_value="kunde-a"),
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
            "tenant_slug": "kunde-a",
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
