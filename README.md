# AI 海报生成小程序

基于微信小程序的 AI 图片生成应用，提供 **AI 看手相** 和 **AI 设计发型** 两大功能。

## 功能特性

- 🖐️ **AI 看手相** - 上传手掌照片，生成专属手相解读海报
- 💇 **AI 设计发型** - 上传正面照片，生成专属发型建议海报
- 🧪 **测试模式** - 前端 checkbox 切换，不消耗 API 费用
- 💾 **保存分享** - 支持保存海报到相册和分享

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
```

## 详细文档

查看 [DESIGN.md](DESIGN.md) 了解完整的项目设计、数据流和架构说明。

## 项目配置

- **AppID**: `wxa7c27609f05eb381`
- **云开发环境**: `cloud1-d7g1nt83fde793ad3`
- **基础库版本**: `3.15.2`
- **服务端地址**: `http://36.156.154.98:8011`
