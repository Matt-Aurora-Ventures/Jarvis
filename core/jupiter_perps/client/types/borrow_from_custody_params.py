from __future__ import annotations
import typing
from dataclasses import dataclass
from construct import Container
import borsh_construct as borsh


class BorrowFromCustodyParamsJSON(typing.TypedDict):
    amount: int


@dataclass
class BorrowFromCustodyParams:
    layout: typing.ClassVar = borsh.CStruct("amount" / borsh.U64)
    amount: int

    @classmethod
    def from_decoded(cls, obj: Container) -> "BorrowFromCustodyParams":
        return cls(amount=obj.amount)

    def to_encodable(self) -> dict[str, typing.Any]:
        return {"amount": self.amount}

    def to_json(self) -> BorrowFromCustodyParamsJSON:
        return {"amount": self.amount}

    @classmethod
    def from_json(cls, obj: BorrowFromCustodyParamsJSON) -> "BorrowFromCustodyParams":
        return cls(amount=obj["amount"])
