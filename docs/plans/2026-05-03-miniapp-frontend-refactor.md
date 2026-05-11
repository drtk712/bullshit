# Miniapp Frontend Refactor Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Refactor the WeChat mini-program frontend and feature configuration into a modern, minimal WeChat-style, cloud-config-driven framework where new capabilities such as makeup design can be adjusted mainly from cloud function config.

**Architecture:** The mini-program becomes a thin client: it fetches public feature metadata from the cloud function and renders a generic feature page. The cloud function owns the full feature registry, including public UI copy, image validation prompt, poster generation prompt, feature enablement, and ordering. The FastAPI server no longer hardcodes palm/hair prompts; it receives a generation prompt from the trusted cloud function when a job is created.

**Tech Stack:** WeChat Mini Program native WXML/WXSS/JavaScript, WeChat cloud functions with CommonJS modules, WeChat cloud database/storage, Python 3.11 + FastAPI.

---

## Why This Plan Changed

The previous plan put `FEATURE_CONFIGS` in `miniprogram/utils/featureConfigClient.js`. That reduces duplicated frontend code but still requires a mini-program release to adjust feature copy, validation rules, or generation prompts. This is not flexible enough.

The improved design moves feature configuration into the cloud function:

- Frontend receives only **public UI config**.
- Cloud function keeps **private operational config** such as validation prompts and generation prompts.
- FastAPI server receives the selected `generationPrompt` from cloud function, so prompt edits happen in one cloud-deployed location.
- A generic `/pages/feature/index?type=palm` page removes the need to create one separate page per feature when UI flow is identical.

---

## Current Hardcoded Locations Found

- `cloudfunctions/quickstartFunctions/index.js:40-43`
  - `validateImage()` hardcodes validation prompts for `palm` and `hair`.
- `cloudfunctions/quickstartFunctions/index.js:47`
  - Validation service URL is hardcoded as infrastructure config.
- `cloudfunctions/quickstartFunctions/index.js:130`
  - `validateAndCreateJob()` hardcodes allowed types: `["palm", "hair"]`.
- `server/main.py:67-80`
  - `generate_poster()` hardcodes palm/hair generation prompts.
- `server/main.py:202`
  - FastAPI hardcodes allowed types: `["palm", "hair"]`.
- `miniprogram/pages/index/index.js`
  - Home page hardcodes feature list.
- `miniprogram/pages/palm/*` and `miniprogram/pages/hair/*`
  - Feature pages duplicate the same UI with small copy/icon differences.

---

## Target Architecture

```
miniprogram/
├── app.json
├── app.wxss
├── pages/
│   ├── index/                 # Home page fetches cloud feature list
│   └── feature/               # Generic feature page: /pages/feature/index?type=palm
│       ├── index.js
│       ├── index.json
│       ├── index.wxml
│       └── index.wxss
├── styles/
│   └── feature-page.wxss           # Shared minimal feature page styles
└── utils/
    ├── featurePage.js              # Modify: generic factory reads feature type from data
    └── featureConfigClient.js # Thin client for cloud getFeatureConfig

cloudfunctions/
└── quickstartFunctions/
    ├── index.js               # Adds getFeatureConfig and uses cloud config for jobs
    └── featureConfig.js       # Full feature registry: public + private prompts

server/
└── main.py                    # Accepts generationPrompt from cloud function
```

---

## Config Contract

### Full Cloud Function Config Shape

Create `cloudfunctions/quickstartFunctions/featureConfig.js`.

```javascript
const FEATURE_CONFIGS = {
  palm: {
    type: "palm",
    enabled: true,
    order: 10,
    public: {
      title: "看手相",
      shortTitle: "看手相",
      description: "上传清晰手掌照片，生成专属手相解读海报",
      icon: "🖐️",
      uploadIcon: "📷",
      uploadTitle: "上传手掌照片",
      uploadTip: "请确保手掌完整、纹路清晰、光线充足",
      retryText: "重新上传",
      route: "/pages/feature/index?type=palm"
    },
    validation: {
      serviceUrl: process.env.VALIDATION_SERVICE_URL || "http://36.156.154.98:8010/v1/chat/completions",
      model: process.env.VALIDATION_MODEL || "qwen3.6",
      prompt: "这张图片是否包含清晰的手掌照片？请只回答'是'或'否'。",
      failMessage: "图片不符合要求，请重新拍摄清晰手掌照片"
    },
    generation: {
      prompt: `Based on this palm photo, generate a beautiful palmistry analysis poster in Chinese.
