from __future__ import annotations
import typing
from dataclasses import dataclass
from construct import Container
import borsh_construct as borsh


class InitParamsJSON(typing.TypedDict):
    allow_swap: bool
    allow_add_liquidity: bool
    allow_remove_liquidity: bool
    allow_increase_position: bool
    allow_decrease_position: bool
    allow_collateral_withdrawal: bool
    allow_liquidate_position: bool


@dataclass
class InitParams:
    layout: typing.ClassVar = borsh.CStruct(
        "allow_swap" / borsh.Bool,
        "allow_add_liquidity" / borsh.Bool,
        "allow_remove_liquidity" / borsh.Bool,
        "allow_increase_position" / borsh.Bool,
        "allow_decrease_position" / borsh.Bool,
        "allow_collateral_withdrawal" / borsh.Bool,
        "allow_liquidate_position" / borsh.Bool,
    )
    allow_swap: bool
    allow_add_liquidity: bool
    allow_remove_liquidity: bool
    allow_increase_position: bool
    allow_decrease_position: bool
    allow_collateral_withdrawal: bool
    allow_liquidate_position: bool

    @classmethod
    def from_decoded(cls, obj: Container) -> "InitParams":
        return cls(
            allow_swap=obj.allow_swap,
            allow_add_liquidity=obj.allow_add_liquidity,
            allow_remove_liquidity=obj.allow_remove_liquidity,
            allow_increase_position=obj.allow_increase_position,
            allow_decrease_position=obj.allow_decrease_position,
            allow_collateral_withdrawal=obj.allow_collateral_withdrawal,
            allow_liquidate_position=obj.allow_liquidate_position,
        )

    def to_encodable(self) -> dict[str, typing.Any]:
        return {
            "allow_swap": self.allow_swap,
            "allow_add_liquidity": self.allow_add_liquidity,
            "allow_remove_liquidity": self.allow_remove_liquidity,
            "allow_increase_position": self.allow_increase_position,
            "allow_decrease_position": self.allow_decrease_position,
            "allow_collateral_withdrawal": self.allow_collateral_withdrawal,
            "allow_liquidate_position": self.allow_liquidate_position,
        }

    def to_json(self) -> InitParamsJSON:
        return {
            "allow_swap": self.allow_swap,
            "allow_add_liquidity": self.allow_add_liquidity,
            "allow_remove_liquidity": self.allow_remove_liquidity,
            "allow_increase_position": self.allow_increase_position,
            "allow_decrease_position": self.allow_decrease_position,
            "allow_collateral_withdrawal": self.allow_collateral_withdrawal,
            "allow_liquidate_position": self.allow_liquidate_position,
        }

    @classmethod
    def from_json(cls, obj: InitParamsJSON) -> "InitParams":
        return cls(
            allow_swap=obj["allow_swap"],
            allow_add_liquidity=obj["allow_add_liquidity"],
            allow_remove_liquidity=obj["allow_remove_liquidity"],
            allow_increase_position=obj["allow_increase_position"],
            allow_decrease_position=obj["allow_decrease_position"],
            allow_collateral_withdrawal=obj["allow_collateral_withdrawal"],
            allow_liquidate_position=obj["allow_liquidate_position"],
        )
