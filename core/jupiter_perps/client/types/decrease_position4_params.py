from __future__ import annotations
import typing
from dataclasses import dataclass
from construct import Container
import borsh_construct as borsh


class DecreasePosition4ParamsJSON(typing.TypedDict):
    pass


@dataclass
class DecreasePosition4Params:
    layout: typing.ClassVar = borsh.CStruct()

    @classmethod
    def from_decoded(cls, obj: Container) -> "DecreasePosition4Params":
        return cls()

    def to_encodable(self) -> dict[str, typing.Any]:
        return {}

    def to_json(self) -> DecreasePosition4ParamsJSON:
        return {}

    @classmethod
    def from_json(cls, obj: DecreasePosition4ParamsJSON) -> "DecreasePosition4Params":
        return cls()
