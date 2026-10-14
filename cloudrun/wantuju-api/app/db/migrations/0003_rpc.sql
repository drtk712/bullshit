-- Atomic points, job claims, and JSONB patches as plpgsql functions.
--
-- CloudBase PostgREST (POST /v1/rdb/rest/rpc/<name>) runs each HTTP request in
-- its own transaction and cannot group several requests into one transaction.
-- These functions take the row locks and write every related row before they
-- return, which is the same boundary the psycopg fallback gets by calling them.
--
-- https://docs.cloudbase.net/http-api/pgdb/postgresql-restful-api
-- https://docs.cloudbase.net/database/postgresql/http/rpc
-- https://docs.cloudbase.net/http-api/pgdb/exec-pgsql

CREATE OR REPLACE FUNCTION public.wantuju_ms(ts timestamptz)
RETURNS bigint
LANGUAGE sql
IMMUTABLE
AS $fn$
  SELECT CASE
    WHEN ts IS NULL THEN NULL
    ELSE (EXTRACT(EPOCH FROM ts) * 1000)::bigint
  END
$fn$;

CREATE OR REPLACE FUNCTION public.wantuju_ts(ms bigint)
RETURNS timestamptz
LANGUAGE sql
IMMUTABLE
AS $fn$
  SELECT CASE
    WHEN ms IS NULL THEN NULL
    ELSE to_timestamp(ms / 1000.0)
  END
$fn$;

