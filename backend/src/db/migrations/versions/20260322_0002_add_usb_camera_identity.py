"""add usb camera identity fields

Revision ID: 20260322_0002
Revises: 20260221_0001
Create Date: 2026-03-22 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "20260322_0002"
down_revision = "20260221_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("cameras", sa.Column("physical_address", sa.String(), nullable=True))
    op.add_column("cameras", sa.Column("usb_vendor_id", sa.String(), nullable=True))
    op.add_column("cameras", sa.Column("usb_product_id", sa.String(), nullable=True))
    op.add_column("cameras", sa.Column("usb_serial_number", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("cameras", "usb_serial_number")
    op.drop_column("cameras", "usb_product_id")
    op.drop_column("cameras", "usb_vendor_id")
    op.drop_column("cameras", "physical_address")
