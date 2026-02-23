from __future__ import annotations
from . import (
    side,
)
import typing
from dataclasses import dataclass
from construct import Container
import borsh_construct as borsh


class InstantCreateLimitOrderParamsJSON(typing.TypedDict):
    size_usd_delta: int
    collateral_token_delta: int
    side: side.SideJSON
    trigger_price: int
    trigger_above_threshold: bool
    counter: int
    request_time: int


@dataclass
class InstantCreateLimitOrderParams:
    layout: typing.ClassVar = borsh.CStruct(
        "size_usd_delta" / borsh.U64,
        "collateral_token_delta" / borsh.U64,
        "side" / side.layout,
        "trigger_price" / borsh.U64,
        "trigger_above_threshold" / borsh.Bool,
        "counter" / borsh.U64,
        "request_time" / borsh.I64,
    )
    size_usd_delta: int
    collateral_token_delta: int
    side: side.SideKind
    trigger_price: int
    trigger_above_threshold: bool
    counter: int
    request_time: int

    @classmethod
    def from_decoded(cls, obj: Container) -> "InstantCreateLimitOrderParams":
        return cls(
            size_usd_delta=obj.size_usd_delta,
            collateral_token_delta=obj.collateral_token_delta,
            side=side.from_decoded(obj.side),
            trigger_price=obj.trigger_price,
            trigger_above_threshold=obj.trigger_above_threshold,
            counter=obj.counter,
            request_time=obj.request_time,
        )

    def to_encodable(self) -> dict[str, typing.Any]:
        return {
            "size_usd_delta": self.size_usd_delta,
            "collateral_token_delta": self.collateral_token_delta,
            "side": self.side.to_encodable(),
            "trigger_price": self.trigger_price,
            "trigger_above_threshold": self.trigger_above_threshold,
            "counter": self.counter,
            "request_time": self.request_time,
        }

    def to_json(self) -> InstantCreateLimitOrderParamsJSON:
        return {
            "size_usd_delta": self.size_usd_delta,
            "collateral_token_delta": self.collateral_token_delta,
            "side": self.side.to_json(),
            "trigger_price": self.trigger_price,
            "trigger_above_threshold": self.trigger_above_threshold,
            "counter": self.counter,
            "request_time": self.request_time,
        }

    @classmethod
    def from_json(
        cls, obj: InstantCreateLimitOrderParamsJSON
    ) -> "InstantCreateLimitOrderParams":
        return cls(
            size_usd_delta=obj["size_usd_delta"],
            collateral_token_delta=obj["collateral_token_delta"],
            side=side.from_json(obj["side"]),
            trigger_price=obj["trigger_price"],
            trigger_above_threshold=obj["trigger_above_threshold"],
            counter=obj["counter"],
            request_time=obj["request_time"],
        )
