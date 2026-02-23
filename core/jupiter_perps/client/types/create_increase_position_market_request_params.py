from __future__ import annotations
from . import (
    side,
)
import typing
from dataclasses import dataclass
from construct import Container
import borsh_construct as borsh


class CreateIncreasePositionMarketRequestParamsJSON(typing.TypedDict):
    size_usd_delta: int
    collateral_token_delta: int
    side: side.SideJSON
    price_slippage: int
    jupiter_minimum_out: typing.Optional[int]
    counter: int


@dataclass
class CreateIncreasePositionMarketRequestParams:
    layout: typing.ClassVar = borsh.CStruct(
        "size_usd_delta" / borsh.U64,
        "collateral_token_delta" / borsh.U64,
        "side" / side.layout,
        "price_slippage" / borsh.U64,
        "jupiter_minimum_out" / borsh.Option(borsh.U64),
        "counter" / borsh.U64,
    )
    size_usd_delta: int
    collateral_token_delta: int
    side: side.SideKind
    price_slippage: int
    jupiter_minimum_out: typing.Optional[int]
    counter: int

    @classmethod
    def from_decoded(
        cls, obj: Container
    ) -> "CreateIncreasePositionMarketRequestParams":
        return cls(
            size_usd_delta=obj.size_usd_delta,
            collateral_token_delta=obj.collateral_token_delta,
            side=side.from_decoded(obj.side),
            price_slippage=obj.price_slippage,
            jupiter_minimum_out=obj.jupiter_minimum_out,
            counter=obj.counter,
        )

    def to_encodable(self) -> dict[str, typing.Any]:
        return {
            "size_usd_delta": self.size_usd_delta,
            "collateral_token_delta": self.collateral_token_delta,
            "side": self.side.to_encodable(),
            "price_slippage": self.price_slippage,
            "jupiter_minimum_out": self.jupiter_minimum_out,
            "counter": self.counter,
        }

    def to_json(self) -> CreateIncreasePositionMarketRequestParamsJSON:
        return {
            "size_usd_delta": self.size_usd_delta,
            "collateral_token_delta": self.collateral_token_delta,
            "side": self.side.to_json(),
            "price_slippage": self.price_slippage,
            "jupiter_minimum_out": self.jupiter_minimum_out,
            "counter": self.counter,
        }

    @classmethod
    def from_json(
        cls, obj: CreateIncreasePositionMarketRequestParamsJSON
    ) -> "CreateIncreasePositionMarketRequestParams":
        return cls(
            size_usd_delta=obj["size_usd_delta"],
            collateral_token_delta=obj["collateral_token_delta"],
            side=side.from_json(obj["side"]),
            price_slippage=obj["price_slippage"],
            jupiter_minimum_out=obj["jupiter_minimum_out"],
            counter=obj["counter"],
        )
