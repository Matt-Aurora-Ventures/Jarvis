from __future__ import annotations
import typing
from dataclasses import dataclass
from construct import Container
import borsh_construct as borsh


class PriceImpactBufferJSON(typing.TypedDict):
    open_interest: list[int]
    last_updated: int
    fee_factor: int
    exponent: float
    delta_imbalance_threshold_decimal: int
    max_fee_bps: int


@dataclass
class PriceImpactBuffer:
    layout: typing.ClassVar = borsh.CStruct(
        "open_interest" / borsh.I64[60],
        "last_updated" / borsh.I64,
        "fee_factor" / borsh.U64,
        "exponent" / borsh.F32,
        "delta_imbalance_threshold_decimal" / borsh.U64,
        "max_fee_bps" / borsh.U64,
    )
    open_interest: list[int]
    last_updated: int
    fee_factor: int
    exponent: float
    delta_imbalance_threshold_decimal: int
    max_fee_bps: int

    @classmethod
    def from_decoded(cls, obj: Container) -> "PriceImpactBuffer":
        return cls(
            open_interest=obj.open_interest,
            last_updated=obj.last_updated,
            fee_factor=obj.fee_factor,
            exponent=obj.exponent,
            delta_imbalance_threshold_decimal=obj.delta_imbalance_threshold_decimal,
            max_fee_bps=obj.max_fee_bps,
        )

    def to_encodable(self) -> dict[str, typing.Any]:
        return {
            "open_interest": self.open_interest,
            "last_updated": self.last_updated,
            "fee_factor": self.fee_factor,
            "exponent": self.exponent,
            "delta_imbalance_threshold_decimal": self.delta_imbalance_threshold_decimal,
            "max_fee_bps": self.max_fee_bps,
        }

    def to_json(self) -> PriceImpactBufferJSON:
        return {
            "open_interest": self.open_interest,
            "last_updated": self.last_updated,
            "fee_factor": self.fee_factor,
            "exponent": self.exponent,
            "delta_imbalance_threshold_decimal": self.delta_imbalance_threshold_decimal,
            "max_fee_bps": self.max_fee_bps,
        }

    @classmethod
    def from_json(cls, obj: PriceImpactBufferJSON) -> "PriceImpactBuffer":
        return cls(
            open_interest=obj["open_interest"],
            last_updated=obj["last_updated"],
            fee_factor=obj["fee_factor"],
            exponent=obj["exponent"],
            delta_imbalance_threshold_decimal=obj["delta_imbalance_threshold_decimal"],
            max_fee_bps=obj["max_fee_bps"],
        )
