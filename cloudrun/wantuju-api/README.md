# Wantuju API CloudRun Service

微信云托管版后端服务，面向小程序提供 `wx.cloud.callContainer` 直连接口，并承载管理端 `/admin`。

数据层默认走 CloudBase HTTP API 访问环境里的 PostgreSQL 17，凭据是已经用于云存储的 `CLOUDBASE_APIKEY`。小程序不直连数据库，接口形状保持不变。只有显式配置了 `DATABASE_URL`（或完整的 `PG*`）时才改用 psycopg 直连。

当前环境：

- 环境 ID：`wantuju-prod-d2gf1sf2r508a56b1`（ap-shanghai）
- 实例：`cloudbase-pg`
- 数据库：`postgres-4lino9f2`
- schema：`public`

## 服务范围

- 小程序用户资料、分享奖励、每日签到、积分流水。
- 玩法配置读取。
- 图片任务创建、校验、队列处理、结果上传、失败退款。
- 低风险图片工具：切图、拼长图。
- 管理端：仪表盘、玩法配置、用户管理、积分流水、任务列表、云存储工具。

## 代码结构

- `app/main.py`：FastAPI 应用入口，启动时应用 SQL 迁移并启动任务队列。
- `app/api/`：小程序 HTTP 路由。
- `app/admin/`：FastHTML 管理端路由和页面。
- `app/services/`：业务逻辑、任务队列、图片生成和工具处理。
- `app/db/`：数据访问。默认是 CloudBase PostgREST；配置了连接串时用 psycopg。
- `app/db/migrations/`：启动时按文件名顺序执行的 SQL，含积分和领任务用的函数。
- `app/cloudbase/`：CloudBase HTTP API 与云存储。文档数据库客户端已移除。
- `app/core/`：运行配置。

## 环境变量

在云托管服务配置里设置，不要写进仓库。

默认数据层和云存储共用这两项。网关是 `https://{envId}.api.tcloudbasegateway.com`，请求头 `Authorization: Bearer <CLOUDBASE_APIKEY>`。API Key 在服务端对应 `service_role`（`BYPASSRLS`），不要放进小程序。

```env
CLOUDBASE_ENV_ID=wantuju-prod-d2gf1sf2r508a56b1
CLOUDBASE_APIKEY=<CloudBase HTTP API Bearer Token>
```

可选的 psycopg 直连。设置了 `DATABASE_URL` 或下面任意一项 `PG*`（`PGSSLMODE` 除外）后，服务不再走 HTTP 数据层：

```env
DATABASE_URL=postgresql://USER:PASSWORD@HOST:5432/postgres-4lino9f2?sslmode=require
```

或拆开写：

```env
PGHOST=<控制台里的内网地址>
PGPORT=5432
PGUSER=<数据库账号>
PGPASSWORD=<数据库密码>
PGDATABASE=postgres-4lino9f2
PGSSLMODE=require
```

图片生成和管理端：

```env
MEMEFAST_API_KEY=<图片生成模型 API Key>
MEMEFAST_API_URL=https://www.openclaudecode.cn/v1/chat/completions
MEMEFAST_MODEL=gpt-image-2

ADMIN_SESSION_SECRET=<强随机字符串>
ADMIN_PASSWORD=<管理端登录密码>
```

可选：

```env
DB_POOL_MIN=1
DB_POOL_MAX=5
DB_POOL_TIMEOUT=10
VALIDATION_API_KEY=<将来的 OpenAI 兼容视觉模型 Key，现在留空>
```

`DB_POOL_*` 只在 psycopg 直连时生效。云托管最大实例数乘以 `DB_POOL_MAX` 要小于数据库最大连接数。HTTP 路径没有应用侧连接池，每次请求由网关自己连库。

已经不再使用，不要再配置：

```env
CLOUDBASE_DB_INSTANCE
CLOUDBASE_DB_NAME
CLOUDBASE_COMMAND_DB_INSTANCE
CLOUDBASE_COMMAND_DB_NAME
CLOUDBASE_ACCESS_TOKEN
POSTER_SERVER_URL
POSTER_SERVER_TOKEN
```

## 连接 CloudBase PostgreSQL

默认用 HTTPS，不需要数据库密码、内网地址或 VPC。

