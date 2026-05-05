Page({
  data: {
    // User card
    user: null,
    userLoading: true,
    userError: '',
    
    // Transactions section
    transactions: [],
    transLoading: true,
    transError: '',
    transTotal: 0,
    
    // Tasks section
    tasks: [],
    tasksLoading: true,
    tasksError: '',
    tasksTotal: 0,

    // Check-in
    checkedIn: false,
    checkInLoading: false,
  },

  onShow() {
    this.loadUserProfile();
    this.loadTransactions();
    this.loadTasks();
  },

  async loadUserProfile() {
    this.setData({ userLoading: true, userError: '' });
    try {
      const res = await wx.cloud.callFunction({
        name: 'quickstartFunctions',
        data: { type: 'getUserProfile', data: {} }
      });
      if (res.result && res.result.success) {
        const checkedIn = this.checkIfCheckedIn(res.result.data.user);
        this.setData({ 
          user: res.result.data.user, 
          userLoading: false,
          checkedIn
        });
      } else {
        this.setData({ 
          userLoading: false, 
          userError: res.result?.errMsg || '加载失败' 
        });
      }
    } catch (err) {
      console.error('加载用户数据失败:', err);
      this.setData({ userLoading: false, userError: '网络错误' });
    }
  },

  async loadTransactions() {
    this.setData({ transLoading: true, transError: '' });
    try {
      const res = await wx.cloud.callFunction({
        name: 'quickstartFunctions',
        data: { type: 'getTransactions', data: { page: 1, pageSize: 5 } }
      });
      if (res.result && res.result.success) {
        const processed = (res.result.data.transactions || []).map(t => ({
          ...t,
          amountText: this.formatAmount(t.amount),
          typeText: this.getTransactionTypeText(t),
          amountClass: t.amount >= 0 ? 'amount-plus' : 'amount-minus',
          timeText: this.formatTime(t.createdAt)
        }));
        this.setData({ 
          transactions: processed, 
          transTotal: res.result.data.total || 0,
          transLoading: false 
        });
      } else {
        this.setData({ 
          transLoading: false, 
          transError: res.result?.errMsg || '加载失败' 
        });
      }
    } catch (err) {
      console.error('加载积分记录失败:', err);
      this.setData({ transLoading: false, transError: '网络错误' });
    }
  },

  async loadTasks() {
    this.setData({ tasksLoading: true, tasksError: '' });
    try {
      const res = await wx.cloud.callFunction({
        name: 'quickstartFunctions',
        data: { type: 'getTasks', data: { page: 1, pageSize: 5 } }
      });
      if (res.result && res.result.success) {
        const processed = (res.result.data.tasks || []).map(t => ({
          ...t,
          displayName: this.getTaskDisplayName(t.type),
          statusText: this.getTaskStatusText(t),
          statusClass: this.getTaskStatusClass(t.status, t.pointsRefunded),
          timeText: this.formatTime(t.createdAt)
        }));
        this.setData({ 
          tasks: processed, 
          tasksTotal: res.result.data.total || 0,
          tasksLoading: false 
        });
      } else {
        this.setData({ 
          tasksLoading: false, 
          tasksError: res.result?.errMsg || '加载失败' 
        });
      }
    } catch (err) {
      console.error('加载生成记录失败:', err);
      this.setData({ tasksLoading: false, tasksError: '网络错误' });
    }
  },

  goToTransactions() {
    wx.navigateTo({ url: '/pages/mine/transactions' });
  },

  goToTasks() {
    wx.navigateTo({ url: '/pages/mine/tasks' });
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

  formatAmount(amount) {
    if (amount > 0) return `+${amount}`;
    return String(amount || 0);
  },

  getTransactionTypeText(transaction) {
    const reasonMap = {
      first_login: '首次登录赠送',
      create_ai_job: '生成消耗',
      job_failed_refund: '失败退款',
      manual_adjust: '积分调整',
      daily_check_in: '每日签到',
      share_reward: '分享奖励'
    };
    return reasonMap[transaction.reason] || '积分变动';
  },

  getTaskDisplayName(type) {
    const typeMap = {
      'palm': '看手相',
      'hair': '设计发型',
      'profile': '个人形象分析',
      'doodle': 'INS手绘风照片',
      'soul': '灵魂画手'
    };
    return typeMap[type] || '生成记录';
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

  async handleShareEarnPoints() {
    try {
      const res = await wx.cloud.callFunction({
        name: 'quickstartFunctions',
        data: { type: 'shareEarnPoints', data: {} }
      });

      if (res.result && res.result.success) {
        wx.showToast({ title: '分享成功 +1 积分', icon: 'success' });
        this.loadUserProfile();
        this.loadTransactions();
        return res.result.data;
      } else {
        wx.showToast({ title: res.result?.errMsg || '今日分享次数已达上限', icon: 'none' });
        return null;
      }
    } catch (err) {
      console.error('分享奖励获取失败:', err);
      return null;
    }
  },

  onShareAppMessage() {
    this.handleShareEarnPoints();
    return {
      title: '玩图局 - AI 图片玩法合集，快来试试！',
      path: '/pages/index/index'
    };
  },

  checkIfCheckedIn(user) {
    if (!user || !user.lastCheckInAt) return false;
    
    const today = new Date();
    const shanghaiToday = new Date(today.getTime() + 8 * 60 * 60 * 1000)
      .toISOString()
      .split('T')[0];
    
    const lastCheckIn = new Date(user.lastCheckInAt);
    const shanghaiLastCheckIn = new Date(lastCheckIn.getTime() + 8 * 60 * 60 * 1000)
      .toISOString()
      .split('T')[0];
    
    return shanghaiToday === shanghaiLastCheckIn;
  },

  async handleCheckIn() {
    if (this.data.checkInLoading || this.data.checkedIn) return;

    this.setData({ checkInLoading: true });
    try {
      const res = await wx.cloud.callFunction({
        name: 'quickstartFunctions',
        data: { type: 'dailyCheckIn', data: {} }
      });
      
      if (res.result && res.result.success) {
        this.setData({ checkedIn: true });
        wx.showToast({ title: '签到成功 +1 积分', icon: 'success' });
        this.loadUserProfile();
        this.loadTransactions();
      } else if (res.result && res.result.data?.checkedIn) {
        this.setData({ checkedIn: true });
        wx.showToast({ title: '今日已签到', icon: 'none' });
      } else {
        wx.showToast({ title: res.result?.errMsg || '签到失败', icon: 'none' });
      }
    } catch (err) {
      console.error('签到失败:', err);
      wx.showToast({ title: '网络错误', icon: 'none' });
    } finally {
      this.setData({ checkInLoading: false });
    }
  }
});