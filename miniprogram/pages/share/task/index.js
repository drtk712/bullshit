const { fetchSharedTask } = require("../../../utils/api/tasks");
const { resolveDisplayURL, httpUrl, saveImageFile } = require("../../../utils/previewImage");
const { buildTaskSharePayload } = require("../../../utils/share");

Page({
  data: {
    taskId: "",
    task: null,
    posterPreviewUrl: "",
    loading: true,
    error: "",
  },

  onLoad(options = {}) {
    const taskId = options.id || "";
    this.setData({ taskId });
    this.loadSharedTask(taskId);
  },

  goBack() {
    wx.navigateBack({
      fail: () => wx.switchTab({ url: "/pages/index/index" }),
    });
  },

  goHome() {
    wx.switchTab({ url: "/pages/index/index" });
  },

  goTryFeature() {
    const type = this.data.task?.type;
    if (!type) {
      this.goHome();
      return;
    }

    wx.navigateTo({
      url: `/pages/feature/index?type=${type}`,
      fail: () => wx.switchTab({ url: "/pages/index/index" }),
    });
  },

  async loadSharedTask(taskId) {
    if (!taskId) {
      this.setData({ loading: false, error: "缺少图片 ID" });
      return;
    }

    this.setData({ loading: true, error: "" });

    try {
      const task = await fetchSharedTask(taskId);
      const posterPreviewUrl = await resolveDisplayURL(task.posterUrl, task.posterFileID);

      this.setData({
        task: {
          ...task,
          displayName: task.featureTitle || "图片处理",
          displayDesc: task.featureHomeDesc || task.featureDescription || "来自玩图局的图片处理结果",
          timeText: this.formatTime(task.createdAt),
        },
        posterPreviewUrl,
        loading: false,
        error: "",
      });
    } catch (err) {
      this.setData({ loading: false, error: err.message || "加载失败，请稍后重试" });
    }
  },

  viewPoster() {
    const url = this.data.posterPreviewUrl;
    if (!url) return;
    wx.previewImage({ urls: [url], current: url });
  },

  savePoster() {
    const posterFileID = this.data.task?.posterFileID;
    if (!posterFileID) {
      wx.showToast({ title: "图片加载中", icon: "none" });
      return;
    }

    saveImageFile(httpUrl(this.data.task.posterUrl) || posterFileID, { loadingTitle: "保存中" });
  },

  retryLoad() {
    this.loadSharedTask(this.data.taskId);
  },

  formatTime(timestamp) {
    if (!timestamp) return "";
    const date = new Date(timestamp);
    const month = String(date.getMonth() + 1).padStart(2, "0");
    const day = String(date.getDate()).padStart(2, "0");
    const hours = String(date.getHours()).padStart(2, "0");
    const minutes = String(date.getMinutes()).padStart(2, "0");
    return `${month}-${day} ${hours}:${minutes}`;
  },

  onShareAppMessage() {
    return buildTaskSharePayload(this.data.task || {}, {
      imageUrl: this.data.posterPreviewUrl,
    });
  },
});
