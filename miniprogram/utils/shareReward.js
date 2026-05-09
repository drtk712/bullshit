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
  const res = await wx.cloud.callFunction({
    name: "quickstartFunctions",
    data: { type: "getShareRewardStatus", data: {} },
  });

  if (!res.result?.success) {
    throw new Error(res.result?.errMsg || "获取分享奖励状态失败");
  }

  return normalizeShareRewardStatus(res.result.data);
};

const claimShareReward = async (options = {}) => {
  const { showToast = true } = options;
  const res = await wx.cloud.callFunction({
    name: "quickstartFunctions",
    data: { type: "shareEarnPoints", data: {} },
  });

  if (res.result?.success) {
    const status = normalizeShareRewardStatus(res.result.data);
    if (showToast) {
      wx.showToast({ title: `分享成功 +${status.shareRewardPoints} 积分`, icon: "success" });
    }
    return { success: true, status };
  }

  const status = normalizeShareRewardStatus(res.result?.data);
  if (showToast) {
    wx.showToast({ title: res.result?.errMsg || "今日分享次数已达上限", icon: "none" });
  }
  return { success: false, status, errMsg: res.result?.errMsg || "" };
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

module.exports = {
  DEFAULT_SHARE_REWARD_STATUS,
  buildShareRewardCopy,
  canClaimShareReward,
  claimShareReward,
  getShareRewardStatus,
  normalizeShareRewardStatus,
};
