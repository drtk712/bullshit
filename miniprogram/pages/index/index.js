Page({
  data: {
    powerList: [
      {
        title: "AI看手相",
        tip: "上传手掌照片，获取专属手相解读",
        page: "palm",
      },
      {
        title: "AI设计发型",
        tip: "上传正面照片，获取专属发型建议",
        page: "hair",
      },
    ],
  },

  onClickPowerInfo(e) {
    const { page } = e.currentTarget.dataset;
    if (page) {
      wx.navigateTo({
        url: `/pages/${page}/index`,
      });
    }
  },
});
