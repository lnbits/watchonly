from typing import Optional

from fastapi import Query
from pydantic import BaseModel


class CreateWallet(BaseModel):
    masterpub: str = Query("")
    title: str = Query("")
    network: str = "Mainnet"
    meta: str = "{}"


class WalletAccount(BaseModel):
    id: str
    user: str
    masterpub: str
    fingerprint: str
    title: str
    address_no: int
    balance: int
    type: Optional[str] = ""
    network: str = "Mainnet"
    meta: str = "{}"


class Address(BaseModel):
    id: str
    address: str
    wallet: str
    amount: int = 0
    branch_index: int = 0
    address_index: int
    note: Optional[str] = None
    has_activity: bool = False


class TransactionInput(BaseModel):
    tx_id: str
    vout: int
    amount: int
    address: str
    branch_index: int
    address_index: int
    wallet: str
    tx_hex: str


class TransactionOutput(BaseModel):
    amount: int
    address: str
    branch_index: Optional[int] = None
    address_index: Optional[int] = None
    wallet: Optional[str] = None


class MasterPublicKey(BaseModel):
    id: str
    public_key: str
    fingerprint: str


class CreatePsbt(BaseModel):
    masterpubs: list[MasterPublicKey]
    inputs: list[TransactionInput]
    outputs: list[TransactionOutput]
    fee_rate: int
    tx_size: int


class SerializedTransaction(BaseModel):
    tx_hex: str


class ExtractPsbt(BaseModel):
    psbt_base64 = ""
    inputs: list[SerializedTransaction]
    network = "Mainnet"


class ExtractTx(BaseModel):
    tx_hex = ""
    network = "Mainnet"


class SignedTransaction(BaseModel):
    tx_hex: Optional[str]
    tx_json: Optional[str]


class Config(BaseModel):
    mempool_endpoint = "https://mempool.space"
    receive_gap_limit = 20
    change_gap_limit = 5
    sats_denominated = True
    network = "Mainnet"
