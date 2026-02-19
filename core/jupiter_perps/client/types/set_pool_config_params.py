from __future__ import annotations
from . import (
    fees,
    limit,
    secp256k1_pubkey,
)
import typing
from dataclasses import dataclass
from construct import Container
import borsh_construct as borsh


class SetPoolConfigParamsJSON(typing.TypedDict):
    fees: fees.FeesJSON
    limit: limit.LimitJSON
    max_request_execution_sec: int
    parameter_update_oracle: secp256k1_pubkey.Secp256k1PubkeyJSON


@dataclass
class SetPoolConfigParams:
    layout: typing.ClassVar = borsh.CStruct(
        "fees" / fees.Fees.layout,
        "limit" / limit.Limit.layout,
        "max_request_execution_sec" / borsh.I64,
        "parameter_update_oracle" / secp256k1_pubkey.Secp256k1Pubkey.layout,
    )
    fees: fees.Fees
    limit: limit.Limit
    max_request_execution_sec: int
    parameter_update_oracle: secp256k1_pubkey.Secp256k1Pubkey

    @classmethod
    def from_decoded(cls, obj: Container) -> "SetPoolConfigParams":
        return cls(
            fees=fees.Fees.from_decoded(obj.fees),
            limit=limit.Limit.from_decoded(obj.limit),
            max_request_execution_sec=obj.max_request_execution_sec,
            parameter_update_oracle=secp256k1_pubkey.Secp256k1Pubkey.from_decoded(
                obj.parameter_update_oracle
            ),
        )

    def to_encodable(self) -> dict[str, typing.Any]:
        return {
            "fees": self.fees.to_encodable(),
            "limit": self.limit.to_encodable(),
            "max_request_execution_sec": self.max_request_execution_sec,
            "parameter_update_oracle": self.parameter_update_oracle.to_encodable(),
        }

    def to_json(self) -> SetPoolConfigParamsJSON:
        return {
            "fees": self.fees.to_json(),
            "limit": self.limit.to_json(),
            "max_request_execution_sec": self.max_request_execution_sec,
            "parameter_update_oracle": self.parameter_update_oracle.to_json(),
        }

    @classmethod
    def from_json(cls, obj: SetPoolConfigParamsJSON) -> "SetPoolConfigParams":
        return cls(
            fees=fees.Fees.from_json(obj["fees"]),
            limit=limit.Limit.from_json(obj["limit"]),
            max_request_execution_sec=obj["max_request_execution_sec"],
            parameter_update_oracle=secp256k1_pubkey.Secp256k1Pubkey.from_json(
                obj["parameter_update_oracle"]
            ),
        )
