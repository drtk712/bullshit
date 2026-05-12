function getApiErrorMessage(resp, fallback) {
  return resp?.data?.errMsg
    || resp?.data?.detail
    || resp?.data?.message
    || resp?.errMsg
    || fallback;
}

function createBusinessError(message) {
  const error = new Error(message);
  error.isBusinessError = true;
  return error;
}

function buildQuery(params = {}) {
  const pairs = Object.keys(params)
    .filter((key) => params[key] !== undefined && params[key] !== null && params[key] !== "")
    .map((key) => `${encodeURIComponent(key)}=${encodeURIComponent(params[key])}`);
  return pairs.length ? `?${pairs.join("&")}` : "";
}

module.exports = {
  buildQuery,
  createBusinessError,
  getApiErrorMessage,
};
