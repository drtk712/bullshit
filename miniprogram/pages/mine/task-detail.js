const { createTaskPoller, isActiveTaskStatus } = require('../../utils/taskPoller');

Page({
  data: {
    task: null,
    posterPreviewUrl: '',
    posterError: '',
    loading: true,
    error: '',
    polling: false,
    syncError: '',
  },

  taskPoller: null,

  ensureTaskPoller() {
    if (this.taskPoller) return this.taskPoller;

    this.taskPoller = createTaskPoller({
      onStatus: async (taskStatus) => {
        await this.applyPolledTaskStatus(taskStatus);
      },
      onError: (errMsg) => {
        this.stopPolling();
        this.setData({
          error: errMsg || '获取状态失败',
        });
      },
      onTimeout: () => {
        this.stopPolling();
        this.setData({
          error: '生成超时，请稍后查看任务记录',
        });
      },
      onTransientError: () => {
        this.setData({ syncError: '状态同步暂时失败，正在重试' });
      },
    });

    return this.taskPoller;
  },

  onLoad(options) {
    this.taskId = options.id;
    this.loadTask();
  },

  onPullDownRefresh() {
    this.loadTask({ silent: true, stopRefresh: true });
  },

  async loadTask(options = {}) {
    const { silent = false, stopRefresh = false } = options;

    if (!silent) {
      this.setData({ loading: true, error: '' });
    }

    try {
      const res = await wx.cloud.callFunction({
        name: 'quickstartFunctions',
        data: {
          type: 'getTask',
          data: { taskId: this.taskId }
        }
      });

      if (res.result && res.result.success) {
        const task = res.result.data.task;
        const posterState = await this.createPosterState(task);

        this.setData({
          task: {
            ...task,
            displayName: this.getTaskDisplayName(task.type),
            statusText: this.getTaskStatusText(task),
            statusClass: this.getTaskStatusClass(task.status, task.pointsRefunded),
            formattedTime: this.formatTime(task.createdAt),
          },
          ...posterState,
          loading: false,
          syncError: '',
        });

        if (this.isActiveTask(task.status) && !this.data.polling) {
          this.startPolling();
        } else if (!this.isActiveTask(task.status) && this.data.polling) {
          this.stopPolling();
        }
      } else {
        this.stopPolling();
        this.setData({
          loading: false,
          error: res.result?.errMsg || '加载失败'
        });
      }
    } catch (err) {
      this.setData({
        loading: false,
        error: '网络错误，请稍后重试'
      });
    }

    if (stopRefresh) {
      wx.stopPullDownRefresh();
    }
  },

  startPolling() {
    if (!this.taskId) return;
    this.setData({ polling: true });
    this.ensureTaskPoller().start(this.taskId);
  },

  stopPolling() {
    this.setData({ polling: false });
    if (this.taskPoller) {
      this.taskPoller.stop();
    }
  },

  async applyPolledTaskStatus(taskStatus) {
    if (!this.data.task) return;

    const nextTask = {
      ...this.data.task,
      status: taskStatus.status || this.data.task.status,
      posterFileID: taskStatus.posterFileID || this.data.task.posterFileID,
      errMsg: taskStatus.errMsg || '',
      statusText: this.getTaskStatusText({
        ...this.data.task,
        status: taskStatus.status || this.data.task.status,
        errMsg: taskStatus.errMsg || '',
      }),
      statusClass: this.getTaskStatusClass(
        taskStatus.status || this.data.task.status,
        this.data.task.pointsRefunded
      ),
    };

    this.setData({
      task: nextTask,
      syncError: '',
    });

    if (!this.isActiveTask(nextTask.status)) {
      await this.loadTask({ silent: true });
    }
  },

  onShow() {
    if (this.data.task && this.isActiveTask(this.data.task.status)) {
      this.ensureTaskPoller().resume();
      this.setData({ polling: true });
    }
  },

  onHide() {
    if (this.taskPoller) {
      this.taskPoller.pause();
    }
    this.setData({ polling: false });
  },

  onUnload() {
    if (this.taskPoller) {
      this.taskPoller.reset();
    }
    this.setData({ polling: false });
  },

  async viewPoster() {
    const posterFileID = this.data.task?.posterFileID;
    if (!posterFileID) return;

    try {
      const tempUrl = this.data.posterPreviewUrl || await this.getPosterTempFileURL(posterFileID);
      wx.previewImage({
        urls: [tempUrl],
        current: tempUrl
      });
    } catch (err) {
      wx.showToast({ title: '预览失败', icon: 'none' });
    }
  },

  async savePoster() {
    const posterFileID = this.data.task?.posterFileID;
    if (!posterFileID) return;

    try {
      wx.showLoading({ title: '保存中...' });
      const tempUrl = await this.getPosterTempFileURL(posterFileID);
      const downloadResult = await wx.downloadFile({ url: tempUrl });

      if (downloadResult.statusCode !== 200 || !downloadResult.tempFilePath) {
        throw new Error('下载图片失败');
      }

      await wx.saveImageToPhotosAlbum({ filePath: downloadResult.tempFilePath });
      wx.showToast({ title: '保存成功', icon: 'success' });
    } catch (err) {
      const errMsg = String(err.errMsg || err.message || '');
      if (errMsg.includes('auth deny') || errMsg.includes('authorize')) {
        wx.showModal({
          title: '提示',
          content: '需要相册权限才能保存图片，请在设置中开启',
          showCancel: false
        });
      } else {
        wx.showToast({ title: '保存失败', icon: 'none' });
      }
    } finally {
      wx.hideLoading();
    }
  },

  async createPosterState(task) {
    if (task.status !== 'completed' || !task.posterFileID) {
      return { posterPreviewUrl: '', posterError: '' };
    }

    try {
      const posterPreviewUrl = await this.getPosterTempFileURL(task.posterFileID);
      return { posterPreviewUrl, posterError: '' };
    } catch (err) {
      return { posterPreviewUrl: '', posterError: '图片加载失败，点击查看大图重试' };
    }
  },

  async getPosterTempFileURL(fileID) {
    const result = await wx.cloud.getTempFileURL({ fileList: [fileID] });
    const fileInfo = result.fileList && result.fileList[0];

    if (!fileInfo || fileInfo.status !== 0 || !fileInfo.tempFileURL) {
      throw new Error(fileInfo?.errMsg || '获取图片链接失败');
    }

    return fileInfo.tempFileURL;
  },

  getTaskDisplayName(type) {
    const typeMap = { 'palm': '看手相', 'hair': '设计发型', 'profile': '个人形象分析', 'doodle': 'INS手绘风照片', 'soul': '灵魂画手' };
    return typeMap[type] || '生成记录';
  },

  isActiveTask(status) {
    return isActiveTaskStatus(status);
  },

  getTaskStatusText(task) {
    const statusMap = {
      'pending': '排队中',
      'processing': '生成中',
      'completed': '已完成',
      'failed': task.pointsRefunded ? '失败已退款' : '生成失败'
    };
    return statusMap[task.status] || task.status;
  },

  getTaskStatusClass(status, pointsRefunded) {
    if (status === 'pending') return 'status-pending';
    if (status === 'processing') return 'status-processing';
    if (status === 'completed') return 'status-completed';
    if (status === 'failed') return pointsRefunded ? 'status-refunded' : 'status-failed';
    return '';
  },

  formatTime(timestamp) {
    if (!timestamp) return '';
    const date = new Date(timestamp);
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    const hours = String(date.getHours()).padStart(2, '0');
    const minutes = String(date.getMinutes()).padStart(2, '0');
    return `${year}-${month}-${day} ${hours}:${minutes}`;
  },
});