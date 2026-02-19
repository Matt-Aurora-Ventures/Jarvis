from __future__ import annotations
from . import (
    fees,
    limit,
)
import typing
from dataclasses import dataclass
from construct import Container
import borsh_construct as borsh


class AddPoolParamsJSON(typing.TypedDict):
    name: str
    limit: limit.LimitJSON
    fees: fees.FeesJSON
    max_request_execution_sec: int


@dataclass
class AddPoolParams:
    layout: typing.ClassVar = borsh.CStruct(
        "name" / borsh.String,
        "limit" / limit.Limit.layout,
        "fees" / fees.Fees.layout,
        "max_request_execution_sec" / borsh.I64,
    )
    name: str
    limit: limit.Limit
    fees: fees.Fees
    max_request_execution_sec: int

    @classmethod
    def from_decoded(cls, obj: Container) -> "AddPoolParams":
        return cls(
            name=obj.name,
            limit=limit.Limit.from_decoded(obj.limit),
            fees=fees.Fees.from_decoded(obj.fees),
            max_request_execution_sec=obj.max_request_execution_sec,
        )

    def to_encodable(self) -> dict[str, typing.Any]:
        return {
            "name": self.name,
            "limit": self.limit.to_encodable(),
            "fees": self.fees.to_encodable(),
            "max_request_execution_sec": self.max_request_execution_sec,
        }

    def to_json(self) -> AddPoolParamsJSON:
        return {
            "name": self.name,
            "limit": self.limit.to_json(),
            "fees": self.fees.to_json(),
            "max_request_execution_sec": self.max_request_execution_sec,
        }

    @classmethod
    def from_json(cls, obj: AddPoolParamsJSON) -> "AddPoolParams":
        return cls(
            name=obj["name"],
            limit=limit.Limit.from_json(obj["limit"]),
            fees=fees.Fees.from_json(obj["fees"]),
            max_request_execution_sec=obj["max_request_execution_sec"],
        )
