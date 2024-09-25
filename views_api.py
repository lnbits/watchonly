import json
from http import HTTPStatus
from typing import List

import httpx
from embit import finalizer, script
from embit.ec import PublicKey
from embit.networks import NETWORKS
from embit.psbt import PSBT, DerivationPath
from embit.transaction import Transaction, TransactionInput, TransactionOutput
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from lnbits.core.models import WalletTypeInfo
from lnbits.decorators import require_admin_key, require_invoice_key
from lnbits.helpers import urlsafe_short_hash

from .crud import (
    create_config,
    create_fresh_addresses,
    create_watch_wallet,
    delete_addresses_for_wallet,
    delete_watch_wallet,
    get_address_by_id,
    get_addresses,
    get_config,
    get_fresh_address,
    get_watch_wallet,
    get_watch_wallets,
    update_address,
    update_config,
    update_watch_wallet,
)
from .helpers import parse_key
from .models import (
    Address,
    Config,
    CreatePsbt,
    CreateWallet,
    ExtractPsbt,
    ExtractTx,
    SerializedTransaction,
    SignedTransaction,
    WalletAccount,
)

watchonly_api_router = APIRouter()


@watchonly_api_router.get("/api/v1/wallet")
async def api_wallets_retrieve(
    network: str = Query("Mainnet"),
    key_info: WalletTypeInfo = Depends(require_invoice_key),
) -> list[WalletAccount]:
    return await get_watch_wallets(key_info.wallet.user, network)


@watchonly_api_router.get(
    "/api/v1/wallet/{wallet_id}", dependencies=[Depends(require_invoice_key)]
)
async def api_wallet_retrieve(wallet_id: str) -> WalletAccount:
    watch_wallet = await get_watch_wallet(wallet_id)

    if not watch_wallet:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Wallet does not exist."
        )

    return watch_wallet


@watchonly_api_router.post("/api/v1/wallet")
async def api_wallet_create_or_update(
    data: CreateWallet, w: WalletTypeInfo = Depends(require_admin_key)
) -> WalletAccount:
    try:
        descriptor, network = parse_key(data.masterpub)
        assert network
        if data.network != network["name"]:
            raise ValueError(
                "Account network error.  This account is for '{}'".format(
                    network["name"]
                )
            )

        new_wallet = WalletAccount(
            id=urlsafe_short_hash(),
            user=w.wallet.user,
            masterpub=data.masterpub,
            fingerprint=descriptor.keys[0].fingerprint.hex(),
            type=descriptor.scriptpubkey_type(),
            title=data.title,
            address_no=-1,  # fresh address on empty wallet can get address with index 0
            balance=0,
            network=network["name"],
            meta=data.meta,
        )

        wallets = await get_watch_wallets(w.wallet.user, network["name"])
        existing_wallet = next(
            (
                ew
                for ew in wallets
                if ew.fingerprint == new_wallet.fingerprint
                and ew.network == new_wallet.network
                and ew.masterpub == new_wallet.masterpub
            ),
            None,
        )
        if existing_wallet:
            raise ValueError(
                f"Account '{existing_wallet.title}' has the same master pulic key"
            )

        wallet = await create_watch_wallet(new_wallet)

        await api_get_addresses(wallet.id, w)
    except Exception as exc:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST, detail=str(exc)
        ) from exc

    config = await get_config(w.wallet.user)
    if not config:
        await create_config(user=w.wallet.user)
    return wallet


@watchonly_api_router.delete(
    "/api/v1/wallet/{wallet_id}", dependencies=[Depends(require_admin_key)]
)
async def api_wallet_delete(wallet_id: str):
    wallet = await get_watch_wallet(wallet_id)

    if not wallet:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Wallet does not exist."
        )

    await delete_watch_wallet(wallet_id)
    await delete_addresses_for_wallet(wallet_id)

    return "", HTTPStatus.NO_CONTENT


#############################ADDRESSES##########################


@watchonly_api_router.get(
    "/api/v1/address/{wallet_id}", dependencies=[Depends(require_invoice_key)]
)
async def api_fresh_address(wallet_id: str) -> Address:
    address = await get_fresh_address(wallet_id)
    assert address
    return address


