from __future__ import annotations
from . import (
    pricing_params,
    jump_rate_state,
    borrow_lend_params,
    oracle_params,
    permissions,
)
import typing
from dataclasses import dataclass
from construct import Container
from solders.pubkey import Pubkey
from anchorpy.borsh_extension import BorshPubkey
import borsh_construct as borsh


class SetCustodyConfigParamsJSON(typing.TypedDict):
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
    borrow_lend_parameters: borrow_lend_params.BorrowLendParamsJSON
    borrow_hourly_funding_dbps: int
    borrow_limit_in_token_amount: int
    min_interest_fee_bps: int
    min_interest_fee_grace_period_seconds: int


@dataclass
class SetCustodyConfigParams:
    layout: typing.ClassVar = borsh.CStruct(
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
        "borrow_lend_parameters" / borrow_lend_params.BorrowLendParams.layout,
        "borrow_hourly_funding_dbps" / borsh.U64,
        "borrow_limit_in_token_amount" / borsh.U64,
        "min_interest_fee_bps" / borsh.U64,
        "min_interest_fee_grace_period_seconds" / borsh.U64,
    )
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
    borrow_lend_parameters: borrow_lend_params.BorrowLendParams
    borrow_hourly_funding_dbps: int
    borrow_limit_in_token_amount: int
    min_interest_fee_bps: int
    min_interest_fee_grace_period_seconds: int

    @classmethod
    def from_decoded(cls, obj: Container) -> "SetCustodyConfigParams":
        return cls(
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
            borrow_lend_parameters=borrow_lend_params.BorrowLendParams.from_decoded(
                obj.borrow_lend_parameters
            ),
            borrow_hourly_funding_dbps=obj.borrow_hourly_funding_dbps,
            borrow_limit_in_token_amount=obj.borrow_limit_in_token_amount,
            min_interest_fee_bps=obj.min_interest_fee_bps,
            min_interest_fee_grace_period_seconds=obj.min_interest_fee_grace_period_seconds,
        )

    def to_encodable(self) -> dict[str, typing.Any]:
        return {
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
            "borrow_lend_parameters": self.borrow_lend_parameters.to_encodable(),
            "borrow_hourly_funding_dbps": self.borrow_hourly_funding_dbps,
            "borrow_limit_in_token_amount": self.borrow_limit_in_token_amount,
            "min_interest_fee_bps": self.min_interest_fee_bps,
            "min_interest_fee_grace_period_seconds": self.min_interest_fee_grace_period_seconds,
        }

    def to_json(self) -> SetCustodyConfigParamsJSON:
        return {
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
            "borrow_lend_parameters": self.borrow_lend_parameters.to_json(),
            "borrow_hourly_funding_dbps": self.borrow_hourly_funding_dbps,
            "borrow_limit_in_token_amount": self.borrow_limit_in_token_amount,
            "min_interest_fee_bps": self.min_interest_fee_bps,
            "min_interest_fee_grace_period_seconds": self.min_interest_fee_grace_period_seconds,
        }

    @classmethod
    def from_json(cls, obj: SetCustodyConfigParamsJSON) -> "SetCustodyConfigParams":
        return cls(
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
            borrow_lend_parameters=borrow_lend_params.BorrowLendParams.from_json(
                obj["borrow_lend_parameters"]
            ),
            borrow_hourly_funding_dbps=obj["borrow_hourly_funding_dbps"],
            borrow_limit_in_token_amount=obj["borrow_limit_in_token_amount"],
            min_interest_fee_bps=obj["min_interest_fee_bps"],
            min_interest_fee_grace_period_seconds=obj[
                "min_interest_fee_grace_period_seconds"
            ],
        )
