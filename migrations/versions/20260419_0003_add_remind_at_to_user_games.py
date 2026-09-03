"""add remind_at to user_games

Revision ID: 20260419_0003
Revises: 20260419_0002
Create Date: 2026-04-19 15:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260419_0003"
down_revision = "20260419_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_cols = {col["name"] for col in inspector.get_columns("user_games")}
    if "remind_at" not in existing_cols:
        op.add_column(
            "user_games",
            sa.Column("remind_at", sa.DateTime(), nullable=True),
        )


def downgrade() -> None:
    op.drop_column("user_games", "remind_at")
