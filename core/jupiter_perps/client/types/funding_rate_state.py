from __future__ import annotations
import typing
from dataclasses import dataclass
from construct import Container
import borsh_construct as borsh


class FundingRateStateJSON(typing.TypedDict):
    cumulative_interest_rate: int
    last_update: int
    hourly_funding_dbps: int


@dataclass
class FundingRateState:
    layout: typing.ClassVar = borsh.CStruct(
        "cumulative_interest_rate" / borsh.U128,
        "last_update" / borsh.I64,
        "hourly_funding_dbps" / borsh.U64,
    )
    cumulative_interest_rate: int
    last_update: int
    hourly_funding_dbps: int

    @classmethod
    def from_decoded(cls, obj: Container) -> "FundingRateState":
        return cls(
            cumulative_interest_rate=obj.cumulative_interest_rate,
            last_update=obj.last_update,
            hourly_funding_dbps=obj.hourly_funding_dbps,
        )

    def to_encodable(self) -> dict[str, typing.Any]:
        return {
            "cumulative_interest_rate": self.cumulative_interest_rate,
            "last_update": self.last_update,
            "hourly_funding_dbps": self.hourly_funding_dbps,
        }

    def to_json(self) -> FundingRateStateJSON:
        return {
            "cumulative_interest_rate": self.cumulative_interest_rate,
            "last_update": self.last_update,
            "hourly_funding_dbps": self.hourly_funding_dbps,
        }

    @classmethod
    def from_json(cls, obj: FundingRateStateJSON) -> "FundingRateState":
        return cls(
            cumulative_interest_rate=obj["cumulative_interest_rate"],
            last_update=obj["last_update"],
            hourly_funding_dbps=obj["hourly_funding_dbps"],
        )
