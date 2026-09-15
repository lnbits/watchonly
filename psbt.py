from typing import Any

import wallycore as wally

from .helpers import (
    TaprootDescriptor,
    address_script,
    descriptor_branch,
    descriptor_script,
    parse_key,
)
from .models import CreatePsbt


def _path(path: str, address_index: int = 0, branch_index: int = 0) -> list[int]:
    if not path:
        return []
    return wally.bip32_path_from_str(
        path,
        address_index if "*" in path else 0,
        branch_index if "<" in path else 0,
        wally.BIP32_FLAG_STR_WILDCARD | wally.BIP32_FLAG_STR_MULTIPATH,
    )


def add_descriptor_metadata(
    psbt: Any,
    index: int,
    descriptor: Any,
    address_index: int,
    branch_index: int,
    *,
    output: bool = False,
) -> None:
    if isinstance(descriptor, TaprootDescriptor):
        raise ValueError("Only Taproot key-spend descriptors are supported")
    scope = "output" if output else "input"
    spk = descriptor_script(descriptor, address_index, branch_index)
    script_type = wally.scriptpubkey_get_type(spk)
    taproot = script_type == wally.WALLY_SCRIPT_TYPE_P2TR
    depth = 0
    if script_type == wally.WALLY_SCRIPT_TYPE_P2SH:
        depth += 1
        spk = descriptor_script(descriptor, address_index, branch_index, depth)
        getattr(wally, f"psbt_set_{scope}_redeem_script")(psbt, index, spk)
    if wally.scriptpubkey_get_type(spk) == wally.WALLY_SCRIPT_TYPE_P2WSH:
        witness = descriptor_script(descriptor, address_index, branch_index, depth + 1)
        getattr(wally, f"psbt_set_{scope}_witness_script")(psbt, index, witness)

    for key_index in range(wally.descriptor_get_num_keys(descriptor)):
        key = wally.descriptor_get_key(descriptor, key_index)
        child_path = _path(
            wally.descriptor_get_key_child_path_str(descriptor, key_index),
            address_index,
            descriptor_branch(descriptor, branch_index),
        )
        features = wally.descriptor_get_key_features(descriptor, key_index)
        if features & wally.WALLY_MS_IS_PARENTED:
            fingerprint = wally.descriptor_get_key_origin_fingerprint(
                descriptor, key_index
            )
            origin = _path(
                wally.descriptor_get_key_origin_path_str(descriptor, key_index)
            )
        else:
            fingerprint, origin = None, []
        if features & wally.WALLY_MS_IS_RAW:
            pubkey = bytes.fromhex(key)
        else:
            hdkey = wally.bip32_key_from_base58(key)
            if fingerprint is None:
                fingerprint = wally.bip32_key_get_fingerprint(hdkey)
            derived = (
                wally.bip32_key_from_parent_path(
                    hdkey, child_path, wally.BIP32_FLAG_KEY_PUBLIC
                )
                if child_path
                else hdkey
            )
            pubkey = bytes(wally.bip32_key_get_pub_key(derived))
        if fingerprint is None:
            raise ValueError(
                "Signing requires a descriptor with key origin information"
            )
        if taproot:
            xonly = pubkey[1:] if len(pubkey) == 33 else pubkey
            getattr(wally, f"psbt_set_{scope}_taproot_internal_key")(psbt, index, xonly)
            getattr(wally, f"psbt_add_{scope}_taproot_keypath")(
                psbt, index, 0, xonly, None, fingerprint, origin + child_path
            )
        else:
            getattr(wally, f"psbt_add_{scope}_keypath")(
                psbt, index, pubkey, fingerprint, origin + child_path
            )


