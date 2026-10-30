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
    type: str | None = ""
    network: str = "Mainnet"
    meta: str = "{}"


class Address(BaseModel):
    id: str
    address: str
    wallet: str
    amount: int = 0
    branch_index: int = 0
    address_index: int
    note: str | None = None
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
    branch_index: int | None = None
    address_index: int | None = None
    wallet: str | None = None


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
    psbt_base64: str = ""
    inputs: list[SerializedTransaction]
    network: str = "Mainnet"


class ExtractTx(BaseModel):
    tx_hex: str = ""
    network: str = "Mainnet"


class SignedTransaction(BaseModel):
    tx_hex: str | None = None
    tx_json: str | None = None


class Config(BaseModel):
    mempool_endpoint: str = "https://mempool.space"
    receive_gap_limit: int = 20
    change_gap_limit: int = 5
    sats_denominated: bool = True
    network: str = "Mainnet"


class ConfigDb(BaseModel):
    user: str
    json_data: Config
