from __future__ import annotations
import typing
from dataclasses import dataclass
from construct import Container
import borsh_construct as borsh


class RemoveLiquidity2ParamsJSON(typing.TypedDict):
    lp_amount_in: int
    min_amount_out: int


@dataclass
class RemoveLiquidity2Params:
    layout: typing.ClassVar = borsh.CStruct(
        "lp_amount_in" / borsh.U64, "min_amount_out" / borsh.U64
    )
    lp_amount_in: int
    min_amount_out: int

    @classmethod
    def from_decoded(cls, obj: Container) -> "RemoveLiquidity2Params":
        return cls(lp_amount_in=obj.lp_amount_in, min_amount_out=obj.min_amount_out)

    def to_encodable(self) -> dict[str, typing.Any]:
        return {
            "lp_amount_in": self.lp_amount_in,
            "min_amount_out": self.min_amount_out,
        }

    def to_json(self) -> RemoveLiquidity2ParamsJSON:
        return {
            "lp_amount_in": self.lp_amount_in,
            "min_amount_out": self.min_amount_out,
        }

    @classmethod
    def from_json(cls, obj: RemoveLiquidity2ParamsJSON) -> "RemoveLiquidity2Params":
        return cls(
            lp_amount_in=obj["lp_amount_in"], min_amount_out=obj["min_amount_out"]
        )
