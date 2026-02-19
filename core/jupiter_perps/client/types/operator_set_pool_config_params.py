from __future__ import annotations
from . import (
    fees,
    limit,
)
import typing
from dataclasses import dataclass
from construct import Container
import borsh_construct as borsh


class OperatorSetPoolConfigParamsJSON(typing.TypedDict):
    fees: fees.FeesJSON
    limit: limit.LimitJSON
    max_request_execution_sec: int


@dataclass
class OperatorSetPoolConfigParams:
    layout: typing.ClassVar = borsh.CStruct(
        "fees" / fees.Fees.layout,
        "limit" / limit.Limit.layout,
        "max_request_execution_sec" / borsh.I64,
    )
    fees: fees.Fees
    limit: limit.Limit
    max_request_execution_sec: int

    @classmethod
    def from_decoded(cls, obj: Container) -> "OperatorSetPoolConfigParams":
        return cls(
            fees=fees.Fees.from_decoded(obj.fees),
            limit=limit.Limit.from_decoded(obj.limit),
            max_request_execution_sec=obj.max_request_execution_sec,
        )

    def to_encodable(self) -> dict[str, typing.Any]:
        return {
            "fees": self.fees.to_encodable(),
            "limit": self.limit.to_encodable(),
            "max_request_execution_sec": self.max_request_execution_sec,
        }

    def to_json(self) -> OperatorSetPoolConfigParamsJSON:
        return {
            "fees": self.fees.to_json(),
            "limit": self.limit.to_json(),
            "max_request_execution_sec": self.max_request_execution_sec,
        }

    @classmethod
    def from_json(
        cls, obj: OperatorSetPoolConfigParamsJSON
    ) -> "OperatorSetPoolConfigParams":
        return cls(
            fees=fees.Fees.from_json(obj["fees"]),
            limit=limit.Limit.from_json(obj["limit"]),
            max_request_execution_sec=obj["max_request_execution_sec"],
        )
