async function trezorSigner(path) {
  const template = await loadTemplateAsync(path)
  Vue.component('trezor-signer', {
    name: 'trezor-signer',
    template,
    props: ['sats-denominated', 'network'],
    data: function () {
      return {
        features: null,
        featuresJson: null,
        showFeatures: false,
        connected: false,
        isConecting: false,
        xpubData: {xpub: null, fingerprint: null}
      }
    },

    methods: {
      connectToDevice: async function () {
        try {
          this.isConecting = true
          this.features = await TrezorConnect.getFeatures()
          this.featuresJson = JSON.stringify(this.features, null, 2)
          this.showFeatures = true
          this.connected = true
          this.$emit('device:connected', 'trezor-device')
        } catch (err) {
          this.showFeatures = false
          this.connected = false
        } finally {
          this.isConecting = false
        }
      },

      isConnected: function () {
        return this.connected
      },
      isAuthenticated: async function () {
        return true
      },
      hwwXpub: async function (accountPath) {
        console.log('### hwwXpub', accountPath, this.network)
        const coin = this.network === 'Mainnet' ? 'btc' : 'test'
        const data = await TrezorConnect.getPublicKey({
          path: accountPath,
          showOnTrezor: true,
          coin
        })
        console.log('### pubkey', data)
        this.xpubData = {
          xpub: data.payload.xpubSegwit || data.payload.xpub,
          fingerprint: data.payload.fingerprint.toString(16)
        }
      },
      isFetchingXpub: async function () {
        console.log('### isFetchingXpub')
        return this.xpubData
      },
      hwwSendPsbt: function (psbtBase64, txData) {
        console.log('### hwwSendPsbt', psbtBase64, txData)
      },
      isSendingPsbt: function () {
        console.log('### isSendingPsbt')
      },
      hwwShowPasswordDialog: function () {
        console.warn('### hwwShowPasswordDialog: not implemented')
      }
    },

    created: async function () {}
  })
}
