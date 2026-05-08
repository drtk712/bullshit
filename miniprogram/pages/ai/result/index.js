const {
  getTaskDisplayName,
  getTaskStatusText,
  getTaskStatusClass,
} = require("../../../utils/taskDisplay");
const { buildFeatureMap, fetchFeatureList } = require("../../../utils/featureConfigClient");
const { getTempFileURL, saveImageFile } = require("../../../utils/previewImage");

Page({
  data: {
    taskId: "",
    task: null,
    posterPreviewUrl: "",
    posterError: "",
    loading: true,
    error: "",
    activeTab: "result",
    originalImageUrl: "",
    featureMap: {},
  },

  onLoad(options) {
    this.setData({ taskId: options.id || "" });
    this.loadTask();
  },

  goBack() {
    wx.navigateBack({
      fail: () => wx.switchTab({ url: "/pages/mine/tasks" }),
    });
  },

  goHome() {
    wx.switchTab({ url: "/pages/index/index" });
  },

  switchTab(e) {
    this.setData({ activeTab: e.currentTarget.dataset.tab });
  },

  async loadTask() {
    if (!this.data.taskId) {
      this.setData({ loading: false, error: "缺少任务 ID" });
      return;
    }

    try {
      if (!Object.keys(this.data.featureMap).length) {
        await this.loadFeatureMap();
      }
      const res = await wx.cloud.callFunction({
        name: "quickstartFunctions",
        data: { type: "getTask", data: { taskId: this.data.taskId } },
      });

      if (!res.result?.success) {
        this.setData({ loading: false, error: res.result?.errMsg || "加载失败" });
        return;
      }

      const task = res.result.data.task;
      const posterState = await this.createPosterState(task);
      const originalImageUrl = task.fileID
        ? await getTempFileURL(task.fileID).catch(() => "")
        : "";
      this.setData({
        task: {
          ...task,
          displayName: getTaskDisplayName(task, this.data.featureMap),
          statusText: getTaskStatusText(task),
          statusClass: getTaskStatusClass(task.status, task.pointsRefunded),
        },
        ...posterState,
        originalImageUrl,
        loading: false,
        error: "",
      });
    } catch (err) {
      this.setData({ loading: false, error: "网络错误，请稍后重试" });
    }
  },

  async loadFeatureMap() {
    try {
      const features = await fetchFeatureList();
      this.setData({ featureMap: buildFeatureMap(features) });
    } catch (e) {
      console.error("加载功能配置失败:", e);
    }
  },

  async createPosterState(task) {
    if (task.status !== "completed" || !task.posterFileID) {
      return { posterPreviewUrl: "", posterError: "图片尚未生成完成" };
    }
    try {
      const posterPreviewUrl = await getTempFileURL(task.posterFileID);
      return { posterPreviewUrl, posterError: "" };
    } catch (err) {
      return { posterPreviewUrl: "", posterError: "图片加载失败，点击记录重试" };
    }
  },

  async viewPoster() {
    const url = this.data.activeTab === "original"
      ? this.data.originalImageUrl
      : this.data.posterPreviewUrl;
    if (!url) return;
    wx.previewImage({ urls: [url], current: url });
  },

  savePoster() {
    const posterFileID = this.data.task?.posterFileID;
    if (!posterFileID) {
      wx.showToast({ title: "图片未生成完成", icon: "none" });
      return;
    }

    saveImageFile(posterFileID, { loadingTitle: "保存中" });
  },

  onShareAppMessage() {
    this.handleShareEarnPoints();
    return {
      title: `我用「玩图局」生成了${this.data.task?.displayName || "趣味图"}，快来试试！`,
      path: "/pages/index/index",
      imageUrl: this.data.posterPreviewUrl || "",
    };
  },

  async handleShareEarnPoints() {
    try {
      const res = await wx.cloud.callFunction({
        name: "quickstartFunctions",
        data: { type: "shareEarnPoints", data: {} },
      });
      if (res.result?.success) {
        wx.showToast({ title: "分享成功 +1 积分", icon: "success" });
      }
    } catch (err) {}
  },
});
