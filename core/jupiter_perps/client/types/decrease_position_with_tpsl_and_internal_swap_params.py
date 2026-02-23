from __future__ import annotations
import typing
from dataclasses import dataclass
from construct import Container
import borsh_construct as borsh


class DecreasePositionWithTpslAndInternalSwapParamsJSON(typing.TypedDict):
    pass


@dataclass
class DecreasePositionWithTpslAndInternalSwapParams:
    layout: typing.ClassVar = borsh.CStruct()

    @classmethod
    def from_decoded(
        cls, obj: Container
    ) -> "DecreasePositionWithTpslAndInternalSwapParams":
        return cls()

    def to_encodable(self) -> dict[str, typing.Any]:
        return {}

    def to_json(self) -> DecreasePositionWithTpslAndInternalSwapParamsJSON:
        return {}

    @classmethod
    def from_json(
        cls, obj: DecreasePositionWithTpslAndInternalSwapParamsJSON
    ) -> "DecreasePositionWithTpslAndInternalSwapParams":
        return cls()
