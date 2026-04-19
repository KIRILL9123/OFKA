"""add user_games table and games.worth column

Revision ID: 20260419_0002
Revises: 20260303_0001
Create Date: 2026-04-19 00:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260419_0002"
down_revision = "20260303_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    table_names = set(inspector.get_table_names())

    if "user_games" not in table_names:
        op.create_table(
            "user_games",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("tg_id", sa.BigInteger(), nullable=False),
            sa.Column("game_external_id", sa.Integer(), nullable=False),
            sa.Column("status", sa.String(length=16), nullable=False),
            sa.Column("remind_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("tg_id", "game_external_id", name="uq_user_games_tg_game"),
        )

    existing_user_games_indexes = {idx["name"] for idx in inspector.get_indexes("user_games")}
    user_games_tg_idx = op.f("ix_user_games_tg_id")
    user_games_game_idx = op.f("ix_user_games_game_external_id")
    if user_games_tg_idx not in existing_user_games_indexes:
        op.create_index(user_games_tg_idx, "user_games", ["tg_id"], unique=False)
    if user_games_game_idx not in existing_user_games_indexes:
        op.create_index(user_games_game_idx, "user_games", ["game_external_id"], unique=False)

    existing_game_cols = {col["name"] for col in inspector.get_columns("games")}
    if "worth" not in existing_game_cols:
        op.add_column("games", sa.Column("worth", sa.String(length=32), nullable=True))


def downgrade() -> None:
    op.drop_column("games", "worth")
    op.drop_index(op.f("ix_user_games_game_external_id"), table_name="user_games")
    op.drop_index(op.f("ix_user_games_tg_id"), table_name="user_games")
    op.drop_table("user_games")
