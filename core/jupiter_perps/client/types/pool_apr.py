from __future__ import annotations
import typing
from dataclasses import dataclass
from construct import Container
import borsh_construct as borsh


class PoolAprJSON(typing.TypedDict):
    last_updated: int
    fee_apr_bps: int
    realized_fee_usd: int


@dataclass
class PoolApr:
    layout: typing.ClassVar = borsh.CStruct(
        "last_updated" / borsh.I64,
        "fee_apr_bps" / borsh.U64,
        "realized_fee_usd" / borsh.U64,
    )
    last_updated: int
    fee_apr_bps: int
    realized_fee_usd: int

    @classmethod
    def from_decoded(cls, obj: Container) -> "PoolApr":
        return cls(
            last_updated=obj.last_updated,
            fee_apr_bps=obj.fee_apr_bps,
            realized_fee_usd=obj.realized_fee_usd,
        )

    def to_encodable(self) -> dict[str, typing.Any]:
        return {
            "last_updated": self.last_updated,
            "fee_apr_bps": self.fee_apr_bps,
            "realized_fee_usd": self.realized_fee_usd,
        }

    def to_json(self) -> PoolAprJSON:
        return {
            "last_updated": self.last_updated,
            "fee_apr_bps": self.fee_apr_bps,
            "realized_fee_usd": self.realized_fee_usd,
        }

    @classmethod
    def from_json(cls, obj: PoolAprJSON) -> "PoolApr":
        return cls(
            last_updated=obj["last_updated"],
            fee_apr_bps=obj["fee_apr_bps"],
            realized_fee_usd=obj["realized_fee_usd"],
        )
