from __future__ import annotations
from . import (
    permissions,
)
import typing
from dataclasses import dataclass
from construct import Container
import borsh_construct as borsh


class SetPerpetualsConfigParamsJSON(typing.TypedDict):
    permissions: permissions.PermissionsJSON


@dataclass
class SetPerpetualsConfigParams:
    layout: typing.ClassVar = borsh.CStruct(
        "permissions" / permissions.Permissions.layout
    )
    permissions: permissions.Permissions

    @classmethod
    def from_decoded(cls, obj: Container) -> "SetPerpetualsConfigParams":
        return cls(permissions=permissions.Permissions.from_decoded(obj.permissions))

    def to_encodable(self) -> dict[str, typing.Any]:
        return {"permissions": self.permissions.to_encodable()}

    def to_json(self) -> SetPerpetualsConfigParamsJSON:
        return {"permissions": self.permissions.to_json()}

    @classmethod
    def from_json(
        cls, obj: SetPerpetualsConfigParamsJSON
    ) -> "SetPerpetualsConfigParams":
        return cls(permissions=permissions.Permissions.from_json(obj["permissions"]))
