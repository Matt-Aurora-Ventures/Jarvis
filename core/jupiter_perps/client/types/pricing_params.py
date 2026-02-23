from __future__ import annotations
import typing
from dataclasses import dataclass
from construct import Container
import borsh_construct as borsh


class PricingParamsJSON(typing.TypedDict):
    trade_impact_fee_scalar: int
    buffer: int
    swap_spread: int
    max_leverage: int
    max_global_long_sizes: int
    max_global_short_sizes: int


@dataclass
class PricingParams:
    layout: typing.ClassVar = borsh.CStruct(
        "trade_impact_fee_scalar" / borsh.U64,
        "buffer" / borsh.U64,
        "swap_spread" / borsh.U64,
        "max_leverage" / borsh.U64,
        "max_global_long_sizes" / borsh.U64,
        "max_global_short_sizes" / borsh.U64,
    )
    trade_impact_fee_scalar: int
    buffer: int
    swap_spread: int
    max_leverage: int
    max_global_long_sizes: int
    max_global_short_sizes: int

    @classmethod
    def from_decoded(cls, obj: Container) -> "PricingParams":
        return cls(
            trade_impact_fee_scalar=obj.trade_impact_fee_scalar,
            buffer=obj.buffer,
            swap_spread=obj.swap_spread,
            max_leverage=obj.max_leverage,
            max_global_long_sizes=obj.max_global_long_sizes,
            max_global_short_sizes=obj.max_global_short_sizes,
        )

    def to_encodable(self) -> dict[str, typing.Any]:
        return {
            "trade_impact_fee_scalar": self.trade_impact_fee_scalar,
            "buffer": self.buffer,
            "swap_spread": self.swap_spread,
            "max_leverage": self.max_leverage,
            "max_global_long_sizes": self.max_global_long_sizes,
            "max_global_short_sizes": self.max_global_short_sizes,
        }

    def to_json(self) -> PricingParamsJSON:
        return {
            "trade_impact_fee_scalar": self.trade_impact_fee_scalar,
            "buffer": self.buffer,
            "swap_spread": self.swap_spread,
            "max_leverage": self.max_leverage,
            "max_global_long_sizes": self.max_global_long_sizes,
            "max_global_short_sizes": self.max_global_short_sizes,
        }

    @classmethod
    def from_json(cls, obj: PricingParamsJSON) -> "PricingParams":
        return cls(
            trade_impact_fee_scalar=obj["trade_impact_fee_scalar"],
            buffer=obj["buffer"],
            swap_spread=obj["swap_spread"],
            max_leverage=obj["max_leverage"],
            max_global_long_sizes=obj["max_global_long_sizes"],
            max_global_short_sizes=obj["max_global_short_sizes"],
        )
