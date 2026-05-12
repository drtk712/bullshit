# 玩图局 - 项目设计文档

> 历史说明：本文描述的是早期「小程序 + quickstartFunctions 云函数 + 外部 FastAPI server」方案。当前主链路已迁移到微信云托管 `cloudrun/wantuju-api`，小程序通过 `wx.cloud.callContainer` 直连云托管服务。当前部署和运维请以 [cloudrun/wantuju-api/README.md](cloudrun/wantuju-api/README.md) 为准，旧链路退场计划见 [docs/operations/legacy-decommission-checklist.md](docs/operations/legacy-decommission-checklist.md)。

## 项目概述

基于微信小程序的图片玩法合集平台。用户上传照片，选择玩法，系统自动生成/改造/解读图片内容，支持保存和分享。

当前开放**看手相**和**设计发型**两大核心功能，采用云配置驱动的模块化架构，未来可快速扩展至老照片修复、头像生成、风格转换、宠物拟人、节日写真、商品图优化等更多玩法。

**AppID**: `wxa7c27609f05eb381`  
**云开发环境**: `cloud1-d7g1nt83fde793ad3`  
**基础库版本**: `3.15.2`

---

## 技术架构

### 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                        微信小程序前端                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │  palm 页面   │  │  hair 页面   │  │  featurePage.js (公共逻辑) │  │
│  └──────┬──────┘  └──────┬──────┘  └──────────┬──────────┘  │
│         └────────────────┼────────────────────┘             │
│                          │ wx.cloud.callFunction            │
└──────────────────────────┼──────────────────────────────────┘
                           │
┌──────────────────────────┼──────────────────────────────────┐
│                     微信云开发                                 │
│  ┌─────────────────────▼──────────────────────────────────┐  │
│  │              quickstartFunctions (云函数)                 │  │
│  │  ┌──────────────────────────────────────────────────┐  │  │
│  │  │  validateAndCreateJob  │  getTaskStatus           │  │  │
│  │  │  validateImage         │  ensureCollection        │  │  │
│  │  └──────────────────────────────────────────────────┘  │  │
│  └────────────────────────┬────────────────────────────────┘  │
│                           │ axios                              │
│  ┌────────────────────────┼────────────────────────────────┐  │
│  │  云数据库 (feature_jobs) │  云存储 (posters/)       │  │
│  └────────────────────────────────────────────────────────┘  │
└───────────────────────────┼───────────────────────────────────┘
                            │ HTTP
┌───────────────────────────┼───────────────────────────────────┐
│                     外部 FastAPI 服务端                         │
│  ┌──────────────────────▼──────────────────────────────────┐  │
│  │  http://36.156.154.98:8011                              │  │
│  │  ┌──────────────────────────────────────────────────┐  │  │
│  │  │  POST /api/job     │  GET /api/job/{task_id}      │  │  │
│  │  │  GET /health       │  测试模式 (test=true)        │  │  │
│  │  └──────────────────────────────────────────────────┘  │  │
│  └────────────────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────────────┘
                            │
┌───────────────────────────┼───────────────────────────────────┐
│                     第三方生成接口                               │
│  ┌──────────────────────▼──────────────────────────────────┐  │
│  │  memefast.top (gpt-image-2-all) - 海报生成               │  │
│  │  36.156.154.98:8010 (qwen3.6) - 图片验证                │  │
│  └────────────────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────────────┘
```

### 技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| **前端** | 微信小程序原生开发 | WXML + WXSS + JavaScript |
| **云开发** | 微信云开发 | 云函数 + 云数据库 + 云存储 |
| **服务端** | Python 3.11 + FastAPI | 异步任务处理 |
| **生成能力** | memefast.top API | gpt-image-2-all 模型 |
| **图片验证** | qwen3.6 API | 图片质量验证 |

---

## 核心功能

### 1. 看手相

- 上传清晰手掌照片
- 系统分析手相特征
- 生成专属手相解读海报
- 支持保存和分享

### 2. 设计发型

- 上传正面清晰照片
- 系统分析脸型特征
- 生成专属发型建议海报
- 支持保存和分享

### 3. 测试模式

- 前端 checkbox 切换测试模式
- 测试模式不调用付费 API
- 模拟 15 秒后返回固定测试图片
- 用于开发和调试，节省 API 费用

---

## 数据流

### 正常流程

```
1. 用户选择图片
   ↓
2. 前端压缩图片 (quality: 70)
   ↓
3. 上传到云存储 (upload/)
   ↓
4. 调用云函数 validateAndCreateJob
   ↓
5. 云函数验证图片质量 (qwen3.6 API)
   ↓
6. 获取图片临时链接
   ↓
7. 调用外部服务端 POST /api/job
   ↓
8. 服务端创建异步任务，返回 taskId
   ↓
9. 云函数保存任务到数据库 (status: pending)
   ↓
10. 前端开始轮询 (10秒间隔，最多60次)
    ↓
11. 云函数查询服务端状态 GET /api/job/{taskId}
    ↓
12. 服务端调用生成接口生成海报
    ↓
13. 服务端返回 posterUrl
    ↓
14. 云函数下载海报并上传到云存储 (posters/)
    ↓
15. 云函数更新数据库 (status: completed, posterFileID)
    ↓
16. 前端获取 posterFileID，直接使用 cloud:// 协议显示图片
    ↓
17. 用户可保存或分享海报
```

### 测试模式流程

```
1-6. 同正常流程
   ↓
7. 调用外部服务端 POST /api/job (test: true)
   ↓
8. 服务端等待 15 秒（模拟生成时间）
   ↓
