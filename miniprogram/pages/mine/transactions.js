const PAGE_SIZE = 10;
const { fetchTransactions } = require('../../utils/api/transactions');

const SYSTEM_REASON_MAP = {
  first_login: '首次登录赠送',
  daily_check_in: '每日签到',
  share_reward: '分享奖励',
  create_feature_job: '处理消耗',
  job_failed_refund: '失败退款',
};

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

  goBack() {
    wx.navigateBack({
      fail: () => wx.switchTab({ url: '/pages/mine/index' }),
    });
  },

  async loadTransactions(page) {
    const wasRefreshing = this.data.refreshing;

    if (page === 1) {
      this.setData({ loading: !wasRefreshing, error: '' });
    } else {
      this.setData({ loadingMore: true });
    }

    try {
      const { transactions, hasMore } = await fetchTransactions({ page, pageSize: PAGE_SIZE });
      const processed = (transactions || []).map(t => ({
        ...t,
        amountText: this.formatAmount(t.amount),
        typeText: this.getTransactionTitle(t),
        reasonText: this.getTransactionReason(t),
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
    } catch (err) {
      this.setData({
        loading: false,
        loadingMore: false,
        refreshing: false,
        error: err.isBusinessError ? err.message : '网络错误，请稍后重试'
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

  getTransactionTitle(transaction) {
    if (transaction.type === 'adjust') return '积分调整';
    return SYSTEM_REASON_MAP[transaction.reason] || '积分变动';
  },

  getTransactionReason(transaction) {
    const reason = String(transaction.reason || '').trim();
    if (!reason) return '';
    if (transaction.type === 'adjust') return reason;
    return SYSTEM_REASON_MAP[reason] ? '' : reason;
  },
});