CREATE OR REPLACE FUNCTION public.wantuju_field_specs(table_name text)
RETURNS jsonb
LANGUAGE sql
STABLE
AS $fn$
  SELECT CASE table_name
    WHEN 'feature_configs' THEN $specs${
      "_id": {"column": "id", "kind": "text", "nullable": false},
      "type": {"column": "type", "kind": "text", "nullable": false},
      "enabled": {"column": "enabled", "kind": "bool", "nullable": false},
      "order": {"column": "sort_order", "kind": "int", "nullable": true},
      "param": {"column": "param", "kind": "jsonb", "nullable": false},
      "public": {"column": "public", "kind": "jsonb", "nullable": false},
      "ui": {"column": "ui", "kind": "jsonb", "nullable": false},
      "validation": {"column": "validation", "kind": "jsonb", "nullable": true},
      "generation": {"column": "generation", "kind": "jsonb", "nullable": true},
      "test": {"column": "test", "kind": "jsonb", "nullable": true},
      "createdAt": {"column": "created_at", "kind": "ts", "nullable": false},
      "updatedAt": {"column": "updated_at", "kind": "ts", "nullable": false}
    }$specs$::jsonb
    WHEN 'users' THEN $specs${
      "_id": {"column": "id", "kind": "text", "nullable": false},
      "openid": {"column": "openid", "kind": "text", "nullable": false},
      "points": {"column": "points", "kind": "int", "nullable": false},
      "totalGrantedPoints": {"column": "total_granted_points", "kind": "int", "nullable": false},
      "totalUsedPoints": {"column": "total_used_points", "kind": "int", "nullable": false},
      "totalRefundedPoints": {"column": "total_refunded_points", "kind": "int", "nullable": false},
      "nickName": {"column": "nick_name", "kind": "text", "nullable": false},
      "avatarFileID": {"column": "avatar_file_id", "kind": "text", "nullable": false},
      "profileCompleted": {"column": "profile_completed", "kind": "bool", "nullable": false},
      "profileCompletedAt": {"column": "profile_completed_at", "kind": "ts", "nullable": true},
      "status": {"column": "status", "kind": "text", "nullable": false},
      "blockedAt": {"column": "blocked_at", "kind": "ts", "nullable": true},
      "blockedReason": {"column": "blocked_reason", "kind": "text", "nullable": false},
      "blockedBy": {"column": "blocked_by", "kind": "text", "nullable": false},
      "unblockedAt": {"column": "unblocked_at", "kind": "ts", "nullable": true},
      "unblockedBy": {"column": "unblocked_by", "kind": "text", "nullable": false},
      "shareCountToday": {"column": "share_count_today", "kind": "int", "nullable": false},
      "lastShareDate": {"column": "last_share_date", "kind": "date", "nullable": true},
      "lastShareAt": {"column": "last_share_at", "kind": "ts", "nullable": true},
      "lastCheckInAt": {"column": "last_check_in_at", "kind": "ts", "nullable": true},
      "checkInDays": {"column": "check_in_days", "kind": "int", "nullable": false},
      "lastLoginAt": {"column": "last_login_at", "kind": "ts", "nullable": true},
      "createdAt": {"column": "created_at", "kind": "ts", "nullable": false},
      "updatedAt": {"column": "updated_at", "kind": "ts", "nullable": false}
    }$specs$::jsonb
    WHEN 'point_transactions' THEN $specs${
      "_id": {"column": "id", "kind": "text", "nullable": false},
      "openid": {"column": "openid", "kind": "text", "nullable": false},
      "type": {"column": "type", "kind": "text", "nullable": false},
      "amount": {"column": "amount", "kind": "int", "nullable": false},
      "balanceAfter": {"column": "balance_after", "kind": "int", "nullable": false},
      "reason": {"column": "reason", "kind": "text", "nullable": false},
      "taskId": {"column": "task_id", "kind": "text", "nullable": true},
      "operator": {"column": "operator", "kind": "text", "nullable": true},
      "createdAt": {"column": "created_at", "kind": "ts", "nullable": false}
    }$specs$::jsonb
    WHEN 'feature_jobs' THEN $specs${
      "_id": {"column": "id", "kind": "text", "nullable": false},
      "openid": {"column": "openid", "kind": "text", "nullable": false},
      "type": {"column": "type", "kind": "text", "nullable": false},
      "flow": {"column": "flow", "kind": "text", "nullable": true},
      "featureTitle": {"column": "feature_title", "kind": "text", "nullable": false},
      "featureHomeDesc": {"column": "feature_home_desc", "kind": "text", "nullable": false},
      "featureDescription": {"column": "feature_description", "kind": "text", "nullable": false},
      "param": {"column": "param", "kind": "jsonb", "nullable": false},
      "validation": {"column": "validation", "kind": "jsonb", "nullable": true},
      "fileID": {"column": "file_id", "kind": "text", "nullable": false},
      "fileIDs": {"column": "file_ids", "kind": "jsonb", "nullable": false},
      "generationPrompt": {"column": "generation_prompt", "kind": "text", "nullable": false},
      "status": {"column": "status", "kind": "text", "nullable": false},
      "posterFileID": {"column": "poster_file_id", "kind": "text", "nullable": true},
      "resultMode": {"column": "result_mode", "kind": "text", "nullable": false},
      "resultFileIDs": {"column": "result_file_ids", "kind": "jsonb", "nullable": false},
      "errMsg": {"column": "err_msg", "kind": "text", "nullable": false},
      "refundErrMsg": {"column": "refund_err_msg", "kind": "text", "nullable": false},
      "pointsCost": {"column": "points_cost", "kind": "int", "nullable": false},
      "pointsConsumed": {"column": "points_consumed", "kind": "bool", "nullable": false},
      "pointsRefunded": {"column": "points_refunded", "kind": "bool", "nullable": false},
      "consumeTransactionId": {"column": "consume_transaction_id", "kind": "text", "nullable": true},
      "refundTransactionId": {"column": "refund_transaction_id", "kind": "text", "nullable": true},
      "sourceFileID": {"column": "source_file_id", "kind": "text", "nullable": true},
      "sourceFileIDs": {"column": "source_file_ids", "kind": "jsonb", "nullable": true},
      "processingLeaseToken": {"column": "processing_lease_token", "kind": "text", "nullable": true},
      "processingLeaseAt": {"column": "processing_lease_at", "kind": "ts", "nullable": true},
      "createdAt": {"column": "created_at", "kind": "ts", "nullable": false},
      "updatedAt": {"column": "updated_at", "kind": "ts", "nullable": false}
    }$specs$::jsonb
    ELSE NULL
  END
$fn$;

CREATE OR REPLACE FUNCTION public.wantuju_insert_job(task jsonb, new_id text)
RETURNS public.feature_jobs
LANGUAGE plpgsql
SET search_path = public
AS $fn$
DECLARE
  v_job public.feature_jobs;
  v_created bigint;
