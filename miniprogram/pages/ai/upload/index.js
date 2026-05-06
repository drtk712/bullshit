const { fetchFeature } = require("../../../utils/featureConfigClient");

const TIPS = {
  palm: ["手掌完整，五指张开", "光线充足，清晰无反光", "避免佩戴饰品遮挡纹路"],
  hair: ["正面露脸，脸部无遮挡", "光线均匀，发型轮廓清楚", "背景简洁，避免多人同框"],
  profile: ["正面肖像，五官清晰", "表情自然，无遮挡", "背景简洁，主体突出"],
  doodle: ["主体清晰，构图完整", "光线明亮，避免严重模糊", "适合生活照或旅行照"],
  soul: ["人物或主体清楚", "画面信息不要过于复杂", "越有表情越有趣"],
};

Page({
  data: {
    feature: null,
    configLoading: true,
    configError: "",
    tips: [],
    points: 0,
    showPointsModal: false,
  },

  goBack() {
    wx.navigateBack({
      fail: () => wx.redirectTo({ url: `/pages/ai/index?type=${this.data.feature?.type || "palm"}` }),
    });
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

    wx.setNavigationBarTitle({ title: "上传照片" });
    this.setData({
      feature,
      tips: TIPS[feature.type] || TIPS.doodle,
      configLoading: false,
      configError: "",
    });
    this.loadPoints();
  },

  getFeatureFromCache(type) {
    const list = getApp().globalData.featureList;
    if (!Array.isArray(list)) return null;
    return list.find((f) => f.type === type) || null;
  },

  async loadPoints() {
    try {
      const res = await wx.cloud.callFunction({
        name: "quickstartFunctions",
        data: { type: "getUserProfile", data: {} },
      });
      if (res.result?.success) {
        this.setData({ points: res.result.data.user?.points || 0 });
      }
    } catch (err) {}
  },

  chooseImage() {
    if (!this.data.feature) return;

    wx.chooseMedia({
      count: 1,
      mediaType: ["image"],
      sourceType: ["camera", "album"],
      success: (res) => {
        const tempFilePath = res.tempFiles?.[0]?.tempFilePath;
        if (!tempFilePath) {
          wx.showToast({ title: "图片选择失败", icon: "none" });
          return;
        }
        this.compressAndUpload(tempFilePath);
      },
    });
  },

  compressAndUpload(tempFilePath) {
    wx.showLoading({ title: "处理图片" });
    wx.compressImage({
      src: tempFilePath,
      quality: 70,
      success: (res) => this.uploadAndCreateJob(res.tempFilePath),
      fail: () => this.uploadAndCreateJob(tempFilePath),
    });
  },

  uploadAndCreateJob(filePath) {
    const cloudPath = `ai-upload/${Date.now()}-${Math.random().toString(36).slice(2, 8)}.jpg`;

    wx.cloud.uploadFile({
      cloudPath,
      filePath,
      success: (res) => this.createJob(res.fileID),
      fail: () => {
        wx.hideLoading();
        wx.showToast({ title: "上传失败", icon: "none" });
      },
    });
  },

  createJob(fileID) {
    const g = getApp().globalData;
    wx.cloud.callFunction({
      name: "quickstartFunctions",
      data: {
        type: "validateAndCreateJob",
        data: {
          type: this.data.feature.type,
          fileID,
          test: !!g.testMode,
          skipPointsDeduction: !!g.skipPointsDeduction,
        },
      },
      success: (resp) => {
        wx.hideLoading();
        if (resp.result?.success) {
          wx.redirectTo({
            url: `/pages/ai/progress/index?id=${resp.result.data.taskId}&type=${this.data.feature.type}`,
          });
          return;
        }

        const errMsg = resp.result?.errMsg || "生成失败";
        if (errMsg.includes("积分不足")) {
          this.setData({ showPointsModal: true });
        } else {
          wx.showToast({ title: errMsg, icon: "none" });
        }
      },
      fail: () => {
        wx.hideLoading();
        wx.showToast({ title: "网络错误", icon: "none" });
      },
    });
  },

  hidePointsModal() {
    this.setData({ showPointsModal: false });
  },

  onShareAppMessage() {
    this.handleShareEarnPoints();
    return {
      title: "玩图局 - 选个玩法，生成你的专属趣味图",
      path: "/pages/index/index",
    };
  },

  async handleShareEarnPoints() {
    try {
      const res = await wx.cloud.callFunction({
        name: "quickstartFunctions",
        data: { type: "shareEarnPoints", data: {} },
      });
      if (res.result?.success) {
        wx.showToast({ title: "+1 积分", icon: "success" });
        this.loadPoints();
      }
    } catch (err) {}
  },
});
