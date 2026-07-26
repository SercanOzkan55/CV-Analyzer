"""add usage reset timestamps

Revision ID: d7f8a9b0c1d2
Revises: 82d43dbf7da4
Create Date: 2026-07-25
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d7f8a9b0c1d2"
down_revision: Union[str, Sequence[str], None] = "82d43dbf7da4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("organizations", sa.Column("usage_reset_at", sa.DateTime(), nullable=True))
    op.add_column("api_subscriptions", sa.Column("usage_reset_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("api_subscriptions", "usage_reset_at")
    op.drop_column("organizations", "usage_reset_at")
