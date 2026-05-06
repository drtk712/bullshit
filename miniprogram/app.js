// app.js
App({
  onLaunch: function () {
    this.globalData = {
      env: "cloud1-d7g1nt83fde793ad3",
      testMode: false,
      skipPointsDeduction: false,
    };
    if (!wx.cloud) {
      console.error("请使用 2.2.3 或以上的基础库以使用云能力");
    } else {
      wx.cloud.init({
        env: this.globalData.env,
        traceUser: true,
      });
    }
  },
});
