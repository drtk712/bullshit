# User Login, Points, and Generation Records Design

**Goal:** Add a lightweight user system for the WeChat mini-program: users log in through WeChat cloud `OPENID`, receive 3 points on first login, spend 1 point per real AI generation, get refunded automatically when generation fails, and view login info, points, and generation records from a new bottom-tab **Mine** page.

**Scope for v1:**

- User login/initialization.
- First-login 3-point grant.
- Real generation consumes 1 point at task creation time.
- Failed generation refunds 1 point automatically.
- Test mode never consumes points.
- Frontend-only per-request `skipPointsDeduction` switch for development testing.
- Mine page shows user identity, current points, recent point transactions, and recent generation records.
- "Tasks" means generation records, not tasks-to-earn-points.
- Reserve point-adjustment interfaces for future earning/recharge/admin flows, but do not implement task earning UI in v1.

---

## Product Rules

### Login

The mini-program does not need a separate account/password system.

- Cloud function uses `cloud.getWXContext().OPENID` as the stable user identity.
- On first login, create a user document and grant 3 points.
- On later login, update `lastLoginAt` and return current profile.

### Points

- Initial grant: `+3` points on first login.
- Real AI generation: `-1` point when a task is created.
- Test mode: `0` points.
- Development skip switch: `0` points for that request, while still using the real generation flow.
- If generation fails after consuming points: refund `+1` point once.
- If points are insufficient: do not create the AI generation task.

### Generation Records

A generation record is the existing `ai_poster_jobs` task enriched with user and points fields.

Statuses:

- `pending`: task accepted, waiting for server result.
- `completed`: poster generated and cloud file ID stored.
- `failed`: generation failed.
- `refunded`: represented through `pointsRefunded: true` on failed tasks, not necessarily a separate task status.

---

## Navigation and Page Design

### Bottom Navigation

Use native mini-program `tabBar` with two tabs:

```text
首页  |  我的
```

`app.json` should add `pages/mine/index` and configure:

```json
"tabBar": {
  "color": "#888888",
  "selectedColor": "#07c160",
  "backgroundColor": "#ffffff",
  "borderStyle": "white",
  "list": [
    {
      "pagePath": "pages/index/index",
      "text": "首页",
      "iconPath": "images/tab-home.png",
      "selectedIconPath": "images/tab-home-active.png"
    },
    {
      "pagePath": "pages/mine/index",
      "text": "我的",
      "iconPath": "images/tab-mine.png",
      "selectedIconPath": "images/tab-mine-active.png"
    }
  ]
}
```

If icon assets are not ready, create simple local PNG icons first; tabBar icons must be local files.

### Home Page

Home remains the feature discovery page.

- It fetches public feature list from `getFeatureConfig`.
- Feature cards still use `wx.navigateTo` to `/pages/ai/index?type=...` because `pages/ai/index` is not a tabBar page.
- Add bottom padding so content does not collide with tabBar.
- Optionally show a small points hint after login, but the authoritative points view lives in Mine.

### AI Feature Page

Add a second development-only switch below test mode:

```text
测试模式
开启后不消耗 API 费用

不扣积分
仅开发测试使用，本次真实生成不消耗积分
```

Semantics:

- `testMode=true`: test generation, no AI API, no points.
- `skipPointsDeduction=true`: real generation, AI API called, no points consumed.
- `skipPointsDeduction` affects only the current request.
- Cloud function trusts this request field as requested for development convenience.
- Remove or hide this switch before production if needed.

### Mine Page

Use the same minimal WeChat style as current pages: `#f7f7f7` background, white cards, subtle shadows, WeChat green `#07c160` accents.

Suggested layout:

1. **User card**
   - Display name: `微信用户`.
   - ID: masked `openid`, for example `ID: ******9a3f`.
   - Copy: `首次登录赠送 3 积分`.
   - v1 does not require avatar/nickname authorization.

2. **Points card**
   - Large current balance.
   - Copy: `每次生成消耗 1 积分`.
   - Recent point transactions list or `积分明细 >` placeholder.

