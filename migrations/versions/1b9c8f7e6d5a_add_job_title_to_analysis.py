"""add job_title to analysis

Revision ID: 1b9c8f7e6d5a
Revises: merge_heads_20260305
Create Date: 2026-03-08
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "1b9c8f7e6d5a"
down_revision: Union[str, Sequence[str], None] = "merge_heads_20260305"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("analysis", sa.Column("job_title", sa.String(), nullable=True))
    op.create_index("ix_analysis_job_title", "analysis", ["job_title"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_analysis_job_title", table_name="analysis")
    op.drop_column("analysis", "job_title")
