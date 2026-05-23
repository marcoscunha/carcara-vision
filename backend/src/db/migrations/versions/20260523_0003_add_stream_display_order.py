"""add display_order to streams

Revision ID: 20260523_0003
Revises: 20260322_0002
Create Date: 2026-05-23 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "20260523_0003"
down_revision = "20260322_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "streams",
        sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_streams_display_order", "streams", ["display_order"])
    # Seed existing rows so initial order matches insertion order (by id).
    op.execute("UPDATE streams SET display_order = id")


def downgrade() -> None:
    op.drop_index("ix_streams_display_order", table_name="streams")
    op.drop_column("streams", "display_order")
