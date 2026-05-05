const { createTaskPoller } = require("./taskPoller");

function createAiPage() {
  return {
    data: {
      feature: null,
      configLoading: true,
      configError: "",
      posterUrl: "",
      posterPreviewUrl: "",
      loading: false,
      loadingText: "",
      errorMsg: "",
      testMode: false,
      skipPointsDeduction: false,
    },

    taskId: null,
    taskPoller: null,

    ensureTaskPoller() {
      if (this.taskPoller) return this.taskPoller;

      this.taskPoller = createTaskPoller({
        onStatus: async ({ status, posterFileID, errMsg }) => {
          if (!this.taskId) return;

          if (status === "completed") {
            const completedPosterFileID = posterFileID;
            this.cleanupTask();

            if (completedPosterFileID) {
              await this.showPoster(completedPosterFileID);
            } else {
              this.setData({
                loading: false,
                errorMsg: "海报数据异常",
              });
            }
            return;
          }

          if (status === "failed") {
            this.cleanupTask();
            this.setData({
              loading: false,
              errorMsg: errMsg || "生成失败，请重试",
            });
          }
        },
        onError: (errMsg) => {
          this.cleanupTask();
          this.setData({
            loading: false,
            errorMsg: errMsg || "获取状态失败",
          });
        },
        onTimeout: () => {
          this.cleanupTask();
          this.setData({
            loading: false,
            errorMsg: "生成超时，请重试",
          });
        },
        onTransientError: () => {
          this.setData({ loadingText: "服务端暂时繁忙，正在重试..." });
        },
      });

      return this.taskPoller;
    },

    cleanupTask() {
      if (this.taskPoller) {
        this.taskPoller.reset();
      }
      this.taskId = null;
    },

    setFeature(feature) {
      this.setData({
        feature,
        configLoading: false,
        configError: "",
      });
    },

    getFeatureType() {
      return this.data.feature && this.data.feature.type;
    },

    handleUploadTap() {
      if (
        this.data.posterUrl ||
        this.data.loading ||
        this.data.configLoading ||
        this.data.configError
      ) {
        return;
      }

      this.chooseImage();
    },

    toggleTestMode(e) {
      this.setData({ testMode: e.detail.value });
    },

    toggleSkipPointsDeduction(e) {
      this.setData({ skipPointsDeduction: e.detail.value });
    },

    chooseImage() {
      if (this.data.loading || this.data.configLoading || this.data.configError) return;

      this.cleanupTask();

      wx.chooseMedia({
        count: 1,
        mediaType: ["image"],
        sourceType: ["camera", "album"],
        success: (res) => {
          if (!res.tempFiles || res.tempFiles.length === 0) {
            this.setData({
              loading: false,
              errorMsg: "图片选择失败，请重试",
            });
            return;
          }
          const tempFilePath = res.tempFiles[0].tempFilePath;
          this.compressAndProcess(tempFilePath);
        },
        fail: (err) => {
          if (err.errMsg !== "chooseMedia:fail cancel") {
            this.setData({
              loading: false,
              errorMsg: "选择图片失败，请重试",
            });
          }
        },
      });
    },

    compressAndProcess(tempFilePath) {
      this.setData({
        loading: true,
        loadingText: "正在处理图片...",
        errorMsg: "",
        posterUrl: "",
        posterPreviewUrl: "",
      });

      wx.compressImage({
        src: tempFilePath,
        quality: 70,
        success: (res) => {
          this.uploadAndCall(res.tempFilePath);
        },
        fail: () => {
          this.uploadAndCall(tempFilePath);
        },
      });
    },

    uploadAndCall(filePath) {
      this.setData({ loadingText: "正在上传..." });

      const cloudPath = `ai-upload/${Date.now()}-${Math.random().toString(36).slice(2, 8)}.jpg`;

      wx.cloud.uploadFile({
        cloudPath,
        filePath,
        uploadTask: (uploadTask) => {
          uploadTask.onProgressUpdate((res) => {
            if (res.progress < 100) {
              this.setData({ loadingText: `正在上传 ${res.progress}%...` });
            }
          });
        },
        success: (res) => {
          this.setData({ loadingText: "AI 分析中，请稍候..." });
          this.createJob(res.fileID);
        },
        fail: () => {
          this.setData({
            loading: false,
            errorMsg: "图片上传失败，请重试",
          });
        },
      });
    },

    createJob(fileID) {
      const type = this.getFeatureType();
      if (!type) {
        this.setData({
          loading: false,
          errorMsg: "功能配置加载失败，请返回重试",
        });
        return;
      }

      wx.cloud
        .callFunction({
          name: "quickstartFunctions",
          data: {
            type: "validateAndCreateJob",
            data: {
              type,
              fileID,
              test: this.data.testMode || false,
              skipPointsDeduction: this.data.skipPointsDeduction || false
            },
          },
        })
        .then((resp) => {
          if (resp.result && resp.result.success) {
            this.taskId = resp.result.data.taskId;
            this.startPolling();
           } else {
             const errMsg = resp.result?.errMsg || "验证失败，请重试";
             if (errMsg.includes("积分不足")) {
               this.setData({ loading: false });
               this.showPointsInsufficientModal();
             } else {
               this.setData({
                 loading: false,
                 errorMsg: errMsg,
               });
             }
           }
         })
        .catch((err) => {
          this.setData({
            loading: false,
            errorMsg: err.errMsg || "网络异常，请重试",
          });
        });
    },

    startPolling() {
      if (!this.taskId) return;
      this.setData({ loadingText: "图片生成中，预计需要 50~100 秒\n也可以稍后在「最近生成」中查看" });
      this.ensureTaskPoller().start(this.taskId);
    },

    onImageLoad() {},
    onImageError(e) {
      console.error("图片加载失败:", e);
    },

    async showPoster(posterFileID) {
      try {
        const posterPreviewUrl = await this.getPosterPreviewURL(posterFileID);
        this.setData({
          loading: false,
          posterUrl: posterFileID,
          posterPreviewUrl,
          errorMsg: "",
        });
        wx.showToast({
          title: "生成成功！分享给好友得积分",
          icon: "success",
          duration: 2500,
        });
      } catch (err) {
        this.setData({
          loading: false,
          posterUrl: posterFileID,
          posterPreviewUrl: "",
          errorMsg: "",
        });
      }
    },

    async previewPoster() {
      const posterUrl = this.data.posterUrl;
      if (!posterUrl) return;

      try {
        const tempUrl = this.data.posterPreviewUrl || await this.getPosterPreviewURL(posterUrl);
        wx.previewImage({
          urls: [tempUrl],
          current: tempUrl,
        });
      } catch (err) {
        wx.showToast({ title: "预览失败", icon: "none" });
      }
    },

    async getPosterPreviewURL(fileID) {
      if (!fileID.startsWith("cloud://")) return fileID;

      const result = await wx.cloud.getTempFileURL({ fileList: [fileID] });
      const fileInfo = result.fileList && result.fileList[0];

      if (!fileInfo || fileInfo.status !== 0 || !fileInfo.tempFileURL) {
        throw new Error(fileInfo?.errMsg || "获取图片链接失败");
      }

      return fileInfo.tempFileURL;
    },

    onShow() {
      if (this.data.loading && this.taskId) {
        this.ensureTaskPoller().resume();
      }
    },

    onHide() {
      if (this.taskPoller) {
        this.taskPoller.pause();
      }
    },

    onUnload() {
      this.cleanupTask();
    },

    savePoster() {
      if (!this.data.posterUrl) return;

      wx.getSetting({
        success: (settingRes) => {
          if (settingRes.authSetting["scope.writePhotosAlbum"]) {
            this.doDownloadAndSave();
          } else {
            wx.authorize({
              scope: "scope.writePhotosAlbum",
              success: () => {
                this.doDownloadAndSave();
              },
              fail: () => {
                wx.showModal({
                  title: "需要相册权限",
                  content: "请在设置中开启相册权限以保存图片",
                  confirmText: "去设置",
                  success: (modalRes) => {
                    if (modalRes.confirm) {
                      wx.openSetting({
                        success: (openRes) => {
                          if (openRes.authSetting["scope.writePhotosAlbum"]) {
                            this.doDownloadAndSave();
                          }
                        },
                      });
                    }
                  },
                });
              },
            });
          }
        },
      });
    },

    doDownloadAndSave() {
      wx.showLoading({ title: "保存中..." });
      wx.cloud.downloadFile({
        fileID: this.data.posterUrl,
        success: (res) => {
          wx.saveImageToPhotosAlbum({
            filePath: res.tempFilePath,
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

    sharePoster() {
      wx.showToast({ title: "请点击右上角「...」分享", icon: "none", duration: 2000 });
    },

    async handleShareEarnPoints() {
      try {
        const res = await wx.cloud.callFunction({
          name: "quickstartFunctions",
          data: { type: "shareEarnPoints", data: {} },
        });

        if (res.result && res.result.success) {
          return res.result.data;
        }
        return null;
      } catch (err) {
        console.error("分享奖励获取失败:", err);
        return null;
      }
    },

    onShareAppMessage() {
      // 微信小程序不会触发分享成功回调，用户点击分享按钮即给积分
      this.handleShareEarnPoints().then((data) => {
        if (data) {
          wx.showToast({ title: "分享成功 +1 积分", icon: "success" });
        }
      });
      
      const featureName = this.data.feature?.name || "AI 创意生成";
      return {
        title: `我用「玩图局」生成了${featureName}，快来试试！`,
        path: "/pages/index/index",
        imageUrl: this.data.posterPreviewUrl || "",
      };
    },

    onFeatureImageLoad() {
      this.setData({ "feature._imageLoaded": true });
    },

    onFeatureImageError() {
      this.setData({ "feature._imageError": true });
    },

    previewFeatureImage() {
      if (!this.data.feature?.previewImageUrl) return;

      wx.previewImage({
        urls: [this.data.feature.previewImageUrl],
        current: this.data.feature.previewImageUrl,
      });
    },

    showPointsInsufficientModal() {
      wx.showModal({
        title: "积分不足",
        content: "当前积分不足，分享小程序给好友可获得 1 积分（每日最多 3 次）",
        confirmText: "去分享",
        cancelText: "取消",
        success: (res) => {
          if (res.confirm) {
            wx.showToast({
              title: "请点击右上角「...」分享",
              icon: "none",
              duration: 2500,
            });
          }
        },
      });
    },
  };
}

module.exports = { createAiPage };