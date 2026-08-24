"""add pre-tenant professional signup links

Revision ID: b7a4f2c81e90
Revises: 8d91f6a3e2c4
Create Date: 2026-08-24 21:15:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b7a4f2c81e90"
down_revision: Union[str, Sequence[str], None] = "8d91f6a3e2c4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "signup_links",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("requested_ip_hash", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_signup_links_email"), "signup_links", ["email"], unique=False)
    op.create_index(
        op.f("ix_signup_links_token_hash"), "signup_links", ["token_hash"], unique=True
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_signup_links_token_hash"), table_name="signup_links")
    op.drop_index(op.f("ix_signup_links_email"), table_name="signup_links")
    op.drop_table("signup_links")
