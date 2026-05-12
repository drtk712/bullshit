const { claimShareRewardPoints, fetchShareRewardStatus } = require("./api/shareApi");

const HOME_SHARE_PAYLOAD = {
  title: "玩图局 - 实用图片处理工具",
  path: "/pages/index/index",
};

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

const buildHomeSharePayload = (overrides = {}) => ({
  ...HOME_SHARE_PAYLOAD,
  ...overrides,
});

const canShareTask = (task = {}) => {
  return task.status === "completed" && !!task._id && !!task.posterFileID;
};

const buildTaskSharePayload = (task = {}, options = {}) => {
  if (!canShareTask(task)) {
    return buildHomeSharePayload(options.fallback || {});
  }

  const featureTitle = String(task.featureTitle || task.displayName || "").trim();
  const title = featureTitle
    ? `我用玩图局做了「${featureTitle}」`
    : "我在玩图局处理了一张图片";

  return {
    title,
    path: `/pages/share/task/index?id=${task._id}`,
    imageUrl: options.imageUrl || task.shareImage || task.posterPreviewUrl || "",
  };
};

module.exports = {
  DEFAULT_SHARE_REWARD_STATUS,
  buildHomeSharePayload,
  buildShareRewardCopy,
  buildTaskSharePayload,
  canClaimShareReward,
  canShareTask,
  claimShareReward,
  getShareRewardStatus,
  normalizeShareRewardStatus,
};
