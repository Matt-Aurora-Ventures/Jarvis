from __future__ import annotations
import typing
from dataclasses import dataclass
from anchorpy.borsh_extension import EnumForCodegen
import borsh_construct as borsh


class NoneJSON(typing.TypedDict):
    kind: typing.Literal["None"]


class LongJSON(typing.TypedDict):
    kind: typing.Literal["Long"]


class ShortJSON(typing.TypedDict):
    kind: typing.Literal["Short"]


@dataclass
class None_:
    discriminator: typing.ClassVar = 0
    kind: typing.ClassVar = "None"

    @classmethod
    def to_json(cls) -> NoneJSON:
        return NoneJSON(
            kind="None",
        )

    @classmethod
    def to_encodable(cls) -> dict:
        return {
            "None": {},
        }


@dataclass
class Long:
    discriminator: typing.ClassVar = 1
    kind: typing.ClassVar = "Long"

    @classmethod
    def to_json(cls) -> LongJSON:
        return LongJSON(
            kind="Long",
        )

    @classmethod
    def to_encodable(cls) -> dict:
        return {
            "Long": {},
        }


@dataclass
class Short:
    discriminator: typing.ClassVar = 2
    kind: typing.ClassVar = "Short"

    @classmethod
    def to_json(cls) -> ShortJSON:
        return ShortJSON(
            kind="Short",
        )

    @classmethod
    def to_encodable(cls) -> dict:
        return {
            "Short": {},
        }


SideKind = typing.Union[None_, Long, Short]
SideJSON = typing.Union[NoneJSON, LongJSON, ShortJSON]


def from_decoded(obj: dict) -> SideKind:
    if not isinstance(obj, dict):
        raise ValueError("Invalid enum object")
    if "None" in obj:
        return None_()
    if "Long" in obj:
        return Long()
    if "Short" in obj:
        return Short()
    raise ValueError("Invalid enum object")


def from_json(obj: SideJSON) -> SideKind:
    if obj["kind"] == "None":
        return None_()
    if obj["kind"] == "Long":
        return Long()
    if obj["kind"] == "Short":
        return Short()
    kind = obj["kind"]
    raise ValueError(f"Unrecognized enum kind: {kind}")


layout = EnumForCodegen(
    "None" / borsh.CStruct(), "Long" / borsh.CStruct(), "Short" / borsh.CStruct()
)
