const { fetchFeature } = require("../../../utils/featureConfigClient");
const {
  buildShareRewardCopy,
  canClaimShareReward,
  claimShareReward,
  getShareRewardStatus,
} = require("../../../utils/shareReward");

Page({
  data: {
    feature: null,
    configLoading: true,
    configError: "",
    tips: [],
    paramFields: [],
    paramValues: {},
    points: 0,
    showPointsModal: false,
    shareRewardStatus: { remainingToday: 0 },
    shareRewardCopy: buildShareRewardCopy(),
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

    wx.setNavigationBarTitle({ title: "上传照片" });
    const paramFields = this.getParamFields(feature.type);
    this.setData({
      feature,
      tips: feature.ui?.requirements || [],
      paramFields,
      paramValues: this.getDefaultParamValues(paramFields),
      configLoading: false,
      configError: "",
    });
    this.loadShareRewardStatus();
  },

  getFeatureFromCache(type) {
    const list = getApp().globalData.featureList;
    if (!Array.isArray(list)) return null;
    return list.find((f) => f.type === type) || null;
  },

  async loadShareRewardStatus() {
    try {
      const status = await getShareRewardStatus();
      this.setData({
        points: status.points,
        shareRewardStatus: status,
        shareRewardCopy: buildShareRewardCopy(status),
      });
      return status;
    } catch (err) {}
    return this.data.shareRewardStatus;
  },

  async chooseImage() {
    if (!this.data.feature) return;

    if (!this.validateParams()) return;

    const status = await this.loadShareRewardStatus();
    if (Number(status?.points || 0) < 1) {
      this.setData({ showPointsModal: true });
      return;
    }

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
    wx.showLoading({ title: "校验图片" });
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
    wx.cloud.callFunction({
      name: "quickstartFunctions",
      data: {
        type: "validateAndCreateJob",
        data: {
          type: this.data.feature.type,
          fileID,
          param: this.buildJobParam(),
        },
      },
      success: async (resp) => {
        wx.hideLoading();
        if (resp.result?.success) {
          getApp().globalData.shouldRefreshTasks = true;
          wx.redirectTo({
            url: `/pages/ai/progress/index?id=${resp.result.data.taskId}&type=${this.data.feature.type}`,
          });
          return;
        }

        const errMsg = resp.result?.errMsg || "生成失败";
        if (errMsg.includes("积分不足")) {
          await this.loadShareRewardStatus();
          this.setData({ showPointsModal: true });
        } else {
          this.showValidationError(errMsg);
        }
      },
      fail: () => {
        wx.hideLoading();
        wx.showToast({ title: "网络错误", icon: "none" });
      },
    });
  },

  showValidationError(message) {
    wx.showModal({
      title: "图片不符合要求",
      content: message || "请重新上传符合要求的图片",
      confirmText: "重新上传",
      showCancel: false,
    });
  },

  hidePointsModal() {
    this.setData({ showPointsModal: false });
  },

  getParamFields(type) {
    const fieldMap = {
      watermark: [
        {
          key: "param",
          label: "水印文字",
          placeholder: "请输入要添加的水印内容",
          required: true,
          maxLength: 40,
        },
      ],
      filter: [
        {
          key: "param",
          label: "滤镜风格",
          type: "select",
          required: true,
          options: [
            { label: "复古胶片", value: "复古胶片" },
            { label: "清新日系", value: "清新日系" },
            { label: "黑白高反差", value: "黑白高反差" },
            { label: "暖阳柔光", value: "暖阳柔光" },
            { label: "冷调电影感", value: "冷调电影感" },
            { label: "高饱和鲜艳", value: "高饱和鲜艳" },
          ],
        },
      ],
    };

    return fieldMap[type] || [];
  },

  getDefaultParamValues(fields) {
    return (fields || []).reduce((acc, field) => {
      if (field.type === "select" && Array.isArray(field.options) && field.options.length > 0) {
        acc[field.key] = field.options[0].value;
      }
      return acc;
    }, {});
  },

  onParamInput(e) {
    const key = e.currentTarget.dataset.key;
    if (!key) return;
    this.setData({
      [`paramValues.${key}`]: e.detail.value,
    });
  },

  onParamSelect(e) {
    const key = e.currentTarget.dataset.key;
    const fieldIndex = Number(e.currentTarget.dataset.index || 0);
    const optionIndex = Number(e.detail.value || 0);
    const field = this.data.paramFields[fieldIndex];
    const option = field?.options?.[optionIndex];
    if (!key || !option) return;

    this.setData({
      [`paramValues.${key}`]: option.value,
    });
  },

  validateParams() {
    const fields = this.data.paramFields || [];
    const values = this.data.paramValues || {};
    const missingField = fields.find((field) => field.required && !String(values[field.key] || "").trim());

    if (missingField) {
      wx.showToast({ title: `请填写${missingField.label}`, icon: "none" });
      return false;
    }

    return true;
  },

  buildJobParam() {
    const values = this.data.paramValues || {};
    const param = {};

    (this.data.paramFields || []).forEach((field) => {
      param[field.key] = String(values[field.key] || "").trim();
    });

    return param;
  },

  onShareAppMessage() {
    this.handleShareEarnPoints();
    return {
      title: "玩图局 - 选个玩法，生成你的专属趣味图",
      path: "/pages/index/index",
    };
  },

  async handleShareEarnPoints() {
    if (!canClaimShareReward(this.data.shareRewardStatus)) return;

    try {
      const res = await claimShareReward();
      if (res.status) {
        this.setData({
          shareRewardStatus: res.status,
          shareRewardCopy: buildShareRewardCopy(res.status),
        });
      }
      if (res.success) {
        this.setData({ points: res.status.points });
      }
    } catch (err) {}
  },
});
