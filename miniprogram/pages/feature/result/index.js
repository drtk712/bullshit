const {
  getTaskDisplayName,
  getTaskStatusText,
  getTaskStatusClass,
} = require("../../../utils/taskDisplay");
const { buildFeatureMap, fetchFeatureList } = require("../../../utils/api/features");
const { fetchTask } = require("../../../utils/api/tasks");
const { resolveDisplayURL, httpUrl, saveImageFile } = require("../../../utils/previewImage");
const { buildTaskSharePayload } = require("../../../utils/share");

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
      const task = await fetchTask(this.data.taskId);
      const posterState = await this.createPosterState(task);
      const resultUrls = await this.createResultUrls(task);
      const originalImageUrl = task.fileID
        ? await resolveDisplayURL(task.fileUrl, task.fileID).catch(() => "")
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
      return { posterPreviewUrl: "", posterError: "图片尚未处理完成" };
    }
    try {
      const posterPreviewUrl = await resolveDisplayURL(task.posterUrl, task.posterFileID);
      return { posterPreviewUrl, posterError: "" };
    } catch (err) {
      return { posterPreviewUrl: "", posterError: "图片加载失败，点击记录重试" };
    }
  },

  async createResultUrls(task) {
    const fileIDs = Array.isArray(task.resultFileIDs) ? task.resultFileIDs.filter(Boolean) : [];
    if (task.status !== "completed" || !fileIDs.length) return [];
    const signed = Array.isArray(task.resultUrls) ? task.resultUrls : [];
    const results = await Promise.all(
      fileIDs.map((fileID, index) => resolveDisplayURL(signed[index], fileID).catch(() => ""))
    );
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
      wx.showToast({ title: "图片未处理完成", icon: "none" });
      return;
    }

    saveImageFile(httpUrl(this.data.task.posterUrl) || posterFileID, { loadingTitle: "保存中" });
  },

  saveResultPiece(e) {
    const index = Number(e.currentTarget.dataset.index || 0);
    const fileID = this.data.task?.resultFileIDs?.[index];
    if (!fileID) {
      wx.showToast({ title: "图片未处理完成", icon: "none" });
      return;
    }
    const signed = this.data.task?.resultUrls?.[index];
    saveImageFile(httpUrl(signed) || fileID, { loadingTitle: "保存中" });
  },

  onShareAppMessage() {
    return buildTaskSharePayload(
      { ...(this.data.task || {}), _id: this.data.taskId },
      { imageUrl: this.data.posterPreviewUrl }
    );
  },
});
