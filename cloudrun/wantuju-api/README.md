# Wantuju API CloudRun Service

微信云托管版后端服务，面向小程序提供 `wx.cloud.callContainer` 直连接口，并承载管理端 `/admin`。

数据层使用 CloudBase PostgreSQL 17。小程序不直连数据库，接口形状保持不变。云存储仍走 CloudBase HTTP API。

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
- `app/db/`：PostgreSQL 连接池、迁移和积分 / 任务 / 玩法访问。
- `app/db/migrations/`：启动时按文件名顺序执行的 SQL。
- `app/cloudbase/`：CloudBase HTTP API 与云存储。文档数据库客户端已移除。
- `app/core/`：运行配置。

## 环境变量

在云托管服务配置里设置，不要写进仓库。

PostgreSQL（二选一）：

```env
DATABASE_URL=postgresql://USER:PASSWORD@HOST:5432/postgres-4lino9f2?sslmode=require
```

或拆开写。未设置 `DATABASE_URL` 时，服务用下面几项拼连接串：

```env
PGHOST=<控制台里的内网地址>
PGPORT=5432
PGUSER=<数据库账号>
PGPASSWORD=<数据库密码>
PGDATABASE=postgres-4lino9f2
PGSSLMODE=require
```

云存储和图片生成仍需要：

