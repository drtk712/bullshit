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
      description: "上传清晰手掌照片，瞎扯一段手相解读海报",
      icon: "🖐️",
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
      description: "上传正面照片，瞎扯一段发型建议海报",
      icon: "💇",
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
