from __future__ import annotations
import typing
from dataclasses import dataclass
from construct import Container
import borsh_construct as borsh


class UpdateDecreasePositionRequest2ParamsJSON(typing.TypedDict):
    size_usd_delta: int
    trigger_price: int


@dataclass
class UpdateDecreasePositionRequest2Params:
    layout: typing.ClassVar = borsh.CStruct(
        "size_usd_delta" / borsh.U64, "trigger_price" / borsh.U64
    )
    size_usd_delta: int
    trigger_price: int

    @classmethod
    def from_decoded(cls, obj: Container) -> "UpdateDecreasePositionRequest2Params":
        return cls(size_usd_delta=obj.size_usd_delta, trigger_price=obj.trigger_price)

    def to_encodable(self) -> dict[str, typing.Any]:
        return {
            "size_usd_delta": self.size_usd_delta,
            "trigger_price": self.trigger_price,
        }

    def to_json(self) -> UpdateDecreasePositionRequest2ParamsJSON:
        return {
            "size_usd_delta": self.size_usd_delta,
            "trigger_price": self.trigger_price,
        }

    @classmethod
    def from_json(
        cls, obj: UpdateDecreasePositionRequest2ParamsJSON
    ) -> "UpdateDecreasePositionRequest2Params":
        return cls(
            size_usd_delta=obj["size_usd_delta"], trigger_price=obj["trigger_price"]
        )
