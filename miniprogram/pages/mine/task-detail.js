Page({
  data: {
    task: null,
    posterPreviewUrl: '',
    posterError: '',
    loading: true,
    error: '',
    polling: false,
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
        });

        if (task.status === 'pending' && !this.data.polling) {
          this.startPolling();
        } else if (task.status !== 'pending' && this.data.polling) {
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
    this.setData({ polling: true });
    this.pollTimer = setInterval(() => {
      this.loadTask({ silent: true });
    }, 3000);
  },

  stopPolling() {
    this.setData({ polling: false });
    if (this.pollTimer) {
      clearInterval(this.pollTimer);
      this.pollTimer = null;
    }
  },

  onUnload() {
    this.stopPolling();
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
    const typeMap = { 'palm': '看手相', 'hair': '设计发型', 'profile': '个人形象分析', 'doodle': 'INS手绘风照片' };
    return typeMap[type] || '生成记录';
  },

  getTaskStatusText(task) {
    const statusMap = {
      'pending': '处理中',
      'completed': '已完成',
      'failed': task.pointsRefunded ? '失败已退款' : '生成失败'
    };
    return statusMap[task.status] || task.status;
  },

  getTaskStatusClass(status, pointsRefunded) {
    if (status === 'pending') return 'status-pending';
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