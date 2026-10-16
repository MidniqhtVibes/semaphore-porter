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
