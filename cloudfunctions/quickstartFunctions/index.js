require("dotenv").config();

const REQUIRED_ENV_VARS = ["POSTER_SERVER_TOKEN"];
for (const varName of REQUIRED_ENV_VARS) {
  if (!process.env[varName]) {
    throw new Error(`[quickstartFunctions] Missing required env: ${varName}`);
  }
}

const cloud = require("wx-server-sdk");
const axios = require("axios");

cloud.init({
  env: cloud.DYNAMIC_CURRENT_ENV,
});

const db = cloud.database();
const _ = db.command;
const JOBS_COLLECTION = "ai_poster_jobs";
const USERS_COLLECTION = "users";
const POINT_TRANSACTIONS_COLLECTION = "point_transactions";
const FEATURE_CONFIGS_COLLECTION = "feature_configs";
const CLOUD_ENV = "cloud1-d7g1nt83fde793ad3";


let _collectionReady = false;

const getFeatureConfig = async (event) => {
  const requestedType = event.data?.type;

  if (requestedType) {
    const result = await db.collection(FEATURE_CONFIGS_COLLECTION)
      .where({ type: requestedType, enabled: true })
      .limit(1)
      .get();

    if (!result.data || result.data.length === 0) {
      return { success: false, errMsg: "功能暂不可用" };
    }

    const config = result.data[0];
    const feature = {
      type: config.type,
      enabled: config.enabled,
      order: config.order,
      ...config.public,
      ui: config.ui || {},
    };

    return { success: true, data: { feature } };
  }

  const result = await db.collection(FEATURE_CONFIGS_COLLECTION)
    .where({ enabled: true })
    .orderBy("order", "asc")
    .get();

  const features = (result.data || []).map((config) => ({
    type: config.type,
    enabled: config.enabled,
    order: config.order,
    ...config.public,
    ui: config.ui || {},
  }));

  return { success: true, data: { features } };
};

const ensureCollection = async () => {
  if (_collectionReady) return;
  
  try {
    await db.createCollection(JOBS_COLLECTION);
  } catch (e) {
    if (e.errCode !== -501001) {
      throw new Error(`数据库初始化失败: ${e.message || e.errCode}`);
    }
  }
  await ensureUserCollections();
  _collectionReady = true;
};

const ensureUserCollections = async () => {
  for (const collectionName of [USERS_COLLECTION, POINT_TRANSACTIONS_COLLECTION]) {
    try {
      await db.createCollection(collectionName);
    } catch (e) {
      if (e.errCode !== -501001) {
        throw new Error(`数据库初始化失败: ${e.message || e.errCode}`);
      }
    }
  }
};

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

const createPointTransaction = async ({
  openid,
  type,
  amount,
  balanceAfter,
  reason,
  taskId = null,
}) => {
  return await db.collection(POINT_TRANSACTIONS_COLLECTION).add({
    data: {
      openid,
      type,
      amount,
      balanceAfter,
      reason,
      taskId,
      createdAt: Date.now(),
    },
  });
};

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

const toPublicTransaction = (transaction) => ({
  _id: transaction._id,
  type: transaction.type,
  amount: transaction.amount,
  balanceAfter: transaction.balanceAfter,
  reason: transaction.reason,
  taskId: transaction.taskId || null,
  createdAt: transaction.createdAt,
});

const toPublicTask = (task) => ({
  _id: task._id,
  type: task.type,
  status: task.status,
  fileID: task.fileID || null,
  posterFileID: task.posterFileID || null,
  errMsg: task.errMsg || "",
  pointsCost: task.pointsCost || 0,
  pointsConsumed: !!task.pointsConsumed,
  pointsRefunded: !!task.pointsRefunded,
  createdAt: task.createdAt,
  updatedAt: task.updatedAt,
});

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

