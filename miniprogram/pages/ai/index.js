const { createAiPage } = require("../../utils/aiPage");
const { fetchFeature } = require("../../utils/featureConfigClient");

Page({
  ...createAiPage(),

  async onLoad(options) {
    const type = options.type;
    if (!type) {
      this.setData({ configLoading: false, configError: "缺少功能类型" });
      return;
    }

    const feature = await fetchFeature(type);
    if (!feature) {
      this.setData({ configLoading: false, configError: "功能暂不可用" });
      return;
    }

    this.setFeature(feature);
    wx.setNavigationBarTitle({ title: feature.title });
  },
});
