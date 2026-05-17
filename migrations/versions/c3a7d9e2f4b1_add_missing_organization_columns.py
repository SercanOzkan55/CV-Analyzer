"""add missing organization columns

Revision ID: c3a7d9e2f4b1
Revises: 7ef8e3bde0ec
Create Date: 2026-05-17
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "c3a7d9e2f4b1"
down_revision: Union[str, Sequence[str], None] = "7ef8e3bde0ec"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return column_name in {column["name"] for column in inspector.get_columns(table_name)}


def _has_index(table_name: str, index_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return index_name in {index["name"] for index in inspector.get_indexes(table_name)}


def upgrade() -> None:
    if not _has_column("organizations", "stripe_customer_id"):
        op.add_column("organizations", sa.Column("stripe_customer_id", sa.String(), nullable=True))
    if not _has_index("organizations", "ix_organizations_stripe_customer_id"):
        op.create_index(
            "ix_organizations_stripe_customer_id",
            "organizations",
            ["stripe_customer_id"],
            unique=False,
        )

    if not _has_column("organizations", "cv_credit_limit"):
        op.add_column(
            "organizations",
            sa.Column("cv_credit_limit", sa.Integer(), server_default="100", nullable=True),
        )


def downgrade() -> None:
    if _has_column("organizations", "cv_credit_limit"):
        op.drop_column("organizations", "cv_credit_limit")

    if _has_column("organizations", "stripe_customer_id"):
        if _has_index("organizations", "ix_organizations_stripe_customer_id"):
            op.drop_index("ix_organizations_stripe_customer_id", table_name="organizations")
        op.drop_column("organizations", "stripe_customer_id")
