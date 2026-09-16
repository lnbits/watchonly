import json
from http import HTTPStatus

import httpx
import wallycore as wally
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from lnbits.helpers import urlsafe_short_hash

from .crud import (
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
from .decorators import (
    WatchOnlyAuth,
    require_watchonly_admin_account,
    require_watchonly_read_account,
)
from .helpers import (
    descriptor_fingerprint,
    descriptor_type,
    parse_key,
    transaction_details,
)
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
from .psbt import (
    combine_matching_psbt,
    create_psbt,
    finalize_signed_psbt,
    psbt_fee,
    set_previous_transaction,
)

watchonly_api_router = APIRouter()


@watchonly_api_router.get("/api/v1/wallet")
async def api_wallets_retrieve(
    network: str = Query("Mainnet"),
    auth: WatchOnlyAuth = Depends(require_watchonly_read_account),
) -> list[WalletAccount]:
    return await get_watch_wallets(auth.user_id, network)


@watchonly_api_router.get("/api/v1/wallet/{wallet_id}")
async def api_wallet_retrieve(
    wallet_id: str,
    auth: WatchOnlyAuth = Depends(require_watchonly_read_account),
) -> WalletAccount:
    return await _get_user_watch_wallet(wallet_id, auth.user_id)


@watchonly_api_router.post("/api/v1/wallet")
async def api_wallet_create_or_update(
    data: CreateWallet,
    auth: WatchOnlyAuth = Depends(require_watchonly_admin_account),
) -> WalletAccount:
    try:
        descriptor, network = parse_key(data.masterpub)
        assert network
        signing_network = "Testnet" if data.network == "Testnet4" else data.network
        if signing_network != network["name"]:
            raise ValueError(
                "Account network error.  This account is for '{}'".format(
                    network["name"]
                )
            )

        new_wallet = WalletAccount(
            id=urlsafe_short_hash(),
            user=auth.user_id,
            masterpub=data.masterpub,
            fingerprint=descriptor_fingerprint(descriptor),
            type=descriptor_type(descriptor),
            title=data.title,
            address_no=-1,  # fresh address on empty wallet can get address with index 0
            balance=0,
            network=data.network,
            meta=data.meta,
        )

        wallets = await get_watch_wallets(auth.user_id, data.network)
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

        await api_get_addresses(wallet.id, auth)
    except Exception as exc:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST, detail=str(exc)
        ) from exc

    return wallet


@watchonly_api_router.delete("/api/v1/wallet/{wallet_id}")
async def api_wallet_delete(
    wallet_id: str,
    auth: WatchOnlyAuth = Depends(require_watchonly_admin_account),
):
    await _get_user_watch_wallet(wallet_id, auth.user_id)
    await delete_watch_wallet(wallet_id)
    await delete_addresses_for_wallet(wallet_id)

    return "", HTTPStatus.NO_CONTENT


#############################ADDRESSES##########################


@watchonly_api_router.get("/api/v1/address/{wallet_id}")
async def api_fresh_address(
    wallet_id: str,
    auth: WatchOnlyAuth = Depends(require_watchonly_read_account),
) -> Address:
    await _get_user_watch_wallet(wallet_id, auth.user_id)
    address = await get_fresh_address(wallet_id)
    assert address
    return address


@watchonly_api_router.put("/api/v1/address/{address_id}")
async def api_update_address(
    address_id: str,
    req: Request,
    auth: WatchOnlyAuth = Depends(require_watchonly_admin_account),
):
    address = await get_address_by_id(address_id)
    if not address:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Address does not exist."
        )

    await _get_user_watch_wallet(address.wallet, auth.user_id)

    body = await req.json()
    # amount is only updated if the address has history
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
    wallet_id: str,
    auth: WatchOnlyAuth = Depends(require_watchonly_read_account),
) -> list[Address]:
    await _get_user_watch_wallet(wallet_id, auth.user_id)

    addresses = await get_addresses(wallet_id)
    config = await get_config(auth.user_id)
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


@watchonly_api_router.post("/api/v1/psbt")
async def api_psbt_create(
    data: CreatePsbt,
    _auth: WatchOnlyAuth = Depends(require_watchonly_admin_account),
):
    try:
        return wally.psbt_to_base64(create_psbt(data), 0)

    except Exception as exc:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST, detail=str(exc)
        ) from exc