const getTransactions = async (event) => {
  try {
    const wxContext = cloud.getWXContext();
    const openid = wxContext.OPENID;
    await ensureCollection();

    const page = Math.max(1, parseInt(event.data?.page) || 1);
    const pageSize = Math.min(50, Math.max(1, parseInt(event.data?.pageSize) || 20));
    const skip = (page - 1) * pageSize;

    const countResult = await db.collection(POINT_TRANSACTIONS_COLLECTION)
      .where({ openid })
      .count();

    const result = await db.collection(POINT_TRANSACTIONS_COLLECTION)
      .where({ openid })
      .orderBy("createdAt", "desc")
      .skip(skip)
      .limit(pageSize)
      .get();

    return {
      success: true,
      data: {
        transactions: (result.data || []).map(toPublicTransaction),
        total: countResult.total,
        page,
        pageSize,
        hasMore: skip + pageSize < countResult.total,
      },
    };
  } catch (e) {
    console.error("getTransactions 错误:", e.message);
    return { success: false, errMsg: e.message || "获取积分明细失败" };
  }
};

const getTasks = async (event) => {
  try {
    const wxContext = cloud.getWXContext();
    const openid = wxContext.OPENID;
    await ensureCollection();

    const page = Math.max(1, parseInt(event.data?.page) || 1);
    const pageSize = Math.min(50, Math.max(1, parseInt(event.data?.pageSize) || 20));
    const skip = (page - 1) * pageSize;

    const countResult = await db.collection(JOBS_COLLECTION)
      .where({ openid })
      .count();

    const result = await db.collection(JOBS_COLLECTION)
      .where({ openid })
      .orderBy("createdAt", "desc")
      .skip(skip)
      .limit(pageSize)
      .get();

    return {
      success: true,
      data: {
        tasks: (result.data || []).map(toPublicTask),
        total: countResult.total,
        page,
        pageSize,
        hasMore: skip + pageSize < countResult.total,
      },
    };
  } catch (e) {
    console.error("getTasks 错误:", e.message);
    return { success: false, errMsg: e.message || "获取生成记录失败" };
  }
};

const getTask = async (event) => {
  try {
    const wxContext = cloud.getWXContext();
    const openid = wxContext.OPENID;
    const { taskId } = event.data;

    if (!taskId) {
      return { success: false, errMsg: "缺少任务ID" };
    }

    await ensureCollection();

    const taskDoc = await db.collection(JOBS_COLLECTION).doc(taskId).get();

    if (!taskDoc.data || taskDoc.data.openid !== openid) {
      return { success: false, errMsg: "任务不存在" };
    }

    return {
      success: true,
      data: {
        task: toPublicTask(taskDoc.data),
      },
    };
  } catch (e) {
    console.error("getTask 错误:", e.message);
    return { success: false, errMsg: e.message || "获取任务详情失败" };
  }
};

