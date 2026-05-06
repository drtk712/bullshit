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
        this.setData({ user: res.result.data.user, loginError: "" });
      } else {
        this.setData({ loginError: res.result?.errMsg || "登录失败" });
      }
    } catch (e) {
      this.setData({ loginError: e.errMsg || "登录失败" });
    }
  },

  createHomeFeatureList(featureList) {
    const displayMap = {
      palm: { homeDesc: "趣味解读运势", badgeIcon: "✋" },
      hair: { homeDesc: "挑发型看新印象", badgeIcon: "👩" },
      profile: { homeDesc: "生成专属形象", badgeIcon: "👩‍🦰" },
      doodle: { homeDesc: "手绘风标注照", badgeIcon: "🖼" },
      soul: { homeDesc: "让人忍不住看", badgeIcon: "🖌" },
    };

    return (featureList || []).map((feature) => ({
      ...feature,
      ...(displayMap[feature.type] || {
        homeDesc: feature.description,
        badgeIcon: feature.icon,
      }),
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
});
