"""Vault configuration, encrypted job payloads and execution leases."""
from alembic import op
import sqlalchemy as sa

revision = "20261016_0004"
down_revision = "20261016_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("vault_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("encrypted_configuration", sa.LargeBinary(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    for name in ("vault_plan", "vault_progress"):
        op.add_column("creation_jobs", sa.Column(name, sa.JSON(), nullable=True))
    op.add_column("creation_jobs", sa.Column("encrypted_vault_payload", sa.LargeBinary(), nullable=True))
    op.add_column("creation_jobs", sa.Column("execution_started_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    for name in ("execution_started_at", "encrypted_vault_payload", "vault_progress", "vault_plan"):
        op.drop_column("creation_jobs", name)
    op.drop_table("vault_settings")
