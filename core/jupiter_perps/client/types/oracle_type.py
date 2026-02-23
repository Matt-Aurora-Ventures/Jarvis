from __future__ import annotations
import typing
from dataclasses import dataclass
from anchorpy.borsh_extension import EnumForCodegen
import borsh_construct as borsh


class NoneJSON(typing.TypedDict):
    kind: typing.Literal["None"]


class TestJSON(typing.TypedDict):
    kind: typing.Literal["Test"]


class PythJSON(typing.TypedDict):
    kind: typing.Literal["Pyth"]


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
class Test:
    discriminator: typing.ClassVar = 1
    kind: typing.ClassVar = "Test"

    @classmethod
    def to_json(cls) -> TestJSON:
        return TestJSON(
            kind="Test",
        )

    @classmethod
    def to_encodable(cls) -> dict:
        return {
            "Test": {},
        }


@dataclass
class Pyth:
    discriminator: typing.ClassVar = 2
    kind: typing.ClassVar = "Pyth"

    @classmethod
    def to_json(cls) -> PythJSON:
        return PythJSON(
            kind="Pyth",
        )

    @classmethod
    def to_encodable(cls) -> dict:
        return {
            "Pyth": {},
        }


OracleTypeKind = typing.Union[None_, Test, Pyth]
OracleTypeJSON = typing.Union[NoneJSON, TestJSON, PythJSON]


def from_decoded(obj: dict) -> OracleTypeKind:
    if not isinstance(obj, dict):
        raise ValueError("Invalid enum object")
    if "None" in obj:
        return None_()
    if "Test" in obj:
        return Test()
    if "Pyth" in obj:
        return Pyth()
    raise ValueError("Invalid enum object")


def from_json(obj: OracleTypeJSON) -> OracleTypeKind:
    if obj["kind"] == "None":
        return None_()
    if obj["kind"] == "Test":
        return Test()
    if obj["kind"] == "Pyth":
        return Pyth()
    kind = obj["kind"]
    raise ValueError(f"Unrecognized enum kind: {kind}")


layout = EnumForCodegen(
    "None" / borsh.CStruct(), "Test" / borsh.CStruct(), "Pyth" / borsh.CStruct()
)
