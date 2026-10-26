from __future__ import annotations

import re
import uuid
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class GitLabSettingsInput(Input):
    base_url: str = Field(min_length=8, max_length=1000)
    project_id: int = Field(gt=0, strict=True)
    base_branch: str = Field(default="main", min_length=1, max_length=200)
    write_enabled: bool = False
    token: SecretStr | None = Field(default=None, max_length=512)

    @field_validator("base_url")
    @classmethod
    def valid_url(cls, value):
        p = urlsplit(value)
        if (p.scheme not in {"http", "https"} or not p.hostname or p.username or p.password
                or p.query or p.fragment or any(s in {".", ".."} for s in p.path.split("/"))
                or not re.fullmatch(r"[A-Za-z0-9/_.-]*", p.path)):
            raise ValueError("GitLab-URL benötigt eine HTTP(S)-Adresse ohne Zugangswerte, Query oder Fragment.")
        _ = p.port
        return value.rstrip("/")

    @field_validator("base_branch")
    @classmethod
    def valid_branch(cls, value):
        if (not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9/_.-]*", value) or ".." in value
                or "//" in value or value.endswith(("/", ".", ".lock"))):
            raise ValueError("Ungültiger Basisbranch.")
        return value


class PackageCreate(Input):
    package_id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{0,62}$")
    source_id: str | None = Field(default=None, pattern=r"^[a-z0-9][a-z0-9-]{0,62}$")
    name: str = Field(min_length=1, max_length=128)
    image_repository: str | None = Field(default=None, max_length=300, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:/-]*$")
    release: str = Field(default="1.0.0", pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
    container_port: int = Field(default=8080, ge=1, le=65535)


class PackageUpdate(Input):
    version: int = Field(ge=1)
    files: dict[str, str] = Field(max_length=100)
    manifest: dict | None = None
    dataset_catalog: dict | None = None


class VersionInput(Input):
    version: int = Field(ge=1)


class PublishInput(VersionInput):
    confirm: Literal[True]


class ActivateInput(Input):
    expected_active_id: uuid.UUID | None = None
    confirm_reviewed: Literal[True]
    project_template_id: uuid.UUID
    repository_name: str = Field(min_length=1, max_length=255)
    template_name: str = Field(min_length=2, max_length=255)
    historical: bool = False