@watchonly_api_router.put(
    "/api/v1/address/{address_id}", dependencies=[Depends(require_admin_key)]
)
async def api_update_address(address_id: str, req: Request):
    address = await get_address_by_id(address_id)
    if not address:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Address does not exist."
        )

    body = await req.json()
    # amout is only updated if the address has history
    if "amount" in body:
        address.amount = int(body["amount"])
        address.has_activity = True

    if "note" in body:
        address.note = body["note"]

    address = await update_address(address)

    wallet = (
        await get_watch_wallet(address.wallet)
        if address.branch_index == 0 and address.amount != 0
        else None
    )

    if wallet and wallet.address_no < address.address_index:
        wallet.address_no = address.address_index
        await update_watch_wallet(wallet)
    return address


@watchonly_api_router.get("/api/v1/addresses/{wallet_id}")
async def api_get_addresses(
    wallet_id, key_info: WalletTypeInfo = Depends(require_invoice_key)
) -> list[Address]:
    wallet = await get_watch_wallet(wallet_id)
    if not wallet:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Wallet does not exist."
        )

    addresses = await get_addresses(wallet_id)
    config = await get_config(key_info.wallet.user)
    assert config, "Config not found"

    if not addresses:
        await create_fresh_addresses(wallet_id, 0, config.receive_gap_limit)
        await create_fresh_addresses(wallet_id, 0, config.change_gap_limit, True)
        addresses = await get_addresses(wallet_id)

    receive_addresses = list(filter(lambda addr: addr.branch_index == 0, addresses))
    change_addresses = list(filter(lambda addr: addr.branch_index == 1, addresses))

    last_receive_address = list(
        filter(lambda addr: addr.has_activity, receive_addresses)
    )[-1:]
    last_change_address = list(
        filter(lambda addr: addr.has_activity, change_addresses)
    )[-1:]

    if last_receive_address:
        current_index = receive_addresses[-1].address_index
        address_index = last_receive_address[0].address_index
        await create_fresh_addresses(
            wallet_id, current_index + 1, address_index + config.receive_gap_limit + 1
        )

    if last_change_address:
        current_index = change_addresses[-1].address_index
        address_index = last_change_address[0].address_index
        await create_fresh_addresses(
            wallet_id,
            current_index + 1,
            address_index + config.change_gap_limit + 1,
            True,
        )

    return await get_addresses(wallet_id)


#############################PSBT##########################


@watchonly_api_router.post("/api/v1/psbt", dependencies=[Depends(require_admin_key)])
async def api_psbt_create(data: CreatePsbt):
    try:
        vin = [
            TransactionInput(bytes.fromhex(inp.tx_id), inp.vout) for inp in data.inputs
        ]
        vout = [
            TransactionOutput(out.amount, script.address_to_scriptpubkey(out.address))
            for out in data.outputs
        ]

        descriptors = {}
        for _, masterpub in enumerate(data.masterpubs):
            descriptors[masterpub.id] = parse_key(masterpub.public_key)

        inputs_extra: List[dict] = []

        for inp in data.inputs:
            bip32_derivations = {}
            descriptor = descriptors[inp.wallet][0]
            d = descriptor.derive(inp.address_index, inp.branch_index)
            for k in d.keys:
                bip32_derivations[PublicKey.parse(k.sec())] = DerivationPath(
                    k.origin.fingerprint, k.origin.derivation
                )
            inputs_extra.append(
                {
                    "bip32_derivations": bip32_derivations,
                    "non_witness_utxo": Transaction.from_string(inp.tx_hex),
                }
            )

        tx = Transaction(vin=vin, vout=vout)
        psbt = PSBT(tx)

        for i, inp_extra in enumerate(inputs_extra):
            psbt.inputs[i].bip32_derivations = inp_extra["bip32_derivations"]
            psbt.inputs[i].non_witness_utxo = inp_extra.get("non_witness_utxo", None)

        outputs_extra = []
        bip32_derivations = {}
        for out in data.outputs:
            if out.branch_index == 1:
                assert out.wallet
                descriptor = descriptors[out.wallet][0]
                d = descriptor.derive(out.address_index, out.branch_index)
                for k in d.keys:
                    bip32_derivations[PublicKey.parse(k.sec())] = DerivationPath(
                        k.origin.fingerprint, k.origin.derivation
                    )
                outputs_extra.append({"bip32_derivations": bip32_derivations})

        for i, out_extra in enumerate(outputs_extra):
            psbt.outputs[i].bip32_derivations = out_extra["bip32_derivations"]

        return psbt.to_string()

    except Exception as exc:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST, detail=str(exc)
        ) from exc


