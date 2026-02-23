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


class PositionRequestJSON(typing.TypedDict):
    owner: str
    pool: str
    custody: str
    position: str
    mint: str
    open_time: int
    update_time: int
    size_usd_delta: int
    collateral_delta: int
    request_change: types.request_change.RequestChangeJSON
    request_type: types.request_type.RequestTypeJSON
    side: types.side.SideJSON
    price_slippage: typing.Optional[int]
    jupiter_minimum_out: typing.Optional[int]
    pre_swap_amount: typing.Optional[int]
    trigger_price: typing.Optional[int]
    trigger_above_threshold: typing.Optional[bool]
    entire_position: typing.Optional[bool]
    executed: bool
    counter: int
    bump: int
    referral: typing.Optional[str]


@dataclass
class PositionRequest:
    discriminator: typing.ClassVar = b"\x0c&\xfa\xc7.\x9a \xd8"
    layout: typing.ClassVar = borsh.CStruct(
        "owner" / BorshPubkey,
        "pool" / BorshPubkey,
        "custody" / BorshPubkey,
        "position" / BorshPubkey,
        "mint" / BorshPubkey,
        "open_time" / borsh.I64,
        "update_time" / borsh.I64,
        "size_usd_delta" / borsh.U64,
        "collateral_delta" / borsh.U64,
        "request_change" / types.request_change.layout,
        "request_type" / types.request_type.layout,
        "side" / types.side.layout,
        "price_slippage" / borsh.Option(borsh.U64),
        "jupiter_minimum_out" / borsh.Option(borsh.U64),
        "pre_swap_amount" / borsh.Option(borsh.U64),
        "trigger_price" / borsh.Option(borsh.U64),
        "trigger_above_threshold" / borsh.Option(borsh.Bool),
        "entire_position" / borsh.Option(borsh.Bool),
        "executed" / borsh.Bool,
        "counter" / borsh.U64,
        "bump" / borsh.U8,
        "referral" / borsh.Option(BorshPubkey),
    )
    owner: Pubkey
    pool: Pubkey
    custody: Pubkey
    position: Pubkey
    mint: Pubkey
    open_time: int
    update_time: int
    size_usd_delta: int
    collateral_delta: int
    request_change: types.request_change.RequestChangeKind
    request_type: types.request_type.RequestTypeKind
    side: types.side.SideKind
    price_slippage: typing.Optional[int]
    jupiter_minimum_out: typing.Optional[int]
    pre_swap_amount: typing.Optional[int]
    trigger_price: typing.Optional[int]
    trigger_above_threshold: typing.Optional[bool]
    entire_position: typing.Optional[bool]
    executed: bool
    counter: int
    bump: int
    referral: typing.Optional[Pubkey]

    @classmethod
    async def fetch(
        cls,
        conn: AsyncClient,
        address: Pubkey,
        commitment: typing.Optional[Commitment] = None,
        program_id: Pubkey = PROGRAM_ID,
    ) -> typing.Optional["PositionRequest"]:
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
    ) -> typing.List[typing.Optional["PositionRequest"]]:
        infos = await get_multiple_accounts(conn, addresses, commitment=commitment)
        res: typing.List[typing.Optional["PositionRequest"]] = []
        for info in infos:
            if info is None:
                res.append(None)
                continue
            if info.account.owner != program_id:
                raise ValueError("Account does not belong to this program")
            res.append(cls.decode(info.account.data))
        return res

    @classmethod
    def decode(cls, data: bytes) -> "PositionRequest":
        if data[:ACCOUNT_DISCRIMINATOR_SIZE] != cls.discriminator:
            raise AccountInvalidDiscriminator(
                "The discriminator for this account is invalid"
            )
        dec = PositionRequest.layout.parse(data[ACCOUNT_DISCRIMINATOR_SIZE:])
        return cls(
            owner=dec.owner,
            pool=dec.pool,
            custody=dec.custody,
            position=dec.position,
            mint=dec.mint,
            open_time=dec.open_time,
            update_time=dec.update_time,
            size_usd_delta=dec.size_usd_delta,
            collateral_delta=dec.collateral_delta,
            request_change=types.request_change.from_decoded(dec.request_change),
            request_type=types.request_type.from_decoded(dec.request_type),
            side=types.side.from_decoded(dec.side),
            price_slippage=dec.price_slippage,
            jupiter_minimum_out=dec.jupiter_minimum_out,
            pre_swap_amount=dec.pre_swap_amount,
            trigger_price=dec.trigger_price,
            trigger_above_threshold=dec.trigger_above_threshold,
            entire_position=dec.entire_position,
            executed=dec.executed,
            counter=dec.counter,
            bump=dec.bump,
            referral=dec.referral,
        )

    def to_json(self) -> PositionRequestJSON:
        return {
            "owner": str(self.owner),
            "pool": str(self.pool),
            "custody": str(self.custody),
            "position": str(self.position),
            "mint": str(self.mint),
            "open_time": self.open_time,
            "update_time": self.update_time,
            "size_usd_delta": self.size_usd_delta,
            "collateral_delta": self.collateral_delta,
            "request_change": self.request_change.to_json(),
            "request_type": self.request_type.to_json(),
            "side": self.side.to_json(),
            "price_slippage": self.price_slippage,
            "jupiter_minimum_out": self.jupiter_minimum_out,
            "pre_swap_amount": self.pre_swap_amount,
            "trigger_price": self.trigger_price,
            "trigger_above_threshold": self.trigger_above_threshold,
            "entire_position": self.entire_position,
            "executed": self.executed,
            "counter": self.counter,
            "bump": self.bump,
            "referral": (None if self.referral is None else str(self.referral)),
        }

    @classmethod
    def from_json(cls, obj: PositionRequestJSON) -> "PositionRequest":
        return cls(
            owner=Pubkey.from_string(obj["owner"]),
            pool=Pubkey.from_string(obj["pool"]),
            custody=Pubkey.from_string(obj["custody"]),
            position=Pubkey.from_string(obj["position"]),
            mint=Pubkey.from_string(obj["mint"]),
            open_time=obj["open_time"],
            update_time=obj["update_time"],
            size_usd_delta=obj["size_usd_delta"],
            collateral_delta=obj["collateral_delta"],
            request_change=types.request_change.from_json(obj["request_change"]),
            request_type=types.request_type.from_json(obj["request_type"]),
            side=types.side.from_json(obj["side"]),
            price_slippage=obj["price_slippage"],
            jupiter_minimum_out=obj["jupiter_minimum_out"],
            pre_swap_amount=obj["pre_swap_amount"],
            trigger_price=obj["trigger_price"],
            trigger_above_threshold=obj["trigger_above_threshold"],
            entire_position=obj["entire_position"],
            executed=obj["executed"],
            counter=obj["counter"],
            bump=obj["bump"],
            referral=(
                None if obj["referral"] is None else Pubkey.from_string(obj["referral"])
            ),
        )
