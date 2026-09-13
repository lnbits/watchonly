const assert = require('node:assert/strict')
const {readFileSync} = require('node:fs')
const {resolve} = require('node:path')
const {test} = require('node:test')
const vm = require('node:vm')
const {webcrypto} = require('node:crypto')

function harness(name = 'serial-signer', trezor = {}) {
  const components = {}
  const logs = []
  const events = []
  const timers = []
  const context = vm.createContext({
    TextEncoder,
    TextDecoder,
    Uint8Array,
    crypto: webcrypto,
    setTimeout(fn, timeout) {
      timers.push(timeout)
      return setTimeout(fn, timeout)
    },
    clearTimeout,
    console: {log: (...args) => logs.push(args)},
    TrezorConnect: trezor,
    LNbits: {utils: {}},
    document: {getElementById: () => null}
  })
  context.window = context
  context.app = {
    component: (name, component) => {
      components[name] = component
    }
  }
  for (const file of [
    'js/utils.js',
    'js/map.js',
    'js/crypto/noble-secp256k1.js',
    'js/crypto/aes.js',
    `components/${name}.js`
  ]) {
    vm.runInContext(
      readFileSync(resolve(__dirname, '../static', file), 'utf8'),
      context
    )
  }
  const component = components[name]
  const instance = {
    ...component.data(),
    network: 'Testnet',
    $q: {notify() {}},
    $emit: (...args) => events.push(args)
  }
  for (const [key, method] of Object.entries(component.methods))
    instance[key] = method.bind(instance)
  return {instance, logs, events, timers}
}

const transaction = () => ({
  inputs: [
    {
      accountPath: "m/84'/1'/0'",
      accountType: 'p2wpkh',
      branch_index: 0,
      address_index: 1,
      tx_id: 'ab'.repeat(32),
      vout: 0,
      amount: 10000
    }
  ],
  outputs: [{address: 'recipient', amount: 9000}],
  feeValue: 1000,
  feeRate: 2
})

test('Bowser uploads acknowledged chunks and signs only after physical review', async () => {
  const {instance: signer, events} = harness()
  signer.hww.authenticated = true
  const commands = []
  const chunks = []
  let releaseReview
  signer.sendCommandSecure = async (command, args) => {
    commands.push(command)
    if (command === '/psbt-begin') {
      await signer.handleSerialPortResponse(
        command,
        `1 ${Math.ceil(args[1] / 64)}`
      )
    } else if (command === '/psbt-chunk') {
      assert.ok(args[1].length <= 64)
      chunks.push(args[1])
      await signer.handleSerialPortResponse(command, `1 ${args[0]}`)
    } else if (command === '/psbt-commit') {
      await signer.handleSerialPortResponse('/psbt-review', 'output 0 1')
      releaseReview = () => signer.handleSerialPortResponse(command, '1')
    } else if (command === '/sign') {
      await signer.handleSerialPortResponse('/psbt-review', 'sign')
      await signer.handleSerialPortResponse(command, '1 cHNidP8signed')
    }
  }
  const psbt = 'cHNidP8' + 'A'.repeat(140)
  const signing = signer.hwwSendPsbt(psbt, transaction())
  while (!releaseReview) await new Promise(resolve => setImmediate(resolve))
  assert.equal(chunks.join(''), psbt)
  assert.equal(signer.hww.confirm.stage, 'output')
  assert.ok(!commands.includes('/sign'))
  await signer.handleSerialPortResponse('/psbt-review', 'output 9 1')
  assert.equal(signer.hww.confirm.outputIndex, 0)
  await signer.handleSerialPortResponse('/psbt-review', 'fee')
  assert.equal(signer.hww.confirm.showFee, true)
  await releaseReview()
  await signing
  assert.deepEqual(events, [['signed:psbt', 'cHNidP8signed']])
  assert.ok(!commands.includes('/confirm-next'))
  assert.equal(signer.hww.showConfirmationDialog, false)
})

for (const [failureAt, response] of [
  ['/psbt-begin', '0 no_memory'],
  ['/psbt-chunk', '1 99'],
  ['/psbt-commit', 'review_rejected'],
  ['/sign', 'review_rejected']
]) {
  test(`Bowser stops on ${failureAt} rejection`, async () => {
    const {instance: signer, events} = harness()
    signer.hww.authenticated = true
    const commands = []
    signer.sendCommandSecure = async command => {
      commands.push(command)
      const replies = {
        '/psbt-begin': '1 1',
        '/psbt-chunk': '1 0',
        '/psbt-commit': '1'
      }
      await signer.handleSerialPortResponse(
        command,
        command === failureAt ? response : replies[command]
      )
    }
    await assert.rejects(signer.hwwSendPsbt('cHNidP8', transaction()))
    assert.equal(commands.at(-1), failureAt)
    assert.equal(events.length, 0)
    assert.equal(signer.hww.sendingPsbt, false)
    assert.equal(signer.hww.signingPsbt, false)
    assert.deepEqual(Object.keys(signer.pendingCommands), [])
  })
}

