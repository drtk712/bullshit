const { fetchFeatureList } = require("../../utils/featureConfigClient");
const { previewImages } = require("../../utils/previewImage");

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

  onPreviewImageLoad(e) {
    const { index } = e.currentTarget.dataset;
    const key = `featureList[${index}]._imageLoaded`;
    this.setData({ [key]: true });
  },

  onPreviewImageError(e) {
    const { index } = e.currentTarget.dataset;
    const key = `featureList[${index}]._imageError`;
    this.setData({ [key]: true });
  },

  async onPreviewImageTap(e) {
    const { index } = e.currentTarget.dataset;
    const feature = this.data.featureList[index];
    if (!feature || !feature.previewImageHD) return;

    try {
      await previewImages({
        urls: this.data.featureList
          .filter((f) => f.previewImageHD)
          .map((f) => f.previewImageHD),
        current: feature.previewImageHD,
      });
    } catch (err) {
      wx.showToast({ title: "预览失败", icon: "none" });
    }
  },
});