Style: minimalist line art, elegant typography, warm beige background.
Include: a traced palm outline with labeled lines (生命线/智慧线/感情线/事业线), personality traits section, career compatibility section, emotional characteristics section.
Text should be in Chinese. Format: vertical poster, clean layout, professional look.`
    },
    test: {
      posterFileID: "cloud://cloud1-d7g1nt83fde793ad3.636c-cloud1-d7g1nt83fde793ad3-1427592986/posters/0274fd6869f6176c00082cfb0eeefd94.png"
    }
  },
  hair: {
    type: "hair",
    enabled: true,
    order: 20,
    public: {
      title: "设计发型",
      shortTitle: "设计发型",
      description: "上传正面照片，生成专属发型建议海报",
      icon: "💇",
      uploadIcon: "📷",
      uploadTitle: "上传正面照片",
      uploadTip: "请确保脸部正面清晰、无遮挡、光线充足",
      retryText: "重新上传",
      route: "/pages/feature/index?type=hair"
    },
    validation: {
      serviceUrl: process.env.VALIDATION_SERVICE_URL || "http://36.156.154.98:8010/v1/chat/completions",
      model: process.env.VALIDATION_MODEL || "qwen3.6",
      prompt: "这张图片是否包含清晰的正面人像照片？请只回答'是'或'否'。",
      failMessage: "图片不符合要求，请重新拍摄清晰正面人像"
    },
    generation: {
      prompt: `Based on this person's photo, generate a professional hairstyle analysis poster in Chinese.
Style: modern clean layout, white cards, WeChat-friendly visual tone.
Include: person's photo with face analysis (脸型/发质/发色), recommended hairstyles, styles to avoid, hair care tips, product recommendations.
Text should be in Chinese. Format: vertical poster, clean layout, professional look.`
    },
    test: {
      posterFileID: "cloud://cloud1-d7g1nt83fde793ad3.636c-cloud1-d7g1nt83fde793ad3-1427592986/posters/0274fd6869f6176c00082cfb0eeefd94.png"
    }
  }
};

function getFeatureConfig(type) {
  return FEATURE_CONFIGS[type];
}

function getEnabledFeatureConfig(type) {
  const config = getFeatureConfig(type);
  if (!config || !config.enabled) return null;
  return config;
}

function toPublicFeature(config) {
  return {
    type: config.type,
    enabled: config.enabled,
    order: config.order,
    ...config.public
  };
}

function getPublicFeatureList() {
  return Object.values(FEATURE_CONFIGS)
    .filter((config) => config.enabled)
    .sort((a, b) => a.order - b.order)
    .map(toPublicFeature);
}

module.exports = {
  getFeatureConfig,
  getEnabledFeatureConfig,
  getPublicFeatureList
};
```

### Public Cloud Function Response

Add operation `getFeatureConfig` to `quickstartFunctions`.

Request:

```javascript
{
  type: "getFeatureConfig",
  data: {
    type: "palm" // optional; omit for list
  }
}
```

List response:

```javascript
{
  success: true,
  data: {
    features: [
      {
        type: "palm",
        enabled: true,
        order: 10,
        title: "看手相",
        shortTitle: "看手相",
        description: "上传清晰手掌照片，生成专属手相解读海报",
        icon: "🖐️",
        uploadIcon: "📷",
        uploadTitle: "上传手掌照片",
        uploadTip: "请确保手掌完整、纹路清晰、光线充足",
        retryText: "重新上传",
        route: "/pages/feature/index?type=palm"
      }
    ]
  }
}
```

Single feature response:

```javascript
{
  success: true,
  data: {
    feature: {
      type: "palm",
      title: "看手相",
      route: "/pages/feature/index?type=palm"
    }
  }
}
```

Never return `validation.prompt`, `generation.prompt`, service URLs, model names, or test URLs to the frontend unless explicitly intended for public display.

---

## Task 1: Add Cloud Feature Config Module

**Files:**
- Create: `cloudfunctions/quickstartFunctions/featureConfig.js`

**Steps:**
1. Create the module using the contract above.
2. Include `palm` and `hair` configs.
3. Export `getEnabledFeatureConfig()` and `getPublicFeatureList()`.
4. Do not include secrets or API keys in this file.
5. Treat validation service URL/model as environment-backed infrastructure config via `process.env.VALIDATION_SERVICE_URL` and `process.env.VALIDATION_MODEL`, with current values only as local fallback.

