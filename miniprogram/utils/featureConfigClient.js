const FALLBACK_FEATURES = [
  {
    type: "palm",
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
  {
    type: "hair",
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
];

/**
 * IMPORTANT: FALLBACK_FEATURES duplicates the public section of cloud config.
 * When updating palm/hair public copy in featureConfig.js, update this fallback too.
 */
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
