import typing
from dataclasses import dataclass
from solders.pubkey import Pubkey
from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Commitment
import borsh_construct as borsh
from anchorpy.coder.accounts import ACCOUNT_DISCRIMINATOR_SIZE
from anchorpy.error import AccountInvalidDiscriminator
from anchorpy.utils.rpc import get_multiple_accounts
from anchorpy.borsh_extension import BorshPubkey
from ..program_id import PROGRAM_ID


class TokenLedgerJSON(typing.TypedDict):
    token_account: str
    amount: int


@dataclass
class TokenLedger:
    discriminator: typing.ClassVar = b"\x9c\xf7\t\xbc6lUM"
    layout: typing.ClassVar = borsh.CStruct(
        "token_account" / BorshPubkey, "amount" / borsh.U64
    )
    token_account: Pubkey
    amount: int

    @classmethod
    async def fetch(
        cls,
        conn: AsyncClient,
        address: Pubkey,
        commitment: typing.Optional[Commitment] = None,
        program_id: Pubkey = PROGRAM_ID,
    ) -> typing.Optional["TokenLedger"]:
        resp = await conn.get_account_info(address, commitment=commitment)
        info = resp.value
        if info is None:
            return None
        if info.owner != program_id:
            raise ValueError("Account does not belong to this program")
        bytes_data = info.data
        return cls.decode(bytes_data)

    @classmethod
    async def fetch_multiple(
        cls,
        conn: AsyncClient,
        addresses: list[Pubkey],
        commitment: typing.Optional[Commitment] = None,
        program_id: Pubkey = PROGRAM_ID,
    ) -> typing.List[typing.Optional["TokenLedger"]]:
        infos = await get_multiple_accounts(conn, addresses, commitment=commitment)
        res: typing.List[typing.Optional["TokenLedger"]] = []
        for info in infos:
            if info is None:
                res.append(None)
                continue
            if info.account.owner != program_id:
                raise ValueError("Account does not belong to this program")
            res.append(cls.decode(info.account.data))
        return res

    @classmethod
    def decode(cls, data: bytes) -> "TokenLedger":
        if data[:ACCOUNT_DISCRIMINATOR_SIZE] != cls.discriminator:
            raise AccountInvalidDiscriminator(
                "The discriminator for this account is invalid"
            )
        dec = TokenLedger.layout.parse(data[ACCOUNT_DISCRIMINATOR_SIZE:])
        return cls(
            token_account=dec.token_account,
            amount=dec.amount,
        )

    def to_json(self) -> TokenLedgerJSON:
        return {
            "token_account": str(self.token_account),
            "amount": self.amount,
        }

    @classmethod
    def from_json(cls, obj: TokenLedgerJSON) -> "TokenLedger":
        return cls(
            token_account=Pubkey.from_string(obj["token_account"]),
            amount=obj["amount"],
        )
