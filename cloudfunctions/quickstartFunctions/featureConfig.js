/**
 * Test poster cloud file ID.
 * Environment-specific: must be uploaded to the target cloud environment.
 * Configure via TEST_POSTER_FILE_ID env var, or use the default below.
 */
const DEFAULT_TEST_POSTER_FILE_ID =
  "cloud://cloud1-d7g1nt83fde793ad3.636c-cloud1-d7g1nt83fde793ad3-1427592986/ai-posters/0274fd6869f6176c00082cfb0eeefd94.png";

const TEST_POSTER_FILE_ID =
  process.env.TEST_POSTER_FILE_ID || DEFAULT_TEST_POSTER_FILE_ID;

const FEATURE_CONFIGS = {
  palm: {
    type: "palm",
    enabled: true,
    order: 10,
    public: {
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
    },
    validation: {
      serviceUrl:
        process.env.VALIDATION_SERVICE_URL ||
        "http://36.156.154.98:8010/v1/chat/completions",
      model: process.env.VALIDATION_MODEL || "qwen3.6",
      prompt: "这张图片是否包含清晰的手掌照片？请只回答'是'或'否'。",
      failMessage: "图片不符合要求，请重新拍摄清晰手掌照片",
    },
    generation: {
      prompt: `Based on this palm photo, generate a beautiful palmistry analysis poster in Chinese.
Style: minimalist line art, elegant typography, warm beige background.
Include: a traced palm outline with labeled lines (生命线/智慧线/感情线/事业线), personality traits section, career compatibility section, emotional characteristics section.
Text should be in Chinese. Format: vertical poster, clean layout, professional look.`,
    },
    test: {
      posterFileID: TEST_POSTER_FILE_ID,
    },
  },
  hair: {
    type: "hair",
    enabled: true,
    order: 20,
    public: {
      title: "设计发型",
      shortTitle: "设计发型",
      description: "上传正面照片，生成适合你的发型建议海报",
      icon: "💇",
      previewImageHD: "cloud://cloud1-d7g1nt83fde793ad3.636c-cloud1-d7g1nt83fde793ad3-1427592986/ai-preview-image/发型.png",
      uploadIcon: "📷",
      uploadTitle: "上传正面照片",
      uploadTip: "请确保脸部正面清晰、无遮挡、光线充足",
      retryText: "重新上传",
      route: "/pages/ai/index?type=hair",
    },
    validation: {
      serviceUrl:
        process.env.VALIDATION_SERVICE_URL ||
        "http://36.156.154.98:8010/v1/chat/completions",
      model: process.env.VALIDATION_MODEL || "qwen3.6",
      prompt: "这张图片是否包含清晰的正面人像照片？请只回答'是'或'否'。",
      failMessage: "图片不符合要求，请重新拍摄清晰正面人像",
    },
    generation: {
      prompt: `Based on this person's photo, generate a professional hairstyle analysis poster in Chinese.
Style: modern clean layout, white cards, WeChat-friendly visual tone.
Include: person's photo with face analysis (脸型/发质/发色), recommended hairstyles, styles to avoid, hair care tips, product recommendations.
Text should be in Chinese. Format: vertical poster, clean layout, professional look.`,
    },
    test: {
      posterFileID: TEST_POSTER_FILE_ID,
    },
  },
  profile: {
    type: "profile",
    enabled: true,
    order: 30,
    public: {
      title: "个人形象分析",
      shortTitle: "形象分析",
      description: "上传正面肖像照，生成专属个人形象分析图卡",
      icon: "✨",
      previewImageHD: "",
      uploadIcon: "📷",
      uploadTitle: "上传正面肖像照",
      uploadTip: "请确保脸部正面清晰、无遮挡、光线充足",
      retryText: "重新上传",
      route: "/pages/ai/index?type=profile",
    },
    validation: {
      serviceUrl:
        process.env.VALIDATION_SERVICE_URL ||
        "http://36.156.154.98:8010/v1/chat/completions",
      model: process.env.VALIDATION_MODEL || "qwen3.6",
      prompt: "这张图片是否包含清晰的正面人像照片？请只回答'是'或'否'。",
      failMessage: "图片不符合要求，请重新拍摄清晰正面人像",
    },
    generation: {
      prompt: `请根据我上传的人像照片，做一套个人形象分析图卡，包含发型、妆容、色彩和珠宝。
要求：保留五官脸型肤色，不要过度修图，所有变化在同一张脸真实展示，风格干净高级。
发型：长短、卷直、刘海，对比最适合 / 普通 / 不建议（显脸小、显老）
妆容：眉眼鼻唇分析，标签（自然、提气色、柔和）
色彩：不同颜色上身，对比推荐 / 普通 / 不适合（显白、显老）
珠宝：珍珠、翡翠、红蓝宝、钻石、黄金，对比推荐 / 普通 / 不建议
整体：视觉为主，文字简短，3:4比例`,
    },
    test: {
      posterFileID: TEST_POSTER_FILE_ID,
    },
  },
  doodle: {
    type: "doodle",
    enabled: true,
    order: 40,
    public: {
      title: "INS手绘风照片",
      shortTitle: "手绘照片",
      description: "上传照片，生成手绘风注解照片",
      icon: "✏️",
      previewImageHD: "",
      uploadIcon: "📷",
      uploadTitle: "上传照片",
      uploadTip: "请确保照片清晰、光线充足",
      retryText: "重新上传",
      route: "/pages/ai/index?type=doodle",
    },
    validation: {
      serviceUrl:
        process.env.VALIDATION_SERVICE_URL ||
        "http://36.156.154.98:8010/v1/chat/completions",
      model: process.env.VALIDATION_MODEL || "qwen3.6",
      prompt: "这张图片是否是一张清晰的照片？请只回答'是'或'否'。",
      failMessage: "图片不符合要求，请重新上传清晰照片",
    },
    generation: {
      prompt: `请观察照片中的元素，并为每个物件加上有意义的手绘风注解。请填写照片中的物品（例：披萨、汽水）

【描写规则】
• 使用像白色笔画的细线手绘线条
• 一笔画风格、随性、略带不均匀感
• 沿着物件外围加上描边轮廓
• 用箭头或虚线做出视线引导

【文字规则】
• 手写风格字体（日系可爱感）
• 句子简短、像自言自语的小碎念
• 语气偏日记感、带一点情绪

【注解生成规则】
• 饮料 → 味道、温度、心情（例：清爽、微甜、刚刚好）
• 食物 → 口感、好吃程度（例：松软、超好吃）
• 空间 → 氛围（例：很放松、喜欢这种感觉）
• 整体 → 一句总结（例：今天有点幸福~）

【装饰】
• 适度加入热气、闪光、爱心、星星、小表情等元素。不要过度装饰，保留空白空间。`,
    },
    test: {
      posterFileID: TEST_POSTER_FILE_ID,
    },
  },
  soul: {
    type: "soul",
    enabled: true,
    order: 50,
    public: {
      title: "灵魂画手",
      shortTitle: "灵魂画手",
      description: "上传照片，生成魔性灵魂画风",
      icon: "🎨",
      previewImageHD: "",
      uploadIcon: "📷",
      uploadTitle: "上传照片",
      uploadTip: "请确保照片清晰",
      retryText: "重新上传",
      route: "/pages/ai/index?type=soul",
    },
    validation: {
      serviceUrl:
        process.env.VALIDATION_SERVICE_URL ||
        "http://36.156.154.98:8010/v1/chat/completions",
      model: process.env.VALIDATION_MODEL || "qwen3.6",
      prompt: "这张图片是否是一张清晰的照片？请只回答'是'或'否'。",
      failMessage: "图片不符合要求，请重新上传清晰照片",
    },
    generation: {
      prompt: `Redraw the attached image in the most clumsy, scribbly, and utterly pathetic way possible. Use a white background, and make it look like it was drawn in MS Paint with a mouse. It should be vaguely similar but also not really, kind of matching but also off in a confusing, awkward way, with that low-quality pixel-by-pixel feel that really emphasizes how ridiculously bad it is. Actually, you know what, whatever, just draw it however you want.`,
    },
    test: {
      posterFileID: TEST_POSTER_FILE_ID,
    },
  },
};

function getEnabledFeatureConfig(type) {
  const config = FEATURE_CONFIGS[type];
  if (!config || !config.enabled) return null;
  return config;
}

function toPublicFeature(config) {
  return {
    type: config.type,
    enabled: config.enabled,
    order: config.order,
    ...config.public,
  };
}

function getPublicFeatureList() {
  return Object.values(FEATURE_CONFIGS)
    .filter((config) => config.enabled)
    .sort((a, b) => a.order - b.order)
    .map(toPublicFeature);
}

module.exports = {
  getEnabledFeatureConfig,
  getPublicFeatureList,
};
