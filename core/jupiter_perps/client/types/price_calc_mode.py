from __future__ import annotations
import typing
from dataclasses import dataclass
from anchorpy.borsh_extension import EnumForCodegen
import borsh_construct as borsh


class MinJSON(typing.TypedDict):
    kind: typing.Literal["Min"]


class MaxJSON(typing.TypedDict):
    kind: typing.Literal["Max"]


class IgnoreJSON(typing.TypedDict):
    kind: typing.Literal["Ignore"]


@dataclass
class Min:
    discriminator: typing.ClassVar = 0
    kind: typing.ClassVar = "Min"

    @classmethod
    def to_json(cls) -> MinJSON:
        return MinJSON(
            kind="Min",
        )

    @classmethod
    def to_encodable(cls) -> dict:
        return {
            "Min": {},
        }


@dataclass
class Max:
    discriminator: typing.ClassVar = 1
    kind: typing.ClassVar = "Max"

    @classmethod
    def to_json(cls) -> MaxJSON:
        return MaxJSON(
            kind="Max",
        )

    @classmethod
    def to_encodable(cls) -> dict:
        return {
            "Max": {},
        }


@dataclass
class Ignore:
    discriminator: typing.ClassVar = 2
    kind: typing.ClassVar = "Ignore"

    @classmethod
    def to_json(cls) -> IgnoreJSON:
        return IgnoreJSON(
            kind="Ignore",
        )

    @classmethod
    def to_encodable(cls) -> dict:
        return {
            "Ignore": {},
        }


PriceCalcModeKind = typing.Union[Min, Max, Ignore]
PriceCalcModeJSON = typing.Union[MinJSON, MaxJSON, IgnoreJSON]


def from_decoded(obj: dict) -> PriceCalcModeKind:
    if not isinstance(obj, dict):
        raise ValueError("Invalid enum object")
    if "Min" in obj:
        return Min()
    if "Max" in obj:
        return Max()
    if "Ignore" in obj:
        return Ignore()
    raise ValueError("Invalid enum object")


def from_json(obj: PriceCalcModeJSON) -> PriceCalcModeKind:
    if obj["kind"] == "Min":
        return Min()
    if obj["kind"] == "Max":
        return Max()
    if obj["kind"] == "Ignore":
        return Ignore()
    kind = obj["kind"]
    raise ValueError(f"Unrecognized enum kind: {kind}")


layout = EnumForCodegen(
    "Min" / borsh.CStruct(), "Max" / borsh.CStruct(), "Ignore" / borsh.CStruct()
)