@watchonly_api_router.put(
    "/api/v1/psbt/utxos", dependencies=[Depends(require_admin_key)]
)
async def api_psbt_utxos_tx(req: Request):
    """Extract previous unspent transaction outputs (tx_id, vout) from PSBT"""

    body = await req.json()
    try:
        psbt = PSBT.from_base64(body["psbtBase64"])
        res = []
        for _, inp in enumerate(psbt.inputs):
            res.append({"tx_id": inp.txid.hex(), "vout": inp.vout})

        return res
    except Exception as exc:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST, detail=str(exc)
        ) from exc


@watchonly_api_router.put(
    "/api/v1/psbt/extract", dependencies=[Depends(require_admin_key)]
)
async def api_psbt_extract_tx(data: ExtractPsbt) -> SignedTransaction:
    network = NETWORKS["main"] if data.network == "Mainnet" else NETWORKS["test"]
    try:
        psbt = PSBT.from_base64(data.psbt_base64)
        for i, inp in enumerate(data.inputs):
            psbt.inputs[i].non_witness_utxo = Transaction.from_string(inp.tx_hex)

        final_psbt = finalizer.finalize_psbt(psbt)
        if not final_psbt:
            raise ValueError("PSBT cannot be finalized!")

        tx_hex = final_psbt.to_string()
        transaction = Transaction.from_string(tx_hex)
        tx = {
            "locktime": transaction.locktime,
            "version": transaction.version,
            "outputs": [],
            "fee": psbt.fee(),
        }

        for out in transaction.vout:
            tx["outputs"].append(
                {"amount": out.value, "address": out.script_pubkey.address(network)}
            )
        signed_tx = SignedTransaction(tx_hex=tx_hex, tx_json=json.dumps(tx))
        return signed_tx
    except Exception as exc:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST, detail=str(exc)
        ) from exc


@watchonly_api_router.put(
    "/api/v1/tx/extract", dependencies=[Depends(require_admin_key)]
)
async def api_extract_tx(data: ExtractTx):
    network = NETWORKS["main"] if data.network == "Mainnet" else NETWORKS["test"]
    try:
        transaction = Transaction.from_string(data.tx_hex)
        tx = {
            "locktime": transaction.locktime,
            "version": transaction.version,
            "outputs": [],
        }

        for out in transaction.vout:
            tx["outputs"].append(
                {"amount": out.value, "address": out.script_pubkey.address(network)}
            )
        return {"tx_json": tx}
    except Exception as exc:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST, detail=str(exc)
        ) from exc


@watchonly_api_router.post("/api/v1/tx")
async def api_tx_broadcast(
    data: SerializedTransaction, w: WalletTypeInfo = Depends(require_admin_key)
):
    try:
        config = await get_config(w.wallet.user)
        if not config:
            raise ValueError(
                "Cannot broadcast transaction. Mempool endpoint not defined!"
            )

        endpoint = (
            config.mempool_endpoint
            if config.network == "Mainnet"
            else config.mempool_endpoint + "/testnet"
        )
        async with httpx.AsyncClient() as client:
            r = await client.post(endpoint + "/api/tx", content=data.tx_hex)
            r.raise_for_status()
            tx_id = r.text
            return tx_id
    except Exception as exc:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST, detail=str(exc)
        ) from exc


@watchonly_api_router.put("/api/v1/config")
async def api_update_config(
    data: Config, w: WalletTypeInfo = Depends(require_admin_key)
) -> Config:
    config = await update_config(data, user=w.wallet.user)
    assert config
    return config


@watchonly_api_router.get("/api/v1/config")
async def api_get_config(
    key_info: WalletTypeInfo = Depends(require_invoice_key),
) -> Config:
    config = await get_config(key_info.wallet.user)
    if not config:
        config = await create_config(user=key_info.wallet.user)
    return config
