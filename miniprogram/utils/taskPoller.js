const DEFAULT_INITIAL_DELAY_MS = 5000;
const DEFAULT_MAX_DELAY_MS = 15000;
const DEFAULT_MAX_DURATION_MS = 15 * 60 * 1000;

function isActiveTaskStatus(status) {
  return status === "init" || status === "pending" || status === "processing";
}

function createTaskPoller(options) {
  const initialDelay = options.initialDelay || DEFAULT_INITIAL_DELAY_MS;
  const maxDelay = options.maxDelay || DEFAULT_MAX_DELAY_MS;
  const maxDuration = options.maxDuration || DEFAULT_MAX_DURATION_MS;

  let taskId = "";
  let timer = null;
  let startedAt = 0;
  let currentDelay = initialDelay;
  let lastStatus = "";
  let polling = false;
  let inFlight = false;
  let runId = 0;

  const clearTimer = () => {
    if (timer) {
      clearTimeout(timer);
      timer = null;
    }
  };

  const stop = () => {
    polling = false;
    inFlight = false;
    runId++;
    clearTimer();
  };

  const scheduleNext = (pollOnce) => {
    if (!polling) return;

    clearTimer();
    timer = setTimeout(pollOnce, currentDelay);
    currentDelay = Math.min(currentDelay * 2, maxDelay);
  };

  const pollOnce = async () => {
    if (!polling || !taskId || inFlight) return;

    const activeRunId = runId;
    const activeTaskId = taskId;

    if (Date.now() - startedAt > maxDuration) {
      stop();
      if (options.onTimeout) options.onTimeout();
      return;
    }

    inFlight = true;

    try {
      const resp = await wx.cloud.callFunction({
        name: "quickstartFunctions",
        data: {
          type: "getTaskStatus",
          data: { taskId: activeTaskId },
        },
      });

      if (!polling || taskId !== activeTaskId || runId !== activeRunId) return;

      if (!resp.result || !resp.result.success) {
        stop();
        if (options.onError) options.onError(resp.result?.errMsg || "获取状态失败");
        return;
      }

      const taskStatus = resp.result.data || {};

      if (taskStatus.status !== lastStatus) {
        lastStatus = taskStatus.status;
        currentDelay = initialDelay;
      }

      if (options.onStatus) await options.onStatus(taskStatus);

      if (isActiveTaskStatus(taskStatus.status)) {
        scheduleNext(pollOnce);
        return;
      }

      stop();
    } catch (err) {
      if (!polling || taskId !== activeTaskId || runId !== activeRunId) return;
      if (options.onTransientError) options.onTransientError(err);
      scheduleNext(pollOnce);
    } finally {
      inFlight = false;
    }
  };

  const start = (nextTaskId) => {
    if (!nextTaskId) return;

    if (polling && taskId === nextTaskId) return;

    stop();
    taskId = nextTaskId;
    startedAt = Date.now();
    currentDelay = initialDelay;
    lastStatus = "";
    polling = true;
    pollOnce();
  };

  const pause = () => {
    polling = false;
    clearTimer();
  };

  const resume = () => {
    if (!taskId || polling) return;
    polling = true;
    pollOnce();
  };

  const reset = () => {
    stop();
    taskId = "";
    startedAt = 0;
    currentDelay = initialDelay;
    lastStatus = "";
  };

  return {
    start,
    stop,
    pause,
    resume,
    reset,
    isPolling() {
      return polling;
    },
    getTaskId() {
      return taskId;
    },
  };
}

module.exports = {
  createTaskPoller,
  isActiveTaskStatus,
};
