"""add delete_user rpc function

Revision ID: 9f1a2b3c4d5e
Revises: merge_heads_20260305
Create Date: 2026-03-08 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9f1a2b3c4d5e"
down_revision: Union[str, Sequence[str], None] = "merge_heads_20260305"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE OR REPLACE FUNCTION public.delete_user()
        RETURNS void
        LANGUAGE sql
        SECURITY DEFINER
        SET search_path = public
        AS $$
          DELETE FROM auth.users WHERE id = auth.uid();
        $$;
    """)
    op.execute("REVOKE ALL ON FUNCTION public.delete_user() FROM PUBLIC;")
    op.execute("GRANT EXECUTE ON FUNCTION public.delete_user() TO authenticated;")


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS public.delete_user();")
