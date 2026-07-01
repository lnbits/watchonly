from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request
from lnbits.decorators import (
    check_access_token,
    check_account_exists,
    require_admin_key,
    require_invoice_key,
)
from pydantic.types import UUID4


@dataclass(frozen=True)
class WatchOnlyAuth:
    user_id: str


async def require_watchonly_read_account(
    request: Request,
    access_token: str | None = Depends(check_access_token),
    usr: UUID4 | None = None,
) -> WatchOnlyAuth:
    return await _require_watchonly_account(
        request, access_token, usr, require_invoice_key
    )


async def require_watchonly_admin_account(
    request: Request,
    access_token: str | None = Depends(check_access_token),
    usr: UUID4 | None = None,
) -> WatchOnlyAuth:
    return await _require_watchonly_account(
        request, access_token, usr, require_admin_key
    )


async def _require_watchonly_account(
    request: Request,
    access_token: str | None,
    usr: UUID4 | None,
    legacy_key_checker,
) -> WatchOnlyAuth:
    api_key_header, api_key_query = _legacy_api_key(request)
    account_error: HTTPException | None = None

    if access_token or usr:
        try:
            account = await check_account_exists(request, access_token, usr)
            return WatchOnlyAuth(user_id=account.id)
        except HTTPException as exc:
            account_error = exc
            if not api_key_header and not api_key_query:
                raise

    try:
        key_info = await legacy_key_checker(
            request,
            api_key_header=api_key_header,
            api_key_query=api_key_query,
        )
    except HTTPException as exc:
        if account_error:
            raise account_error from exc
        raise

    return WatchOnlyAuth(user_id=key_info.wallet.user)


def _legacy_api_key(request: Request) -> tuple[str | None, str | None]:
    return request.headers.get("X-API-KEY"), request.query_params.get("api-key")
