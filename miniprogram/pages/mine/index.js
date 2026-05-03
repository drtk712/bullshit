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
        this.setData({ 
          user: res.result.data.user, 
          userLoading: false 
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
      manual_adjust: '积分调整'
    };
    return reasonMap[transaction.reason] || '积分变动';
  },

  getTaskDisplayName(type) {
    const typeMap = {
      'palm': 'AI看手相',
      'hair': 'AI设计发型'
    };
    return typeMap[type] || 'AI生成';
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
  }
});