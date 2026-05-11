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
  fileIDs: Array.isArray(task.fileIDs) ? task.fileIDs : [],
  posterFileID: task.posterFileID || null,
  resultMode: task.resultMode || "single",
  resultFileIDs: Array.isArray(task.resultFileIDs) ? task.resultFileIDs : [],
  errMsg: task.errMsg || "",
  pointsCost: task.pointsCost || 0,
  pointsConsumed: !!task.pointsConsumed,
  pointsRefunded: !!task.pointsRefunded,
  createdAt: task.createdAt,
  updatedAt: task.updatedAt,
});

const toSharedTask = (task, taskId) => ({
  _id: task._id || taskId,
  type: task.type,
  featureTitle: task.featureTitle || "",
  featureHomeDesc: task.featureHomeDesc || "",
  featureDescription: task.featureDescription || "",
  status: task.status,
  posterFileID: task.posterFileID || null,
  createdAt: task.createdAt,
});

const normalizeJobParam = (input) => {
  if (!input || typeof input !== "object" || Array.isArray(input)) return {};

  return Object.entries(input).reduce((acc, [key, value]) => {
    if (!/^[a-zA-Z0-9_]{1,32}$/.test(String(key))) return acc;
    const text = String(value ?? "").trim();
    if (!text) return acc;
    acc[key] = text.slice(0, 200);
    return acc;
  }, {});
};

const MULTI_IMAGE_TYPES = new Set(["long_image"]);

const normalizeFileIDs = (input) => {
  const values = Array.isArray(input) ? input : [input];
  return values
    .map((item) => String(item || "").trim())
    .filter((item) => item.startsWith("cloud://"))
    .slice(0, 9);
};

const resolveTempFileUrls = async (fileIDs) => {
  const tempFileResult = await cloud.getTempFileURL({ fileList: fileIDs });

  if (!tempFileResult.fileList || tempFileResult.fileList.length === 0) {
    throw new Error("获取图片链接失败");
  }

  const urlMap = {};
  for (const fileInfo of tempFileResult.fileList) {
    if (fileInfo.status !== 0 || !fileInfo.tempFileURL) {
      throw new Error("图片链接生成失败");
    }
    urlMap[fileInfo.fileID] = fileInfo.tempFileURL;
  }

  const imageUrls = fileIDs.map((fileID) => urlMap[fileID]).filter(Boolean);
  if (imageUrls.length !== fileIDs.length) {
    throw new Error("图片链接生成失败");
  }
  return imageUrls;
};

