from __future__ import annotations
import typing
from dataclasses import dataclass
from construct import Container
import borsh_construct as borsh


class LiquidateFullPosition4ParamsJSON(typing.TypedDict):
    pass


@dataclass
class LiquidateFullPosition4Params:
    layout: typing.ClassVar = borsh.CStruct()

    @classmethod
    def from_decoded(cls, obj: Container) -> "LiquidateFullPosition4Params":
        return cls()

    def to_encodable(self) -> dict[str, typing.Any]:
        return {}

    def to_json(self) -> LiquidateFullPosition4ParamsJSON:
        return {}

    @classmethod
    def from_json(
        cls, obj: LiquidateFullPosition4ParamsJSON
    ) -> "LiquidateFullPosition4Params":
        return cls()
