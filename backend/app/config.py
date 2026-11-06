from __future__ import annotations

from functools import lru_cache
from contextvars import ContextVar
from typing import Annotated

from pydantic import BeforeValidator, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _split_csv(value: object) -> object:
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    return value


CsvList = Annotated[list[str], BeforeValidator(_split_csv)]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", enable_decoding=False)

    app_name: str = "Semaporter"
    demo_mode: bool = False
    demo_enabled: bool = True
    environment: str = "production"
    database_url: str = "postgresql+psycopg://semaporter@postgres/semaporter"
    portal_secret_key: SecretStr = Field(min_length=32)
    portal_fernet_key: SecretStr
    portal_cookie_secure: bool = True
    portal_allowed_hosts: CsvList = ["localhost"]
    portal_session_hours: int = Field(default=12, ge=1, le=168)
    portal_bootstrap_admin_email: str | None = None
    portal_bootstrap_admin_password: SecretStr | None = None
    portal_bootstrap_admin_name: str = "Portal Administrator"
    semaphore_request_timeout_seconds: float = Field(default=30, ge=2, le=120)
    vault_request_timeout_seconds: float = Field(default=30, ge=2, le=120)
    vault_ca_bundle: str | None = None
    gitlab_request_timeout_seconds: float = Field(default=30, ge=2, le=120)
    gitlab_ca_bundle: str | None = None
    approval_smtp_host: str | None = None
    approval_smtp_port: int = Field(default=587, ge=1, le=65535)
    approval_smtp_username: str | None = None
    approval_smtp_password: SecretStr | None = None
    approval_smtp_from: str | None = None
    approval_smtp_security: str = "starttls"
    approval_portal_url: str | None = None

    @model_validator(mode="before")
    @classmethod
    def isolated_demo(cls, values):
        import secrets
        from cryptography.fernet import Fernet
        if isinstance(values, dict) and str(values.get("demo_mode", "false")).lower() in {"true", "1", "yes", "on"}:
            if values.get("database_url") != "sqlite+pysqlite:///:memory:":
                raise ValueError("Demo benötigt den internen In-Memory-Datenbankkontext.")
            # Never inherit production keys, bootstrap accounts or CA paths.
            values = {**values, "portal_secret_key": secrets.token_urlsafe(48), "portal_fernet_key": Fernet.generate_key().decode(),
                "portal_bootstrap_admin_email": None, "portal_bootstrap_admin_password": None,
                "vault_ca_bundle": None, "gitlab_ca_bundle": None}
            values.update(approval_smtp_host=None, approval_smtp_username=None, approval_smtp_password=None,
                          approval_smtp_from=None, approval_portal_url=None)
        return values

    @field_validator("portal_allowed_hosts", mode="after")
    @classmethod
    def include_internal_health_hosts(cls, value: list[str]) -> list[str]:
        return list(dict.fromkeys([*value, "localhost", "127.0.0.1"]))

    @field_validator("portal_fernet_key")
    @classmethod
    def valid_fernet_key(cls, value: SecretStr) -> SecretStr:
        from cryptography.fernet import Fernet

        Fernet(value.get_secret_value().encode())
        return value


@lru_cache
def default_settings() -> Settings:
    # Simulation can only be entered by the mounted server-side sandbox.
    return Settings(demo_mode=False)  # type: ignore[call-arg]


settings_context: ContextVar[Settings | None] = ContextVar("settings_context", default=None)


def get_settings() -> Settings:
    return settings_context.get() or default_settings()
