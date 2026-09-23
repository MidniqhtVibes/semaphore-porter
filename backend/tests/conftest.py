import os

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")
os.environ.setdefault("PORTAL_SECRET_KEY", "test-secret-key-that-is-longer-than-32-characters")
os.environ.setdefault("PORTAL_FERNET_KEY", "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=")
os.environ.setdefault("PORTAL_COOKIE_SECURE", "false")
os.environ.setdefault("PORTAL_ALLOWED_HOSTS", "testserver,localhost")

import pytest
from fastapi.testclient import TestClient

from app.database import Base, SessionLocal, engine
from app.main import app
from app.models import Role, User
from app.security import hash_password


@pytest.fixture(autouse=True)
def clean_database():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        roles = [
            Role(id=1, code="system_admin", name="System Admin"),
            Role(id=2, code="tenant_admin", name="Tenant Admin"),
            Role(id=3, code="operator", name="Operator"),
            Role(id=4, code="viewer", name="Viewer"),
        ]
        db.add_all(roles)
        admin = User(email="admin@example.com", display_name="Admin", password_hash=hash_password("correct-horse-battery"))
        admin.roles.append(roles[0])
        operator = User(email="operator@example.com", display_name="Operator", password_hash=hash_password("correct-horse-battery"))
        operator.roles.append(roles[2])
        db.add_all([admin, operator])
        db.commit()
    yield


@pytest.fixture
def client():
    with TestClient(app) as value:
        yield value


def login(client: TestClient, email: str = "admin@example.com") -> dict[str, str]:
    response = client.post("/api/auth/login", json={"email": email, "password": "correct-horse-battery"})
    assert response.status_code == 200, response.text
    return {"X-CSRF-Token": response.json()["csrf_token"]}


@pytest.fixture
def admin_headers(client):
    return login(client)


@pytest.fixture
def operator_headers(client):
    return login(client, "operator@example.com")
