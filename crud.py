from typing import Optional

from lnbits.db import Database
from lnbits.helpers import urlsafe_short_hash

from .helpers import derive_address
from .models import Address, Config, ConfigDb, WalletAccount

db = Database("ext_watchonly")


async def create_watch_wallet(wallet: WalletAccount) -> WalletAccount:
    await db.insert("watchonly.wallets", wallet)
    return wallet


async def get_watch_wallet(wallet_id: str) -> Optional[WalletAccount]:
    return await db.fetchone(
        "SELECT * FROM watchonly.wallets WHERE id = :id",
        {"id": wallet_id},
        WalletAccount,
    )


async def get_watch_wallets(user: str, network: str) -> list[WalletAccount]:
    return await db.fetchall(
        """
        SELECT * FROM watchonly.wallets
        WHERE "user" = :user AND network = :network
        """,
        {"user": user, "network": network},
        WalletAccount,
    )


async def update_watch_wallet(wallet: WalletAccount) -> WalletAccount:
    await db.update("watchonly.wallets", wallet)
    return wallet


async def delete_watch_wallet(wallet_id: str) -> None:
    await db.execute(
        "DELETE FROM watchonly.wallets WHERE id = :id",
        {"id": wallet_id},
    )


async def get_fresh_address(wallet_id: str) -> Optional[Address]:
    # todo: move logic to views_api after satspay refactoring
    wallet = await get_watch_wallet(wallet_id)

    if not wallet:
        return None

    wallet_addresses = await get_addresses(wallet_id)
    receive_addresses = list(
        filter(
            lambda addr: addr.branch_index == 0 and addr.has_activity, wallet_addresses
        )
    )
    last_receive_index = (
        receive_addresses.pop().address_index if receive_addresses else -1
    )
    address_index = (
        last_receive_index
        if last_receive_index > wallet.address_no
        else wallet.address_no
    )

    address = await get_address_at_index(wallet_id, 0, address_index + 1)

    if not address:
        addresses = await create_fresh_addresses(
            wallet_id, address_index + 1, address_index + 2
        )
        address = addresses.pop()

    wallet.address_no = address_index + 1
    await update_watch_wallet(wallet)

    return address


async def create_fresh_addresses(
    wallet_id: str,
    start_address_index: int,
    end_address_index: int,
    change_address=False,
) -> list[Address]:
    if start_address_index > end_address_index:
        return []

    wallet = await get_watch_wallet(wallet_id)
    if not wallet:
        return []

    branch_index = 1 if change_address else 0

    for address_index in range(start_address_index, end_address_index):
        address = await derive_address(wallet.masterpub, address_index, branch_index)
        assert address  # TODO: why optional

        addr = Address(
            id=urlsafe_short_hash(),
            address=address,
            wallet=wallet_id,
            branch_index=branch_index,
            address_index=address_index,
        )

        await db.insert("watchonly.addresses", addr)

    # return fresh addresses
    return await db.fetchall(
        """
            SELECT * FROM watchonly.addresses WHERE wallet = :wallet
            AND branch_index = :branch_index
            AND address_index >= :start_address_index
            AND address_index < :end_address_index
            ORDER BY branch_index, address_index
        """,
        {
            "wallet": wallet_id,
            "branch_index": branch_index,
            "start_address_index": start_address_index,
            "end_address_index": end_address_index,
        },
        Address,
    )


async def get_address(address: str) -> Optional[Address]:
    return await db.fetchone(
        "SELECT * FROM watchonly.addresses WHERE address = :address",
        {"address": address},
        Address,
    )


async def get_address_by_id(address_id: str) -> Optional[Address]:
    return await db.fetchone(
        "SELECT * FROM watchonly.addresses WHERE id = :id",
        {"id": address_id},
        Address,
    )


async def get_address_at_index(
    wallet_id: str, branch_index: int, address_index: int
) -> Optional[Address]:
    return await db.fetchone(
        """
            SELECT * FROM watchonly.addresses
            WHERE wallet = :wallet AND branch_index = :branch_index
            AND address_index = :address_index
        """,
        {
            "wallet": wallet_id,
            "branch_index": branch_index,
            "address_index": address_index,
        },
        Address,
    )


async def get_addresses(wallet_id: str) -> list[Address]:
    return await db.fetchall(
        """
        SELECT * FROM watchonly.addresses WHERE wallet = :wallet
        ORDER BY branch_index, address_index
        """,
        {"wallet": wallet_id},
        Address,
    )


async def update_address(address: Address) -> Address:
    await db.update("watchonly.addresses", address)
    return address


async def delete_addresses_for_wallet(wallet_id: str) -> None:
    await db.execute(
        "DELETE FROM watchonly.addresses WHERE wallet = :wallet", {"wallet": wallet_id}
    )


async def create_config(user: str) -> Config:
    config = Config()
    await db.insert("watchonly.config", ConfigDb(user=user, json_data=config))
    return config


async def update_config(config: Config, user: str) -> Config:
    _config = ConfigDb(user=user, json_data=config)
    await db.update("watchonly.config", _config, """WHERE "user" = :user""")
    return config


async def get_config(user: str) -> Config:
    _config = await db.fetchone(
        """SELECT * FROM watchonly.config WHERE "user" = :user""",
        {"user": user},
        ConfigDb,
    )
    if not _config:
        return await create_config(user)
    return _config.json_data
