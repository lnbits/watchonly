from types import SimpleNamespace

import pytest
from fastapi import APIRouter
from fastapi.exceptions import HTTPException
from starlette.requests import Request

from .. import decorators as watchonly_decorators
from .. import views_api, watchonly_ext
from ..models import WalletAccount


# just import router and add it to a test router
@pytest.mark.asyncio
async def test_router():
    router = APIRouter()
    router.include_router(watchonly_ext)


def _request(api_key: str | None = None) -> Request:
    headers = []
    if api_key:
        headers.append((b"x-api-key", api_key.encode()))
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/watchonly/api/v1/wallet",
            "headers": headers,
            "query_string": b"",
        }
    )


@pytest.mark.asyncio
async def test_watchonly_account_auth_uses_lnbits_account(monkeypatch):
    async def fake_check_account_exists(request, access_token, usr):
        return SimpleNamespace(id="account-user")

    async def fake_legacy_key_checker(*args, **kwargs):
        raise AssertionError("legacy auth should not be used")

    monkeypatch.setattr(
        watchonly_decorators, "check_account_exists", fake_check_account_exists
    )

    auth = await watchonly_decorators._require_watchonly_account(
        _request(), "access-token", None, fake_legacy_key_checker
    )

    assert auth.user_id == "account-user"


@pytest.mark.asyncio
async def test_watchonly_account_auth_falls_back_to_legacy_key(monkeypatch):
    async def fake_check_account_exists(request, access_token, usr):
        raise HTTPException(status_code=401, detail="Invalid access token.")

    async def fake_legacy_key_checker(request, api_key_header, api_key_query):
        assert api_key_header == "legacy-key"
        assert api_key_query is None
        return SimpleNamespace(wallet=SimpleNamespace(user="legacy-user"))

    monkeypatch.setattr(
        watchonly_decorators, "check_account_exists", fake_check_account_exists
    )

    auth = await watchonly_decorators._require_watchonly_account(
        _request("legacy-key"), "bad-token", None, fake_legacy_key_checker
    )

    assert auth.user_id == "legacy-user"


@pytest.mark.asyncio
async def test_watchonly_account_auth_keeps_account_error_without_legacy_key(
    monkeypatch,
):
    async def fake_check_account_exists(request, access_token, usr):
        raise HTTPException(status_code=401, detail="Invalid access token.")

    async def fake_legacy_key_checker(*args, **kwargs):
        raise AssertionError("legacy auth should not be used without a key")

    monkeypatch.setattr(
        watchonly_decorators, "check_account_exists", fake_check_account_exists
    )

    with pytest.raises(HTTPException) as exc:
        await watchonly_decorators._require_watchonly_account(
            _request(), "bad-token", None, fake_legacy_key_checker
        )

    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_get_user_watch_wallet_rejects_other_user(monkeypatch):
    async def fake_get_watch_wallet(wallet_id):
        return WalletAccount(
            id=wallet_id,
            user="owner",
            masterpub="xpub",
            fingerprint="fingerprint",
            title="Wallet",
            address_no=0,
            balance=0,
        )

    monkeypatch.setattr(views_api, "get_watch_wallet", fake_get_watch_wallet)

    with pytest.raises(HTTPException) as exc:
        await views_api._get_user_watch_wallet("wallet-id", "other-user")

    assert exc.value.status_code == 403
