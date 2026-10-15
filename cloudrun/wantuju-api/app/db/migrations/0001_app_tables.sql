-- Users, point ledger, and feature jobs. No backfill: the old document database
-- was released with the previous CloudBase environment.

CREATE TABLE IF NOT EXISTS public.users (
  id text PRIMARY KEY DEFAULT md5(random()::text || clock_timestamp()::text),
  openid text NOT NULL UNIQUE,
  points integer NOT NULL DEFAULT 0 CHECK (points >= 0),
  total_granted_points integer NOT NULL DEFAULT 0,
  total_used_points integer NOT NULL DEFAULT 0,
  total_refunded_points integer NOT NULL DEFAULT 0,
  nick_name text NOT NULL DEFAULT '',
  avatar_file_id text NOT NULL DEFAULT '',
  profile_completed boolean NOT NULL DEFAULT false,
  profile_completed_at timestamptz,
  status text NOT NULL DEFAULT 'active',
  blocked_at timestamptz,
  blocked_reason text NOT NULL DEFAULT '',
  blocked_by text NOT NULL DEFAULT '',
  unblocked_at timestamptz,
  unblocked_by text NOT NULL DEFAULT '',
  share_count_today integer NOT NULL DEFAULT 0,
  last_share_date date,
  last_share_at timestamptz,
  last_check_in_at timestamptz,
  check_in_days integer NOT NULL DEFAULT 0,
  last_login_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS users_last_login_at_idx ON public.users (last_login_at DESC NULLS LAST);
CREATE INDEX IF NOT EXISTS users_profile_completed_idx ON public.users (profile_completed);

CREATE TABLE IF NOT EXISTS public.point_transactions (
  id text PRIMARY KEY DEFAULT md5(random()::text || clock_timestamp()::text),
  openid text NOT NULL,
  type text NOT NULL,
  amount integer NOT NULL,
  balance_after integer NOT NULL,
  reason text NOT NULL DEFAULT '',
  task_id text,
  operator text,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS point_transactions_openid_created_idx
  ON public.point_transactions (openid, created_at DESC);
CREATE INDEX IF NOT EXISTS point_transactions_task_id_idx ON public.point_transactions (task_id);
CREATE INDEX IF NOT EXISTS point_transactions_reason_idx ON public.point_transactions (reason);
CREATE INDEX IF NOT EXISTS point_transactions_type_idx ON public.point_transactions (type);

CREATE TABLE IF NOT EXISTS public.feature_jobs (
  id text PRIMARY KEY DEFAULT md5(random()::text || clock_timestamp()::text),
  openid text NOT NULL,
  type text NOT NULL,
  flow text,
  feature_title text NOT NULL DEFAULT '',
  feature_home_desc text NOT NULL DEFAULT '',
  feature_description text NOT NULL DEFAULT '',
  param jsonb NOT NULL DEFAULT '{}'::jsonb,
  validation jsonb,
  file_id text NOT NULL DEFAULT '',
  file_ids jsonb NOT NULL DEFAULT '[]'::jsonb,
  generation_prompt text NOT NULL DEFAULT '',
  status text NOT NULL,
  poster_file_id text,
  result_mode text NOT NULL DEFAULT 'single',
  result_file_ids jsonb NOT NULL DEFAULT '[]'::jsonb,
  err_msg text NOT NULL DEFAULT '',
  refund_err_msg text NOT NULL DEFAULT '',
  points_cost integer NOT NULL DEFAULT 0,
  points_consumed boolean NOT NULL DEFAULT false,
  points_refunded boolean NOT NULL DEFAULT false,
  consume_transaction_id text,
  refund_transaction_id text,
  source_file_id text,
  source_file_ids jsonb,
  processing_lease_token text,
  processing_lease_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS feature_jobs_openid_created_idx
  ON public.feature_jobs (openid, created_at DESC);
CREATE INDEX IF NOT EXISTS feature_jobs_status_updated_idx
  ON public.feature_jobs (status, updated_at);
CREATE INDEX IF NOT EXISTS feature_jobs_status_created_idx
  ON public.feature_jobs (status, created_at);
CREATE INDEX IF NOT EXISTS feature_jobs_active_updated_idx
  ON public.feature_jobs (updated_at)
  WHERE status IN ('pending', 'processing');
