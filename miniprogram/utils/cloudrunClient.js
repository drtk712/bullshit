const CLOUDRUN_SERVICE_NAME = "wantuju-api";

const callCloudRun = async ({ path, method = "GET", data = {} }) => {
  const app = getApp();
  try {
    return await wx.cloud.callContainer({
      config: { env: app.globalData.env },
      path,
      method,
      header: {
        "X-WX-SERVICE": CLOUDRUN_SERVICE_NAME,
      },
      data,
    });
  } catch (err) {
    const error = new Error(err?.errMsg || err?.message || "云托管请求失败");
    error.isCloudRunError = true;
    error.raw = err;
    throw error;
  }
};

module.exports = {
  callCloudRun,
};
