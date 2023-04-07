async function serialPortConfig(path) {
  const t = await loadTemplateAsync(path)
  Vue.component('serial-port-config', {
    name: 'serial-port-config',
    props: ['config'],
    template: t,
    data() {
      return {}
    },
    methods: {},
    created: async function () {
      const accountPubKey = await TrezorConnect.getPublicKey({
        path: "m/49'/0'/0'",
        showOnTrezor: true,
        coin: 'btc'
      })

      console.log('### TrezorConnect.getPublicKey', accountPubKey)
    }
  })
}
