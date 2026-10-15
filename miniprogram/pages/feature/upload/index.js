const { fetchFeature } = require("../../../utils/api/features");
const { createTaskV2 } = require("../../../utils/api/tasks");
const { uploadPhoto } = require("../../../utils/api/upload");
const { buildHomeSharePayload, getShareRewardStatus } = require("../../../utils/share");

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
    submitting: false,
    submittingText: "",
  },
  choosingImage: false,

  goBack() {
    wx.navigateBack({
      fail: () => wx.redirectTo({ url: `/pages/feature/index?type=${this.data.feature?.type || "palm"}` }),
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

    const paramFields = this.getParamFields(feature);
    const ui = feature.ui || {};
    this.setData({
      feature,
      tips: ui.requirements || [],
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
      });
      return status;
    } catch (err) {}
    return this.data.shareRewardStatus;
  },

  async chooseImage() {
    if (this.data.submitting || this.choosingImage || !this.data.feature) return;

    if (!this.validateParams()) return;

    this.choosingImage = true;
    try {
      const status = await this.loadShareRewardStatus();
      if (Number(status?.points || 0) < 1) {
        this.setData({ showPointsModal: true });
        return;
      }
    } finally {
      this.choosingImage = false;
    }

    const isMultiImage = this.isMultiImageFeature(this.data.feature.type);
    wx.chooseMedia({
      count: isMultiImage ? 9 : 1,
      mediaType: ["image"],
      sourceType: ["camera", "album"],
      success: (res) => {
        const tempFilePaths = (res.tempFiles || [])
          .map((item) => item.tempFilePath)
          .filter(Boolean);
        if (!tempFilePaths.length) {
          this.showNoticeModal("图片选择失败", "没有获取到可用图片，请重新选择。");
          return;
        }
        if (isMultiImage && tempFilePaths.length < 2) {
          this.showNoticeModal("图片数量不足", "请至少选择 2 张图片后再开始处理。");
          return;
        }
        this.compressAndUpload(tempFilePaths);
      },
    });
  },

  async compressAndUpload(tempFilePaths) {
    this.setSubmitting(true, "正在上传图片");
    const paths = Array.isArray(tempFilePaths) ? tempFilePaths : [tempFilePaths];
    try {
      const fileIDs = [];
      for (const filePath of paths) {
        const compressedPath = await this.compressImage(filePath);
        fileIDs.push(await this.uploadImage(compressedPath));
      }
      this.setSubmitting(true, "正在创建任务");
      this.createJob(this.isMultiImageFeature(this.data.feature.type) ? fileIDs : fileIDs[0]);
    } catch (err) {
      this.setSubmitting(false);
      this.showNoticeModal("上传失败", err.message || "图片上传失败，请稍后重试。");
    }
  },

  compressImage(filePath) {
    return new Promise((resolve) => {
      wx.compressImage({
        src: filePath,
        quality: 70,
        success: (res) => resolve(res.tempFilePath),
        fail: () => resolve(filePath),
      });
    });
  },

  uploadImage(filePath) {
    return uploadPhoto(filePath);
  },

  createJob(fileIDOrFileIDs) {
    const fileIDs = Array.isArray(fileIDOrFileIDs) ? fileIDOrFileIDs : [fileIDOrFileIDs];
    createTaskV2({
      type: this.data.feature.type,
      fileID: fileIDs[0],
      fileIDs,
      param: this.buildJobParam(),
    })
      .then((data) => {
        this.setSubmitting(false);
        getApp().globalData.shouldRefreshTasks = true;
        wx.redirectTo({
          url: `/pages/feature/progress/index?id=${data.taskId}&type=${this.data.feature.type}`,
        });
      })
      .catch(async (err) => {
        this.setSubmitting(false);
        const errMsg = err.message || "处理失败";
        if (errMsg.includes("积分不足")) {
          await this.loadShareRewardStatus();
          this.setData({ showPointsModal: true });
        } else {
          this.showValidationError(errMsg);
        }
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

  showNoticeModal(title, content) {
    wx.showModal({
      title,
      content,
      confirmText: "知道了",
      showCancel: false,
    });
  },

  hidePointsModal() {
    this.setData({ showPointsModal: false });
  },

  noop() {},

  setSubmitting(submitting, text = "") {
    this.setData({
      submitting,
      submittingText: submitting ? text : "",
    });
  },

  getParamFields(feature) {
    if (feature?.type === "split") {
      return [
        {
          key: "grid",
          label: "切分规格",
          type: "select",
          options: [
            { label: "2 x 2", value: "2x2" },
            { label: "3 x 3", value: "3x3" },
            { label: "1 x 3", value: "1x3" },
            { label: "3 x 1", value: "3x1" },
          ],
        },
      ];
    }
    return this.normalizeParamFields(feature?.param);
  },

  normalizeParamFields(items) {
    if (!Array.isArray(items)) return [];
    return items
      .map((item) => {
        const key = String(item?.value || "").trim();
        const label = String(item?.name || "").trim();
        const rawType = String(item?.type || "text").trim();
        const type = rawType === "select" || rawType === "下拉框" ? "select" : "text";
        if (!key || !label || !/^[a-zA-Z0-9_]{1,32}$/.test(key)) return null;

        const field = {
          key,
          label,
          type,
          placeholder: String(item?.placeholder || `请输入${label}`).trim(),
          maxLength: 40,
        };

        if (type === "select") {
          const data = Array.isArray(item?.data) ? item.data : [];
          const options = data
            .map((value) => String(value || "").trim())
            .filter(Boolean)
            .map((value) => ({ label: value, value }));
          if (!options.length) return null;
          field.options = options;
        }

        return field;
      })
      .filter(Boolean);
  },

  isMultiImageFeature(type) {
    return type === "long_image";
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
    const missingField = fields.find((field) => !String(values[field.key] || "").trim());

    if (missingField) {
      this.showNoticeModal("参数未填写", `请填写${missingField.label}`);
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
    return buildHomeSharePayload();
  },
});