def create_psbt(data: CreatePsbt) -> Any:
    descriptors = {
        masterpub.id: parse_key(masterpub.public_key)[0]
        for masterpub in data.masterpubs
    }
    tx = wally.tx_init(2, 0, len(data.inputs), len(data.outputs))
    for inp in data.inputs:
        wally.tx_add_raw_input(
            tx,
            bytes.fromhex(inp.tx_id)[::-1],
            inp.vout,
            wally.WALLY_TX_SEQUENCE_FINAL,
            None,
            None,
            0,
        )
    for out in data.outputs:
        wally.tx_add_raw_output(tx, out.amount, address_script(out.address), 0)
    # Attaching the transaction initializes its keypath maps in Wally 1.5.6.
    psbt = wally.psbt_init(0, 0, 0, 0, 0)
    wally.psbt_set_global_tx(psbt, tx)
    for index, inp in enumerate(data.inputs):
        descriptor = descriptors[inp.wallet]
        spk = descriptor_script(descriptor, inp.address_index, inp.branch_index)
        previous = wally.tx_from_hex(inp.tx_hex, wally.WALLY_TX_FLAG_USE_WITNESS)
        previous_txid = bytes(wally.tx_get_txid(previous))[::-1].hex()
        if previous_txid != inp.tx_id or not 0 <= inp.vout < wally.tx_get_num_outputs(
            previous
        ):
            raise ValueError("Input transaction does not match its outpoint")
        if (
            bytes(wally.tx_get_output_script(previous, inp.vout)) != spk
            or wally.tx_get_output_satoshi(previous, inp.vout) != inp.amount
        ):
            raise ValueError("Input does not match its wallet descriptor or amount")
        # Keep SegWit PSBTs within the hardware signer's bounded transfer buffer.
        redeem = (
            descriptor_script(descriptor, inp.address_index, inp.branch_index, 1)
            if wally.scriptpubkey_get_type(spk) == wally.WALLY_SCRIPT_TYPE_P2SH
            else b""
        )
        if wally.scriptpubkey_get_type(redeem or spk) in (
            wally.WALLY_SCRIPT_TYPE_P2WPKH,
            wally.WALLY_SCRIPT_TYPE_P2WSH,
            wally.WALLY_SCRIPT_TYPE_P2TR,
        ):
            wally.psbt_set_input_witness_utxo_from_tx(psbt, index, previous, inp.vout)
        else:
            wally.psbt_set_input_utxo(psbt, index, previous)
        add_descriptor_metadata(
            psbt, index, descriptor, inp.address_index, inp.branch_index
        )

    for index, out in enumerate(data.outputs):
        if out.wallet is None or out.branch_index is None or out.address_index is None:
            continue
        descriptor = descriptors[out.wallet]
        if bytes(wally.tx_get_output_script(tx, index)) != descriptor_script(
            descriptor, out.address_index, out.branch_index
        ):
            raise ValueError("Output does not match its wallet descriptor")
        add_descriptor_metadata(
            psbt, index, descriptor, out.address_index, out.branch_index, output=True
        )
    return psbt


def set_previous_transaction(psbt: Any, index: int, tx_hex: str) -> None:
    previous = wally.tx_from_hex(tx_hex, wally.WALLY_TX_FLAG_USE_WITNESS)
    vout = wally.psbt_get_input_output_index(psbt, index)
    if bytes(wally.tx_get_txid(previous)) != bytes(
        wally.psbt_get_input_previous_txid(psbt, index)
    ) or not 0 <= vout < wally.tx_get_num_outputs(previous):
        raise ValueError("Input transaction does not match its outpoint")
    witness = wally.psbt_get_input_witness_utxo(psbt, index)
    if witness and (
        bytes(wally.tx_output_get_script(witness))
        != bytes(wally.tx_get_output_script(previous, vout))
        or wally.tx_output_get_satoshi(witness)
        != wally.tx_get_output_satoshi(previous, vout)
    ):
        raise ValueError("Input witness UTXO does not match its previous transaction")
    wally.psbt_set_input_utxo(psbt, index, previous)


def psbt_fee(psbt: Any) -> int:
    amount = sum(
        wally.tx_output_get_satoshi(wally.psbt_get_input_best_utxo(psbt, index))
        for index in range(wally.psbt_get_num_inputs(psbt))
    )
    tx = wally.psbt_extract(psbt, wally.WALLY_PSBT_EXTRACT_NON_FINAL)
    return amount - wally.tx_get_total_output_satoshi(tx)


def finalize_signed_psbt(psbt: Any) -> Any:
    # Finalization assembles witnesses; it does not verify signatures.
    verification = wally.psbt_clone(psbt, 0)
    tx = wally.psbt_extract(verification, wally.WALLY_PSBT_EXTRACT_NON_FINAL)
    for index in range(wally.psbt_get_num_inputs(verification)):
        signature = bytes(wally.psbt_get_input_taproot_signature(verification, index))
        if not signature:
            continue
        utxo = wally.psbt_get_input_best_utxo(verification, index)
        spk = bytes(wally.tx_output_get_script(utxo))
        is_taproot = wally.scriptpubkey_get_type(spk) == wally.WALLY_SCRIPT_TYPE_P2TR
        if not is_taproot or len(signature) not in (64, 65):
            raise ValueError("Invalid Taproot key signature")
        sighash = signature[64] if len(signature) == 65 else 0
        if len(signature) == 65 and sighash not in (1, 2, 3, 0x81, 0x82, 0x83):
            raise ValueError("Invalid Taproot sighash")
        wally.psbt_set_input_sighash(verification, index, sighash)
        digest = wally.psbt_get_input_signature_hash(verification, index, tx, None, 0)
        try:
            wally.ec_sig_verify(spk[2:], digest, wally.EC_FLAG_SCHNORR, signature[:64])
        except ValueError as exc:
            raise ValueError("Invalid Taproot key signature") from exc
    wally.psbt_finalize(psbt, 0)
    if not wally.psbt_is_finalized(psbt):
        raise ValueError("PSBT cannot be finalized!")
    return wally.psbt_extract(psbt, 0)