BEGIN
  v_created := COALESCE(
    (task->>'createdAt')::bigint,
    (EXTRACT(EPOCH FROM clock_timestamp()) * 1000)::bigint
  );
  INSERT INTO public.feature_jobs (
    id, openid, type, flow,
    feature_title, feature_home_desc, feature_description,
    param, validation,
    file_id, file_ids, generation_prompt,
    status, poster_file_id, result_mode, result_file_ids,
    err_msg, refund_err_msg,
    points_cost, points_consumed, points_refunded,
    consume_transaction_id, refund_transaction_id,
    source_file_id, source_file_ids,
    processing_lease_token, processing_lease_at,
    created_at, updated_at
  ) VALUES (
    new_id,
    task->>'openid',
    task->>'type',
    NULLIF(task->>'flow', ''),
    COALESCE(task->>'featureTitle', ''),
    COALESCE(task->>'featureHomeDesc', ''),
    COALESCE(task->>'featureDescription', ''),
    COALESCE(CASE WHEN task->'param' IS NULL OR task->'param' = 'null'::jsonb THEN NULL ELSE task->'param' END, '{}'::jsonb),
    CASE WHEN task->'validation' IS NULL OR task->'validation' = 'null'::jsonb THEN NULL ELSE task->'validation' END,
    COALESCE(task->>'fileID', ''),
    COALESCE(CASE WHEN task->'fileIDs' IS NULL OR task->'fileIDs' = 'null'::jsonb THEN NULL ELSE task->'fileIDs' END, '[]'::jsonb),
    COALESCE(task->>'generationPrompt', ''),
    COALESCE(NULLIF(task->>'status', ''), 'pending'),
    NULLIF(task->>'posterFileID', ''),
    COALESCE(NULLIF(task->>'resultMode', ''), 'single'),
    COALESCE(CASE WHEN task->'resultFileIDs' IS NULL OR task->'resultFileIDs' = 'null'::jsonb THEN NULL ELSE task->'resultFileIDs' END, '[]'::jsonb),
    COALESCE(task->>'errMsg', ''),
    COALESCE(task->>'refundErrMsg', ''),
    COALESCE((task->>'pointsCost')::integer, 0),
    COALESCE((task->>'pointsConsumed')::boolean, false),
    COALESCE((task->>'pointsRefunded')::boolean, false),
    NULLIF(task->>'consumeTransactionId', ''),
    NULLIF(task->>'refundTransactionId', ''),
    NULLIF(task->>'sourceFileID', ''),
    CASE WHEN task->'sourceFileIDs' IS NULL OR task->'sourceFileIDs' = 'null'::jsonb THEN NULL ELSE task->'sourceFileIDs' END,
    NULLIF(task->>'processingLeaseToken', ''),
    CASE
      WHEN task->>'processingLeaseAt' IS NULL OR task->>'processingLeaseAt' = '' THEN NULL
      ELSE public.wantuju_ts((task->>'processingLeaseAt')::bigint)
    END,
    public.wantuju_ts(v_created),
    public.wantuju_ts(COALESCE((task->>'updatedAt')::bigint, v_created))
  )
  RETURNING * INTO v_job;
  RETURN v_job;
END
$fn$;

CREATE OR REPLACE FUNCTION public.wantuju_create_pending_job(payload jsonb)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $fn$
DECLARE
  v_task jsonb := payload->'task';
  v_amount integer := COALESCE((payload->>'amount')::integer, 1);
  v_openid text;
  v_user public.users;
  v_job public.feature_jobs;
  v_tx text;
  v_balance integer;
  v_now bigint;
  v_id text;
BEGIN
  IF v_task IS NULL OR jsonb_typeof(v_task) <> 'object' THEN
    RAISE EXCEPTION '创建任务失败';
  END IF;
  v_openid := v_task->>'openid';
  IF v_openid IS NULL OR v_openid = '' THEN
    RAISE EXCEPTION '任务缺少 openid';
  END IF;
  SELECT * INTO v_user FROM public.users WHERE openid = v_openid FOR UPDATE;
  IF NOT FOUND THEN
    RAISE EXCEPTION '用户不存在';
  END IF;
  IF v_user.points < v_amount THEN
    RAISE EXCEPTION '积分不足，请先获取积分';
  END IF;
  v_balance := v_user.points - v_amount;
  v_now := COALESCE(
    (v_task->>'createdAt')::bigint,
    (EXTRACT(EPOCH FROM clock_timestamp()) * 1000)::bigint
  );
  UPDATE public.users
  SET points = v_balance,
      total_used_points = total_used_points + v_amount,
      updated_at = public.wantuju_ts(v_now)
  WHERE id = v_user.id;

  v_task := v_task || jsonb_build_object(
    'status', 'pending',
    'errMsg', '',
    'pointsCost', v_amount,
    'pointsConsumed', true,
    'pointsRefunded', false,
    'updatedAt', v_now,
    'createdAt', v_now
  );
  v_id := md5(random()::text || clock_timestamp()::text);
  v_job := public.wantuju_insert_job(v_task, v_id);

  INSERT INTO public.point_transactions (
    openid, type, amount, balance_after, reason, task_id, created_at
  ) VALUES (
    v_openid, 'consume', -v_amount, v_balance, 'create_feature_job', v_job.id, public.wantuju_ts(v_now)
  )
  RETURNING id INTO v_tx;

  UPDATE public.feature_jobs
  SET consume_transaction_id = v_tx,
      updated_at = public.wantuju_ts(v_now)
  WHERE id = v_job.id
  RETURNING * INTO v_job;

  RETURN to_jsonb(v_job);
END
$fn$;

