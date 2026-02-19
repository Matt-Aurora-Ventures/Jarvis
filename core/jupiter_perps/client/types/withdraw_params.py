from __future__ import annotations
import typing
from dataclasses import dataclass
from construct import Container
import borsh_construct as borsh


class WithdrawParamsJSON(typing.TypedDict):
    amount: int


@dataclass
class WithdrawParams:
    layout: typing.ClassVar = borsh.CStruct("amount" / borsh.U64)
    amount: int

    @classmethod
    def from_decoded(cls, obj: Container) -> "WithdrawParams":
        return cls(amount=obj.amount)

    def to_encodable(self) -> dict[str, typing.Any]:
        return {"amount": self.amount}

    def to_json(self) -> WithdrawParamsJSON:
        return {"amount": self.amount}

    @classmethod
    def from_json(cls, obj: WithdrawParamsJSON) -> "WithdrawParams":
        return cls(amount=obj["amount"])
