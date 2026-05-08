const TASK_STATUS_CLASSES = {
  init: "status-pending",
  pending: "status-pending",
  processing: "status-processing",
  completed: "status-completed",
};

function getTaskDisplayName(type, featureMap = {}) {
  return featureMap[type]?.title || "生成记录";
}

function getTaskDisplayDesc(type, featureMap = {}) {
  return featureMap[type]?.homeDesc || featureMap[type]?.description || "趣味生成";
}

function getTaskStatusText(task) {
  const statusMap = {
    init: "提交中",
    pending: "排队中",
    processing: "生成中",
    completed: "已完成",
    failed: task.pointsRefunded ? "失败已退款" : "生成失败",
  };
  return statusMap[task.status] || task.status;
}

function getTaskStatusClass(status, pointsRefunded) {
  if (status === "failed") return pointsRefunded ? "status-refunded" : "status-failed";
  return TASK_STATUS_CLASSES[status] || "";
}

module.exports = {
  getTaskDisplayName,
  getTaskDisplayDesc,
  getTaskStatusText,
  getTaskStatusClass,
};
