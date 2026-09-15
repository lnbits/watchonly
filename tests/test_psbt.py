import pytest
from embit import bip32, script
from embit.descriptor import Descriptor
from embit.networks import NETWORKS
from embit.psbt import PSBT
from embit.transaction import SIGHASH, Transaction, TransactionInput, TransactionOutput

from .. import views_api
from ..models import CreatePsbt, ExtractPsbt
from ..psbt import create_psbt, finalize_signed_psbt


def signing_data(kind="wpkh", network="test"):
    root = bip32.HDKey.from_seed(bytes(range(32)), version=NETWORKS[network]["xprv"])
    purpose = {"pkh": 44, "sh": 49, "wpkh": 84, "tr": 86}[kind]
    path = f"m/{purpose}h/{0 if network == 'main' else 1}h/0h"
    account = root.derive(path).to_public()
    key = f"[{root.my_fingerprint.hex()}/{path[2:]}]{account}/{{0,1}}/*"
    descriptor_text = f"sh(wpkh({key}))" if kind == "sh" else f"{kind}({key})"
    descriptor = Descriptor.from_string(descriptor_text)
    spent = descriptor.derive(0, 0)
    previous = Transaction(
        vin=[TransactionInput(bytes(32), 0)],
        vout=[TransactionOutput(100000, spent.script_pubkey())],
    )
    change = descriptor.derive(3, 1)
    recipient = script.p2wpkh(root.derive("m/123").get_public_key())
    data = CreatePsbt(
        masterpubs=[
            {
                "id": "wallet",
                "public_key": descriptor_text,
                "fingerprint": root.my_fingerprint.hex(),
            }
        ],
        inputs=[
            {
                "tx_id": previous.txid().hex(),
                "vout": 0,
                "amount": 100000,
                "address": spent.address(NETWORKS[network]),
                "branch_index": 0,
                "address_index": 0,
                "wallet": "wallet",
                "tx_hex": previous.to_string(),
            }
        ],
        outputs=[
            {"amount": 40000, "address": recipient.address(NETWORKS[network])},
            {
                "amount": 59000,
                "address": change.address(NETWORKS[network]),
                "wallet": "wallet",
                "branch_index": 1,
                "address_index": 3,
            },
        ],
        fee_rate=1,
        tx_size=200,
    )
    return root, descriptor, data


@pytest.mark.parametrize("network", ["main", "test"])
@pytest.mark.parametrize("kind", ["pkh", "sh", "wpkh", "tr"])
def test_signing_metadata_and_finalization(kind, network):
    root, descriptor, data = signing_data(kind, network)
    psbt = PSBT.from_base64(create_psbt(data).to_string())
    assert psbt.fee() == 1000
    assert psbt.inputs[0].redeem_script == descriptor.derive(0, 0).redeem_script()
    assert (psbt.inputs[0].witness_utxo is not None) == (kind != "pkh")
    assert (psbt.inputs[0].non_witness_utxo is not None) == (kind == "pkh")
    assert not psbt.outputs[0].bip32_derivations
    assert not psbt.outputs[0].taproot_bip32_derivations
    if kind == "tr":
        assert psbt.inputs[0].taproot_internal_key is not None
        assert not psbt.inputs[0].bip32_derivations
        paths = psbt.outputs[1].taproot_bip32_derivations
        derivation = next(iter(paths.values()))[1]
    else:
        derivation = next(iter(psbt.outputs[1].bip32_derivations.values()))
    assert derivation.fingerprint == root.my_fingerprint
    assert derivation.derivation[-2:] == [1, 3]
    assert psbt.sign_with(root) == 1
    if kind == "tr":
        # libwally returns PSBT_IN_TAP_KEY_SIG, whereas embit's signer creates
        # the final witness directly. Exercise the actual libwally wire format.
        signature = psbt.inputs[0].final_scriptwitness.items[0]
        psbt.inputs[0].final_scriptwitness = None
        psbt.inputs[0].unknown = {b"\x13": signature}
        psbt = PSBT.from_base64(psbt.to_string())
    finalized = finalize_signed_psbt(psbt)
    assert finalized is not None
    assert [out.value for out in finalized.vout] == [40000, 59000]


def test_change_metadata_follows_each_output_after_shuffling():
    _, _, data = signing_data()
    data.outputs.reverse()
    data.outputs.append(data.outputs[0].copy(deep=True))
    psbt = create_psbt(data)
    assert psbt.outputs[0].bip32_derivations
    assert not psbt.outputs[1].bip32_derivations
    assert psbt.outputs[2].bip32_derivations
    assert psbt.outputs[0].bip32_derivations is not psbt.outputs[2].bip32_derivations


@pytest.mark.parametrize(
    "field,value",
    [("tx_id", "11" * 32), ("vout", 9), ("amount", 99999), ("address_index", 9)],
)
def test_inconsistent_input_rejected(field, value):
    _, _, data = signing_data()
    setattr(data.inputs[0], field, value)
    with pytest.raises(ValueError, match="Input"):
        create_psbt(data)


def test_inconsistent_change_rejected():
    _, _, data = signing_data()
    data.outputs[1].address_index = 9
    with pytest.raises(ValueError, match="Output"):
        create_psbt(data)


@pytest.mark.parametrize("sighash", [SIGHASH.DEFAULT, SIGHASH.ALL])
def test_taproot_key_signature_verification(sighash):
    root, _, data = signing_data("tr")
    psbt = create_psbt(data)
    psbt.inputs[0].sighash_type = sighash
    assert psbt.sign_with(root, sighash=sighash) == 1
    signature = psbt.inputs[0].final_scriptwitness.items[0]
    psbt.inputs[0].final_scriptwitness = None
    psbt.inputs[0].unknown = {b"\x13": signature}
    invalid = PSBT.from_base64(psbt.to_string())
    invalid.inputs[0].unknown[b"\x13"] = bytes([signature[0] ^ 1]) + signature[1:]
    with pytest.raises(ValueError, match="Invalid Taproot"):
        finalize_signed_psbt(invalid)
    assert finalize_signed_psbt(psbt) is not None


def test_compact_segwit_psbt_stays_below_bowser_transfer_limit():
    _, _, data = signing_data()
    previous = Transaction.from_string(data.inputs[0].tx_hex)
    previous.vout.extend([previous.vout[0]] * 100)
    data.inputs[0].tx_hex = previous.to_string()
    data.inputs[0].tx_id = previous.txid().hex()
    data.inputs = [data.inputs[0].copy(update={"vout": i}) for i in range(64)]
    encoded = create_psbt(data).to_string()
    assert len(encoded) <= 16384
    assert len(PSBT.from_base64(encoded).inputs) == 64


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["pkh", "sh", "wpkh", "tr"])
@pytest.mark.parametrize("network", ["Testnet", "Testnet4"])
async def test_psbt_api_create_and_extract(kind, network):
    root, _, data = signing_data(kind)
    encoded = await views_api.api_psbt_create(data, _auth=None)
    psbt = PSBT.from_base64(encoded)
    assert psbt.sign_with(root) == 1
    if kind == "tr":
        signature = psbt.inputs[0].final_scriptwitness.items[0]
        psbt.inputs[0].final_scriptwitness = None
        psbt.inputs[0].unknown = {b"\x13": signature}
    result = await views_api.api_psbt_extract_tx(
        ExtractPsbt(
            psbt_base64=psbt.to_string(),
            inputs=[{"tx_hex": data.inputs[0].tx_hex}],
            network=network,
        ),
        _auth=None,
    )
    assert result.tx_hex
    assert len(Transaction.from_string(result.tx_hex).vout) == 2
