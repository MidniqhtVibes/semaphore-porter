"""Registry access profiles and their separate Vault reader."""
from alembic import op
import sqlalchemy as sa

revision = "20261102_0010"
down_revision = "20261102_0009"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("registry_settings", sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("encrypted_configuration", sa.LargeBinary(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    op.create_table("registry_profiles", sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(160), nullable=False, unique=True),
        sa.Column("application_id", sa.String(63), nullable=False),
        sa.Column("host", sa.String(255), nullable=False), sa.Column("username", sa.String(255), nullable=False),
        sa.Column("host_variable", sa.String(160), nullable=False), sa.Column("username_variable", sa.String(160), nullable=False),
        sa.Column("source", sa.String(20), nullable=False), sa.Column("encrypted_password", sa.LargeBinary()),
        sa.Column("vault_path", sa.String(500)), sa.Column("vault_version", sa.Integer()),
        sa.Column("vault_field", sa.String(100)), sa.Column("vault_connection_id", sa.String(64)),
        sa.Column("revision", sa.String(64), nullable=False), sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    op.create_index("ix_registry_profiles_application_id", "registry_profiles", ["application_id"])


def downgrade():
    op.drop_index("ix_registry_profiles_application_id", table_name="registry_profiles")
    op.drop_table("registry_profiles")
    op.drop_table("registry_settings")
