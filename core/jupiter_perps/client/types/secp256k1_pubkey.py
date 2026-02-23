from __future__ import annotations
import typing
from dataclasses import dataclass
from construct import Container
import borsh_construct as borsh


class Secp256k1PubkeyJSON(typing.TypedDict):
    prefix: int
    key: list[int]


@dataclass
class Secp256k1Pubkey:
    layout: typing.ClassVar = borsh.CStruct("prefix" / borsh.U8, "key" / borsh.U8[32])
    prefix: int
    key: list[int]

    @classmethod
    def from_decoded(cls, obj: Container) -> "Secp256k1Pubkey":
        return cls(prefix=obj.prefix, key=obj.key)

    def to_encodable(self) -> dict[str, typing.Any]:
        return {"prefix": self.prefix, "key": self.key}

    def to_json(self) -> Secp256k1PubkeyJSON:
        return {"prefix": self.prefix, "key": self.key}

    @classmethod
    def from_json(cls, obj: Secp256k1PubkeyJSON) -> "Secp256k1Pubkey":
        return cls(prefix=obj["prefix"], key=obj["key"])
