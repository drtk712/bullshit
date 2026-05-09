require("dotenv").config();

const REQUIRED_ENV_VARS = ["POSTER_SERVER_TOKEN"];
for (const varName of REQUIRED_ENV_VARS) {
  if (!process.env[varName]) {
    throw new Error(`[quickstartFunctions] Missing required env: ${varName}`);
  }
}

const { getFeatureConfig } = require("./lib/features");
const { validateAndCreateJob, getTaskStatus, getTasks, getTask, cleanupStaleTasks, deleteTask } = require("./lib/jobs");
const { getTransactions } = require("./lib/points");
const { dailyCheckIn, getShareRewardStatus, shareEarnPoints } = require("./lib/rewards");
const { login, getUserProfile, updateUserProfile } = require("./lib/users");

const handlers = {
  cleanupStaleTasks,
  dailyCheckIn,
  deleteTask,
  getFeatureConfig,
  getTask,
  getTasks,
  getTaskStatus,
  getShareRewardStatus,
  getTransactions,
  getUserProfile,
  login,
  shareEarnPoints,
  updateUserProfile,
  validateAndCreateJob,
};

exports.main = async (event) => {
  if (event.Type === "Timer" || event.TriggerName) {
    if (event.TriggerName === "cleanupStaleTasksTimer") {
      console.log("[Timer] 定时任务触发: 清理超时任务", new Date().toISOString());
      const result = await cleanupStaleTasks(event);
      console.log("[Timer] 定时任务完成: 清理了", result.data?.cleanedCount || 0, "个任务");
      return result;
    }
    return { success: false, errMsg: `未知触发器: ${event.TriggerName}` };
  }

  const handler = handlers[event.type];
  if (!handler) {
    return { success: false, errMsg: `未知的操作类型: ${event.type}` };
  }

  return await handler(event);
};
