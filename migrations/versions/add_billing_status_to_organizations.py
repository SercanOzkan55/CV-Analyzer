"""add billing_status to organizations

Revision ID: add_billing_status_to_organizations
Revises: 4bb2cf15d957
Create Date: 2026-03-04
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "add_billing_status_to_organizations"
down_revision = "4bb2cf15d957"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "organizations", sa.Column("billing_status", sa.String(), nullable=True)
    )


def downgrade():
    op.drop_column("organizations", "billing_status")
