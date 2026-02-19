from __future__ import annotations
import typing
from dataclasses import dataclass
from construct import Container
import borsh_construct as borsh


class LimitJSON(typing.TypedDict):
    max_aum_usd: int
    token_weightage_buffer_bps: int
    buffer: int


@dataclass
class Limit:
    layout: typing.ClassVar = borsh.CStruct(
        "max_aum_usd" / borsh.U128,
        "token_weightage_buffer_bps" / borsh.U128,
        "buffer" / borsh.U64,
    )
    max_aum_usd: int
    token_weightage_buffer_bps: int
    buffer: int

    @classmethod
    def from_decoded(cls, obj: Container) -> "Limit":
        return cls(
            max_aum_usd=obj.max_aum_usd,
            token_weightage_buffer_bps=obj.token_weightage_buffer_bps,
            buffer=obj.buffer,
        )

    def to_encodable(self) -> dict[str, typing.Any]:
        return {
            "max_aum_usd": self.max_aum_usd,
            "token_weightage_buffer_bps": self.token_weightage_buffer_bps,
            "buffer": self.buffer,
        }

    def to_json(self) -> LimitJSON:
        return {
            "max_aum_usd": self.max_aum_usd,
            "token_weightage_buffer_bps": self.token_weightage_buffer_bps,
            "buffer": self.buffer,
        }

    @classmethod
    def from_json(cls, obj: LimitJSON) -> "Limit":
        return cls(
            max_aum_usd=obj["max_aum_usd"],
            token_weightage_buffer_bps=obj["token_weightage_buffer_bps"],
            buffer=obj["buffer"],
        )