```env
CLOUDBASE_ENV_ID=wantuju-prod-d2gf1sf2r508a56b1
CLOUDBASE_APIKEY=<CloudBase HTTP API Bearer Token>

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

`DB_POOL_MAX` 是单个实例的连接池上限。云托管最大实例数乘以这个值要小于数据库最大连接数。

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

官方说明：云函数、云托管和自有后端用 PostgreSQL 协议直连，适合事务、复杂 SQL 和连接池。连接地址、端口、账号和密码以控制台为准。

控制台路径：云开发 → 环境 `wantuju-prod-d2gf1sf2r508a56b1` → 数据库 → PostgreSQL → 实例 `cloudbase-pg` → 连接信息。数据库名是 `postgres-4lino9f2`，schema 用 `public`。

参考：

- [连接数据库](https://docs.cloudbase.net/database/postgresql/connecting-to-postgresql)
- [角色与权限](https://docs.cloudbase.net/database/postgresql/roles)
- [云托管 VPC](https://docs.cloudbase.net/run/deploy/networking/vpc)

### 内网还是公网

服务和数据库在同一个云开发环境时，用控制台给出的**内网地址**。不要把公网地址配进 Cloud Run，除非控制台明确开了公网访问并做了 IP 白名单。

内网地址有两种常见形态，以控制台为准：

- 同环境内网域名：云托管实例通常可以直接解析，不必再配 VPC。
- VPC 私网 IP（`10.` / `172.16.`–`172.31.` / `192.168.`）：给云托管服务打开私有网络，选数据库所在的 VPC 和子网。安全组放通该子网访问 TCP `5432`。`VpcConf` 是服务访问数据库的出网配置，和小程序 `callContainer` 的入站无关。

小程序仍然用 `wx.cloud.callContainer`。关掉云托管公网入口不影响 callContainer，但容器自己必须能连上数据库。

### SSL

官方 Node 示例使用 `rejectUnauthorized: false`，对应 libpq 的 `sslmode=require`（加密，不校验私有 CA）。这是 `PGSSLMODE` 的默认值。如果控制台写明内网端点不启用 SSL，改成 `PGSSLMODE=disable`。本地 Postgres 用 `disable`。

### 行级安全（RLS）

CloudBase 给 `feature_configs` 打开了 RLS，而且没有策略。`anon` / `authenticated`（小程序 SDK、Publishable Key）因此读不到任何行，这是预期的。表主、超级用户，以及带 `BYPASSRLS` 的 `service_role` 不受这些策略限制，除非另外执行了 `FORCE ROW LEVEL SECURITY`。

Cloud Run 必须使用下面其中一种账号：

- 控制台「数据库账号」里创建 `feature_configs` 的那个主账号（表主）。
- 具备 `BYPASSRLS` 的 `service_role`。

不要使用客户端匿名角色，也不要把数据库密码放到小程序里。

进程启动时会执行 `app/db/migrations/0002_rls.sql`：

- 给 `users`、`point_transactions`、`feature_jobs` 也打开 RLS，避免客户端角色以后被误授权。
- 收回 `PUBLIC`、`anon`、`authenticated` 在这四张表上的权限。
- 只给**执行迁移的当前角色**加一条 `FOR ALL ... USING (true)` 策略。

所以迁移角色和运行角色必须是同一个 `DATABASE_URL`。表主和 `BYPASSRLS` 角色即使没有这条策略也能读写；如果 CloudBase 对表开了 `FORCE ROW LEVEL SECURITY`，这条策略保证迁移角色仍然能访问。策略没有授给 `anon` / `authenticated`，客户端仍然被拒绝。

## 迁移

启动时自动执行 `app/db/migrations/*.sql`，并记在 `public.schema_migrations`。也可以手动跑：

```bash
cd cloudrun/wantuju-api
uv run python -m app.db.migrate
```

- `0000_feature_configs.sql` 与线上 DDL 一致，使用 `CREATE TABLE IF NOT EXISTS`。已有的 10 行不会被改写，也不会重复插入。
- `0001_app_tables.sql` 创建 `users`、`point_transactions`、`feature_jobs`。旧文档库已随环境释放，不做数据回填。
- `0002_rls.sql` 处理上面的 RLS。

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

1. 在控制台确认 PostgreSQL 实例 `cloudbase-pg`、数据库 `postgres-4lino9f2` 可用，并复制内网连接信息。
2. 用该数据库账号作为 Cloud Run 的 `DATABASE_URL`（或 `PG*`）。这个账号要是表主，或者是 `service_role` 这类 `BYPASSRLS` 角色。
3. 如果主机是 VPC 私网 IP，在云托管服务设置里绑定同一 VPC / 子网，并放通 TCP 5432。
4. 配置上面的云存储、图片生成和管理端变量。`VALIDATION_API_KEY` 留空。
5. 用 `cloudrun/wantuju-api` 的 Dockerfile 发布。容器启动后会自己跑迁移。
6. 看日志里的 `[数据库迁移]`。失败时服务仍会启动，但业务接口会返回 502，需要先修好连接。
7. 小程序 `callContainer` 的云环境要指向 `wantuju-prod-d2gf1sf2r508a56b1`。代码里 `miniprogram/app.js` 仍写着已释放的旧环境 ID，切换环境时改那里，接口路径不用改。

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
- 领取任务时对 `feature_jobs` 行加锁。`pending` 可以领取；`processing` 只有租约超过 15 分钟才能被重新领取。
- 服务启动时会尝试恢复 `pending` 和超时 `processing` 任务。
- 恢复失败不会阻止服务启动，但需要查看日志排查 PostgreSQL 是否可用。

扣分、退款、人工调整、签到和分享奖励都在数据库事务里完成，并对用户行 `SELECT ... FOR UPDATE`。积分列有 `points >= 0` 约束。

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

排查：

- `DATABASE_URL` 或 `PGHOST` / `PGUSER` / `PGPASSWORD` / `PGDATABASE` 是否完整。
- 主机是否为内网地址。VPC IP 是否已把云托管服务绑到同一 VPC，安全组是否放通 5432。
- `sslmode=require` 连不上时，对照控制台改成 `disable` 再试。
- 账号是否为表主或 `BYPASSRLS`。如果查询成功但结果永远是 0 行，就是 RLS 把当前角色滤掉了。用执行迁移的那个角色连接，或换 `service_role`。
- 查看启动日志里的 `[数据库迁移失败]`。

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
