"""Resumable tenant cleanup, removed together with the tenant after success."""
from alembic import op
import sqlalchemy as sa

revision = "20261105_0012"
down_revision = "20261103_0011"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("tenant_deletions",
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("plan", sa.JSON(), nullable=False), sa.Column("progress", sa.JSON(), nullable=False),
        sa.Column("revision", sa.String(64), nullable=False), sa.Column("last_error", sa.Text()),
        sa.Column("execution_started_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))


def downgrade():
    op.drop_table("tenant_deletions")