const validateImage = async (fileID, featureConfig) => {
  const tempFileResult = await cloud.getTempFileURL({ fileList: [fileID] });
  
  if (!tempFileResult.fileList || tempFileResult.fileList.length === 0) {
    return { passed: false, reason: "获取图片链接失败" };
  }
  
  const fileInfo = tempFileResult.fileList[0];
  if (fileInfo.status !== 0) {
    return { passed: false, reason: "图片链接生成失败: " + (fileInfo.errMsg || "未知错误") };
  }
  
  const imageUrl = fileInfo.tempFileURL;

  const validationConfig = featureConfig.validation;
  const prompt = validationConfig.prompt;

  try {
    const res = await axios.post(
      validationConfig.serviceUrl,
      {
        model: validationConfig.model,
        messages: [
          {
            role: "user",
            content: [
              { type: "image_url", image_url: { url: imageUrl } },
              { type: "text", text: prompt },
            ],
          },
        ],
        max_tokens: 32000,
      },
      {
        headers: { "Content-Type": "application/json" },
        timeout: 55000,
      }
    );

    if (res.status !== 200) {
      return { passed: false, reason: "验证服务响应异常，请稍后重试" };
    }

    const content = res.data?.choices?.[0]?.message?.content;
    if (!content) {
      return { passed: false, reason: "图片验证服务异常，请稍后重试" };
    }

    let answerText = content;
    const thinkEndTag = "endencies>";
    const tagIndex = content.indexOf(thinkEndTag);
    if (tagIndex > -1) {
      answerText = content.slice(tagIndex + thinkEndTag.length);
    }
    answerText = answerText.replace(/\s+/g, "");

    const lastYesIndex = answerText.lastIndexOf("是");
    const lastNoIndex = answerText.lastIndexOf("否");

    let hasYes = lastYesIndex > -1;
    let hasNo = lastNoIndex > -1;

    if (hasYes && hasNo) {
      hasYes = lastYesIndex > lastNoIndex;
      hasNo = !hasYes;
    }

    if (!hasYes && !hasNo) {
      return { passed: false, reason: "验证服务响应格式异常，请稍后重试" };
    }

    return {
      passed: hasYes,
      reason: hasNo ? validationConfig.failMessage : "",
    };
  } catch (e) {
    console.error("validateImage 错误:", e.code, e.message);
    
    if (e.code === "ECONNABORTED") {
      return { passed: false, reason: "验证服务超时，请稍后重试" };
    }
    if (e.code === "ENOTFOUND" || e.code === "ECONNREFUSED") {
      return { passed: false, reason: "验证服务不可用，请稍后重试" };
    }
    
    return {
      passed: false,
      reason: "验证失败，请稍后重试",
    };
  }
};

const validateAndCreateJob = async (event) => {
  try {
    await ensureCollection();
    
    const { type, fileID, test, skipPointsDeduction = false } = event.data;

    if (!type || !fileID) {
      return { success: false, errMsg: "缺少必要参数" };
    }

    const featureResult = await db.collection(FEATURE_CONFIGS_COLLECTION)
      .where({ type, enabled: true })
      .limit(1)
      .get();

    if (!featureResult.data || featureResult.data.length === 0) {
      return { success: false, errMsg: "功能暂不可用" };
    }

    const featureConfig = featureResult.data[0];
    const validation = await validateImage(fileID, featureConfig);
    if (!validation.passed) {
      await cloud.deleteFile({ fileList: [fileID] }).catch(() => {});
      return { success: false, errMsg: validation.reason };
    }

    const wxContext = cloud.getWXContext();
    const openid = wxContext.OPENID;
    const shouldConsumePoints = !skipPointsDeduction;
    const user = await ensureUser(openid);

    if (shouldConsumePoints && user.points < 1) {
      await cloud.deleteFile({ fileList: [fileID] }).catch(() => {});
      return { success: false, errMsg: "积分不足，请先获取积分" };
    }

    const tempFileResult = await cloud.getTempFileURL({ fileList: [fileID] });
    
    if (!tempFileResult.fileList || tempFileResult.fileList.length === 0) {
      return { success: false, errMsg: "获取图片链接失败" };
    }
    
    const fileInfo = tempFileResult.fileList[0];
    if (fileInfo.status !== 0) {
      return { success: false, errMsg: "图片链接生成失败" };
    }
    
    const imageUrl = fileInfo.tempFileURL;

    const taskResult = await db.collection(JOBS_COLLECTION).add({
      data: {
        type,
        fileID,
        serverTaskId: null,
        status: "init",
        posterFileID: null,
        errMsg: "",
        openid,
        pointsCost: shouldConsumePoints ? 1 : 0,
        pointsConsumed: false,
        pointsRefunded: false,
        skipPointsDeduction: skipPointsDeduction || false,
        consumeTransactionId: null,
        refundTransactionId: null,
        createdAt: Date.now(),
        updatedAt: Date.now(),
      },
    });

    const taskId = taskResult._id;

    const SERVER_URL = process.env.POSTER_SERVER_URL || "http://36.156.154.98:8011";
    try {
      const serverResp = await axios.post(`${SERVER_URL}/api/job`, {
        taskId,
        imageUrl,
        sourceFileID: fileID,
        type,
        test: test || false,
        generationPrompt: featureConfig.generation?.prompt || "",
        testPosterFileID: featureConfig.test?.posterFileID,
      }, {
        headers: {
          "X-Internal-Token": process.env.POSTER_SERVER_TOKEN || "",
        },
        timeout: 10000,
        validateStatus: (status) => status < 500
      });

      if (serverResp.status !== 200 || !serverResp.data?.taskId) {
        throw new Error(serverResp.data?.detail || serverResp.data?.errMsg || `服务端错误（${serverResp.status}）`);
      }

      await db.collection(JOBS_COLLECTION).doc(taskId).update({
        data: {
          serverTaskId: serverResp.data.taskId,
          updatedAt: Date.now(),
        },
      });
    } catch (serverErr) {
      console.error("调用服务端失败:", serverErr.code, serverErr.message);

      await db.collection(JOBS_COLLECTION).doc(taskId).update({
        data: {
          status: "failed",
          errMsg: serverErr.code === "ECONNABORTED"
            ? "连接服务端超时，请稍后重试"
            : (serverErr.code === "ENOTFOUND" || serverErr.code === "ECONNREFUSED")
              ? "服务端不可用，请稍后重试"
              : (serverErr.message || "网络异常，请检查网络后重试"),
          pointsRefunded: false,
          refundTransactionId: null,
          updatedAt: Date.now(),
        },
      });

      return {
        success: false,
        errMsg: serverErr.code === "ECONNABORTED"
          ? "连接服务端超时，请稍后重试"
          : (serverErr.code === "ENOTFOUND" || serverErr.code === "ECONNREFUSED")
            ? "服务端不可用，请稍后重试"
            : (serverErr.message || "网络异常，请检查网络后重试"),
      };
    }

    return {
      success: true,
      data: { taskId },
    };
  } catch (e) {
    console.error("validateAndCreateJob 错误:", e.message);
    return {
      success: false,
      errMsg: e.message || "创建任务失败",
    };
  }
};

