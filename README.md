# 玩图局

基于微信小程序的图片玩法合集。用户上传照片，选择玩法，系统自动生成/改造/解读图片内容，支持保存和分享。

当前后端主链路已迁移到微信云托管 `cloudrun/wantuju-api`，小程序通过 `wx.cloud.callContainer` 直连云托管服务。旧 `cloudfunctions/quickstartFunctions` 和旧 `server` 仅作为历史备份保留。

运维与部署以 [cloudrun/wantuju-api/README.md](cloudrun/wantuju-api/README.md) 为准；旧链路退场计划见 [docs/operations/legacy-decommission-checklist.md](docs/operations/legacy-decommission-checklist.md)。

## 功能特性

- 🖐️ **看手相** - 上传手掌照片，生成趣味手相解读
- 💇 **设计发型** - 上传正面照片，生成发型建议和效果图
- 🔮 **可扩展** - 支持接入老照片修复、头像生成、风格转换、宠物拟人、节日写真等更多玩法
- 👤 **用户系统** - 微信一键登录，首次登录赠送 3 积分
- 💰 **积分系统** - 每次生成消耗 1 积分，失败自动退款
- 💾 **保存分享** - 支持保存生成结果到相册和分享
- 📱 **底部导航** - 首页 / 我的，查看积分和生成记录

## 技术架构

| 层级 | 技术 |
|------|------|
| 前端 | 微信小程序原生开发 |
| 云开发 | 微信云托管 + 云数据库 + 云存储 |
| 服务端 | Python 3.11 + FastAPI (`cloudrun/wantuju-api`) |
| 生成能力 | `MEMEFAST_API_URL` 配置的图片生成模型 |

## 快速开始

### 前端

1. 使用微信开发者工具打开项目
2. 填写 `project.config.json` 中的 AppID
3. 确认云托管服务 `wantuju-api` 已部署
4. 编译预览

### 服务端

```bash
cd cloudrun/wantuju-api
uv sync
uv run python -m uvicorn app.main:app --host 0.0.0.0 --port 8012
```

### 环境变量

在云托管服务配置：

```env
CLOUDBASE_ENV_ID=cloud1-d7g1nt83fde793ad3
CLOUDBASE_APIKEY=<CloudBase HTTP API Bearer Token>
CLOUDBASE_DB_INSTANCE=flexdb
CLOUDBASE_DB_NAME=tnt-gizs5ya5s
MEMEFAST_API_KEY=<图片生成模型 API Key>
MEMEFAST_API_URL=<图片生成模型接口地址>
MEMEFAST_MODEL=<图片生成模型名>
ADMIN_SESSION_SECRET=<管理端 Cookie 签名密钥>
ADMIN_PASSWORD=<管理端登录密码>
```

## 详细文档

查看 [cloudrun/wantuju-api/README.md](cloudrun/wantuju-api/README.md) 了解 CloudRun 部署、接口、管理端和排障说明。

[DESIGN.md](DESIGN.md) 和 `docs/plans/` 下的旧设计文档保留为历史参考，不再代表当前主链路。

## 云数据库集合

| 集合名 | 用途 |
|--------|------|
| `feature_jobs` | 生成任务记录 |
| `users` | 用户信息（openid、积分等） |
| `point_transactions` | 积分流水（赠送/消耗/退款） |

## CloudRun 小程序接口

| 接口 | 说明 |
|------|------|
| `/miniapp/features` | 获取玩法配置 |
| `/miniapp/me` | 获取用户资料 |
| `/miniapp/share-reward/*` | 分享奖励和每日签到 |
| `/miniapp/transactions` | 积分明细 |
| `/miniapp/tasks*` | 任务创建、查询、删除 |
| `/admin/*` | 管理端 |

## 项目配置

- **AppID**: `wxa7c27609f05eb381`
- **云开发环境**: `cloud1-d7g1nt83fde793ad3`
- **基础库版本**: `3.15.2`
- **云托管服务**: `wantuju-api`
