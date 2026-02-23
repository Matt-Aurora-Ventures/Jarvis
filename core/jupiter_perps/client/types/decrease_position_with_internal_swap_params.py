from __future__ import annotations
import typing
from dataclasses import dataclass
from construct import Container
import borsh_construct as borsh


class DecreasePositionWithInternalSwapParamsJSON(typing.TypedDict):
    pass


@dataclass
class DecreasePositionWithInternalSwapParams:
    layout: typing.ClassVar = borsh.CStruct()

    @classmethod
    def from_decoded(cls, obj: Container) -> "DecreasePositionWithInternalSwapParams":
        return cls()

    def to_encodable(self) -> dict[str, typing.Any]:
        return {}

    def to_json(self) -> DecreasePositionWithInternalSwapParamsJSON:
        return {}

    @classmethod
    def from_json(
        cls, obj: DecreasePositionWithInternalSwapParamsJSON
    ) -> "DecreasePositionWithInternalSwapParams":
        return cls()
