-- feature_configs already exists in CloudBase PostgreSQL
-- (env wantuju-prod-d2gf1sf2r508a56b1, instance cloudbase-pg, database postgres-4lino9f2).
-- This statement matches that DDL exactly. IF NOT EXISTS leaves the live table and its
-- 10 rows untouched. Fresh local databases get the same shape; rows are not seeded here.

CREATE TABLE IF NOT EXISTS public.feature_configs (
  id          text PRIMARY KEY DEFAULT md5(random()::text || clock_timestamp()::text),
  type        text NOT NULL UNIQUE CHECK (type ~ '^[a-z][a-z0-9_-]{1,31}$'),
  enabled     boolean NOT NULL DEFAULT false,
  sort_order  integer,
  param       jsonb NOT NULL DEFAULT '[]'::jsonb,
  public      jsonb NOT NULL DEFAULT '{}'::jsonb,
  ui          jsonb NOT NULL DEFAULT '{}'::jsonb,
  validation  jsonb,
  generation  jsonb,
  test        jsonb,
  created_at  timestamptz NOT NULL DEFAULT now(),
  updated_at  timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS feature_configs_enabled_order_idx ON public.feature_configs (enabled, sort_order);
