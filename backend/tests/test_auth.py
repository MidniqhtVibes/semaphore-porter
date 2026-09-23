from app.database import SessionLocal
from app.models import AuditEvent, User
from sqlalchemy import select


def test_login_cookie_is_httponly_and_mutations_require_csrf(client):
    response = client.post("/api/auth/login", json={"email": "admin@example.com", "password": "correct-horse-battery"})
    assert response.status_code == 200
    assert "httponly" in response.headers["set-cookie"].lower()
    assert client.post("/api/auth/logout").status_code == 403
    csrf = response.json()["csrf_token"]
    assert client.post("/api/auth/logout", headers={"X-CSRF-Token": csrf}).status_code == 200


def test_failed_login_is_audited_without_password(client):
    response = client.post("/api/auth/login", json={"email": "admin@example.com", "password": "wrong"})
    assert response.status_code == 401
    with SessionLocal() as db:
        event = db.scalar(select(AuditEvent).where(AuditEvent.event_type == "login_failed"))
        assert event is not None
        assert "password" not in str(event.details).lower()


def test_non_admin_cannot_use_admin_api(client, operator_headers):
    assert client.get("/api/admin/users", headers=operator_headers).status_code == 403
