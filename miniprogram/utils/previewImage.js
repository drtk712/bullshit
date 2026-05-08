const PREVIEW_URL_TTL_MS = 4 * 60 * 1000;
const previewUrlCache = {};

function isCloudFileID(url) {
  return typeof url === "string" && url.startsWith("cloud://");
}

function getCachedPreviewUrl(fileID) {
  const cached = previewUrlCache[fileID];
  if (!cached || cached.expiresAt <= Date.now()) {
    delete previewUrlCache[fileID];
    return "";
  }
  return cached.tempFileURL;
}

function setCachedPreviewUrl(fileID, tempFileURL) {
  previewUrlCache[fileID] = {
    tempFileURL,
    expiresAt: Date.now() + PREVIEW_URL_TTL_MS,
  };
}

async function getTempFileURL(fileID) {
  if (!fileID) {
    throw new Error("缺少文件 ID");
  }
  if (!isCloudFileID(fileID)) {
    return fileID;
  }

  const cachedUrl = getCachedPreviewUrl(fileID);
  if (cachedUrl) return cachedUrl;

  const result = await wx.cloud.getTempFileURL({ fileList: [fileID] });
  const fileInfo = result.fileList && result.fileList[0];
  if (!fileInfo || fileInfo.status !== 0 || !fileInfo.tempFileURL) {
    throw new Error(fileInfo?.errMsg || "获取图片链接失败");
  }
  setCachedPreviewUrl(fileID, fileInfo.tempFileURL);
  return fileInfo.tempFileURL;
}

async function resolvePreviewUrls(urls) {
  const validUrls = urls.filter(Boolean);
  const cloudFileIDs = Array.from(new Set(
    validUrls.filter((url) => isCloudFileID(url) && !getCachedPreviewUrl(url))
  ));

  if (cloudFileIDs.length > 0) {
    const result = await wx.cloud.getTempFileURL({ fileList: cloudFileIDs });
    const fileList = result.fileList || [];

    fileList.forEach((fileInfo) => {
      if (fileInfo.status === 0 && fileInfo.tempFileURL) {
        setCachedPreviewUrl(fileInfo.fileID, fileInfo.tempFileURL);
      }
    });
  }

  const resolvedUrls = validUrls.map((url) => getCachedPreviewUrl(url) || url);
  const unresolvedCloudUrl = resolvedUrls.find(isCloudFileID);

  if (unresolvedCloudUrl) {
    throw new Error("预览图片链接转换失败");
  }

  return resolvedUrls;
}

async function previewImages({ urls, current }) {
  const rawUrls = (Array.isArray(urls) ? urls : [current]).filter(Boolean);
  if (!rawUrls.length) return;

  const resolvedUrls = await resolvePreviewUrls(rawUrls);
  const currentIndex = rawUrls.indexOf(current);
  const resolvedCurrent = currentIndex >= 0 ? resolvedUrls[currentIndex] : resolvedUrls[0];

  wx.previewImage({
    urls: resolvedUrls,
    current: resolvedCurrent,
  });
}

function showAlbumPermissionModal(onAuthorized) {
  wx.showModal({
    title: "需要相册权限",
    content: "请在设置中开启相册权限以保存图片",
    confirmText: "去设置",
    success: (modalRes) => {
      if (!modalRes.confirm) return;
      wx.openSetting({
        success: (openRes) => {
          if (openRes.authSetting["scope.writePhotosAlbum"]) {
            onAuthorized();
          }
        },
      });
    },
  });
}

function downloadFile(fileID) {
  return new Promise((resolve, reject) => {
    wx.cloud.downloadFile({
      fileID,
      success: (downloadRes) => {
        if (!downloadRes.tempFilePath) {
          reject(new Error("下载失败"));
          return;
        }
        resolve(downloadRes.tempFilePath);
      },
      fail: () => reject(new Error("下载失败")),
    });
  });
}

function saveTempImage(filePath) {
  return new Promise((resolve, reject) => {
    wx.saveImageToPhotosAlbum({
      filePath,
      success: resolve,
      fail: () => reject(new Error("保存失败")),
    });
  });
}

function saveImageFile(fileID, options = {}) {
  const loadingTitle = options.loadingTitle || "保存中...";
  const successTitle = options.successTitle || "已保存到相册";

  const doSave = async () => {
    wx.showLoading({ title: loadingTitle });
    try {
      const tempFilePath = await downloadFile(fileID);
      await saveTempImage(tempFilePath);
      wx.hideLoading();
      wx.showToast({ title: successTitle, icon: "success" });
    } catch (err) {
      wx.hideLoading();
      wx.showToast({ title: err.message || "保存失败", icon: "none" });
    }
  };

  wx.getSetting({
    success: (settingRes) => {
      if (settingRes.authSetting["scope.writePhotosAlbum"]) {
        doSave();
        return;
      }

      wx.authorize({
        scope: "scope.writePhotosAlbum",
        success: doSave,
        fail: () => showAlbumPermissionModal(doSave),
      });
    },
  });
}

module.exports = {
  getTempFileURL,
  previewImages,
  resolvePreviewUrls,
  saveImageFile,
};
