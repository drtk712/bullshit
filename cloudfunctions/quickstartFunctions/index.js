require("dotenv").config();

const REQUIRED_ENV_VARS = ["POSTER_SERVER_TOKEN"];
for (const varName of REQUIRED_ENV_VARS) {
  if (!process.env[varName]) {
    throw new Error(`[quickstartFunctions] Missing required env: ${varName}`);
  }
}

const cloud = require("wx-server-sdk");
const axios = require("axios");
const {
  getEnabledFeatureConfig,
  getPublicFeatureList,
} = require("./featureConfig");

cloud.init({
  env: cloud.DYNAMIC_CURRENT_ENV,
});

const db = cloud.database();
const _ = db.command;
const JOBS_COLLECTION = "ai_poster_jobs";
const USERS_COLLECTION = "users";
const POINT_TRANSACTIONS_COLLECTION = "point_transactions";
const CLOUD_ENV = cloud.DYNAMIC_CURRENT_ENV;

let _collectionReady = false;

const getFeatureConfig = async (event) => {
  const requestedType = event.data?.type;

  if (requestedType) {
    const config = getEnabledFeatureConfig(requestedType);
    if (!config) {
      return { success: false, errMsg: "功能暂不可用" };
    }

    return {
      success: true,
      data: {
        feature: {
          type: config.type,
          enabled: config.enabled,
          order: config.order,
          ...config.public,
        },
      },
    };
  }

  return {
    success: true,
    data: {
      features: getPublicFeatureList(),
    },
  };
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

const consumePoints = async ({ openid, amount, reason }) => {
  const user = await ensureUser(openid);

  const updateResult = await db.collection(USERS_COLLECTION)
    .where({ _id: user._id, points: _.gte(amount) })
    .update({
      data: {
        points: _.inc(-amount),
        totalUsedPoints: _.inc(amount),
        updatedAt: Date.now(),
      },
    });

  if (!updateResult.stats || updateResult.stats.updated !== 1) {
    throw new Error("积分不足，请先获取积分");
  }

  const updatedUser = await db.collection(USERS_COLLECTION).doc(user._id).get();

  return await createPointTransaction({
    openid,
    type: "consume",
    amount: -amount,
    balanceAfter: updatedUser.data.points,
    reason,
    taskId: null,
  });
};

const refundPoints = async ({ openid, amount, reason, taskId }) => {
  const user = await ensureUser(openid);

  await db.collection(USERS_COLLECTION).doc(user._id).update({
    data: {
      points: _.inc(amount),
      totalRefundedPoints: _.inc(amount),
      updatedAt: Date.now(),
    },
  });

  const updatedUser = await db.collection(USERS_COLLECTION).doc(user._id).get();

  return await createPointTransaction({
    openid,
    type: "refund",
    amount,
    balanceAfter: updatedUser.data.points,
    reason,
    taskId,
  });
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
  posterFileID: task.posterFileID || null,
  errMsg: task.errMsg || "",
  pointsCost: task.pointsCost || 0,
  pointsConsumed: !!task.pointsConsumed,
  pointsRefunded: !!task.pointsRefunded,
  skipPointsDeduction: !!task.skipPointsDeduction,
  createdAt: task.createdAt,
  updatedAt: task.updatedAt,
});