3. **Generation records card**
   - Recent tasks from `ai_poster_jobs`.
   - Show feature title/type, status, creation time, and points action.
   - Completed task can navigate to the result page or preview poster in a later iteration.

Example visual structure:

```text
[微信用户]
ID: ******9a3f
首次登录赠送 3 积分

[当前积分]
3
每次生成消耗 1 积分

[最近生成]
看手相      生成中      -1
设计发型    已完成      -1
看手相      失败已退款  +1
```

---

## Cloud Database Design

### `users`

```js
{
  _id,
  openid,
  points: 3,
  totalGrantedPoints: 3,
  totalUsedPoints: 0,
  totalRefundedPoints: 0,
  createdAt,
  updatedAt,
  lastLoginAt
}
```

Indexes:

- Unique or lookup index on `openid`.

### `point_transactions`

```js
{
  _id,
  openid,
  type: "grant" | "consume" | "refund" | "adjust",
  amount: 3,
  balanceAfter: 3,
  reason: "first_login" | "create_ai_job" | "job_failed_refund" | "manual_adjust",
  taskId: null,
  createdAt
}
```

Rules:

- Positive `amount` for grants/refunds/adjust-up.
- Negative `amount` for consume/adjust-down.
- Always store `balanceAfter` for auditability.

### Extend `ai_poster_jobs`

Add fields:

```js
{
  openid,
  type,
  fileID,
  serverTaskId,
  status,
  posterFileID,
  errMsg,
  pointsCost: 1,
  pointsConsumed: true,
  pointsRefunded: false,
  skipPointsDeduction: false,
  consumeTransactionId,
  refundTransactionId,
  createdAt,
  updatedAt
}
```

Test mode or skip-points task:

```js
{
  pointsCost: 0,
  pointsConsumed: false,
  pointsRefunded: false,
  skipPointsDeduction: true
}
```

---

## Cloud Function API Design

Add operations to `quickstartFunctions`.

### `login`

Request:

```js
{
  type: "login",
  data: {}
}
```

Behavior:

1. Get `OPENID` from `cloud.getWXContext()`.
2. Ensure `users` and `point_transactions` collections exist.
3. If no user exists:
   - Create `users` with `points=3`.
   - Create `point_transactions` grant record with `reason="first_login"`.
   - Return `isNewUser=true`.
4. If user exists:
   - Update `lastLoginAt`.
   - Return `isNewUser=false`.

Response:

```js
{
  success: true,
  data: {
    user: {
      openidMasked: "******9a3f",
      points: 3,
      isNewUser: true,
      createdAt,
      lastLoginAt
    }
  }
}
```

### `getUserProfile`

Request:

```js
{
  type: "getUserProfile",
  data: {
    transactionLimit: 5,
    taskLimit: 10
  }
}
```

Response:

```js
{
  success: true,
  data: {
    user: {
      openidMasked,
      points,
      createdAt,
      lastLoginAt
    },
    recentTransactions: [],
    recentTasks: []
  }
}
```

Implementation can call the same ensure-user helper as `login`, so Mine page works even if user opens it first.

### `adjustUserPoints` (reserved)

Reserved for future admin/activity flows.

Request:

```js
{
  type: "adjustUserPoints",
  data: {
    openid,
    amount: 10,
    reason: "manual_adjust"
  }
}
```

Do not expose this from frontend in v1. It must later require admin authorization.

---

## Points Flow in `validateAndCreateJob`

Existing generation flow should be extended after image validation succeeds and before FastAPI job creation.

Pseudo-flow:

```js
const { type, fileID, test, skipPointsDeduction } = event.data;
const shouldConsumePoints = !test && !skipPointsDeduction;

const user = await ensureUser(openid);

if (shouldConsumePoints) {
  if (user.points < 1) {
    await cloud.deleteFile({ fileList: [fileID] }).catch(() => {});
    return { success: false, errMsg: "积分不足，请先获取积分" };
  }

  const consumeResult = await consumePoint({
    openid,
    amount: 1,
    reason: "create_ai_job"
  });
}

// Create server job and then ai_poster_jobs document with points metadata.
```