**Validation:**
- Run a Node syntax check if available:

```bash
node -c cloudfunctions/quickstartFunctions/featureConfig.js
```

Expected: no output and exit code 0.

---

## Task 2: Add `getFeatureConfig` Cloud Function Operation

**Files:**
- Modify: `cloudfunctions/quickstartFunctions/index.js`

**Implementation:**

At top:

```javascript
const {
  getEnabledFeatureConfig,
  getPublicFeatureList
} = require("./featureConfig");
```

Add handler:

```javascript
const getFeatureConfig = async (event) => {
  const requestedType = event.data?.type;

  if (requestedType) {
    const config = getEnabledFeatureConfig(requestedType);
    if (!config) {
      return { success: false, errMsg: "功能暂不可用" };
    }
    return { success: true, data: { feature: { type: config.type, enabled: config.enabled, order: config.order, ...config.public } } };
  }

  return { success: true, data: { features: getPublicFeatureList() } };
};
```

Add switch case:

```javascript
case "getFeatureConfig":
  return await getFeatureConfig(event);
```

**Validation:**
- Confirm no private prompt fields are returned.
- Confirm disabled features do not appear.

---

## Task 3: Use Cloud Config for Image Validation

**Files:**
- Modify: `cloudfunctions/quickstartFunctions/index.js`

**Current code:**

```javascript
const prompt =
  type === "palm"
    ? "这张图片是否包含清晰的手掌照片？请只回答'是'或'否'。"
    : "这张图片是否包含清晰的正面人像照片？请只回答'是'或'否'。";
```

**New approach:**

Change `validateImage(fileID, type)` to `validateImage(fileID, featureConfig)`.

Use:

```javascript
const validationConfig = featureConfig.validation;
const prompt = validationConfig.prompt;
```

Use configurable service URL/model:

```javascript
const res = await axios.post(
  validationConfig.serviceUrl,
  {
    model: validationConfig.model,
    messages: [/* unchanged */],
    max_tokens: 32000
  },
  { headers: { "Content-Type": "application/json" }, timeout: 55000 }
);
```

When validation returns “否”, use `validationConfig.failMessage` before falling back to generic text.

**Validation:**
- `palm` still validates hand images.
- `hair` still validates front-face images.
- No prompt literals remain inside `validateImage()`.

---

## Task 4: Use Cloud Config for Job Creation and Type Validation

**Files:**
- Modify: `cloudfunctions/quickstartFunctions/index.js`

**Current code:**

```javascript
if (!["palm", "hair"].includes(type)) {
  return { success: false, errMsg: "无效的类型参数" };
}
```

**New code:**

```javascript
const featureConfig = getEnabledFeatureConfig(type);
if (!featureConfig) {
  return { success: false, errMsg: "功能暂不可用" };
}
```

Pass config into validation:

```javascript
const validation = await validateImage(fileID, featureConfig);
```

Pass prompt into FastAPI job creation:

```javascript
serverResp = await axios.post(`${SERVER_URL}/api/job`, {
  imageUrl,
  type,
  test: test || false,
  generationPrompt: featureConfig.generation.prompt,
  testPosterFileID: featureConfig.test?.posterFileID
}, {
  headers: {
    "X-Internal-Token": process.env.POSTER_SERVER_TOKEN || ""
  },
  timeout: 10000,
  validateStatus: (status) => status < 500
});
```

**Security note:** This does not expose prompts to the frontend. The prompt travels only cloud function → server.

**Required hardening:** Add `POSTER_SERVER_TOKEN` as a shared secret in both cloud function and FastAPI environments.

- Cloud function sends header `X-Internal-Token`.
- FastAPI checks it before accepting `/api/job`.
- If `POSTER_SERVER_TOKEN` is missing in production, startup should fail or `/api/job` should reject requests.

This is mandatory because the server runs on a public IP and will accept a cloud-supplied `generationPrompt`.

---

## Task 5: Update FastAPI Request Model and Internal Authentication

**Files:**
- Modify: `server/main.py`

**Current model:**

```python
class JobRequest(BaseModel):
    imageUrl: str
    type: str  # "palm" or "hair"
    test: bool = False
```

**New model:**

