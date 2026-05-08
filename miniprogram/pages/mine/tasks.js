const {
  getTaskDisplayName,
  getTaskDisplayDesc,
  getTaskStatusText,
  getTaskStatusClass,
} = require('../../utils/taskDisplay');
const { buildFeatureMap, fetchFeatureList } = require('../../utils/featureConfigClient');

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
    shareTask: null,
  },

  async onLoad() {
    await this.loadFeatureMap();
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
      this.setData({ featureMap: buildFeatureMap(features) });
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
        const processed = (tasks || []).map(t => {
          const displayName = getTaskDisplayName(t.type, this.data.featureMap);
          const progressPercent = t.status === 'processing' ? (t.progress || 65) : 0;
          const statusText = getTaskStatusText(t);
          return {
            ...t,
            displayName,
            displayInitial: displayName.slice(0, 1),
            displayDesc: getTaskDisplayDesc(t.type, this.data.featureMap),
            thumbImage: t.posterFileID || '',
            progressPercent,
            progressStyle: `width: ${progressPercent}%;`,
            statusText,
            statusDisplay: progressPercent ? `${statusText} ${progressPercent}%` : statusText,
            statusClass: getTaskStatusClass(t.status, t.pointsRefunded),
            timeText: this.formatTime(t.createdAt),
            errMsgText: t.errMsg || '生成失败，请重新上传照片再试一次。',
          };
        });

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

  onShareTask(e) {
    const task = this.getTaskById(e.currentTarget.dataset.id);
    if (task) {
      this.setData({ shareTask: task });
    }
  },

  onSaveTaskPoster(e) {
    const task = this.getTaskById(e.currentTarget.dataset.id);
    if (!task?.posterFileID) {
      wx.showToast({ title: '图片未生成完成', icon: 'none' });
      return;
    }

    this.savePosterFile(task.posterFileID);
  },

  retryTask(e) {
    const type = e.currentTarget.dataset.type || 'palm';
    wx.navigateTo({ url: `/pages/ai/upload/index?type=${type}` });
  },

  applyFilter() {
    const filter = this.data.activeFilter;
    const allTasks = this.data.allTasks;
    let filtered = allTasks;

    if (filter === 'processing') {
      filtered = allTasks.filter(t => t.status === 'init' || t.status === 'pending' || t.status === 'processing');
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

  getTaskById(taskId) {
    if (!taskId) return null;
    return this.data.allTasks.find((task) => task._id === taskId) || null;
  },

  savePosterFile(posterFileID) {
    wx.getSetting({
      success: (settingRes) => {
        if (settingRes.authSetting['scope.writePhotosAlbum']) {
          this.downloadAndSavePoster(posterFileID);
          return;
        }

        wx.authorize({
          scope: 'scope.writePhotosAlbum',
          success: () => this.downloadAndSavePoster(posterFileID),
          fail: () => {
            wx.showModal({
              title: '需要相册权限',
              content: '请在设置中开启相册权限以保存图片',
              confirmText: '去设置',
              success: (modalRes) => {
                if (!modalRes.confirm) return;

                wx.openSetting({
                  success: (openRes) => {
                    if (openRes.authSetting['scope.writePhotosAlbum']) {
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
    wx.showLoading({ title: '保存中...' });

    wx.cloud.downloadFile({
      fileID: posterFileID,
      success: (downloadRes) => {
        if (!downloadRes.tempFilePath) {
          wx.hideLoading();
          wx.showToast({ title: '下载失败', icon: 'none' });
          return;
        }

        wx.saveImageToPhotosAlbum({
          filePath: downloadRes.tempFilePath,
          success: () => {
            wx.hideLoading();
            wx.showToast({ title: '已保存到相册', icon: 'success' });
          },
          fail: () => {
            wx.hideLoading();
            wx.showToast({ title: '保存失败', icon: 'none' });
          },
        });
      },
      fail: () => {
        wx.hideLoading();
        wx.showToast({ title: '下载失败', icon: 'none' });
      },
    });
  },

  onShareAppMessage(options = {}) {
    const taskId = options.target?.dataset?.id;
    const task = this.getTaskById(taskId) || this.data.shareTask;
    return {
      title: `我在玩图局生成了${task?.displayName || '趣味图'}`,
      path: '/pages/index/index',
      imageUrl: task?.thumbImage || '',
    };
  },

});
