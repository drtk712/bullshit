const { saveProfile } = require("./api/user");
const { uploadPhoto } = require("./api/upload");

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

  return uploadPhoto(avatarPath);
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
