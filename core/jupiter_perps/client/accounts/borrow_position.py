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


class BorrowPositionJSON(typing.TypedDict):
    owner: str
    pool: str
    custody: str
    open_time: int
    update_time: int
    borrow_size: int
    cumulative_compounded_interest_snapshot: int
    locked_collateral: int
    bump: int
    last_borrowed: int


@dataclass
class BorrowPosition:
    discriminator: typing.ClassVar = b"\xf3\x8c\x14\x8b \xf3r7"
    layout: typing.ClassVar = borsh.CStruct(
        "owner" / BorshPubkey,
        "pool" / BorshPubkey,
        "custody" / BorshPubkey,
        "open_time" / borsh.I64,
        "update_time" / borsh.I64,
        "borrow_size" / borsh.U128,
        "cumulative_compounded_interest_snapshot" / borsh.U128,
        "locked_collateral" / borsh.U64,
        "bump" / borsh.U8,
        "last_borrowed" / borsh.I64,
    )
    owner: Pubkey
    pool: Pubkey
    custody: Pubkey
    open_time: int
    update_time: int
    borrow_size: int
    cumulative_compounded_interest_snapshot: int
    locked_collateral: int
    bump: int
    last_borrowed: int

    @classmethod
    async def fetch(
        cls,
        conn: AsyncClient,
        address: Pubkey,
        commitment: typing.Optional[Commitment] = None,
        program_id: Pubkey = PROGRAM_ID,
    ) -> typing.Optional["BorrowPosition"]:
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
    ) -> typing.List[typing.Optional["BorrowPosition"]]:
        infos = await get_multiple_accounts(conn, addresses, commitment=commitment)
        res: typing.List[typing.Optional["BorrowPosition"]] = []
        for info in infos:
            if info is None:
                res.append(None)
                continue
            if info.account.owner != program_id:
                raise ValueError("Account does not belong to this program")
            res.append(cls.decode(info.account.data))
        return res

    @classmethod
    def decode(cls, data: bytes) -> "BorrowPosition":
        if data[:ACCOUNT_DISCRIMINATOR_SIZE] != cls.discriminator:
            raise AccountInvalidDiscriminator(
                "The discriminator for this account is invalid"
            )
        dec = BorrowPosition.layout.parse(data[ACCOUNT_DISCRIMINATOR_SIZE:])
        return cls(
            owner=dec.owner,
            pool=dec.pool,
            custody=dec.custody,
            open_time=dec.open_time,
            update_time=dec.update_time,
            borrow_size=dec.borrow_size,
            cumulative_compounded_interest_snapshot=dec.cumulative_compounded_interest_snapshot,
            locked_collateral=dec.locked_collateral,
            bump=dec.bump,
            last_borrowed=dec.last_borrowed,
        )

    def to_json(self) -> BorrowPositionJSON:
        return {
            "owner": str(self.owner),
            "pool": str(self.pool),
            "custody": str(self.custody),
            "open_time": self.open_time,
            "update_time": self.update_time,
            "borrow_size": self.borrow_size,
            "cumulative_compounded_interest_snapshot": self.cumulative_compounded_interest_snapshot,
            "locked_collateral": self.locked_collateral,
            "bump": self.bump,
            "last_borrowed": self.last_borrowed,
        }

    @classmethod
    def from_json(cls, obj: BorrowPositionJSON) -> "BorrowPosition":
        return cls(
            owner=Pubkey.from_string(obj["owner"]),
            pool=Pubkey.from_string(obj["pool"]),
            custody=Pubkey.from_string(obj["custody"]),
            open_time=obj["open_time"],
            update_time=obj["update_time"],
            borrow_size=obj["borrow_size"],
            cumulative_compounded_interest_snapshot=obj[
                "cumulative_compounded_interest_snapshot"
            ],
            locked_collateral=obj["locked_collateral"],
            bump=obj["bump"],
            last_borrowed=obj["last_borrowed"],
        )
