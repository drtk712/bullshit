const { fetchFeatureList } = require("../../utils/featureConfigClient");

Page({
  data: {
    featureList: [],
    loadingFeatures: true,
    featureError: "",
    user: null,
    loginError: "",
  },

  async onLoad() {
    this.loginUser();

    try {
      const featureList = await fetchFeatureList();
      getApp().globalData.featureList = featureList;
      this.setData({
        featureList,
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

  onClickFeature(e) {
    const { url } = e.currentTarget.dataset;
    if (!url) return;

    wx.navigateTo({ url });
  },
});
