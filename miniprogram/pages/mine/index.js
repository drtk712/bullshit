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

    // Dev switches
    testMode: false,
    skipPointsDeduction: false,
  },

  onShow() {
    this.loadDevSwitches();
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
        const checkedIn = this.checkIfCheckedIn(res.result.data.user);
        getApp().globalData.user = res.result.data.user;
        this.setData({ 
          user: res.result.data.user, 
          userLoading: false,
          checkedIn,
          showProfileGate: !res.result.data.user.profileCompleted,
          profileNickName: res.result.data.user.nickName || '',
          profileAvatarTempPath: res.result.data.user.avatarFileID || '',
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

  goToTasks() {
    wx.navigateTo({ url: '/pages/mine/tasks' });
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
        this.setData({ checkedIn: true });
        this.setData({ showCheckInModal: true });
        this.loadUserProfile();
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

  loadDevSwitches() {
    const g = getApp().globalData;
    this.setData({
      testMode: !!g.testMode,
      skipPointsDeduction: !!g.skipPointsDeduction,
    });
  },

  onTestModeChange(e) {
    getApp().globalData.testMode = e.detail.value;
    this.setData({ testMode: e.detail.value });
  },

  onSkipPointsChange(e) {
    getApp().globalData.skipPointsDeduction = e.detail.value;
    this.setData({ skipPointsDeduction: e.detail.value });
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
    const nickName = (this.data.profileNickName || '').trim();
    const avatarPath = this.data.profileAvatarTempPath;

    if (!avatarPath) {
      this.setData({ profileError: '请先选择头像' });
      return;
    }
    if (!nickName) {
      this.setData({ profileError: '请填写昵称' });
      return;
    }

    this.setData({ profileSaving: true, profileError: '' });
    wx.showLoading({ title: '保存中', mask: true });

    try {
      let avatarFileID = avatarPath;
      if (!String(avatarPath).startsWith('cloud://')) {
        const extMatch = avatarPath.match(/\.(png|jpg|jpeg|webp)$/i);
        const ext = extMatch ? extMatch[1].toLowerCase().replace('jpeg', 'jpg') : 'jpg';
        const cloudPath = `user-avatars/${Date.now()}-${Math.random().toString(16).slice(2)}.${ext}`;
        const uploadRes = await wx.cloud.uploadFile({ cloudPath, filePath: avatarPath });
        avatarFileID = uploadRes.fileID;
      }

      const res = await wx.cloud.callFunction({
        name: 'quickstartFunctions',
        data: {
          type: 'updateUserProfile',
          data: { nickName, avatarFileID }
        }
      });

      if (!res.result || !res.result.success) {
        throw new Error(res.result?.errMsg || '保存失败');
      }

      const user = res.result.data.user;
      getApp().globalData.user = user;
      this.setData({
        user,
        showProfileGate: false,
        profileSaving: false,
        profileError: '',
      });
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
