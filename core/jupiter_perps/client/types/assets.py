from __future__ import annotations
import typing
from dataclasses import dataclass
from construct import Container
import borsh_construct as borsh


class AssetsJSON(typing.TypedDict):
    fees_reserves: int
    owned: int
    locked: int
    guaranteed_usd: int
    global_short_sizes: int
    global_short_average_prices: int


@dataclass
class Assets:
    layout: typing.ClassVar = borsh.CStruct(
        "fees_reserves" / borsh.U64,
        "owned" / borsh.U64,
        "locked" / borsh.U64,
        "guaranteed_usd" / borsh.U64,
        "global_short_sizes" / borsh.U64,
        "global_short_average_prices" / borsh.U64,
    )
    fees_reserves: int
    owned: int
    locked: int
    guaranteed_usd: int
    global_short_sizes: int
    global_short_average_prices: int

    @classmethod
    def from_decoded(cls, obj: Container) -> "Assets":
        return cls(
            fees_reserves=obj.fees_reserves,
            owned=obj.owned,
            locked=obj.locked,
            guaranteed_usd=obj.guaranteed_usd,
            global_short_sizes=obj.global_short_sizes,
            global_short_average_prices=obj.global_short_average_prices,
        )

    def to_encodable(self) -> dict[str, typing.Any]:
        return {
            "fees_reserves": self.fees_reserves,
            "owned": self.owned,
            "locked": self.locked,
            "guaranteed_usd": self.guaranteed_usd,
            "global_short_sizes": self.global_short_sizes,
            "global_short_average_prices": self.global_short_average_prices,
        }

    def to_json(self) -> AssetsJSON:
        return {
            "fees_reserves": self.fees_reserves,
            "owned": self.owned,
            "locked": self.locked,
            "guaranteed_usd": self.guaranteed_usd,
            "global_short_sizes": self.global_short_sizes,
            "global_short_average_prices": self.global_short_average_prices,
        }

    @classmethod
    def from_json(cls, obj: AssetsJSON) -> "Assets":
        return cls(
            fees_reserves=obj["fees_reserves"],
            owned=obj["owned"],
            locked=obj["locked"],
            guaranteed_usd=obj["guaranteed_usd"],
            global_short_sizes=obj["global_short_sizes"],
            global_short_average_prices=obj["global_short_average_prices"],
        )
