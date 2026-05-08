const { cloud, db, POINT_TRANSACTIONS_COLLECTION } = require("./cloudbase");
const { ensureCollection } = require("./collections");

const toPublicTransaction = (transaction) => ({
  _id: transaction._id,
  type: transaction.type,
  amount: transaction.amount,
  balanceAfter: transaction.balanceAfter,
  reason: transaction.reason,
  taskId: transaction.taskId || null,
  createdAt: transaction.createdAt,
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

module.exports = {
  createPointTransaction,
  getTransactions,
  toPublicTransaction,
};
