"""Optional organizational colors and tags; no authorization changes."""
from alembic import op
import sqlalchemy as sa

revision = "20261102_0008"
down_revision = "20261029_0007"
branch_labels = None
depends_on = None


def upgrade():
    for table in ("users", "groups"):
        with op.batch_alter_table(table) as batch:
            batch.add_column(sa.Column("color", sa.String(16), nullable=False, server_default="slate"))
            batch.add_column(sa.Column("tags", sa.JSON(), nullable=False, server_default="[]"))


def downgrade():
    for table in ("groups", "users"):
        with op.batch_alter_table(table) as batch:
            batch.drop_column("tags")
            batch.drop_column("color")
