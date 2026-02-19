from __future__ import annotations
import typing
from dataclasses import dataclass
from construct import Container
import borsh_construct as borsh


class SetMaxGlobalSizesParamsJSON(typing.TypedDict):
    max_global_long_size: int
    max_global_short_size: int
    recovery_id: int
    signature: list[int]
    reference_id: list[int]
    timestamp: int


@dataclass
class SetMaxGlobalSizesParams:
    layout: typing.ClassVar = borsh.CStruct(
        "max_global_long_size" / borsh.U64,
        "max_global_short_size" / borsh.U64,
        "recovery_id" / borsh.U8,
        "signature" / borsh.U8[64],
        "reference_id" / borsh.U8[16],
        "timestamp" / borsh.U64,
    )
    max_global_long_size: int
    max_global_short_size: int
    recovery_id: int
    signature: list[int]
    reference_id: list[int]
    timestamp: int

    @classmethod
    def from_decoded(cls, obj: Container) -> "SetMaxGlobalSizesParams":
        return cls(
            max_global_long_size=obj.max_global_long_size,
            max_global_short_size=obj.max_global_short_size,
            recovery_id=obj.recovery_id,
            signature=obj.signature,
            reference_id=obj.reference_id,
            timestamp=obj.timestamp,
        )

    def to_encodable(self) -> dict[str, typing.Any]:
        return {
            "max_global_long_size": self.max_global_long_size,
            "max_global_short_size": self.max_global_short_size,
            "recovery_id": self.recovery_id,
            "signature": self.signature,
            "reference_id": self.reference_id,
            "timestamp": self.timestamp,
        }

    def to_json(self) -> SetMaxGlobalSizesParamsJSON:
        return {
            "max_global_long_size": self.max_global_long_size,
            "max_global_short_size": self.max_global_short_size,
            "recovery_id": self.recovery_id,
            "signature": self.signature,
            "reference_id": self.reference_id,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_json(cls, obj: SetMaxGlobalSizesParamsJSON) -> "SetMaxGlobalSizesParams":
        return cls(
            max_global_long_size=obj["max_global_long_size"],
            max_global_short_size=obj["max_global_short_size"],
            recovery_id=obj["recovery_id"],
            signature=obj["signature"],
            reference_id=obj["reference_id"],
            timestamp=obj["timestamp"],
        )
