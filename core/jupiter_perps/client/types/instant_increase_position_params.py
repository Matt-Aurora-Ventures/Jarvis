from __future__ import annotations
from . import (
    side,
)
import typing
from dataclasses import dataclass
from construct import Container
import borsh_construct as borsh


class InstantIncreasePositionParamsJSON(typing.TypedDict):
    size_usd_delta: int
    collateral_token_delta: typing.Optional[int]
    side: side.SideJSON
    price_slippage: int
    request_time: int


@dataclass
class InstantIncreasePositionParams:
    layout: typing.ClassVar = borsh.CStruct(
        "size_usd_delta" / borsh.U64,
        "collateral_token_delta" / borsh.Option(borsh.U64),
        "side" / side.layout,
        "price_slippage" / borsh.U64,
        "request_time" / borsh.I64,
    )
    size_usd_delta: int
    collateral_token_delta: typing.Optional[int]
    side: side.SideKind
    price_slippage: int
    request_time: int

    @classmethod
    def from_decoded(cls, obj: Container) -> "InstantIncreasePositionParams":
        return cls(
            size_usd_delta=obj.size_usd_delta,
            collateral_token_delta=obj.collateral_token_delta,
            side=side.from_decoded(obj.side),
            price_slippage=obj.price_slippage,
            request_time=obj.request_time,
        )

    def to_encodable(self) -> dict[str, typing.Any]:
        return {
            "size_usd_delta": self.size_usd_delta,
            "collateral_token_delta": self.collateral_token_delta,
            "side": self.side.to_encodable(),
            "price_slippage": self.price_slippage,
            "request_time": self.request_time,
        }

    def to_json(self) -> InstantIncreasePositionParamsJSON:
        return {
            "size_usd_delta": self.size_usd_delta,
            "collateral_token_delta": self.collateral_token_delta,
            "side": self.side.to_json(),
            "price_slippage": self.price_slippage,
            "request_time": self.request_time,
        }

    @classmethod
    def from_json(
        cls, obj: InstantIncreasePositionParamsJSON
    ) -> "InstantIncreasePositionParams":
        return cls(
            size_usd_delta=obj["size_usd_delta"],
            collateral_token_delta=obj["collateral_token_delta"],
            side=side.from_json(obj["side"]),
            price_slippage=obj["price_slippage"],
            request_time=obj["request_time"],
        )
