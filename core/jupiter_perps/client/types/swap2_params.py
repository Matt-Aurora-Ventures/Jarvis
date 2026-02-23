from __future__ import annotations
import typing
from dataclasses import dataclass
from construct import Container
import borsh_construct as borsh


class Swap2ParamsJSON(typing.TypedDict):
    amount_in: int
    min_amount_out: int


@dataclass
class Swap2Params:
    layout: typing.ClassVar = borsh.CStruct(
        "amount_in" / borsh.U64, "min_amount_out" / borsh.U64
    )
    amount_in: int
    min_amount_out: int

    @classmethod
    def from_decoded(cls, obj: Container) -> "Swap2Params":
        return cls(amount_in=obj.amount_in, min_amount_out=obj.min_amount_out)

    def to_encodable(self) -> dict[str, typing.Any]:
        return {"amount_in": self.amount_in, "min_amount_out": self.min_amount_out}

    def to_json(self) -> Swap2ParamsJSON:
        return {"amount_in": self.amount_in, "min_amount_out": self.min_amount_out}

    @classmethod
    def from_json(cls, obj: Swap2ParamsJSON) -> "Swap2Params":
        return cls(amount_in=obj["amount_in"], min_amount_out=obj["min_amount_out"])
