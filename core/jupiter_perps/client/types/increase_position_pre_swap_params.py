from __future__ import annotations
import typing
from dataclasses import dataclass
from construct import Container
import borsh_construct as borsh


class IncreasePositionPreSwapParamsJSON(typing.TypedDict):
    pass


@dataclass
class IncreasePositionPreSwapParams:
    layout: typing.ClassVar = borsh.CStruct()

    @classmethod
    def from_decoded(cls, obj: Container) -> "IncreasePositionPreSwapParams":
        return cls()

    def to_encodable(self) -> dict[str, typing.Any]:
        return {}

    def to_json(self) -> IncreasePositionPreSwapParamsJSON:
        return {}

    @classmethod
    def from_json(
        cls, obj: IncreasePositionPreSwapParamsJSON
    ) -> "IncreasePositionPreSwapParams":
        return cls()
