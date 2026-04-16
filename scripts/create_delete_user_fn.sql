-- ============================================================
-- Supabase: delete_user() RPC function
-- ============================================================
-- Run this in the Supabase Dashboard → SQL Editor (or via psql).
-- It allows an authenticated user to permanently delete their own
-- account from auth.users via a SECURITY DEFINER function, which
-- elevates to superuser privilege only for this specific operation.
--
-- The React frontend calls this as:
--   await supabase.rpc('delete_user')
-- ============================================================

CREATE OR REPLACE FUNCTION public.delete_user()
RETURNS void
LANGUAGE sql
SECURITY DEFINER
SET search_path = public        -- pin search_path to prevent search-path injection
AS $$
  DELETE FROM auth.users WHERE id = auth.uid();
$$;

-- Grant execute only to authenticated users (not anon).
REVOKE ALL ON FUNCTION public.delete_user() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.delete_user() TO authenticated;