| 用途 | 方法 | 路径 |
|------|------|------|
| 查询、插入、更新、删除 | GET / POST / PATCH / DELETE | `/v1/rdb/rest/{table}` |
| 扣分、退款、领任务、签到、分享、调积分、删用户、首登赠送、嵌套 JSON 更新 | POST | `/v1/rdb/rest/rpc/{function}` |
| 启动迁移 | POST | `/v1/rdb/exec-pgsql`（`role=cloudbase_postgres`） |

只访问 `public` schema。文档：

- [HTTP API 概览](https://docs.cloudbase.net/http-api/basic/overview)
- [PostgreSQL REST](https://docs.cloudbase.net/http-api/pgdb/postgresql-restful-api)
- [RPC](https://docs.cloudbase.net/database/postgresql/http/rpc)
- [执行 SQL](https://docs.cloudbase.net/http-api/pgdb/exec-pgsql)
- [角色与权限](https://docs.cloudbase.net/database/postgresql/roles)

### 事务

PostgREST 的每一次请求是一个数据库事务，不能把多次 HTTP 请求包进同一个事务。条件更新也盖不住「锁用户、改余额、插任务、插流水」这种多表步骤，并发扣分会丢更新。

这些步骤写在 `app/db/migrations/0003_rpc.sql` 的 plpgsql 函数里。函数内 `SELECT ... FOR UPDATE`，全部写完才返回；请求结束时提交或回滚。psycopg 回退调用同一批函数，所以两条路径的原子性一致。普通列表、详情和单行更新仍走 REST 或直连 SQL。

`service_role` 带 `BYPASSRLS`，但表权限仍要 GRANT。`0003` 在角色存在时把四张业务表的读写和这些函数的 `EXECUTE` 授给 `service_role`，并收回 `PUBLIC` / `anon` / `authenticated` 对函数的执行权。API Key 只放在云托管环境变量里。

### 可选的协议直连

需要连接池、或 HTTP 网关不可用时，再配 `DATABASE_URL`。官方也把 PostgreSQL 协议作为事务和连接池的直连方式。控制台路径：云开发 → 环境 `wantuju-prod-d2gf1sf2r508a56b1` → 数据库 → PostgreSQL → 实例 `cloudbase-pg` → 连接信息。数据库名是 `postgres-4lino9f2`，schema 用 `public`。

参考：[连接数据库](https://docs.cloudbase.net/database/postgresql/connecting-to-postgresql)、[云托管 VPC](https://docs.cloudbase.net/run/deploy/networking/vpc)。

### 内网还是公网

服务和数据库在同一个云开发环境时，用控制台给出的**内网地址**。不要把公网地址配进 Cloud Run，除非控制台明确开了公网访问并做了 IP 白名单。

内网地址有两种常见形态，以控制台为准：

- 同环境内网域名：云托管实例通常可以直接解析，不必再配 VPC。
- VPC 私网 IP（`10.` / `172.16.`–`172.31.` / `192.168.`）：给云托管服务打开私有网络，选数据库所在的 VPC 和子网。安全组放通该子网访问 TCP `5432`。`VpcConf` 是服务访问数据库的出网配置，和小程序 `callContainer` 的入站无关。

小程序仍然用 `wx.cloud.callContainer`。关掉云托管公网入口不影响 callContainer，但容器自己必须能连上数据库。

### SSL

官方 Node 示例使用 `rejectUnauthorized: false`，对应 libpq 的 `sslmode=require`（加密，不校验私有 CA）。这是 `PGSSLMODE` 的默认值。如果控制台写明内网端点不启用 SSL，改成 `PGSSLMODE=disable`。本地 Postgres 用 `disable`。

### 行级安全（RLS）

CloudBase 给 `feature_configs` 打开了 RLS，而且没有策略。`anon` / `authenticated`（小程序 SDK、Publishable Key）因此读不到任何行，这是预期的。表主和超级用户默认跳过 RLS；`FORCE ROW LEVEL SECURITY` 会把表主也纳进策略。带 `BYPASSRLS` 的 `service_role` 仍然跳过 RLS。

HTTP 路径用 API Key，网关把它换成 `service_role`。直连路径用表主，或同样具备 `BYPASSRLS` 的账号。不要使用客户端匿名角色，也不要把 API Key 或数据库密码放到小程序里。

进程启动时会执行 `app/db/migrations/0002_rls.sql`：

- 给 `users`、`point_transactions`、`feature_jobs` 也打开 RLS，避免客户端角色以后被误授权。
- 收回 `PUBLIC`、`anon`、`authenticated` 在这四张表上的权限。
- 只给**执行迁移的当前角色**加一条 `FOR ALL ... USING (true)` 策略。

直连时，迁移角色和运行角色必须是同一个 `DATABASE_URL`。`0003_rpc.sql` 另外在 `service_role` 存在时授予表的读写和函数的 `EXECUTE`。策略没有授给 `anon` / `authenticated`，客户端仍然被拒绝。

## 迁移

启动时自动执行 `app/db/migrations/*.sql`，并记在 `public.schema_migrations`。也可以手动跑：

```bash
cd cloudrun/wantuju-api
uv run python -m app.db.migrate
```

没配 `DATABASE_URL` 时，迁移经 `POST /v1/rdb/exec-pgsql` 逐条执行，角色是 `cloudbase_postgres`。该角色可以做 DML；CloudBase 对它的 DDL 有白名单（策略、索引），`CREATE TABLE` / `CREATE FUNCTION` 可能被拒绝。遇到这种错误时，在控制台 SQL 编辑器（`cloudbase_admin`）按文件名顺序执行 `app/db/migrations/*.sql`，再重启服务。说明见 [执行 SQL](https://docs.cloudbase.net/http-api/pgdb/exec-pgsql) 和 [身份与权限收敛](https://docs.cloudbase.net/en/authentication-v2/auth/auth-pg)。

- `0000_feature_configs.sql` 与线上 DDL 一致，使用 `CREATE TABLE IF NOT EXISTS`。已有的 10 行不会被改写，也不会重复插入。
- `0001_app_tables.sql` 创建 `users`、`point_transactions`、`feature_jobs`。旧文档库已随环境释放，不做数据回填。
- `0002_rls.sql` 处理上面的 RLS。
- `0003_rpc.sql` 创建扣分、退款、领任务等函数，并在 `service_role` 存在时授权。

玩法表用 `sort_order` 而不是文档库里的 `order`。接口和后台仍对外使用 `order`。`validation` 为 NULL 时跳过图片校验。旧验证服务 `http://36.156.154.98:8010` 已不可用，不要把地址写回去。后台把校验字段全部留空会把 `validation` 存成 NULL。如果以后接 OpenAI 兼容视觉模型，填写 `validation.serviceUrl` / `model` / `prompt` / `failMessage`，并可选填 `validation.apiKey` 或环境变量 `VALIDATION_API_KEY`（请求头 `Authorization: Bearer`）。只配置了 Key、没有 URL 时不会发起校验。

## 本地运行

```bash
cd cloudrun/wantuju-api
uv sync
DATABASE_URL='postgresql://USER:PASSWORD@127.0.0.1:5432/wantuju?sslmode=disable' \
  uv run python -m uvicorn app.main:app --host 0.0.0.0 --port 8012
```

本地库可用 Docker：

```bash
docker run -d --name wantuju-pg \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=wantuju \
  -p 5432:5432 \
  postgres:17
```

测试使用本机 Postgres（默认 `postgresql://wantuju:wantuju@127.0.0.1:5432/wantuju?sslmode=disable`）。可以用 `TEST_DATABASE_URL` 覆盖，但主机必须是 `127.0.0.1` 或 `localhost`。

```bash
uv sync --group dev
uv run pytest
```

如果本地 `uv` 缓存权限异常，可临时使用项目内缓存：

```bash
UV_CACHE_DIR=.uv-cache uv run python -m uvicorn app.main:app --host 0.0.0.0 --port 8012
```

## 云托管部署

服务名固定为：

```text
wantuju-api
```

`cloudbaserc.json` 的环境 ID 是 `wantuju-prod-d2gf1sf2r508a56b1`。

部署步骤：

1. 在控制台确认 PostgreSQL 实例 `cloudbase-pg`、数据库 `postgres-4lino9f2` 可用。默认不需要复制内网地址。
2. 配置 `CLOUDBASE_ENV_ID`、`CLOUDBASE_APIKEY`、图片生成和管理端变量。`VALIDATION_API_KEY` 留空。不要设置 `DATABASE_URL`，除非要改走 psycopg。
3. 用 `cloudrun/wantuju-api` 的 Dockerfile 发布。容器启动后会自己跑迁移。
4. 看日志里的 `[数据库迁移]`。如果 `cloudbase_postgres` 不能建表或建函数，按上一节在 SQL 编辑器执行迁移文件后再重启。失败时服务仍会启动，但业务接口会返回 502。
5. 只有选用 psycopg 时才填写 `DATABASE_URL`。账号要是表主或 `BYPASSRLS`。主机若是 VPC 私网 IP，把云托管服务绑到同一 VPC / 子网，并放通 TCP 5432。
6. 小程序 `callContainer` 的云环境要指向 `wantuju-prod-d2gf1sf2r508a56b1`。代码里 `miniprogram/app.js` 仍写着已释放的旧环境 ID，切换环境时改那里，接口路径不用改。

Dockerfile 会监听 `${PORT:-80}`：

```bash
uv run python -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-80}
```

部署后先用小程序 callContainer 验证：

```js
wx.cloud.callContainer({
  config: { env: 'wantuju-prod-d2gf1sf2r508a56b1' },
  path: '/health',
  method: 'GET',
  header: { 'X-WX-SERVICE': 'wantuju-api' },
  success: console.log,
  fail: console.error,
})
```

再验证用户身份注入：

```js
wx.cloud.callContainer({
  config: { env: 'wantuju-prod-d2gf1sf2r508a56b1' },
  path: '/miniapp/whoami',
  method: 'GET',
  header: { 'X-WX-SERVICE': 'wantuju-api' },
  success: console.log,
  fail: console.error,
})
```

`/miniapp/whoami` 应返回非空 `openid`。

## 小程序接口

- `GET /health`：健康检查。
- `GET /miniapp/whoami`：查看 CloudBase/WeChat 注入的请求头和 `openid`。
- `GET /miniapp/features`：启用玩法列表。
- `GET /miniapp/features?type=palm`：单个启用玩法。
- `GET /miniapp/me`：当前用户资料和分享积分状态。
- `POST /miniapp/profile`：保存昵称头像。
- `GET /miniapp/share-reward/status`：分享积分状态。
- `POST /miniapp/share-reward/claim`：领取分享积分。
- `POST /miniapp/share-reward/check-in`：每日签到。
- `GET /miniapp/transactions`：积分流水。
- `GET /miniapp/tasks`：任务列表。
- `POST /miniapp/tasks`：创建任务并入队处理。
- `GET /miniapp/tasks/{task_id}`：任务详情。
- `GET /miniapp/tasks/{task_id}/status`：任务状态。
- `GET /miniapp/shared-tasks/{task_id}`：分享任务详情。
- `DELETE /miniapp/tasks/{task_id}`：删除当前用户任务。

## 管理端

入口：

```text
/admin/login
```

页面：

- `/admin/dashboard`：仪表盘、队列状态、处理中任务。
- `/admin/features`：玩法配置管理。嵌套字段（如 `public.title`）写入对应 JSONB 列。
- `/admin/users`：用户列表、详情、积分调整、封禁/解封、删除。
- `/admin/transactions`：积分流水筛选。
- `/admin/tasks`：任务筛选、图片预览。
- `/admin/storage`：云存储下载链接、上传授权、预览图合成。

管理端直接操作线上表。删除用户会在一个事务里删除该用户的积分流水和任务。只用测试用户验证危险操作。

## 任务处理

任务状态：

- `init`：小程序已创建任务，服务端尚未扣分接管。
- `pending`：已扣分，进入队列等待处理。
- `processing`：worker 已领取处理。
- `completed`：处理完成。
- `failed`：处理失败，已尝试退款。

队列行为：

- 最多 5 个任务并发处理。
- 其他任务保持 `pending` 排队。
- 领取任务调用 `wantuju_claim_job`，对 `feature_jobs` 行加锁。`pending` 可以领取；`processing` 只有租约超过 15 分钟才能被重新领取。
- 服务启动时会尝试恢复 `pending` 和超时 `processing` 任务。
- 恢复失败不会阻止服务启动，但需要查看日志排查数据库是否可用。

扣分、退款、人工调整、签到和分享奖励都在对应的 SQL 函数里完成，并对用户行 `SELECT ... FOR UPDATE`。积分列有 `points >= 0` 约束。HTTP 与 psycopg 都调用这些函数。

## 上线检查

部署后按顺序验证：

1. 日志出现 `[数据库迁移] PostgreSQL schema 已是最新` 或列出新应用的文件。
2. `/health` 返回 `status: ok`。
3. `/miniapp/whoami` 能拿到 `openid`。
4. 小程序首页玩法列表正常（`validation` 为 NULL 的玩法不会请求旧校验服务）。
5. 我的页面积分、签到、分享状态正常。
6. 上传图片创建任务，任务进入生成中。
7. 任务完成后结果页、生成记录、任务详情正常。
8. 管理端登录、仪表盘、玩法配置、用户管理、积分流水、任务列表正常。
9. 用测试用户验证积分调整、封禁/解封。

## 常见故障

### `{"detail":"Not Found"}`

请求已经到 CloudRun，但当前容器没有对应路由。

排查：

- 确认 `X-WX-SERVICE` 是 `wantuju-api`。
- 确认部署的是 `cloudrun/wantuju-api` 最新代码。
- 确认 Dockerfile 启动的是 `app.main:app`。

### `401 无法获取用户身份`

CloudRun 没拿到微信注入的 `openid`。

排查：

- 必须使用 `wx.cloud.callContainer`，不要用 `wx.request`。
- 调用 `/miniapp/whoami` 查看 header keys。
- 确认云托管服务允许小程序访问。
- 确认小程序云环境是 `wantuju-prod-d2gf1sf2r508a56b1`。

### PostgreSQL 连接失败或业务接口 502

默认路径排查：

- `CLOUDBASE_ENV_ID` 和 `CLOUDBASE_APIKEY` 是否是新环境的值。请求域名是 `https://wantuju-prod-d2gf1sf2r508a56b1.api.tcloudbasegateway.com`。
- 启动日志里的 `[数据库迁移失败]`。`403` 表示这个 Key 不能调用 `exec-pgsql`。`CREATE` 被拒绝时，到 SQL 编辑器执行 `app/db/migrations/*.sql`。
- RPC 返回找不到函数时，确认 `0003_rpc.sql` 已执行。迁移末尾会 `NOTIFY pgrst` 刷新 schema 缓存。
- 查询成功但永远是 0 行：当前身份不是 `service_role`，或 `0003` 没有把表 GRANT 给它。

直连路径再排查：

- `DATABASE_URL` 或 `PGHOST` / `PGUSER` / `PGPASSWORD` / `PGDATABASE` 是否完整。一旦设置，HTTP 数据层不会启用。
- 主机是否为内网地址。VPC IP 是否已把云托管服务绑到同一 VPC，安全组是否放通 5432。
- `sslmode=require` 连不上时，对照控制台改成 `disable` 再试。
- 账号是否为表主或 `BYPASSRLS`。如果查询成功但结果永远是 0 行，就是 RLS 把当前角色滤掉了。用执行迁移的那个角色连接，或换 `service_role`。

### 签到或分享并发异常

签到、分享、扣分和退款在 PostgreSQL 事务里对用户行加锁。若重复奖励或失败：

- 查看 `point_transactions` 是否有对应 `reason`（`share_reward`、`daily_check_in`、`create_feature_job`、`job_failed_refund`）。
- 确认没有两个 Cloud Run 服务连到不同的数据库。

### 任务长时间 pending

可能是队列未启动、worker 异常或启动恢复失败。

排查：

- 查看 CloudRun 日志里的 `[队列启动]`、`[队列取出]`、`[任务完成]`、`[任务失败]`、`task_claimed_processing`。
- 管理端 `/admin/dashboard` 查看队列状态和处理中任务。
- 检查 `MEMEFAST_API_KEY`、`MEMEFAST_API_URL`、`MEMEFAST_MODEL`。
- `processing` 且租约未过期的任务不会被另一个 worker 抢走。超过 15 分钟才会重新领取。

### 任务 failed 但未退款

失败退款由服务端执行。

排查：

- 查看任务字段 `pointsConsumed`、`pointsRefunded`、`refundErrMsg`。
- 查看积分流水是否有 `reason=job_failed_refund`。
- 如果 `refundErrMsg` 非空，优先看 PostgreSQL 事务错误和用户记录是否存在。

### 玩法列表为空，但表里有数据

多半是连库角色被 RLS 挡住。用表主或 `service_role` 重新部署，并确认启动迁移已为该角色创建 `backend_all_feature_configs`。客户端 SDK 读这张表会继续被拒绝，小程序应走 `/miniapp/features`。
