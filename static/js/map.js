const mapAddressesData = a => ({
  id: a.id,
  address: a.address,
  amount: a.amount,
  wallet: a.wallet,
  note: a.note,

  isChange: a.branch_index === 1,
  addressIndex: a.address_index,
  hasActivity: a.has_activity
})

const mapInputToSentHistory = (tx, addressData, prevOut, meta = {}) => ({
  sent: true,
  txId: tx.txid,
  address: addressData.address,
  isChange: addressData.isChange,
  amount: Math.round(prevOut.value * 1e8),
  height: meta.height,
  confirmed: (meta.height || 0) > 0,
  fee: meta.fee,
  expanded: false
})

const mapOutputToReceiveHistory = (tx, addressData, vout, meta = {}) => ({
  received: true,
  txId: tx.txid,
  address: addressData.address,
  isChange: addressData.isChange,
  amount: Math.round(vout.value * 1e8),
  height: meta.height,
  confirmed: (meta.height || 0) > 0,
  fee: meta.fee,
  expanded: false
})

const mapUtxoToPsbtInput = utxo => ({
  tx_id: utxo.txId,
  vout: utxo.vout,
  amount: utxo.amount,
  address: utxo.address,
  branch_index: utxo.isChange ? 1 : 0,
  address_index: utxo.addressIndex,
  wallet: utxo.wallet,
  accountType: utxo.accountType,
  accountPath: utxo.accountPath,
  txHex: ''
})

const mapAddressDataToUtxo = (wallet, addressData, utxo) => ({
  id: addressData.id,
  address: addressData.address,
  isChange: addressData.isChange,
  addressIndex: addressData.addressIndex,
  wallet: addressData.wallet,
  accountType: addressData.accountType,
  accountPath: wallet.meta.accountPath,
  masterpubFingerprint: wallet.fingerprint,
  txId: utxo.tx_hash,
  vout: utxo.tx_pos,
  confirmed: utxo.height > 0,
  amount: utxo.value,
  height: utxo.height,
  sort: utxo.height,
  expanded: false,
  selected: false
})

const mapWalletAccount = function (o) {
  return Object.assign({}, o, {
    date: o.time
      ? Quasar.utils.date.formatDate(
          new Date(o.time * 1000),
          'YYYY-MM-DD HH:mm'
        )
      : '',
    meta: o.meta ? JSON.parse(o.meta) : null,
    label: o.title,
    expanded: false
  })
}

const mapDerivationPathToTrezor = function (path = '') {
  return path
    .split('/')
    .filter(p => p !== 'm')
    .map(p => (p.endsWith("'") ? +p.slice(0, -1) | 0x80000000 : +p))
}

const mapOutputAccountTypeToTrezor = function (accountType) {
  switch (accountType) {
    case 'p2pkh':
      return 'PAYTOADDRESS'
    case 'p2wpkh':
      return 'PAYTOWITNESS'
    case 'p2sh':
      return 'PAYTOP2SHWITNESS'
    case 'p2tr':
      return 'PAYTOTAPROOT'
    default:
      return undefined
  }
}

const mapInputAccountTypeToTrezor = function (accountType) {
  switch (accountType) {
    case 'p2pkh':
      return 'SPENDADDRESS'
    case 'p2wpkh':
      return 'SPENDWITNESS'
    case 'p2sh':
      return 'SPENDP2SHWITNESS'
    case 'p2tr':
      return 'SPENDTAPROOT'
    default:
      return undefined
  }
}
