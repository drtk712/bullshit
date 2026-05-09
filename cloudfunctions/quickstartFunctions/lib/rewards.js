const { cloud, db, _, USERS_COLLECTION, POINT_TRANSACTIONS_COLLECTION } = require("./cloudbase");
const { ensureCollection } = require("./collections");
const { createPointTransaction } = require("./points");
const { ensureUser } = require("./users");

const getShanghaiDateString = () => {
  const now = new Date();
  const shanghaiTime = new Date(now.getTime() + 8 * 60 * 60 * 1000);
  return shanghaiTime.toISOString().split("T")[0];
};

const dailyCheckIn = async () => {
  try {
    const wxContext = cloud.getWXContext();
    const openid = wxContext.OPENID;
    await ensureCollection();

    const user = await ensureUser(openid);
    const todayStr = getShanghaiDateString();

    if (user.lastCheckInAt) {
      const lastCheckInDate = new Date(user.lastCheckInAt);
      const lastCheckInDateStr = new Date(lastCheckInDate.getTime() + 8 * 60 * 60 * 1000)
        .toISOString()
        .split("T")[0];
      if (lastCheckInDateStr === todayStr) {
        return {
          success: false,
          errMsg: "今日已签到",
          data: {
            checkedIn: true,
            points: user.points,
            checkInAt: user.lastCheckInAt,
          },
        };
      }
    }

    const now = Date.now();
    await db.collection(USERS_COLLECTION).doc(user._id).update({
      data: {
        points: _.inc(1),
        totalGrantedPoints: _.inc(1),
        lastCheckInAt: now,
        checkInDays: _.inc(1),
        updatedAt: now,
      },
    });

    const updatedUser = await db.collection(USERS_COLLECTION).doc(user._id).get();

    await createPointTransaction({
      openid,
      type: "grant",
      amount: 1,
      balanceAfter: updatedUser.data.points,
      reason: "daily_check_in",
      taskId: null,
    });

    return {
      success: true,
      data: {
        checkedIn: true,
        pointsGained: 1,
        points: updatedUser.data.points,
        checkInAt: now,
      },
    };
  } catch (e) {
    console.error("dailyCheckIn 错误:", e.message);
    return {
      success: false,
      errMsg: e.message || "签到失败",
    };
  }
};

const SHARE_POINTS_LIMIT_PER_DAY = 3;

class ShareRewardLimitError extends Error {
  constructor(status) {
    super("今日分享次数已达上限");
    this.name = "ShareRewardLimitError";
    this.status = status;
  }
}

const getShareRewardData = (user) => {
  const todayStr = getShanghaiDateString();
  const shareCountToday = user.lastShareDate === todayStr
    ? Number(user.shareCountToday || 0)
    : 0;
  const remainingToday = Math.max(0, SHARE_POINTS_LIMIT_PER_DAY - shareCountToday);

  return {
    shareRewardPoints: 1,
    shareLimitPerDay: SHARE_POINTS_LIMIT_PER_DAY,
    shareCountToday,
    remainingToday,
    canEarnSharePoints: remainingToday > 0,
    points: user.points || 0,
  };
};

const getShareRewardStatus = async () => {
  try {
    const wxContext = cloud.getWXContext();
    const openid = wxContext.OPENID;
    await ensureCollection();

    const user = await ensureUser(openid);

    return {
      success: true,
      data: getShareRewardData(user),
    };
  } catch (e) {
    console.error("getShareRewardStatus 错误:", e.message);
    return {
      success: false,
      errMsg: e.message || "获取分享奖励状态失败",
    };
  }
};

const shareEarnPoints = async () => {
  try {
    const wxContext = cloud.getWXContext();
    const openid = wxContext.OPENID;
    await ensureCollection();

    const user = await ensureUser(openid);
    const todayStr = getShanghaiDateString();
    let resultData = null;

    await db.runTransaction(async (transaction) => {
      const userDoc = await transaction.collection(USERS_COLLECTION).doc(user._id).get();
      const latestUser = userDoc.data || {};
      const status = getShareRewardData(latestUser);

      if (!status.canEarnSharePoints) {
        throw new ShareRewardLimitError(status);
      }

      const now = Date.now();
      const nextPoints = Number(latestUser.points || 0) + 1;
      const nextUser = {
        ...latestUser,
        points: nextPoints,
        totalGrantedPoints: Number(latestUser.totalGrantedPoints || 0) + 1,
        shareCountToday: status.shareCountToday + 1,
        lastShareDate: todayStr,
        lastShareAt: now,
        updatedAt: now,
      };

      await transaction.collection(USERS_COLLECTION).doc(user._id).update({
        data: {
          points: _.inc(1),
          totalGrantedPoints: _.inc(1),
          shareCountToday: nextUser.shareCountToday,
          lastShareDate: todayStr,
          lastShareAt: now,
          updatedAt: now,
        },
      });

      await transaction.collection(POINT_TRANSACTIONS_COLLECTION).add({
        data: {
          openid,
          type: "grant",
          amount: 1,
          balanceAfter: nextPoints,
          reason: "share_reward",
          taskId: null,
          createdAt: now,
        },
      });

      resultData = {
        pointsGained: 1,
        ...getShareRewardData(nextUser),
      };
    });

    return {
      success: true,
      data: resultData,
    };
  } catch (e) {
    if (e instanceof ShareRewardLimitError) {
      return {
        success: false,
        errMsg: e.message,
        data: e.status,
      };
    }

    console.error("shareEarnPoints 错误:", e.message);
    return {
      success: false,
      errMsg: e.message || "分享奖励获取失败",
    };
  }
};

module.exports = {
  dailyCheckIn,
  getShanghaiDateString,
  getShareRewardStatus,
  shareEarnPoints,
};