@watchonly_api_router.put("/api/v1/psbt/utxos")
async def api_psbt_utxos_tx(
    req: Request,
    _auth: WatchOnlyAuth = Depends(require_watchonly_admin_account),
):
    """Extract previous unspent transaction outputs (tx_id, vout) from PSBT"""

    body = await req.json()
    try:
        psbt = wally.psbt_from_base64(body["psbtBase64"], 0)
        res = []
        for index in range(wally.psbt_get_num_inputs(psbt)):
            res.append(
                {
                    "tx_id": bytes(wally.psbt_get_input_previous_txid(psbt, index))[
                        ::-1
                    ].hex(),
                    "vout": wally.psbt_get_input_output_index(psbt, index),
                }
            )

        return res
    except Exception as exc:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST, detail=str(exc)
        ) from exc


@watchonly_api_router.put("/api/v1/psbt/extract")
async def api_psbt_extract_tx(
    data: ExtractPsbt,
    _auth: WatchOnlyAuth = Depends(require_watchonly_admin_account),
) -> SignedTransaction:
    network = (
        wally.WALLY_NETWORK_BITCOIN_MAINNET
        if data.network == "Mainnet"
        else wally.WALLY_NETWORK_BITCOIN_TESTNET
    )
    try:
        psbt = wally.psbt_from_base64(data.psbt_base64, 0)
        if data.expected_psbt_base64:
            expected = wally.psbt_from_base64(data.expected_psbt_base64, 0)
            psbt = combine_matching_psbt(expected, psbt)
        for i, inp in enumerate(data.inputs):
            set_previous_transaction(psbt, i, inp.tx_hex)

        fee = psbt_fee(psbt)
        transaction = finalize_signed_psbt(psbt)
        tx_hex = wally.tx_to_hex(transaction, wally.WALLY_TX_FLAG_USE_WITNESS)
        tx = transaction_details(transaction, network)
        tx["fee"] = fee
        signed_tx = SignedTransaction(tx_hex=tx_hex, tx_json=json.dumps(tx))
        return signed_tx
    except Exception as exc:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST, detail=str(exc)
        ) from exc


@watchonly_api_router.put("/api/v1/tx/extract")
async def api_extract_tx(
    data: ExtractTx,
    _auth: WatchOnlyAuth = Depends(require_watchonly_admin_account),
):
    network = (
        wally.WALLY_NETWORK_BITCOIN_MAINNET
        if data.network == "Mainnet"
        else wally.WALLY_NETWORK_BITCOIN_TESTNET
    )
    try:
        transaction = wally.tx_from_hex(data.tx_hex, wally.WALLY_TX_FLAG_USE_WITNESS)
        tx = transaction_details(transaction, network)
        return {"tx_json": tx}
    except Exception as exc:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST, detail=str(exc)
        ) from exc


@watchonly_api_router.post("/api/v1/tx")
async def api_tx_broadcast(
    data: SerializedTransaction,
    auth: WatchOnlyAuth = Depends(require_watchonly_admin_account),
):
    try:
        config = await get_config(auth.user_id)
        if not config:
            raise ValueError(
                "Cannot broadcast transaction. Mempool endpoint not defined!"
            )

        network_path = {"Mainnet": "", "Testnet": "/testnet", "Testnet4": "/testnet4"}
        endpoint = config.mempool_endpoint.rstrip("/") + network_path[config.network]
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
    data: Config,
    auth: WatchOnlyAuth = Depends(require_watchonly_admin_account),
) -> Config:
    config = await update_config(data, user=auth.user_id)
    return config


@watchonly_api_router.get("/api/v1/config")
async def api_get_config(
    auth: WatchOnlyAuth = Depends(require_watchonly_read_account),
) -> Config:
    config = await get_config(auth.user_id)
    return config


async def _get_user_watch_wallet(wallet_id: str, user_id: str) -> WalletAccount:
    watch_wallet = await get_watch_wallet(wallet_id)

    if not watch_wallet:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Wallet does not exist."
        )

    if watch_wallet.user != user_id:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN, detail="Wallet does not belong to user."
        )

    return watch_wallet
