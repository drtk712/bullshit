const { fetchFeature } = require("../../utils/api/features");
const { previewImages } = require("../../utils/previewImage");
const { buildHomeSharePayload } = require("../../utils/share");

Page({
  data: {
    feature: null,
    configLoading: true,
    configError: "",
    requirements: [],
    requirementItems: [],
    analysisItems: [],
    detailAnalysis: [],
    detailSubtitle: "",
    detailTags: [],
  },

  async onLoad(options) {
    const type = options.type;
    if (!type) {
      this.setData({ configLoading: false, configError: "缺少功能类型" });
      return;
    }

    let feature;
    try {
      feature = this.getFeatureFromCache(type) || await fetchFeature(type);
    } catch (err) {
      this.setData({ configLoading: false, configError: err.message || "功能暂不可用" });
      return;
    }

    if (!feature) {
      this.setData({ configLoading: false, configError: "功能暂不可用" });
      return;
    }

    const ui = feature.ui || {};
    this.setData({
      feature,
      requirements: ui.requirements || [],
      requirementItems: this.buildRequirementItems(ui),
      analysisItems: ui.analysisItems || [],
      detailAnalysis: this.buildDetailAnalysis(ui.analysisItems || []),
      detailSubtitle: ui.detailSubtitle || "",
      detailTags: this.buildDetailTags(ui.tags || []),
      configLoading: false,
      configError: "",
    });
  },

  getFeatureFromCache(type) {
    const list = getApp().globalData.featureList;
    if (!Array.isArray(list)) return null;
    return list.find((f) => f.type === type) || null;
  },

  startUpload() {
    const type = this.data.feature?.type;
    if (!type) return;
    wx.navigateTo({ url: `/pages/feature/upload/index?type=${type}` });
  },

  buildDetailAnalysis(items) {
    const tones = ["green", "yellow", "coral"];

    return (items || []).map((source, index) => {
      const sourceItems = Array.isArray(source.items) ? source.items : [];
      return {
        title: source.title || "",
        desc: sourceItems[0] || "",
        tone: tones[index % tones.length],
      };
    }).filter((item) => item.title || item.desc);
  },

  buildDetailTags(tags) {
    const normalized = (tags || [])
      .map((tag) => {
        if (typeof tag === "string") return { text: tag };
        return {
          text: tag.text || tag.title || "",
        };
      })
      .filter((tag) => tag.text);

    return normalized;
  },

  buildRequirementItems(ui = {}) {
    if (Array.isArray(ui.requirementItems) && ui.requirementItems.length > 0) {
      return ui.requirementItems
        .map((item) => ({
          text: item.text || item.title || "",
        }))
        .filter((item) => item.text);
    }

    return [];
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

  onShareAppMessage() {
    const feature = this.data.feature || {};
    const type = feature.type || this.data.type || "";
    return buildHomeSharePayload({
      title: feature.title ? `玩图局 - ${feature.title}` : "玩图局 - 实用图片处理工具",
      path: type ? `/pages/feature/index?type=${type}` : "/pages/index/index",
    });
  },
});
