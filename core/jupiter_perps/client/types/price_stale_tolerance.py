from __future__ import annotations
import typing
from dataclasses import dataclass
from anchorpy.borsh_extension import EnumForCodegen
import borsh_construct as borsh


class StrictJSON(typing.TypedDict):
    kind: typing.Literal["Strict"]


class LooseJSON(typing.TypedDict):
    kind: typing.Literal["Loose"]


@dataclass
class Strict:
    discriminator: typing.ClassVar = 0
    kind: typing.ClassVar = "Strict"

    @classmethod
    def to_json(cls) -> StrictJSON:
        return StrictJSON(
            kind="Strict",
        )

    @classmethod
    def to_encodable(cls) -> dict:
        return {
            "Strict": {},
        }


@dataclass
class Loose:
    discriminator: typing.ClassVar = 1
    kind: typing.ClassVar = "Loose"

    @classmethod
    def to_json(cls) -> LooseJSON:
        return LooseJSON(
            kind="Loose",
        )

    @classmethod
    def to_encodable(cls) -> dict:
        return {
            "Loose": {},
        }


PriceStaleToleranceKind = typing.Union[Strict, Loose]
PriceStaleToleranceJSON = typing.Union[StrictJSON, LooseJSON]


def from_decoded(obj: dict) -> PriceStaleToleranceKind:
    if not isinstance(obj, dict):
        raise ValueError("Invalid enum object")
    if "Strict" in obj:
        return Strict()
    if "Loose" in obj:
        return Loose()
    raise ValueError("Invalid enum object")


def from_json(obj: PriceStaleToleranceJSON) -> PriceStaleToleranceKind:
    if obj["kind"] == "Strict":
        return Strict()
    if obj["kind"] == "Loose":
        return Loose()
    kind = obj["kind"]
    raise ValueError(f"Unrecognized enum kind: {kind}")


layout = EnumForCodegen("Strict" / borsh.CStruct(), "Loose" / borsh.CStruct())
