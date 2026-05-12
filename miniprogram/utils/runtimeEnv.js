function getMiniProgramEnvVersion() {
  try {
    return wx.getAccountInfoSync?.().miniProgram?.envVersion || "release";
  } catch (err) {
    return "release";
  }
}

function isDevelopVersion() {
  return getMiniProgramEnvVersion() === "develop";
}

module.exports = {
  getMiniProgramEnvVersion,
  isDevelopVersion,
};
