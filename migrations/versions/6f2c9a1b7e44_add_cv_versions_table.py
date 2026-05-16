"""Add cv_versions table for CV version history

Revision ID: 6f2c9a1b7e44
Revises: merge_heads_20260305
Create Date: 2026-03-12
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "6f2c9a1b7e44"
down_revision: Union[str, Sequence[str], None] = "merge_heads_20260305"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "cv_versions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("app_users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=True),
        sa.Column("version_label", sa.String(), nullable=False, server_default="v1"),
        sa.Column("source", sa.String(), nullable=False, server_default="manual"),
        sa.Column("lang", sa.String(), nullable=False, server_default="en"),
        sa.Column("cv_text", sa.Text(), nullable=False),
        sa.Column("optimized_cv_text", sa.Text(), nullable=True),
        sa.Column("job_description", sa.Text(), nullable=True),
        sa.Column("match_score", sa.Float(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_cv_versions_user_id", "cv_versions", ["user_id"])
    op.create_index("ix_cv_versions_organization_id", "cv_versions", ["organization_id"])
    op.create_index("ix_cv_versions_created_at", "cv_versions", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_cv_versions_created_at", table_name="cv_versions")
    op.drop_index("ix_cv_versions_organization_id", table_name="cv_versions")
    op.drop_index("ix_cv_versions_user_id", table_name="cv_versions")
    op.drop_table("cv_versions")
