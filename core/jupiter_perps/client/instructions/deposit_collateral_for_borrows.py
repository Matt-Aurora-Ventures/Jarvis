from __future__ import annotations
import typing
from solders.pubkey import Pubkey
from solders.system_program import ID as SYS_PROGRAM_ID
from spl.token.constants import TOKEN_PROGRAM_ID
from solders.instruction import Instruction, AccountMeta
import borsh_construct as borsh
from .. import types
from ..program_id import PROGRAM_ID


class DepositCollateralForBorrowsArgs(typing.TypedDict):
    params: types.deposit_params.DepositParams


layout = borsh.CStruct("params" / types.deposit_params.DepositParams.layout)


class DepositCollateralForBorrowsAccounts(typing.TypedDict):
    owner: Pubkey
    perpetuals: Pubkey
    pool: Pubkey
    custody: Pubkey
    transfer_authority: Pubkey
    borrow_position: Pubkey
    collateral_token_account: Pubkey
    user_token_account: Pubkey
    lp_token_mint: Pubkey
    event_authority: Pubkey
    program: Pubkey


def deposit_collateral_for_borrows(
    args: DepositCollateralForBorrowsArgs,
    accounts: DepositCollateralForBorrowsAccounts,
    program_id: Pubkey = PROGRAM_ID,
    remaining_accounts: typing.Optional[typing.List[AccountMeta]] = None,
) -> Instruction:
    keys: list[AccountMeta] = [
        AccountMeta(pubkey=accounts["owner"], is_signer=True, is_writable=True),
        AccountMeta(pubkey=accounts["perpetuals"], is_signer=False, is_writable=False),
        AccountMeta(pubkey=accounts["pool"], is_signer=False, is_writable=False),
        AccountMeta(pubkey=accounts["custody"], is_signer=False, is_writable=False),
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
            pubkey=accounts["user_token_account"], is_signer=False, is_writable=True
        ),
        AccountMeta(
            pubkey=accounts["lp_token_mint"], is_signer=False, is_writable=False
        ),
        AccountMeta(pubkey=TOKEN_PROGRAM_ID, is_signer=False, is_writable=False),
        AccountMeta(pubkey=SYS_PROGRAM_ID, is_signer=False, is_writable=False),
        AccountMeta(
            pubkey=accounts["event_authority"], is_signer=False, is_writable=False
        ),
        AccountMeta(pubkey=accounts["program"], is_signer=False, is_writable=False),
    ]
    if remaining_accounts is not None:
        keys += remaining_accounts
    identifier = b"\x11\x02\xc3\xbeL\x10\xeeJ"
    encoded_args = layout.build(
        {
            "params": args["params"].to_encodable(),
        }
    )
    data = identifier + encoded_args
    return Instruction(program_id, data, keys)
