async function fetchFeatureList() {
  const resp = await wx.cloud.callFunction({
    name: "quickstartFunctions",
    data: { type: "getFeatureConfig", data: {} },
  });

  if (resp.result?.success && Array.isArray(resp.result.data?.features)) {
    return resp.result.data.features;
  }

  throw new Error(resp.result?.errMsg || "功能列表加载失败");
}

async function fetchFeature(type) {
  const resp = await wx.cloud.callFunction({
    name: "quickstartFunctions",
    data: { type: "getFeatureConfig", data: { type } },
  });

  if (resp.result?.success && resp.result.data?.feature) {
    return resp.result.data.feature;
  }

  throw new Error(resp.result?.errMsg || "功能暂不可用");
}

function buildFeatureMap(features) {
  return (features || []).reduce((acc, item) => {
    if (item?.type) acc[item.type] = item;
    return acc;
  }, {});
}

module.exports = {
  buildFeatureMap,
  fetchFeatureList,
  fetchFeature,
};
