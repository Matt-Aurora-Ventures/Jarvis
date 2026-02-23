from __future__ import annotations
import typing
from dataclasses import dataclass
from anchorpy.borsh_extension import EnumForCodegen
import borsh_construct as borsh


class IncreaseJSON(typing.TypedDict):
    kind: typing.Literal["Increase"]


class DecreaseJSON(typing.TypedDict):
    kind: typing.Literal["Decrease"]


@dataclass
class Increase:
    discriminator: typing.ClassVar = 0
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
    discriminator: typing.ClassVar = 1
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


TradePoolTypeKind = typing.Union[Increase, Decrease]
TradePoolTypeJSON = typing.Union[IncreaseJSON, DecreaseJSON]


def from_decoded(obj: dict) -> TradePoolTypeKind:
    if not isinstance(obj, dict):
        raise ValueError("Invalid enum object")
    if "Increase" in obj:
        return Increase()
    if "Decrease" in obj:
        return Decrease()
    raise ValueError("Invalid enum object")


def from_json(obj: TradePoolTypeJSON) -> TradePoolTypeKind:
    if obj["kind"] == "Increase":
        return Increase()
    if obj["kind"] == "Decrease":
        return Decrease()
    kind = obj["kind"]
    raise ValueError(f"Unrecognized enum kind: {kind}")


layout = EnumForCodegen("Increase" / borsh.CStruct(), "Decrease" / borsh.CStruct())
