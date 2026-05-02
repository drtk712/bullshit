function createAiPage(type) {
  return {
    data: {
      posterUrl: "",
      loading: false,
      loadingText: "",
      errorMsg: "",
      testMode: false,
    },

    taskId: null,
    pollTimer: null,

    cleanupTask() {
      if (this.pollTimer) {
        clearInterval(this.pollTimer);
        this.pollTimer = null;
      }
      this.taskId = null;
    },

    toggleTestMode(e) {
      this.setData({ testMode: e.detail.value });
    },

    chooseImage() {
      if (this.data.loading) return;
      
      this.cleanupTask();
      
      wx.chooseMedia({
        count: 1,
        mediaType: ["image"],
        sourceType: ["camera", "album"],
        success: (res) => {
          if (!res.tempFiles || res.tempFiles.length === 0) {
            this.setData({
              loading: false,
              errorMsg: "图片选择失败，请重试"
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
              errorMsg: "选择图片失败，请重试"
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
        cloudPath: cloudPath,
        filePath: filePath,
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
        fail: (err) => {
          this.setData({
            loading: false,
            errorMsg: "图片上传失败，请重试",
          });
        },
      });
    },

    createJob(fileID) {
      wx.cloud
        .callFunction({
          name: "quickstartFunctions",
          data: {
            type: "validateAndCreateJob",
            data: { type, fileID, test: this.data.testMode || false },
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
      const MAX_POLL_COUNT = 60;
      const POLL_INTERVAL = 10000;

      const pollOnce = () => {
        pollCount++;
        if (pollCount > MAX_POLL_COUNT) {
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
              const { status, posterUrl, posterFileID, errMsg } = resp.result.data;

              if (status === "completed") {
                this.cleanupTask();

                if (posterFileID) {
                  this.setData({
                    loading: false,
                    posterUrl: posterFileID,
                    errorMsg: "",
                  });
                } else if (posterUrl) {
                  this.setData({
                    loading: false,
                    posterUrl: posterUrl,
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
                this.pollTimer = setTimeout(pollOnce, POLL_INTERVAL);
              }
            } else {
              this.cleanupTask();
              this.setData({
                loading: false,
                errorMsg: resp.result?.errMsg || "获取状态失败",
              });
            }
          })
          .catch((err) => {
            if (!this.taskId) return;

            if (pollCount >= 3) {
              this.cleanupTask();
              this.setData({
                loading: false,
                errorMsg: "网络异常，请重试",
              });
            } else {
              this.pollTimer = setTimeout(pollOnce, POLL_INTERVAL);
            }
          });
      };

      pollOnce();
    },

    onImageLoad() {
      console.log("图片加载成功");
    },

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
      wx.downloadFile({
        url: this.data.posterUrl,
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