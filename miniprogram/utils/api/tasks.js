const { callCloudRun } = require("../cloudrunClient");
const { buildQuery, createBusinessError, getApiErrorMessage } = require("./errors");

async function fetchTasks({ page = 1, pageSize = 5, filter = "all" } = {}) {
  const resp = await callCloudRun({
    path: `/miniapp/tasks${buildQuery({ page, pageSize, filter })}`,
    method: "GET",
  });

  if (resp.data?.success) {
    return resp.data.data;
  }

  throw createBusinessError(getApiErrorMessage(resp, "获取生成记录失败"));
}

async function fetchTask(taskId) {
  const resp = await callCloudRun({
    path: `/miniapp/tasks/${encodeURIComponent(taskId)}`,
    method: "GET",
  });

  if (resp.data?.success && resp.data?.data?.task) {
    return resp.data.data.task;
  }

  throw createBusinessError(getApiErrorMessage(resp, "任务不存在"));
}

async function fetchTaskStatus(taskId) {
  const resp = await callCloudRun({
    path: `/miniapp/tasks/${encodeURIComponent(taskId)}/status`,
    method: "GET",
  });

  if (resp.data?.success) {
    return resp.data.data;
  }

  throw createBusinessError(getApiErrorMessage(resp, "获取状态失败"));
}

async function fetchSharedTask(taskId) {
  const resp = await callCloudRun({
    path: `/miniapp/shared-tasks/${encodeURIComponent(taskId)}`,
    method: "GET",
  });

  if (resp.data?.success && resp.data?.data?.task) {
    return resp.data.data.task;
  }

  throw createBusinessError(getApiErrorMessage(resp, "图片暂不可查看"));
}

async function deleteTask(taskId) {
  const resp = await callCloudRun({
    path: `/miniapp/tasks/${encodeURIComponent(taskId)}`,
    method: "DELETE",
  });

  if (resp.data?.success) {
    return resp.data.data;
  }

  throw createBusinessError(getApiErrorMessage(resp, "删除任务失败"));
}

async function createTask({ type, fileID, fileIDs = [], param = {} }) {
  const resp = await callCloudRun({
    path: "/miniapp/tasks",
    method: "POST",
    data: {
      type,
      fileID,
      fileIDs,
      param,
    },
  });

  if (resp.data?.success && resp.data?.data?.taskId) {
    return resp.data.data;
  }

  throw createBusinessError(getApiErrorMessage(resp, "处理失败"));
}

module.exports = {
  createTask,
  deleteTask,
  fetchTasks,
  fetchTask,
  fetchTaskStatus,
  fetchSharedTask,
};
