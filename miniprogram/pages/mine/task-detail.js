const { createTaskPoller, isActiveTaskStatus } = require('../../utils/taskPoller');
const {
  getTaskDisplayName,
  getTaskStatusText,
  getTaskStatusClass,
} = require('../../utils/taskDisplay');
const { buildFeatureMap, fetchFeatureList } = require('../../utils/api/features');
const { deleteTask, fetchTask } = require('../../utils/api/tasks');
const { getTempFileURL, saveImageFile } = require('../../utils/previewImage');

Page({
  data: {
    task: null,
    posterPreviewUrl: '',
    posterError: '',
    resultUrls: [],
    originalImageUrl: '',
    originalImageError: '',
    activeTab: 'result',
    loading: true,
    error: '',
    polling: false,
    syncError: '',
    featureMap: {},
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
          error: '处理超时，请稍后查看任务记录',
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

  goBack() {
    wx.navigateBack({
      fail: () => wx.switchTab({ url: '/pages/mine/tasks' }),
    });
  },

  retryUpload() {
    const type = this.data.task?.type || 'palm';
    wx.redirectTo({ url: `/pages/feature/upload/index?type=${type}` });
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
      if (!Object.keys(this.data.featureMap).length) {
        await this.loadFeatureMap();
      }
      const task = await fetchTask(this.taskId);
      const posterState = await this.createPosterState(task);
      const resultUrls = await this.createResultUrls(task);
      const originalState = await this.createOriginalImageState(task);

      const displayName = getTaskDisplayName(task, this.data.featureMap);
      this.setData({
        task: {
          ...task,
          displayName,
          displayInitial: displayName.slice(0, 1),
          statusText: getTaskStatusText(task),
          statusClass: getTaskStatusClass(task.status, task.pointsRefunded),
          formattedTime: this.formatTime(task.createdAt),
          pointsCostText: this.getPointsCostText(task),
          friendlyErrMsg: this.getFriendlyErrMsg(task.errMsg),
        },
        ...posterState,
        resultUrls,
        ...originalState,
        loading: false,
        syncError: '',
      });

      if (this.isActiveTask(task.status) && !this.data.polling) {
        this.startPolling();
      } else if (!this.isActiveTask(task.status) && this.data.polling) {
        this.stopPolling();
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

  async loadFeatureMap() {
    try {
      const features = await fetchFeatureList();
      this.setData({ featureMap: buildFeatureMap(features) });
    } catch (e) {
      console.error('加载功能配置失败:', e);
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

    const wasActive = this.isActiveTask(this.data.task.status);
    const nextTask = {
      ...this.data.task,
      status: taskStatus.status || this.data.task.status,
      posterFileID: taskStatus.posterFileID || this.data.task.posterFileID,
      errMsg: taskStatus.errMsg || '',
      statusText: getTaskStatusText({
        ...this.data.task,
        status: taskStatus.status || this.data.task.status,
        errMsg: taskStatus.errMsg || '',
      }),
      statusClass: getTaskStatusClass(
        taskStatus.status || this.data.task.status,
        this.data.task.pointsRefunded
      ),
    };
    nextTask.pointsCostText = this.getPointsCostText(nextTask);
    nextTask.friendlyErrMsg = this.getFriendlyErrMsg(nextTask.errMsg);

    this.setData({
      task: nextTask,
      syncError: '',
    });

    if (!this.isActiveTask(nextTask.status)) {
      if (wasActive) {
        getApp().globalData.shouldRefreshTasks = true;
      }
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

  switchTab(e) {
    this.setData({ activeTab: e.currentTarget.dataset.tab || 'result' });
  },

  async viewPoster() {
    const fileID = this.data.activeTab === 'original'
      ? this.data.task?.fileID
      : this.data.task?.posterFileID;
    if (!fileID) return;

    try {
      const cachedUrl = this.data.activeTab === 'original'
        ? this.data.originalImageUrl
        : this.data.posterPreviewUrl;
      const tempUrl = cachedUrl || await getTempFileURL(fileID);
      wx.previewImage({
        urls: [tempUrl],
        current: tempUrl
      });
    } catch (err) {
      wx.showToast({ title: '预览失败', icon: 'none' });
    }
  },

  savePoster() {
    const posterFileID = this.data.task?.posterFileID;
    if (!posterFileID) {
      wx.showToast({ title: '图片未处理完成', icon: 'none' });
      return;
    }

    saveImageFile(posterFileID);
  },

  viewResultPiece(e) {
    const current = e.currentTarget.dataset.url;
    if (!current) return;
    wx.previewImage({ urls: this.data.resultUrls, current });
  },

  saveResultPiece(e) {
    const index = Number(e.currentTarget.dataset.index || 0);
    const fileID = this.data.task?.resultFileIDs?.[index];
    if (!fileID) {
      wx.showToast({ title: '图片未处理完成', icon: 'none' });
      return;
    }
    saveImageFile(fileID);
  },

  async createPosterState(task) {
    if (task.status !== 'completed' || !task.posterFileID) {
      return { posterPreviewUrl: '', posterError: '' };
    }

    try {
      const posterPreviewUrl = await getTempFileURL(task.posterFileID);
      return { posterPreviewUrl, posterError: '' };
    } catch (err) {
      return { posterPreviewUrl: '', posterError: '图片加载失败，点击查看大图重试' };
    }
  },

  async createOriginalImageState(task) {
    if (!task.fileID) {
      return { originalImageUrl: '', originalImageError: '原图不存在' };
    }

    try {
      const originalImageUrl = await getTempFileURL(task.fileID);
      return { originalImageUrl, originalImageError: '' };
    } catch (err) {
      return { originalImageUrl: '', originalImageError: '原图加载失败，点击重试' };
    }
  },

  async createResultUrls(task) {
    const fileIDs = Array.isArray(task.resultFileIDs) ? task.resultFileIDs.filter(Boolean) : [];
    if (task.status !== 'completed' || !fileIDs.length) return [];
    const results = await Promise.all(fileIDs.map((fileID) => getTempFileURL(fileID).catch(() => '')));
    return results.filter(Boolean);
  },

  isActiveTask(status) {
    return isActiveTaskStatus(status);
  },

  getPointsCostText(task = {}) {
    if (task.status === 'failed' && task.pointsRefunded) {
      return '积分已退回';
    }

    const cost = Number(task.pointsCost || 0);
    return cost > 0 ? `-${cost} 积分` : '未扣积分';
  },

  getFriendlyErrMsg(errMsg) {
    if (!errMsg) {
      return '原因：上传的图片主体不够清晰或光线过暗，请尝试更换一张更清晰的照片。';
    }

    if (/API|model|\/v1\/|503|OpenAI|gpt|错误/i.test(errMsg)) {
      return '图片处理服务暂时不可用，请稍后重试或重新上传。';
    }

    return errMsg;
  },

  onShareAppMessage() {
    const task = this.data.task || {};
    const path = task.status === 'completed' && this.taskId
      ? `/pages/share/task/index?id=${this.taskId}`
      : '/pages/index/index';

    return {
      title: `我在玩图局处理了一张图片`,
      path,
      imageUrl: this.data.posterPreviewUrl || '',
    };
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

  handleDeleteTask() {
    if (!this.taskId) return;

    const status = this.data.task?.status;
    if (status === 'init' || status === 'pending' || status === 'processing') {
      wx.showToast({ title: '进行中的任务不能删除', icon: 'none' });
      return;
    }

    const taskId = this.taskId;

    wx.showModal({
      title: '确认删除',
      content: '删除后无法恢复，确定要删除这条记录吗？',
      success: async (res) => {
        if (!res.confirm) return;

        wx.showLoading({ title: '删除中...' });
        try {
          await deleteTask(taskId);
          wx.hideLoading();
          getApp().globalData.shouldRefreshTasks = true;
          wx.showToast({ title: '删除成功', icon: 'success' });
          setTimeout(() => {
            wx.navigateBack({ fail: () => wx.switchTab({ url: '/pages/mine/tasks' }) });
          }, 500);
        } catch (err) {
          wx.hideLoading();
          wx.showToast({ title: err.message || '删除失败', icon: 'none' });
        }
      }
    });
  },
});
