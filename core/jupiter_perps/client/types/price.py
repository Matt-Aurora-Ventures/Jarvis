from __future__ import annotations
import typing
from dataclasses import dataclass
from construct import Container
import borsh_construct as borsh


class PriceJSON(typing.TypedDict):
    price: int
    expo: int
    publish_time: int


@dataclass
class Price:
    layout: typing.ClassVar = borsh.CStruct(
        "price" / borsh.U64, "expo" / borsh.I32, "publish_time" / borsh.I64
    )
    price: int
    expo: int
    publish_time: int

    @classmethod
    def from_decoded(cls, obj: Container) -> "Price":
        return cls(price=obj.price, expo=obj.expo, publish_time=obj.publish_time)

    def to_encodable(self) -> dict[str, typing.Any]:
        return {
            "price": self.price,
            "expo": self.expo,
            "publish_time": self.publish_time,
        }

    def to_json(self) -> PriceJSON:
        return {
            "price": self.price,
            "expo": self.expo,
            "publish_time": self.publish_time,
        }

    @classmethod
    def from_json(cls, obj: PriceJSON) -> "Price":
        return cls(
            price=obj["price"], expo=obj["expo"], publish_time=obj["publish_time"]
        )
