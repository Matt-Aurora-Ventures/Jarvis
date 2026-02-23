from __future__ import annotations
import typing
from dataclasses import dataclass
from construct import Container
import borsh_construct as borsh


class InstantCreateTpslParamsJSON(typing.TypedDict):
    collateral_usd_delta: int
    size_usd_delta: int
    trigger_price: int
    trigger_above_threshold: bool
    entire_position: bool
    counter: int
    request_time: int


@dataclass
class InstantCreateTpslParams:
    layout: typing.ClassVar = borsh.CStruct(
        "collateral_usd_delta" / borsh.U64,
        "size_usd_delta" / borsh.U64,
        "trigger_price" / borsh.U64,
        "trigger_above_threshold" / borsh.Bool,
        "entire_position" / borsh.Bool,
        "counter" / borsh.U64,
        "request_time" / borsh.I64,
    )
    collateral_usd_delta: int
    size_usd_delta: int
    trigger_price: int
    trigger_above_threshold: bool
    entire_position: bool
    counter: int
    request_time: int

    @classmethod
    def from_decoded(cls, obj: Container) -> "InstantCreateTpslParams":
        return cls(
            collateral_usd_delta=obj.collateral_usd_delta,
            size_usd_delta=obj.size_usd_delta,
            trigger_price=obj.trigger_price,
            trigger_above_threshold=obj.trigger_above_threshold,
            entire_position=obj.entire_position,
            counter=obj.counter,
            request_time=obj.request_time,
        )

    def to_encodable(self) -> dict[str, typing.Any]:
        return {
            "collateral_usd_delta": self.collateral_usd_delta,
            "size_usd_delta": self.size_usd_delta,
            "trigger_price": self.trigger_price,
            "trigger_above_threshold": self.trigger_above_threshold,
            "entire_position": self.entire_position,
            "counter": self.counter,
            "request_time": self.request_time,
        }

    def to_json(self) -> InstantCreateTpslParamsJSON:
        return {
            "collateral_usd_delta": self.collateral_usd_delta,
            "size_usd_delta": self.size_usd_delta,
            "trigger_price": self.trigger_price,
            "trigger_above_threshold": self.trigger_above_threshold,
            "entire_position": self.entire_position,
            "counter": self.counter,
            "request_time": self.request_time,
        }

    @classmethod
    def from_json(cls, obj: InstantCreateTpslParamsJSON) -> "InstantCreateTpslParams":
        return cls(
            collateral_usd_delta=obj["collateral_usd_delta"],
            size_usd_delta=obj["size_usd_delta"],
            trigger_price=obj["trigger_price"],
            trigger_above_threshold=obj["trigger_above_threshold"],
            entire_position=obj["entire_position"],
            counter=obj["counter"],
            request_time=obj["request_time"],
        )
