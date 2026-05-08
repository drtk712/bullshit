const { db, FEATURE_CONFIGS_COLLECTION } = require("./cloudbase");

const toPublicFeature = (config) => ({
  type: config.type,
  enabled: config.enabled,
  order: config.order,
  ...config.public,
  ui: config.ui || {},
});

const getFeatureConfig = async (event) => {
  const requestedType = event.data?.type;

  if (requestedType) {
    const result = await db.collection(FEATURE_CONFIGS_COLLECTION)
      .where({ type: requestedType, enabled: true })
      .limit(1)
      .get();

    if (!result.data || result.data.length === 0) {
      return { success: false, errMsg: "功能暂不可用" };
    }

    return { success: true, data: { feature: toPublicFeature(result.data[0]) } };
  }

  const result = await db.collection(FEATURE_CONFIGS_COLLECTION)
    .where({ enabled: true })
    .orderBy("order", "asc")
    .get();

  const features = (result.data || []).map(toPublicFeature);

  return { success: true, data: { features } };
};

module.exports = {
  getFeatureConfig,
};
