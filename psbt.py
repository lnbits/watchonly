from embit import ec, finalizer, script
from embit.psbt import PSBT, DerivationPath
from embit.transaction import SIGHASH, Transaction, TransactionInput, TransactionOutput

from .helpers import parse_key
from .models import CreatePsbt


def add_descriptor_metadata(scope, descriptor):
    scope.redeem_script = descriptor.redeem_script()
    scope.witness_script = descriptor.witness_script()
    for key in descriptor.keys:
        if key.origin is None:
            raise ValueError(
                "Signing requires a descriptor with key origin information"
            )
        derivation = DerivationPath(key.origin.fingerprint, key.origin.derivation)
        if descriptor.is_taproot:
            if descriptor.taptree:
                raise ValueError("Only Taproot key-spend descriptors are supported")
            pubkey = ec.PublicKey.from_xonly(key.xonly())
            scope.taproot_internal_key = pubkey
            scope.taproot_bip32_derivations[pubkey] = ([], derivation)
        else:
            scope.bip32_derivations[ec.PublicKey.parse(key.sec())] = derivation


def create_psbt(data: CreatePsbt) -> PSBT:
    descriptors = {
        masterpub.id: parse_key(masterpub.public_key)[0]
        for masterpub in data.masterpubs
    }
    tx = Transaction(
        vin=[
            TransactionInput(bytes.fromhex(inp.tx_id), inp.vout) for inp in data.inputs
        ],
        vout=[
            TransactionOutput(out.amount, script.address_to_scriptpubkey(out.address))
            for out in data.outputs
        ],
    )
    psbt = PSBT(tx)
    for scope, inp in zip(psbt.inputs, data.inputs, strict=True):
        descriptor = descriptors[inp.wallet].derive(inp.address_index, inp.branch_index)
        previous_tx = Transaction.from_string(inp.tx_hex)
        if previous_tx.txid().hex() != inp.tx_id or not 0 <= inp.vout < len(
            previous_tx.vout
        ):
            raise ValueError("Input transaction does not match its outpoint")
        utxo = previous_tx.vout[inp.vout]
        if utxo.script_pubkey != descriptor.script_pubkey() or utxo.value != inp.amount:
            raise ValueError("Input does not match its wallet descriptor or amount")
        add_descriptor_metadata(scope, descriptor)
        # SegWit commits to the spent amount. Avoid transporting entire previous
        # transactions in Bowser's bounded PSBT buffer for these inputs.
        if descriptor.is_segwit:
            scope.witness_utxo = utxo
        else:
            scope.non_witness_utxo = previous_tx

    for scope, out in zip(psbt.outputs, data.outputs, strict=True):
        if out.wallet is None or out.branch_index is None or out.address_index is None:
            continue
        descriptor = descriptors[out.wallet].derive(out.address_index, out.branch_index)
        if scope.script_pubkey != descriptor.script_pubkey():
            raise ValueError("Output does not match its wallet descriptor")
        add_descriptor_metadata(scope, descriptor)
    return psbt


def finalize_signed_psbt(psbt: PSBT):
    # embit 0.8 retains BIP371 PSBT_IN_TAP_KEY_SIG as an unknown field.
    # Convert only a verified key-spend signature into its final witness.
    for index, scope in enumerate(psbt.inputs):
        signature = scope.unknown.get(b"\x13")
        if signature is None or scope.final_scriptwitness is not None:
            continue
        if not scope.is_taproot or len(signature) not in (64, 65):
            raise ValueError("Invalid Taproot key signature")
        sighash = signature[64] if len(signature) == 65 else SIGHASH.DEFAULT
        if len(signature) == 65 and sighash not in (1, 2, 3, 0x81, 0x82, 0x83):
            raise ValueError("Invalid Taproot sighash")
        pubkey = ec.PublicKey.from_xonly(scope.utxo.script_pubkey.data[2:])
        if not pubkey.schnorr_verify(
            ec.SchnorrSig(signature[:64]), psbt.sighash(index, sighash=sighash)
        ):
            raise ValueError("Invalid Taproot key signature")
        scope.final_scriptwitness = script.Witness([signature])
    return finalizer.finalize_psbt(psbt)
