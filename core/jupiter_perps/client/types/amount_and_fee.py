from __future__ import annotations
import typing
from dataclasses import dataclass
from construct import Container
import borsh_construct as borsh


class AmountAndFeeJSON(typing.TypedDict):
    amount: int
    fee: int
    fee_bps: int


@dataclass
class AmountAndFee:
    layout: typing.ClassVar = borsh.CStruct(
        "amount" / borsh.U64, "fee" / borsh.U64, "fee_bps" / borsh.U64
    )
    amount: int
    fee: int
    fee_bps: int

    @classmethod
    def from_decoded(cls, obj: Container) -> "AmountAndFee":
        return cls(amount=obj.amount, fee=obj.fee, fee_bps=obj.fee_bps)

    def to_encodable(self) -> dict[str, typing.Any]:
        return {"amount": self.amount, "fee": self.fee, "fee_bps": self.fee_bps}

    def to_json(self) -> AmountAndFeeJSON:
        return {"amount": self.amount, "fee": self.fee, "fee_bps": self.fee_bps}

    @classmethod
    def from_json(cls, obj: AmountAndFeeJSON) -> "AmountAndFee":
        return cls(amount=obj["amount"], fee=obj["fee"], fee_bps=obj["fee_bps"])
