from __future__ import annotations
import typing
from dataclasses import dataclass
from construct import Container
import borsh_construct as borsh


class OraclePriceJSON(typing.TypedDict):
    price: int
    exponent: int


@dataclass
class OraclePrice:
    layout: typing.ClassVar = borsh.CStruct("price" / borsh.U64, "exponent" / borsh.I32)
    price: int
    exponent: int

    @classmethod
    def from_decoded(cls, obj: Container) -> "OraclePrice":
        return cls(price=obj.price, exponent=obj.exponent)

    def to_encodable(self) -> dict[str, typing.Any]:
        return {"price": self.price, "exponent": self.exponent}

    def to_json(self) -> OraclePriceJSON:
        return {"price": self.price, "exponent": self.exponent}

    @classmethod
    def from_json(cls, obj: OraclePriceJSON) -> "OraclePrice":
        return cls(price=obj["price"], exponent=obj["exponent"])
