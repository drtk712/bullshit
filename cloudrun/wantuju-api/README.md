# Wantuju API CloudRun Service

微信云托管版后端服务，面向小程序提供 `wx.cloud.callContainer` 直连接口，并承载管理端 `/admin`。

## 服务范围

- 小程序用户资料、分享奖励、每日签到、积分流水。
- 玩法配置读取。
- 图片任务创建、校验、队列处理、结果上传、失败退款。
- 低风险图片工具：切图、拼长图。
- 管理端：仪表盘、玩法配置、用户管理、积分流水、任务列表、云存储工具。

## 代码结构

- `app/main.py`：FastAPI 应用入口，挂载路由并启动任务队列。
- `app/api/`：小程序 HTTP 路由。
- `app/admin/`：FastHTML 管理端路由和页面。
- `app/services/`：业务逻辑、任务队列、图片生成和工具处理。
- `app/cloudbase/`：CloudBase HTTP API、NoSQL、Storage 封装。
- `app/core/`：运行配置。

## 环境变量

必填：

```env
CLOUDBASE_ENV_ID=cloud1-d7g1nt83fde793ad3
CLOUDBASE_APIKEY=<CloudBase HTTP API Bearer Token>
CLOUDBASE_DB_INSTANCE=flexdb
CLOUDBASE_DB_NAME=tnt-gizs5ya5s

MEMEFAST_API_KEY=<图片生成模型 API Key>
MEMEFAST_API_URL=https://www.openclaudecode.cn/v1/chat/completions
MEMEFAST_MODEL=gpt-image-2

ADMIN_SESSION_SECRET=<强随机字符串>
ADMIN_PASSWORD=<管理端登录密码>
```

可选：

```env
CLOUDBASE_COMMAND_DB_INSTANCE=<命令/事务 API 实例，默认跟随 CLOUDBASE_DB_INSTANCE>
CLOUDBASE_COMMAND_DB_NAME=<命令/事务 API 数据库，默认跟随 CLOUDBASE_DB_NAME>
```

已经废弃，不要再配置或依赖：

```env
CLOUDBASE_ACCESS_TOKEN
POSTER_SERVER_URL
POSTER_SERVER_TOKEN
```

## 本地运行

```bash
cd cloudrun/wantuju-api
uv sync
uv run python -m uvicorn app.main:app --host 0.0.0.0 --port 8012
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

Dockerfile 会监听 `${PORT:-80}`：

```bash
uv run python -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-80}
```

部署后先用小程序 callContainer 验证：

```js
wx.cloud.callContainer({
  config: { env: 'cloud1-d7g1nt83fde793ad3' },
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
  config: { env: 'cloud1-d7g1nt83fde793ad3' },
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
- `GET /debug/routes`：调试当前容器实际挂载路由。
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
- `/admin/features`：玩法配置管理。
- `/admin/users`：用户列表、详情、积分调整、封禁/解封、删除。
- `/admin/transactions`：积分流水筛选。
- `/admin/tasks`：任务筛选、图片预览。
- `/admin/storage`：云存储下载链接、上传授权、预览图合成。

管理端会直接操作正式集合，删除用户会级联删除该用户的积分流水和任务记录。只用测试用户验证危险操作。

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
- 服务启动时会尝试恢复 `pending` 和超时 `processing` 任务。
- 恢复失败不会阻止服务启动，但需要查看日志排查 CloudBase API 是否可用。

## 上线检查

部署后按顺序验证：

1. `/health` 返回 `status: ok`。
2. `/debug/routes` 包含 `/miniapp/share-reward/check-in`、`/miniapp/tasks`、`/admin/login`。
3. `/miniapp/whoami` 能拿到 `openid`。
4. 小程序首页玩法列表正常。
5. 我的页面积分、签到、分享状态正常。
6. 上传图片创建任务，任务进入生成中。
7. 任务完成后结果页、生成记录、任务详情正常。
8. 管理端登录、仪表盘、玩法配置、用户管理、积分流水、任务列表正常。
9. 用测试用户验证积分调整、封禁/解封。

## 常见故障

### `{"detail":"Not Found"}`

请求已经到 CloudRun，但当前容器没有对应路由。

排查：

- 调用 `/debug/routes`，确认路由是否存在。
- 确认 `X-WX-SERVICE` 是 `wantuju-api`。
- 确认部署的是 `cloudrun/wantuju-api` 最新代码。
- 确认 Dockerfile 启动的是 `app.main:app`。

### `401 无法获取用户身份`

CloudRun 没拿到微信注入的 `openid`。

排查：

- 必须使用 `wx.cloud.callContainer`，不要用 `wx.request`。
- 调用 `/miniapp/whoami` 查看 header keys。
- 确认云托管服务允许小程序访问。

### CloudBase API `502`

服务端访问 CloudBase HTTP API 失败。

排查：

- 检查 `CLOUDBASE_ENV_ID`、`CLOUDBASE_APIKEY`。
- 检查 `CLOUDBASE_DB_INSTANCE`、`CLOUDBASE_DB_NAME`。
- 检查 CloudBase API Key 权限。
- 查看返回的 CloudBase request id。

### 签到或分享并发异常

签到和分享奖励通过 CloudBase 事务执行。若出现重复奖励或失败：

- 检查事务 URL 是否为 `/v1/database/instances/{instance}/databases/{database}/transactions`。
- 检查 `run_commands` 是否为 `/commands` 后缀。
- 查看 `point_transactions` 是否写入了对应 reason。

### 任务长时间 pending

可能是队列未启动、worker 异常或启动恢复失败。

排查：

- 查看 CloudRun 日志里的 `[队列启动]`、`[队列取出]`、`[任务完成]`、`[任务失败]`。
- 管理端 `/admin/dashboard` 查看队列状态和处理中任务。
- 检查 `MEMEFAST_API_KEY`、`MEMEFAST_API_URL`、`MEMEFAST_MODEL`。

### 任务 failed 但未退款

失败退款由服务端执行。

排查：

- 查看任务字段 `pointsConsumed`、`pointsRefunded`、`refundErrMsg`。
- 查看积分流水是否有 `reason=job_failed_refund`。
- 如果 `refundErrMsg` 非空，优先排查 CloudBase 事务或用户记录。
