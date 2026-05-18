const { createTaskPoller } = require("../../../utils/taskPoller");

const PROGRESS_STAGES = {
  pending: { max: 28, title: "正在排队处理" },
  processing: { max: 92 },
};
const INITIAL_PROGRESS = 8;
const PROCESSING_START_PROGRESS = 28;
const PROCESSING_END_PROGRESS = 92;
const PROGRESS_INTERVAL = 1800;
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
    const configuredProgressTitle = ui.progressTitle || "正在校验并处理图片";
    this.configuredProgressTitle = configuredProgressTitle;

    this.setData({
      taskId: options.id || "",
      type,
      progress: INITIAL_PROGRESS,
      progressTitle: PROGRESS_STAGES.pending.title,
      progressChecks: this.buildProgressChecks(ui),
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

  buildProgressChecks(ui = {}) {
    const validationChecks = this.normalizeRequirementItems(ui.requirementItems)
      .map((item) => ({ title: `检查：${item.text}` }));
    const processChecks = Array.isArray(ui.progressChecks) ? ui.progressChecks : [];
    const configuredChecks = [...validationChecks, ...processChecks];
    const checks = configuredChecks.length
      ? [{ title: "检查图片安全性" }, ...configuredChecks]
      : [{ title: "检查图片安全性" }, { title: "分析图片内容" }, { title: "处理图片效果" }, { title: "保存处理结果" }];

    return checks.map((item, index) => ({
      title: item.title || `处理步骤 ${index + 1}`,
      done: false,
      displayStatus: "等待中",
    }));
  },

  normalizeRequirementItems(items) {
    if (!Array.isArray(items)) return [];
    return items
      .map((item) => {
        if (typeof item === "string") return { text: item.trim() };
        return { text: String(item?.text || item?.title || "").trim() };
      })
      .filter((item) => item.text);
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