9. 返回固定测试图片 URL
   ↓
10-17. 同正常流程
```

---

## 数据库设计

### 集合：feature_jobs

| 字段 | 类型 | 说明 |
|------|------|------|
| `_id` | String | 文档 ID（自动生成） |
| `type` | String | 任务类型：`palm` 或 `hair` |
| `fileID` | String | 用户上传的云存储文件 ID |
| `serverTaskId` | String | 服务端任务 ID |
| `status` | String | 任务状态：`pending` / `completed` / `failed` |
| `posterFileID` | String | 生成的海报云存储文件 ID |
| `errMsg` | String | 错误信息（失败时） |
| `openid` | String | 用户 openid |
| `createdAt` | Number | 创建时间戳 |
| `updatedAt` | Number | 更新时间戳 |

---

## 云函数设计

### quickstartFunctions

| 函数 | 说明 | 输入 | 输出 |
|------|------|------|------|
| `validateAndCreateJob` | 验证图片并创建任务 | `{ type, fileID, test }` | `{ success, data: { taskId } }` |
| `getTaskStatus` | 查询任务状态 | `{ taskId }` | `{ success, data: { status, posterFileID, errMsg } }` |

### 关键实现

- **ensureCollection**: 自动创建数据库集合，忽略"集合已存在"错误 (-501001)
- **validateImage**: 调用 qwen3.6 API 验证图片质量
- **轮询机制**: 前端 10 秒间隔轮询，最多 60 次（10 分钟超时）

---

## 服务端设计

### FastAPI 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/job` | POST | 创建图片生成任务 |
| `/api/job/{task_id}` | GET | 查询任务状态 |
| `/health` | GET | 健康检查 |

### 请求/响应模型

```python
class JobRequest(BaseModel):
    imageUrl: str
    type: str  # "palm" or "hair"
    test: bool = False  # 测试模式，不调用API

class JobCreateResponse(BaseModel):
    taskId: str

class JobStatusResponse(BaseModel):
    status: str  # "pending", "processing", "completed", "failed"
    posterUrl: str | None = None
    errMsg: str | None = None
```

### 关键特性

- **异步任务处理**: `BackgroundTasks` + `asyncio.to_thread()` 避免阻塞
- **线程安全**: `asyncio.Lock` 保护任务字典
- **任务过期清理**: 1 小时自动清理过期任务
- **日志脱敏**: `mask_url()` 函数脱敏 URL 日志

---

## 前端设计

### 页面结构

```
miniprogram/
├── pages/
│   ├── palm/          # 看手相页面
│   └── hair/          # 设计发型页面
├── utils/
│   └── featurePage.js      # 公共玩法页面逻辑
└── app.js             # 应用入口
```

### featurePage.js 公共逻辑

| 方法 | 说明 |
|------|------|
| `chooseImage` | 选择图片 |
| `compressAndProcess` | 压缩图片 |
| `uploadAndCall` | 上传到云存储并调用云函数 |
| `createJob` | 创建任务并开始轮询 |
| `startPolling` | 递归轮询任务状态 |
| `toggleTestMode` | 切换测试模式 |
| `savePoster` | 保存海报到相册 |
| `sharePoster` | 分享海报 |
| `cleanupTask` | 清理定时器和任务 ID |

### 关键实现

- **轮询机制**: 递归 `setTimeout` 而非 `setInterval`，确保上次请求完成后再等待 10 秒
- **图片显示**: 直接使用 `cloud://` 协议，无需异步转换
- **生命周期**: `onShow` 恢复轮询，`onHide`/`onUnload` 清理任务

---

## 部署说明

### 前端部署

1. 微信开发者工具打开项目
2. 上传云函数 `quickstartFunctions`
3. 编译并预览小程序

### 服务端部署

```bash
cd server/
uvicorn main:app --host 0.0.0.0 --port 8011
```

### 环境变量

服务端需要配置 `.env` 文件：

```env
MEMEFAST_API_KEY=your_api_key
MEMEFAST_API_URL=https://memefast.top/v1/chat/completions
```

---

## 已知问题与优化建议

### 当前限制

1. 轮询超时时间较长（10 分钟），可考虑优化为 WebSocket 或 Server-Sent Events
2. 图片验证依赖外部 API，可增加本地验证逻辑
3. 测试模式图片为固定 URL，可增加随机测试图片

### 未来优化

1. 增加用户历史记录功能
2. 增加海报模板选择
3. 增加分享海报到社交平台功能
4. 增加付费 API 调用统计和限额管理

---

## 项目结构

```
wantujv/
├── DESIGN.md                      # 项目设计文档
├── README.md                      # 项目说明
├── project.config.json            # 小程序项目配置
├── miniprogram/                   # 小程序前端
│   ├── app.js                     # 应用入口
│   ├── app.json                   # 应用配置
│   ├── app.wxss                   # 全局样式
│   ├── pages/
│   │   ├── index/                 # 首页
│   │   ├── palm/                  # 看手相
│   │   └── hair/                  # 设计发型
│   └── utils/
│       └── featurePage.js              # 公共逻辑
├── cloudfunctions/                # 云函数
│   └── quickstartFunctions/
│       ├── index.js               # 云函数入口
│       └── package.json
└── server/                        # 外部 FastAPI 服务端
    ├── main.py                    # 服务端入口
    ├── .env                       # 环境变量
    ├── pyproject.toml             # Python 依赖
    └── uv.lock                    # 依赖锁文件
```

---

**文档版本**: v1.0  
**最后更新**: 2026-05-03  
**维护者**: Sisyphus
