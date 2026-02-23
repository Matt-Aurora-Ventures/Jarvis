from __future__ import annotations
import typing
from solders.pubkey import Pubkey
from solders.system_program import ID as SYS_PROGRAM_ID
from solders.instruction import Instruction, AccountMeta
import borsh_construct as borsh
from .. import types
from ..program_id import PROGRAM_ID


class CloseBorrowPositionArgs(typing.TypedDict):
    params: types.close_borrow_position_params.CloseBorrowPositionParams


layout = borsh.CStruct(
    "params" / types.close_borrow_position_params.CloseBorrowPositionParams.layout
)


class CloseBorrowPositionAccounts(typing.TypedDict):
    owner: Pubkey
    borrow_position: Pubkey
    event_authority: Pubkey
    program: Pubkey


def close_borrow_position(
    args: CloseBorrowPositionArgs,
    accounts: CloseBorrowPositionAccounts,
    program_id: Pubkey = PROGRAM_ID,
    remaining_accounts: typing.Optional[typing.List[AccountMeta]] = None,
) -> Instruction:
    keys: list[AccountMeta] = [
        AccountMeta(pubkey=accounts["owner"], is_signer=True, is_writable=True),
        AccountMeta(
            pubkey=accounts["borrow_position"], is_signer=False, is_writable=True
        ),
        AccountMeta(pubkey=SYS_PROGRAM_ID, is_signer=False, is_writable=False),
        AccountMeta(
            pubkey=accounts["event_authority"], is_signer=False, is_writable=False
        ),
        AccountMeta(pubkey=accounts["program"], is_signer=False, is_writable=False),
    ]
    if remaining_accounts is not None:
        keys += remaining_accounts
    identifier = b"\xcc\xe2\x91\xcd\xe8%\x03\x8c"
    encoded_args = layout.build(
        {
            "params": args["params"].to_encodable(),
        }
    )
    data = identifier + encoded_args
    return Instruction(program_id, data, keys)
