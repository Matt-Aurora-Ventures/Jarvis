from __future__ import annotations
import typing
from dataclasses import dataclass
from anchorpy.borsh_extension import EnumForCodegen
import borsh_construct as borsh


class NoneJSON(typing.TypedDict):
    kind: typing.Literal["None"]


class IncreaseJSON(typing.TypedDict):
    kind: typing.Literal["Increase"]


class DecreaseJSON(typing.TypedDict):
    kind: typing.Literal["Decrease"]


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
class Increase:
    discriminator: typing.ClassVar = 1
    kind: typing.ClassVar = "Increase"

    @classmethod
    def to_json(cls) -> IncreaseJSON:
        return IncreaseJSON(
            kind="Increase",
        )

    @classmethod
    def to_encodable(cls) -> dict:
        return {
            "Increase": {},
        }


@dataclass
class Decrease:
    discriminator: typing.ClassVar = 2
    kind: typing.ClassVar = "Decrease"

    @classmethod
    def to_json(cls) -> DecreaseJSON:
        return DecreaseJSON(
            kind="Decrease",
        )

    @classmethod
    def to_encodable(cls) -> dict:
        return {
            "Decrease": {},
        }


RequestChangeKind = typing.Union[None_, Increase, Decrease]
RequestChangeJSON = typing.Union[NoneJSON, IncreaseJSON, DecreaseJSON]


def from_decoded(obj: dict) -> RequestChangeKind:
    if not isinstance(obj, dict):
        raise ValueError("Invalid enum object")
    if "None" in obj:
        return None_()
    if "Increase" in obj:
        return Increase()
    if "Decrease" in obj:
        return Decrease()
    raise ValueError("Invalid enum object")


def from_json(obj: RequestChangeJSON) -> RequestChangeKind:
    if obj["kind"] == "None":
        return None_()
    if obj["kind"] == "Increase":
        return Increase()
    if obj["kind"] == "Decrease":
        return Decrease()
    kind = obj["kind"]
    raise ValueError(f"Unrecognized enum kind: {kind}")


layout = EnumForCodegen(
    "None" / borsh.CStruct(), "Increase" / borsh.CStruct(), "Decrease" / borsh.CStruct()
)
