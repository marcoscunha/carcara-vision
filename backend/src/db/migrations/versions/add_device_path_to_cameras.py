"""Add device_path column to cameras table

Revision ID: a1b2c3d4e5f6
Revises: add_stream_name_001
Create Date: 2026-02-07

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = 'add_stream_name_001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('cameras', sa.Column('device_path', sa.String(), nullable=True))

    # Back-fill existing local cameras: set device_path = '/dev/video{device_id}'
    # so they keep working until the next scan resolves persistent paths.
    op.execute(
        "UPDATE cameras SET device_path = '/dev/video' || device_id "
        "WHERE camera_type IN ('local', 'usb') AND device_id IS NOT NULL AND device_path IS NULL"
    )


def downgrade() -> None:
    op.drop_column('cameras', 'device_path')
