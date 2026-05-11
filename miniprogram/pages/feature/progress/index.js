const { createTaskPoller } = require("../../../utils/taskPoller");

const PROGRESS_STAGES = {
  init: { min: 8, max: 20, title: "正在提交图片" },
  pending: { min: 20, max: 45, title: "正在排队处理" },
  processing: { min: 45, max: 92 },
};
const PROCESSING_START_PROGRESS = 45;
const CHECK_PROGRESS_STEP = 10;

Page({
  data: {
    taskId: "",
    type: "",
    progress: 8,
    remainText: "约 60 秒",
    progressTitle: "",
    progressChecks: [],
  },

  poller: null,
  progressTimer: null,
  progressStage: PROGRESS_STAGES.init,
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
      progress: PROGRESS_STAGES.init.min,
      progressTitle: PROGRESS_STAGES.init.title,
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
      const stage = this.progressStage || PROGRESS_STAGES.init;
      const step = stage.max <= 20 ? 2 : stage.max <= 45 ? 3 : 4;
      const next = Math.min(this.data.progress + step, stage.max);
      this.updateProgress(next);
    }, 2200);
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
    return Math.min(
      this.data.progressChecks.length,
      Math.floor((progress - PROCESSING_START_PROGRESS) / CHECK_PROGRESS_STEP)
    );
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
    this.updateProgress(Math.max(this.data.progress, this.progressStage.min));
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
