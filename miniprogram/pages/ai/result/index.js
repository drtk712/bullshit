const {
  getTaskDisplayName,
  getTaskStatusText,
  getTaskStatusClass,
} = require("../../../utils/taskDisplay");

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
        ? await this.getFileTempURL(task.fileID).catch(() => "")
        : "";
      this.setData({
        task: {
          ...task,
          displayName: getTaskDisplayName(task.type),
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

  async createPosterState(task) {
    if (task.status !== "completed" || !task.posterFileID) {
      return { posterPreviewUrl: "", posterError: "图片尚未生成完成" };
    }
    try {
      const posterPreviewUrl = await this.getPosterTempFileURL(task.posterFileID);
      return { posterPreviewUrl, posterError: "" };
    } catch (err) {
      return { posterPreviewUrl: "", posterError: "图片加载失败，点击记录重试" };
    }
  },

  async getPosterTempFileURL(fileID) {
    return this.getFileTempURL(fileID);
  },

  async getFileTempURL(fileID) {
    const result = await wx.cloud.getTempFileURL({ fileList: [fileID] });
    const fileInfo = result.fileList && result.fileList[0];
    if (!fileInfo || fileInfo.status !== 0 || !fileInfo.tempFileURL) {
      throw new Error(fileInfo?.errMsg || "获取图片链接失败");
    }
    return fileInfo.tempFileURL;
  },

  async viewPoster() {
    const url = this.data.posterPreviewUrl;
    if (!url) return;
    wx.previewImage({ urls: [url], current: url });
  },

  savePoster() {
    const posterFileID = this.data.task?.posterFileID;
    if (!posterFileID) {
      wx.showToast({ title: "图片未生成完成", icon: "none" });
      return;
    }

    wx.getSetting({
      success: (settingRes) => {
        if (settingRes.authSetting["scope.writePhotosAlbum"]) {
          this.downloadAndSavePoster(posterFileID);
          return;
        }

        wx.authorize({
          scope: "scope.writePhotosAlbum",
          success: () => this.downloadAndSavePoster(posterFileID),
          fail: () => {
            wx.showModal({
              title: "需要相册权限",
              content: "请在设置中开启相册权限以保存图片",
              confirmText: "去设置",
              success: (modalRes) => {
                if (!modalRes.confirm) return;
                wx.openSetting({
                  success: (openRes) => {
                    if (openRes.authSetting["scope.writePhotosAlbum"]) {
                      this.downloadAndSavePoster(posterFileID);
                    }
                  },
                });
              },
            });
          },
        });
      },
    });
  },

  downloadAndSavePoster(posterFileID) {
    wx.showLoading({ title: "保存中" });
    wx.cloud.downloadFile({
      fileID: posterFileID,
      success: (downloadRes) => {
        if (!downloadRes.tempFilePath) {
          wx.hideLoading();
          wx.showToast({ title: "下载失败", icon: "none" });
          return;
        }
        wx.saveImageToPhotosAlbum({
          filePath: downloadRes.tempFilePath,
          success: () => {
            wx.hideLoading();
            wx.showToast({ title: "已保存到相册", icon: "success" });
          },
          fail: () => {
            wx.hideLoading();
            wx.showToast({ title: "保存失败", icon: "none" });
          },
        });
      },
      fail: () => {
        wx.hideLoading();
        wx.showToast({ title: "下载失败", icon: "none" });
      },
    });
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
