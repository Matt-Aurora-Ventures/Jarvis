from __future__ import annotations
import typing
from dataclasses import dataclass
from construct import Container
import borsh_construct as borsh


class GetRemoveLiquidityAmountAndFee2ParamsJSON(typing.TypedDict):
    lp_amount_in: int


@dataclass
class GetRemoveLiquidityAmountAndFee2Params:
    layout: typing.ClassVar = borsh.CStruct("lp_amount_in" / borsh.U64)
    lp_amount_in: int

    @classmethod
    def from_decoded(cls, obj: Container) -> "GetRemoveLiquidityAmountAndFee2Params":
        return cls(lp_amount_in=obj.lp_amount_in)

    def to_encodable(self) -> dict[str, typing.Any]:
        return {"lp_amount_in": self.lp_amount_in}

    def to_json(self) -> GetRemoveLiquidityAmountAndFee2ParamsJSON:
        return {"lp_amount_in": self.lp_amount_in}

    @classmethod
    def from_json(
        cls, obj: GetRemoveLiquidityAmountAndFee2ParamsJSON
    ) -> "GetRemoveLiquidityAmountAndFee2Params":
        return cls(lp_amount_in=obj["lp_amount_in"])
