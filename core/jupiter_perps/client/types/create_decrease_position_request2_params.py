from __future__ import annotations
from . import (
    request_type,
)
import typing
from dataclasses import dataclass
from construct import Container
import borsh_construct as borsh


class CreateDecreasePositionRequest2ParamsJSON(typing.TypedDict):
    collateral_usd_delta: int
    size_usd_delta: int
    request_type: request_type.RequestTypeJSON
    price_slippage: typing.Optional[int]
    jupiter_minimum_out: typing.Optional[int]
    trigger_price: typing.Optional[int]
    trigger_above_threshold: typing.Optional[bool]
    entire_position: typing.Optional[bool]
    counter: int


@dataclass
class CreateDecreasePositionRequest2Params:
    layout: typing.ClassVar = borsh.CStruct(
        "collateral_usd_delta" / borsh.U64,
        "size_usd_delta" / borsh.U64,
        "request_type" / request_type.layout,
        "price_slippage" / borsh.Option(borsh.U64),
        "jupiter_minimum_out" / borsh.Option(borsh.U64),
        "trigger_price" / borsh.Option(borsh.U64),
        "trigger_above_threshold" / borsh.Option(borsh.Bool),
        "entire_position" / borsh.Option(borsh.Bool),
        "counter" / borsh.U64,
    )
    collateral_usd_delta: int
    size_usd_delta: int
    request_type: request_type.RequestTypeKind
    price_slippage: typing.Optional[int]
    jupiter_minimum_out: typing.Optional[int]
    trigger_price: typing.Optional[int]
    trigger_above_threshold: typing.Optional[bool]
    entire_position: typing.Optional[bool]
    counter: int

    @classmethod
    def from_decoded(cls, obj: Container) -> "CreateDecreasePositionRequest2Params":
        return cls(
            collateral_usd_delta=obj.collateral_usd_delta,
            size_usd_delta=obj.size_usd_delta,
            request_type=request_type.from_decoded(obj.request_type),
            price_slippage=obj.price_slippage,
            jupiter_minimum_out=obj.jupiter_minimum_out,
            trigger_price=obj.trigger_price,
            trigger_above_threshold=obj.trigger_above_threshold,
            entire_position=obj.entire_position,
            counter=obj.counter,
        )

    def to_encodable(self) -> dict[str, typing.Any]:
        return {
            "collateral_usd_delta": self.collateral_usd_delta,
            "size_usd_delta": self.size_usd_delta,
            "request_type": self.request_type.to_encodable(),
            "price_slippage": self.price_slippage,
            "jupiter_minimum_out": self.jupiter_minimum_out,
            "trigger_price": self.trigger_price,
            "trigger_above_threshold": self.trigger_above_threshold,
            "entire_position": self.entire_position,
            "counter": self.counter,
        }

    def to_json(self) -> CreateDecreasePositionRequest2ParamsJSON:
        return {
            "collateral_usd_delta": self.collateral_usd_delta,
            "size_usd_delta": self.size_usd_delta,
            "request_type": self.request_type.to_json(),
            "price_slippage": self.price_slippage,
            "jupiter_minimum_out": self.jupiter_minimum_out,
            "trigger_price": self.trigger_price,
            "trigger_above_threshold": self.trigger_above_threshold,
            "entire_position": self.entire_position,
            "counter": self.counter,
        }

    @classmethod
    def from_json(
        cls, obj: CreateDecreasePositionRequest2ParamsJSON
    ) -> "CreateDecreasePositionRequest2Params":
        return cls(
            collateral_usd_delta=obj["collateral_usd_delta"],
            size_usd_delta=obj["size_usd_delta"],
            request_type=request_type.from_json(obj["request_type"]),
            price_slippage=obj["price_slippage"],
            jupiter_minimum_out=obj["jupiter_minimum_out"],
            trigger_price=obj["trigger_price"],
            trigger_above_threshold=obj["trigger_above_threshold"],
            entire_position=obj["entire_position"],
            counter=obj["counter"],
        )
