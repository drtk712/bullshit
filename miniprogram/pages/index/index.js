const { fetchFeatureList } = require("../../utils/api/features");
const { fetchMe } = require("../../utils/api/user");
const { previewImages } = require("../../utils/previewImage");
const { buildHomeSharePayload } = require("../../utils/share");

Page({
  data: {
    featureList: [],
    homeFeatureList: [],
    filteredFeatureList: [],
    recommendedFeature: null,
    categories: [
      { key: "all", icon: "🔥", text: "热门" },
      { key: "人像", icon: "🙂", text: "人像" },
      { key: "风格化", icon: "🖼", text: "风格化" },
      { key: "趣味", icon: "✨", text: "趣味" },
      { key: "创意", icon: "💡", text: "创意" },
      { key: "工具", icon: "🛠", text: "工具" },
      { key: "营销", icon: "📣", text: "营销" },
    ],
    activeCategory: "all",
    loadingFeatures: true,
    refreshing: false,
    refreshDoneVisible: false,
    featureError: "",
    user: null,
    loginError: "",
  },

  async onLoad() {
    this.loginUser();
    this.loadFeatures();
  },

  async loadFeatures(options = {}) {
    const { refreshing = false } = options;
    if (!refreshing) {
      this.setData({ loadingFeatures: true, featureError: "" });
    }
    try {
      const featureList = await fetchFeatureList();
      const homeFeatureList = this.createHomeFeatureList(featureList);
      const recommendedFeature =
        homeFeatureList.find((item) => item.type === "doodle") || homeFeatureList[0] || null;
      const filteredFeatureList = this.filterFeatureList(homeFeatureList, this.data.activeCategory);
      getApp().globalData.featureList = featureList;
      this.setData({
        featureList,
        homeFeatureList,
        filteredFeatureList,
        recommendedFeature,
        loadingFeatures: false,
        refreshing: false,
        featureError: "",
      });
      if (refreshing) {
        this.showRefreshDone();
      }
    } catch (e) {
      this.setData({
        loadingFeatures: false,
        refreshing: false,
        featureError: "功能列表加载失败",
      });
    } finally {
      if (refreshing) {
        wx.stopPullDownRefresh();
      }
    }
  },

  async loginUser() {
    try {
      const { user } = await fetchMe({ recordLogin: true });
      getApp().globalData.user = user;
      this.setData({
        user,
        loginError: "",
      });
    } catch (e) {
      this.setData({ loginError: e.errMsg || "登录失败" });
    }
  },

  createHomeFeatureList(featureList) {
    return (featureList || []).map((feature) => ({
      ...feature,
      category: feature.category || "其他",
    }));
  },

  filterFeatureList(featureList, category) {
    return category === "all"
      ? featureList
      : featureList.filter((feature) => (feature.category || "其他") === category);
  },

  buildFeatureRoute(type) {
    return type ? `/pages/feature/index?type=${type}` : "";
  },

  onClickFeature(e) {
    const url = this.buildFeatureRoute(e.currentTarget.dataset.type);
    if (!url) return;

    wx.navigateTo({ url });
  },

  onClickRecommend() {
    const url = this.buildFeatureRoute(this.data.recommendedFeature?.type);
    if (!url) return;
    wx.navigateTo({ url });
  },

  onCategoryTap(e) {
    const category = e.currentTarget.dataset.category || "all";
    const filtered = this.filterFeatureList(this.data.homeFeatureList, category);

     this.setData({ activeCategory: category, filteredFeatureList: filtered });
   },

  onPullDownRefresh() {
    if (this.data.refreshing) return;
    this.setData({ refreshing: true });
    this.loadFeatures({ refreshing: true });
  },

  showRefreshDone() {
    if (this.refreshDoneTimer) {
      clearTimeout(this.refreshDoneTimer);
    }
    this.setData({ refreshDoneVisible: true });
    this.refreshDoneTimer = setTimeout(() => {
      this.setData({ refreshDoneVisible: false });
      this.refreshDoneTimer = null;
    }, 1400);
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

  onShareAppMessage() {
    return buildHomeSharePayload();
  },

});
