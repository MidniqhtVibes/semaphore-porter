from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class RuleType(str, enum.Enum):
    FIXED = "fixed"
    ENUM = "enum"
    INTEGER_RANGE = "integer_range"
    STRING = "string"
    BOOLEAN = "boolean"
    HIDDEN = "hidden"


class TenantStatus(str, enum.Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    INACTIVE = "inactive"
    DELETED = "deleted"


class CreationStatus(str, enum.Enum):
    DRAFT = "draft"
    VALIDATED = "validated"
    RESTORING = "restoring"
    VERIFICATION_REQUIRED = "verification_required"
    SEMAPHORE_CREATED = "semaphore_created"
    COMPLETED = "completed"
    FAILED = "failed"


class TaskRunStatus(str, enum.Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    STOPPED = "stopped"
    UNKNOWN = "unknown"


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(160))
    password_hash: Mapped[str] = mapped_column(String(512))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    roles: Mapped[list[Role]] = relationship(secondary="user_roles", back_populates="users")
    group_memberships: Mapped[list[GroupMembership]] = relationship(back_populates="user", cascade="all, delete-orphan")
    tenant_memberships: Mapped[list[TenantMembership]] = relationship(back_populates="user")


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(40), unique=True)
    name: Mapped[str] = mapped_column(String(80))
    description: Mapped[str] = mapped_column(String(300), default="")
    users: Mapped[list[User]] = relationship(secondary="user_roles", back_populates="roles")


class UserRole(Base):
    __tablename__ = "user_roles"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True)


class Group(Base, TimestampMixin):
    __tablename__ = "groups"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    description: Mapped[str] = mapped_column(String(500), default="")
    memberships: Mapped[list[GroupMembership]] = relationship(back_populates="group", cascade="all, delete-orphan")


class GroupMembership(Base):
    __tablename__ = "group_memberships"

    group_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("groups.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    group: Mapped[Group] = relationship(back_populates="memberships")
    user: Mapped[User] = relationship(back_populates="group_memberships")


class Tenant(Base, TimestampMixin):
    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_slug: Mapped[str] = mapped_column(String(31), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text, default="")
    application_id: Mapped[str | None] = mapped_column(String(160))
    status: Mapped[TenantStatus] = mapped_column(
        Enum(TenantStatus, name="tenant_status", native_enum=False), default=TenantStatus.DRAFT, index=True
    )
    configuration_complete: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    semaphore_project: Mapped[SemaphoreProject | None] = relationship(
        back_populates="tenant", cascade="all, delete-orphan", uselist=False
    )
    memberships: Mapped[list[TenantMembership]] = relationship(back_populates="tenant", cascade="all, delete-orphan")
    task_templates: Mapped[list[TaskTemplate]] = relationship(back_populates="tenant", cascade="all, delete-orphan")


class TenantMembership(Base, TimestampMixin):
    __tablename__ = "tenant_memberships"
    __table_args__ = (
        CheckConstraint("(user_id IS NULL) <> (group_id IS NULL)", name="one_principal"),
        UniqueConstraint("tenant_id", "user_id", name="uq_tenant_membership_user"),
        UniqueConstraint("tenant_id", "group_id", name="uq_tenant_membership_group"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    group_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("groups.id", ondelete="CASCADE"), index=True)
    role_code: Mapped[str] = mapped_column(String(40), default="viewer")

    tenant: Mapped[Tenant] = relationship(back_populates="memberships")
    user: Mapped[User | None] = relationship(back_populates="tenant_memberships")
    group: Mapped[Group | None] = relationship()


class SemaphoreProject(Base, TimestampMixin):
    __tablename__ = "semaphore_projects"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="RESTRICT"), unique=True)
    semaphore_project_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)

    tenant: Mapped[Tenant] = relationship(back_populates="semaphore_project")


