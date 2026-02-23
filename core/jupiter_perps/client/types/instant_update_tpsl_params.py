from __future__ import annotations
import typing
from dataclasses import dataclass
from construct import Container
import borsh_construct as borsh


class InstantUpdateTpslParamsJSON(typing.TypedDict):
    size_usd_delta: int
    trigger_price: int
    request_time: int


@dataclass
class InstantUpdateTpslParams:
    layout: typing.ClassVar = borsh.CStruct(
        "size_usd_delta" / borsh.U64,
        "trigger_price" / borsh.U64,
        "request_time" / borsh.I64,
    )
    size_usd_delta: int
    trigger_price: int
    request_time: int

    @classmethod
    def from_decoded(cls, obj: Container) -> "InstantUpdateTpslParams":
        return cls(
            size_usd_delta=obj.size_usd_delta,
            trigger_price=obj.trigger_price,
            request_time=obj.request_time,
        )

    def to_encodable(self) -> dict[str, typing.Any]:
        return {
            "size_usd_delta": self.size_usd_delta,
            "trigger_price": self.trigger_price,
            "request_time": self.request_time,
        }

    def to_json(self) -> InstantUpdateTpslParamsJSON:
        return {
            "size_usd_delta": self.size_usd_delta,
            "trigger_price": self.trigger_price,
            "request_time": self.request_time,
        }

    @classmethod
    def from_json(cls, obj: InstantUpdateTpslParamsJSON) -> "InstantUpdateTpslParams":
        return cls(
            size_usd_delta=obj["size_usd_delta"],
            trigger_price=obj["trigger_price"],
            request_time=obj["request_time"],
        )
