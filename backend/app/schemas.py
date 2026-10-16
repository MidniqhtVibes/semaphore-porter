from __future__ import annotations

import uuid
from typing import Any, Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.models import RuleType


class LoginRequest(BaseModel):
    identifier: str = Field(min_length=1, max_length=320)
    password: str = Field(min_length=1, max_length=512)

    @model_validator(mode="before")
    @classmethod
    def legacy_login_fields(cls, value):
        if isinstance(value, dict) and "identifier" not in value:
            return {**value, "identifier": value.get("email", value.get("username"))}
        return value

    @field_validator("identifier", mode="before")
    @classmethod
    def trim_identifier(cls, value):
        return value.strip() if isinstance(value, str) else value


class UsernameFields(BaseModel):
    username: str | None = Field(default=None, min_length=2, max_length=64, pattern=r"^[a-z0-9][a-z0-9._-]*$")

    @field_validator("username", mode="before")
    @classmethod
    def normalize_username(cls, value):
        return value.strip().lower() if isinstance(value, str) else value


class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=12, max_length=512)


class UserCreate(UsernameFields):
    email: EmailStr
    display_name: str = Field(min_length=2, max_length=160)
    password: str = Field(min_length=12, max_length=512)
    role_codes: list[str] = Field(default_factory=lambda: ["viewer"])
    must_change_password: bool = True


class UserUpdate(UsernameFields):
    display_name: str | None = Field(default=None, min_length=2, max_length=160)
    is_active: bool | None = None
    role_codes: list[str] | None = None


class PasswordReset(BaseModel):
    password: str = Field(min_length=12, max_length=512)
    must_change_password: bool = True


class GroupCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    description: str = Field(default="", max_length=500)


class GroupMembersUpdate(BaseModel):
    user_ids: list[uuid.UUID]


class TenantUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=2, max_length=160)
    description: str | None = Field(default=None, max_length=5000)
    application_id: str | None = Field(default=None, max_length=160)
    status: Literal["draft", "active", "inactive"] | None = None


class TenantMembershipInput(BaseModel):
    user_id: uuid.UUID | None = None
    group_id: uuid.UUID | None = None
    role_code: Literal["tenant_admin", "operator", "viewer"] = "viewer"

    @model_validator(mode="after")
    def one_principal(self) -> TenantMembershipInput:
        if (self.user_id is None) == (self.group_id is None):
            raise ValueError("Genau user_id oder group_id ist erforderlich.")
        return self


class TaskPermissionInput(BaseModel):
    user_id: uuid.UUID | None = None
    group_id: uuid.UUID | None = None
    can_view: bool = True
    can_start: bool = False
    can_stop: bool = False

    @model_validator(mode="after")
    def one_principal(self) -> TaskPermissionInput:
        if (self.user_id is None) == (self.group_id is None):
            raise ValueError("Genau user_id oder group_id ist erforderlich.")
        if (self.can_start or self.can_stop) and not self.can_view:
            raise ValueError("Starten/Stoppen setzt Sichtbarkeit voraus.")
        return self


class VariableRuleInput(BaseModel):
    variable_name: str = Field(pattern=r"^[A-Za-z_][A-Za-z0-9_]*$", max_length=160)
    title: str = Field(min_length=1, max_length=255)
    help_text: str = Field(default="", max_length=4000)
    rule_type: RuleType
    fixed_value: Any | None = None
    default_value: Any | None = None
    allowed_values: list[Any] | None = None
    minimum: int | None = None
    maximum: int | None = None
    regex_pattern: str | None = Field(default=None, max_length=500)
    max_length: int | None = Field(default=None, ge=1, le=10000)
    is_required: bool = True
    position: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def validate_by_type(self) -> VariableRuleInput:
        if self.rule_type in {RuleType.FIXED, RuleType.HIDDEN} and self.fixed_value is None:
            raise ValueError("Fixed/Hidden benötigt fixed_value.")
        if self.rule_type == RuleType.ENUM and not self.allowed_values:
            raise ValueError("Enum benötigt mindestens einen erlaubten Wert.")
        if self.rule_type == RuleType.INTEGER_RANGE:
            if self.minimum is None or self.maximum is None or self.minimum > self.maximum:
                raise ValueError("Integer Range benötigt gültiges Minimum und Maximum.")
        return self


