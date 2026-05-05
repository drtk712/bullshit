const TASK_TYPE_NAMES = {
  palm: "看手相",
  hair: "设计发型",
  profile: "个人形象分析",
  doodle: "INS手绘风照片",
  soul: "灵魂画手",
};

const TASK_STATUS_CLASSES = {
  pending: "status-pending",
  processing: "status-processing",
  completed: "status-completed",
};

function getTaskDisplayName(type) {
  return TASK_TYPE_NAMES[type] || "生成记录";
}

function getTaskStatusText(task) {
  const statusMap = {
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
  getTaskStatusText,
  getTaskStatusClass,
};
