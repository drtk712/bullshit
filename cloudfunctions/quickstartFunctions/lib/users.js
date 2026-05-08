const { cloud, db, USERS_COLLECTION } = require("./cloudbase");
const { ensureCollection } = require("./collections");
const { createPointTransaction } = require("./points");

const maskOpenid = (openid) => `******${String(openid || "").slice(-4)}`;

const toPublicUser = (user, openid) => ({
  openidMasked: maskOpenid(openid),
  points: user.points,
  isNewUser: !!user.isNewUser,
  createdAt: user.createdAt,
  lastLoginAt: user.lastLoginAt,
  lastCheckInAt: user.lastCheckInAt,
  checkInDays: user.checkInDays || 0,
  nickName: user.nickName || "",
  avatarFileID: user.avatarFileID || "",
  profileCompleted: !!user.profileCompleted,
  profileCompletedAt: user.profileCompletedAt || null,
});

const ensureUser = async (openid, options = {}) => {
  await ensureCollection();

  const now = Date.now();
  const userResult = await db.collection(USERS_COLLECTION)
    .where({ openid })
    .limit(1)
    .get();

  if (userResult.data && userResult.data.length > 0) {
    const user = userResult.data[0];
    if (options.recordLogin) {
      await db.collection(USERS_COLLECTION).doc(user._id).update({
        data: {
          updatedAt: now,
          lastLoginAt: now,
        },
      });
      return {
        ...user,
        updatedAt: now,
        lastLoginAt: now,
        isNewUser: false,
      };
    }

    return {
      ...user,
      isNewUser: false,
    };
  }

  const userData = {
    openid,
    points: 3,
    totalGrantedPoints: 3,
    totalUsedPoints: 0,
    totalRefundedPoints: 0,
    createdAt: now,
    updatedAt: now,
    lastLoginAt: now,
  };
  const createResult = await db.collection(USERS_COLLECTION).add({ data: userData });

  await createPointTransaction({
    openid,
    type: "grant",
    amount: 3,
    balanceAfter: 3,
    reason: "first_login",
    taskId: null,
  });

  return {
    _id: createResult._id,
    ...userData,
    isNewUser: true,
  };
};

const login = async () => {
  try {
    const wxContext = cloud.getWXContext();
    const openid = wxContext.OPENID;
    const user = await ensureUser(openid, { recordLogin: true });

    return {
      success: true,
      data: {
        user: {
          ...toPublicUser(user, openid),
        },
      },
    };
  } catch (e) {
    console.error("login 错误:", e.message);
    return {
      success: false,
      errMsg: e.message || "登录失败",
    };
  }
};

const getUserProfile = async () => {
  try {
    const wxContext = cloud.getWXContext();
    const openid = wxContext.OPENID;
    const user = await ensureUser(openid);

    return {
      success: true,
      data: {
        user: {
          ...toPublicUser(user, openid),
        },
      },
    };
  } catch (e) {
    console.error("getUserProfile 错误:", e.message);
    return {
      success: false,
      errMsg: e.message || "获取用户资料失败",
    };
  }
};

const updateUserProfile = async (event) => {
  try {
    const wxContext = cloud.getWXContext();
    const openid = wxContext.OPENID;
    const user = await ensureUser(openid);
    const nickName = String(event.data?.nickName || "").trim();
    const avatarFileID = String(event.data?.avatarFileID || "").trim();

    if (!nickName) {
      return { success: false, errMsg: "请填写昵称" };
    }
    if (nickName.length > 24) {
      return { success: false, errMsg: "昵称不能超过 24 个字符" };
    }
    if (!avatarFileID || !avatarFileID.startsWith("cloud://")) {
      return { success: false, errMsg: "请选择头像" };
    }

    const now = Date.now();
    await db.collection(USERS_COLLECTION).doc(user._id).update({
      data: {
        nickName,
        avatarFileID,
        profileCompleted: true,
        profileCompletedAt: user.profileCompletedAt || now,
        updatedAt: now,
      },
    });

    return {
      success: true,
      data: {
        user: toPublicUser({
          ...user,
          nickName,
          avatarFileID,
          profileCompleted: true,
          profileCompletedAt: user.profileCompletedAt || now,
          updatedAt: now,
        }, openid),
      },
    };
  } catch (e) {
    console.error("updateUserProfile 错误:", e.message);
    return {
      success: false,
      errMsg: e.message || "保存用户资料失败",
    };
  }
};

module.exports = {
  ensureUser,
  getUserProfile,
  login,
  toPublicUser,
  updateUserProfile,
};
