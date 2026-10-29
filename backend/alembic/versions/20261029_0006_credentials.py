"""Central Vault SSH profiles and tracked project assignments."""
from alembic import op
import sqlalchemy as sa

revision = "20261029_0006"
down_revision = "20261026_0005"
branch_labels = None
depends_on = None


def timestamps():
    return [sa.Column(name, sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
            for name in ("created_at", "updated_at")]


def upgrade():
    op.create_table("credential_settings", sa.Column("id", sa.Integer(), primary_key=True),
                    sa.Column("encrypted_configuration", sa.LargeBinary(), nullable=False), *timestamps())
    op.create_table("credential_profiles", sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(160), nullable=False, unique=True),
        sa.Column("purpose", sa.String(20), nullable=False), sa.Column("login", sa.String(100), nullable=False),
        sa.Column("vault_path", sa.String(500), nullable=False), sa.Column("vault_version", sa.Integer(), nullable=False),
        sa.Column("allowed_targets", sa.JSON(), nullable=False), sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("fingerprint", sa.String(100)), sa.Column("public_key", sa.Text()),
        sa.Column("last_tested_at", sa.DateTime(timezone=True)), *timestamps())
    op.create_table("credential_uses", sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("profile_id", sa.Uuid(), sa.ForeignKey("credential_profiles.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("creation_job_id", sa.Uuid(), sa.ForeignKey("creation_jobs.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("semaphore_project_id", sa.BigInteger(), nullable=False),
        sa.Column("semaphore_key_id", sa.BigInteger(), nullable=False), sa.Column("vault_version", sa.Integer(), nullable=False),
        sa.Column("fingerprint", sa.String(100), nullable=False), sa.Column("bindings", sa.JSON(), nullable=False),
        sa.Column("source", sa.JSON(), nullable=False), sa.Column("status", sa.String(20), nullable=False),
        sa.Column("last_error", sa.Text()), sa.Column("execution_started_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("semaphore_project_id", "profile_id", name="uq_credential_project_profile"), *timestamps())
    with op.batch_alter_table("creation_jobs") as batch:
        batch.add_column(sa.Column("credential_plan", sa.JSON()))
        batch.add_column(sa.Column("credential_progress", sa.JSON()))


def downgrade():
    op.drop_table("credential_uses")
    op.drop_table("credential_profiles")
    op.drop_table("credential_settings")
    with op.batch_alter_table("creation_jobs") as batch:
        batch.drop_column("credential_progress")
        batch.drop_column("credential_plan")
