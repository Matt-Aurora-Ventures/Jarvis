from __future__ import annotations
import typing
from dataclasses import dataclass
from construct import Container
import borsh_construct as borsh


class BorrowLendParamsJSON(typing.TypedDict):
    borrows_limit_in_bps: int
    maintainance_margin_bps: int
    protocol_fee_bps: int
    liquidation_margin: int
    liquidation_fee_bps: int


@dataclass
class BorrowLendParams:
    layout: typing.ClassVar = borsh.CStruct(
        "borrows_limit_in_bps" / borsh.U64,
        "maintainance_margin_bps" / borsh.U64,
        "protocol_fee_bps" / borsh.U64,
        "liquidation_margin" / borsh.U64,
        "liquidation_fee_bps" / borsh.U64,
    )
    borrows_limit_in_bps: int
    maintainance_margin_bps: int
    protocol_fee_bps: int
    liquidation_margin: int
    liquidation_fee_bps: int

    @classmethod
    def from_decoded(cls, obj: Container) -> "BorrowLendParams":
        return cls(
            borrows_limit_in_bps=obj.borrows_limit_in_bps,
            maintainance_margin_bps=obj.maintainance_margin_bps,
            protocol_fee_bps=obj.protocol_fee_bps,
            liquidation_margin=obj.liquidation_margin,
            liquidation_fee_bps=obj.liquidation_fee_bps,
        )

    def to_encodable(self) -> dict[str, typing.Any]:
        return {
            "borrows_limit_in_bps": self.borrows_limit_in_bps,
            "maintainance_margin_bps": self.maintainance_margin_bps,
            "protocol_fee_bps": self.protocol_fee_bps,
            "liquidation_margin": self.liquidation_margin,
            "liquidation_fee_bps": self.liquidation_fee_bps,
        }

    def to_json(self) -> BorrowLendParamsJSON:
        return {
            "borrows_limit_in_bps": self.borrows_limit_in_bps,
            "maintainance_margin_bps": self.maintainance_margin_bps,
            "protocol_fee_bps": self.protocol_fee_bps,
            "liquidation_margin": self.liquidation_margin,
            "liquidation_fee_bps": self.liquidation_fee_bps,
        }

    @classmethod
    def from_json(cls, obj: BorrowLendParamsJSON) -> "BorrowLendParams":
        return cls(
            borrows_limit_in_bps=obj["borrows_limit_in_bps"],
            maintainance_margin_bps=obj["maintainance_margin_bps"],
            protocol_fee_bps=obj["protocol_fee_bps"],
            liquidation_margin=obj["liquidation_margin"],
            liquidation_fee_bps=obj["liquidation_fee_bps"],
        )
