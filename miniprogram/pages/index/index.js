const { fetchFeatureList } = require("../../utils/featureConfigClient");
const { previewImages } = require("../../utils/previewImage");

Page({
  data: {
    featureList: [],
    homeFeatureList: [],
    filteredFeatureList: [],
    recommendedFeature: null,
    categories: [
      { icon: "🔥", text: "热门" },
      { icon: "🙂", text: "人像" },
      { icon: "🖼", text: "风格化" },
      { icon: "✨", text: "趣味" },
      { icon: "🧭", text: "最新" },
    ],
    activeCategory: 0,
    loadingFeatures: true,
    featureError: "",
    user: null,
    loginError: "",
    showProfileGate: false,
    profileAvatarTempPath: "",
    profileNickName: "",
    profileSaving: false,
    profileError: "",
  },

  categoryMap: {
    0: null,
    1: ["palm", "hair", "profile"],
    2: ["doodle", "soul"],
    3: ["soul"],
    4: null,
  },

  async onLoad() {
    this.loginUser();

    try {
      const featureList = await fetchFeatureList();
      const homeFeatureList = this.createHomeFeatureList(featureList);
      const recommendedFeature =
        homeFeatureList.find((item) => item.type === "palm") || homeFeatureList[0] || null;
      getApp().globalData.featureList = featureList;
      this.setData({
        featureList,
        homeFeatureList,
        filteredFeatureList: homeFeatureList,
        recommendedFeature,
        loadingFeatures: false,
        featureError: "",
      });
    } catch (e) {
      this.setData({
        loadingFeatures: false,
        featureError: "功能列表加载失败",
      });
    }
  },

  async loginUser() {
    try {
      const res = await wx.cloud.callFunction({
        name: "quickstartFunctions",
        data: { type: "login", data: {} },
      });

      if (res.result && res.result.success) {
        const user = res.result.data.user;
        getApp().globalData.user = user;
        this.setData({
          user,
          loginError: "",
          showProfileGate: !user.profileCompleted,
          profileNickName: user.nickName || "",
        });
      } else {
        this.setData({ loginError: res.result?.errMsg || "登录失败" });
      }
    } catch (e) {
      this.setData({ loginError: e.errMsg || "登录失败" });
    }
  },

  createHomeFeatureList(featureList) {
    return (featureList || []).map((feature) => ({
      ...feature,
    }));
  },

  onClickFeature(e) {
    const { url } = e.currentTarget.dataset;
    if (!url) return;

    wx.navigateTo({ url });
  },

  onClickRecommend() {
    const url = this.data.recommendedFeature?.route;
    if (!url) return;
    wx.navigateTo({ url });
  },

  onCategoryTap(e) {
    const index = e.currentTarget.dataset.index;
    const types = this.categoryMap[index];
    const filtered = types
      ? this.data.homeFeatureList.filter((f) => types.includes(f.type))
      : this.data.homeFeatureList;

     this.setData({ activeCategory: index, filteredFeatureList: filtered });
   },

   async onPreviewImageTap(e) {
    const { index } = e.currentTarget.dataset;
    const feature = this.data.filteredFeatureList[index];
    if (!feature || !feature.previewImageHD) return;

    try {
      await previewImages({
        urls: this.data.filteredFeatureList
          .filter((f) => f.previewImageHD)
          .map((f) => f.previewImageHD),
        current: feature.previewImageHD,
      });
    } catch (err) {
      wx.showToast({ title: "预览失败", icon: "none" });
    }
  },

  onChooseAvatar(e) {
    const avatarUrl = e.detail?.avatarUrl || "";
    if (!avatarUrl) {
      this.setData({ profileError: "请选择头像" });
      return;
    }
    this.setData({
      profileAvatarTempPath: avatarUrl,
      profileError: "",
    });
  },

  onNickNameInput(e) {
    this.setData({
      profileNickName: e.detail.value,
      profileError: "",
    });
  },

  async onSaveProfile() {
    const nickName = (this.data.profileNickName || "").trim();
    const avatarPath = this.data.profileAvatarTempPath;

    if (!avatarPath) {
      this.setData({ profileError: "请先选择头像" });
      return;
    }
    if (!nickName) {
      this.setData({ profileError: "请填写昵称" });
      return;
    }

    this.setData({ profileSaving: true, profileError: "" });
    wx.showLoading({ title: "保存中", mask: true });

    try {
      const extMatch = avatarPath.match(/\.(png|jpg|jpeg|webp)$/i);
      const ext = extMatch ? extMatch[1].toLowerCase().replace("jpeg", "jpg") : "jpg";
      const cloudPath = `user-avatars/${Date.now()}-${Math.random().toString(16).slice(2)}.${ext}`;
      const uploadRes = await wx.cloud.uploadFile({
        cloudPath,
        filePath: avatarPath,
      });

      const res = await wx.cloud.callFunction({
        name: "quickstartFunctions",
        data: {
          type: "updateUserProfile",
          data: {
            nickName,
            avatarFileID: uploadRes.fileID,
          },
        },
      });

      if (!res.result || !res.result.success) {
        throw new Error(res.result?.errMsg || "保存失败");
      }

      const user = res.result.data.user;
      getApp().globalData.user = user;
      this.setData({
        user,
        showProfileGate: false,
        profileSaving: false,
        profileError: "",
      });
      wx.showToast({ title: "资料已保存", icon: "success" });
    } catch (err) {
      this.setData({
        profileSaving: false,
        profileError: err.message || err.errMsg || "保存失败",
      });
    } finally {
      wx.hideLoading();
    }
  },
});