CREATE OR REPLACE FUNCTION public.wantuju_consume_existing_job(payload jsonb)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $fn$
DECLARE
  v_amount integer := COALESCE((payload->>'amount')::integer, 1);
  v_user public.users;
  v_job public.feature_jobs;
  v_tx text;
  v_balance integer;
  v_now bigint;
BEGIN
  SELECT * INTO v_job
  FROM public.feature_jobs
  WHERE id = payload->>'task_id'
  FOR UPDATE;
  IF NOT FOUND THEN
    RAISE EXCEPTION '任务不存在';
  END IF;
  IF v_job.points_consumed THEN
    RETURN to_jsonb(v_job);
  END IF;
  IF v_job.openid IS NULL OR v_job.openid = '' THEN
    RAISE EXCEPTION '任务缺少 openid';
  END IF;
  SELECT * INTO v_user FROM public.users WHERE openid = v_job.openid FOR UPDATE;
  IF NOT FOUND THEN
    RAISE EXCEPTION '用户不存在';
  END IF;
  IF v_user.points < v_amount THEN
    RAISE EXCEPTION '积分不足，请先获取积分';
  END IF;
  v_balance := v_user.points - v_amount;
  v_now := (EXTRACT(EPOCH FROM clock_timestamp()) * 1000)::bigint;
  UPDATE public.users
  SET points = v_balance,
      total_used_points = total_used_points + v_amount,
      updated_at = public.wantuju_ts(v_now)
  WHERE id = v_user.id;

  INSERT INTO public.point_transactions (
    openid, type, amount, balance_after, reason, task_id, created_at
  ) VALUES (
    v_job.openid, 'consume', -v_amount, v_balance, 'create_feature_job', v_job.id, public.wantuju_ts(v_now)
  )
  RETURNING id INTO v_tx;

  UPDATE public.feature_jobs
  SET points_cost = v_amount,
      points_consumed = true,
      points_refunded = false,
      consume_transaction_id = v_tx,
      updated_at = public.wantuju_ts(v_now)
  WHERE id = v_job.id
  RETURNING * INTO v_job;
  RETURN to_jsonb(v_job);
END
$fn$;

CREATE OR REPLACE FUNCTION public.wantuju_refund_failed_job(payload jsonb)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $fn$
DECLARE
  v_amount integer := COALESCE((payload->>'amount')::integer, 1);
  v_user public.users;
  v_job public.feature_jobs;
  v_tx text;
  v_balance integer;
  v_now bigint;
  v_refunded boolean;
BEGIN
  SELECT * INTO v_job
  FROM public.feature_jobs
  WHERE id = payload->>'task_id'
  FOR UPDATE;
  IF NOT FOUND THEN
    RAISE EXCEPTION '任务不存在';
  END IF;
  v_tx := v_job.refund_transaction_id;
  v_refunded := v_job.points_refunded;
  IF v_job.points_consumed AND NOT v_job.points_refunded THEN
    IF v_job.openid IS NULL OR v_job.openid = '' THEN
      RAISE EXCEPTION '任务缺少 openid';
    END IF;
    SELECT * INTO v_user FROM public.users WHERE openid = v_job.openid FOR UPDATE;
    IF NOT FOUND THEN
      RAISE EXCEPTION '用户不存在';
    END IF;
    v_balance := v_user.points + v_amount;
    v_now := (EXTRACT(EPOCH FROM clock_timestamp()) * 1000)::bigint;
    UPDATE public.users
    SET points = v_balance,
        total_refunded_points = total_refunded_points + v_amount,
        updated_at = public.wantuju_ts(v_now)
    WHERE id = v_user.id;
    INSERT INTO public.point_transactions (
      openid, type, amount, balance_after, reason, task_id, created_at
    ) VALUES (
      v_job.openid, 'refund', v_amount, v_balance, 'job_failed_refund', v_job.id, public.wantuju_ts(v_now)
    )
    RETURNING id INTO v_tx;
    v_refunded := true;
  END IF;

  UPDATE public.feature_jobs
  SET status = 'failed',
      err_msg = COALESCE(payload->>'err_msg', ''),
      points_refunded = v_refunded,
      refund_transaction_id = v_tx,
      refund_err_msg = '',
      updated_at = clock_timestamp()
  WHERE id = v_job.id;
  RETURN NULL;
END
$fn$;

CREATE OR REPLACE FUNCTION public.wantuju_claim_job(payload jsonb)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $fn$
DECLARE
  v_job public.feature_jobs;
  v_now bigint := (payload->>'now_ms')::bigint;
  v_lease bigint := COALESCE((payload->>'lease_ms')::bigint, 900000);
