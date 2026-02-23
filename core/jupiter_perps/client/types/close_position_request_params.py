from __future__ import annotations
import typing
from dataclasses import dataclass
from construct import Container
import borsh_construct as borsh


class ClosePositionRequestParamsJSON(typing.TypedDict):
    pass


@dataclass
class ClosePositionRequestParams:
    layout: typing.ClassVar = borsh.CStruct()

    @classmethod
    def from_decoded(cls, obj: Container) -> "ClosePositionRequestParams":
        return cls()

    def to_encodable(self) -> dict[str, typing.Any]:
        return {}

    def to_json(self) -> ClosePositionRequestParamsJSON:
        return {}

    @classmethod
    def from_json(
        cls, obj: ClosePositionRequestParamsJSON
    ) -> "ClosePositionRequestParams":
        return cls()
