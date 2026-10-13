function getMiniProgramEnvVersion() {
  try {
    return wx.getAccountInfoSync?.().miniProgram?.envVersion || "release";
  } catch (err) {
    return "release";
  }
}

function isDevelopVersion() {
  //临时注释
  return getMiniProgramEnvVersion() === "develop";
  //return false;
}

module.exports = {
  getMiniProgramEnvVersion,
  isDevelopVersion,
};
