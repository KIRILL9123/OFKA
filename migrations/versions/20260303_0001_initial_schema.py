"""initial schema

Revision ID: 20260303_0001
Revises:
Create Date: 2026-03-03 00:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260303_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    table_names = set(inspector.get_table_names())

    if "users" not in table_names:
        op.create_table(
            "users",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("tg_id", sa.BigInteger(), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False),
            sa.Column("language", sa.String(length=5), nullable=True),
            sa.Column("pref_steam", sa.Boolean(), server_default=sa.text("1"), nullable=False),
            sa.Column("pref_epic", sa.Boolean(), server_default=sa.text("1"), nullable=False),
            sa.Column("pref_gog", sa.Boolean(), server_default=sa.text("0"), nullable=False),
            sa.Column("pref_other", sa.Boolean(), server_default=sa.text("0"), nullable=False),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("tg_id"),
        )
    else:
        existing_user_cols = {col["name"] for col in inspector.get_columns("users")}
        if "language" not in existing_user_cols:
            op.add_column("users", sa.Column("language", sa.String(length=5), nullable=True))
        if "pref_steam" not in existing_user_cols:
            op.add_column(
                "users",
                sa.Column("pref_steam", sa.Boolean(), server_default=sa.text("1"), nullable=False),
            )
        if "pref_epic" not in existing_user_cols:
            op.add_column(
                "users",
                sa.Column("pref_epic", sa.Boolean(), server_default=sa.text("1"), nullable=False),
            )
        if "pref_gog" not in existing_user_cols:
            op.add_column(
                "users",
                sa.Column("pref_gog", sa.Boolean(), server_default=sa.text("0"), nullable=False),
            )
        if "pref_other" not in existing_user_cols:
            op.add_column(
                "users",
                sa.Column("pref_other", sa.Boolean(), server_default=sa.text("0"), nullable=False),
            )

        op.execute(sa.text("UPDATE users SET pref_steam = 1 WHERE pref_steam IS NULL"))
        op.execute(sa.text("UPDATE users SET pref_epic = 1 WHERE pref_epic IS NULL"))
        op.execute(sa.text("UPDATE users SET pref_gog = 0 WHERE pref_gog IS NULL"))
        op.execute(sa.text("UPDATE users SET pref_other = 0 WHERE pref_other IS NULL"))

    existing_user_indexes = {idx["name"] for idx in inspector.get_indexes("users")}
    users_tg_idx = op.f("ix_users_tg_id")
    if users_tg_idx not in existing_user_indexes:
        op.create_index(users_tg_idx, "users", ["tg_id"], unique=True)

    if "games" not in table_names:
        op.create_table(
            "games",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("external_id", sa.Integer(), nullable=False),
            sa.Column("title", sa.String(length=512), nullable=False),
            sa.Column("sent_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("external_id"),
        )

    existing_game_indexes = {idx["name"] for idx in inspector.get_indexes("games")}
    games_ext_idx = op.f("ix_games_external_id")
    if games_ext_idx not in existing_game_indexes:
        op.create_index(games_ext_idx, "games", ["external_id"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_games_external_id"), table_name="games")
    op.drop_table("games")
    op.drop_index(op.f("ix_users_tg_id"), table_name="users")
    op.drop_table("users")
