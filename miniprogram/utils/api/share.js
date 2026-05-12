const { callCloudRun } = require("../cloudrunClient");
const { getApiErrorMessage } = require("./errors");

async function fetchShareRewardStatus() {
  const resp = await callCloudRun({
    path: "/miniapp/share-reward/status",
    method: "GET",
  });

  if (resp.data?.success) {
    return resp.data.data;
  }

  throw new Error(getApiErrorMessage(resp, "获取分享奖励状态失败"));
}

async function claimShareRewardPoints() {
  const resp = await callCloudRun({
    path: "/miniapp/share-reward/claim",
    method: "POST",
  });

  return {
    success: !!resp.data?.success,
    data: resp.data?.data,
    errMsg: getApiErrorMessage(resp, ""),
  };
}

async function dailyCheckIn() {
  const resp = await callCloudRun({
    path: "/miniapp/share-reward/check-in",
    method: "POST",
  });

  return {
    success: !!resp.data?.success,
    data: resp.data?.data,
    errMsg: getApiErrorMessage(resp, "签到失败"),
  };
}

module.exports = {
  claimShareRewardPoints,
  dailyCheckIn,
  fetchShareRewardStatus,
};
