from __future__ import annotations
import typing
from dataclasses import dataclass
from construct import Container
import borsh_construct as borsh


class WithdrawFees2ParamsJSON(typing.TypedDict):
    pass


@dataclass
class WithdrawFees2Params:
    layout: typing.ClassVar = borsh.CStruct()

    @classmethod
    def from_decoded(cls, obj: Container) -> "WithdrawFees2Params":
        return cls()

    def to_encodable(self) -> dict[str, typing.Any]:
        return {}

    def to_json(self) -> WithdrawFees2ParamsJSON:
        return {}

    @classmethod
    def from_json(cls, obj: WithdrawFees2ParamsJSON) -> "WithdrawFees2Params":
        return cls()
