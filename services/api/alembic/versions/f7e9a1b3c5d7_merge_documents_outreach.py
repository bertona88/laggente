"""merge document and outreach migration heads

Revision ID: f7e9a1b3c5d7
Revises: c2d4e6f8a1b3, d4f6a8c9b012
Create Date: 2026-08-27
"""

from collections.abc import Sequence


revision: str = "f7e9a1b3c5d7"
down_revision: str | Sequence[str] | None = (
    "c2d4e6f8a1b3",
    "d4f6a8c9b012",
)
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