```python
class JobRequest(BaseModel):
    imageUrl: str
    type: str
    generationPrompt: str
    test: bool = False
    testPosterFileID: str | None = None
```

**Internal authentication:**

At module load:

```python
POSTER_SERVER_TOKEN = os.environ.get("POSTER_SERVER_TOKEN", "")
```

In `/api/job`, require the header before processing the request:

```python
from fastapi import FastAPI, BackgroundTasks, HTTPException, Header

@app.post("/api/job", response_model=JobCreateResponse)
async def create_job(
    job: JobRequest,
    background_tasks: BackgroundTasks,
    x_internal_token: str | None = Header(default=None, alias="X-Internal-Token"),
):
    if not POSTER_SERVER_TOKEN or x_internal_token != POSTER_SERVER_TOKEN:
        raise HTTPException(status_code=403, detail="Forbidden")
```

**Validation:**
- Reject empty prompt and overly long prompts:

```python
prompt = job.generationPrompt.strip()
if not prompt:
    raise HTTPException(status_code=400, detail="缺少生成提示词")
if len(prompt) > 4000:
    raise HTTPException(status_code=400, detail="生成提示词过长")
```

- Keep lightweight type validation, but do not hardcode feature names:

```python
if not re.fullmatch(r"[a-z][a-z0-9_-]{1,31}", job.type):
    raise HTTPException(status_code=400, detail="无效的类型参数")
```

This lets cloud function config define future `makeup` without redeploying server code while preventing arbitrary unauthenticated public prompt execution.

---

## Task 6: Remove Hardcoded Poster Prompts From FastAPI

**Files:**
- Modify: `server/main.py`

Change:

```python
def generate_poster(image_url: str, job_type: str) -> str:
```

To:

```python
def generate_poster(image_url: str, job_type: str, generation_prompt: str) -> str:
```

Remove local `palm_prompt` and `hair_prompt`. Use:

```python
prompt = generation_prompt
```

Change job processor:

```python
async def process_job(
    task_id: str,
    image_url: str,
    job_type: str,
    generation_prompt: str,
    is_test: bool = False,
    test_poster_file_id: str | None = None,
):
```

Use configurable test poster:

```python
if is_test:
    await asyncio.sleep(15)
    poster_url = test_poster_file_id or "cloud://cloud1-d7g1nt83fde793ad3.636c-cloud1-d7g1nt83fde793ad3-1427592986/posters/0274fd6869f6176c00082cfb0eeefd94.png"
```

Start background task with prompt:

```python
background_tasks.add_task(
    process_job,
    task_id,
    job.imageUrl,
    job.type,
    job.generationPrompt,
    job.test,
    job.testPosterFileID,
)
```

**Validation:**
- Search `server/main.py` for old `palm_prompt` and `hair_prompt`; none should remain.
- Existing palm/hair still work because cloud function supplies prompts.

---

## Task 7: Add Mini-Program Config Client

**Files:**
- Create: `miniprogram/utils/featureConfigClient.js`

**Purpose:** Frontend fetches public config from cloud function, with safe fallback for unavailable network/cloud function.

**Implementation:**

```javascript
const FALLBACK_FEATURES = [
  {
    type: "palm",
    title: "看手相",
    shortTitle: "看手相",
    description: "上传清晰手掌照片，生成专属手相解读海报",
    icon: "🖐️",
    uploadIcon: "📷",
    uploadTitle: "上传手掌照片",
    uploadTip: "请确保手掌完整、纹路清晰、光线充足",
    retryText: "重新上传",
    route: "/pages/feature/index?type=palm"
  },
  {
    type: "hair",
    title: "设计发型",
    shortTitle: "设计发型",
    description: "上传正面照片，生成专属发型建议海报",
    icon: "💇",
    uploadIcon: "📷",
    uploadTitle: "上传正面照片",
    uploadTip: "请确保脸部正面清晰、无遮挡、光线充足",
    retryText: "重新上传",
    route: "/pages/feature/index?type=hair"
  }
];

async function fetchFeatureList() {
  try {
    const resp = await wx.cloud.callFunction({
      name: "quickstartFunctions",
      data: { type: "getFeatureConfig", data: {} }
    });
    if (resp.result?.success && Array.isArray(resp.result.data?.features)) {
      return resp.result.data.features;
    }
  } catch (e) {
    // Fallback keeps home page usable when config fetch fails.
  }
  return FALLBACK_FEATURES;
}

async function fetchFeature(type) {
  try {
    const resp = await wx.cloud.callFunction({
      name: "quickstartFunctions",
      data: { type: "getFeatureConfig", data: { type } }
    });
    if (resp.result?.success && resp.result.data?.feature) {
      return resp.result.data.feature;
    }
  } catch (e) {
    // Fallback below.
  }
  return FALLBACK_FEATURES.find((feature) => feature.type === type) || null;
}

module.exports = {
  fetchFeatureList,
  fetchFeature
};
```

