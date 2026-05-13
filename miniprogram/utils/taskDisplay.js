const TASK_STATUS_CLASSES = {
  pending: "status-pending",
  processing: "status-processing",
  completed: "status-completed",
};

function getTaskDisplayName(task, featureMap = {}) {
  const type = typeof task === "string" ? task : task?.type;
  const snapshotTitle = typeof task === "object" ? task?.featureTitle : "";
  return snapshotTitle || featureMap[type]?.title || "处理记录";
}

function getTaskDisplayDesc(task, featureMap = {}) {
  const type = typeof task === "string" ? task : task?.type;
  const snapshotHomeDesc = typeof task === "object" ? task?.featureHomeDesc : "";
  const snapshotDescription = typeof task === "object" ? task?.featureDescription : "";
  return snapshotHomeDesc || snapshotDescription || featureMap[type]?.homeDesc || featureMap[type]?.description || "图片处理";
}

function getTaskStatusText(task) {
  const statusMap = {
    pending: "排队中",
    processing: "处理中",
    completed: "已完成",
    failed: task.pointsRefunded ? "失败已退款" : "处理失败",
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
