"""Optional Docker management agent and action records."""
from alembic import op
import sqlalchemy as sa

revision = "20261103_0011"
down_revision = "20261102_0010"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("container_settings",sa.Column("id",sa.Integer(),primary_key=True),
        sa.Column("encrypted_configuration",sa.LargeBinary(),nullable=False),
        sa.Column("created_at",sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),
        sa.Column("updated_at",sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()))
    op.create_table("container_operations",sa.Column("id",sa.Uuid(),primary_key=True),
        sa.Column("agent_id",sa.String(36),nullable=False),sa.Column("agent_name",sa.String(160),nullable=False),
        sa.Column("connection_id",sa.String(64),nullable=False),sa.Column("container_id",sa.String(64),nullable=False),
        sa.Column("container_name",sa.String(255),nullable=False),sa.Column("action",sa.String(20),nullable=False),
        sa.Column("status",sa.String(20),nullable=False),sa.Column("message",sa.Text(),nullable=False),
        sa.Column("actor_user_id",sa.Uuid(),sa.ForeignKey("users.id",ondelete="SET NULL")),sa.Column("payload",sa.JSON(),nullable=False),
        sa.Column("created_at",sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),
        sa.Column("updated_at",sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()))


def downgrade():
    op.drop_table("container_operations")
    op.drop_table("container_settings")
