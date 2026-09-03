"""add consent-qualified outreach campaigns

Revision ID: d4f6a8c9b012
Revises: b7a4f2c81e90
Create Date: 2026-08-27 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d4f6a8c9b012"
down_revision: str | Sequence[str] | None = "b7a4f2c81e90"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "outreach_campaigns",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("account_id", sa.String(length=36), nullable=False),
        sa.Column("space_id", sa.String(length=36), nullable=False),
        sa.Column("studio_conversation_id", sa.String(length=36), nullable=False),
        sa.Column("source_message_id", sa.String(length=36), nullable=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("landing_url", sa.String(length=1000), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("recipient_cap", sa.Integer(), nullable=False),
        sa.Column("authorized_by_member_id", sa.String(length=36), nullable=True),
        sa.Column("authorized_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["space_id"], ["spaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["studio_conversation_id"], ["conversations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["source_message_id"], ["messages.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_outreach_campaign_account_space",
        "outreach_campaigns",
        ["account_id", "space_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_outreach_campaigns_account_id"),
        "outreach_campaigns",
        ["account_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_outreach_campaigns_source_message_id"),
        "outreach_campaigns",
        ["source_message_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_outreach_campaigns_space_id"),
        "outreach_campaigns",
        ["space_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_outreach_campaigns_studio_conversation_id"),
        "outreach_campaigns",
        ["studio_conversation_id"],
        unique=False,
    )

    op.create_table(
        "outreach_recipients",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("account_id", sa.String(length=36), nullable=False),
        sa.Column("space_id", sa.String(length=36), nullable=False),
        sa.Column("campaign_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column("source_url", sa.String(length=1000), nullable=False),
        sa.Column("source_label", sa.String(length=300), nullable=True),
        sa.Column("personalization_note", sa.Text(), nullable=True),
        sa.Column("permission_basis", sa.String(length=48), nullable=False),
        sa.Column("permission_evidence", sa.Text(), nullable=True),
        sa.Column("permission_recorded_by_member_id", sa.String(length=36), nullable=True),
        sa.Column("permission_source_message_id", sa.String(length=36), nullable=True),
        sa.Column("permission_recorded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("unsubscribe_token_hash", sa.String(length=64), nullable=True),
        sa.Column("unsubscribe_requested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("professional_email_id", sa.String(length=36), nullable=True),
        sa.Column("retention_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["campaign_id"], ["outreach_campaigns.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["space_id"], ["spaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["permission_source_message_id"], ["messages.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("campaign_id", "email", name="uq_outreach_campaign_email"),
    )
    op.create_index(
        "ix_outreach_recipient_account_campaign",
        "outreach_recipients",
        ["account_id", "campaign_id"],
        unique=False,
    )
    for column in (
        "account_id",
        "campaign_id",
        "professional_email_id",
        "permission_source_message_id",
        "space_id",
    ):
        op.create_index(
            op.f(f"ix_outreach_recipients_{column}"),
            "outreach_recipients",
            [column],
            unique=False,
        )
    op.create_index(
        op.f("ix_outreach_recipients_unsubscribe_token_hash"),
        "outreach_recipients",
        ["unsubscribe_token_hash"],
        unique=True,
    )

    op.create_table(
        "outreach_suppressions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("account_id", sa.String(length=36), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("reason", sa.String(length=80), nullable=False),
        sa.Column("source", sa.String(length=40), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("account_id", "email", name="uq_outreach_suppression_email"),
    )
    op.create_index(
        op.f("ix_outreach_suppressions_account_id"),
        "outreach_suppressions",
        ["account_id"],
        unique=False,
    )

    with op.batch_alter_table("professional_emails") as batch_op:
        batch_op.add_column(sa.Column("outreach_campaign_id", sa.String(length=36)))
        batch_op.add_column(sa.Column("outreach_recipient_id", sa.String(length=36)))
        batch_op.create_foreign_key(
            "fk_professional_email_outreach_campaign",
            "outreach_campaigns",
            ["outreach_campaign_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_foreign_key(
            "fk_professional_email_outreach_recipient",
            "outreach_recipients",
            ["outreach_recipient_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_index(
            op.f("ix_professional_emails_outreach_campaign_id"),
            ["outreach_campaign_id"],
            unique=False,
        )
        batch_op.create_index(
            op.f("ix_professional_emails_outreach_recipient_id"),
            ["outreach_recipient_id"],
            unique=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("professional_emails") as batch_op:
        batch_op.drop_index(op.f("ix_professional_emails_outreach_recipient_id"))
        batch_op.drop_index(op.f("ix_professional_emails_outreach_campaign_id"))
        batch_op.drop_constraint(
            "fk_professional_email_outreach_recipient", type_="foreignkey"
        )
        batch_op.drop_constraint(
            "fk_professional_email_outreach_campaign", type_="foreignkey"
        )
        batch_op.drop_column("outreach_recipient_id")
        batch_op.drop_column("outreach_campaign_id")

    op.drop_index(op.f("ix_outreach_suppressions_account_id"), table_name="outreach_suppressions")
    op.drop_table("outreach_suppressions")
    op.drop_index(
        op.f("ix_outreach_recipients_unsubscribe_token_hash"),
        table_name="outreach_recipients",
    )
    for column in (
        "space_id",
        "professional_email_id",
        "permission_source_message_id",
        "campaign_id",
        "account_id",
    ):
        op.drop_index(
            op.f(f"ix_outreach_recipients_{column}"),
            table_name="outreach_recipients",
        )
    op.drop_index(
        "ix_outreach_recipient_account_campaign", table_name="outreach_recipients"
    )
    op.drop_table("outreach_recipients")
    for column in (
        "studio_conversation_id",
        "space_id",
        "source_message_id",
        "account_id",
    ):
        op.drop_index(
            op.f(f"ix_outreach_campaigns_{column}"),
            table_name="outreach_campaigns",
        )
    op.drop_index("ix_outreach_campaign_account_space", table_name="outreach_campaigns")
    op.drop_table("outreach_campaigns")
