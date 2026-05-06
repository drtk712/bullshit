const { fetchFeature } = require("../../utils/featureConfigClient");
const { previewImages } = require("../../utils/previewImage");

Page({
  data: {
    feature: null,
    configLoading: true,
    configError: "",
    requirements: [],
    analysisItems: [],
    reportTitle: "",
  },

  async onLoad(options) {
    const type = options.type;
    if (!type) {
      this.setData({ configLoading: false, configError: "缺少功能类型" });
      return;
    }

    const feature = this.getFeatureFromCache(type) || await fetchFeature(type);
    if (!feature) {
      this.setData({ configLoading: false, configError: "功能暂不可用" });
      return;
    }

    const ui = feature.ui || {};
    this.setData({
      feature,
      requirements: ui.requirements || [],
      analysisItems: ui.analysisItems || [],
      reportTitle: ui.reportTitle || "",
      configLoading: false,
      configError: "",
    });
    wx.setNavigationBarTitle({ title: feature.title });
  },

  getFeatureFromCache(type) {
    const list = getApp().globalData.featureList;
    if (!Array.isArray(list)) return null;
    return list.find((f) => f.type === type) || null;
  },

  startUpload() {
    const type = this.data.feature?.type;
    if (!type) return;
    wx.navigateTo({ url: `/pages/ai/upload/index?type=${type}` });
  },

  goBack() {
    wx.navigateBack({
      fail: () => wx.switchTab({ url: "/pages/index/index" }),
    });
  },

  noop() {},

  async previewFeatureImage() {
    if (!this.data.feature?.previewImageHD) return;

    try {
      await previewImages({
        urls: [this.data.feature.previewImageHD],
        current: this.data.feature.previewImageHD,
      });
    } catch (err) {
      wx.showToast({ title: "预览失败", icon: "none" });
    }
  },

  onFeatureImageLoad() {
    this.setData({ "feature._imageLoaded": true });
  },

  onFeatureImageError() {
    this.setData({ "feature._imageError": true });
  },
});
