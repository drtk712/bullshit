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

module.exports = {
  previewImages,
  resolvePreviewUrls,
};
