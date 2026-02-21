"""baseline schema

Revision ID: 20260221_0001
Revises:
Create Date: 2026-02-21 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "20260221_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "cameras",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("camera_type", sa.String(), nullable=True),
        sa.Column("device_id", sa.Integer(), nullable=True),
        sa.Column("device_path", sa.String(), nullable=True),
        sa.Column("rtsp_url", sa.String(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_cameras_id"), "cameras", ["id"], unique=False)
    op.create_index(op.f("ix_cameras_name"), "cameras", ["name"], unique=False)
    op.create_index(op.f("ix_cameras_rtsp_url"), "cameras", ["rtsp_url"], unique=True)

    op.create_table(
        "streams",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("camera_id", sa.Integer(), nullable=True),
        sa.Column("stream_name", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=True),
        sa.Column("current_frame", sa.Integer(), nullable=True),
        sa.Column("stream_metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["camera_id"], ["cameras.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_streams_id"), "streams", ["id"], unique=False)
    op.create_index(op.f("ix_streams_stream_name"), "streams", ["stream_name"], unique=True)

    op.create_table(
        "alarms",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("camera_id", sa.Integer(), nullable=True),
        sa.Column("class_name", sa.String(), nullable=True),
        sa.Column("confidence_threshold", sa.Float(), nullable=True),
        sa.Column("region_of_interest", sa.JSON(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["camera_id"], ["cameras.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_alarms_id"), "alarms", ["id"], unique=False)

    op.create_table(
        "roi",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("camera_id", sa.Integer(), nullable=True),
        sa.Column("points", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["camera_id"], ["cameras.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_roi_id"), "roi", ["id"], unique=False)

    op.create_table(
        "detections",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("camera_id", sa.Integer(), nullable=True),
        sa.Column("stream_id", sa.Integer(), nullable=True),
        sa.Column("frame_number", sa.Integer(), nullable=True),
        sa.Column("timestamp", sa.DateTime(), nullable=True),
        sa.Column("detection_model_name", sa.String(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("class_name", sa.String(), nullable=True),
        sa.Column("bbox", sa.JSON(), nullable=True),
        sa.Column("detection_metadata", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(["camera_id"], ["cameras.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["stream_id"], ["streams.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_detections_id"), "detections", ["id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_detections_id"), table_name="detections")
    op.drop_table("detections")

    op.drop_index(op.f("ix_roi_id"), table_name="roi")
    op.drop_table("roi")

    op.drop_index(op.f("ix_alarms_id"), table_name="alarms")
    op.drop_table("alarms")

    op.drop_index(op.f("ix_streams_stream_name"), table_name="streams")
    op.drop_index(op.f("ix_streams_id"), table_name="streams")
    op.drop_table("streams")

    op.drop_index(op.f("ix_cameras_rtsp_url"), table_name="cameras")
    op.drop_index(op.f("ix_cameras_name"), table_name="cameras")
    op.drop_index(op.f("ix_cameras_id"), table_name="cameras")
    op.drop_table("cameras")
