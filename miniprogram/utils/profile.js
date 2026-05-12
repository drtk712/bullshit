const { saveProfile } = require("./api/user");

const getAvatarExt = (avatarPath) => {
  const extMatch = String(avatarPath || "").match(/\.(png|jpg|jpeg|webp)$/i);
  return extMatch ? extMatch[1].toLowerCase().replace("jpeg", "jpg") : "jpg";
};

const createAvatarCloudPath = (avatarPath) => {
  const ext = getAvatarExt(avatarPath);
  return `user-avatars/${Date.now()}-${Math.random().toString(16).slice(2)}.${ext}`;
};

const normalizeProfileInput = ({ nickName, avatarPath }) => {
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
};

const uploadAvatarIfNeeded = async (avatarPath) => {
  if (String(avatarPath).startsWith("cloud://")) {
    return avatarPath;
  }

  const uploadRes = await wx.cloud.uploadFile({
    cloudPath: createAvatarCloudPath(avatarPath),
    filePath: avatarPath,
  });

  return uploadRes.fileID;
};

const saveUserProfile = async ({ nickName, avatarPath }) => {
  const profile = normalizeProfileInput({ nickName, avatarPath });
  const avatarFileID = await uploadAvatarIfNeeded(profile.avatarPath);

  return saveProfile({
    nickName: profile.nickName,
    avatarFileID,
  });
};

module.exports = {
  saveUserProfile,
};
