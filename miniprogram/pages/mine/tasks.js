const {
  getTaskDisplayName,
  getTaskDisplayDesc,
  getTaskStatusText,
  getTaskStatusClass,
} = require('../../utils/taskDisplay');
const { buildFeatureMap, fetchFeatureList } = require('../../utils/api/features');
const { fetchTasks } = require('../../utils/api/tasks');
const { getTempFileURL, saveImageFile } = require('../../utils/previewImage');
const { buildTaskSharePayload } = require('../../utils/share');

const PAGE_SIZE = 5;
const THUMB_STYLE_NAME = '2jpg';

function applyThumbStyle(url) {
  if (!url) return '';
  return `${String(url).replace(/\/+$/, '')}/${THUMB_STYLE_NAME}`;
}

Page({
  data: {
    tasks: [],
    featureMap: {},
    loading: true,
    loadingMore: false,
    error: '',
    page: 1,
    hasMore: true,
    refreshing: false,
    activeFilter: 'all',
  },

  async onLoad() {
    await this.loadFeatureMap();
    this.loadTasks(1);
  },

  onShow() {
    const app = getApp();
    if (!app.globalData.shouldRefreshTasks || this.data.loading) return;

    app.globalData.shouldRefreshTasks = false;
    this.loadTasks(1);
  },

  async loadFeatureMap() {
    try {
      const features = await fetchFeatureList();
      this.setData({ featureMap: buildFeatureMap(features) });
    } catch (e) {
      console.error('加载功能配置失败:', e);
    }
  },

  async loadTasks(page) {
    const wasRefreshing = this.data.refreshing;

    if (page === 1) {
      this.setData({ loading: !wasRefreshing, error: '' });
    } else {
      this.setData({ loadingMore: true });
    }

    try {
      const { tasks, hasMore } = await fetchTasks({
        page,
        pageSize: PAGE_SIZE,
        filter: this.data.activeFilter,
      });
      const processed = (tasks || []).map(t => {
        const displayName = getTaskDisplayName(t, this.data.featureMap);
        const progressPercent = t.status === 'processing' ? (t.progress || 65) : 0;
        const statusText = getTaskStatusText(t);
        return {
          ...t,
          displayName,
          displayInitial: displayName.slice(0, 1),
          displayDesc: getTaskDisplayDesc(t, this.data.featureMap),
          thumbImage: '',
          shareImage: '',
          progressPercent,
          progressStyle: `width: ${progressPercent}%;`,
          statusText,
          statusDisplay: progressPercent ? `${statusText} ${progressPercent}%` : statusText,
          statusClass: getTaskStatusClass(t.status, t.pointsRefunded),
          timeText: this.formatTime(t.createdAt),
          errMsgText: t.errMsg || '处理失败，请重新上传图片再试一次。',
        };
      });
      await this.attachThumbImages(processed);

      this.setData({
        tasks: page === 1 ? processed : [...this.data.tasks, ...processed],
        page,
        hasMore,
        loading: false,
        loadingMore: false,
        refreshing: false,
      });
      if (page === 1) {
        getApp().globalData.shouldRefreshTasks = false;
      }
    } catch (err) {
      this.setData({
        loading: false,
        loadingMore: false,
        refreshing: false,
        error: '网络错误，请稍后重试'
      });
    }

    if (wasRefreshing) {
      wx.stopPullDownRefresh();
    }
  },

  async attachThumbImages(tasks) {
    await Promise.all((tasks || []).map(async (task) => {
      if (!task.posterFileID) return;
      try {
        const tempFileURL = await getTempFileURL(task.posterFileID);
        task.shareImage = tempFileURL;
        task.thumbImage = applyThumbStyle(tempFileURL);
      } catch (err) {
        task.thumbImage = '';
        task.shareImage = '';
      }
    }));
  },

  onPullDownRefresh() {
    this.setData({ refreshing: true });
    this.loadTasks(1);
  },

  onReachBottom() {
    if (this.data.hasMore && !this.data.loadingMore && !this.data.loading) {
      this.loadTasks(this.data.page + 1);
    }
  },

  goToTaskDetail(e) {
    const taskId = e.currentTarget.dataset.id;
    wx.navigateTo({ url: `/pages/mine/task-detail?id=${taskId}` });
  },

  onFilterTap(e) {
    const filter = e.currentTarget.dataset.filter;
    if (filter === this.data.activeFilter) return;
    this.setData({ activeFilter: filter, page: 1, hasMore: true });
    this.loadTasks(1);
  },

  onShareTask(e) {
    const task = this.getTaskById(e.currentTarget.dataset.id);
    if (task) {
      this.shareTaskId = task._id;
    }
  },

  onSaveTaskPoster(e) {
    const task = this.getTaskById(e.currentTarget.dataset.id);
    if (!task?.posterFileID) {
      wx.showToast({ title: '图片未处理完成', icon: 'none' });
      return;
    }

    saveImageFile(task.posterFileID);
  },

  retryTask(e) {
    const type = e.currentTarget.dataset.type || 'palm';
    wx.navigateTo({ url: `/pages/feature/upload/index?type=${type}` });
  },

  formatTime(timestamp) {
    if (!timestamp) return '';
    const date = new Date(timestamp);
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    const hours = String(date.getHours()).padStart(2, '0');
    const minutes = String(date.getMinutes()).padStart(2, '0');
    return `${month}-${day} ${hours}:${minutes}`;
  },

  getTaskById(taskId) {
    if (!taskId) return null;
    return this.data.tasks.find((task) => task._id === taskId) || null;
  },

  onShareAppMessage(options = {}) {
    const isButtonShare = options.from === 'button';
    const taskId = isButtonShare ? options.target?.dataset?.id : '';
    const task = isButtonShare ? this.getTaskById(taskId || this.shareTaskId) : null;
    this.shareTaskId = '';
    return buildTaskSharePayload(task || {});
  },

});
