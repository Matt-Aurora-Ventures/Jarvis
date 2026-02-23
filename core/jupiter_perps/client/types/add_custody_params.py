from __future__ import annotations
from . import (
    pricing_params,
    jump_rate_state,
    oracle_params,
    permissions,
)
import typing
from dataclasses import dataclass
from construct import Container
from solders.pubkey import Pubkey
from anchorpy.borsh_extension import BorshPubkey
import borsh_construct as borsh


class AddCustodyParamsJSON(typing.TypedDict):
    is_stable: bool
    oracle: oracle_params.OracleParamsJSON
    pricing: pricing_params.PricingParamsJSON
    permissions: permissions.PermissionsJSON
    hourly_funding_dbps: int
    target_ratio_bps: int
    increase_position_bps: int
    decrease_position_bps: int
    doves_oracle: str
    max_position_size_usd: int
    jump_rate: jump_rate_state.JumpRateStateJSON
    price_impact_fee_factor: int
    price_impact_exponent: float
    delta_imbalance_threshold_decimal: int
    max_fee_bps: int
    doves_ag_oracle: str


@dataclass
class AddCustodyParams:
    layout: typing.ClassVar = borsh.CStruct(
        "is_stable" / borsh.Bool,
        "oracle" / oracle_params.OracleParams.layout,
        "pricing" / pricing_params.PricingParams.layout,
        "permissions" / permissions.Permissions.layout,
        "hourly_funding_dbps" / borsh.U64,
        "target_ratio_bps" / borsh.U64,
        "increase_position_bps" / borsh.U64,
        "decrease_position_bps" / borsh.U64,
        "doves_oracle" / BorshPubkey,
        "max_position_size_usd" / borsh.U64,
        "jump_rate" / jump_rate_state.JumpRateState.layout,
        "price_impact_fee_factor" / borsh.U64,
        "price_impact_exponent" / borsh.F32,
        "delta_imbalance_threshold_decimal" / borsh.U64,
        "max_fee_bps" / borsh.U64,
        "doves_ag_oracle" / BorshPubkey,
    )
    is_stable: bool
    oracle: oracle_params.OracleParams
    pricing: pricing_params.PricingParams
    permissions: permissions.Permissions
    hourly_funding_dbps: int
    target_ratio_bps: int
    increase_position_bps: int
    decrease_position_bps: int
    doves_oracle: Pubkey
    max_position_size_usd: int
    jump_rate: jump_rate_state.JumpRateState
    price_impact_fee_factor: int
    price_impact_exponent: float
    delta_imbalance_threshold_decimal: int
    max_fee_bps: int
    doves_ag_oracle: Pubkey

    @classmethod
    def from_decoded(cls, obj: Container) -> "AddCustodyParams":
        return cls(
            is_stable=obj.is_stable,
            oracle=oracle_params.OracleParams.from_decoded(obj.oracle),
            pricing=pricing_params.PricingParams.from_decoded(obj.pricing),
            permissions=permissions.Permissions.from_decoded(obj.permissions),
            hourly_funding_dbps=obj.hourly_funding_dbps,
            target_ratio_bps=obj.target_ratio_bps,
            increase_position_bps=obj.increase_position_bps,
            decrease_position_bps=obj.decrease_position_bps,
            doves_oracle=obj.doves_oracle,
            max_position_size_usd=obj.max_position_size_usd,
            jump_rate=jump_rate_state.JumpRateState.from_decoded(obj.jump_rate),
            price_impact_fee_factor=obj.price_impact_fee_factor,
            price_impact_exponent=obj.price_impact_exponent,
            delta_imbalance_threshold_decimal=obj.delta_imbalance_threshold_decimal,
            max_fee_bps=obj.max_fee_bps,
            doves_ag_oracle=obj.doves_ag_oracle,
        )

    def to_encodable(self) -> dict[str, typing.Any]:
        return {
            "is_stable": self.is_stable,
            "oracle": self.oracle.to_encodable(),
            "pricing": self.pricing.to_encodable(),
            "permissions": self.permissions.to_encodable(),
            "hourly_funding_dbps": self.hourly_funding_dbps,
            "target_ratio_bps": self.target_ratio_bps,
            "increase_position_bps": self.increase_position_bps,
            "decrease_position_bps": self.decrease_position_bps,
            "doves_oracle": self.doves_oracle,
            "max_position_size_usd": self.max_position_size_usd,
            "jump_rate": self.jump_rate.to_encodable(),
            "price_impact_fee_factor": self.price_impact_fee_factor,
            "price_impact_exponent": self.price_impact_exponent,
            "delta_imbalance_threshold_decimal": self.delta_imbalance_threshold_decimal,
            "max_fee_bps": self.max_fee_bps,
            "doves_ag_oracle": self.doves_ag_oracle,
        }

    def to_json(self) -> AddCustodyParamsJSON:
        return {
            "is_stable": self.is_stable,
            "oracle": self.oracle.to_json(),
            "pricing": self.pricing.to_json(),
            "permissions": self.permissions.to_json(),
            "hourly_funding_dbps": self.hourly_funding_dbps,
            "target_ratio_bps": self.target_ratio_bps,
            "increase_position_bps": self.increase_position_bps,
            "decrease_position_bps": self.decrease_position_bps,
            "doves_oracle": str(self.doves_oracle),
            "max_position_size_usd": self.max_position_size_usd,
            "jump_rate": self.jump_rate.to_json(),
            "price_impact_fee_factor": self.price_impact_fee_factor,
            "price_impact_exponent": self.price_impact_exponent,
            "delta_imbalance_threshold_decimal": self.delta_imbalance_threshold_decimal,
            "max_fee_bps": self.max_fee_bps,
            "doves_ag_oracle": str(self.doves_ag_oracle),
        }

    @classmethod
    def from_json(cls, obj: AddCustodyParamsJSON) -> "AddCustodyParams":
        return cls(
            is_stable=obj["is_stable"],
            oracle=oracle_params.OracleParams.from_json(obj["oracle"]),
            pricing=pricing_params.PricingParams.from_json(obj["pricing"]),
            permissions=permissions.Permissions.from_json(obj["permissions"]),
            hourly_funding_dbps=obj["hourly_funding_dbps"],
            target_ratio_bps=obj["target_ratio_bps"],
            increase_position_bps=obj["increase_position_bps"],
            decrease_position_bps=obj["decrease_position_bps"],
            doves_oracle=Pubkey.from_string(obj["doves_oracle"]),
            max_position_size_usd=obj["max_position_size_usd"],
            jump_rate=jump_rate_state.JumpRateState.from_json(obj["jump_rate"]),
            price_impact_fee_factor=obj["price_impact_fee_factor"],
            price_impact_exponent=obj["price_impact_exponent"],
            delta_imbalance_threshold_decimal=obj["delta_imbalance_threshold_decimal"],
            max_fee_bps=obj["max_fee_bps"],
            doves_ag_oracle=Pubkey.from_string(obj["doves_ag_oracle"]),
        )