**Important:** Fallback contains public UI copy only. It must not contain prompts.

**Maintenance note:** This fallback intentionally duplicates the public section of cloud config. When updating palm/hair public copy in `featureConfig.js`, update `FALLBACK_FEATURES` in the same change or accept that offline/cloud-failure UI may show older copy.

---

## Task 8: Replace Palm/Hair Pages With Generic Feature Page

**Files:**
- Modify: `miniprogram/app.json`
- Modify: `miniprogram/utils/featurePage.js`
- Create: `miniprogram/pages/feature/index.js`
- Create: `miniprogram/pages/feature/index.json`
- Create: `miniprogram/pages/feature/index.wxml`
- Create: `miniprogram/pages/feature/index.wxss`
- Modify: `miniprogram/pages/palm/index.js` if keeping old route compatibility
- Modify: `miniprogram/pages/hair/index.js` if keeping old route compatibility

**app.json:**

```json
{
  "pages": [
    "pages/index/index",
    "pages/feature/index"
  ]
}
```

If you want old routes to keep working during transition:

```json
{
  "pages": [
    "pages/index/index",
    "pages/feature/index",
    "pages/palm/index",
    "pages/hair/index"
  ]
}
```

**Generic page JS:**

`miniprogram/pages/feature/index.js` should combine the shared factory with async cloud config loading:

```javascript
const { createAiPage } = require("../../utils/aiPage");
const { fetchFeature } = require("../../utils/featureConfigClient");

Page({
  ...createAiPage(),

  async onLoad(options) {
    const type = options.type;
    if (!type) {
      this.setData({ configLoading: false, configError: "缺少功能类型" });
      return;
    }

    const feature = await fetchFeature(type);
    if (!feature) {
      this.setData({ configLoading: false, configError: "功能暂不可用" });
      return;
    }

    this.setFeature(feature);
    wx.setNavigationBarTitle({ title: feature.title });
  },
});
```

**Required `featurePage.js` changes:** update `createAiPage()` to support async config and remove the closure-only `type` dependency:

```javascript
function createAiPage() {
  return {
    data: {
      feature: null,
      configLoading: true,
      configError: "",
      posterUrl: "",
      loading: false,
      loadingText: "",
      errorMsg: "",
      testMode: false
    },
    setFeature(feature) {
      this.setData({ feature, configLoading: false, configError: "" });
    },
    getFeatureType() {
      return this.data.feature && this.data.feature.type;
    },
    handleUploadTap() {
      if (this.data.posterUrl || this.data.loading || this.data.configLoading || this.data.configError) return;
      this.chooseImage();
    }
  };
}
```

Then `createJob()` must use the loaded feature type instead of a closure variable:

```javascript
const type = this.getFeatureType();
if (!type) {
  this.setData({ loading: false, errorMsg: "功能配置加载失败，请返回重试" });
  return;
}
```

Keep the existing image selection, compression, upload, polling, save, and cleanup methods. Also change `clearInterval(this.pollTimer)` to `clearTimeout(this.pollTimer)` because polling uses `setTimeout`.

**Generic page WXML:**

