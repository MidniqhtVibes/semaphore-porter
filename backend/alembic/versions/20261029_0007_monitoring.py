"""Read-only deployment monitoring sources and their last snapshot."""
from alembic import op
import sqlalchemy as sa

revision = "20261029_0007"
down_revision = "20261029_0006"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("deployment_sources",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("snapshot", sa.JSON()),
        sa.Column("received_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))


def downgrade():
    op.drop_table("deployment_sources")
