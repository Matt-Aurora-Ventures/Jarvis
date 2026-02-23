from __future__ import annotations
import typing
from dataclasses import dataclass
from anchorpy.borsh_extension import EnumForCodegen
import borsh_construct as borsh


class MarketJSON(typing.TypedDict):
    kind: typing.Literal["Market"]


class TriggerJSON(typing.TypedDict):
    kind: typing.Literal["Trigger"]


@dataclass
class Market:
    discriminator: typing.ClassVar = 0
    kind: typing.ClassVar = "Market"

    @classmethod
    def to_json(cls) -> MarketJSON:
        return MarketJSON(
            kind="Market",
        )

    @classmethod
    def to_encodable(cls) -> dict:
        return {
            "Market": {},
        }


@dataclass
class Trigger:
    discriminator: typing.ClassVar = 1
    kind: typing.ClassVar = "Trigger"

    @classmethod
    def to_json(cls) -> TriggerJSON:
        return TriggerJSON(
            kind="Trigger",
        )

    @classmethod
    def to_encodable(cls) -> dict:
        return {
            "Trigger": {},
        }


RequestTypeKind = typing.Union[Market, Trigger]
RequestTypeJSON = typing.Union[MarketJSON, TriggerJSON]


def from_decoded(obj: dict) -> RequestTypeKind:
    if not isinstance(obj, dict):
        raise ValueError("Invalid enum object")
    if "Market" in obj:
        return Market()
    if "Trigger" in obj:
        return Trigger()
    raise ValueError("Invalid enum object")


def from_json(obj: RequestTypeJSON) -> RequestTypeKind:
    if obj["kind"] == "Market":
        return Market()
    if obj["kind"] == "Trigger":
        return Trigger()
    kind = obj["kind"]
    raise ValueError(f"Unrecognized enum kind: {kind}")


layout = EnumForCodegen("Market" / borsh.CStruct(), "Trigger" / borsh.CStruct())
