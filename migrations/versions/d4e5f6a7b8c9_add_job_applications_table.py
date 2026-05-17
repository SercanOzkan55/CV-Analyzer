"""add job applications table

Revision ID: d4e5f6a7b8c9
Revises: c3a7d9e2f4b1
Create Date: 2026-05-17
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, Sequence[str], None] = "c3a7d9e2f4b1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "job_applications",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("app_users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=True),
        sa.Column("company", sa.String(length=200), nullable=False),
        sa.Column("role", sa.String(length=200), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="wishlist"),
        sa.Column("location", sa.String(length=200), nullable=True),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("salary", sa.String(length=120), nullable=True),
        sa.Column("priority", sa.String(length=20), nullable=False, server_default="medium"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("applied_date", sa.DateTime(), nullable=True),
        sa.Column("reminder_id", sa.Integer(), sa.ForeignKey("reminders.id", ondelete="SET NULL"), nullable=True),
        sa.Column("board_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("source", sa.String(length=80), nullable=False, server_default="manual"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_job_applications_user_id", "job_applications", ["user_id"])
    op.create_index("ix_job_applications_organization_id", "job_applications", ["organization_id"])
    op.create_index("ix_job_applications_status", "job_applications", ["status"])
    op.create_index("ix_job_applications_applied_date", "job_applications", ["applied_date"])
    op.create_index("ix_job_applications_created_at", "job_applications", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_job_applications_created_at", table_name="job_applications")
    op.drop_index("ix_job_applications_applied_date", table_name="job_applications")
    op.drop_index("ix_job_applications_status", table_name="job_applications")
    op.drop_index("ix_job_applications_organization_id", table_name="job_applications")
    op.drop_index("ix_job_applications_user_id", table_name="job_applications")
    op.drop_table("job_applications")
