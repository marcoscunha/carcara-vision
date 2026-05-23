"""alarms v2: stream-scoped rules, polygon zones, event lifecycle

Revision ID: 20260523_0004
Revises: 20260523_0003
Create Date: 2026-05-23 12:30:00.000000

This migration is intentionally destructive for the legacy ``alarms`` table.
The previous schema was camera-scoped and never wired to the inference
worker, so no production data depends on it.

It introduces:
  * ``alarm_zones``   — named polygon zones attached to a stream
                        (normalized [0..1] coordinates).
  * ``alarms``        — rebuilt: stream-scoped rules with a discriminated
                        ``trigger_type`` / ``trigger_config``, hysteresis,
                        storage and notification options.
  * ``alarm_events``  — lifecycle rows (open → closed → acknowledged) with
                        snapshot/clip paths and the rule snapshot at trigger
                        time.
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "20260523_0004"
down_revision = "20260523_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Drop the legacy alarms table ─────────────────────────────────────
    op.drop_index(op.f("ix_alarms_id"), table_name="alarms")
    op.drop_table("alarms")

    # ── alarm_zones ──────────────────────────────────────────────────────
    op.create_table(
        "alarm_zones",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("stream_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("polygon", sa.JSON(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["stream_id"], ["streams.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_alarm_zones_stream_id", "alarm_zones", ["stream_id"])

    # ── alarms (v2) ──────────────────────────────────────────────────────
    op.create_table(
        "alarms",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("stream_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "severity",
            sa.String(),
            nullable=False,
            server_default="warning",
        ),
        sa.Column("trigger_type", sa.String(), nullable=False),
        sa.Column("trigger_config", sa.JSON(), nullable=False),
        sa.Column("zone_id", sa.Integer(), nullable=True),
        sa.Column("min_on_seconds", sa.Float(), nullable=False, server_default="0"),
        sa.Column("min_off_seconds", sa.Float(), nullable=False, server_default="2"),
        sa.Column("cooldown_seconds", sa.Float(), nullable=False, server_default="0"),
        sa.Column("schedule", sa.JSON(), nullable=True),
        sa.Column("store_events", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("store_snapshot", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("store_clip_seconds", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("notify_channels", sa.JSON(), nullable=False, server_default=sa.text("'[\"ws\"]'")),
        sa.Column("webhook_url", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["stream_id"], ["streams.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["zone_id"], ["alarm_zones.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_alarms_stream_id", "alarms", ["stream_id"])
    op.create_index("ix_alarms_is_active", "alarms", ["is_active"])

    # ── alarm_events ─────────────────────────────────────────────────────
    op.create_table(
        "alarm_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("alarm_id", sa.Integer(), nullable=False),
        sa.Column("stream_id", sa.Integer(), nullable=False),
        sa.Column("zone_id", sa.Integer(), nullable=True),
        sa.Column("state", sa.String(), nullable=False, server_default="open"),
        sa.Column("started_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("ended_at", sa.DateTime(), nullable=True),
        sa.Column("peak_confidence", sa.Float(), nullable=True),
        sa.Column("peak_count", sa.Integer(), nullable=True),
        sa.Column("matched_classes", sa.JSON(), nullable=True),
        sa.Column("matched_track_ids", sa.JSON(), nullable=True),
        sa.Column("rule_snapshot", sa.JSON(), nullable=False),
        sa.Column("snapshot_path", sa.String(), nullable=True),
        sa.Column("clip_path", sa.String(), nullable=True),
        sa.Column("acknowledged_at", sa.DateTime(), nullable=True),
        sa.Column("acknowledged_by", sa.String(), nullable=True),
        sa.Column("ack_note", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(["alarm_id"], ["alarms.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["stream_id"], ["streams.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["zone_id"], ["alarm_zones.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_alarm_events_alarm_id", "alarm_events", ["alarm_id"])
    op.create_index("ix_alarm_events_stream_id", "alarm_events", ["stream_id"])
    op.create_index("ix_alarm_events_state", "alarm_events", ["state"])
    op.create_index("ix_alarm_events_started_at", "alarm_events", ["started_at"])


def downgrade() -> None:
    op.drop_index("ix_alarm_events_started_at", table_name="alarm_events")
    op.drop_index("ix_alarm_events_state", table_name="alarm_events")
    op.drop_index("ix_alarm_events_stream_id", table_name="alarm_events")
    op.drop_index("ix_alarm_events_alarm_id", table_name="alarm_events")
    op.drop_table("alarm_events")

    op.drop_index("ix_alarms_is_active", table_name="alarms")
    op.drop_index("ix_alarms_stream_id", table_name="alarms")
    op.drop_table("alarms")

    op.drop_index("ix_alarm_zones_stream_id", table_name="alarm_zones")
    op.drop_table("alarm_zones")

    # Recreate legacy alarms table to match prior baseline schema.
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
