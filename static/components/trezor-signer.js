window.app.component('trezor-signer', {
  name: 'trezor-signer',
  template: '#trezor-signer',
  props: ['sats-denominated', 'network'],
  delimiters: ['${', '}'],
  data: function () {
    return {
      features: null,
      featuresJson: null,
      showFeatures: false,
      connected: false,
      isConnecting: false,
      xpubData: {xpub: null, fingerprint: null}
    }
  },

  methods: {
    connectToDevice: async function () {
      try {
        this.isConnecting = true
        this.features = await TrezorConnect.getFeatures()
        this.featuresJson = JSON.stringify(this.features, null, 2)
        this.showFeatures = true
        this.connected = true
        this.$emit('device:connected', 'trezor-device')
      } catch (err) {
        this.showFeatures = false
        this.connected = false
      } finally {
        this.isConnecting = false
      }
    },

    isConnected: function () {
      return this.connected
    },
    isTaprootSupported: function () {
      return true
    },
    isAuthenticated: async function () {
      return true
    },
    hwwXpub: async function (accountPath) {
      const coin = this.network === 'Mainnet' ? 'btc' : 'test'
      const data = await TrezorConnect.getPublicKey({
        path: accountPath,
        showOnTrezor: true,
        coin
      })
      if (!data.success) {
        throw new Error(data.payload.error)
      }
      this.xpubData = {
        xpub: data.payload.xpub,
        fingerprint: data.payload.fingerprint.toString(16)
      }
    },
    isFetchingXpub: async function () {
      return this.xpubData
    },
    hwwSendPsbt: async function (_, txData) {
      const coin = this.network === 'Mainnet' ? 'btc' : 'test'
      const inputs = txData.inputs.map(input => ({
        address_n: mapDerivationPathToTrezor(
          `${input.accountPath}/${input.branch_index}/${input.address_index}`
        ),
        prev_index: input.vout,
        prev_hash: input.tx_id,
        amount: input.amount,
        script_type: mapInputAccountTypeToTrezor(input.accountType)
      }))
      const outputs = txData.outputs.map(out => {
        const o = {
          amount: out.amount,
          script_type: 'PAYTOADDRESS'
        }
        if (out.accountPath) {
          o.address_n = mapDerivationPathToTrezor(
            `${out.accountPath}/${out.branch_index}/${out.address_index}`
          )
        } else {
          o.address = out.address
        }
        if (out.accountType) {
          o.script_type = mapOutputAccountTypeToTrezor(out.accountType)
        }
        return o
      })
      const tx = {
        coin,
        inputs,
        outputs
      }
      const data = await TrezorConnect.signTransaction(tx)
      if (!data.success) {
        throw new Error(data.payload.error)
      }
      this.$emit('signed:tx', {
        serializedTx: data.payload.serializedTx,
        feeValue: txData.feeValue
      })
    },
    isSendingPsbt: function () {
      return false
    },
    hwwShowPasswordDialog: function () {}
  },

  created: async function () {}
})
