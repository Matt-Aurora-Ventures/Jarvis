from __future__ import annotations
import typing
from dataclasses import dataclass
from construct import Container
import borsh_construct as borsh


class LiquidateBorrowPositionParamsJSON(typing.TypedDict):
    pass


@dataclass
class LiquidateBorrowPositionParams:
    layout: typing.ClassVar = borsh.CStruct()

    @classmethod
    def from_decoded(cls, obj: Container) -> "LiquidateBorrowPositionParams":
        return cls()

    def to_encodable(self) -> dict[str, typing.Any]:
        return {}

    def to_json(self) -> LiquidateBorrowPositionParamsJSON:
        return {}

    @classmethod
    def from_json(
        cls, obj: LiquidateBorrowPositionParamsJSON
    ) -> "LiquidateBorrowPositionParams":
        return cls()
