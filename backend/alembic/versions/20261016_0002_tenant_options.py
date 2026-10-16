"""Persist tenant application, database and dataset selections."""
from alembic import op
import sqlalchemy as sa

revision = "20261016_0002"
down_revision = "20260922_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for name in ("application_ids", "database_types", "dataset_ids"):
        op.add_column("tenants", sa.Column(name, sa.JSON(), server_default="[]", nullable=False))
    tenants = sa.table("tenants", sa.column("id", sa.Uuid()), sa.column("application_id", sa.String()), sa.column("application_ids", sa.JSON()))
    connection = op.get_bind()
    for tenant in connection.execute(sa.select(tenants.c.id, tenants.c.application_id)).mappings():
        if tenant["application_id"]:
            connection.execute(tenants.update().where(tenants.c.id == tenant["id"]).values(application_ids=[tenant["application_id"]]))


def downgrade() -> None:
    for name in ("dataset_ids", "database_types", "application_ids"):
        op.drop_column("tenants", name)