const markTaskFailedWithRefund = async ({ taskId, task, errMsg }) => {
  let refundTransactionId = task.refundTransactionId || null;

  if (task.pointsConsumed && !task.pointsRefunded) {
    const refundResult = await refundPoints({
      openid: task.openid,
      amount: 1,
      reason: "job_failed_refund",
      taskId,
    });
    refundTransactionId = refundResult._id;
  }

  await db.collection(JOBS_COLLECTION).doc(taskId).update({
    data: {
      status: "failed",
      errMsg,
      pointsRefunded: task.pointsConsumed ? true : !!task.pointsRefunded,
      refundTransactionId,
      updatedAt: Date.now(),
    },
  });

  return refundTransactionId;
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
          openidMasked: maskOpenid(openid),
          points: user.points,
          isNewUser: user.isNewUser,
          createdAt: user.createdAt,
          lastLoginAt: user.lastLoginAt,
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
          openidMasked: maskOpenid(openid),
          points: user.points,
          createdAt: user.createdAt,
          lastLoginAt: user.lastLoginAt,
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

    const featureConfig = getEnabledFeatureConfig(type);
    if (!featureConfig) {
      return { success: false, errMsg: "功能暂不可用" };
    }

    const validation = await validateImage(fileID, featureConfig);
    if (!validation.passed) {
      await cloud.deleteFile({ fileList: [fileID] }).catch(() => {});
      return { success: false, errMsg: validation.reason };
    }

    const wxContext = cloud.getWXContext();
    const openid = wxContext.OPENID;
    const shouldConsumePoints = !skipPointsDeduction;
    const user = await ensureUser(openid);
    let consumeResult = null;

    if (shouldConsumePoints && user.points < 1) {
      await cloud.deleteFile({ fileList: [fileID] }).catch(() => {});
      return { success: false, errMsg: "积分不足，请先获取积分" };
    }

    if (shouldConsumePoints) {
      consumeResult = await consumePoints({
        openid,
        amount: 1,
        reason: "create_ai_job",
      });
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

    const SERVER_URL = process.env.POSTER_SERVER_URL || "http://36.156.154.98:8011";
    
    let serverResp;
    try {
      serverResp = await axios.post(`${SERVER_URL}/api/job`, {
        imageUrl,
        type,
        test: test || false,
        generationPrompt: featureConfig.generation.prompt,
        testPosterFileID: featureConfig.test?.posterFileID,
      }, {
        headers: {
          "X-Internal-Token": process.env.POSTER_SERVER_TOKEN || "",
        },
        timeout: 10000,
        validateStatus: (status) => status < 500
      });
    } catch (serverErr) {
      console.error("调用服务端失败:", serverErr.code, serverErr.message);
      
      if (shouldConsumePoints && consumeResult) {
        await refundPoints({
          openid,
          amount: 1,
          reason: "job_failed_refund",
          taskId: null,
        }).catch((refundErr) => {
          console.error("自动退款失败:", refundErr.message);
        });
      }
      
      if (serverErr.code === "ECONNABORTED") {
        return { success: false, errMsg: "连接服务端超时，请稍后重试" };
      }
      if (serverErr.code === "ENOTFOUND" || serverErr.code === "ECONNREFUSED") {
        return { success: false, errMsg: "服务端不可用，请稍后重试" };
      }
      
      return { success: false, errMsg: "网络异常，请检查网络后重试" };
    }

    if (serverResp.status !== 200) {
      if (shouldConsumePoints && consumeResult) {
        await refundPoints({ openid, amount: 1, reason: "job_failed_refund", taskId: null })
          .catch((e) => console.error("自动退款失败:", e.message));
      }
      return { success: false, errMsg: `服务端错误（${serverResp.status}): 请稍后重试` };
    }

    const serverTaskId = serverResp.data?.taskId;
    if (!serverTaskId) {
      if (shouldConsumePoints && consumeResult) {
        await refundPoints({ openid, amount: 1, reason: "job_failed_refund", taskId: null })
          .catch((e) => console.error("自动退款失败:", e.message));
      }
      return { success: false, errMsg: "服务端返回无效任务ID" };
    }

    const taskResult = await db.collection(JOBS_COLLECTION).add({
      data: {
        type,
        fileID,
        serverTaskId,
        status: "pending",
        posterFileID: null,
        errMsg: "",
        openid,
        pointsCost: shouldConsumePoints ? 1 : 0,
        pointsConsumed: shouldConsumePoints,
        pointsRefunded: false,
        skipPointsDeduction: skipPointsDeduction || false,
        consumeTransactionId: shouldConsumePoints ? consumeResult._id : null,
        refundTransactionId: null,
        createdAt: Date.now(),
        updatedAt: Date.now(),
      },
    });

    const taskId = taskResult._id;

    if (consumeResult && consumeResult._id) {
      await db.collection(POINT_TRANSACTIONS_COLLECTION).doc(consumeResult._id).update({
        data: { taskId },
      });
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

    if (task.status === "pending" || task.status === "processing") {
      const SERVER_URL = process.env.POSTER_SERVER_URL || "http://36.156.154.98:8011";
      
      if (!task.serverTaskId) {
        await markTaskFailedWithRefund({
          taskId,
          task,
          errMsg: "任务配置错误，缺少服务端任务ID",
        });
        return { success: false, errMsg: "任务配置错误" };
      }
      
      try {
        const serverResp = await axios.get(`${SERVER_URL}/api/job/${task.serverTaskId}`, {
          timeout: 10000
        });

        const serverStatus = serverResp.data?.status;
        const posterUrl = serverResp.data?.posterUrl;
        const errMsg = serverResp.data?.errMsg;

        if (serverStatus === "pending" || serverStatus === "processing") {
          if (task.status !== serverStatus) {
            await db.collection(JOBS_COLLECTION).doc(taskId).update({
              data: {
                status: serverStatus,
                errMsg: errMsg || "",
                updatedAt: Date.now(),
              },
            });
          }

          return {
            success: true,
            data: {
              status: serverStatus,
              posterFileID: task.posterFileID,
              errMsg: errMsg || "",
            },
          };
        }

        if (serverStatus === "completed" && !posterUrl) {
          await markTaskFailedWithRefund({
            taskId,
            task,
            errMsg: "服务端已完成但未返回图片链接",
          });
          return { success: false, errMsg: "生成结果异常，请重试" };
        }

        if (serverStatus === "completed" && posterUrl) {
          if (posterUrl.startsWith("cloud://")) {
            const expectedPrefix = `cloud://${CLOUD_ENV}-`;
            if (!posterUrl.startsWith(expectedPrefix)) {
              console.warn(
                "[getTaskStatus] Poster cloud file ID from unexpected environment:",
                posterUrl.slice(0, 30) + "..."
              );
            }

            await db.collection(JOBS_COLLECTION).doc(taskId).update({
              data: {
                status: "completed",
                posterFileID: posterUrl,
                updatedAt: Date.now(),
              },
            });

            return {
              success: true,
              data: {
                status: "completed",
                posterFileID: posterUrl,
              },
            };
          }

          if (!posterUrl.startsWith("http")) {
            await markTaskFailedWithRefund({
              taskId,
              task,
              errMsg: "生成的图片链接无效",
            });
            return { success: false, errMsg: "生成结果异常，请重试" };
          }

          let imageBuffer;
          try {
            const imageRes = await axios.get(posterUrl, {
              responseType: "arraybuffer",
              timeout: 30000,
              maxContentLength: 50 * 1024 * 1024,
            });
            imageBuffer = Buffer.from(imageRes.data);
          } catch (downloadErr) {
            console.error("下载海报失败:", downloadErr.message);
            await markTaskFailedWithRefund({
              taskId,
              task,
              errMsg: "海报下载失败",
            });
            return { success: false, errMsg: "海报下载失败，请重试" };
          }

          let uploadResult;
          try {
            uploadResult = await cloud.uploadFile({
              cloudPath: `ai-posters/${taskId}.png`,
              fileContent: imageBuffer,
            });
          } catch (uploadErr) {
            console.error("云存储上传失败:", uploadErr.message);
            await markTaskFailedWithRefund({
              taskId,
              task,
              errMsg: "图片上传失败",
            });
            return { success: false, errMsg: "图片上传失败，请重试" };
          }

          await db.collection(JOBS_COLLECTION).doc(taskId).update({
            data: {
              status: "completed",
              posterFileID: uploadResult.fileID,
              updatedAt: Date.now(),
            },
          });

          const result = {
            success: true,
            data: {
              status: "completed",
              posterFileID: uploadResult.fileID,
            },
          };
          return result;
        } else if (serverStatus === "failed") {
          await markTaskFailedWithRefund({
            taskId,
            task,
            errMsg: errMsg || "生成失败",
          });

          return {
            success: true,
            data: {
              status: "failed",
              errMsg: errMsg || "生成失败",
            },
          };
        }
      } catch (e) {
        const statusCode = e.response?.status;
        const responseDetail = e.response?.data?.detail || e.response?.data?.errMsg || "";
        console.error("查询服务端失败:", {
          code: e.code,
          statusCode,
          message: e.message,
          responseDetail,
          taskId,
          serverTaskId: task.serverTaskId,
        });
        
        if (statusCode === 404) {
          await markTaskFailedWithRefund({
            taskId,
            task,
            errMsg: "服务端任务不存在或已过期",
          });
          return { success: true, data: { status: "failed", errMsg: "任务已过期，请重试" } };
        }

        if (statusCode >= 400 && statusCode < 500) {
          await markTaskFailedWithRefund({
            taskId,
            task,
            errMsg: responseDetail || "服务端任务状态异常",
          });
          return { success: true, data: { status: "failed", errMsg: responseDetail || "生成失败，请重试" } };
        }

        if (e.code === "ECONNABORTED" || e.code === "ETIMEDOUT" || e.code === "ENOTFOUND" || e.code === "EAI_AGAIN" || e.code === "ECONNREFUSED" || e.code === "ECONNRESET" || statusCode >= 500 || !e.response) {
          return {
            success: true,
            data: {
              status: task.status,
              posterFileID: task.posterFileID,
              errMsg: e.code ? `服务端暂时不可用，请稍后重试（${e.code}）` : "服务端暂时不可用，请稍后重试",
            }
          };
        }
      }
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

const cleanupStaleTasks = async () => {
  try {
    const staleThreshold = Date.now() - STALE_TASK_TIMEOUT_MS;

    const staleTasks = await db.collection(JOBS_COLLECTION)
      .where({
        status: "pending",
        createdAt: _.lt(staleThreshold),
      })
      .limit(100)
      .get();

    let cleanedCount = 0;

    for (const task of staleTasks.data || []) {
      try {
        await markTaskFailedWithRefund({
          taskId: task._id,
          task,
          errMsg: "任务超时，自动取消",
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
    case "cleanupStaleTasks":
      return await cleanupStaleTasks(event);
    default:
      return { success: false, errMsg: `未知的操作类型: ${event.type}` };
  }
};
