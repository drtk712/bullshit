const {
  getTaskDisplayName,
  getTaskStatusText,
  getTaskStatusClass,
} = require('../../utils/taskDisplay');

const PAGE_SIZE = 20;

Page({
  data: {
    tasks: [],
    loading: true,
    loadingMore: false,
    error: '',
    page: 1,
    hasMore: true,
    refreshing: false,
  },

  onLoad() {
    this.loadTasks(1);
  },

  async loadTasks(page) {
    const wasRefreshing = this.data.refreshing;

    if (page === 1) {
      this.setData({ loading: true, error: '' });
    } else {
      this.setData({ loadingMore: true });
    }

    try {
      const res = await wx.cloud.callFunction({
        name: 'quickstartFunctions',
        data: {
          type: 'getTasks',
          data: { page, pageSize: PAGE_SIZE }
        }
      });

      if (res.result && res.result.success) {
        const { tasks, hasMore } = res.result.data;
        const processed = (tasks || []).map(t => ({
          ...t,
          displayName: getTaskDisplayName(t.type),
          statusText: getTaskStatusText(t),
          statusClass: getTaskStatusClass(t.status, t.pointsRefunded),
          timeText: this.formatTime(t.createdAt)
        }));

        this.setData({
          tasks: page === 1 ? processed : [...this.data.tasks, ...processed],
          page,
          hasMore,
          loading: false,
          loadingMore: false,
          refreshing: false,
        });
      } else {
        this.setData({
          loading: false,
          loadingMore: false,
          refreshing: false,
          error: res.result?.errMsg || '加载失败'
        });
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

  formatTime(timestamp) {
    if (!timestamp) return '';
    const date = new Date(timestamp);
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    const hours = String(date.getHours()).padStart(2, '0');
    const minutes = String(date.getMinutes()).padStart(2, '0');
    return `${month}-${day} ${hours}:${minutes}`;
  },

});