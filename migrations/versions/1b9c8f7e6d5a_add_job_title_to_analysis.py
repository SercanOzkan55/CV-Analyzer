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
    # Check if 'job_title' column already exists
    from sqlalchemy import inspect
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = [col['name'] for col in inspector.get_columns('analysis')]
    if 'job_title' not in columns:
        op.add_column("analysis", sa.Column("job_title", sa.String(), nullable=True))
        op.create_index("ix_analysis_job_title", "analysis", ["job_title"], unique=False)
    else:
        # Only create index if not exists
        indexes = [ix['name'] for ix in inspector.get_indexes('analysis')]
        if 'ix_analysis_job_title' not in indexes:
            op.create_index("ix_analysis_job_title", "analysis", ["job_title"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_analysis_job_title", table_name="analysis")
    op.drop_column("analysis", "job_title")
