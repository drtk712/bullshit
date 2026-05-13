const { fetchFeature } = require("../../../utils/api/features");
const { createTask } = require("../../../utils/api/tasks");
const { buildHomeSharePayload, getShareRewardStatus } = require("../../../utils/share");

const SUBMIT_PROGRESS = {
  initial: 8,
  maxBeforeDone: 94,
  stepStart: 28,
  stepEnd: 94,
  interval: 650,
  increments: [
    { below: 60, value: 8 },
    { below: 86, value: 3 },
    { below: 94, value: 1 },
  ],
};

const BASE_SUBMIT_STEPS = [
  "检查图片是否存在违规内容",
  "创建图片处理任务",
];

Page({
  data: {
    feature: null,
    configLoading: true,
    configError: "",
    tips: [],
    requirementItems: [],
    paramFields: [],
    paramValues: {},
    points: 0,
    showPointsModal: false,
    shareRewardStatus: { remainingToday: 0 },
    submitting: false,
    submittingText: "",
    submitProgress: 0,
    submitSteps: [],
  },
  submitProgressTimer: null,
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

    const paramFields = this.getParamFields(feature.type);
    const ui = feature.ui || {};
    this.setData({
      feature,
      tips: ui.requirements || [],
      requirementItems: this.normalizeRequirementItems(ui.requirementItems),
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
    this.startSubmitFlow();
    const paths = Array.isArray(tempFilePaths) ? tempFilePaths : [tempFilePaths];
    try {
      const fileIDs = [];
      for (const filePath of paths) {
        const compressedPath = await this.compressImage(filePath);
        fileIDs.push(await this.uploadImage(compressedPath));
      }
      this.createJob(this.isMultiImageFeature(this.data.feature.type) ? fileIDs : fileIDs[0]);
    } catch (err) {
      this.stopSubmitFlow();
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
    const cloudPath = `feature-upload/${Date.now()}-${Math.random().toString(36).slice(2, 8)}.jpg`;
    return new Promise((resolve, reject) => {
      wx.cloud.uploadFile({
        cloudPath,
        filePath,
        success: (res) => resolve(res.fileID),
        fail: () => reject(new Error("上传失败")),
      });
    });
  },

  createJob(fileIDOrFileIDs) {
    const fileIDs = Array.isArray(fileIDOrFileIDs) ? fileIDOrFileIDs : [fileIDOrFileIDs];
    createTask({
      type: this.data.feature.type,
      fileID: fileIDs[0],
      fileIDs,
      param: this.buildJobParam(),
    })
      .then((data) => {
        this.finishSubmitFlow();
        getApp().globalData.shouldRefreshTasks = true;
        wx.redirectTo({
          url: `/pages/feature/progress/index?id=${data.taskId}&type=${this.data.feature.type}`,
        });
      })
      .catch(async (err) => {
        this.stopSubmitFlow();
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

  startSubmitFlow() {
    const progress = SUBMIT_PROGRESS.initial;
    const submitSteps = this.buildSubmitSteps(progress);
    this.stopSubmitProgress();
    this.setData({
      submitting: true,
      submittingText: this.getCurrentSubmitStepText(submitSteps),
      submitProgress: progress,
      submitSteps,
    });
    this.startSubmitProgress();
  },

  finishSubmitFlow() {
    this.stopSubmitFlow();
  },

  stopSubmitFlow() {
    this.stopSubmitProgress();
    this.setData({
      submitting: false,
      submittingText: "",
      submitProgress: 0,
      submitSteps: this.buildSubmitSteps(0),
    });
  },

  startSubmitProgress() {
    if (this.submitProgressTimer) return;
    this.submitProgressTimer = setInterval(() => {
      if (!this.data.submitting) {
        this.stopSubmitProgress();
        return;
      }
      const current = Number(this.data.submitProgress || 0);
      const increment = SUBMIT_PROGRESS.increments.find((item) => current < item.below)?.value || 0;
      const next = increment ? current + increment : current;
      if (next !== current) {
        this.syncSubmitProgress(next);
      }
    }, SUBMIT_PROGRESS.interval);
  },

  stopSubmitProgress() {
    if (this.submitProgressTimer) {
      clearInterval(this.submitProgressTimer);
      this.submitProgressTimer = null;
    }
  },

  syncSubmitProgress(progress) {
    const next = Math.max(
      Number(this.data.submitProgress || 0),
      Math.min(SUBMIT_PROGRESS.maxBeforeDone, Number(progress || 0))
    );
    const submitSteps = this.buildSubmitSteps(next);
    this.setData({
      submitProgress: next,
      submittingText: this.getCurrentSubmitStepText(submitSteps),
      submitSteps,
    });
  },

  getCurrentSubmitStepText(steps) {
    const current = (steps || []).find((step) => !step.done);
    return current?.text || "校验完成";
  },

  getRequirementCheckSteps() {
    const items = this.data.requirementItems || [];
    return items.length
      ? items.map((item) => `检查：${item.text}`)
      : ["检查图片是否符合要求"];
  },

  buildSubmitSteps(progress) {
    const stepTexts = this.buildSubmitStepTexts();
    const thresholds = this.buildStepThresholds(stepTexts.length);
    const steps = stepTexts.map((text, index) => ({ text, threshold: thresholds[index] }));
    return steps.map((step) => ({
      text: step.text,
      done: Number(progress || 0) >= step.threshold,
    }));
  },

  buildSubmitStepTexts() {
    return [
      ...this.getRequirementCheckSteps(),
      ...BASE_SUBMIT_STEPS,
    ];
  },

  buildStepThresholds(count) {
    if (count <= 1) return [SUBMIT_PROGRESS.stepEnd];
    const start = SUBMIT_PROGRESS.stepStart;
    const end = SUBMIT_PROGRESS.stepEnd;
    const gap = (end - start) / (count - 1);
    return Array.from({ length: count }, (_, index) => Math.round(start + gap * index));
  },

  onUnload() {
    this.stopSubmitProgress();
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
      split: [
        {
          key: "grid",
          label: "切分规格",
          type: "select",
          required: true,
          options: [
            { label: "2 x 2", value: "2x2" },
            { label: "3 x 3", value: "3x3" },
            { label: "1 x 3", value: "1x3" },
            { label: "3 x 1", value: "3x1" },
          ],
        },
      ],
    };

    return fieldMap[type] || [];
  },

  normalizeRequirementItems(items) {
    if (!Array.isArray(items)) return [];
    return items
      .map((item) => {
        if (typeof item === "string") return { text: item.trim() };
        return { text: String(item?.text || item?.title || "").trim() };
      })
      .filter((item) => item.text);
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
    const missingField = fields.find((field) => field.required && !String(values[field.key] || "").trim());

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