```xml
<view class="feature-page">
  <view wx:if="{{configLoading}}" class="status-panel standalone">
    <view class="loading-spinner"></view>
    <text class="status-title">正在加载功能配置</text>
  </view>

  <view wx:elif="{{configError}}" class="error-card standalone">
    <text class="error-text">{{configError}}</text>
  </view>

  <block wx:else>
    <view class="feature-card">
      <view class="feature-icon">{{feature.icon}}</view>
      <view class="feature-copy">
        <text class="feature-title">{{feature.title}}</text>
        <text class="feature-desc">{{feature.description}}</text>
      </view>
    </view>

    <view class="test-toggle">
      <view class="test-copy">
        <text class="test-title">测试模式</text>
        <text class="test-desc">开启后不消耗 API 费用</text>
      </view>
      <switch checked="{{testMode}}" bindchange="toggleTestMode" color="#07c160" />
    </view>

    <view class="upload-card" bindtap="handleUploadTap">
      <image wx:if="{{posterUrl}}" class="poster-image" src="{{posterUrl}}" mode="aspectFill" binderror="onImageError" bindload="onImageLoad" />

      <view wx:elif="{{loading}}" class="status-panel">
        <view class="loading-spinner"></view>
        <text class="status-title">正在生成</text>
        <text class="status-desc">{{loadingText}}</text>
      </view>

      <view wx:else class="upload-placeholder">
        <text class="upload-icon">{{feature.uploadIcon}}</text>
        <text class="upload-title">{{feature.uploadTitle}}</text>
        <text class="upload-tip">{{feature.uploadTip}}</text>
      </view>
    </view>

    <view wx:if="{{errorMsg}}" class="error-card">
      <text class="error-text">{{errorMsg}}</text>
      <button class="secondary-button" bindtap="chooseImage">{{feature.retryText}}</button>
    </view>

    <view wx:if="{{posterUrl}}" class="action-area">
      <button class="primary-button" bindtap="savePoster">保存海报</button>
      <button class="secondary-button" bindtap="sharePoster">分享</button>
    </view>
  </block>
</view>
```

**Old route compatibility:** keep old routes during transition and redirect them to the generic page.

`miniprogram/pages/palm/index.js`:

```javascript
Page({
  onLoad() {
    wx.redirectTo({ url: "/pages/feature/index?type=palm" });
  }
});
```

`miniprogram/pages/hair/index.js`:

```javascript
Page({
  onLoad() {
    wx.redirectTo({ url: "/pages/feature/index?type=hair" });
  }
});
```

**Validation:**
- `/pages/feature/index?type=palm` displays palm public config.
- `/pages/feature/index?type=hair` displays hair public config.
- Invalid type displays friendly error and no upload action.
- `/pages/palm/index` redirects to the generic palm page.
- `/pages/hair/index` redirects to the generic hair page.
- Navigation bar title changes after feature config loads.

---

## Task 9: Refactor Home Page to Fetch Cloud Feature List

**Files:**
- Modify: `miniprogram/pages/index/index.js`
- Modify: `miniprogram/pages/index/index.wxml`
- Modify: `miniprogram/pages/index/index.wxss`

**JS:**

```javascript
const { fetchFeatureList } = require("../../utils/featureConfigClient");

Page({
  data: {
    featureList: [],
    loadingFeatures: true,
    featureError: ""
  },

  async onLoad() {
    try {
      const featureList = await fetchFeatureList();
      this.setData({ featureList, loadingFeatures: false, featureError: "" });
    } catch (e) {
      this.setData({ loadingFeatures: false, featureError: "功能列表加载失败" });
    }
  },

  onClickFeature(e) {
    const { url } = e.currentTarget.dataset;
    if (!url) return;
    wx.navigateTo({ url });
  }
});
```

**WXML:** Render `featureList`, use `item.route` as `data-url`.

**Validation:**
- Home page no longer hardcodes palm/hair.
- Changing order/enabled/title in cloud function config changes home page after cloud function deploy.

---

## Task 10: Shared Minimal UI Styles

**Files:**
- Create: `miniprogram/styles/feature-page.wxss`
- Modify: `miniprogram/pages/feature/index.wxss`
- Modify: `miniprogram/pages/index/index.wxss`

**Direction:** Keep 极简微信风:

- `#f7f7f7` page background.
- White cards with subtle shadow.
- WeChat green `#07c160` for the primary action.
- One upload/result card as page focal point.

`pages/feature/index.wxss` should import:

```css
@import "../../styles/feature-page.wxss";
```

---

## Task 11: Standardize Poster Save Handling on Cloud File IDs

**Files:**
- Modify: `cloudfunctions/quickstartFunctions/index.js`
- Modify: `miniprogram/utils/featurePage.js`

**Why:** Normal generated posters are uploaded by the cloud function and returned to the mini-program as `posterFileID`. The test poster is also now a fixed cloud file ID:

```text
cloud://cloud1-d7g1nt83fde793ad3.636c-cloud1-d7g1nt83fde793ad3-1427592986/posters/0274fd6869f6176c00082cfb0eeefd94.png
```

