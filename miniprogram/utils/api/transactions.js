const { callCloudRun } = require("../cloudrunClient");
const { buildQuery, createBusinessError, getApiErrorMessage } = require("./errors");

async function fetchTransactions({ page = 1, pageSize = 10 } = {}) {
  const resp = await callCloudRun({
    path: `/miniapp/transactions${buildQuery({ page, pageSize })}`,
    method: "GET",
  });

  if (resp.data?.success) {
    return resp.data.data;
  }

  throw createBusinessError(getApiErrorMessage(resp, "获取积分明细失败"));
}

module.exports = {
  fetchTransactions,
};
