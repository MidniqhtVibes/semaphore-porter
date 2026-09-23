from __future__ import annotations

from sqlalchemy import select

from app.config import get_settings
from app.database import SessionLocal
from app.models import Preset, PresetVersion, Role, User
from app.security import hash_password


ROLES = [
    (1, "system_admin", "System Admin", "Vollständige Portalverwaltung"),
    (2, "tenant_admin", "Tenant Admin", "Verwaltung zugewiesener Tenants"),
    (3, "operator", "Operator", "Freigegebene Tasks ausführen"),
    (4, "viewer", "Viewer", "Freigegebene Inhalte ansehen"),
]

BUILTIN_PRESETS = [
    ("Deployment / Ports", "deployment", {"host_bind_address": "0.0.0.0", "host_port": 0, "readiness_timeout_seconds": 300}),
    ("Container Registry", "registry", {"registry_host": "", "registry_username": "", "image_repository": ""}),
    ("PostgreSQL 17", "postgresql", {"postgres_image": "postgres:17", "postgres_user": "postgres", "postgres_db": "app"}),
    ("MariaDB 11", "mariadb", {"mariadb_image": "mariadb:11", "mariadb_database": "app", "mariadb_user": "app"}),
    ("MySQL 8.4", "mysql", {"mysql_image": "mysql:8.4", "mysql_database": "app", "mysql_user": "app"}),
    ("Vault", "vault", {"vault_url": "", "vault_kv_mount": "kv", "vault_auth_mount": "semaphore-ansible"}),
    ("SMTP", "smtp", {"mail_host": "", "mail_port": 25, "mail_secure": "never", "deployment_mail_sender": ""}),
]


def bootstrap() -> None:
    settings = get_settings()
    with SessionLocal() as db:
        for role_id, code, name, description in ROLES:
            role = db.scalar(select(Role).where(Role.code == code))
            if role is None:
                db.add(Role(id=role_id, code=code, name=name, description=description))
        db.flush()
        for name, category, values in BUILTIN_PRESETS:
            if db.scalar(select(Preset).where(Preset.name == name)) is None:
                preset = Preset(name=name, category=category, description="Integrierte, secret-freie Vorlage", is_builtin=True)
                preset.versions.append(PresetVersion(version=1, values=values))
                db.add(preset)

        if settings.portal_bootstrap_admin_email and settings.portal_bootstrap_admin_password:
            email = settings.portal_bootstrap_admin_email.strip().lower()
            user = db.scalar(select(User).where(User.email == email))
            if user is None:
                admin_role = db.scalar(select(Role).where(Role.code == "system_admin"))
                user = User(
                    email=email,
                    display_name=settings.portal_bootstrap_admin_name,
                    password_hash=hash_password(settings.portal_bootstrap_admin_password.get_secret_value()),
                    must_change_password=True,
                )
                if admin_role:
                    user.roles.append(admin_role)
                db.add(user)
        db.commit()


if __name__ == "__main__":
    bootstrap()

