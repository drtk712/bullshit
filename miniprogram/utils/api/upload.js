const { callCloudRun } = require("../cloudrunClient");
const { getApiErrorMessage } = require("./errors");

function readFileBuffer(filePath) {
  return new Promise((resolve, reject) => {
    wx.getFileSystemManager().readFile({
      filePath,
      success: (res) => resolve(res.data),
      fail: () => reject(new Error("读取图片失败")),
    });
  });
}

async function uploadPhoto(filePath) {
  const data = await readFileBuffer(filePath);
  const resp = await callCloudRun({
    path: "/miniapp/upload",
    method: "POST",
    header: { "content-type": "application/octet-stream" },
    data,
  });
  const fileID = resp.data?.data?.fileID;
  if (resp.data?.success && fileID) {
    return fileID;
  }
  throw new Error(getApiErrorMessage(resp, "上传失败"));
}

module.exports = {
  uploadPhoto,
};
