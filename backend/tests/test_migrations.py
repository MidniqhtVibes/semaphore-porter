import importlib.util
from pathlib import Path
import uuid

from alembic.migration import MigrationContext
from alembic.operations import Operations
import sqlalchemy as sa


def test_monitoring_migration_is_additive_and_reversible():
    path = Path(__file__).parents[1] / "alembic/versions/20261029_0007_monitoring.py"
    spec = importlib.util.spec_from_file_location("monitoring_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = sa.create_engine("sqlite://")
    existing = sa.Table("task_runs", sa.MetaData(), sa.Column("id", sa.Integer(), primary_key=True))
    existing.metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(existing.insert().values(id=42))
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
        table = sa.Table("deployment_sources", sa.MetaData(), autoload_with=connection)
        connection.execute(table.insert().values(id=uuid.uuid4().hex, name="Host", token_hash="a" * 64,
            snapshot={"observed_at": 100, "deployments": []}))
        assert connection.execute(sa.select(table.c.snapshot)).scalar_one()["observed_at"] == 100
        assert "token" not in {column["name"] for column in sa.inspect(connection).get_columns("deployment_sources")}
        with Operations.context(MigrationContext.configure(connection)):
            migration.downgrade()
        assert "deployment_sources" not in sa.inspect(connection).get_table_names()
        assert connection.execute(sa.select(existing.c.id)).scalar_one() == 42


def test_ssh_profiles_migration_preserves_existing_jobs_and_has_no_private_key_column():
    path = Path(__file__).parents[1] / "alembic/versions/20261029_0006_credentials.py"
    spec = importlib.util.spec_from_file_location("credentials_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = sa.create_engine("sqlite://")
    old = sa.Table("creation_jobs", sa.MetaData(), sa.Column("id", sa.Uuid(), primary_key=True),
                   sa.Column("status", sa.String()), sa.Column("draft_data", sa.JSON()))
    old.metadata.create_all(engine)
    identifier = uuid.uuid4()
    with engine.begin() as connection:
        connection.execute(old.insert().values(id=identifier, status="validated", draft_data={"tenant_slug": "old-a"}))
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
        jobs = sa.Table("creation_jobs", sa.MetaData(), autoload_with=connection)
        row = connection.execute(sa.select(jobs)).mappings().one()
        assert row["draft_data"] == {"tenant_slug": "old-a"} and row["credential_plan"] is None
        assert row["credential_progress"] is None
        inspector = sa.inspect(connection)
        assert {"credential_settings", "credential_profiles", "credential_uses"}.issubset(inspector.get_table_names())
        assert "private_key" not in {column["name"] for column in inspector.get_columns("credential_profiles")}
        with Operations.context(MigrationContext.configure(connection)):
            migration.downgrade()
        assert "credential_profiles" not in sa.inspect(connection).get_table_names()
        assert connection.execute(sa.select(old.c.status)).scalar_one() == "validated"


def test_tenant_options_migration_preserves_legacy_application():
    path = Path(__file__).parents[1] / "alembic/versions/20261016_0002_tenant_options.py"
    spec = importlib.util.spec_from_file_location("tenant_options_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = sa.create_engine("sqlite://")
    metadata = sa.MetaData()
    legacy = sa.Table("tenants", metadata, sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("application_id", sa.String(160)))
    metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(legacy.insert(), [{"id": uuid.uuid4(), "application_id": "azubiorga"}, {"id": uuid.uuid4(), "application_id": None}])
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
        updated = sa.Table("tenants", sa.MetaData(), autoload_with=connection)
        rows = connection.execute(sa.select(updated)).mappings().all()
        assert next(row for row in rows if row["application_id"])["application_ids"] == ["azubiorga"]
        assert next(row for row in rows if not row["application_id"])["application_ids"] == []
        assert all(row["database_types"] == [] and row["dataset_ids"] == [] for row in rows)


def test_username_migration_preserves_accounts_and_generates_unique_valid_names():
    from app.schemas import UserUpdate
    from app.usernames import suggest_username

    path = Path(__file__).parents[1] / "alembic/versions/20261016_0003_usernames.py"
    spec = importlib.util.spec_from_file_location("username_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = sa.create_engine("sqlite://")
    legacy = sa.Table("users", sa.MetaData(), sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("email", sa.String(320)), sa.Column("password_hash", sa.String(512)))
    legacy.metadata.create_all(engine)
    emails = ["Team@a.example", "team@b.example", "team-2@example.com", "a@example.com", "---@example.com", "äö@example.com", "x" * 80 + "@example.com", "x" * 80 + "@other.example.com"]
    before = [{"id": uuid.uuid4(), "email": email, "password_hash": "unchanged-hash"} for email in emails]
    with engine.begin() as connection:
        connection.execute(legacy.insert(), before)
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
        updated = sa.Table("users", sa.MetaData(), autoload_with=connection)
        rows = connection.execute(sa.select(updated).order_by(updated.c.email, updated.c.id)).mappings().all()
        assert {uuid.UUID(str(row["id"])) for row in rows} == {row["id"] for row in before}
        assert {row["email"] for row in rows} == set(emails)
        assert all(row["password_hash"] == "unchanged-hash" for row in rows)
        assert len({row["username"] for row in rows}) == len(emails)
        taken = set()
        for row in rows:
            assert UserUpdate(username=row["username"]).username == row["username"]
            assert suggest_username(row["email"], taken) == row["username"]
            taken.add(row["username"])
        with Operations.context(MigrationContext.configure(connection)):
            migration.downgrade()
        assert "username" not in {column["name"] for column in sa.inspect(connection).get_columns("users")}


def test_vault_migration_preserves_existing_jobs_and_supports_downgrade():
    path = Path(__file__).parents[1] / "alembic/versions/20261016_0004_vault.py"
    spec = importlib.util.spec_from_file_location("vault_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = sa.create_engine("sqlite://")
    legacy = sa.Table("creation_jobs", sa.MetaData(), sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("status", sa.String()), sa.Column("draft_data", sa.JSON()))
    legacy.metadata.create_all(engine)
    job_id = uuid.uuid4()
    with engine.begin() as connection:
        connection.execute(legacy.insert().values(id=job_id, status="validated", draft_data={"tenant_slug": "existing-a"}))
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
        jobs = sa.Table("creation_jobs", sa.MetaData(), autoload_with=connection)
        row = connection.execute(sa.select(jobs)).mappings().one()
        assert row["status"] == "validated" and row["draft_data"] == {"tenant_slug": "existing-a"}
        assert all(row[name] is None for name in ("vault_plan", "vault_progress", "encrypted_vault_payload", "execution_started_at"))
        assert "vault_settings" in sa.inspect(connection).get_table_names()
        with Operations.context(MigrationContext.configure(connection)):
            migration.downgrade()
        assert "vault_settings" not in sa.inspect(connection).get_table_names()
        row = connection.execute(sa.select(legacy)).mappings().one()
        assert row["status"] == "validated" and row["draft_data"] == {"tenant_slug": "existing-a"}
