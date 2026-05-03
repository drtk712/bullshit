Page({
  data: {
    user: null,
    points: 0,
    transactions: [],
    tasks: [],
    loading: true,
    error: ''
  },

  onShow() {
    this.loadUserData();
  },

  async loadUserData() {
    this.setData({ loading: true, error: '' });

    try {
      const res = await wx.cloud.callFunction({
        name: 'quickstartFunctions',
        data: {
          type: 'getUserProfile',
          data: {
            transactionLimit: 5,
            taskLimit: 10
          }
        }
      });

      if (res.result && res.result.success) {
        const { user, recentTransactions, recentTasks } = res.result.data;

        const processedTransactions = (recentTransactions || []).map(transaction => ({
          ...transaction,
          amountText: this.formatAmount(transaction.amount),
          typeText: this.getTransactionTypeText(transaction),
          amountClass: transaction.amount >= 0 ? 'amount-plus' : 'amount-minus',
          timeText: this.formatTime(transaction.createdAt)
        }));
        const processedTasks = (recentTasks || []).map(task => ({
          ...task,
          displayName: this.getTaskDisplayName(task.type),
          statusText: this.getTaskStatusText(task),
          statusClass: this.getTaskStatusClass(task.status, task.pointsRefunded),
          timeText: this.formatTime(task.createdAt)
        }));

        this.setData({
          user,
          points: (user && user.points) || 0,
          transactions: processedTransactions,
          tasks: processedTasks,
          loading: false
        });
      } else {
        this.setData({
          loading: false,
          error: res.result?.errMsg || '加载失败'
        });
      }
    } catch (err) {
      console.error('加载用户数据失败:', err);
      this.setData({
        loading: false,
        error: '网络错误，请稍后重试'
      });
    }
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