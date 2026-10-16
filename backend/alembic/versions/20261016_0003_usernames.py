"""Add unique usernames and populate existing accounts without changing credentials."""
import re

from alembic import op
import sqlalchemy as sa

revision = "20261016_0003"
down_revision = "20261016_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("username", sa.String(64), nullable=True))
    users = sa.table("users", sa.column("id", sa.Uuid()), sa.column("email", sa.String()), sa.column("username", sa.String(64)))
    connection = op.get_bind()
    taken = set()
    # Freeze the suggestion algorithm here so future code changes cannot alter this migration.
    for user in connection.execute(sa.select(users.c.id, users.c.email).order_by(users.c.email, users.c.id)).mappings().all():
        stem = re.sub(r"[^a-z0-9._-]+", "-", user["email"].split("@", 1)[0].lower()).strip("._-")[:64]
        if len(stem) < 2:
            stem = "user"
        username, number = stem, 2
        while username in taken:
            suffix = f"-{number}"
            username = stem[:64 - len(suffix)] + suffix
            number += 1
        taken.add(username)
        connection.execute(users.update().where(users.c.id == user["id"]).values(username=username))
    op.create_index("ix_users_username", "users", ["username"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_users_username", table_name="users")
    op.drop_column("users", "username")
