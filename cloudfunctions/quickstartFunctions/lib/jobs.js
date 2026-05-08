const axios = require("axios");
const {
  cloud,
  db,
  _,
  JOBS_COLLECTION,
  FEATURE_CONFIGS_COLLECTION,
} = require("./cloudbase");
const { ensureCollection } = require("./collections");
const { ensureUser } = require("./users");

const toPublicTask = (task) => ({
  _id: task._id,
  type: task.type,
  featureTitle: task.featureTitle || "",
  featureHomeDesc: task.featureHomeDesc || "",
  featureDescription: task.featureDescription || "",
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
        featureTitle: featureConfig.public?.title || "",
        featureHomeDesc: featureConfig.public?.homeDesc || "",
        featureDescription: featureConfig.public?.description || "",
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

    const task = taskDoc.data;
    if (task.status === "init" || task.status === "pending" || task.status === "processing") {
      return { success: false, errMsg: "进行中的任务不能删除" };
    }

    if (task.posterFileID) {
      try {
        await cloud.deleteFile({ fileList: [task.posterFileID] });
      } catch (e) {
        console.warn("删除海报文件失败（继续删除数据库记录）:", e.message);
      }
    }

    await db.collection(JOBS_COLLECTION).doc(taskId).remove();

    return { success: true, data: { taskId } };
  } catch (e) {
    console.error("deleteTask 错误:", e.message);
    return { success: false, errMsg: e.message || "删除任务失败" };
  }
};

const STALE_TASK_TIMEOUT_MS = 15 * 60 * 1000;

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

module.exports = {
  cleanupStaleTasks,
  deleteTask,
  getTask,
  getTasks,
  getTaskStatus,
  toPublicTask,
  validateAndCreateJob,
  validateImage,
};
