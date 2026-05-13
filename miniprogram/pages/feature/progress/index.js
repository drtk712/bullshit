const { createTaskPoller } = require("../../../utils/taskPoller");

const PROGRESS_STAGES = {
  pending: { max: 28, title: "正在排队处理" },
  processing: { max: 92 },
};
const INITIAL_PROGRESS = 8;
const PROCESSING_START_PROGRESS = 28;
const PROCESSING_END_PROGRESS = 92;
const PROGRESS_INTERVAL = 1500;
const PROGRESS_INCREMENTS = [
  { below: PROCESSING_END_PROGRESS, value: 2 },
];

Page({
  data: {
    taskId: "",
    type: "",
    progress: INITIAL_PROGRESS,
    remainText: "约 60 秒",
    progressTitle: "",
    progressChecks: [],
  },

  poller: null,
  progressTimer: null,
  progressStage: PROGRESS_STAGES.pending,
  configuredProgressTitle: "",

  goBack() {
    wx.showModal({
      title: "确认离开？",
      content: "图片会继续处理。离开后可在「处理记录」查看进度和结果。",
      cancelText: "继续等待",
      confirmText: "离开",
      success: (res) => {
        if (!res.confirm) return;
        wx.navigateBack({
          fail: () => wx.switchTab({ url: "/pages/mine/tasks" }),
        });
      },
    });
  },

  onLoad(options) {
    const type = options.type || "palm";
    const ui = this.getFeatureUI(type);
    const configuredProgressTitle = ui.progressTitle || "正在处理图片";
    this.configuredProgressTitle = configuredProgressTitle;

    this.setData({
      taskId: options.id || "",
      type,
      progress: INITIAL_PROGRESS,
      progressTitle: PROGRESS_STAGES.pending.title,
      progressChecks: this.buildProgressChecks(ui.progressChecks || []),
    });
    this.startFakeProgress();
    this.startPolling();
  },

  getFeatureUI(type) {
    const list = getApp().globalData.featureList;
    if (!Array.isArray(list)) return {};
    const feature = list.find((f) => f.type === type);
    return feature?.ui || {};
  },

  startFakeProgress() {
    this.progressTimer = setInterval(() => {
      const stage = this.progressStage || PROGRESS_STAGES.pending;
      const current = Number(this.data.progress || INITIAL_PROGRESS);
      const step = PROGRESS_INCREMENTS.find((item) => current < item.below)?.value || 1;
      const next = Math.min(current + step, stage.max);
      this.updateProgress(next);
    }, PROGRESS_INTERVAL);
  },

  buildProgressChecks(checks) {
    return (checks || []).map((item, index) => ({
      title: item.title || `处理步骤 ${index + 1}`,
      done: false,
      displayStatus: "等待中",
    }));
  },

  progressCheckDoneCount(progress) {
    if (progress < PROCESSING_START_PROGRESS) return 0;
    const total = this.data.progressChecks.length;
    if (!total) return 0;
    const ratio = (progress - PROCESSING_START_PROGRESS) / (PROCESSING_END_PROGRESS - PROCESSING_START_PROGRESS);
    return Math.min(total, Math.floor(ratio * total));
  },

  updateProgress(progress) {
    const doneCount = this.progressCheckDoneCount(progress);
    const progressChecks = this.data.progressChecks.map((item, index) => {
      if (index < doneCount) {
        return { ...item, done: true, displayStatus: "完成" };
      }
      if (index === doneCount && progress >= PROCESSING_START_PROGRESS) {
        return { ...item, done: false, displayStatus: "进行中" };
      }
      return { ...item, done: false, displayStatus: "等待中" };
    });

    this.setData({
      progress,
      progressChecks,
      remainText: progress > 80 ? "约 20 秒" : progress > 45 ? "约 40 秒" : "约 60 秒",
    });
  },

  syncProgressByStatus(status) {
    const stage = PROGRESS_STAGES[status];
    if (!stage) return;

    this.progressStage = {
      ...stage,
      title: status === "processing"
        ? this.configuredProgressTitle
        : stage.title,
    };

    this.setData({
      progressTitle: this.progressStage.title,
    });
    this.updateProgress(status === "processing"
      ? Math.max(this.data.progress, PROCESSING_START_PROGRESS)
      : this.data.progress);
  },

  startPolling() {
    if (!this.data.taskId) return;

    this.poller = createTaskPoller({
      onStatus: (status) => {
        if (status.status === "completed") {
          this.setData({ progress: 100, remainText: "即将完成" });
          this.cleanup();
          wx.redirectTo({ url: `/pages/feature/result/index?id=${this.data.taskId}` });
        } else if (status.status === "failed") {
          this.cleanup();
          wx.redirectTo({ url: `/pages/mine/task-detail?id=${this.data.taskId}` });
        } else {
          this.syncProgressByStatus(status.status);
        }
      },
      onError: () => {
        wx.redirectTo({ url: `/pages/mine/task-detail?id=${this.data.taskId}` });
      },
      onTimeout: () => {
        wx.switchTab({ url: "/pages/mine/tasks" });
      },
    });
    this.poller.start(this.data.taskId);
  },

  cleanup() {
    if (this.progressTimer) {
      clearInterval(this.progressTimer);
      this.progressTimer = null;
    }
    if (this.poller) {
      this.poller.reset();
    }
  },

  onHide() {
    if (this.poller) this.poller.pause();
  },

  onShow() {
    if (this.poller) this.poller.resume();
  },

  onUnload() {
    this.cleanup();
  },
});
