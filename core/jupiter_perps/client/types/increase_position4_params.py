from __future__ import annotations
import typing
from dataclasses import dataclass
from construct import Container
import borsh_construct as borsh


class IncreasePosition4ParamsJSON(typing.TypedDict):
    pass


@dataclass
class IncreasePosition4Params:
    layout: typing.ClassVar = borsh.CStruct()

    @classmethod
    def from_decoded(cls, obj: Container) -> "IncreasePosition4Params":
        return cls()

    def to_encodable(self) -> dict[str, typing.Any]:
        return {}

    def to_json(self) -> IncreasePosition4ParamsJSON:
        return {}

    @classmethod
    def from_json(cls, obj: IncreasePosition4ParamsJSON) -> "IncreasePosition4Params":
        return cls()
