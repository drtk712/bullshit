const {
  getTaskDisplayName,
  getTaskStatusText,
  getTaskStatusClass,
} = require('../../utils/taskDisplay');
const { fetchFeatureList } = require('../../utils/featureConfigClient');

const PAGE_SIZE = 20;

Page({
  data: {
    tasks: [],
    allTasks: [],
    featureMap: {},
    loading: true,
    loadingMore: false,
    error: '',
    page: 1,
    hasMore: true,
    refreshing: false,
    activeFilter: 'all',
  },

  onLoad() {
    this.loadFeatureMap();
    this.loadTasks(1);
  },

  onShow() {
    // tabBar 页面切换回来时刷新数据
    if (this.data.allTasks.length > 0) {
      this.loadTasks(1);
    }
  },

  async loadFeatureMap() {
    try {
      const features = await fetchFeatureList();
      const featureMap = (features || []).reduce((acc, item) => {
        if (item?.type) acc[item.type] = item;
        return acc;
      }, {});
      this.setData({ featureMap });
    } catch (e) {
      console.error('加载功能配置失败:', e);
    }
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
          displayInitial: getTaskDisplayName(t.type).slice(0, 1),
          displayDesc: this.getTaskDesc(t.type),
          previewImageHD: this.data.featureMap[t.type]?.previewImageHD || '',
          statusText: getTaskStatusText(t),
          statusClass: getTaskStatusClass(t.status, t.pointsRefunded),
          timeText: this.formatTime(t.createdAt)
        }));

        this.setData({
          tasks: page === 1 ? processed : [...this.data.tasks, ...processed],
          allTasks: page === 1 ? processed : [...this.data.allTasks, ...processed],
          page,
          hasMore,
          loading: false,
          loadingMore: false,
          refreshing: false,
        });
        this.applyFilter();
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

  onFilterTap(e) {
    const filter = e.currentTarget.dataset.filter;
    this.setData({ activeFilter: filter });
    this.applyFilter();
  },

  applyFilter() {
    const filter = this.data.activeFilter;
    const allTasks = this.data.allTasks;
    let filtered = allTasks;

    if (filter === 'processing') {
      filtered = allTasks.filter(t => t.status === 'pending' || t.status === 'processing');
    } else if (filter === 'completed') {
      filtered = allTasks.filter(t => t.status === 'completed');
    } else if (filter === 'failed') {
      filtered = allTasks.filter(t => t.status === 'failed');
    }

    this.setData({ tasks: filtered });
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

  getTaskDesc(type) {
    const descMap = {
      palm: '灵面看手',
      hair: '短发一眼飒',
      profile: '职业形象卡',
      doodle: '手绘风头像',
      soul: '山水简笔画',
    };
    return descMap[type] || '趣味生成';
  },

});
