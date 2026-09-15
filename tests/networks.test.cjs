const assert = require('node:assert/strict')
const {readFileSync} = require('node:fs')
const {resolve} = require('node:path')
const {test} = require('node:test')
const vm = require('node:vm')

async function harness() {
  const components = {}
  const endpoints = []
  const context = vm.createContext({
    URL,
    console,
    setTimeout: fn => fn(),
    Vue: {defineAsyncComponent: load => load()},
    LNbits: {utils: {loadScript: async () => {}}},
    tables: {},
    tableData: {utxos: {data: [], total: 0}},
    mempoolJS: ({hostname}) => {
      endpoints.push(hostname)
      return {
        bitcoin: {
          addresses: {
            getAddressTxs: async () => [],
            getAddressTxsUtxo: async () => []
          },
          fees: {getFeesRecommended: async () => ({halfHourFee: 1})}
        }
      }
    }
  })
  context.window = context
  context.trezor = {default: {}}
  context.app = {component: (name, component) => (components[name] = component)}
  for (const file of [
    'js/utils.js',
    'components/wallet-config.js',
    'components/wallet-list.js',
    'components/fee-rate.js',
    'index.js'
  ]) {
    vm.runInContext(
      readFileSync(resolve(__dirname, '../static', file), 'utf8'),
      context
    )
  }
  const page = await context.PageWatchonly
  const instance = {...page.data(), $emit() {}, $q: {notify() {}}}
  for (const [name, method] of Object.entries(page.methods))
    instance[name] = method.bind(instance)
  Object.defineProperty(instance, 'mempoolHostname', {
    get: () => page.computed.mempoolHostname.call(instance)
  })
  return {instance, page, components, endpoints}
}

for (const [network, path] of [
  ['Mainnet', ''],
  ['Testnet', '/testnet'],
  ['Testnet4', '/testnet4']
]) {
  test(`${network} routes scans and fees to the selected explorer`, async () => {
    const {instance, components, endpoints} = await harness()
    instance.config = {
      isLoaded: true,
      network,
      mempool_endpoint: 'https://mempool.space'
    }
    instance.walletAccounts = [{id: 'wallet'}]
    assert.equal(instance.mempoolHostname, `mempool.space${path}`)
    await instance.getAddressTxsDelayed({
      wallet: 'wallet',
      address: 'test-address'
    })
    await instance.getAddressTxsUtxoDelayed('test-address')
    await components['fee-rate'].methods.refreshRecommendedFees.call({
      mempoolEndpoint: instance.mempoolHostname
    })
    assert.deepEqual(endpoints, Array(3).fill(`mempool.space${path}`))
  })
}

test('network selector distinguishes Testnet3 and Testnet4, with testnet key paths', async () => {
  const {components} = await harness()
  const options = components['wallet-config'].data().networkOptions
  assert.equal(options.find(o => o.label === 'Testnet3').value, 'Testnet')
  assert.equal(options.find(o => o.label === 'Testnet4').value, 'Testnet4')
  const wallets = components['wallet-list']
  const instance = {...wallets.data(), network: 'Testnet4'}
  for (const type of instance.addressTypeOptions) {
    wallets.methods.handleAddressTypeChanged.call(instance, type)
    assert.equal(instance.accountPath, type.pathTestnet)
  }
})

for (const phase of ['history', 'utxos']) {
  test(`switching networks discards an in-flight ${phase} scan response`, async () => {
    const {instance, page} = await harness()
    instance.config = {network: 'Testnet'}
    instance.walletAccounts = [{id: 'old-wallet', network: 'Testnet'}]
    let release
    const pending = new Promise(resolve => (release = resolve))
    instance.getAddressTxsDelayed = async () =>
      phase === 'history' ? pending : [{address: 'old-chain'}]
    instance.getAddressTxsUtxoDelayed = async () => pending
    instance.updateUtxosForAddress = () =>
      assert.fail('stale UTXOs must not be saved')
    const scan = instance.updateUtxosForAddresses([{address: 'old-chain'}])
    await Promise.resolve()
    instance.config.network = 'Testnet4'
    page.watch['config.network'].call(instance)
    release([{address: 'old-chain'}])
    assert.equal(await scan, false)
    assert.equal(instance.history.length, 0)
    assert.equal(instance.walletAccounts.length, 0)
    assert.equal(instance.utxos.total, 0)
  })
}

test('network switch discards an old account-list response', async () => {
  const {components} = await harness()
  const wallets = components['wallet-list']
  let release
  const instance = {
    ...wallets.data(),
    network: 'Testnet',
    getWatchOnlyWallets: () => new Promise(resolve => (release = resolve)),
    $emit: () => assert.fail('old accounts must not be published')
  }
  const refresh = wallets.methods.refreshWalletAccounts.call(instance)
  instance.network = 'Testnet4'
  release([{network: 'Testnet'}])
  await refresh
  assert.equal(instance.walletAccounts.length, 0)
})

test('network switch discards an old address-list response', async () => {
  const {instance, page} = await harness()
  instance.config = {network: 'Testnet'}
  instance.walletAccounts = [{id: 'old-wallet', type: 'p2wpkh'}]
  let release
  instance.getAddressesForWallet = () =>
    new Promise(resolve => (release = resolve))
  const refresh = instance.refreshAddresses()
  instance.config.network = 'Testnet4'
  page.watch['config.network'].call(instance)
  release([{address: 'old-chain-address'}])
  await refresh
  assert.equal(instance.addresses.length, 0)
})
