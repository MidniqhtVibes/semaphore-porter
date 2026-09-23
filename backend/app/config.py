from __future__ import annotations

from functools import lru_cache
from typing import Annotated

from pydantic import BeforeValidator, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _split_csv(value: object) -> object:
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    return value


CsvList = Annotated[list[str], BeforeValidator(_split_csv)]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", enable_decoding=False)

    app_name: str = "Semaphore Tenant Portal"
    environment: str = "production"
    database_url: str = "postgresql+psycopg://semaphore_portal@postgres/semaphore_portal"
    portal_secret_key: SecretStr = Field(min_length=32)
    portal_fernet_key: SecretStr
    portal_cookie_secure: bool = True
    portal_allowed_hosts: CsvList = ["localhost"]
    portal_session_hours: int = Field(default=12, ge=1, le=168)
    portal_bootstrap_admin_email: str | None = None
    portal_bootstrap_admin_password: SecretStr | None = None
    portal_bootstrap_admin_name: str = "Portal Administrator"
    semaphore_request_timeout_seconds: float = Field(default=30, ge=2, le=120)

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
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