const getTasks = async (event) => {
  try {
    const wxContext = cloud.getWXContext();
    const openid = wxContext.OPENID;
    await ensureCollection();

    const page = Math.max(1, parseInt(event.data?.page) || 1);
    const pageSize = Math.min(50, Math.max(1, parseInt(event.data?.pageSize) || 20));
    const filter = String(event.data?.filter || "all");
    const skip = (page - 1) * pageSize;
    const query = { openid };

    if (["pending", "processing", "completed", "failed"].includes(filter)) {
      query.status = filter;
    }

    const countResult = await db.collection(JOBS_COLLECTION)
      .where(query)
      .count();

    const result = await db.collection(JOBS_COLLECTION)
      .where(query)
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

const getSharedTask = async (event) => {
  try {
    const { taskId } = event.data || {};

    if (!taskId) {
      return { success: false, errMsg: "缺少任务ID" };
    }

    await ensureCollection();

    const taskDoc = await db.collection(JOBS_COLLECTION).doc(taskId).get();
    const task = taskDoc.data;

    if (!task || task.status !== "completed" || !task.posterFileID) {
      return { success: false, errMsg: "作品暂不可查看" };
    }

    return {
      success: true,
      data: {
        task: toSharedTask(task, taskId),
      },
    };
  } catch (e) {
    console.error("getSharedTask 错误:", e.message);
    return { success: false, errMsg: e.message || "获取分享作品失败" };
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

const stripThinkingText = (content) => {
  let answerText = String(content || "");
  const tagIndex = answerText.lastIndexOf("</think>");
  if (tagIndex > -1) {
    answerText = answerText.slice(tagIndex + "</think>".length);
  }
  return answerText.trim();
};

const buildValidationPrompt = (requirement) => `
快速的分析这张图片是否符合下面的要求。
要求：${String(requirement || "").trim()}

如果符合，请只回答：
是

如果不符合，请回答：
否｜原因：一句简短中文原因,不超过40个中文字符
`.trim();

const parseValidationResult = (content, fallbackReason) => {
  const fallback = fallbackReason || "图片不符合要求，请重新上传";
  const text = stripThinkingText(content)
    .replace(/\r/g, "\n")
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
    .join("");

  if (text.startsWith("是")) {
    return { passed: true, reason: "" };
  }

  if (text.startsWith("否")) {
    const reasonMatch = text.match(/原因\s*[:：]\s*(.+)$/) || text.match(/^否\s*[|｜]\s*(.+)$/);
    const rawReason = reasonMatch ? String(reasonMatch[1] || "") : "";
    const reason = rawReason.replace(/^原因\s*[:：]\s*/, "").trim().slice(0, 40);
    return { passed: false, reason: reason || fallback };
  }

  return { passed: false, reason: "验证服务响应格式异常，请稍后重试" };
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
  const prompt = buildValidationPrompt(validationConfig.prompt);

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

    return parseValidationResult(content, validationConfig.failMessage);
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
    const param = normalizeJobParam(event.data?.param);
    const isMultiImage = MULTI_IMAGE_TYPES.has(type);
    const fileIDs = normalizeFileIDs(isMultiImage ? event.data?.fileIDs : fileID);
    const primaryFileID = fileIDs[0] || "";

    if (!type || !primaryFileID || (isMultiImage && fileIDs.length < 2)) {
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
    const wxContext = cloud.getWXContext();
    const openid = wxContext.OPENID;
    const shouldConsumePoints = !skipPointsDeduction;
    const user = await ensureUser(openid);

    if (shouldConsumePoints && user.points < 1) {
      await cloud.deleteFile({ fileList: fileIDs }).catch(() => {});
      return { success: false, errMsg: "积分不足，请先获取积分" };
    }

    const validation = await validateImage(primaryFileID, featureConfig);
    if (!validation.passed) {
      await cloud.deleteFile({ fileList: fileIDs }).catch(() => {});
      return { success: false, errMsg: validation.reason };
    }

    const imageUrls = await resolveTempFileUrls(fileIDs);
    const imageUrl = imageUrls[0];

    const taskResult = await db.collection(JOBS_COLLECTION).add({
      data: {
        type,
        featureTitle: featureConfig.public?.title || "",
        featureHomeDesc: featureConfig.public?.homeDesc || "",
        featureDescription: featureConfig.public?.description || "",
        param,
        fileID: primaryFileID,
        fileIDs,
        serverTaskId: null,
        status: "init",
        posterFileID: null,
        resultMode: "single",
        resultFileIDs: [],
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
        imageUrls,
        sourceFileID: primaryFileID,
        sourceFileIDs: fileIDs,
        type,
        test: test || false,
        generationPrompt: featureConfig.generation?.prompt || "",
        param,
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
        resultMode: task.resultMode || "single",
        resultFileIDs: Array.isArray(task.resultFileIDs) ? task.resultFileIDs : [],
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

    const fileList = [
      task.posterFileID,
      ...(Array.isArray(task.resultFileIDs) ? task.resultFileIDs : []),
    ].filter(Boolean);

    if (fileList.length > 0) {
      try {
        await cloud.deleteFile({ fileList });
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
  getSharedTask,
  getTask,
  getTasks,
  getTaskStatus,
  toPublicTask,
  validateAndCreateJob,
  validateImage,
};
