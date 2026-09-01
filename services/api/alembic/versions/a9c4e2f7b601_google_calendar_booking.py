"""add tenant-scoped Google Calendar connections and bookings

Revision ID: a9c4e2f7b601
Revises: f7e9a1b3c5d7
Create Date: 2026-09-01
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a9c4e2f7b601"
down_revision: str | Sequence[str] | None = "f7e9a1b3c5d7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "calendar_connections",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("account_id", sa.String(length=36), nullable=False),
        sa.Column("space_id", sa.String(length=36), nullable=False),
        sa.Column("connected_by_member_id", sa.String(length=36), nullable=False),
        sa.Column("provider", sa.String(length=24), nullable=False),
        sa.Column("provider_email", sa.String(length=320), nullable=False),
        sa.Column("refresh_token_encrypted", sa.LargeBinary(), nullable=False),
        sa.Column("access_token_encrypted", sa.LargeBinary(), nullable=True),
        sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("booking_enabled", sa.Boolean(), nullable=False),
        sa.Column("timezone", sa.String(length=80), nullable=False),
        sa.Column("work_days", sa.JSON(), nullable=False),
        sa.Column("day_start", sa.String(length=5), nullable=False),
        sa.Column("day_end", sa.String(length=5), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column("slot_interval_minutes", sa.Integer(), nullable=False),
        sa.Column("buffer_minutes", sa.Integer(), nullable=False),
        sa.Column("minimum_notice_minutes", sa.Integer(), nullable=False),
        sa.Column("appointment_title", sa.String(length=200), nullable=False),
        sa.Column("location", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["space_id"], ["spaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["connected_by_member_id"], ["members.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("space_id", name="uq_calendar_connection_space"),
    )
    op.create_index("ix_calendar_connections_account_id", "calendar_connections", ["account_id"])
    op.create_index("ix_calendar_connections_space_id", "calendar_connections", ["space_id"])
    op.create_index(
        "ix_calendar_connections_connected_by_member_id",
        "calendar_connections",
        ["connected_by_member_id"],
    )
    op.create_index(
        "ix_calendar_connection_account_space",
        "calendar_connections",
        ["account_id", "space_id"],
    )

    op.create_table(
        "calendar_bookings",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("account_id", sa.String(length=36), nullable=False),
        sa.Column("space_id", sa.String(length=36), nullable=False),
        sa.Column("conversation_id", sa.String(length=36), nullable=False),
        sa.Column("calendar_connection_id", sa.String(length=36), nullable=True),
        sa.Column("visitor_name", sa.String(length=200), nullable=False),
        sa.Column("visitor_email", sa.String(length=320), nullable=False),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("timezone", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("provider_event_id", sa.String(length=998), nullable=True),
        sa.Column("provider_event_link", sa.String(length=2000), nullable=True),
        sa.Column("idempotency_key", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["space_id"], ["spaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["calendar_connection_id"], ["calendar_connections.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "account_id", "idempotency_key", name="uq_calendar_booking_idempotency"
        ),
        sa.UniqueConstraint(
            "account_id",
            "calendar_connection_id",
            "start_at",
            name="uq_calendar_booking_slot",
        ),
        sa.UniqueConstraint(
            "calendar_connection_id",
            "provider_event_id",
            name="uq_calendar_booking_provider_event",
        ),
    )
    op.create_index("ix_calendar_bookings_account_id", "calendar_bookings", ["account_id"])
    op.create_index("ix_calendar_bookings_space_id", "calendar_bookings", ["space_id"])
    op.create_index("ix_calendar_bookings_conversation_id", "calendar_bookings", ["conversation_id"])
    op.create_index(
        "ix_calendar_bookings_calendar_connection_id",
        "calendar_bookings",
        ["calendar_connection_id"],
    )
    op.create_index(
        "ix_calendar_booking_account_conversation",
        "calendar_bookings",
        ["account_id", "conversation_id"],
    )


def downgrade() -> None:
    op.drop_table("calendar_bookings")
    op.drop_table("calendar_connections")
