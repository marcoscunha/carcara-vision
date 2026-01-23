"""add stream_name column to streams table

Revision ID: add_stream_name_001
Revises: e193b5d44c2d
Create Date: 2026-01-21 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = 'add_stream_name_001'
down_revision = 'e193b5d44c2d'
branch_labels = None
depends_on = None


def column_exists(table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table."""
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns


def table_exists(table_name: str) -> bool:
    """Check if a table exists."""
    bind = op.get_bind()
    inspector = inspect(bind)
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    # Create streams table if it doesn't exist
    if not table_exists('streams'):
        op.create_table(
            'streams',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('camera_id', sa.Integer(), nullable=True),
            sa.Column('stream_name', sa.String(), nullable=True),
            sa.Column('status', sa.String(), nullable=True),
            sa.Column('current_frame', sa.Integer(), nullable=True, default=0),
            sa.Column('stream_metadata', sa.JSON(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['camera_id'], ['cameras.id'], ),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_streams_id'), 'streams', ['id'], unique=False)
        op.create_index(op.f('ix_streams_stream_name'), 'streams', ['stream_name'], unique=True)
    else:
        # Add stream_name column if it doesn't exist
        if not column_exists('streams', 'stream_name'):
            op.add_column('streams', sa.Column('stream_name', sa.String(), nullable=True))
            op.create_index(op.f('ix_streams_stream_name'), 'streams', ['stream_name'], unique=True)


def downgrade() -> None:
    # Remove stream_name column if it exists
    if table_exists('streams') and column_exists('streams', 'stream_name'):
        op.drop_index(op.f('ix_streams_stream_name'), table_name='streams')
        op.drop_column('streams', 'stream_name')
