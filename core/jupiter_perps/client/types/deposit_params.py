from __future__ import annotations
import typing
from dataclasses import dataclass
from construct import Container
import borsh_construct as borsh


class DepositParamsJSON(typing.TypedDict):
    amount: int


@dataclass
class DepositParams:
    layout: typing.ClassVar = borsh.CStruct("amount" / borsh.U64)
    amount: int

    @classmethod
    def from_decoded(cls, obj: Container) -> "DepositParams":
        return cls(amount=obj.amount)

    def to_encodable(self) -> dict[str, typing.Any]:
        return {"amount": self.amount}

    def to_json(self) -> DepositParamsJSON:
        return {"amount": self.amount}

    @classmethod
    def from_json(cls, obj: DepositParamsJSON) -> "DepositParams":
        return cls(amount=obj["amount"])
