from __future__ import annotations
import typing
from dataclasses import dataclass
from construct import Container
import borsh_construct as borsh


class RepayToCustodyParamsJSON(typing.TypedDict):
    amount: int


@dataclass
class RepayToCustodyParams:
    layout: typing.ClassVar = borsh.CStruct("amount" / borsh.U64)
    amount: int

    @classmethod
    def from_decoded(cls, obj: Container) -> "RepayToCustodyParams":
        return cls(amount=obj.amount)

    def to_encodable(self) -> dict[str, typing.Any]:
        return {"amount": self.amount}

    def to_json(self) -> RepayToCustodyParamsJSON:
        return {"amount": self.amount}

    @classmethod
    def from_json(cls, obj: RepayToCustodyParamsJSON) -> "RepayToCustodyParams":
        return cls(amount=obj["amount"])
