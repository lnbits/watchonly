window.app.component('serial-signer', {
  name: 'serial-signer',
  template: '#serial-signer',

  props: ['sats-denominated', 'network'],
  data: function () {
    return {
      selectedPort: null,
      writableStreamClosed: null,
      writer: null,
      readableStreamClosed: null,
      reader: null,
      closingSerialPort: false,
      receivedData: '',
      config: {},
      decryptionKey: null,
      sharedSecret: null,
      pendingCommands: {},
      loginPromise: null,
      loginResolve: null,
      xpubData: {},

      hww: {
        password: null,
        showPassword: false,
        mnemonic: null,
        showMnemonic: false,
        quickMnemonicInput: false,
        passphrase: null,
        showPassphrase: false,
        hasPassphrase: false,
        authenticated: false,
        loggingIn: false,
        showPasswordDialog: false,
        showConfigDialog: false,
        showWipeDialog: false,
        showRestoreDialog: false,
        showConfirmationDialog: false,
        showSignedPsbt: false,
        sendingPsbt: false,
        signingPsbt: false,
        seedWordPosition: 1,
        seedWord: null,
        showSeedWord: false,
        showSeedDialog: false,
        // config: null,

        confirm: {
          outputIndex: 0,
          showFee: false,
          stage: ''
        }
      },
      tx: null, // todo: move to hww

      showConsole: false
    }
  },

  methods: {
    satBtc(val, showUnit = true) {
      return satOrBtc(val, showUnit, this.satsDenominated)
    },
    openSerialPortDialog: async function () {
      this.config = {...HWW_DEFAULT_CONFIG}
      await this.openSerialPort(this.config)
    },
    openSerialPort: async function (config = {baudRate: 9600}) {
      if (!this.checkSerialPortSupported()) return false
      if (this.selectedPort) {
        this.$q.notify({
          type: 'warning',
          message: 'Already connected. Disconnect first!',
          timeout: 10000
        })
        return true
      }

      try {
        this.selectedPort = await navigator.serial.requestPort()
        this.selectedPort.addEventListener('connect', event => {
          // do nothing
        })

        this.selectedPort.addEventListener('disconnect', () => {
          this.failPendingCommands(new Error('Serial device disconnected'))
          this.selectedPort = null
          this.sharedSecret = null
          this.decryptionKey = null
          this.hww.authenticated = false
          this.$q.notify({
            type: 'warning',
            message: 'Disconnected from Serial Port!',
            timeout: 10000
          })
        })

        // Wait for the serial port to open.
        await this.selectedPort.open(config)
        // do not await
        this.startSerialPortReading()
        // wait to init
        await sleep(1000)

        const textEncoder = new TextEncoderStream()
        this.writableStreamClosed = textEncoder.readable.pipeTo(
          this.selectedPort.writable
        )

        this.writer = textEncoder.writable.getWriter()

        await this.hwwPing()

        return true
      } catch (error) {
        this.selectedPort = null
        this.$q.notify({
          type: 'warning',
          message: 'Cannot open serial port!',
          caption: `${error}`,
          timeout: 10000
        })
        return false
      }
    },
    openSerialPortConfig: async function () {
      this.config = {...HWW_DEFAULT_CONFIG}
      this.hww.showConfigDialog = true
    },
    closeSerialPort: async function () {
      this.closingSerialPort = true
      try {
        if (this.writer) await this.writer.close()
        if (this.writableStreamClosed) await this.writableStreamClosed
        if (this.reader) await this.reader.cancel()
        if (this.readableStreamClosed)
          await this.readableStreamClosed.catch(() => {
            /* Ignore the error */
          })
        if (this.selectedPort) await this.selectedPort.close()
        this.$q.notify({
          type: 'positive',
          message: 'Serial port disconnected!',
          timeout: 5000
        })
      } catch (error) {
        this.$q.notify({
          type: 'warning',
          message: 'Cannot close serial port!',
          caption: `${error}`,
          timeout: 10000
        })
      } finally {
        this.failPendingCommands(new Error('Serial connection closed'))
        this.selectedPort = null
        this.writer = null
        this.reader = null
        this.writableStreamClosed = null
        this.readableStreamClosed = null
        this.sharedSecret = null
        this.decryptionKey = null
        this.hww.authenticated = false
        this.closingSerialPort = false
      }
    },

    isConnected: function () {
      return !!this.selectedPort
    },
    isTaprootSupported: function () {
      return true
    },
    isAuthenticated: function () {
      return this.hww.authenticated
    },

    seedInputDone: function (mnemonic) {
      this.hww.mnemonic = mnemonic
    },
    isAuthenticating: function () {
      return this.isAuthenticated() ? Promise.resolve(true) : this.loginPromise
    },

    isSendingPsbt: async function () {
      return false
    },

    isFetchingXpub: async function () {
      return this.xpubData
    },

    checkSerialPortSupported: function () {
      if (!navigator.serial) {
        this.$q.notify({
          type: 'warning',
          message: 'Serial port communication not supported!',
          caption:
            'Make sure your browser supports Serial Port and that you are using HTTPS.',
          timeout: 10000
        })
        return false
      }
      return true
    },
    startSerialPortReading: async function () {
      const port = this.selectedPort

      while (port && port.readable) {
        const textDecoder = new TextDecoderStream()
        this.readableStreamClosed = port.readable.pipeTo(textDecoder.writable)
        this.reader = textDecoder.readable.getReader()
        const readStringUntil = readFromSerialPort(this.reader)

        try {
          while (true) {
            const {value, done} = await readStringUntil('\n')
            if (value) {
              const {command, commandData} = await this.extractCommand(value)
              await this.handleSerialPortResponse(command, commandData)
              this.updateSerialPortConsole(command)
            }
            if (done) {
              this.failPendingCommands(new Error('Serial device disconnected'))
              return
            }
          }
        } catch (error) {
          this.failPendingCommands(error)
          if (!this.closingSerialPort && this.selectedPort === port) {
            this.$q.notify({
              type: 'warning',
              message: 'Serial port communication error!',
              caption: `${error}`,
              timeout: 10000
            })
          }
          return
        }
      }
    },
    handleSerialPortResponse: async function (command, commandData) {
      this.logPublicCommandsResponse(command, commandData)
      const pending = this.pendingCommands[command]
      if (pending) {
        clearTimeout(pending.timer)
        delete this.pendingCommands[command]
        pending.resolve(commandData)
        return
      }

      switch (command) {
        case COMMAND_PING:
          await this.handlePingResponse(commandData)
          break
        case COMMAND_PASSWORD:
          this.handleLoginResponse(commandData)
          break
        case COMMAND_PASSWORD_CLEAR:
          this.handleLogoutResponse(commandData)
          break
        case COMMAND_PSBT_REVIEW:
          this.handlePsbtReview(commandData)
          break
        case COMMAND_WIPE:
          this.handleWipeResponse(commandData)
          break
        case COMMAND_RESTORE:
          this.handleRestoreResponse(commandData)
          break
        case COMMAND_SEED:
          this.handleShowSeedResponse(commandData)
          break
        case COMMAND_PAIR:
          await this.handlePairResponse(commandData)
          break
        case COMMAND_LOG:
          break
        case COMMAND_NEW:
          this.hww.authenticated = false
          break
        default:
          console.log(`   %c${command}`, 'background: #222; color: red')
      }
    },
    logPublicCommandsResponse: function (command, commandData) {
      switch (command) {
        case COMMAND_SIGN_PSBT:
        case COMMAND_PASSWORD:
        case COMMAND_PASSWORD_CLEAR:
        case COMMAND_SEND_PSBT:
        case COMMAND_WIPE:
        case COMMAND_XPUB:
        case COMMAND_PAIR:
          console.log(`   %c${command}`, 'background: #222; color: yellow')
      }
    },
    updateSerialPortConsole: function (value) {
      this.receivedData += value + '\n'
      const textArea = document.getElementById('serial-port-console')
      if (textArea) textArea.scrollTop = textArea.scrollHeight
    },
    hwwPing: async function () {
      try {
        await this.sendCommandClearText(COMMAND_PING, [window.location.host])
      } catch (error) {
        this.$q.notify({
          type: 'warning',
          message: 'Failed to ping Hardware Wallet!',
          caption: `${error}`,
          timeout: 10000
        })
      }
    },
    handlePingResponse: async function (res = '') {
      const [status, deviceId] = res.split(' ')
      this.deviceId = deviceId

      if (!this.deviceId) {
        this.$q.notify({
          type: 'warning',
          message: 'Missing device ID for Hardware Wallet',
          timeout: 10000
        })
        return
      }

      await this.hwwPair()
    },
    hwwShowPasswordDialog: async function () {
      this.loginPromise = new Promise(resolve => {
        this.loginResolve = resolve
      })
      this.hww.showPasswordDialog = true
    },
    passwordDialogClosed: function () {
      if (!this.hww.loggingIn && this.loginResolve) {
        this.loginResolve(false)
        this.loginResolve = null
      }
    },
    hwwShowWipeDialog: async function () {
      try {
        this.hww.showWipeDialog = true
        await this.sendCommandSecure(COMMAND_WIPE)
      } catch (error) {
        this.$q.notify({
          type: 'warning',
          message: 'Failed to connect to Hardware Wallet!',
          caption: `${error}`,
          timeout: 10000
        })
      }
    },
    hwwShowRestoreDialog: async function () {
      try {
        this.hww.showRestoreDialog = true
        await this.sendCommandSecure(COMMAND_RESTORE)
      } catch (error) {
        this.$q.notify({
          type: 'warning',
          message: 'Failed to connect to Hardware Wallet!',
          caption: `${error}`,
          timeout: 10000
        })
      }
    },
    closeSeedDialog: function () {
      this.hww.seedWord = null
      this.hww.showSeedWord = false
    },
    cancelOperation: async function () {
      try {
        await this.sendCommandSecure(COMMAND_CANCEL)
      } catch (error) {
        this.$q.notify({
          type: 'warning',
          message: 'Failed to send cancel!',
          caption: `${error}`,
          timeout: 10000
        })
      }
    },
    hwwConfigAndConnect: async function () {
      this.hww.showConfigDialog = false
      await this.openSerialPort(this.config)
      return true
    },
    hwwLogin: async function () {
      if (this.hww.loggingIn) return
      this.hww.loggingIn = true
      try {
        const response = await this.requestCommand(
          COMMAND_PASSWORD,
          [
            this.hww.password,
            this.hww.hasPassphrase ? this.hww.passphrase || '' : ''
          ],
          120000
        )
        this.handleLoginResponse(response)
      } catch (error) {
        this.hww.authenticated = false
        if (this.loginResolve) this.loginResolve(false)
        this.$q.notify({
          type: 'warning',
          message: 'Failed to send password to Hardware Wallet!',
          caption: `${error}`,
          timeout: 10000
        })
      } finally {
        this.loginResolve = null
        this.hww.loggingIn = false
        this.hww.showPasswordDialog = false
        this.hww.password = null
        this.hww.passphrase = null
        this.hww.showPassword = false
        this.hww.showPassphrase = false
      }
    },
    handleLoginResponse: function (res = '') {
      this.hww.authenticated = res.trim() === '1'
      if (this.loginResolve) {
        this.loginResolve(this.hww.authenticated)
      }

      if (this.hww.authenticated) {
        this.$q.notify({
          type: 'positive',
          message: 'Login successfull!',
          timeout: 10000
        })
      } else {
        this.$q.notify({
          type: 'warning',
          message: 'Wrong password, try again!',
          timeout: 10000
        })
      }
    },
    hwwLogout: async function () {
      try {
        await this.sendCommandSecure(COMMAND_PASSWORD_CLEAR)
      } catch (error) {
        this.$q.notify({
          type: 'warning',
          message: 'Failed to logout from Hardware Wallet!',
          caption: `${error}`,
          timeout: 10000
        })
      }
    },
    hwwShowAddress: async function (path, address) {
      try {
        await this.sendCommandSecure(COMMAND_ADDRESS, [
          getSigningNetwork(this.network),
          path,
          address
        ])
      } catch (error) {
        this.$q.notify({
          type: 'warning',
          message: 'Failed to logout from Hardware Wallet!',
          caption: `${error}`,
          timeout: 10000
        })
      }
    },
    handleLogoutResponse: function (res = '') {
      if (this.hww.authenticated) {
        this.$q.notify({
          type: 'positive',
          message: 'Logged Out',
          timeout: 10000
        })
      }
      this.failPendingCommands(new Error('Bowser Wallet locked or restarted'))
    },
    hwwSendPsbt: async function (psbtBase64, tx) {
      if (!this.hww.authenticated) throw new Error('Unlock Bowser Wallet first')
      if (this.hww.sendingPsbt || this.hww.signingPsbt) {
        throw new Error('A signing operation is already in progress')
      }
      if (!psbtBase64 || psbtBase64.length > 16384) {
        throw new Error('Bowser PSBT must fit within 16,384 base64 characters')
      }
      if (tx.inputs.length > 64 || tx.outputs.length > 64) {
        throw new Error('Bowser supports at most 64 inputs and 64 outputs')
      }
      try {
        this.tx = tx
        this.hww.sendingPsbt = true
        this.hww.confirm = {outputIndex: 0, showFee: false, stage: 'transfer'}
        this.hww.showConfirmationDialog = true
        const count = Math.ceil(psbtBase64.length / 64)
        const started = await this.requestCommand(COMMAND_PSBT_BEGIN, [
          getSigningNetwork(this.network),
          psbtBase64.length
        ])
        if (started !== `1 ${count}`)
          throw new Error(`PSBT transfer refused: ${started}`)
        for (let index = 0; index < count; index++) {
          const response = await this.requestCommand(COMMAND_PSBT_CHUNK, [
            index,
            psbtBase64.slice(index * 64, (index + 1) * 64)
          ])
          if (response !== `1 ${index}`)
            throw new Error(`PSBT chunk rejected: ${response}`)
        }
        this.hww.confirm.stage = 'review'
        const reviewed = await this.requestCommand(
          COMMAND_PSBT_COMMIT,
          [],
          15 * 60000
        )
        if (reviewed !== '1') throw new Error(`PSBT review failed: ${reviewed}`)
        this.hww.sendingPsbt = false
        await this.hwwSignPsbt()
      } finally {
        this.hww.sendingPsbt = false
        this.hww.signingPsbt = false
        this.hww.showConfirmationDialog = false
        this.tx = null
      }
    },
    handlePsbtReview: function (res = '') {
      if (!this.tx || (!this.hww.sendingPsbt && !this.hww.signingPsbt)) return
      const [stage, index, total] = res.split(' ')
      if (
        stage === 'output' &&
        /^\d+$/.test(index) &&
        +index < this.tx.outputs.length &&
        +total === this.tx.outputs.length
      ) {
        this.hww.confirm = {outputIndex: +index, showFee: false, stage}
      } else if (res === 'fee' || res === 'sign') {
        this.hww.confirm.showFee = true
        this.hww.confirm.stage = res
      }
    },
    hwwSignPsbt: async function () {
      this.hww.signingPsbt = true
      this.hww.confirm.stage = 'sign'
      const res = await this.requestCommand(COMMAND_SIGN_PSBT, [], 120000)
      const [count, psbt] = res.trim().split(' ')
      if (
        !/^\d+$/.test(count) ||
        +count < 1 ||
        !psbt?.startsWith(PSBT_BASE64_PREFIX)
      ) {
        throw new Error(`PSBT signing failed: ${res}`)
      }
      this.updateSignedPsbt(psbt)
      this.$q.notify({
        type: 'positive',
        message: 'Transaction Signed',
        caption: `Inputs signed: ${count}`,
        timeout: 10000
      })
    },
    hwwPair: async function () {
      try {
        this.decryptionKey = nobleSecp256k1.utils.randomPrivateKey()
        const publicKey = nobleSecp256k1.Point.fromPrivateKey(
          this.decryptionKey
        )
        const publicKeyHex = publicKey.toHex().slice(2)

        await this.sendCommandClearText(COMMAND_PAIR, [publicKeyHex])
        this.$q.notify({
          type: 'positive',
          message: 'Pairing started!',
          timeout: 5000
        })
      } catch (error) {
        this.$q.notify({
          type: 'warning',
          message: 'Failed to pair with device!',
          caption: `${error}`,
          timeout: 10000
        })
      }
    },
    handlePairResponse: async function (res = '') {
      const [statusCode, data] = res.trim().split(' ')
      let pubKeyHex, errorMessage, captionMessage
      switch (statusCode) {
        case '0':
          pubKeyHex = data
          if (!data) errorMessage = 'Failed to exchange DH secret!'
          break
        case '1':
          if (data === 'connection_period_expired') {
            errorMessage =
              'Device pairing only possible during the startup countdown!'
            captionMessage = 'Restart the device and try again'
          } else if (data === 'rng_failure') {
            errorMessage = 'Device hardware RNG health check failed!'
            captionMessage = 'Pairing was safely refused by the device'
          } else {
            errorMessage = 'Device refused pairing'
            captionMessage = data || 'Unknown device error'
          }
          break

        default:
          errorMessage = 'Unexpected error code'
          break
      }

      if (errorMessage) {
        this.$q.notify({
          type: 'warning',
          message: errorMessage,
          caption: captionMessage || '',
          timeout: 10000
        })
        this.closeSerialPort()
        return
      }
      const hwwPublicKey = nobleSecp256k1.Point.fromHex('04' + pubKeyHex)

      this.sharedSecret = nobleSecp256k1
        .getSharedSecret(this.decryptionKey, hwwPublicKey)
        .slice(1, 33)

      const sharedSecretHex = nobleSecp256k1.utils.bytesToHex(this.sharedSecret)
      const sharedSecredHash = await nobleSecp256k1.utils.sha256(
        asciiToUint8Array(sharedSecretHex)
      )
      const fingerprint = nobleSecp256k1.utils
        .bytesToHex(sharedSecredHash)
        .substring(0, 5)
        .toUpperCase()

      LNbits.utils
        .confirmDialog('Confirm code from display: ' + fingerprint)
        .onOk(() => {
          this.$emit('device:connected', 'usb-device')
          this.$q.notify({
            type: 'positive',
            message: 'Paired with device!',
            timeout: 5000
          })
        })
        .onCancel(() => {
          this.closeSerialPort()
        })
    },
    hwwHelp: async function () {
      try {
        await this.sendCommandSecure(COMMAND_HELP)
        this.$q.notify({
          type: 'positive',
          message: 'Check display or console for details!',
          timeout: 5000
        })
      } catch (error) {
        this.$q.notify({
          type: 'warning',
          message: 'Failed to ask for help!',
          caption: `${error}`,
          timeout: 10000
        })
      }
    },
    hwwWipe: async function () {
      try {
        this.hww.showWipeDialog = false
        await this.sendCommandSecure(COMMAND_WIPE, [this.hww.password])
      } catch (error) {
        this.$q.notify({
          type: 'warning',
          message: 'Failed to wipe!',
          caption: `${error}`,
          timeout: 10000
        })
      } finally {
        this.hww.password = null
        this.hww.confirmedPassword = null
        this.hww.showPassword = false
      }
    },
    handleWipeResponse: function (res = '') {
      const wiped = res.trim() === '1'
      this.hww.authenticated = wiped
      if (wiped) {
        this.xpubData = {}
        this.$q.notify({
          type: 'positive',
          message: 'Wallet wiped!',
          timeout: 10000
        })
      } else {
        this.$q.notify({
          type: 'warning',
          message: 'Failed to wipe wallet!',
          timeout: 10000
        })
      }
    },
    hwwXpub: async function (path) {
      this.xpubData = {}
      const res = await this.requestCommand(COMMAND_XPUB, [
        getSigningNetwork(this.network),
        path
      ])
      const args = res.trim().split(' ')
      if (args.length < 3 || args[0].trim() !== '1') {
        throw new Error(`Failed to fetch XPub: ${res}`)
      }
      const xpub = args[1].trim()
      const fingerprint = args[2].trim()
      this.xpubData = {xpub, fingerprint}
    },

    hwwShowSeed: async function () {
      try {
        this.hww.showSeedDialog = true
        this.hww.seedWordPosition = 1

        await this.sendCommandSecure(COMMAND_SEED, [this.hww.seedWordPosition])
      } catch (error) {
        this.$q.notify({
          type: 'warning',
          message: 'Failed to show seed!',
          caption: `${error}`,
          timeout: 10000
        })
      }
    },
    showNextSeedWord: async function () {
      this.hww.seedWordPosition++
      await this.sendCommandSecure(COMMAND_SEED, [this.hww.seedWordPosition])
    },
    showPrevSeedWord: async function () {
      this.hww.seedWordPosition = Math.max(1, this.hww.seedWordPosition - 1)
      await this.sendCommandSecure(COMMAND_SEED, [this.hww.seedWordPosition])
    },
    handleShowSeedResponse: function (res = '') {
      const [pos, status] = res.trim().split(' ')
      this.hww.seedWord = null
      if (
        status === 'displayed' &&
        /^\d+$/.test(pos) &&
        +pos >= 1 &&
        +pos <= 24
      ) {
        this.hww.seedWordPosition = +pos
      }
    },
    hwwRestore: async function () {
      try {
        await this.sendCommandSecure(COMMAND_RESTORE, [
          this.hww.password,
          this.hww.mnemonic
        ])
      } catch (error) {
        this.$q.notify({
          type: 'warning',
          message: 'Failed to restore from seed!',
          caption: `${error}`,
          timeout: 10000
        })
      } finally {
        this.hww.showRestoreDialog = false
        this.hww.mnemonic = null
        this.hww.showMnemonic = false
        this.hww.password = null
        this.hww.confirmedPassword = null
        this.hww.showPassword = false
      }
    },

    handleRestoreResponse: function (res = '') {
      const restored = res.trim() === '1'
      this.hww.authenticated = restored
      if (restored) this.xpubData = {}
      this.$q.notify({
        type: restored ? 'positive' : 'warning',
        message: restored ? 'Wallet restored!' : 'Failed to restore wallet!',
        timeout: 10000
      })
    },

    updateSignedPsbt: async function (value) {
      this.$emit('signed:psbt', value)
    },

    requestCommand: function (command, attrs = [], timeout = 20000) {
      if (this.pendingCommands[command])
        return Promise.reject(new Error(`${command} is already pending`))
      return new Promise((resolve, reject) => {
        const fail = error => {
          const pending = this.pendingCommands[command]
          if (!pending) return
          clearTimeout(pending.timer)
          delete this.pendingCommands[command]
          reject(error)
        }
        const timer = setTimeout(
          () => fail(new Error(`${command} timed out`)),
          timeout
        )
        this.pendingCommands[command] = {resolve, reject, timer}
        this.sendCommandSecure(command, attrs).catch(fail)
      })
    },
    failPendingCommands: function (error) {
      for (const pending of Object.values(this.pendingCommands)) {
        clearTimeout(pending.timer)
        pending.reject(error)
      }
      this.pendingCommands = {}
      if (this.loginResolve) this.loginResolve(false)
      this.loginResolve = null
      this.hww.authenticated = false
      this.hww.sendingPsbt = false
      this.hww.signingPsbt = false
      this.hww.showConfirmationDialog = false
    },

    sendCommandSecure: async function (command, attrs = []) {
      const message = [command].concat(attrs).join(' ')
      const iv = window.crypto.getRandomValues(new Uint8Array(16))
      if (!this.sharedSecret || !this.sharedSecret.length) {
        throw new Error(
          `Secure connection not estabileshed. Tried to run command: ${command}`
        )
      }
      const encrypted = await this.encryptMessage(
        this.sharedSecret,
        iv,
        new TextEncoder().encode(message).length + ' ' + message
      )

      const encryptedHex = nobleSecp256k1.utils.bytesToHex(encrypted)
      const encryptedIvHex = nobleSecp256k1.utils.bytesToHex(iv)
      await this.writer.write(encryptedHex + encryptedIvHex + '\n')
    },
    sendCommandClearText: async function (command, attrs = []) {
      const message = [command].concat(attrs).join(' ')
      await this.writer.write(message + '\n')
    },
    extractCommand: async function (value) {
      const command = value.split(' ')[0]
      const commandData = value.substring(command.length).trim()

      if (
        command === COMMAND_PAIR ||
        command === COMMAND_LOG ||
        command === COMMAND_NEW ||
        command === COMMAND_PSBT_BEGIN ||
        command === COMMAND_PSBT_CHUNK ||
        command === COMMAND_PSBT_REVIEW ||
        command === COMMAND_PASSWORD_CLEAR ||
        command === COMMAND_PING
      )
        return {command, commandData}

      const decryptedValue = await this.decryptData(value)
      const decryptedCommand = decryptedValue.split(' ')[0]
      const decryptedCommandData = decryptedValue
        .substring(decryptedCommand.length)
        .trim()
      return {
        command: decryptedCommand,
        commandData: decryptedCommandData
      }
    },
    decryptData: async function (value) {
      if (!this.sharedSecret) {
        console.log('/error Secure session not established!')
        return '/error Secure session not established!'
      }
      try {
        const ivSize = 32
        const messageHex = value.substring(0, value.length - ivSize)
        const ivHex = value.substring(value.length - ivSize)
        const messageBytes = nobleSecp256k1.utils.hexToBytes(messageHex)
        const iv = nobleSecp256k1.utils.hexToBytes(ivHex)
        const decrypted1 = await this.decryptMessage(
          this.sharedSecret,
          iv,
          messageBytes
        )
        const separator = decrypted1.indexOf(32)
        const lengthText = new TextDecoder().decode(
          decrypted1.slice(0, separator)
        )
        const length = Number(lengthText)
        if (
          separator < 1 ||
          !/^\d+$/.test(lengthText) ||
          !Number.isSafeInteger(length) ||
          separator + 1 + length > decrypted1.length
        ) {
          throw new Error('Invalid encrypted response length')
        }
        return new TextDecoder().decode(
          decrypted1.slice(separator + 1, separator + 1 + length)
        )
      } catch (error) {
        console.log('/error Failed to decrypt message from device!')
        return '/error Failed to decrypt message from device!'
      }
    },
    encryptMessage: async function (key, iv, message) {
      const bytes = new TextEncoder().encode(message)
      const encodedMessage = new Uint8Array(
        Math.ceil(bytes.length / 16) * 16
      ).fill(32)
      encodedMessage.set(bytes)

      const aesCbc = new aesjs.ModeOfOperation.cbc(key, iv)
      const encryptedBytes = aesCbc.encrypt(encodedMessage)

      return encryptedBytes
    },
    decryptMessage: async function (key, iv, encryptedBytes) {
      const aesCbc = new aesjs.ModeOfOperation.cbc(key, iv)
      const decryptedBytes = aesCbc.decrypt(encryptedBytes)
      return decryptedBytes
    }
  },
  created: async function () {
    window.localStorage.removeItem('lnbits-paired-devices')
  }
})
