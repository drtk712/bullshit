const cloud = require("wx-server-sdk");

cloud.init({
  env: cloud.DYNAMIC_CURRENT_ENV,
});

const db = cloud.database();
const _ = db.command;

const JOBS_COLLECTION = "ai_poster_jobs";
const USERS_COLLECTION = "users";
const POINT_TRANSACTIONS_COLLECTION = "point_transactions";
const FEATURE_CONFIGS_COLLECTION = "feature_configs";

module.exports = {
  cloud,
  db,
  _,
  JOBS_COLLECTION,
  USERS_COLLECTION,
  POINT_TRANSACTIONS_COLLECTION,
  FEATURE_CONFIGS_COLLECTION,
};
