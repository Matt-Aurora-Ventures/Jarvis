from __future__ import annotations
import typing
from dataclasses import dataclass
from construct import Container
import borsh_construct as borsh


class InstantDecreasePositionParamsJSON(typing.TypedDict):
    collateral_usd_delta: int
    size_usd_delta: int
    price_slippage: int
    entire_position: typing.Optional[bool]
    request_time: int


@dataclass
class InstantDecreasePositionParams:
    layout: typing.ClassVar = borsh.CStruct(
        "collateral_usd_delta" / borsh.U64,
        "size_usd_delta" / borsh.U64,
        "price_slippage" / borsh.U64,
        "entire_position" / borsh.Option(borsh.Bool),
        "request_time" / borsh.I64,
    )
    collateral_usd_delta: int
    size_usd_delta: int
    price_slippage: int
    entire_position: typing.Optional[bool]
    request_time: int

    @classmethod
    def from_decoded(cls, obj: Container) -> "InstantDecreasePositionParams":
        return cls(
            collateral_usd_delta=obj.collateral_usd_delta,
            size_usd_delta=obj.size_usd_delta,
            price_slippage=obj.price_slippage,
            entire_position=obj.entire_position,
            request_time=obj.request_time,
        )

    def to_encodable(self) -> dict[str, typing.Any]:
        return {
            "collateral_usd_delta": self.collateral_usd_delta,
            "size_usd_delta": self.size_usd_delta,
            "price_slippage": self.price_slippage,
            "entire_position": self.entire_position,
            "request_time": self.request_time,
        }

    def to_json(self) -> InstantDecreasePositionParamsJSON:
        return {
            "collateral_usd_delta": self.collateral_usd_delta,
            "size_usd_delta": self.size_usd_delta,
            "price_slippage": self.price_slippage,
            "entire_position": self.entire_position,
            "request_time": self.request_time,
        }

    @classmethod
    def from_json(
        cls, obj: InstantDecreasePositionParamsJSON
    ) -> "InstantDecreasePositionParams":
        return cls(
            collateral_usd_delta=obj["collateral_usd_delta"],
            size_usd_delta=obj["size_usd_delta"],
            price_slippage=obj["price_slippage"],
            entire_position=obj["entire_position"],
            request_time=obj["request_time"],
        )
