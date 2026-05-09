const {
  buildShareRewardCopy,
  canClaimShareReward,
  claimShareReward,
  getShareRewardStatus,
} = require('../../utils/shareReward');
const { saveUserProfile } = require('../../utils/profile');

Page({
  data: {
    // User card
    user: null,
    userLoading: true,
    userError: '',

    // Check-in
    checkedIn: false,
    checkInLoading: false,
    showCheckInModal: false,
    showProfileGate: false,
    profileAvatarTempPath: '',
    profileNickName: '',
    profileSaving: false,
    profileError: '',
    shareRewardStatus: null,
    shareRewardCopy: buildShareRewardCopy(),

  },

  onShow() {
    const app = getApp();
    const cachedUser = app.globalData.user;
    if (cachedUser && !app.globalData.shouldRefreshUserProfile) {
      this.applyUserProfile(cachedUser);
      this.loadShareRewardStatus();
      return;
    }

    if (this.data.user) {
      this.setData({ userLoading: false, userError: '' });
      this.loadShareRewardStatus();
      return;
    }

    this.loadUserProfile();
  },

  async loadUserProfile() {
    this.setData({ userLoading: true, userError: '' });
    try {
      const res = await wx.cloud.callFunction({
        name: 'quickstartFunctions',
        data: { type: 'getUserProfile', data: {} }
      });
      if (res.result && res.result.success) {
        getApp().globalData.shouldRefreshUserProfile = false;
        this.applyUserProfile(res.result.data.user);
        this.loadShareRewardStatus();
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

  applyUserProfile(user) {
    const checkedIn = this.checkIfCheckedIn(user);
    getApp().globalData.user = user;
    this.setData({
      user,
      userLoading: false,
      userError: '',
      checkedIn,
      showProfileGate: !user.profileCompleted,
      profileNickName: user.nickName || '',
      profileAvatarTempPath: user.avatarFileID || '',
    });
  },

  async loadShareRewardStatus() {
    try {
      const status = await getShareRewardStatus();
      const user = this.data.user || getApp().globalData.user;
      if (user) {
        this.applyUserProfile({
          ...user,
          points: status.points,
        });
      }
      this.setData({
        shareRewardStatus: status,
        shareRewardCopy: buildShareRewardCopy(status),
      });
    } catch (err) {
      console.error('加载分享奖励状态失败:', err);
    }
  },

  goToTasks() {
    wx.switchTab({ url: '/pages/mine/tasks' });
  },

  goToTransactions() {
    wx.navigateTo({ url: '/pages/mine/transactions' });
  },

  onFavorite() {
    wx.showToast({ title: '功能开发中', icon: 'none' });
  },

  async handleShareEarnPoints() {
    if (!canClaimShareReward(this.data.shareRewardStatus)) return null;

    try {
      const res = await claimShareReward();
      if (res.status) {
        this.setData({
          shareRewardStatus: res.status,
          shareRewardCopy: buildShareRewardCopy(res.status),
        });
      }
      if (res.success) {
        const user = this.data.user
          ? { ...this.data.user, points: res.status.points }
          : null;
        if (user) {
          this.applyUserProfile(user);
        } else {
          getApp().globalData.shouldRefreshUserProfile = true;
        }
        return res.status;
      }
      return null;
    } catch (err) {
      console.error('分享奖励获取失败:', err);
      return null;
    }
  },

  onShareAppMessage() {
    this.handleShareEarnPoints();
    return {
      title: '玩图局 - 图片玩法合集，快来试试！',
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
        const data = res.result.data || {};
        const user = this.data.user
          ? {
              ...this.data.user,
              points: data.points ?? this.data.user.points,
              lastCheckInAt: data.checkInAt || Date.now(),
              checkInDays: Number(this.data.user.checkInDays || 0) + 1,
            }
          : null;
        if (user) {
          this.applyUserProfile(user);
        } else {
          this.setData({ checkedIn: true });
          getApp().globalData.shouldRefreshUserProfile = true;
        }
        this.setData({ showCheckInModal: true });
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
  },

  hideCheckInModal() {
    this.setData({ showCheckInModal: false });
  },

  onEditProfile() {
    this.setData({
      showProfileGate: true,
      profileAvatarTempPath: this.data.user?.avatarFileID || '',
      profileNickName: this.data.user?.nickName || '',
      profileError: '',
    });
  },

  hideProfileGate() {
    if (!this.data.user?.profileCompleted) return;
    this.setData({ showProfileGate: false, profileError: '' });
  },

  onChooseAvatar(e) {
    const avatarUrl = e.detail?.avatarUrl || '';
    if (!avatarUrl) {
      this.setData({ profileError: '请选择头像' });
      return;
    }
    this.setData({ profileAvatarTempPath: avatarUrl, profileError: '' });
  },

  onNickNameInput(e) {
    this.setData({ profileNickName: e.detail.value, profileError: '' });
  },

  async onSaveProfile() {
    this.setData({ profileSaving: true, profileError: '' });
    wx.showLoading({ title: '保存中', mask: true });

    try {
      const user = await saveUserProfile({
        nickName: this.data.profileNickName,
        avatarPath: this.data.profileAvatarTempPath,
      });

      getApp().globalData.shouldRefreshUserProfile = false;
      this.setData({
        showProfileGate: false,
        profileSaving: false,
        profileError: '',
      });
      this.applyUserProfile(user);
      wx.showToast({ title: '资料已保存', icon: 'success' });
    } catch (err) {
      this.setData({
        profileSaving: false,
        profileError: err.message || err.errMsg || '保存失败',
      });
    } finally {
      wx.hideLoading();
    }
  },

  onSettings() {
    wx.showToast({ title: '设置中心功能开发中', icon: 'none' });
  },
});
