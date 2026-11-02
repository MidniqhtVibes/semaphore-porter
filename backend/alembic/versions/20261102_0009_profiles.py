"""Personal profiles and optional teams; existing authorization is unchanged."""
from alembic import op
import sqlalchemy as sa

revision = "20261102_0009"
down_revision = "20261102_0008"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("groups") as batch:
        batch.add_column(sa.Column("is_team", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch.add_column(sa.Column("responsibilities", sa.JSON(), nullable=False, server_default="[]"))
        batch.add_column(sa.Column("responsibility_notes", sa.Text(), nullable=False, server_default=""))
    with op.batch_alter_table("users") as batch:
        for name, datatype in [("bio", sa.Text()), ("responsibility_notes", sa.Text()), ("phone", sa.String(80)),
                ("position", sa.String(160)), ("department", sa.String(160)), ("location", sa.String(160)), ("profile_color", sa.String(16))]:
            batch.add_column(sa.Column(name, datatype, nullable=False, server_default="slate" if name == "profile_color" else ""))
        for name in ("skills", "responsibilities"):
            batch.add_column(sa.Column(name, sa.JSON(), nullable=False, server_default="[]"))
        batch.add_column(sa.Column("primary_team_id", sa.Uuid(), nullable=True))
        batch.add_column(sa.Column("avatar_data", sa.LargeBinary(), nullable=True))
        batch.add_column(sa.Column("avatar_mime", sa.String(40), nullable=True))
        batch.add_column(sa.Column("avatar_version", sa.String(64), nullable=True))
        batch.create_foreign_key("fk_users_primary_team_id_groups", "groups", ["primary_team_id"], ["id"], ondelete="SET NULL")
        batch.create_index("ix_users_primary_team_id", ["primary_team_id"])


def downgrade():
    with op.batch_alter_table("users") as batch:
        batch.drop_index("ix_users_primary_team_id")
        batch.drop_constraint("fk_users_primary_team_id_groups", type_="foreignkey")
        for name in ("avatar_version", "avatar_mime", "avatar_data", "primary_team_id", "responsibilities", "skills", "profile_color",
                     "location", "department", "position", "phone", "responsibility_notes", "bio"):
            batch.drop_column(name)
    with op.batch_alter_table("groups") as batch:
        for name in ("responsibility_notes", "responsibilities", "is_team"):
            batch.drop_column(name)
