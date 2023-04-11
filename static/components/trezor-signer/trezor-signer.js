async function trezorSigner(path) {
  const template = await loadTemplateAsync(path)
  Vue.component('trezor-signer', {
    name: 'trezor-signer',
    template,

    computed: {},

    data: function () {
      return {
        features: null,
        featuresJson: null,
        showFeatures: false,
        isConecting: false
      }
    },

    methods: {
      connectToDevice: async function () {
        try {
          this.isConecting = true
          this.features = await TrezorConnect.getFeatures()
          this.featuresJson = JSON.stringify(this.features, null, 2)
          this.showFeatures = true
        } catch (err) {
          this.showFeatures = false
        } finally {
          this.isConecting = false
        }
      }
    },

    created: async function () {}
  })
}
