const cloud = require("wx-server-sdk");
const axios = require("axios");

cloud.init({
  env: cloud.DYNAMIC_CURRENT_ENV,
});

const db = cloud.database();
const JOBS_COLLECTION = "ai_poster_jobs";

let _collectionReady = false;

const ensureCollection = async () => {
  if (_collectionReady) return;
  
  try {
    await db.createCollection(JOBS_COLLECTION);
  } catch (e) {
    if (e.errCode !== -501001) {
      throw new Error(`数据库初始化失败: ${e.message || e.errCode}`);
    }
  }
  _collectionReady = true;
};

const validateImage = async (fileID, type) => {
  const tempFileResult = await cloud.getTempFileURL({ fileList: [fileID] });
  
  if (!tempFileResult.fileList || tempFileResult.fileList.length === 0) {
    return { passed: false, reason: "获取图片链接失败" };
  }
  
  const fileInfo = tempFileResult.fileList[0];
  if (fileInfo.status !== 0) {
    return { passed: false, reason: "图片链接生成失败: " + (fileInfo.errMsg || "未知错误") };
  }
  
  const imageUrl = fileInfo.tempFileURL;

  const prompt =
    type === "palm"
      ? "这张图片是否包含清晰的手掌照片？请只回答'是'或'否'。"
      : "这张图片是否包含清晰的正面人像照片？请只回答'是'或'否'。";

  try {
    const res = await axios.post(
      "http://36.156.154.98:8010/v1/chat/completions",
      {
        model: "qwen3.6",
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
      reason: hasNo ? "图片不符合要求，请重新拍摄" : "",
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
    
    const { type, fileID, test } = event.data;

    if (!type || !fileID) {
      return { success: false, errMsg: "缺少必要参数" };
    }

    if (!["palm", "hair"].includes(type)) {
      return { success: false, errMsg: "无效的类型参数" };
    }

    const validation = await validateImage(fileID, type);
    if (!validation.passed) {
      await cloud.deleteFile({ fileList: [fileID] }).catch(() => {});
      return { success: false, errMsg: validation.reason };
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
        test: test || false
      }, { 
        timeout: 10000,
        validateStatus: (status) => status < 500
      });
    } catch (serverErr) {
      console.error("调用服务端失败:", serverErr.code, serverErr.message);
      
      if (serverErr.code === "ECONNABORTED") {
        return { success: false, errMsg: "连接服务端超时，请稍后重试" };
      }
      if (serverErr.code === "ENOTFOUND" || serverErr.code === "ECONNREFUSED") {
        return { success: false, errMsg: "服务端不可用，请稍后重试" };
      }
      
      return { success: false, errMsg: "网络异常，请检查网络后重试" };
    }

    if (serverResp.status !== 200) {
      return { success: false, errMsg: `服务端错误（${serverResp.status}): 请稍后重试` };
    }

    const serverTaskId = serverResp.data?.taskId;
    if (!serverTaskId) {
      return { success: false, errMsg: "服务端返回无效任务ID" };
    }

    const wxContext = cloud.getWXContext();
    const openid = wxContext.OPENID;

    const taskResult = await db.collection(JOBS_COLLECTION).add({
      data: {
        type,
        fileID,
        serverTaskId,
        status: "pending",
        posterFileID: null,
        errMsg: "",
        openid,
        createdAt: Date.now(),
        updatedAt: Date.now(),
      },
    });

    const taskId = taskResult._id;

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

    if (task.status === "pending") {
      const SERVER_URL = process.env.POSTER_SERVER_URL || "http://36.156.154.98:8011";
      
      if (!task.serverTaskId) {
        await db.collection(JOBS_COLLECTION).doc(taskId).update({
          data: { 
            status: "failed", 
            errMsg: "任务配置错误，缺少服务端任务ID", 
            updatedAt: Date.now() 
          }
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

        if (serverStatus === "completed" && posterUrl) {
          if (!posterUrl.startsWith("http")) {
            await db.collection(JOBS_COLLECTION).doc(taskId).update({
              data: { 
                status: "failed", 
                errMsg: "生成的图片链接无效", 
                updatedAt: Date.now() 
              }
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
            await db.collection(JOBS_COLLECTION).doc(taskId).update({
              data: { 
                status: "failed", 
                errMsg: "海报下载失败", 
                updatedAt: Date.now() 
              }
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
            await db.collection(JOBS_COLLECTION).doc(taskId).update({
              data: { 
                status: "failed", 
                errMsg: "图片上传失败", 
                updatedAt: Date.now() 
              }
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
          await db.collection(JOBS_COLLECTION).doc(taskId).update({
            data: {
              status: "failed",
              errMsg: errMsg || "生成失败",
              updatedAt: Date.now(),
            },
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
        console.error("查询服务端失败:", e.code, e.message);
        
        if (e.code === "ECONNABORTED" || e.code === "ENOTFOUND" || e.code === "ECONNREFUSED") {
          return {
            success: true,
            data: {
              status: task.status,
              posterFileID: task.posterFileID,
              errMsg: "服务端暂时不可用，请稍后重试",
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

exports.main = async (event, context) => {
  switch (event.type) {
    case "validateAndCreateJob":
      return await validateAndCreateJob(event);
    case "getTaskStatus":
      return await getTaskStatus(event);
    default:
      return { success: false, errMsg: `未知的操作类型: ${event.type}` };
  }
};