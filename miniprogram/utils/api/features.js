const { callCloudRun } = require("../cloudrunClient");
const { buildQuery, getApiErrorMessage } = require("./errors");

async function fetchFeatureList() {
  const resp = await callCloudRun({
    path: "/miniapp/features",
    method: "GET",
  });

  if (resp.data?.success && Array.isArray(resp.data?.data?.features)) {
    return resp.data.data.features;
  }

  throw new Error(getApiErrorMessage(resp, "功能列表加载失败"));
}

async function fetchFeature(type) {
  const resp = await callCloudRun({
    path: `/miniapp/features${buildQuery({ type })}`,
    method: "GET",
  });

  if (resp.data?.success && resp.data?.data?.feature) {
    return resp.data.data.feature;
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
};
