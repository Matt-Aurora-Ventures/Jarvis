from __future__ import annotations
import typing
from dataclasses import dataclass
from construct import Container
import borsh_construct as borsh


class CloseBorrowPositionParamsJSON(typing.TypedDict):
    pass


@dataclass
class CloseBorrowPositionParams:
    layout: typing.ClassVar = borsh.CStruct()

    @classmethod
    def from_decoded(cls, obj: Container) -> "CloseBorrowPositionParams":
        return cls()

    def to_encodable(self) -> dict[str, typing.Any]:
        return {}

    def to_json(self) -> CloseBorrowPositionParamsJSON:
        return {}

    @classmethod
    def from_json(
        cls, obj: CloseBorrowPositionParamsJSON
    ) -> "CloseBorrowPositionParams":
        return cls()
