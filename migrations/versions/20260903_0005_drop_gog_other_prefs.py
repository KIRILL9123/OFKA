"""drop users.pref_gog and users.pref_other — only Steam and Epic are supported

Revision ID: 20260903_0005
Revises: 20260604_0004
Create Date: 2026-09-03 00:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260903_0005"
down_revision = "20260604_0004"
branch_labels = None
depends_on = None

DROPPED_COLUMNS = ("pref_gog", "pref_other")


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_cols = {col["name"] for col in inspector.get_columns("users")}
    cols_to_drop = [name for name in DROPPED_COLUMNS if name in existing_cols]
    if not cols_to_drop:
        return

    # SQLite needs batch mode (table recreate) to drop columns.
    with op.batch_alter_table("users") as batch_op:
        for name in cols_to_drop:
            batch_op.drop_column(name)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_cols = {col["name"] for col in inspector.get_columns("users")}

    with op.batch_alter_table("users") as batch_op:
        if "pref_gog" not in existing_cols:
            batch_op.add_column(
                sa.Column("pref_gog", sa.Boolean(), nullable=False, server_default=sa.text("0"))
            )
        if "pref_other" not in existing_cols:
            batch_op.add_column(
                sa.Column("pref_other", sa.Boolean(), nullable=False, server_default=sa.text("0"))
            )
