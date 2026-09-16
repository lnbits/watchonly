# Bowser integration audit

Compared against the local reference repository at
`/home/ben/Projects/hardware-wallet`, commit `1a26051`. That repository was read
only and remains unchanged. This audit covers Watchonly's exposed Bowser flows
and the shared payment flow used by Trezor, rather than a firmware security audit.

## Reference and result

| Flow                  | Reference behavior                                                                                                          | Watchonly result                                                                                                                                                                                                                                                                               |
| --------------------- | --------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Connect/pair          | `webapp/src/lib/bowser.ts`: native serial streams, ping, ECDH pairing, user confirms fingerprint                            | Matching handshake, encrypted framing, pairing deadline errors, and cleanup covered by simulated serial tests using independent Node cryptography.                                                                                                                                             |
| Unlock/passphrase     | `/password` transmits the complete BIP39 passphrase; it selects the derived wallet                                          | Leading/trailing spaces and Unicode preserved. Login waits for acknowledgement, clears entered credentials, and ignores unsolicited login successes. Changing passphrase requires unlocking again and importing the resulting account. Existing accounts remain separate.                      |
| Account import        | `/xpub` returns public key and root fingerprint for network/path                                                            | Awaited response with strict status/fingerprint parsing. Invalid derivation components and indices outside the unhardened range are rejected. Testnet4 uses testnet hardware key derivation.                                                                                                   |
| Address verification  | `/address` must return success and the requested address                                                                    | Now waits for and checks the returned address; mismatches produce an address-specific error.                                                                                                                                                                                                   |
| Wipe/restore          | Await success, retain the paired connection; wipe opens seed backup at word 1                                               | Both now use timed requests. Only confirmed success updates authentication. Wipe then requests word 1; restore does not automatically start backup, matching the webapp. Password confirmation and minimum length/no-whitespace rules are checked before sending.                              |
| Seed backup           | `/seed` acknowledges a word displayed on hardware; words are never returned to the browser                                  | Navigation waits for acknowledgements, blocks repeated clicks, and bounds positions to 1–24. Hardware-button acknowledgements update an open backup dialog. Closed dialogs ignore late responses.                                                                                              |
| Logout/disconnect     | Await logout; reject outstanding work on disconnect/restart                                                                 | Logout now waits for confirmation. Connection cleanup releases streams, removes the disconnect listener, clears entered credentials, and closes device dialogs.                                                                                                                                |
| TRNG diagnostic       | `/trng` reports 5,000-sample aggregate statistics, then waits for physical Continue                                         | Matching command, timeout, validation, verdict, and explanatory text. Browser tests confirm readable results in dark/light themes. No raw entropy samples are requested.                                                                                                                       |
| PSBT transport/review | 64-character chunks with acknowledgements; physical review, then `/sign`                                                    | Transfer limits, chunk ordering, review rejection, timeouts, and on-device review progress covered. Errors no longer include raw device response payloads.                                                                                                                                     |
| Returned PSBT         | `webapp/src/lib/bitcoin.ts`: compare unsigned transaction, combine original metadata, validate partial signatures, finalize | Now binds the result to the reviewed PSBT, including version, locktime, ordered outpoints/sequences and outputs. Combines original metadata and verifies ECDSA as well as Taproot key signatures before finalization.                                                                          |
| Payment UI            | Only a successfully finalized transaction can be broadcast                                                                  | Failed builds clear stale PSBTs. Change is captured before asynchronous previous-transaction fetches. Finalization retains the expected PSBT, blocks overlapping work, clears stale results, and enables Send only with transaction hex. Imported PSBTs fetch their own previous transactions. |
| Trezor compatibility  | Separate Trezor Connect native transaction signing                                                                          | Native signing remains separate. Shared finalization/broadcast tests pass. Cancelled connections no longer report success; imported root fingerprints retain all eight hex digits.                                                                                                             |

## Verification

- 151 Python tests: PSBT creation/finalization/API, descriptors and address
  derivation, and network handling. Includes legacy, wrapped/native SegWit,
  multisig and Taproot vectors; corrupted signatures; supported sighashes;
  changed reviewed transactions; and both API field naming conventions.
- 87 JavaScript tests: 70 hardware adapter/serial tests, 9 payment tests, and
  8 network tests. Hardware adapter coverage includes Trezor on Mainnet,
  Testnet and Testnet4.
- Local Chromium with the real Vue/Quasar templates and a simulated serial
  device: pairing, wipe-to-backup, TRNG loading/healthy/unexpected results,
  disconnect, and dark/light table contrast. Passphrase input preservation
  checked separately.
- `UV_NO_SYNC=1 make checkblack checkruff`, workspace Prettier on the changed
  frontend/test files, and `git diff --check`.
- No generated bundles or dependencies changed. These extension assets are
  loaded directly, so no core bundle regeneration was needed.

## Boundaries and device checks still required

- No physical Bowser or Trezor was controlled by these automated checks, and
  no transaction was broadcast. Confirm pairing, unlock, account/address
  matching and signing on the devices after restarting LNbits and refreshing
  Watchonly. Destructive wipe/restore checks require a disposable test wallet.
- Bowser's separate dice-creation workflow and interactive multisig co-signing
  workflow are not exposed by Watchonly. An incompletely signed PSBT is not
  broadcast; it still reports that finalization is incomplete.
- Seed navigation follows the firmware/webapp's 24-position protocol. That
  protocol does not return the restored mnemonic's word count. A shorter
  restored mnemonic cannot be reliably bounded from the acknowledgement alone.
- As in the reference webapp, validation here checks available partial
  signatures. It is not a general Bitcoin script interpreter for imported
  already-finalized scripts. Taproot script-path spending is outside the
  supported BIP86 key-spend flow.
- An imported PSBT with no locally reviewed original cannot be compared with
  an earlier transaction. Its supplied previous transactions are still checked
  against its outpoints and witness UTXOs before finalization.

## Files changed

The integration fixes and their regression coverage are in `models.py`,
`psbt.py`, `views_api.py`, `static/components/serial-signer.js`,
`static/components/trezor-signer.js`, `static/components/payment.js`,
`static/js/utils.js`, `static/index.vue`, `static/i18n/en.js`,
`tests/hardware-signers.test.cjs`, `tests/payment-finalization.test.cjs`, and
`tests/test_psbt.py`. User guidance is in `README.md` and this audit record.
