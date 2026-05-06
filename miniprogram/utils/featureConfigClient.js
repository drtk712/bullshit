const FALLBACK_FEATURES = [
  {
    type: "palm",
    title: "看手相",
    shortTitle: "看手相",
    description: "上传清晰手掌照片，生成趣味手相解读海报",
    icon: "🖐️",
    previewImageHD: "cloud://cloud1-d7g1nt83fde793ad3.636c-cloud1-d7g1nt83fde793ad3-1427592986/ai-preview-image/手相.png",
    uploadIcon: "📷",
    uploadTitle: "上传手掌照片",
    uploadTip: "请确保手掌完整、纹路清晰、光线充足",
    retryText: "重新上传",
    route: "/pages/ai/index?type=palm",
    ui: {
      reportTitle: "你的手相解读报告",
      progressTitle: "正在分析手掌特征",
      requirements: ["手掌完整，五指张开", "光线充足，清晰无反光", "背景干净，避免杂物遮挡"],
      analysisItems: [
        { title: "智慧线", items: ["思维敏捷", "学习潜力强"] },
        { title: "感情线", items: ["重视情绪"] },
        { title: "生命线", items: ["活力充沛"] },
      ],
      progressChecks: [
        { title: "图像清晰度检测", status: "完成" },
        { title: "手相结构识别", status: "完成" },
        { title: "纹理特征分析", status: "progress" },
        { title: "生成解读报告", status: "等待中" },
      ],
    },
  },
  {
    type: "hair",
    title: "设计发型",
    shortTitle: "设计发型",
    description: "上传正面照片，生成适合你的发型建议海报",
    icon: "💇",
    previewImageHD: "cloud://cloud1-d7g1nt83fde793ad3.636c-cloud1-d7g1nt83fde793ad3-1427592986/ai-preview-image/hair.png",
    uploadIcon: "📷",
    uploadTitle: "上传正面照片",
    uploadTip: "请确保脸部正面清晰、无遮挡、光线充足",
    retryText: "重新上传",
    route: "/pages/ai/index?type=hair",
    ui: {
      reportTitle: "你的发型分析报告",
      progressTitle: "正在分析脸型特征",
      requirements: ["正面露脸，脸部无遮挡", "光线均匀，发型轮廓清楚", "尽量使用近期照片"],
      analysisItems: [
        { title: "脸型分析", items: ["轮廓立体", "比例协调"] },
        { title: "发质评估", items: ["柔顺度佳"] },
        { title: "风格匹配", items: ["气质契合"] },
      ],
      progressChecks: [
        { title: "图像清晰度检测", status: "完成" },
        { title: "脸型轮廓识别", status: "完成" },
        { title: "发质特征分析", status: "progress" },
        { title: "生成发型报告", status: "等待中" },
      ],
    },
  },
  {
    type: "profile",
    title: "个人形象分析",
    shortTitle: "形象分析",
    description: "上传正面肖像照，生成专属个人形象分析图卡",
    icon: "✨",
    previewImageHD: "cloud://cloud1-d7g1nt83fde793ad3.636c-cloud1-d7g1nt83fde793ad3-1427592986/ai-preview-image/个人形象分析.png",
    uploadIcon: "📷",
    uploadTitle: "上传正面肖像照",
    uploadTip: "请确保脸部正面清晰、无遮挡、光线充足",
    retryText: "重新上传",
    route: "/pages/ai/index?type=profile",
    ui: {
      reportTitle: "你的形象分析报告",
      progressTitle: "正在分析形象特征",
      requirements: ["正面肖像，五官清晰", "表情自然，无遮挡", "背景简洁，主体突出"],
      analysisItems: [
        { title: "五官分析", items: ["比例协调", "气质独特"] },
        { title: "肤色评估", items: ["色调均匀"] },
        { title: "风格定位", items: ["专业干练"] },
      ],
      progressChecks: [
        { title: "图像清晰度检测", status: "完成" },
        { title: "五官特征识别", status: "完成" },
        { title: "肤色气质分析", status: "progress" },
        { title: "生成形象报告", status: "等待中" },
      ],
    },
  },
  {
    type: "doodle",
    title: "INS手绘风照片",
    shortTitle: "手绘照片",
    description: "上传照片，生成手绘风注解照片",
    icon: "✏️",
    previewImageHD: "cloud://cloud1-d7g1nt83fde793ad3.636c-cloud1-d7g1nt83fde793ad3-1427592986/ai-preview-image/INS手绘风.png",
    uploadIcon: "📷",
    uploadTitle: "上传照片",
    uploadTip: "请确保照片清晰、光线充足",
    retryText: "重新上传",
    route: "/pages/ai/index?type=doodle",
    ui: {
      reportTitle: "你的手绘风报告",
      progressTitle: "正在分析画面构图",
      requirements: ["主体清晰，构图完整", "光线明亮，避免严重模糊", "适合生活照或旅行照"],
      analysisItems: [
        { title: "构图分析", items: ["层次分明", "主体突出"] },
        { title: "色彩评估", items: ["色调和谐"] },
        { title: "氛围感知", items: ["温馨自然"] },
      ],
      progressChecks: [
        { title: "图像清晰度检测", status: "完成" },
        { title: "主体构图分析", status: "完成" },
        { title: "色彩风格分析", status: "progress" },
        { title: "生成手绘注解", status: "等待中" },
      ],
    },
  },
  {
    type: "soul",
    title: "灵魂画手",
    shortTitle: "灵魂画手",
    description: "上传照片，生成魔性灵魂画风",
    icon: "🎨",
    previewImageHD: "cloud://cloud1-d7g1nt83fde793ad3.636c-cloud1-d7g1nt83fde793ad3-1427592986/ai-preview-image/灵魂画手.png",
    uploadIcon: "📷",
    uploadTitle: "上传照片",
    uploadTip: "请确保照片清晰",
    retryText: "重新上传",
    route: "/pages/ai/index?type=soul",
    ui: {
      reportTitle: "你的灵魂画作报告",
      progressTitle: "正在分析画面内容",
      requirements: ["人物或主体清楚", "画面信息不要过于复杂", "越有表情越有趣"],
      analysisItems: [
        { title: "主体识别", items: ["表情生动", "趣味十足"] },
        { title: "画面氛围", items: ["轻松愉快"] },
        { title: "创意指数", items: ["想象力丰富"] },
      ],
      progressChecks: [
        { title: "图像清晰度检测", status: "完成" },
        { title: "主体内容识别", status: "完成" },
        { title: "趣味元素提取", status: "progress" },
        { title: "生成灵魂画作", status: "等待中" },
      ],
    },
  },
];

async function fetchFeatureList() {
  try {
    const resp = await wx.cloud.callFunction({
      name: "quickstartFunctions",
      data: { type: "getFeatureConfig", data: {} },
    });

    if (resp.result?.success && Array.isArray(resp.result.data?.features)) {
      return resp.result.data.features;
    }
  } catch (e) {
    console.debug("[featureConfigClient] fetchFeatureList failed, using fallback:", e);
  }

  return FALLBACK_FEATURES;
}

async function fetchFeature(type) {
  try {
    const resp = await wx.cloud.callFunction({
      name: "quickstartFunctions",
      data: { type: "getFeatureConfig", data: { type } },
    });

    if (resp.result?.success && resp.result.data?.feature) {
      return resp.result.data.feature;
    }
  } catch (e) {
    console.debug("[featureConfigClient] fetchFeature failed for type=\"" + type + "\", using fallback:", e);
  }

  return FALLBACK_FEATURES.find((feature) => feature.type === type) || null;
}

module.exports = {
  fetchFeatureList,
  fetchFeature,
};