BEGIN
  SELECT * INTO v_job
  FROM public.feature_jobs
  WHERE id = payload->>'task_id'
  FOR UPDATE;
  IF NOT FOUND THEN
    RETURN NULL;
  END IF;
  IF v_job.status = 'processing'
     AND v_job.processing_lease_at IS NOT NULL
     AND v_now - public.wantuju_ms(v_job.processing_lease_at) < v_lease THEN
    RETURN NULL;
  END IF;
  IF v_job.status NOT IN ('pending', 'processing') THEN
    RETURN NULL;
  END IF;
  UPDATE public.feature_jobs
  SET status = 'processing',
      processing_lease_token = payload->>'token',
      processing_lease_at = public.wantuju_ts(v_now),
      err_msg = '',
      updated_at = public.wantuju_ts(v_now)
  WHERE id = v_job.id
  RETURNING * INTO v_job;
  RETURN to_jsonb(v_job);
END
$fn$;

CREATE OR REPLACE FUNCTION public.wantuju_adjust_points(payload jsonb)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $fn$
DECLARE
  v_user public.users;
  v_amount integer := (payload->>'amount')::integer;
  v_balance integer;
  v_now bigint := COALESCE((payload->>'now')::bigint, (EXTRACT(EPOCH FROM clock_timestamp()) * 1000)::bigint);
  v_tx text;
BEGIN
  SELECT * INTO v_user FROM public.users WHERE id = payload->>'user_id' FOR UPDATE;
  IF NOT FOUND THEN
    RAISE EXCEPTION '用户不存在';
  END IF;
  v_balance := v_user.points + v_amount;
  IF v_balance < 0 THEN
    RAISE EXCEPTION '调整后积分不能小于 0';
  END IF;
  UPDATE public.users
  SET points = v_balance,
      total_granted_points = CASE
        WHEN v_amount > 0 THEN total_granted_points + v_amount
        ELSE total_granted_points
      END,
      total_used_points = CASE
        WHEN v_amount < 0 THEN total_used_points + abs(v_amount)
        ELSE total_used_points
      END,
      updated_at = public.wantuju_ts(v_now)
  WHERE id = v_user.id;
  INSERT INTO public.point_transactions (
    openid, type, amount, balance_after, reason, task_id, operator, created_at
  ) VALUES (
    v_user.openid,
    'adjust',
    v_amount,
    v_balance,
    COALESCE(payload->>'reason', ''),
    NULL,
    NULLIF(payload->>'operator', ''),
    public.wantuju_ts(v_now)
  )
  RETURNING id INTO v_tx;
  RETURN jsonb_build_object('ids', jsonb_build_array(v_tx), '_id', v_tx);
END
$fn$;

CREATE OR REPLACE FUNCTION public.wantuju_delete_user(payload jsonb)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $fn$
DECLARE
  v_user public.users;
  v_tx integer;
  v_jobs integer;
BEGIN
  SELECT * INTO v_user FROM public.users WHERE id = payload->>'user_id' FOR UPDATE;
  IF NOT FOUND OR v_user.openid IS NULL OR v_user.openid = '' THEN
    RAISE EXCEPTION '用户缺少 openid，无法级联删除关联数据';
  END IF;
  DELETE FROM public.point_transactions WHERE openid = v_user.openid;
  GET DIAGNOSTICS v_tx = ROW_COUNT;
  DELETE FROM public.feature_jobs WHERE openid = v_user.openid;
  GET DIAGNOSTICS v_jobs = ROW_COUNT;
  DELETE FROM public.users WHERE id = v_user.id;
  RETURN jsonb_build_object(
    'userId', v_user.id,
    'openid', v_user.openid,
    'transactionsDeleted', v_tx,
    'jobsDeleted', v_jobs
  );
END
$fn$;

CREATE OR REPLACE FUNCTION public.wantuju_ensure_user(payload jsonb)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $fn$
DECLARE
  v_openid text := payload->>'openid';
  v_grant text := payload->>'grant_id';
  v_now bigint := COALESCE((payload->>'now')::bigint, (EXTRACT(EPOCH FROM clock_timestamp()) * 1000)::bigint);
  v_user public.users;
  v_is_new boolean := false;
