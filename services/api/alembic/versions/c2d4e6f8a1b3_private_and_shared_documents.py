"""private and shared documents

Revision ID: c2d4e6f8a1b3
Revises: b7a4f2c81e90
Create Date: 2026-08-25
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "c2d4e6f8a1b3"
down_revision: Union[str, Sequence[str], None] = "b7a4f2c81e90"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "documents",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("account_id", sa.String(length=36), nullable=False),
        sa.Column("space_id", sa.String(length=36), nullable=False),
        sa.Column("conversation_id", sa.String(length=36), nullable=True),
        sa.Column("message_id", sa.String(length=36), nullable=True),
        sa.Column("scope", sa.String(length=24), nullable=False),
        sa.Column("uploader_type", sa.String(length=32), nullable=False),
        sa.Column("uploader_id", sa.String(length=100), nullable=True),
        sa.Column("storage_key", sa.String(length=500), nullable=False),
        sa.Column("original_name", sa.String(length=255), nullable=False),
        sa.Column("media_type", sa.String(length=160), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("extracted_text", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["space_id"], ["spaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["message_id"], ["messages.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("storage_key"),
    )
    op.create_index("ix_documents_account_id", "documents", ["account_id"], unique=False)
    op.create_index("ix_documents_space_id", "documents", ["space_id"], unique=False)
    op.create_index("ix_documents_conversation_id", "documents", ["conversation_id"], unique=False)
    op.create_index("ix_documents_message_id", "documents", ["message_id"], unique=False)
    op.create_index(
        "ix_document_account_space_scope",
        "documents",
        ["account_id", "space_id", "scope"],
        unique=False,
    )
    op.create_index(
        "ix_document_account_conversation",
        "documents",
        ["account_id", "conversation_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_document_account_conversation", table_name="documents")
    op.drop_index("ix_document_account_space_scope", table_name="documents")
    op.drop_index("ix_documents_message_id", table_name="documents")
    op.drop_index("ix_documents_conversation_id", table_name="documents")
    op.drop_index("ix_documents_space_id", table_name="documents")
    op.drop_index("ix_documents_account_id", table_name="documents")
    op.drop_table("documents")
