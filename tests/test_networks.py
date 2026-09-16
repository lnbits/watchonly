from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from .. import views_api
from ..models import Config, CreateWallet, SerializedTransaction
from .test_psbt import signing_data


@pytest.mark.asyncio
@pytest.mark.parametrize("network", ["Mainnet", "Testnet", "Testnet4"])
async def test_account_keeps_selected_chain(monkeypatch, network):
    _, descriptor, _ = signing_data(network="main" if network == "Mainnet" else "test")
    lookup = AsyncMock(return_value=[])
    save = AsyncMock(side_effect=lambda wallet: wallet)
    monkeypatch.setattr(views_api, "get_watch_wallets", lookup)
    monkeypatch.setattr(views_api, "create_watch_wallet", save)
    monkeypatch.setattr(views_api, "api_get_addresses", AsyncMock(return_value=[]))
    wallet = await views_api.api_wallet_create_or_update(
        CreateWallet(masterpub=str(descriptor), title="Test", network=network),
        SimpleNamespace(user_id="user"),
    )
    assert wallet.network == network
    lookup.assert_awaited_once_with("user", network)
    assert wallet.balance == 0
    assert wallet.address_no == -1


@pytest.mark.asyncio
async def test_testnet4_rejects_mainnet_keys(monkeypatch):
    _, descriptor, _ = signing_data(network="main")
    save = AsyncMock()
    monkeypatch.setattr(views_api, "create_watch_wallet", save)
    with pytest.raises(HTTPException, match="Account network error"):
        await views_api.api_wallet_create_or_update(
            CreateWallet(masterpub=str(descriptor), network="Testnet4"),
            SimpleNamespace(user_id="user"),
        )
    save.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("network", "path"),
    [("Mainnet", ""), ("Testnet", "/testnet"), ("Testnet4", "/testnet4")],
)
async def test_broadcast_uses_selected_chain(monkeypatch, network, path):
    monkeypatch.setattr(
        views_api,
        "get_config",
        AsyncMock(
            return_value=Config(
                network=network, mempool_endpoint="https://mempool.space/"
            )
        ),
    )
    response = SimpleNamespace(text="test-txid", raise_for_status=lambda: None)
    client = AsyncMock()
    client.post.return_value = response
    client.__aenter__.return_value = client
    monkeypatch.setattr(views_api.httpx, "AsyncClient", lambda: client)
    result = await views_api.api_tx_broadcast(
        SerializedTransaction(tx_hex="test-only"), SimpleNamespace(user_id="user")
    )
    assert result == "test-txid"
    client.post.assert_awaited_once_with(
        f"https://mempool.space{path}/api/tx", content="test-only"
    )