class TaskPolicyInput(BaseModel):
    name: str = Field(min_length=2, max_length=180)
    is_active: bool = True
    rules: list[VariableRuleInput]

    @field_validator("rules")
    @classmethod
    def unique_rules(cls, value: list[VariableRuleInput]) -> list[VariableRuleInput]:
        names = [rule.variable_name for rule in value]
        if len(names) != len(set(names)):
            raise ValueError("Variablennamen dürfen nicht doppelt vorkommen.")
        return value


class TaskStartRequest(BaseModel):
    variables: dict[str, Any] = Field(default_factory=dict)


class SemaphoreSettingsInput(BaseModel):
    base_url: str = Field(min_length=8, max_length=1000)
    token: str | None = Field(default=None, max_length=5000)
    proxy_url: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def safe_urls(self) -> SemaphoreSettingsInput:
        for label, value in (("Semaphore-URL", self.base_url), ("Proxy-URL", self.proxy_url)):
            if not value:
                continue
            parsed = urlsplit(value)
            if parsed.scheme not in {"http", "https"} or not parsed.hostname:
                raise ValueError(f"{label} muss eine vollständige HTTP(S)-URL sein.")
            if parsed.username or parsed.password:
                raise ValueError(f"{label} darf keine Zugangsdaten enthalten.")
        return self


class ProjectTemplateSave(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    description: str = Field(default="", max_length=5000)
    source_project_id: int = Field(gt=0)


class CreationJobCreate(BaseModel):
    idempotency_key: str = Field(min_length=16, max_length=100, pattern=r"^[A-Za-z0-9_-]+$")
    project_template_id: uuid.UUID


class CopyResources(BaseModel):
    model_config = ConfigDict(extra="forbid")
    environments: list[dict[str, Any]]
    repositories: list[dict[str, Any]]
    inventories: list[dict[str, Any]]
    templates: list[dict[str, Any]]


class CreationDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project_name: str = Field(default="", max_length=255)
    tenant_slug: str = Field(default="", max_length=31)
    runtime_scope_id: str = Field(default="", max_length=31)
    display_name: str = Field(default="", max_length=160)
    description: str = Field(default="", max_length=5000)
    application_id: str = Field(default="", max_length=160)
    database_type: str = Field(default="", max_length=160)
    dataset_id: str = Field(default="", max_length=160)
    application_ids: list[str] | None = Field(default=None, max_length=200)
    database_types: list[str] | None = Field(default=None, max_length=200)
    dataset_ids: list[str] | None = Field(default=None, max_length=200)
    wizard_step: int = Field(default=0, ge=0, le=7)
    ttl_minutes: int = Field(default=60, ge=5, le=1440)
    task_template_names: list[str] = Field(default_factory=list)
    environment_names: list[str] = Field(default_factory=list)
    preset_ids: list[uuid.UUID] = Field(default_factory=list)
    resource_overrides: CopyResources | None = None
    repository_url: str | None = Field(default=None, max_length=2000)
    repository_branch: str | None = Field(default=None, max_length=255)
    access_assignments: list[TenantMembershipInput] = Field(default_factory=list)
    create_default_policies: bool = True
    activate_after_creation: bool = False


class CreationJobUpdate(BaseModel):
    draft_data: CreationDraft


class CreationExecuteRequest(BaseModel):
    confirm_project_creation: bool
    allow_retry_after_verified_absence: bool = False


class PresetInput(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    category: Literal["deployment", "registry", "postgresql", "mariadb", "mysql", "vault", "smtp", "application"]
    description: str = Field(default="", max_length=5000)
    values: dict[str, Any]


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)
