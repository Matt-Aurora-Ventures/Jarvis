from __future__ import annotations
import typing
from dataclasses import dataclass
from construct import Container
import borsh_construct as borsh


class GetAddLiquidityAmountAndFee2ParamsJSON(typing.TypedDict):
    token_amount_in: int


@dataclass
class GetAddLiquidityAmountAndFee2Params:
    layout: typing.ClassVar = borsh.CStruct("token_amount_in" / borsh.U64)
    token_amount_in: int

    @classmethod
    def from_decoded(cls, obj: Container) -> "GetAddLiquidityAmountAndFee2Params":
        return cls(token_amount_in=obj.token_amount_in)

    def to_encodable(self) -> dict[str, typing.Any]:
        return {"token_amount_in": self.token_amount_in}

    def to_json(self) -> GetAddLiquidityAmountAndFee2ParamsJSON:
        return {"token_amount_in": self.token_amount_in}

    @classmethod
    def from_json(
        cls, obj: GetAddLiquidityAmountAndFee2ParamsJSON
    ) -> "GetAddLiquidityAmountAndFee2Params":
        return cls(token_amount_in=obj["token_amount_in"])
