from app.database import SessionLocal
import pytest
from app.models import AuditEvent, LoginAttempt, User
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


def test_username_create_edit_and_login_preserves_email_login(client, admin_headers):
    response = client.post("/api/admin/users", headers=admin_headers, json={
        "email": "louis@example.com", "username": " Louis.Findeisen ", "display_name": "Louis", "password": "correct-horse-battery",
    })
    assert response.status_code == 201, response.text
    user = response.json()
    assert user["username"] == "louis.findeisen"
    renamed = client.patch(f"/api/admin/users/{user['id']}", headers=admin_headers, json={"username": "louis"})
    assert renamed.status_code == 200
    for identifier in (" LOUIS ", "louis@example.com"):
        response = client.post("/api/auth/login", json={"identifier": identifier, "password": "correct-horse-battery"})
        assert response.status_code == 200, response.text
        assert response.json()["user"]["id"] == user["id"]
        assert client.get("/api/auth/me").json()["username"] == "louis"
    assert client.post("/api/auth/login", json={"identifier": "louis.findeisen", "password": "correct-horse-battery"}).status_code == 401


def test_username_is_unique_for_create_and_update(client, admin_headers):
    users = client.get("/api/admin/users", headers=admin_headers).json()
    first, second = users[0]["id"], users[1]["id"]
    assert client.patch(f"/api/admin/users/{first}", headers=admin_headers, json={"username": "unique.name"}).status_code == 200
    assert client.patch(f"/api/admin/users/{second}", headers=admin_headers, json={"username": "UNIQUE.NAME"}).status_code == 409
    response = client.post("/api/admin/users", headers=admin_headers, json={"email": "new@example.com", "username": "Unique.Name", "display_name": "New", "password": "correct-horse-battery"})
    assert response.status_code == 409


@pytest.mark.parametrize("username", ["a", "with space", "name@example.com", ".invalid", "üser", "x" * 65, ""])
def test_invalid_username_rejected(client, admin_headers, username):
    user_id = client.get("/api/auth/me").json()["id"]
    assert client.patch(f"/api/admin/users/{user_id}", headers=admin_headers, json={"username": username}).status_code == 422


def test_automatic_usernames_handle_email_local_part_collisions(client, admin_headers):
    usernames = []
    for email in ("team@example.com", "team@other.example.com", "a@example.com"):
        response = client.post("/api/admin/users", headers=admin_headers, json={"email": email, "display_name": "Team", "password": "correct-horse-battery"})
        assert response.status_code == 201, response.text
        usernames.append(response.json()["username"])
    assert usernames == ["team", "team-2", "user"]


def test_login_failure_limit_is_shared_by_username_and_email(client):
    with SessionLocal() as db:
        db.scalar(select(User).where(User.email == "admin@example.com")).username = "admin"
        db.commit()
    for index in range(8):
        identifier = "admin" if index % 2 else "admin@example.com"
        assert client.post("/api/auth/login", json={"identifier": identifier, "password": "wrong"}).status_code == 401
    with SessionLocal() as db:
        attempts = db.scalars(select(LoginAttempt)).all()
        assert len({attempt.identity_hash for attempt in attempts}) == 1
        # Verify the account limit independently of the IP limit.
        for attempt in attempts:
            attempt.ip_hash = b"different-ip"
        db.commit()
    assert client.post("/api/auth/login", json={"identifier": "ADMIN", "password": "correct-horse-battery"}).status_code == 429


@pytest.mark.parametrize("identifier", ["disabled", "disabled@example.com"])
def test_disabled_account_cannot_login_with_either_identifier(client, identifier):
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == "operator@example.com"))
        user.email, user.username, user.is_active = "disabled@example.com", "disabled", False
        db.commit()
    assert client.post("/api/auth/login", json={"identifier": identifier, "password": "correct-horse-battery"}).status_code == 401
