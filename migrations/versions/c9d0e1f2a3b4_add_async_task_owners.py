"""add_async_task_owners

Revision ID: c9d0e1f2a3b4
Revises: c2d3e4f5a6b7
Create Date: 2026-06-13 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c9d0e1f2a3b4"
down_revision: Union[str, Sequence[str], None] = "c2d3e4f5a6b7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "async_task_owners",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("task_id", sa.String(), nullable=False),
        sa.Column("task_type", sa.String(), nullable=False, server_default="analysis"),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["app_users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("task_id"),
    )
    op.create_index(op.f("ix_async_task_owners_task_id"), "async_task_owners", ["task_id"], unique=False)
    op.create_index(op.f("ix_async_task_owners_task_type"), "async_task_owners", ["task_type"], unique=False)
    op.create_index(op.f("ix_async_task_owners_user_id"), "async_task_owners", ["user_id"], unique=False)
    op.create_index(op.f("ix_async_task_owners_organization_id"), "async_task_owners", ["organization_id"], unique=False)
    op.create_index(op.f("ix_async_task_owners_created_at"), "async_task_owners", ["created_at"], unique=False)
    op.create_index(op.f("ix_async_task_owners_expires_at"), "async_task_owners", ["expires_at"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_async_task_owners_expires_at"), table_name="async_task_owners")
    op.drop_index(op.f("ix_async_task_owners_created_at"), table_name="async_task_owners")
    op.drop_index(op.f("ix_async_task_owners_organization_id"), table_name="async_task_owners")
    op.drop_index(op.f("ix_async_task_owners_user_id"), table_name="async_task_owners")
    op.drop_index(op.f("ix_async_task_owners_task_type"), table_name="async_task_owners")
    op.drop_index(op.f("ix_async_task_owners_task_id"), table_name="async_task_owners")
    op.drop_table("async_task_owners")
