from __future__ import annotations
import typing
from dataclasses import dataclass
from construct import Container
import borsh_construct as borsh


class CreateTokenMetadataParamsJSON(typing.TypedDict):
    name: str
    symbol: str
    uri: str


@dataclass
class CreateTokenMetadataParams:
    layout: typing.ClassVar = borsh.CStruct(
        "name" / borsh.String, "symbol" / borsh.String, "uri" / borsh.String
    )
    name: str
    symbol: str
    uri: str

    @classmethod
    def from_decoded(cls, obj: Container) -> "CreateTokenMetadataParams":
        return cls(name=obj.name, symbol=obj.symbol, uri=obj.uri)

    def to_encodable(self) -> dict[str, typing.Any]:
        return {"name": self.name, "symbol": self.symbol, "uri": self.uri}

    def to_json(self) -> CreateTokenMetadataParamsJSON:
        return {"name": self.name, "symbol": self.symbol, "uri": self.uri}

    @classmethod
    def from_json(
        cls, obj: CreateTokenMetadataParamsJSON
    ) -> "CreateTokenMetadataParams":
        return cls(name=obj["name"], symbol=obj["symbol"], uri=obj["uri"])
