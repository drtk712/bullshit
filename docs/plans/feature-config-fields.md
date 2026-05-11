# 玩法配置字段定义

> 集合名：`feature_configs` | 数据库：CloudBase NoSQL (flexdb/tnt-gizs5ya5s)
> 最后更新：2026-05-07

## 文档结构

每个玩法是一个独立文档，`_id` 为随机字符串，`type` 为玩法唯一标识。

```
feature_configs
├── _id              # 文档 ID（随机字符串）
├── type             # 玩法标识，如 palm / hair / profile / doodle / crayon / soul
├── enabled          # 是否启用
├── order            # 排序权重（MongoDB EJSON: {"$numberDouble": "10.0"}）
├── public           # 公开可见字段（小程序端可读取）
├── ui               # UI 渲染配置
├── validation       # 图片验证配置
├── generation       # 生成配置
└── test             # 测试数据
```

## 字段详情

### 基础字段

| 字段 | 类型 | 必填 | 说明 | 示例 |
|------|------|------|------|------|
| `_id` | string | 自动 | 文档唯一 ID | `"3ff49ca369fade3d000c1a3f54c1ddde"` |
| `type` | string | ✅ | 玩法标识，用于路由和查询 | `"palm"` |
| `enabled` | boolean | ✅ | 是否在前端展示 | `true` |
| `order` | number | ✅ | 排序权重，越小越靠前 | `10.0` |

### public（公开信息）

| 字段 | 类型 | 必填 | 说明 | 示例 |
|------|------|------|------|------|
| `public.title` | string | ✅ | 玩法完整标题 | `"看手相"` |
| `public.category` | string | ✅ | 首页分类名称，固定可选：`趣味` / `人像` / `风格化` / `创意` / `工具` / `营销` | `"趣味"` |
| `public.description` | string | ✅ | 玩法描述（详情/卡片展示） | `"上传清晰手掌照片，生成趣味手相解读海报"` |
| `public.homeDesc` | string | | 首页一句话描述 | `"看看你的手相"` |
| `public.uploadTitle` | string | ✅ | 上传页标题 | `"上传手掌照片"` |
| `public.cardSize` | string | | 卡片尺寸：`normal` / `wide` | `"normal"` |
| `public.previewImageHD` | string | | 预览图云存储 ID | `"cloud://.../preview-image/手相.png"` |

### ui（UI 渲染配置）

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `ui.progressTitle` | string | ✅ | 进度页加载文案 |
| `ui.detailSubtitle` | string | ✅ | 详情页副标题 |
| `ui.requirements` | string[] | ✅ | 上传要求列表（纯文本数组） |
| `ui.requirementItems` | object[] | | 详情页拍摄要求 |
| `ui.analysisItems` | object[] | | 分析维度列表 |
| `ui.progressChecks` | object[] | | 进度检查步骤 |
| `ui.tags` | object[] | | 玩法标签 |

#### ui.requirementItems / ui.tags 结构

```json
{ "text": "光线充足" }
```

- `text`: 显示文案

#### ui.analysisItems 结构

```json
{
  "title": "生命线",
  "items": ["精力旺盛", "健康指数高"]
}
```

#### ui.progressChecks 结构

```json
{
  "title": "图像清晰度检测",
  "status": "完成"
}
```

- `status`: `"完成"` / `"progress"` / `"等待中"`

### validation（图片验证）

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `validation.serviceUrl` | string | ✅ | 验证服务 URL |
| `validation.model` | string | ✅ | 验证模型 |
| `validation.prompt` | string | ✅ | 验证 prompt（需返回"是"或"否"） |
| `validation.failMessage` | string | ✅ | 验证失败提示 |

### generation（生成）

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `generation.prompt` | string | ✅ | 生成 prompt |

### test（测试数据）

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `test.posterFileID` | string | | 测试海报云文件 ID |

## 完整示例

```json
{
  "_id": "3ff49ca369fade3d000c1a3f54c1ddde",
  "type": "palm",
  "enabled": true,
  "order": 10.0,
  "public": {
    "title": "看手相",
    "category": "趣味",
    "description": "上传清晰手掌照片，生成趣味手相解读海报",
    "homeDesc": "看看你的手相",
    "uploadTitle": "上传手掌照片",
    "cardSize": "normal",
    "previewImageHD": "cloud://.../preview-image/手相.png"
  },
  "ui": {
    "progressTitle": "正在解读手相...",
    "detailSubtitle": "你的专属手相解读",
    "requirements": ["清晰的手掌照片", "手掌朝上", "光线充足"],
    "requirementItems": [
      {"text": "手掌完整"},
      {"text": "光线充足"},
      {"text": "纹路清晰"}
    ],
    "analysisItems": [
      {"title": "生命线", "items": ["精力旺盛", "健康指数高"]},
      {"title": "智慧线", "items": ["思维敏捷", "逻辑清晰"]},
      {"title": "感情线", "items": ["情感丰富", "重情重义"]},
      {"title": "事业线", "items": ["事业心强", "稳步上升"]}
    ],
    "progressChecks": [
      {"title": "图像清晰度检测", "status": "完成"},
      {"title": "手掌区域识别", "status": "完成"},
      {"title": "掌纹特征分析", "status": "progress"},
      {"title": "生成手相报告", "status": "等待中"}
    ],
    "tags": [
      {"text": "手相解读"},
      {"text": "趣味分析"},
      {"text": "运势海报"}
    ]
  },
  "validation": {
    "serviceUrl": "http://36.156.154.98:8010/v1/chat/completions",
    "model": "qwen3.6",
    "prompt": "这张图片是否包含清晰的手掌照片？请只回答'是'或'否'。",
    "failMessage": "图片不符合要求，请重新拍摄清晰手掌照片"
  },
  "generation": {
    "prompt": "Based on this palm photo, generate a beautiful palmistry analysis poster..."
  },
  "test": {
    "posterFileID": "cloud://.../posters/test-poster.png"
  }
}
```

## 注意事项

1. **emoji 限制**：CloudBase API 不支持 emoji 字符，写入会返回 400 错误。玩法配置不再维护图标字段，文案字段也应避免 emoji
2. **order 格式**：MongoDB 存储为 EJSON `{"$numberDouble": "10.0"}`，读取时需解包
3. **新增玩法**：复制现有文档，修改 `type`、`public.*`、`validation.prompt`、`generation.prompt` 即可
4. **管理后台**：通过 `/admin/features` 可视化编辑，表单提交时自动处理编码和嵌套字段