class TaskTemplate(Base, TimestampMixin):
    __tablename__ = "task_templates"
    __table_args__ = (UniqueConstraint("tenant_id", "semaphore_template_id", name="uq_task_template_remote"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    semaphore_template_id: Mapped[int] = mapped_column(BigInteger)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default="")
    app: Mapped[str] = mapped_column(String(40), default="ansible")
    survey_schema: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    tenant: Mapped[Tenant] = relationship(back_populates="task_templates")
    policy: Mapped[TaskPolicy | None] = relationship(back_populates="task_template", cascade="all, delete-orphan", uselist=False)
    permissions: Mapped[list[TaskPermission]] = relationship(back_populates="task_template", cascade="all, delete-orphan")


class TaskPermission(Base, TimestampMixin):
    __tablename__ = "task_permissions"
    __table_args__ = (
        CheckConstraint("(user_id IS NULL) <> (group_id IS NULL)", name="one_principal"),
        UniqueConstraint("task_template_id", "user_id", name="uq_task_permission_user"),
        UniqueConstraint("task_template_id", "group_id", name="uq_task_permission_group"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    task_template_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("task_templates.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    group_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("groups.id", ondelete="CASCADE"), index=True)
    can_view: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    can_start: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    can_stop: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    task_template: Mapped[TaskTemplate] = relationship(back_populates="permissions")
    user: Mapped[User | None] = relationship()
    group: Mapped[Group | None] = relationship()


class TaskPolicy(Base, TimestampMixin):
    __tablename__ = "task_policies"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    task_template_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("task_templates.id", ondelete="CASCADE"), unique=True)
    name: Mapped[str] = mapped_column(String(180))
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    task_template: Mapped[TaskTemplate] = relationship(back_populates="policy")
    variable_rules: Mapped[list[VariableRule]] = relationship(
        back_populates="policy", cascade="all, delete-orphan", order_by="VariableRule.position"
    )


class VariableRule(Base, TimestampMixin):
    __tablename__ = "variable_rules"
    __table_args__ = (UniqueConstraint("policy_id", "variable_name", name="uq_variable_rule_name"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    policy_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("task_policies.id", ondelete="CASCADE"), index=True)
    variable_name: Mapped[str] = mapped_column(String(160))
    title: Mapped[str] = mapped_column(String(255))
    help_text: Mapped[str] = mapped_column(Text, default="")
    rule_type: Mapped[RuleType] = mapped_column(Enum(RuleType, name="rule_type", native_enum=False))
    fixed_value: Mapped[Any | None] = mapped_column(JSON)
    default_value: Mapped[Any | None] = mapped_column(JSON)
    allowed_values: Mapped[list[Any] | None] = mapped_column(JSON)
    minimum: Mapped[int | None] = mapped_column(Integer)
    maximum: Mapped[int | None] = mapped_column(Integer)
    regex_pattern: Mapped[str | None] = mapped_column(String(500))
    max_length: Mapped[int | None] = mapped_column(Integer)
    is_required: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    policy: Mapped[TaskPolicy] = relationship(back_populates="variable_rules")


class Preset(Base, TimestampMixin):
    __tablename__ = "presets"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(160), unique=True)
    category: Mapped[str] = mapped_column(String(80))
    description: Mapped[str] = mapped_column(Text, default="")
    current_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_builtin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    versions: Mapped[list[PresetVersion]] = relationship(back_populates="preset", cascade="all, delete-orphan")


class PresetVersion(Base):
    __tablename__ = "preset_versions"
    __table_args__ = (UniqueConstraint("preset_id", "version", name="uq_preset_version"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    preset_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("presets.id", ondelete="CASCADE"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    values: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    preset: Mapped[Preset] = relationship(back_populates="versions")


class ProjectTemplate(Base, TimestampMixin):
    __tablename__ = "project_templates"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default="")
    source_type: Mapped[str] = mapped_column(String(30))
    source_project_id: Mapped[int | None] = mapped_column(BigInteger)
    backup_document: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))


class CreationJob(Base, TimestampMixin):
    __tablename__ = "creation_jobs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    idempotency_key: Mapped[str] = mapped_column(String(100), unique=True)
    status: Mapped[CreationStatus] = mapped_column(
        Enum(CreationStatus, name="creation_status", native_enum=False), default=CreationStatus.DRAFT, index=True
    )
    created_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    project_template_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("project_templates.id", ondelete="SET NULL"))
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("tenants.id", ondelete="SET NULL"))
    draft_data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    prepared_backup: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    validation_result: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    semaphore_project_id: Mapped[int | None] = mapped_column(BigInteger)
    semaphore_response: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    last_error: Mapped[str | None] = mapped_column(Text)
    restore_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TaskRun(Base, TimestampMixin):
    __tablename__ = "task_runs"
    __table_args__ = (UniqueConstraint("tenant_id", "semaphore_task_id", name="uq_task_run_remote"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="RESTRICT"), index=True)
    task_template_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("task_templates.id", ondelete="RESTRICT"), index=True)
    started_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    semaphore_task_id: Mapped[int] = mapped_column(BigInteger)
    status: Mapped[TaskRunStatus] = mapped_column(
        Enum(TaskRunStatus, name="task_run_status", native_enum=False), default=TaskRunStatus.QUEUED, index=True
    )
    submitted_variables: Mapped[dict[str, Any]] = mapped_column(JSON)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    remote_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSON)

    tenant: Mapped[Tenant] = relationship()
    task_template: Mapped[TaskTemplate] = relationship()
    started_by: Mapped[User] = relationship()


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    event_type: Mapped[str] = mapped_column(String(80), index=True)
    target_type: Mapped[str | None] = mapped_column(String(80))
    target_id: Mapped[str | None] = mapped_column(String(100))
    ip_address: Mapped[str | None] = mapped_column(String(64))
    details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    success: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class PortalSession(Base):
    __tablename__ = "portal_sessions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[bytes] = mapped_column(LargeBinary(32), unique=True, index=True)
    csrf_hash: Mapped[bytes] = mapped_column(LargeBinary(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    ip_address: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(String(500))
    user: Mapped[User] = relationship()


class LoginAttempt(Base):
    __tablename__ = "login_attempts"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    identity_hash: Mapped[bytes] = mapped_column(LargeBinary(32), index=True)
    ip_hash: Mapped[bytes] = mapped_column(LargeBinary(32), index=True)
    success: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class SemaphoreSettings(Base, TimestampMixin):
    __tablename__ = "semaphore_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    base_url: Mapped[str] = mapped_column(String(1000))
    encrypted_token: Mapped[bytes] = mapped_column(LargeBinary)
    proxy_url: Mapped[str | None] = mapped_column(String(1000))
    last_tested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_test_success: Mapped[bool | None] = mapped_column(Boolean)
    last_test_message: Mapped[str | None] = mapped_column(Text)
    updated_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))


Index("ix_task_runs_tenant_started", TaskRun.tenant_id, TaskRun.started_at.desc())
Index("ix_audit_events_type_time", AuditEvent.event_type, AuditEvent.occurred_at.desc())

