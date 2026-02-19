from __future__ import annotations
import typing
from dataclasses import dataclass
from construct import Container
import borsh_construct as borsh


class IncreasePositionWithInternalSwapParamsJSON(typing.TypedDict):
    pass


@dataclass
class IncreasePositionWithInternalSwapParams:
    layout: typing.ClassVar = borsh.CStruct()

    @classmethod
    def from_decoded(cls, obj: Container) -> "IncreasePositionWithInternalSwapParams":
        return cls()

    def to_encodable(self) -> dict[str, typing.Any]:
        return {}

    def to_json(self) -> IncreasePositionWithInternalSwapParamsJSON:
        return {}

    @classmethod
    def from_json(
        cls, obj: IncreasePositionWithInternalSwapParamsJSON
    ) -> "IncreasePositionWithInternalSwapParams":
        return cls()
