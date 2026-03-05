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


def upgrade() -> None:
    """Upgrade schema.

    Rename the existing ``users`` table to ``app_users`` and add the
    ``last_reset`` column used by the quota system.  We deliberately do
    **not** drop or recreate any of the legacy tables; those are managed
    separately and should remain untouched.
    """
    # rename table, preserving indexes/constraints automatically
    op.rename_table("users", "app_users")

    # add new column with nullable=True so existing rows stay valid
    op.add_column("app_users", sa.Column("last_reset", sa.DateTime(), nullable=True))


def downgrade() -> None:
    """Downgrade schema.

    Reverse the rename and drop the ``last_reset`` column.
    """
    op.drop_column("app_users", "last_reset")
    op.rename_table("app_users", "users")
