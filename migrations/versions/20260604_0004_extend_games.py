"""extend games table with end_date, thumbnail, platforms, description, open_giveaway_url

Revision ID: 20260604_0004
Revises: 20260419_0003
Create Date: 2026-06-04 00:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260604_0004"
down_revision = "20260419_0003"
branch_labels = None
depends_on = None


NEW_COLUMNS: dict[str, sa.types.TypeEngine] = {
    "end_date": sa.String(length=32),
    "thumbnail": sa.String(length=1024),
    "platforms": sa.String(length=512),
    "description": sa.String(length=2000),
    "open_giveaway_url": sa.String(length=1024),
}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_cols = {col["name"] for col in inspector.get_columns("games")}
    for col_name, col_type in NEW_COLUMNS.items():
        if col_name not in existing_cols:
            op.add_column("games", sa.Column(col_name, col_type, nullable=True))


def downgrade() -> None:
    for col_name in NEW_COLUMNS:
        op.drop_column("games", col_name)
