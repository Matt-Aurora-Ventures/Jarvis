from __future__ import annotations
from . import (
    oracle_type,
)
import typing
from dataclasses import dataclass
from construct import Container
from solders.pubkey import Pubkey
from anchorpy.borsh_extension import BorshPubkey
import borsh_construct as borsh


class OracleParamsJSON(typing.TypedDict):
    oracle_account: str
    oracle_type: oracle_type.OracleTypeJSON
    buffer: int
    max_price_age_sec: int


@dataclass
class OracleParams:
    layout: typing.ClassVar = borsh.CStruct(
        "oracle_account" / BorshPubkey,
        "oracle_type" / oracle_type.layout,
        "buffer" / borsh.U64,
        "max_price_age_sec" / borsh.U32,
    )
    oracle_account: Pubkey
    oracle_type: oracle_type.OracleTypeKind
    buffer: int
    max_price_age_sec: int

    @classmethod
    def from_decoded(cls, obj: Container) -> "OracleParams":
        return cls(
            oracle_account=obj.oracle_account,
            oracle_type=oracle_type.from_decoded(obj.oracle_type),
            buffer=obj.buffer,
            max_price_age_sec=obj.max_price_age_sec,
        )

    def to_encodable(self) -> dict[str, typing.Any]:
        return {
            "oracle_account": self.oracle_account,
            "oracle_type": self.oracle_type.to_encodable(),
            "buffer": self.buffer,
            "max_price_age_sec": self.max_price_age_sec,
        }

    def to_json(self) -> OracleParamsJSON:
        return {
            "oracle_account": str(self.oracle_account),
            "oracle_type": self.oracle_type.to_json(),
            "buffer": self.buffer,
            "max_price_age_sec": self.max_price_age_sec,
        }

    @classmethod
    def from_json(cls, obj: OracleParamsJSON) -> "OracleParams":
        return cls(
            oracle_account=Pubkey.from_string(obj["oracle_account"]),
            oracle_type=oracle_type.from_json(obj["oracle_type"]),
            buffer=obj["buffer"],
            max_price_age_sec=obj["max_price_age_sec"],
        )
