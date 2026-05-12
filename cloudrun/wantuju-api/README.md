# Wantuju API CloudRun Service

独立的微信云托管 FastAPI 服务，用于开发版/体验版小程序验证 `wx.cloud.callContainer` 直连链路。

## 当前接口

- `GET /health`：服务健康检查
- `GET /miniapp/whoami`：返回 CloudBase/WeChat 注入的请求头，并尝试解析 `openid`
- `GET /miniapp/features`：返回启用的玩法公开配置
- `GET /miniapp/features?type=palm`：返回单个启用玩法公开配置
- `GET /miniapp/me`：返回当前用户资料与分享积分状态
- `POST /miniapp/profile`：保存用户昵称和头像
- `GET /miniapp/share-reward/status`：返回分享积分状态
- `POST /miniapp/share-reward/claim`：领取分享积分
- `POST /miniapp/share-reward/check-in`：每日签到领取积分
- `GET /miniapp/transactions`：分页返回当前用户积分流水
- `GET /miniapp/tasks`：分页返回当前用户任务
- `POST /miniapp/tasks`：校验图片、创建任务并进入云托管内部处理队列
- `GET /miniapp/tasks/{task_id}`：返回当前用户任务详情
- `GET /miniapp/tasks/{task_id}/status`：返回当前用户任务状态
- `GET /miniapp/shared-tasks/{task_id}`：返回公开分享任务详情
- `DELETE /miniapp/tasks/{task_id}`：删除当前用户任务记录
- `GET /admin/dashboard`：管理端仪表盘，需要管理员登录
- `GET /admin/features`：玩法配置管理
- `GET /admin/users`：用户管理
- `GET /admin/transactions`：积分流水管理
- `GET /admin/tasks`：任务管理
- `GET /admin/storage`：云存储工具

## 代码结构

- `app/main.py`：FastAPI 应用入口，只挂载路由
- `app/api/`：HTTP 路由层
- `app/services/`：业务逻辑层
- `app/cloudbase/`：CloudBase HTTP API 与 NoSQL 基础封装
- `app/core/`：配置等基础设施

## 本地运行

```bash
uv sync
uv run python -m uvicorn app.main:app --host 0.0.0.0 --port 8012
```

## 环境变量

- `CLOUDBASE_ENV_ID`：云开发环境 ID
- `CLOUDBASE_APIKEY`：CloudBase HTTP API Bearer Token
- `CLOUDBASE_DB_INSTANCE`：NoSQL 实例，默认 `flexdb`
- `CLOUDBASE_DB_NAME`：NoSQL 数据库，默认 `tnt-gizs5ya5s`
- `CLOUDBASE_COMMAND_DB_INSTANCE`：命令/事务 API 实例，默认跟随 `CLOUDBASE_DB_INSTANCE`
- `CLOUDBASE_COMMAND_DB_NAME`：命令/事务 API 数据库，默认跟随 `CLOUDBASE_DB_NAME`
- `MEMEFAST_API_KEY`：图片生成模型 API Key
- `MEMEFAST_API_URL`：图片生成模型接口地址，默认 `https://memefast.top/v1/chat/completions`
- `MEMEFAST_MODEL`：图片生成模型名，默认 `gpt-image-2-all`
- `ADMIN_SESSION_SECRET`：管理端登录 Cookie 签名密钥
- `ADMIN_PASSWORD`：管理端登录密码

## 云托管启动

Dockerfile 会监听 `${PORT:-80}`：

```bash
uv run python -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-80}
```

## 小程序调用示例

```js
wx.cloud.callContainer({
  config: { env: 'cloud1-d7g1nt83fde793ad3' },
  path: '/miniapp/whoami',
  method: 'GET',
  header: {
    'X-WX-SERVICE': 'wantuju-api',
  },
})
```

第一阶段用于确认云托管能否拿到可信 `openid`，并把玩法配置这类低风险只读接口迁到云托管。