BEGIN
  IF v_openid IS NULL OR v_openid = '' OR v_grant IS NULL OR v_grant !~ '^first_login_[0-9a-f]{64}$' THEN
    RAISE EXCEPTION '创建用户失败';
  END IF;
  INSERT INTO public.users (
    openid, points, total_granted_points, total_used_points, total_refunded_points,
    created_at, updated_at, last_login_at
  ) VALUES (
    v_openid, 3, 3, 0, 0,
    public.wantuju_ts(v_now), public.wantuju_ts(v_now), public.wantuju_ts(v_now)
  )
  ON CONFLICT (openid) DO NOTHING
  RETURNING * INTO v_user;
  IF FOUND THEN
    v_is_new := true;
    BEGIN
      INSERT INTO public.point_transactions (
        id, openid, type, amount, balance_after, reason, task_id, created_at
      ) VALUES (
        v_grant, v_openid, 'grant', 3, 3, 'first_login', NULL, public.wantuju_ts(v_now)
      );
    EXCEPTION
      WHEN unique_violation THEN
        NULL;
    END;
  ELSE
    SELECT * INTO v_user FROM public.users WHERE openid = v_openid FOR UPDATE;
    IF NOT FOUND THEN
      RAISE EXCEPTION '创建用户失败';
    END IF;
    IF COALESCE(v_user.status, 'active') = 'blocked' THEN
      RETURN jsonb_build_object('ok', false, 'code', 'blocked', 'isNewUser', false, 'user', to_jsonb(v_user));
    END IF;
    IF COALESCE((payload->>'record_login')::boolean, false) THEN
      UPDATE public.users
      SET last_login_at = public.wantuju_ts(v_now),
          updated_at = public.wantuju_ts(v_now)
      WHERE id = v_user.id
      RETURNING * INTO v_user;
    END IF;
  END IF;
  RETURN jsonb_build_object('ok', true, 'isNewUser', v_is_new, 'user', to_jsonb(v_user));
END
$fn$;

CREATE OR REPLACE FUNCTION public.wantuju_claim_share(payload jsonb)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $fn$
DECLARE
  v_user public.users;
  v_today date := (payload->>'today')::date;
  v_now bigint := (payload->>'now')::bigint;
  v_count integer;
  v_points integer;
BEGIN
  SELECT * INTO v_user FROM public.users WHERE id = payload->>'user_id' FOR UPDATE;
  IF NOT FOUND THEN
    RAISE EXCEPTION '用户不存在';
  END IF;
  IF v_user.last_share_date = v_today THEN
    v_count := v_user.share_count_today;
  ELSE
    v_count := 0;
  END IF;
  IF v_count >= 3 THEN
    RETURN jsonb_build_object('ok', false, 'code', 'share_limit', 'user', to_jsonb(v_user));
  END IF;
  v_points := v_user.points + 1;
  UPDATE public.users
  SET points = v_points,
      total_granted_points = total_granted_points + 1,
      share_count_today = v_count + 1,
      last_share_date = v_today,
      last_share_at = public.wantuju_ts(v_now),
      updated_at = public.wantuju_ts(v_now)
  WHERE id = v_user.id
  RETURNING * INTO v_user;
  INSERT INTO public.point_transactions (
    openid, type, amount, balance_after, reason, task_id, created_at
  ) VALUES (
    v_user.openid, 'grant', 1, v_points, 'share_reward', NULL, public.wantuju_ts(v_now)
  );
  RETURN jsonb_build_object('ok', true, 'user', to_jsonb(v_user));
END
$fn$;

CREATE OR REPLACE FUNCTION public.wantuju_check_in(payload jsonb)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $fn$
DECLARE
  v_user public.users;
  v_today date := (payload->>'today')::date;
  v_now bigint := (payload->>'now')::bigint;
  v_points integer;
  v_days integer;
  v_last date;
BEGIN
  SELECT * INTO v_user FROM public.users WHERE id = payload->>'user_id' FOR UPDATE;
  IF NOT FOUND THEN
    RAISE EXCEPTION '用户不存在';
  END IF;
  IF v_user.last_check_in_at IS NOT NULL THEN
    v_last := ((v_user.last_check_in_at AT TIME ZONE 'UTC') + interval '8 hours')::date;
    IF v_last = v_today THEN
      RETURN jsonb_build_object('ok', false, 'code', 'already_checked_in', 'user', to_jsonb(v_user));
    END IF;
  END IF;
  v_points := v_user.points + 1;
  v_days := COALESCE(v_user.check_in_days, 0) + 1;
  UPDATE public.users
  SET points = v_points,
      total_granted_points = total_granted_points + 1,
      last_check_in_at = public.wantuju_ts(v_now),
      check_in_days = v_days,
      updated_at = public.wantuju_ts(v_now)
  WHERE id = v_user.id
  RETURNING * INTO v_user;
  INSERT INTO public.point_transactions (
    openid, type, amount, balance_after, reason, task_id, created_at
  ) VALUES (
    v_user.openid, 'grant', 1, v_points, 'daily_check_in', NULL, public.wantuju_ts(v_now)
  );
  RETURN jsonb_build_object('ok', true, 'user', to_jsonb(v_user));
END
$fn$;

