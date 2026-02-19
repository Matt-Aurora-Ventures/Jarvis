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
from .. import types


class PositionJSON(typing.TypedDict):
    owner: str
    pool: str
    custody: str
    collateral_custody: str
    open_time: int
    update_time: int
    side: types.side.SideJSON
    price: int
    size_usd: int
    collateral_usd: int
    realised_pnl_usd: int
    cumulative_interest_snapshot: int
    locked_amount: int
    bump: int


@dataclass
class Position:
    discriminator: typing.ClassVar = b"\xaa\xbc\x8f\xe4z@\xf7\xd0"
    layout: typing.ClassVar = borsh.CStruct(
        "owner" / BorshPubkey,
        "pool" / BorshPubkey,
        "custody" / BorshPubkey,
        "collateral_custody" / BorshPubkey,
        "open_time" / borsh.I64,
        "update_time" / borsh.I64,
        "side" / types.side.layout,
        "price" / borsh.U64,
        "size_usd" / borsh.U64,
        "collateral_usd" / borsh.U64,
        "realised_pnl_usd" / borsh.I64,
        "cumulative_interest_snapshot" / borsh.U128,
        "locked_amount" / borsh.U64,
        "bump" / borsh.U8,
    )
    owner: Pubkey
    pool: Pubkey
    custody: Pubkey
    collateral_custody: Pubkey
    open_time: int
    update_time: int
    side: types.side.SideKind
    price: int
    size_usd: int
    collateral_usd: int
    realised_pnl_usd: int
    cumulative_interest_snapshot: int
    locked_amount: int
    bump: int

    @classmethod
    async def fetch(
        cls,
        conn: AsyncClient,
        address: Pubkey,
        commitment: typing.Optional[Commitment] = None,
        program_id: Pubkey = PROGRAM_ID,
    ) -> typing.Optional["Position"]:
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
    ) -> typing.List[typing.Optional["Position"]]:
        infos = await get_multiple_accounts(conn, addresses, commitment=commitment)
        res: typing.List[typing.Optional["Position"]] = []
        for info in infos:
            if info is None:
                res.append(None)
                continue
            if info.account.owner != program_id:
                raise ValueError("Account does not belong to this program")
            res.append(cls.decode(info.account.data))
        return res

    @classmethod
    def decode(cls, data: bytes) -> "Position":
        if data[:ACCOUNT_DISCRIMINATOR_SIZE] != cls.discriminator:
            raise AccountInvalidDiscriminator(
                "The discriminator for this account is invalid"
            )
        dec = Position.layout.parse(data[ACCOUNT_DISCRIMINATOR_SIZE:])
        return cls(
            owner=dec.owner,
            pool=dec.pool,
            custody=dec.custody,
            collateral_custody=dec.collateral_custody,
            open_time=dec.open_time,
            update_time=dec.update_time,
            side=types.side.from_decoded(dec.side),
            price=dec.price,
            size_usd=dec.size_usd,
            collateral_usd=dec.collateral_usd,
            realised_pnl_usd=dec.realised_pnl_usd,
            cumulative_interest_snapshot=dec.cumulative_interest_snapshot,
            locked_amount=dec.locked_amount,
            bump=dec.bump,
        )

    def to_json(self) -> PositionJSON:
        return {
            "owner": str(self.owner),
            "pool": str(self.pool),
            "custody": str(self.custody),
            "collateral_custody": str(self.collateral_custody),
            "open_time": self.open_time,
            "update_time": self.update_time,
            "side": self.side.to_json(),
            "price": self.price,
            "size_usd": self.size_usd,
            "collateral_usd": self.collateral_usd,
            "realised_pnl_usd": self.realised_pnl_usd,
            "cumulative_interest_snapshot": self.cumulative_interest_snapshot,
            "locked_amount": self.locked_amount,
            "bump": self.bump,
        }

    @classmethod
    def from_json(cls, obj: PositionJSON) -> "Position":
        return cls(
            owner=Pubkey.from_string(obj["owner"]),
            pool=Pubkey.from_string(obj["pool"]),
            custody=Pubkey.from_string(obj["custody"]),
            collateral_custody=Pubkey.from_string(obj["collateral_custody"]),
            open_time=obj["open_time"],
            update_time=obj["update_time"],
            side=types.side.from_json(obj["side"]),
            price=obj["price"],
            size_usd=obj["size_usd"],
            collateral_usd=obj["collateral_usd"],
            realised_pnl_usd=obj["realised_pnl_usd"],
            cumulative_interest_snapshot=obj["cumulative_interest_snapshot"],
            locked_amount=obj["locked_amount"],
            bump=obj["bump"],
        )
