function createAiPage() {
  return {
    data: {
      feature: null,
      configLoading: true,
      configError: "",
      posterUrl: "",
      loading: false,
      loadingText: "",
      errorMsg: "",
      testMode: false,
      skipPointsDeduction: false,
    },

    taskId: null,
    pollTimer: null,

    cleanupTask() {
      if (this.pollTimer) {
        clearTimeout(this.pollTimer);
        this.pollTimer = null;
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
            this.setData({
              loading: false,
              errorMsg: resp.result?.errMsg || "验证失败，请重试",
            });
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
      this.setData({ loadingText: "海报生成中..." });

      let pollCount = 0;
      const maxPollCount = 60;
      const pollInterval = 10000;

      const pollOnce = () => {
        pollCount++;
        if (pollCount > maxPollCount) {
          this.cleanupTask();
          this.setData({
            loading: false,
            errorMsg: "生成超时，请重试",
          });
          return;
        }

        wx.cloud
          .callFunction({
            name: "quickstartFunctions",
            data: {
              type: "getTaskStatus",
              data: { taskId: this.taskId },
            },
          })
          .then((resp) => {
            if (!this.taskId) return;

            if (resp.result && resp.result.success) {
              const { status, posterFileID, errMsg } = resp.result.data;

              if (status === "completed") {
                this.cleanupTask();

                if (posterFileID) {
                  this.setData({
                    loading: false,
                    posterUrl: posterFileID,
                    errorMsg: "",
                  });
                } else {
                  this.setData({
                    loading: false,
                    errorMsg: "海报数据异常",
                  });
                }
              } else if (status === "failed") {
                this.cleanupTask();
                this.setData({
                  loading: false,
                  errorMsg: errMsg || "生成失败，请重试",
                });
              } else {
                this.pollTimer = setTimeout(pollOnce, pollInterval);
              }
            } else {
              this.cleanupTask();
              this.setData({
                loading: false,
                errorMsg: resp.result?.errMsg || "获取状态失败",
              });
            }
          })
          .catch(() => {
            if (!this.taskId) return;

            if (pollCount >= 3) {
              this.cleanupTask();
              this.setData({
                loading: false,
                errorMsg: "网络异常，请重试",
              });
            } else {
              this.pollTimer = setTimeout(pollOnce, pollInterval);
            }
          });
      };

      pollOnce();
    },

    onImageLoad() {},
    onImageError(e) {
      console.error("图片加载失败:", e);
    },

    onShow() {
      if (this.data.loading && this.taskId && !this.pollTimer) {
        this.startPolling();
      }
    },

    onHide() {
      this.cleanupTask();
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
      wx.showToast({ title: "请使用右上角分享", icon: "none" });
    },
  };
}

module.exports = { createAiPage };