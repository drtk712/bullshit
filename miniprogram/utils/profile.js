function getAvatarExt(avatarPath) {
  const extMatch = String(avatarPath || "").match(/\.(png|jpg|jpeg|webp)$/i);
  return extMatch ? extMatch[1].toLowerCase().replace("jpeg", "jpg") : "jpg";
}

function createAvatarCloudPath(avatarPath) {
  const ext = getAvatarExt(avatarPath);
  return `user-avatars/${Date.now()}-${Math.random().toString(16).slice(2)}.${ext}`;
}

function normalizeProfileInput({ nickName, avatarPath }) {
  const normalizedNickName = String(nickName || "").trim();
  const normalizedAvatarPath = String(avatarPath || "").trim();

  if (!normalizedAvatarPath) {
    throw new Error("请先选择头像");
  }
  if (!normalizedNickName) {
    throw new Error("请填写昵称");
  }

  return {
    nickName: normalizedNickName,
    avatarPath: normalizedAvatarPath,
  };
}

async function uploadAvatarIfNeeded(avatarPath) {
  if (String(avatarPath).startsWith("cloud://")) {
    return avatarPath;
  }

  const uploadRes = await wx.cloud.uploadFile({
    cloudPath: createAvatarCloudPath(avatarPath),
    filePath: avatarPath,
  });

  return uploadRes.fileID;
}

async function saveUserProfile({ nickName, avatarPath }) {
  const profile = normalizeProfileInput({ nickName, avatarPath });
  const avatarFileID = await uploadAvatarIfNeeded(profile.avatarPath);

  const res = await wx.cloud.callFunction({
    name: "quickstartFunctions",
    data: {
      type: "updateUserProfile",
      data: {
        nickName: profile.nickName,
        avatarFileID,
      },
    },
  });

  if (!res.result || !res.result.success) {
    throw new Error(res.result?.errMsg || "保存失败");
  }

  return res.result.data.user;
}

module.exports = {
  saveUserProfile,
};
