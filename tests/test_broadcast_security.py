import asyncio
import ipaddress
import socket
from http import HTTPStatus
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import HTTPException
from lnbits.settings import settings

from .. import views_api
from ..decorators import WatchOnlyAuth
from ..models import SerializedTransaction

PRIVATE_TARGETS = [
    "http://127.0.0.1:5099",  # loopback
    "http://192.168.1.200:5099",  # LAN
    "http://127.0.0.1.nip.io:5099",  # DNS alias for loopback
    "http://169.254.169.254",  # cloud metadata
    "http://[fc00::1]",  # IPv6 ULA
    "https://instance.example",  # this LNbits instance
    "https://9.9.9.9",  # this host as configured via LNBITS_OUTBOUND_HOST_IPS
]


@pytest.fixture
def broadcast_env(monkeypatch):
    """Exercise the broadcast sink without real network requests."""
    monkeypatch.setattr(settings, "lnbits_baseurl", "https://instance.example")
    monkeypatch.setattr(settings, "lnbits_outbound_host_ips", ["9.9.9.9"])
    monkeypatch.setattr(settings, "lnbits_callback_url_rules", [])

    destinations = {"127.0.0.1.nip.io": "127.0.0.1"}
    env = SimpleNamespace(
        requests=[],
        response=lambda: httpx.Response(200, text="broadcast-txid"),
    )

    async def resolve(self, host, port, **kwargs):
        address = destinations.get(host, host)
        assert address is not None
        try:
            ipaddress.ip_address(address)
        except ValueError:
            address = "93.184.216.34"
        family = socket.AF_INET6 if ":" in address else socket.AF_INET
        return [(family, socket.SOCK_STREAM, 6, "", (address, port))]

    def handler(request):
        env.requests.append(request)
        return env.response()

    class RecordingAsyncClient(httpx.AsyncClient):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._transport = httpx.MockTransport(handler)

    monkeypatch.setattr(asyncio.BaseEventLoop, "getaddrinfo", resolve)
    monkeypatch.setattr(httpx, "AsyncClient", RecordingAsyncClient)
    return env


async def _broadcast(monkeypatch, endpoint, *, network="Mainnet"):
    config = SimpleNamespace(network=network, mempool_endpoint=endpoint)
    monkeypatch.setattr(views_api, "get_config", AsyncMock(return_value=config))
    return await views_api.api_tx_broadcast(
        SerializedTransaction(tx_hex="deadbeef"), WatchOnlyAuth(user_id="user")
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("target", PRIVATE_TARGETS)
async def test_broadcast_blocks_unsafe_destinations(broadcast_env, monkeypatch, target):
    with pytest.raises(HTTPException) as exc_info:
        await _broadcast(monkeypatch, target)

    assert exc_info.value.status_code == HTTPStatus.BAD_REQUEST
    assert exc_info.value.detail == "Transaction broadcast failed."
    assert broadcast_env.requests == []


@pytest.mark.asyncio
async def test_broadcast_public_endpoint_still_works(broadcast_env, monkeypatch):
    assert await _broadcast(monkeypatch, "https://mempool.example") == "broadcast-txid"

    assert len(broadcast_env.requests) == 1
    request = broadcast_env.requests[0]
    assert request.method == "POST"
    assert request.url.path == "/api/tx"
    assert request.headers["host"] == "mempool.example"
    assert request.content == b"deadbeef"


@pytest.mark.asyncio
async def test_broadcast_testnet_uses_network_path(broadcast_env, monkeypatch):
    assert (
        await _broadcast(monkeypatch, "https://mempool.example", network="Testnet")
        == "broadcast-txid"
    )

    assert broadcast_env.requests[0].url.path == "/testnet/api/tx"


@pytest.mark.asyncio
async def test_broadcast_ignores_admin_callback_url_rules(broadcast_env, monkeypatch):
    # A broadcast is not a callback: restrictive admin callback rules must not
    # reject an otherwise valid public mempool endpoint.
    monkeypatch.setattr(
        settings, "lnbits_callback_url_rules", [r"https://allowed\.example"]
    )

    assert await _broadcast(monkeypatch, "https://mempool.example") == "broadcast-txid"
    assert len(broadcast_env.requests) == 1


@pytest.mark.asyncio
async def test_broadcast_error_does_not_leak_backend_response(
    broadcast_env, monkeypatch
):
    broadcast_env.response = lambda: httpx.Response(500, text="backend-secret")

    with pytest.raises(HTTPException) as exc_info:
        await _broadcast(monkeypatch, "https://mempool.example")

    assert exc_info.value.status_code == HTTPStatus.BAD_REQUEST
    assert exc_info.value.detail == "Transaction broadcast failed."
    assert len(broadcast_env.requests) == 1
