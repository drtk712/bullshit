Component({
  properties: {
    title: {
      type: String,
      value: "",
    },
    showBack: {
      type: Boolean,
      value: true,
    },
    variant: {
      type: String,
      value: "detail",
    },
  },

  methods: {
    handleBack() {
      this.triggerEvent("back");
    },
  },
});
