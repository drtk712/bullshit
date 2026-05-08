const {
  db,
  JOBS_COLLECTION,
  USERS_COLLECTION,
  POINT_TRANSACTIONS_COLLECTION,
} = require("./cloudbase");

let collectionReady = false;

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

const ensureCollection = async () => {
  if (collectionReady) return;

  try {
    await db.createCollection(JOBS_COLLECTION);
  } catch (e) {
    if (e.errCode !== -501001) {
      throw new Error(`数据库初始化失败: ${e.message || e.errCode}`);
    }
  }

  await ensureUserCollections();
  collectionReady = true;
};

module.exports = {
  ensureCollection,
  ensureUserCollections,
};
