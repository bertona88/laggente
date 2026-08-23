"""add invited professional space lifecycle

Revision ID: 8d91f6a3e2c4
Revises: 5258d1a3248a
Create Date: 2026-08-23 10:15:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "8d91f6a3e2c4"
down_revision: Union[str, Sequence[str], None] = "5258d1a3248a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "members",
        sa.Column("can_invite", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    # Every member that predates invitations belongs to the closed pilot operator cohort. New
    # invitees use the model default (false), so invitation authority does not propagate.
    op.execute(sa.text("UPDATE members SET can_invite = true"))
    op.add_column(
        "spaces",
        sa.Column("slug_claimed", sa.Boolean(), server_default=sa.true(), nullable=False),
    )
    op.add_column(
        "spaces",
        sa.Column(
            "onboarding_state",
            sa.String(length=24),
            server_default="published",
            nullable=False,
        ),
    )
    op.add_column(
        "magic_links",
        sa.Column("purpose", sa.String(length=40), server_default="login", nullable=False),
    )
    op.add_column(
        "magic_links",
        sa.Column("created_by_member_id", sa.String(length=36), nullable=True),
    )
    op.create_index(
        op.f("ix_magic_links_purpose"), "magic_links", ["purpose"], unique=False
    )
    op.create_index(
        op.f("ix_magic_links_created_by_member_id"),
        "magic_links",
        ["created_by_member_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_magic_links_created_by_member_id"), table_name="magic_links")
    op.drop_index(op.f("ix_magic_links_purpose"), table_name="magic_links")
    op.drop_column("magic_links", "created_by_member_id")
    op.drop_column("magic_links", "purpose")
    op.drop_column("spaces", "onboarding_state")
    op.drop_column("spaces", "slug_claimed")
    op.drop_column("members", "can_invite")