test('Bowser enforces its size/count limits without sending data', async () => {
  const {instance: signer} = harness()
  signer.hww.authenticated = true
  signer.sendCommandSecure = () => assert.fail('must not send')
  await assert.rejects(
    signer.hwwSendPsbt('A'.repeat(16385), transaction()),
    /16,384/
  )
  await assert.rejects(
    signer.hwwSendPsbt('cHNidP8', {
      ...transaction(),
      inputs: Array(65).fill({})
    }),
    /64 inputs/
  )
})

test('Bowser request failures settle on timeout, disconnect, reboot and write error', async () => {
  for (const mode of ['timeout', 'disconnect', 'reboot', 'write']) {
    const {instance: signer} = harness()
    signer.sendCommandSecure = async () => {
      if (mode === 'write') throw new Error('write failed')
    }
    const response = signer.requestCommand('/psbt-commit', [], 5)
    const rejected = assert.rejects(response)
    if (mode === 'disconnect')
      signer.failPendingCommands(new Error('disconnected'))
    if (mode === 'reboot')
      await signer.handleSerialPortResponse('/password-clear', '1')
    await rejected
    assert.deepEqual(Object.keys(signer.pendingCommands), [])
  }
})

test('Bowser recognizes plaintext transfer/review and empty-wallet messages', async () => {
  const {instance: signer} = harness()
  signer.decryptData = () => assert.fail('plaintext must not be decrypted')
  for (const line of [
    '/psbt-begin 1 2',
    '/psbt-chunk 1 0',
    '/psbt-review output 0 1',
    '/new'
  ]) {
    const parsed = await signer.extractCommand(line)
    assert.equal(parsed.command, line.split(' ')[0])
  }
})

test('Bowser unlock and xpub handle immediate responses without resolver races', async () => {
  const {instance: signer, timers} = harness()
  signer.sendCommandSecure = async (command, args) => {
    if (command === '/password') {
      assert.deepEqual(Array.from(args), ['test-password', ''])
      await signer.handleSerialPortResponse(command, '1')
    } else
      await signer.handleSerialPortResponse(command, '1 tpubExample 00112233')
  }
  await signer.hwwShowPasswordDialog()
  signer.hww.password = 'test-password'
  const login = signer.isAuthenticating()
  await signer.hwwLogin()
  assert.equal(await login, true)
  assert.ok(timers.includes(120000))
  await signer.hwwXpub("m/84'/1'/0'")
  assert.equal((await signer.isFetchingXpub()).fingerprint, '00112233')
  assert.equal(signer.hww.password, null)
})

test('canceling Bowser unlock settles the waiting payment', async () => {
  const {instance: signer} = harness()
  await signer.hwwShowPasswordDialog()
  const login = signer.isAuthenticating()
  signer.passwordDialogClosed()
  assert.equal(await login, false)
})

test('Bowser encrypted framing preserves UTF-8 passphrases', async () => {
  const {instance: signer} = harness()
  signer.sharedSecret = new Uint8Array(32).fill(1)
  let written
  signer.writer = {
    write: async value => {
      written = value.trim()
    }
  }
  await signer.sendCommandSecure('/password', [
    'test-password',
    'caf\u00e9 space'
  ])
  assert.equal(
    await signer.decryptData(written),
    '/password test-password caf\u00e9 space'
  )
})

test('Bowser keeps seed acknowledgements on-device and omits response data from logs', async () => {
  const {instance: signer, logs} = harness()
  signer.handleShowSeedResponse('24 displayed')
  assert.equal(signer.hww.seedWordPosition, 24)
  assert.equal(signer.hww.seedWord, null)
  signer.logPublicCommandsResponse('/xpub', 'private test payload')
  await signer.handleSerialPortResponse('/log', 'private test payload')
  assert.ok(!JSON.stringify(logs).includes('private test payload'))
})

for (const network of ['Mainnet', 'Testnet']) {
  for (const [accountType, inputType, outputType] of [
    ['p2pkh', 'SPENDADDRESS', 'PAYTOADDRESS'],
    ['p2sh', 'SPENDP2SHWITNESS', 'PAYTOP2SHWITNESS'],
    ['p2wpkh', 'SPENDWITNESS', 'PAYTOWITNESS'],
    ['p2tr', 'SPENDTAPROOT', 'PAYTOTAPROOT']
  ]) {
    test(`Trezor ${network} ${accountType} retains its native signing contract`, async () => {
      let submitted
      const {instance: signer, events} = harness('trezor-signer', {
        signTransaction: async tx => {
          submitted = tx
          return {success: true, payload: {serializedTx: 'signed-trezor-tx'}}
        }
      })
      signer.network = network
      const tx = transaction()
      tx.inputs[0].accountType = accountType
      tx.outputs.push({
        accountPath: tx.inputs[0].accountPath,
        branch_index: 1,
        address_index: 0,
        accountType,
        amount: 100
      })
      await signer.hwwSendPsbt('ignored PSBT', tx)
      assert.equal(submitted.coin, network === 'Mainnet' ? 'btc' : 'test')
      assert.equal(submitted.inputs[0].script_type, inputType)
      assert.equal(submitted.outputs[1].script_type, outputType)
      assert.equal(submitted.outputs[0].address, 'recipient')
      assert.equal(events[0][0], 'signed:tx')
      assert.equal(events[0][1].serializedTx, 'signed-trezor-tx')
      assert.equal(events[0][1].feeValue, 1000)
    })
  }
}
