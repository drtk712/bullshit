const { claimShareRewardPoints, fetchShareRewardStatus } = require("./api/share");
const { saveProfile } = require("./api/user");

const DEFAULT_SHARE_REWARD_STATUS = {
  shareRewardPoints: 1,
  shareLimitPerDay: 3,
  shareCountToday: 0,
  remainingToday: 3,
  canEarnSharePoints: true,
  points: 0,
};

const normalizeShareRewardStatus = (data = {}) => ({
  ...DEFAULT_SHARE_REWARD_STATUS,
  ...data,
  shareRewardPoints: Number(data.shareRewardPoints ?? DEFAULT_SHARE_REWARD_STATUS.shareRewardPoints),
  shareLimitPerDay: Number(data.shareLimitPerDay ?? DEFAULT_SHARE_REWARD_STATUS.shareLimitPerDay),
  shareCountToday: Number(data.shareCountToday ?? DEFAULT_SHARE_REWARD_STATUS.shareCountToday),
  remainingToday: Number(data.remainingToday ?? DEFAULT_SHARE_REWARD_STATUS.remainingToday),
  canEarnSharePoints: Number(data.remainingToday ?? DEFAULT_SHARE_REWARD_STATUS.remainingToday) > 0,
  points: Number(data.points ?? DEFAULT_SHARE_REWARD_STATUS.points),
});

const getShareRewardStatus = async () => {
  return normalizeShareRewardStatus(await fetchShareRewardStatus());
};

const claimShareReward = async (options = {}) => {
  const { showToast = true } = options;
  const res = await claimShareRewardPoints();

  if (res.success) {
    const status = normalizeShareRewardStatus(res.data);
    if (showToast) {
      wx.showToast({ title: `分享成功 +${status.shareRewardPoints} 积分`, icon: "success" });
    }
    return { success: true, status };
  }

  const status = normalizeShareRewardStatus(res.data);
  if (showToast) {
    wx.showToast({ title: res.errMsg || "今日分享次数已达上限", icon: "none" });
  }
  return { success: false, status, errMsg: res.errMsg || "" };
};

const buildShareRewardCopy = (status = DEFAULT_SHARE_REWARD_STATUS) => {
  const normalized = normalizeShareRewardStatus(status);
  if (normalized.remainingToday > 0) {
    return {
      buttonText: "分享得积分",
      shortButtonText: "去分享",
      title: "分享得积分",
      desc: `今日还可获得 ${normalized.remainingToday} 积分`,
      rewardText: `今日还可 +${normalized.remainingToday} 积分`,
      canEarn: true,
    };
  }

  return {
    buttonText: "分享给朋友",
    shortButtonText: "去分享",
    title: "分享给朋友",
    desc: "今日分享积分已达上限",
    rewardText: "明日再来 +1 积分",
    canEarn: false,
  };
};

const canClaimShareReward = (status) => {
  if (!status) return true;
  return normalizeShareRewardStatus(status).remainingToday > 0;
};

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
  DEFAULT_SHARE_REWARD_STATUS,
  buildShareRewardCopy,
  canClaimShareReward,
  claimShareReward,
  getShareRewardStatus,
  normalizeShareRewardStatus,
  saveUserProfile,
};