So the frontend should treat result images as cloud file IDs and should not keep an HTTP test-image branch.

**Cloud function implementation:** when polling the server, if test mode returns the configured `cloud://` file ID, store it directly as `posterFileID` instead of trying to download and re-upload it.

```javascript
if (serverStatus === "completed" && posterUrl) {
  if (posterUrl.startsWith("cloud://")) {
    await db.collection(JOBS_COLLECTION).doc(taskId).update({
      data: {
        status: "completed",
        posterFileID: posterUrl,
        updatedAt: Date.now(),
      },
    });

    return {
      success: true,
      data: {
        status: "completed",
        posterFileID: posterUrl,
      },
    };
  }

  // Existing HTTP/HTTPS branch remains only for real generation API image URLs:
  // download posterUrl, upload to cloud storage, save uploadResult.fileID.
}
```

**Mini-program implementation:** update `doDownloadAndSave()` to use `wx.cloud.downloadFile` for `this.data.posterUrl`.

```javascript
wx.cloud.downloadFile({
  fileID: this.data.posterUrl,
  success: (res) => {
    wx.saveImageToPhotosAlbum({
      filePath: res.tempFilePath,
      success: () => {
        wx.hideLoading();
        wx.showToast({ title: "已保存到相册", icon: "success" });
      },
      fail: () => {
        wx.hideLoading();
        wx.showToast({ title: "保存失败", icon: "none" });
      },
    });
  },
  fail: () => {
    wx.hideLoading();
    wx.showToast({ title: "下载失败", icon: "none" });
  },
});
```

**Validation:**
- Completed generated posters can be saved to album.
- Test-mode cloud poster can be saved to album.
- Permission denial flow still opens settings correctly.

---

## Task 12: Future Makeup Feature Contract

Once this refactor is implemented, adding makeup should require:

1. Add `makeup` entry in `cloudfunctions/quickstartFunctions/featureConfig.js`.
2. Include public copy:
   - title: `设计妆容`
   - upload tip: clear front-face image, no heavy obstruction.
3. Include validation prompt:
   - Ask whether image contains clear front-face portrait suitable for makeup design.
4. Include generation prompt:
   - Ask for Chinese makeup recommendation poster with face/skin tone analysis, style suggestions, product categories, and cautions.
5. Deploy cloud function.
6. Ensure server is already deployed with `generationPrompt` support.

No new frontend page is needed as long as makeup uses the same upload → generate → save/share flow.

---

## Verification Plan

### Cloud Function

- `node -c cloudfunctions/quickstartFunctions/featureConfig.js`
- `node -c cloudfunctions/quickstartFunctions/index.js`
- Manually call cloud function `getFeatureConfig` with no type:
  - Expected: public `features` array.
  - Must not include `validation`, `generation`, `serviceUrl`, `model`, or test private config.
- Manually call `getFeatureConfig` with `{ type: "palm" }`:
  - Expected: public palm config.
- Manually call `validateAndCreateJob` in test mode:
  - Expected: cloud function uses config validation and sends generation prompt to server.

### FastAPI Server

- Run Python syntax check:

```bash
cd server
python -m py_compile main.py
```

- Start server and test health:

```bash
uvicorn main:app --host 0.0.0.0 --port 8011
curl http://127.0.0.1:8011/health
```

- Test `/api/job` rejects empty prompt:

```bash
curl -X POST http://127.0.0.1:8011/api/job \
  -H 'Content-Type: application/json' \
  -d '{"imageUrl":"https://example.com/a.jpg","type":"palm","generationPrompt":""}'
```

Expected: HTTP 400.

### Mini-Program

- Home page loads features from cloud function.
- Feature cards navigate to `/pages/feature/index?type=...`.
- Generic feature page loads feature config by `type`.
- Test mode still works.
- Upload → validate → create job → polling → poster display flow still works.
- Saving a generated cloud poster works via `wx.cloud.downloadFile`.
- Saving the fixed test-mode cloud poster works via `wx.cloud.downloadFile`.
- Invalid `/pages/feature/index?type=unknown` shows friendly unavailable state.

### Static Checks

- Search frontend for private prompt text; none should exist.
- Search server for `palm_prompt` and `hair_prompt`; none should exist.
- Search cloud function public response handler to confirm it never returns `validation`, `generation`, `serviceUrl`, `model`, or `test`.
- `git diff --check` passes.

---

## Deployment Order

