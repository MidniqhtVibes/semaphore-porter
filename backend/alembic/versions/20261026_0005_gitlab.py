"""GitLab configuration, resumable package changes and versioned catalogs."""
from alembic import op
import sqlalchemy as sa

revision = "20261026_0005"
down_revision = "20261016_0004"
branch_labels = None
depends_on = None


def timestamps():
    return [sa.Column(name, sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
            for name in ("created_at", "updated_at")]


def upgrade():
    op.create_table("gitlab_settings", sa.Column("id", sa.Integer(), primary_key=True),
                    sa.Column("encrypted_configuration", sa.LargeBinary(), nullable=False), *timestamps())
    op.create_table("program_package_drafts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("connection_id", sa.String(64), nullable=False, index=True),
        sa.Column("package_id", sa.String(63), nullable=False), sa.Column("name", sa.String(128), nullable=False),
        sa.Column("base_sha", sa.String(64), nullable=False), sa.Column("base_branch", sa.String(200), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False), sa.Column("status", sa.String(40), nullable=False, index=True),
        sa.Column("files", sa.JSON(), nullable=False), sa.Column("original_files", sa.JSON(), nullable=False),
        sa.Column("source_files", sa.JSON(), nullable=False), sa.Column("validation", sa.JSON()),
        sa.Column("branch", sa.String(200), unique=True), sa.Column("commit_sha", sa.String(64)),
        sa.Column("merge_request_iid", sa.Integer()), sa.Column("remote_status", sa.JSON()),
        sa.Column("last_error", sa.Text()), sa.Column("execution_started_at", sa.DateTime(timezone=True)),
        sa.Column("execution_token", sa.String(32)),
        sa.Column("created_by_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL")), *timestamps())
    op.create_table("catalog_snapshots",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("connection_id", sa.String(64), nullable=False, index=True),
        sa.Column("source_sha", sa.String(64), nullable=False), sa.Column("catalog", sa.JSON(), nullable=False),
        sa.Column("validation", sa.JSON(), nullable=False), sa.Column("source_hash", sa.String(64), nullable=False),
        sa.Column("project_metadata", sa.JSON(), nullable=False),
        sa.Column("created_by_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL")), *timestamps())
    op.create_table("catalog_activation", sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("snapshot_id", sa.Uuid(), sa.ForeignKey("catalog_snapshots.id", ondelete="RESTRICT")), *timestamps())
    op.execute(sa.text("INSERT INTO catalog_activation (id) VALUES (1)"))
    with op.batch_alter_table("project_templates") as batch:
        batch.add_column(sa.Column("catalog_snapshot_id", sa.Uuid()))
        batch.create_foreign_key("fk_project_templates_catalog_snapshot_id_catalog_snapshots", "catalog_snapshots", ["catalog_snapshot_id"], ["id"], ondelete="RESTRICT")


def downgrade():
    with op.batch_alter_table("project_templates") as batch:
        batch.drop_constraint("fk_project_templates_catalog_snapshot_id_catalog_snapshots", type_="foreignkey")
        batch.drop_column("catalog_snapshot_id")
    for table in ("catalog_activation", "catalog_snapshots", "program_package_drafts", "gitlab_settings"):
        op.drop_table(table)
