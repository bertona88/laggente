"""agent-native professional email artifacts

Revision ID: 8c61d3d9b2a4
Revises: 5258d1a3248a
Create Date: 2026-08-23
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "8c61d3d9b2a4"
down_revision: Union[str, Sequence[str], None] = "5258d1a3248a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "professional_emails",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("account_id", sa.String(length=36), nullable=False),
        sa.Column("space_id", sa.String(length=36), nullable=False),
        sa.Column("studio_conversation_id", sa.String(length=36), nullable=False),
        sa.Column("source_message_id", sa.String(length=36), nullable=True),
        sa.Column("in_reply_to_email_id", sa.String(length=36), nullable=True),
        sa.Column("direction", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("from_address", sa.String(length=320), nullable=False),
        sa.Column("to_address", sa.String(length=320), nullable=False),
        sa.Column("reply_to_address", sa.String(length=320), nullable=True),
        sa.Column("subject", sa.String(length=998), nullable=False),
        sa.Column("body_text", sa.Text(), nullable=False),
        sa.Column("raw_content", sa.LargeBinary(), nullable=False),
        sa.Column("raw_sha256", sa.String(length=64), nullable=False),
        sa.Column("content_sha256", sa.String(length=64), nullable=False),
        sa.Column("internet_message_id", sa.String(length=998), nullable=True),
        sa.Column("provider", sa.String(length=40), nullable=True),
        sa.Column("provider_message_id", sa.String(length=998), nullable=True),
        sa.Column("proposed_by_member_id", sa.String(length=36), nullable=True),
        sa.Column("authorized_by_member_id", sa.String(length=36), nullable=True),
        sa.Column("authorized_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_code", sa.String(length=120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["space_id"], ["spaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["studio_conversation_id"], ["conversations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["source_message_id"], ["messages.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["in_reply_to_email_id"], ["professional_emails.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "provider", "provider_message_id", name="uq_professional_email_provider_message"
        ),
    )
    op.create_index(
        "ix_professional_email_account_space",
        "professional_emails",
        ["account_id", "space_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_professional_emails_account_id"),
        "professional_emails",
        ["account_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_professional_emails_space_id"),
        "professional_emails",
        ["space_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_professional_emails_studio_conversation_id"),
        "professional_emails",
        ["studio_conversation_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_professional_emails_source_message_id"),
        "professional_emails",
        ["source_message_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_professional_emails_in_reply_to_email_id"),
        "professional_emails",
        ["in_reply_to_email_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_professional_emails_in_reply_to_email_id"),
        table_name="professional_emails",
    )
    op.drop_index(
        op.f("ix_professional_emails_source_message_id"), table_name="professional_emails"
    )
    op.drop_index(
        op.f("ix_professional_emails_studio_conversation_id"),
        table_name="professional_emails",
    )
    op.drop_index(op.f("ix_professional_emails_space_id"), table_name="professional_emails")
    op.drop_index(op.f("ix_professional_emails_account_id"), table_name="professional_emails")
    op.drop_index("ix_professional_email_account_space", table_name="professional_emails")
    op.drop_table("professional_emails")