Important: use database transactions if the cloud database SDK/environment supports them. If transactions are unavailable, order operations carefully and make refund idempotent.

---

## Refund Flow in `getTaskStatus`

When server status is `failed`:

```js
if (task.pointsConsumed && !task.pointsRefunded) {
  const refundTransaction = await refundPoint({
    openid: task.openid,
    amount: 1,
    reason: "job_failed_refund",
    taskId
  });

  await db.collection(JOBS_COLLECTION).doc(taskId).update({
    data: {
      status: "failed",
      errMsg,
      pointsRefunded: true,
      refundTransactionId: refundTransaction._id,
      updatedAt: Date.now()
    }
  });
}
```

Refund must be idempotent: repeated polling must not refund twice.

---

## Frontend Data Flow

### App/Home

- On app start or home `onLoad`, call `login`.
- Store user summary in page data or app global state.
- Home does not need to block feature browsing on login, but AI generation will require user creation in cloud function anyway.

### Mine

- On `onShow`, call `getUserProfile` so points/tasks refresh after returning from generation.
- Show loading skeleton/card while fetching.
- Show fallback empty states:
  - `暂无积分记录`
  - `暂无生成记录`

### AI Page

Add data:

```js
skipPointsDeduction: false
```

Add method:

```js
toggleSkipPointsDeduction(e) {
  this.setData({ skipPointsDeduction: e.detail.value });
}
```

Send to cloud function:

```js
data: {
  type,
  fileID,
  test: this.data.testMode || false,
  skipPointsDeduction: this.data.skipPointsDeduction || false
}
```

---

## Error Handling

- Missing/invalid user: cloud function should create user automatically from `OPENID`.
- Insufficient points: return `success:false`, `errMsg:"积分不足，请先获取积分"`.
- Task creation fails after points were consumed: refund immediately if possible; otherwise mark task or transaction for later reconciliation.
- Server generation fails: refund during `getTaskStatus` failure handling.
- Mine profile fetch fails: show `资料加载失败，请下拉刷新` or retry button.

---

## Verification Plan

### Cloud Function

- `login` first call creates user and grants 3 points.
- `login` second call does not grant again.
- `validateAndCreateJob` with `test=true` does not consume points.
- `validateAndCreateJob` with `skipPointsDeduction=true` does not consume points.
- Real generation consumes 1 point at task creation.
- Insufficient points prevents task creation.
- Failed generation refunds exactly once.
- `getUserProfile` returns user, recent transactions, recent tasks.

### Mini-Program

- Bottom tabBar shows 首页 / 我的.
- 首页 feature cards still navigate to `/pages/ai/index?type=...`.
- 我的 page displays masked user ID and current points.
- 我的 page refreshes on `onShow` after generation.
- AI page shows `测试模式` and `不扣积分` switches.
- Successful real generation updates Mine points and records.
- Failed generation shows refunded state in Mine.

### Static Checks

- No user point changes happen only in frontend; authoritative mutation remains cloud function side.
- `adjustUserPoints` is not reachable from public UI in v1.
- `skipPointsDeduction` is clearly marked development-only in UI copy.
- No secrets or raw full openid are displayed in frontend.

---

## Implementation Order

1. Add database helpers in cloud function:
   - `ensureUserCollections`
   - `ensureUser`
   - `createPointTransaction`
   - `consumePoints`
   - `refundPoints`
2. Add `login` and `getUserProfile` operations.
3. Extend `validateAndCreateJob` with points consumption and skip switch.
4. Extend `getTaskStatus` with refund logic.
5. Add `pages/mine/index.*`.
6. Add `tabBar` and tab icons.
7. Add `skipPointsDeduction` switch to AI page.
8. Update README and run verification.

---

## Open Production Note

The frontend-only `skipPointsDeduction` switch is intentionally accepted for development convenience. Before production release, either remove/hide the switch or ensure the release build cannot expose it to normal users.
