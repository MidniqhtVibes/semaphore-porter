"""Optional tenant task approvals; disabled for existing tenants."""
from alembic import op
import sqlalchemy as sa

revision = "20261106_0013"
down_revision = "20261105_0012"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("tenants", sa.Column("approval_config", sa.JSON(), nullable=False, server_default="{}"))
    op.add_column("tenants", sa.Column("project_artwork", sa.JSON(), nullable=False, server_default="{}"))
    op.add_column("tenants", sa.Column("project_logo_data", sa.LargeBinary()))
    op.add_column("tenants", sa.Column("project_logo_mime", sa.String(40)))
    op.add_column("task_policies", sa.Column("cost_class", sa.String(10)))
    op.add_column("task_policies", sa.Column("effort_class", sa.String(10)))
    op.create_table("task_approvals",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("task_template_id", sa.Uuid(), sa.ForeignKey("task_templates.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("requester_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True),
        sa.Column("approver_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("encrypted_variables", sa.LargeBinary(), nullable=False),
        sa.Column("context_digest", sa.String(64), nullable=False),
        sa.Column("reason", sa.String(2000), nullable=False),
        sa.Column("decision_note", sa.String(2000), nullable=False),
        sa.Column("notification_status", sa.String(20), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True)),
        sa.Column("execution_started_at", sa.DateTime(timezone=True)),
        sa.Column("run_id", sa.Uuid(), sa.ForeignKey("task_runs.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))


def downgrade():
    op.drop_table("task_approvals")
    op.drop_column("task_policies", "effort_class")
    op.drop_column("task_policies", "cost_class")
    op.drop_column("tenants", "approval_config")
    op.drop_column("tenants", "project_logo_mime")
    op.drop_column("tenants", "project_logo_data")
    op.drop_column("tenants", "project_artwork")
