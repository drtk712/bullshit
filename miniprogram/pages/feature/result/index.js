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
    resultUrls: [],
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
      const resultUrls = await this.createResultUrls(task);
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
        resultUrls,
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

  async createResultUrls(task) {
    const fileIDs = Array.isArray(task.resultFileIDs) ? task.resultFileIDs.filter(Boolean) : [];
    if (task.status !== "completed" || !fileIDs.length) return [];
    const results = await Promise.all(fileIDs.map((fileID) => getTempFileURL(fileID).catch(() => "")));
    return results.filter(Boolean);
  },

  async viewPoster() {
    const url = this.data.activeTab === "original"
      ? this.data.originalImageUrl
      : this.data.posterPreviewUrl;
    if (!url) return;
    wx.previewImage({ urls: [url], current: url });
  },

  viewResultPiece(e) {
    const current = e.currentTarget.dataset.url;
    if (!current) return;
    wx.previewImage({ urls: this.data.resultUrls, current });
  },

  savePoster() {
    const posterFileID = this.data.task?.posterFileID;
    if (!posterFileID) {
      wx.showToast({ title: "图片未生成完成", icon: "none" });
      return;
    }

    saveImageFile(posterFileID, { loadingTitle: "保存中" });
  },

  saveResultPiece(e) {
    const index = Number(e.currentTarget.dataset.index || 0);
    const fileID = this.data.task?.resultFileIDs?.[index];
    if (!fileID) {
      wx.showToast({ title: "图片未生成完成", icon: "none" });
      return;
    }
    saveImageFile(fileID, { loadingTitle: "保存中" });
  },

  onShareAppMessage() {
    const task = this.data.task || {};
    const path = task.status === "completed" && this.data.taskId
      ? `/pages/share/task/index?id=${this.data.taskId}`
      : "/pages/index/index";

    return {
      title: `我用「玩图局」生成了${this.data.task?.displayName || "趣味图"}，快来试试！`,
      path,
      imageUrl: this.data.posterPreviewUrl || "",
    };
  },
});
