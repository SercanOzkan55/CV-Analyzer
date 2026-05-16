"""rename users to app_users

Revision ID: 2a2ae8f5f8c3
Revises: 01cc20e2945c
Create Date: 2026-03-03 14:41:35.156709

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "2a2ae8f5f8c3"
down_revision: Union[str, Sequence[str], None] = "01cc20e2945c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(table_name: str) -> bool:
    return table_name in set(sa.inspect(op.get_bind()).get_table_names())


def _column_exists(table_name: str, column_name: str) -> bool:
    if not _table_exists(table_name):
        return False
    columns = sa.inspect(op.get_bind()).get_columns(table_name)
    return any(column["name"] == column_name for column in columns)


def _create_app_users_table() -> None:
    op.create_table(
        "app_users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("supabase_id", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("plan_type", sa.String(), server_default="free", nullable=False),
        sa.Column("billing_status", sa.String(), server_default="trialing", nullable=False),
        sa.Column("stripe_customer_id", sa.String(), nullable=True),
        sa.Column("daily_usage", sa.Integer(), server_default="0", nullable=True),
        sa.Column("monthly_usage", sa.Integer(), server_default="0", nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )


def upgrade() -> None:
    """Upgrade schema.

    Rename the existing ``users`` table to ``app_users`` and add the
    ``last_reset`` column used by the quota system.  We deliberately do
    **not** drop or recreate any of the legacy tables; those are managed
    separately and should remain untouched.
    """
    # Rename legacy databases. Fresh CI/dev databases already get app_users
    # from the baseline migration, so this must be safe in both directions.
    if _table_exists("users") and not _table_exists("app_users"):
        op.rename_table("users", "app_users")
    elif not _table_exists("app_users"):
        _create_app_users_table()

    # add new column with nullable=True so existing rows stay valid
    if not _column_exists("app_users", "last_reset"):
        op.add_column("app_users", sa.Column("last_reset", sa.DateTime(), nullable=True))


def downgrade() -> None:
    """Downgrade schema.

    Reverse the rename and drop the ``last_reset`` column.
    """
    op.drop_column("app_users", "last_reset")
    op.rename_table("app_users", "users")
