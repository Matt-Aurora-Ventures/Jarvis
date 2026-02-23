from __future__ import annotations
import typing
from solders.pubkey import Pubkey
from spl.token.constants import TOKEN_PROGRAM_ID
from solders.instruction import Instruction, AccountMeta
import borsh_construct as borsh
from .. import types
from ..program_id import PROGRAM_ID


class BorrowFromCustodyArgs(typing.TypedDict):
    params: types.borrow_from_custody_params.BorrowFromCustodyParams


layout = borsh.CStruct(
    "params" / types.borrow_from_custody_params.BorrowFromCustodyParams.layout
)


class BorrowFromCustodyAccounts(typing.TypedDict):
    owner: Pubkey
    perpetuals: Pubkey
    pool: Pubkey
    custody: Pubkey
    transfer_authority: Pubkey
    borrow_position: Pubkey
    custody_token_account: Pubkey
    user_token_account: Pubkey
    lp_token_mint: Pubkey
    event_authority: Pubkey
    program: Pubkey


def borrow_from_custody(
    args: BorrowFromCustodyArgs,
    accounts: BorrowFromCustodyAccounts,
    program_id: Pubkey = PROGRAM_ID,
    remaining_accounts: typing.Optional[typing.List[AccountMeta]] = None,
) -> Instruction:
    keys: list[AccountMeta] = [
        AccountMeta(pubkey=accounts["owner"], is_signer=True, is_writable=True),
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
            pubkey=accounts["custody_token_account"], is_signer=False, is_writable=True
        ),
        AccountMeta(
            pubkey=accounts["user_token_account"], is_signer=False, is_writable=True
        ),
        AccountMeta(
            pubkey=accounts["lp_token_mint"], is_signer=False, is_writable=False
        ),
        AccountMeta(pubkey=TOKEN_PROGRAM_ID, is_signer=False, is_writable=False),
        AccountMeta(
            pubkey=accounts["event_authority"], is_signer=False, is_writable=False
        ),
        AccountMeta(pubkey=accounts["program"], is_signer=False, is_writable=False),
    ]
    if remaining_accounts is not None:
        keys += remaining_accounts
    identifier = b"\x99\xb7AAq!\xf9-"
    encoded_args = layout.build(
        {
            "params": args["params"].to_encodable(),
        }
    )
    data = identifier + encoded_args
    return Instruction(program_id, data, keys)
