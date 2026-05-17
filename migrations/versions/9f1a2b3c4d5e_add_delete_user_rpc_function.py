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
        DO $$
        DECLARE
          has_supabase_auth boolean;
          has_authenticated_role boolean;
        BEGIN
          SELECT
            to_regclass('auth.users') IS NOT NULL
            AND to_regprocedure('auth.uid()') IS NOT NULL
          INTO has_supabase_auth;

          IF has_supabase_auth THEN
            EXECUTE $create_fn$
              CREATE OR REPLACE FUNCTION public.delete_user()
              RETURNS void
              LANGUAGE sql
              SECURITY DEFINER
              SET search_path = public
              AS $body$
                DELETE FROM auth.users WHERE id = auth.uid();
              $body$;
            $create_fn$;
          ELSE
            EXECUTE $create_fn$
              CREATE OR REPLACE FUNCTION public.delete_user()
              RETURNS void
              LANGUAGE plpgsql
              SECURITY DEFINER
              SET search_path = public
              AS $body$
              BEGIN
                RAISE NOTICE 'delete_user RPC is unavailable without Supabase auth schema';
                RETURN;
              END;
              $body$;
            $create_fn$;
          END IF;

          REVOKE ALL ON FUNCTION public.delete_user() FROM PUBLIC;

          SELECT EXISTS (
            SELECT 1 FROM pg_roles WHERE rolname = 'authenticated'
          ) INTO has_authenticated_role;

          IF has_authenticated_role THEN
            GRANT EXECUTE ON FUNCTION public.delete_user() TO authenticated;
          END IF;
        END $$;
    """)


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS public.delete_user();")
