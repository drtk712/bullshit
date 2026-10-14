# 旧链路退场清单

本文记录从「云函数 quickstartFunctions + 旧 server」迁移到「CloudRun wantuju-api」后的退场计划。当前先作为执行清单，不直接删除旧代码。

## 当前结论

小程序前端当前主链路已切到 `wx.cloud.callContainer` 调用 `wantuju-api`：

- 玩法配置：`/miniapp/features`
- 用户资料：`/miniapp/me`、`/miniapp/profile`
- 分享/签到：`/miniapp/share-reward/*`
- 积分流水：`/miniapp/transactions`
- 任务创建/轮询/详情/删除：`/miniapp/tasks*`
- 分享详情：`/miniapp/shared-tasks/{task_id}`

旧云函数和旧 server 目前保留为历史备份，不再作为开发版/体验版主链路。

## 可退场对象

### 旧云函数

目录：

```text
cloudfunctions/quickstartFunctions
```

包含的旧职责：

- `getFeatureConfig`
- `validateAndCreateJob`
- `getTaskStatus`
- `getTask`
- `getTasks`
- `getTransactions`
- `dailyCheckIn`
- `shareEarnPoints`
- `getShareRewardStatus`
- `login`
- `getUserProfile`
- `updateUserProfile`
- `cleanupStaleTasks`

CloudRun 替代位置：

```text
cloudrun/wantuju-api/app/api
cloudrun/wantuju-api/app/services
```

退场条件：

- 小程序正式版也已发布 CloudRun 版本。
- CloudRun 日志连续观察 1-2 天无主链路异常。
- 不再需要云函数定时触发器 `cleanupStaleTasksTimer`。
- 云开发控制台中确认没有小程序页面继续调用 `quickstartFunctions`。

退场动作：

1. 暂停云函数触发器。
2. 保留云函数 1 个发布周期作为回滚备份。
3. 删除云函数环境变量 `POSTER_SERVER_URL`、`POSTER_SERVER_TOKEN`、`VALIDATION_SERVICE_URL`、`VALIDATION_MODEL`。
4. 删除或归档 `cloudfunctions/quickstartFunctions` 目录。
5. 删除 `uploadCloudFunction.sh`。

### 旧 FastAPI server

目录：

```text
server
```

包含的旧职责：

- `/api/job`
- `/api/job/{task_id}`
- 旧管理端 `/admin`
- 旧 CloudBase HTTP API 封装
- 旧云存储工具
- 旧图片处理队列

CloudRun 替代位置：

```text
cloudrun/wantuju-api
```

退场条件：

- CloudRun 任务创建、队列处理、失败退款、结果上传稳定。
- CloudRun 管理端已覆盖旧管理端功能。
- 服务器 `36.156.154.98:8011` 不再被任何线上配置引用。
- 没有运维脚本依赖 `server/.env` 或 `POSTER_SERVER_TOKEN`。

退场动作：

1. 停止旧 server 进程。
2. 保留旧 server 代码 1 个发布周期作为回滚备份。
3. 删除服务器上的旧 `.env` 和敏感配置。
4. 删除或归档 `server` 目录。

## 需要先更新的文档

已经过时或属于历史方案：

- `DESIGN.md`
- `docs/plans/2026-05-03-miniapp-frontend-refactor.md`
- `docs/plans/2026-05-03-user-points-tasks-design.md`

当前运维文档以此文件为准：

```text
cloudrun/wantuju-api/README.md
```

## 发布前确认

正式版切换 CloudRun 前，逐项确认：

- `/health` 正常。
- `/debug/routes` 包含核心小程序接口和 `/admin/login`。
- `/miniapp/whoami` 在 callContainer 下返回 `openidResolved: true`，且响应不含请求头。
- 首页玩法列表正常。
- 上传图片创建任务正常。
- 任务完成、失败退款、任务删除正常。
- 每日签到正常。
- 分享奖励正常。
- 积分流水分页正常。
- 管理端只读页正常。
- 管理端玩法保存正常。
- 管理端积分调整、封禁/解封只对测试用户验证通过。

## 暂不删除的原因

旧云函数和旧 server 仍可作为回滚参考。等正式版小程序发布并稳定后，再删除旧链路更稳。