CREATE OR REPLACE FUNCTION public.wantuju_patch_document(payload jsonb)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $fn$
DECLARE
  v_table text := payload->>'table';
  v_id text := payload->>'id';
  v_patch jsonb := payload->'patch';
  v_specs jsonb;
  v_key text;
  v_val jsonb;
  v_head text;
  v_spec jsonb;
  v_column text;
  v_kind text;
  v_nullable boolean;
  v_flat text[] := ARRAY[]::text[];
  v_nested jsonb := '{}'::jsonb;
  v_assigns text[] := ARRAY[]::text[];
  v_expr text;
  v_entries jsonb;
  v_entry jsonb;
  v_touched_updated boolean := false;
  v_result jsonb;
  v_sql text;
BEGIN
  IF v_patch IS NULL OR jsonb_typeof(v_patch) <> 'object' OR v_patch = '{}'::jsonb THEN
    RAISE EXCEPTION '更新内容为空';
  END IF;
  v_specs := public.wantuju_field_specs(v_table);
  IF v_specs IS NULL THEN
    RAISE EXCEPTION USING MESSAGE = '未知数据表: ' || COALESCE(v_table, '');
  END IF;

  FOR v_key, v_val IN SELECT key, value FROM jsonb_each(v_patch)
  LOOP
    IF position('.' IN v_key) > 0 THEN
      v_head := split_part(v_key, '.', 1);
      v_spec := v_specs->v_head;
      IF v_spec IS NULL OR v_spec->>'kind' <> 'jsonb' THEN
        RAISE EXCEPTION USING MESSAGE = '不支持的字段路径: ' || v_table || '.' || v_key;
      END IF;
      v_column := v_spec->>'column';
      IF v_column = ANY(v_flat) THEN
        RAISE EXCEPTION USING MESSAGE = '不能同时替换和修改嵌套字段: ' || v_table || '.' || v_head;
      END IF;
      v_nested := jsonb_set(
        v_nested,
        ARRAY[v_column],
        COALESCE(v_nested->v_column, '[]'::jsonb) || jsonb_build_array(
          jsonb_build_object(
            'path', to_jsonb(string_to_array(substr(v_key, length(v_head) + 2), '.')),
            'key', v_key
          )
        ),
        true
      );
    ELSE
      v_spec := v_specs->v_key;
      IF v_spec IS NULL THEN
        RAISE EXCEPTION USING MESSAGE = '不支持的写入字段: ' || v_table || '.' || v_key;
      END IF;
      v_column := v_spec->>'column';
      v_kind := v_spec->>'kind';
      v_nullable := COALESCE((v_spec->>'nullable')::boolean, true);
      IF v_nested ? v_column THEN
        RAISE EXCEPTION USING MESSAGE = '不能同时替换和修改嵌套字段: ' || v_table || '.' || v_key;
      END IF;
      v_flat := array_append(v_flat, v_column);
      IF v_key = 'updatedAt' THEN
        v_touched_updated := true;
      END IF;
      IF v_val = 'null'::jsonb THEN
        IF v_kind = 'text' AND NOT v_nullable THEN
          v_assigns := array_append(v_assigns, quote_ident(v_column) || ' = ' || quote_literal(''));
        ELSE
          v_assigns := array_append(v_assigns, quote_ident(v_column) || ' = NULL');
        END IF;
      ELSIF v_kind = 'text' THEN
        v_assigns := array_append(v_assigns, quote_ident(v_column) || ' = ' || quote_literal(v_val #>> '{}'));
      ELSIF v_kind = 'int' THEN
        v_assigns := array_append(v_assigns, quote_ident(v_column) || ' = ' || ((v_val #>> '{}')::bigint)::text);
      ELSIF v_kind = 'bool' THEN
        v_assigns := array_append(
          v_assigns,
          quote_ident(v_column) || ' = ' || CASE WHEN (v_val #>> '{}')::boolean THEN 'TRUE' ELSE 'FALSE' END
        );
      ELSIF v_kind = 'ts' THEN
        v_assigns := array_append(
          v_assigns,
          quote_ident(v_column) || ' = to_timestamp(' || ((v_val #>> '{}')::numeric)::text || ' / 1000.0)'
        );
      ELSIF v_kind = 'date' THEN
        v_assigns := array_append(
          v_assigns,
          quote_ident(v_column) || ' = ' || quote_literal(v_val #>> '{}') || '::date'
        );
      ELSIF v_kind = 'jsonb' THEN
        v_assigns := array_append(
          v_assigns,
          quote_ident(v_column) || ' = ' || quote_literal(v_val::text) || '::jsonb'
        );
      ELSE
        RAISE EXCEPTION USING MESSAGE = '未知字段类型: ' || COALESCE(v_kind, '');
      END IF;
    END IF;
  END LOOP;

  FOR v_column, v_entries IN SELECT key, value FROM jsonb_each(v_nested)
  LOOP
    v_expr := 'COALESCE(' || quote_ident(v_column) || ', ''{}''::jsonb)';
    FOR v_entry IN SELECT value FROM jsonb_array_elements(v_entries)
    LOOP
      v_expr := 'jsonb_set('
        || v_expr
        || ', ARRAY(SELECT jsonb_array_elements_text('
        || quote_literal((v_entry->'path')::text)
        || '::jsonb)), COALESCE($1 -> '
        || quote_literal(v_entry->>'key')
        || ', ''null''::jsonb), true)';
    END LOOP;
    v_assigns := array_append(v_assigns, quote_ident(v_column) || ' = ' || v_expr);
  END LOOP;

  IF v_specs ? 'updatedAt' AND NOT v_touched_updated AND NOT ('updated_at' = ANY(v_flat)) THEN
    v_assigns := array_append(v_assigns, 'updated_at = now()');
  END IF;
  IF v_assigns = ARRAY[]::text[] THEN
    RAISE EXCEPTION '更新内容为空';
  END IF;

  IF v_nested = '{}'::jsonb THEN
    v_sql := 'UPDATE public.' || quote_ident(v_table)
      || ' SET ' || array_to_string(v_assigns, ', ')
      || ' WHERE id = $1 RETURNING to_jsonb(public.' || quote_ident(v_table) || '.*)';
    EXECUTE v_sql INTO v_result USING v_id;
  ELSE
    v_sql := 'UPDATE public.' || quote_ident(v_table)
      || ' SET ' || array_to_string(v_assigns, ', ')
      || ' WHERE id = $2 RETURNING to_jsonb(public.' || quote_ident(v_table) || '.*)';
    EXECUTE v_sql INTO v_result USING v_patch, v_id;
  END IF;
  IF v_result IS NULL THEN
    RAISE EXCEPTION '文档不存在';
  END IF;
  RETURN v_result;
END
$fn$;

DO $grant$
DECLARE
  v_fn text;
  v_helper boolean;
BEGIN
  FOREACH v_fn IN ARRAY ARRAY[
    'wantuju_ms(timestamptz)',
    'wantuju_ts(bigint)',
    'wantuju_field_specs(text)',
    'wantuju_insert_job(jsonb, text)',
    'wantuju_create_pending_job(jsonb)',
    'wantuju_consume_existing_job(jsonb)',
    'wantuju_refund_failed_job(jsonb)',
    'wantuju_claim_job(jsonb)',
    'wantuju_adjust_points(jsonb)',
    'wantuju_delete_user(jsonb)',
    'wantuju_ensure_user(jsonb)',
    'wantuju_claim_share(jsonb)',
    'wantuju_check_in(jsonb)',
    'wantuju_patch_document(jsonb)'
  ]
  LOOP
    v_helper := v_fn IN (
      'wantuju_ms(timestamptz)',
      'wantuju_ts(bigint)',
      'wantuju_field_specs(text)',
      'wantuju_insert_job(jsonb, text)'
    );
    EXECUTE 'REVOKE ALL ON FUNCTION public.' || v_fn || ' FROM PUBLIC';
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
      EXECUTE 'REVOKE ALL ON FUNCTION public.' || v_fn || ' FROM anon';
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
      EXECUTE 'REVOKE ALL ON FUNCTION public.' || v_fn || ' FROM authenticated';
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'service_role') THEN
      IF v_helper THEN
        EXECUTE 'REVOKE ALL ON FUNCTION public.' || v_fn || ' FROM service_role';
      ELSE
        EXECUTE 'GRANT EXECUTE ON FUNCTION public.' || v_fn || ' TO service_role';
      END IF;
    END IF;
  END LOOP;

  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'service_role') THEN
    EXECUTE 'GRANT USAGE ON SCHEMA public TO service_role';
    EXECUTE 'GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.feature_configs, public.users, public.point_transactions, public.feature_jobs TO service_role';
  END IF;

  IF EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'public' AND table_name = 'schema_migrations'
  ) THEN
    EXECUTE 'REVOKE ALL ON TABLE public.schema_migrations FROM PUBLIC';
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
      EXECUTE 'REVOKE ALL ON TABLE public.schema_migrations FROM anon';
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
      EXECUTE 'REVOKE ALL ON TABLE public.schema_migrations FROM authenticated';
    END IF;
  END IF;
END
$grant$;

DO $reload$
BEGIN
  PERFORM pg_notify('pgrst', 'reload schema');
EXCEPTION
  WHEN OTHERS THEN
    NULL;
END
$reload$;
