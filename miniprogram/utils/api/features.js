const { callCloudRun } = require("../cloudrunClient");
const { buildQuery, getApiErrorMessage } = require("./errors");

const RETIRED_CLOUD_ENV = "cloud1-d7g1nt83fde793ad3";

function withoutRetiredPreview(feature) {
  if (!feature || typeof feature.previewImageHD !== "string") return feature;
  if (!feature.previewImageHD.includes(RETIRED_CLOUD_ENV)) return feature;
  return { ...feature, previewImageHD: "" };
}

function filterFeatureListForRuntime(features = []) {
  return features || [];
}

async function fetchFeatureList() {
  const resp = await callCloudRun({
    path: "/miniapp/features",
    method: "GET",
  });

  if (resp.data?.success && Array.isArray(resp.data?.data?.features)) {
    return filterFeatureListForRuntime(resp.data.data.features).map(withoutRetiredPreview);
  }

  throw new Error(getApiErrorMessage(resp, "功能列表加载失败"));
}

async function fetchFeature(type) {
  const resp = await callCloudRun({
    path: `/miniapp/features${buildQuery({ type })}`,
    method: "GET",
  });

  if (resp.data?.success && resp.data?.data?.feature) {
    return withoutRetiredPreview(resp.data.data.feature);
  }

  throw new Error(getApiErrorMessage(resp, "功能暂不可用"));
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
  filterFeatureListForRuntime,
};
