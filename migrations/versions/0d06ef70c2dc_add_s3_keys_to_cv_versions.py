"""Add S3 key columns to cv_versions

Revision ID: 0d06ef70c2dc
Revises: 6f2c9a1b7e44
Create Date: 2026-03-23
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0d06ef70c2dc"
down_revision: Union[str, Sequence[str], None] = "6f2c9a1b7e44"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("cv_versions", sa.Column("original_s3_key", sa.String(), nullable=True))
    op.add_column("cv_versions", sa.Column("optimized_s3_key", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("cv_versions", "optimized_s3_key")
    op.drop_column("cv_versions", "original_s3_key")
