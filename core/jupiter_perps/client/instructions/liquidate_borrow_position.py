from __future__ import annotations
import typing
from solders.pubkey import Pubkey
from spl.token.constants import TOKEN_PROGRAM_ID
from solders.instruction import Instruction, AccountMeta
import borsh_construct as borsh
from .. import types
from ..program_id import PROGRAM_ID


class LiquidateBorrowPositionArgs(typing.TypedDict):
    params: types.liquidate_borrow_position_params.LiquidateBorrowPositionParams


layout = borsh.CStruct(
    "params"
    / types.liquidate_borrow_position_params.LiquidateBorrowPositionParams.layout
)


class LiquidateBorrowPositionAccounts(typing.TypedDict):
    signer: Pubkey
    perpetuals: Pubkey
    pool: Pubkey
    custody: Pubkey
    transfer_authority: Pubkey
    borrow_position: Pubkey
    collateral_token_account: Pubkey
    lp_token_mint: Pubkey
    event_authority: Pubkey
    program: Pubkey


def liquidate_borrow_position(
    args: LiquidateBorrowPositionArgs,
    accounts: LiquidateBorrowPositionAccounts,
    program_id: Pubkey = PROGRAM_ID,
    remaining_accounts: typing.Optional[typing.List[AccountMeta]] = None,
) -> Instruction:
    keys: list[AccountMeta] = [
        AccountMeta(pubkey=accounts["signer"], is_signer=True, is_writable=False),
        AccountMeta(pubkey=accounts["perpetuals"], is_signer=False, is_writable=False),
        AccountMeta(pubkey=accounts["pool"], is_signer=False, is_writable=False),
        AccountMeta(pubkey=accounts["custody"], is_signer=False, is_writable=True),
        AccountMeta(
            pubkey=accounts["transfer_authority"], is_signer=False, is_writable=False
        ),
        AccountMeta(
            pubkey=accounts["borrow_position"], is_signer=False, is_writable=True
        ),
        AccountMeta(
            pubkey=accounts["collateral_token_account"],
            is_signer=False,
            is_writable=True,
        ),
        AccountMeta(
            pubkey=accounts["lp_token_mint"], is_signer=False, is_writable=True
        ),
        AccountMeta(pubkey=TOKEN_PROGRAM_ID, is_signer=False, is_writable=False),
        AccountMeta(
            pubkey=accounts["event_authority"], is_signer=False, is_writable=False
        ),
        AccountMeta(pubkey=accounts["program"], is_signer=False, is_writable=False),
    ]
    if remaining_accounts is not None:
        keys += remaining_accounts
    identifier = b"\xeb\xc9\x11\x85\xeaHT\xd2"
    encoded_args = layout.build(
        {
            "params": args["params"].to_encodable(),
        }
    )
    data = identifier + encoded_args
    return Instruction(program_id, data, keys)
