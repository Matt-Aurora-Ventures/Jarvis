from __future__ import annotations
import typing
from dataclasses import dataclass
from construct import Container
import borsh_construct as borsh


class JumpRateStateJSON(typing.TypedDict):
    min_rate_bps: int
    max_rate_bps: int
    target_rate_bps: int
    target_utilization_rate: int


@dataclass
class JumpRateState:
    layout: typing.ClassVar = borsh.CStruct(
        "min_rate_bps" / borsh.U64,
        "max_rate_bps" / borsh.U64,
        "target_rate_bps" / borsh.U64,
        "target_utilization_rate" / borsh.U64,
    )
    min_rate_bps: int
    max_rate_bps: int
    target_rate_bps: int
    target_utilization_rate: int

    @classmethod
    def from_decoded(cls, obj: Container) -> "JumpRateState":
        return cls(
            min_rate_bps=obj.min_rate_bps,
            max_rate_bps=obj.max_rate_bps,
            target_rate_bps=obj.target_rate_bps,
            target_utilization_rate=obj.target_utilization_rate,
        )

    def to_encodable(self) -> dict[str, typing.Any]:
        return {
            "min_rate_bps": self.min_rate_bps,
            "max_rate_bps": self.max_rate_bps,
            "target_rate_bps": self.target_rate_bps,
            "target_utilization_rate": self.target_utilization_rate,
        }

    def to_json(self) -> JumpRateStateJSON:
        return {
            "min_rate_bps": self.min_rate_bps,
            "max_rate_bps": self.max_rate_bps,
            "target_rate_bps": self.target_rate_bps,
            "target_utilization_rate": self.target_utilization_rate,
        }

    @classmethod
    def from_json(cls, obj: JumpRateStateJSON) -> "JumpRateState":
        return cls(
            min_rate_bps=obj["min_rate_bps"],
            max_rate_bps=obj["max_rate_bps"],
            target_rate_bps=obj["target_rate_bps"],
            target_utilization_rate=obj["target_utilization_rate"],
        )
