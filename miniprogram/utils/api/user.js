const { callCloudRun } = require("../cloudrunClient");
const { buildQuery, getApiErrorMessage } = require("./errors");

async function fetchMe(options = {}) {
  const resp = await callCloudRun({
    path: `/miniapp/me${buildQuery({ recordLogin: options.recordLogin ? "true" : "false" })}`,
    method: "GET",
  });

  if (resp.data?.success && resp.data?.data?.user) {
    return resp.data.data;
  }

  throw new Error(getApiErrorMessage(resp, "获取用户资料失败"));
}

async function saveProfile({ nickName, avatarFileID }) {
  const resp = await callCloudRun({
    path: "/miniapp/profile",
    method: "POST",
    data: { nickName, avatarFileID },
  });

  if (resp.data?.success && resp.data?.data?.user) {
    return resp.data.data.user;
  }

  throw new Error(getApiErrorMessage(resp, "保存失败"));
}

module.exports = {
  fetchMe,
  saveProfile,
};
