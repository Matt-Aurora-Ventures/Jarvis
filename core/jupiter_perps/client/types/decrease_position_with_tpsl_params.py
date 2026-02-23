from __future__ import annotations
import typing
from dataclasses import dataclass
from construct import Container
import borsh_construct as borsh


class DecreasePositionWithTpslParamsJSON(typing.TypedDict):
    pass


@dataclass
class DecreasePositionWithTpslParams:
    layout: typing.ClassVar = borsh.CStruct()

    @classmethod
    def from_decoded(cls, obj: Container) -> "DecreasePositionWithTpslParams":
        return cls()

    def to_encodable(self) -> dict[str, typing.Any]:
        return {}

    def to_json(self) -> DecreasePositionWithTpslParamsJSON:
        return {}

    @classmethod
    def from_json(
        cls, obj: DecreasePositionWithTpslParamsJSON
    ) -> "DecreasePositionWithTpslParams":
        return cls()
