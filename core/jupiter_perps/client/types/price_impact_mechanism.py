from __future__ import annotations
import typing
from dataclasses import dataclass
from anchorpy.borsh_extension import EnumForCodegen
import borsh_construct as borsh


class TradeSizeJSON(typing.TypedDict):
    kind: typing.Literal["TradeSize"]


class DeltaImbalanceJSON(typing.TypedDict):
    kind: typing.Literal["DeltaImbalance"]


@dataclass
class TradeSize:
    discriminator: typing.ClassVar = 0
    kind: typing.ClassVar = "TradeSize"

    @classmethod
    def to_json(cls) -> TradeSizeJSON:
        return TradeSizeJSON(
            kind="TradeSize",
        )

    @classmethod
    def to_encodable(cls) -> dict:
        return {
            "TradeSize": {},
        }


@dataclass
class DeltaImbalance:
    discriminator: typing.ClassVar = 1
    kind: typing.ClassVar = "DeltaImbalance"

    @classmethod
    def to_json(cls) -> DeltaImbalanceJSON:
        return DeltaImbalanceJSON(
            kind="DeltaImbalance",
        )

    @classmethod
    def to_encodable(cls) -> dict:
        return {
            "DeltaImbalance": {},
        }


PriceImpactMechanismKind = typing.Union[TradeSize, DeltaImbalance]
PriceImpactMechanismJSON = typing.Union[TradeSizeJSON, DeltaImbalanceJSON]


def from_decoded(obj: dict) -> PriceImpactMechanismKind:
    if not isinstance(obj, dict):
        raise ValueError("Invalid enum object")
    if "TradeSize" in obj:
        return TradeSize()
    if "DeltaImbalance" in obj:
        return DeltaImbalance()
    raise ValueError("Invalid enum object")


def from_json(obj: PriceImpactMechanismJSON) -> PriceImpactMechanismKind:
    if obj["kind"] == "TradeSize":
        return TradeSize()
    if obj["kind"] == "DeltaImbalance":
        return DeltaImbalance()
    kind = obj["kind"]
    raise ValueError(f"Unrecognized enum kind: {kind}")


layout = EnumForCodegen(
    "TradeSize" / borsh.CStruct(), "DeltaImbalance" / borsh.CStruct()
)
