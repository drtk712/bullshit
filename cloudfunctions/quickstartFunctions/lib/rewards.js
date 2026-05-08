const { cloud, db, _, USERS_COLLECTION } = require("./cloudbase");
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
const SHARE_MIN_INTERVAL_MS = 60 * 1000;

const shareEarnPoints = async () => {
  try {
    const wxContext = cloud.getWXContext();
    const openid = wxContext.OPENID;
    await ensureCollection();

    const user = await ensureUser(openid);
    const todayStr = getShanghaiDateString();
    const now = Date.now();

    if (user.lastShareDate !== todayStr) {
      user.shareCountToday = 0;
      user.lastShareDate = todayStr;
    } else if (!user.shareCountToday) {
      user.shareCountToday = 0;
    }

    if (user.shareCountToday >= SHARE_POINTS_LIMIT_PER_DAY) {
      return {
        success: false,
        errMsg: "今日分享次数已达上限",
        data: {
          shareCountToday: user.shareCountToday,
          remainingToday: 0,
          points: user.points,
        },
      };
    }

    if (user.lastShareAt && now - user.lastShareAt < SHARE_MIN_INTERVAL_MS) {
      return {
        success: false,
        errMsg: "操作过于频繁，请稍后再试",
        data: {
          shareCountToday: user.shareCountToday,
          remainingToday: SHARE_POINTS_LIMIT_PER_DAY - user.shareCountToday,
          points: user.points,
        },
      };
    }

    await db.collection(USERS_COLLECTION).doc(user._id).update({
      data: {
        points: _.inc(1),
        totalGrantedPoints: _.inc(1),
        shareCountToday: user.shareCountToday + 1,
        lastShareDate: todayStr,
        lastShareAt: now,
        updatedAt: now,
      },
    });

    const updatedUser = await db.collection(USERS_COLLECTION).doc(user._id).get();

    await createPointTransaction({
      openid,
      type: "grant",
      amount: 1,
      balanceAfter: updatedUser.data.points,
      reason: "share_reward",
      taskId: null,
    });

    return {
      success: true,
      data: {
        pointsGained: 1,
        shareCountToday: user.shareCountToday + 1,
        remainingToday: SHARE_POINTS_LIMIT_PER_DAY - user.shareCountToday - 1,
        points: updatedUser.data.points,
      },
    };
  } catch (e) {
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
  shareEarnPoints,
};
