const PAGE_SIZE = 20;

Page({
  data: {
    transactions: [],
    loading: true,
    loadingMore: false,
    error: '',
    page: 1,
    hasMore: true,
    refreshing: false,
  },

  onLoad() {
    this.loadTransactions(1);
  },

  async loadTransactions(page) {
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
          type: 'getTransactions',
          data: { page, pageSize: PAGE_SIZE }
        }
      });

      if (res.result && res.result.success) {
        const { transactions, hasMore } = res.result.data;
        const processed = (transactions || []).map(t => ({
          ...t,
          amountText: this.formatAmount(t.amount),
          typeText: this.getTransactionTypeText(t),
          amountClass: t.amount >= 0 ? 'amount-plus' : 'amount-minus',
          timeText: this.formatTime(t.createdAt)
        }));

        this.setData({
          transactions: page === 1 ? processed : [...this.data.transactions, ...processed],
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
    this.loadTransactions(1);
  },

  onReachBottom() {
    if (this.data.hasMore && !this.data.loadingMore && !this.data.loading) {
      this.loadTransactions(this.data.page + 1);
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
});