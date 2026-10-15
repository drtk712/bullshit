-- CloudBase turns on row level security for console-created tables and ships no
-- policies, so anon/authenticated (mini program / JS SDK) see zero rows.
-- Table owners, superusers, and BYPASSRLS roles such as service_role skip RLS
-- unless FORCE ROW LEVEL SECURITY is set.
--
-- This migration:
--   1. Enables RLS on the app tables so client roles stay denied.
--   2. Revokes table privileges from PUBLIC, anon, and authenticated.
--   3. Adds one permissive policy for the role that applies the migration
--      (the Cloud Run login). Run the service as that same role.
-- Do not grant these tables to anon or authenticated.

ALTER TABLE public.feature_configs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.point_transactions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.feature_jobs ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON TABLE public.feature_configs FROM PUBLIC;
REVOKE ALL ON TABLE public.users FROM PUBLIC;
REVOKE ALL ON TABLE public.point_transactions FROM PUBLIC;
REVOKE ALL ON TABLE public.feature_jobs FROM PUBLIC;

DO $revoke$
DECLARE
  role_name text;
  table_name text;
BEGIN
  FOREACH role_name IN ARRAY ARRAY['anon', 'authenticated']
  LOOP
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = role_name) THEN
      FOREACH table_name IN ARRAY ARRAY['feature_configs', 'users', 'point_transactions', 'feature_jobs']
      LOOP
        EXECUTE 'REVOKE ALL ON TABLE public.' || quote_ident(table_name) || ' FROM ' || quote_ident(role_name);
      END LOOP;
    END IF;
  END LOOP;
END
$revoke$;

GRANT USAGE ON SCHEMA public TO CURRENT_USER;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.feature_configs TO CURRENT_USER;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.users TO CURRENT_USER;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.point_transactions TO CURRENT_USER;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.feature_jobs TO CURRENT_USER;

DO $policy$
DECLARE
  role_name text := current_user;
  table_name text;
  policy_name text;
BEGIN
  FOREACH table_name IN ARRAY ARRAY['feature_configs', 'users', 'point_transactions', 'feature_jobs']
  LOOP
    policy_name := 'backend_all_' || table_name;
    EXECUTE 'DROP POLICY IF EXISTS ' || quote_ident(policy_name) || ' ON public.' || quote_ident(table_name);
    EXECUTE 'CREATE POLICY ' || quote_ident(policy_name)
      || ' ON public.' || quote_ident(table_name)
      || ' FOR ALL TO ' || quote_ident(role_name)
      || ' USING (true) WITH CHECK (true)';
  END LOOP;
END
$policy$;
