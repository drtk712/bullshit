const { createTaskPoller } = require("../../../utils/taskPoller");

Page({
  data: {
    taskId: "",
    type: "",
    progress: 65,
    remainText: "20 秒",
    progressTitle: "",
    progressChecks: [],
  },

  poller: null,
  progressTimer: null,

  onLoad(options) {
    const type = options.type || "palm";
    const ui = this.getFeatureUI(type);

    this.setData({
      taskId: options.id || "",
      type,
      progressTitle: ui.progressTitle || "生成中",
      progressChecks: ui.progressChecks || [],
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
      const next = Math.min(this.data.progress + 7, 92);
      this.setData({
        progress: next,
        remainText: next > 80 ? "约 20 秒" : "约 50 秒",
      });
    }, 2200);
  },

  startPolling() {
    if (!this.data.taskId) return;

    this.poller = createTaskPoller({
      initialDelay: 2500,
      onStatus: (status) => {
        if (status.status === "completed") {
          this.cleanup();
          wx.redirectTo({ url: `/pages/ai/result/index?id=${this.data.taskId}` });
        } else if (status.status === "failed") {
          this.cleanup();
          wx.redirectTo({ url: `/pages/mine/task-detail?id=${this.data.taskId}` });
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
