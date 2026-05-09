const { getTempFileURL, saveImageFile } = require("../../../utils/previewImage");

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
      url: `/pages/ai/index?type=${type}`,
      fail: () => wx.switchTab({ url: "/pages/index/index" }),
    });
  },

  async loadSharedTask(taskId) {
    if (!taskId) {
      this.setData({ loading: false, error: "缺少作品 ID" });
      return;
    }

    this.setData({ loading: true, error: "" });

    try {
      const res = await wx.cloud.callFunction({
        name: "quickstartFunctions",
        data: { type: "getSharedTask", data: { taskId } },
      });

      if (!res.result?.success) {
        this.setData({
          loading: false,
          error: res.result?.errMsg || "作品暂不可查看",
        });
        return;
      }

      const task = res.result.data.task;
      const posterPreviewUrl = await getTempFileURL(task.posterFileID);

      this.setData({
        task: {
          ...task,
          displayName: task.featureTitle || "趣味作品",
          displayDesc: task.featureHomeDesc || task.featureDescription || "来自玩图局的趣味生成",
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

    saveImageFile(posterFileID, { loadingTitle: "保存中" });
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
    const task = this.data.task;
    const path = task?._id
      ? `/pages/share/task/index?id=${task._id}`
      : "/pages/index/index";

    return {
      title: `我在玩图局发现了${task?.displayName || "趣味作品"}`,
      path,
      imageUrl: this.data.posterPreviewUrl || "",
    };
  },
});