const getTaskStatus = async (event) => {
  try {
    await ensureCollection();
    
    const { taskId } = event.data;

    if (!taskId) {
      return { success: false, errMsg: "缺少任务ID" };
    }

    const taskDoc = await db.collection(JOBS_COLLECTION).doc(taskId).get();

    if (!taskDoc.data) {
      return { success: false, errMsg: "任务不存在" };
    }

    const task = taskDoc.data;
    const wxContext = cloud.getWXContext();
    const openid = wxContext.OPENID;

    if (!task.openid || task.openid !== openid) {
      return { success: false, errMsg: "任务不存在" };
    }

    return {
      success: true,
      data: {
        status: task.status,
        posterFileID: task.posterFileID,
        errMsg: task.errMsg,
      },
    };
  } catch (e) {
    console.error("getTaskStatus 错误:", e.message);
    return {
      success: false,
      errMsg: e.message || "查询失败",
    };
  }
};

const STALE_TASK_TIMEOUT_MS = 15 * 60 * 1000;

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

    // 检查是否已经签到（根据 lastCheckInAt 日期）
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

    // 执行签到：+1 积分
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
const SHARE_MIN_INTERVAL_MS = 60 * 1000; // 1分钟间隔防刷

const shareEarnPoints = async () => {
  try {
    const wxContext = cloud.getWXContext();
    const openid = wxContext.OPENID;
    await ensureCollection();

    const user = await ensureUser(openid);
    const todayStr = getShanghaiDateString();
    const now = Date.now();

    // 每日重置分享次数（兼容旧用户）
    if (user.lastShareDate !== todayStr) {
      user.shareCountToday = 0;
      user.lastShareDate = todayStr;
    } else if (!user.shareCountToday) {
      user.shareCountToday = 0;
    }

    // 检查每日上限
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

    // 检查最小时间间隔防刷
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

    // 执行分享奖励：+1 积分
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

const deleteTask = async (event) => {
  try {
    const wxContext = cloud.getWXContext();
    const openid = wxContext.OPENID;
    const { taskId } = event.data;

    if (!taskId) {
      return { success: false, errMsg: "缺少任务ID" };
    }

    await ensureCollection();

    const taskDoc = await db.collection(JOBS_COLLECTION).doc(taskId).get();

    if (!taskDoc.data || taskDoc.data.openid !== openid) {
      return { success: false, errMsg: "任务不存在" };
    }

    // 只有已完成或失败的任务可以删除
    const task = taskDoc.data;
    if (task.status === "init" || task.status === "pending" || task.status === "processing") {
      return { success: false, errMsg: "进行中的任务不能删除" };
    }

    // 删除云存储中的海报文件（如果有）
    if (task.posterFileID) {
      try {
        await cloud.deleteFile({ fileList: [task.posterFileID] });
      } catch (e) {
        console.warn("删除海报文件失败（继续删除数据库记录）:", e.message);
      }
    }

    // 删除数据库记录
    await db.collection(JOBS_COLLECTION).doc(taskId).remove();

    return { success: true, data: { taskId } };
  } catch (e) {
    console.error("deleteTask 错误:", e.message);
    return { success: false, errMsg: e.message || "删除任务失败" };
  }
};

const cleanupStaleTasks = async () => {
  try {
    const staleThreshold = Date.now() - STALE_TASK_TIMEOUT_MS;

    const staleTasks = await db.collection(JOBS_COLLECTION)
      .where({
        status: "init",
        createdAt: _.lt(staleThreshold),
      })
      .limit(100)
      .get();

    let cleanedCount = 0;

    for (const task of staleTasks.data || []) {
      try {
        await db.collection(JOBS_COLLECTION).doc(task._id).update({
          data: {
            status: "failed",
            errMsg: "任务提交超时，自动取消",
            updatedAt: Date.now(),
          },
        });
        cleanedCount++;
      } catch (e) {
        console.error(`cleanupStaleTasks 处理任务 ${task._id} 失败:`, e.message);
      }
    }

    return {
      success: true,
      data: { cleanedCount, total: (staleTasks.data || []).length },
    };
  } catch (e) {
    console.error("cleanupStaleTasks 错误:", e.message);
    return { success: false, errMsg: e.message || "清理超时任务失败" };
  }
};

exports.main = async (event, context) => {
  // 处理定时触发器触发 (微信云开发定时任务 event.Type = "Timer")
  if (event.Type === "Timer" || event.TriggerName) {
    if (event.TriggerName === "cleanupStaleTasksTimer") {
      console.log("[Timer] 定时任务触发: 清理超时任务", new Date().toISOString());
      const result = await cleanupStaleTasks(event);
      console.log("[Timer] 定时任务完成: 清理了", result.data?.cleanedCount || 0, "个任务");
      return result;
    }
    return { success: false, errMsg: `未知触发器: ${event.TriggerName}` };
  }

  // 处理普通调用
  switch (event.type) {
    case "getFeatureConfig":
      return await getFeatureConfig(event);
    case "login":
      return await login(event);
    case "getUserProfile":
      return await getUserProfile(event);
    case "updateUserProfile":
      return await updateUserProfile(event);
    case "validateAndCreateJob":
      return await validateAndCreateJob(event);
    case "getTaskStatus":
      return await getTaskStatus(event);
    case "getTransactions":
      return await getTransactions(event);
    case "getTasks":
      return await getTasks(event);
    case "getTask":
      return await getTask(event);
    case "dailyCheckIn":
      return await dailyCheckIn(event);
    case "shareEarnPoints":
      return await shareEarnPoints(event);
    case "cleanupStaleTasks":
      return await cleanupStaleTasks(event);
    case "deleteTask":
      return await deleteTask(event);
    default:
      return { success: false, errMsg: `未知的操作类型: ${event.type}` };
  }
};
