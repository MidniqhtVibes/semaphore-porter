import importlib.util
from pathlib import Path
import uuid

from alembic.migration import MigrationContext
from alembic.operations import Operations
import sqlalchemy as sa


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