Deploy in this order to avoid breaking live traffic:

1. **FastAPI server first** if implemented backward-compatible with old requests, or deploy cloud function and server together during a short maintenance window if `generationPrompt` is required immediately.
2. **Cloud function second** with `featureConfig.js`, `getFeatureConfig`, config-backed validation, and `X-Internal-Token` header.
3. **Mini-program frontend last** after cloud function `getFeatureConfig` is deployed and tested.

Safer rollout option:

- Temporarily let FastAPI use a legacy prompt fallback only when `generationPrompt` is missing and `type` is `palm` or `hair`.
- Remove the legacy fallback after the cloud function has been deployed and verified.

Environment variables required before deployment:

- Cloud function: `POSTER_SERVER_URL`, `POSTER_SERVER_TOKEN`, `VALIDATION_SERVICE_URL`, `VALIDATION_MODEL`.
- FastAPI server: `MEMEFAST_API_KEY`, `MEMEFAST_API_URL`, `POSTER_SERVER_TOKEN`.

---

## Risks and Mitigations

- **Risk:** Frontend depends on cloud config; cloud function failure could make home empty.
  - **Mitigation:** `featureConfigClient.js` keeps public fallback config for palm/hair only.

- **Risk:** A public FastAPI endpoint accepting arbitrary `generationPrompt` can be abused if called directly.
  - **Mitigation:** `X-Internal-Token` is mandatory in this refactor, and the server must reject `/api/job` when the token is missing or wrong.

- **Risk:** Cloud function deployment is still needed for prompt changes.
  - **Mitigation:** This is already much faster than mini-program review. If non-developer prompt editing is needed later, move `FEATURE_CONFIGS` into a cloud database collection with admin-only writes and cache it in memory.

- **Risk:** Fallback frontend config can drift from cloud config.
  - **Mitigation:** Keep fallback minimal and public-only; treat it as emergency UI only and update it whenever public cloud config changes.

- **Risk:** Old shared links to `/pages/palm/index` or `/pages/hair/index` break after generic route migration.
  - **Mitigation:** Keep old pages in `app.json` during transition and redirect them to `/pages/feature/index?type=...`.

- **Risk:** Generic route cannot support radically different UX per feature.
  - **Mitigation:** Keep config fields for minor UI variation. If a future feature requires custom flow, add `renderMode` or a dedicated page then.

---

## Definition of Done

- Feature list and feature page copy are driven by cloud function public config.
- Validation prompts live in cloud function config, not frontend or inline conditional code.
- Poster generation prompts live in cloud function config and are passed to FastAPI when creating jobs.
- FastAPI has no palm/hair-specific prompt branches.
- Home page has no hardcoded feature list except public fallback.
- Generic feature page supports palm/hair and future makeup without duplicating page files.
- No private prompts or service URLs are returned to mini-program frontend.
- Existing palm/hair test-mode and generation flows continue to work.
- Generated cloud-storage posters and the fixed test-mode cloud poster can both be saved to the photo album.
- FastAPI `/api/job` rejects unauthenticated requests and overly long/empty prompts.
- Old palm/hair routes either redirect correctly or are intentionally removed only after confirming no compatibility requirement.

---

## Post-Review Fixes

After Oracle code review, the following operational robustness fixes were applied:

1. **Cloud function startup env validation** (`index.js`): Missing `POSTER_SERVER_TOKEN` now logs `console.error` at module load, matching server's fail-fast principle.
2. **Environment-aware test poster** (`featureConfig.js`): `TEST_POSTER_FILE_ID` is now configurable via `process.env.TEST_POSTER_FILE_ID`, with the original value as fallback. Documented as environment-specific.
3. **Debug logging for config fetch failures** (`featureConfigClient.js`): `console.debug` added to `fetchFeatureList` and `fetchFeature` catch blocks for production debugging.
4. **Cloud file ID environment prefix check** (`index.js`): When server returns `cloud://` poster URL, cloud function logs a warning if the file ID's environment prefix doesn't match `cloud.DYNAMIC_CURRENT_ENV`.
5. **Type naming convention documented** (`main.py`): Added inline comment explaining the `[a-z][a-z0-9_-]{1,31}` regex for feature type validation.
6. **Fallback sync reminder** (`featureConfigClient.js`): Added JSDoc comment above `FALLBACK_FEATURES` warning maintainers to sync with `featureConfig.js` public sections.
