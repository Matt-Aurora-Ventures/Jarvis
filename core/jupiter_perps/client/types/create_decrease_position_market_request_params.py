from __future__ import annotations
import typing
from dataclasses import dataclass
from construct import Container
import borsh_construct as borsh


class CreateDecreasePositionMarketRequestParamsJSON(typing.TypedDict):
    collateral_usd_delta: int
    size_usd_delta: int
    price_slippage: int
    jupiter_minimum_out: typing.Optional[int]
    entire_position: typing.Optional[bool]
    counter: int


@dataclass
class CreateDecreasePositionMarketRequestParams:
    layout: typing.ClassVar = borsh.CStruct(
        "collateral_usd_delta" / borsh.U64,
        "size_usd_delta" / borsh.U64,
        "price_slippage" / borsh.U64,
        "jupiter_minimum_out" / borsh.Option(borsh.U64),
        "entire_position" / borsh.Option(borsh.Bool),
        "counter" / borsh.U64,
    )
    collateral_usd_delta: int
    size_usd_delta: int
    price_slippage: int
    jupiter_minimum_out: typing.Optional[int]
    entire_position: typing.Optional[bool]
    counter: int

    @classmethod
    def from_decoded(
        cls, obj: Container
    ) -> "CreateDecreasePositionMarketRequestParams":
        return cls(
            collateral_usd_delta=obj.collateral_usd_delta,
            size_usd_delta=obj.size_usd_delta,
            price_slippage=obj.price_slippage,
            jupiter_minimum_out=obj.jupiter_minimum_out,
            entire_position=obj.entire_position,
            counter=obj.counter,
        )

    def to_encodable(self) -> dict[str, typing.Any]:
        return {
            "collateral_usd_delta": self.collateral_usd_delta,
            "size_usd_delta": self.size_usd_delta,
            "price_slippage": self.price_slippage,
            "jupiter_minimum_out": self.jupiter_minimum_out,
            "entire_position": self.entire_position,
            "counter": self.counter,
        }

    def to_json(self) -> CreateDecreasePositionMarketRequestParamsJSON:
        return {
            "collateral_usd_delta": self.collateral_usd_delta,
            "size_usd_delta": self.size_usd_delta,
            "price_slippage": self.price_slippage,
            "jupiter_minimum_out": self.jupiter_minimum_out,
            "entire_position": self.entire_position,
            "counter": self.counter,
        }

    @classmethod
    def from_json(
        cls, obj: CreateDecreasePositionMarketRequestParamsJSON
    ) -> "CreateDecreasePositionMarketRequestParams":
        return cls(
            collateral_usd_delta=obj["collateral_usd_delta"],
            size_usd_delta=obj["size_usd_delta"],
            price_slippage=obj["price_slippage"],
            jupiter_minimum_out=obj["jupiter_minimum_out"],
            entire_position=obj["entire_position"],
            counter=obj["counter"],
        )
