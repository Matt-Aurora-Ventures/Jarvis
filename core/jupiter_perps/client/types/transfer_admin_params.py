from __future__ import annotations
import typing
from dataclasses import dataclass
from construct import Container
import borsh_construct as borsh


class TransferAdminParamsJSON(typing.TypedDict):
    pass


@dataclass
class TransferAdminParams:
    layout: typing.ClassVar = borsh.CStruct()

    @classmethod
    def from_decoded(cls, obj: Container) -> "TransferAdminParams":
        return cls()

    def to_encodable(self) -> dict[str, typing.Any]:
        return {}

    def to_json(self) -> TransferAdminParamsJSON:
        return {}

    @classmethod
    def from_json(cls, obj: TransferAdminParamsJSON) -> "TransferAdminParams":
        return cls()
