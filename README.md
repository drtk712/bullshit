# AI 海报生成小程序

基于微信小程序的 AI 图片生成应用，提供 **AI 看手相** 和 **AI 设计发型** 两大功能。

## 功能特性

- 🖐️ **AI 看手相** - 上传手掌照片，生成专属手相解读海报
- 💇 **AI 设计发型** - 上传正面照片，生成专属发型建议海报
- 👤 **用户系统** - 微信一键登录，首次登录赠送 3 积分
- 💰 **积分系统** - 每次生成消耗 1 积分，失败自动退款
- 🧪 **测试模式** - 前端 switch 切换，不消耗 API 费用
- 🔧 **不扣积分开关** - 开发测试用，真实生成但不消耗积分
- 💾 **保存分享** - 支持保存海报到相册和分享
- 📱 **底部导航** - 首页 / 我的，查看积分和生成记录

## 技术架构

| 层级 | 技术 |
|------|------|
| 前端 | 微信小程序原生开发 |
| 云开发 | 微信云开发（云函数 + 云数据库 + 云存储） |
| 服务端 | Python 3.11 + FastAPI |
| AI 能力 | memefast.top (gpt-image-2-all) |

## 快速开始

### 前端

1. 使用微信开发者工具打开项目
2. 填写 `project.config.json` 中的 AppID
3. 上传云函数 `quickstartFunctions`
4. 编译预览

### 服务端

```bash
cd server/
uv sync
uvicorn main:app --host 0.0.0.0 --port 8011
```

### 环境变量

创建 `server/.env` 文件：

```env
MEMEFAST_API_KEY=your_api_key
MEMEFAST_API_URL=https://memefast.top/v1/chat/completions
POSTER_SERVER_TOKEN=shared_internal_token
```

云函数 `quickstartFunctions` 也需要配置同一个 `POSTER_SERVER_TOKEN`。本地开发可复制模板：

```bash
cp cloudfunctions/quickstartFunctions/.env.example cloudfunctions/quickstartFunctions/.env
```

然后编辑 `cloudfunctions/quickstartFunctions/.env`：

```env
POSTER_SERVER_URL=http://36.156.154.98:8011
POSTER_SERVER_TOKEN=shared_internal_token
VALIDATION_SERVICE_URL=http://36.156.154.98:8010/v1/chat/completions
VALIDATION_MODEL=qwen3.6

# 测试海报云文件 ID（与环境相关，需上传测试图到你的云存储）
TEST_POSTER_FILE_ID=cloud://your-env-id.your-bucket/ai-posters/test-poster.png
```

`server/.env` 和 `cloudfunctions/quickstartFunctions/.env` 都不会提交到 Git。

## 详细文档

查看 [DESIGN.md](DESIGN.md) 了解完整的项目设计、数据流和架构说明。
查看 [docs/plans/2026-05-03-user-points-tasks-design.md](docs/plans/2026-05-03-user-points-tasks-design.md) 了解用户/积分/生成记录系统设计。

## 云数据库集合

| 集合名 | 用途 |
|--------|------|
| `ai_poster_jobs` | AI 生成任务记录 |
| `users` | 用户信息（openid、积分等） |
| `point_transactions` | 积分流水（赠送/消耗/退款） |

## 云函数操作

| 操作类型 | 说明 |
|----------|------|
| `login` | 用户登录，首次赠送 3 积分 |
| `getUserProfile` | 获取用户资料、积分、最近任务 |
| `getFeatureConfig` | 获取功能配置 |
| `validateAndCreateJob` | 验证图片并创建生成任务（扣积分） |
| `getTaskStatus` | 查询任务状态（失败自动退款） |

## 项目配置

- **AppID**: `wxa7c27609f05eb381`
- **云开发环境**: `cloud1-d7g1nt83fde793ad3`
- **基础库版本**: `3.15.2`
- **服务端地址**: `http://36.156.154.98:8011`
