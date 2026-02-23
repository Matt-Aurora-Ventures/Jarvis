from __future__ import annotations
import typing
from solders.pubkey import Pubkey
from spl.token.constants import TOKEN_PROGRAM_ID
from solders.instruction import Instruction, AccountMeta
import borsh_construct as borsh
from .. import types
from ..program_id import PROGRAM_ID


class RemoveLiquidity2Args(typing.TypedDict):
    params: types.remove_liquidity2_params.RemoveLiquidity2Params


layout = borsh.CStruct(
    "params" / types.remove_liquidity2_params.RemoveLiquidity2Params.layout
)


class RemoveLiquidity2Accounts(typing.TypedDict):
    owner: Pubkey
    receiving_account: Pubkey
    lp_token_account: Pubkey
    transfer_authority: Pubkey
    perpetuals: Pubkey
    pool: Pubkey
    custody: Pubkey
    custody_doves_price_account: Pubkey
    custody_pythnet_price_account: Pubkey
    custody_token_account: Pubkey
    lp_token_mint: Pubkey
    event_authority: Pubkey
    program: Pubkey


def remove_liquidity2(
    args: RemoveLiquidity2Args,
    accounts: RemoveLiquidity2Accounts,
    program_id: Pubkey = PROGRAM_ID,
    remaining_accounts: typing.Optional[typing.List[AccountMeta]] = None,
) -> Instruction:
    keys: list[AccountMeta] = [
        AccountMeta(pubkey=accounts["owner"], is_signer=True, is_writable=False),
        AccountMeta(
            pubkey=accounts["receiving_account"], is_signer=False, is_writable=True
        ),
        AccountMeta(
            pubkey=accounts["lp_token_account"], is_signer=False, is_writable=True
        ),
        AccountMeta(
            pubkey=accounts["transfer_authority"], is_signer=False, is_writable=False
        ),
        AccountMeta(pubkey=accounts["perpetuals"], is_signer=False, is_writable=False),
        AccountMeta(pubkey=accounts["pool"], is_signer=False, is_writable=True),
        AccountMeta(pubkey=accounts["custody"], is_signer=False, is_writable=True),
        AccountMeta(
            pubkey=accounts["custody_doves_price_account"],
            is_signer=False,
            is_writable=False,
        ),
        AccountMeta(
            pubkey=accounts["custody_pythnet_price_account"],
            is_signer=False,
            is_writable=False,
        ),
        AccountMeta(
            pubkey=accounts["custody_token_account"], is_signer=False, is_writable=True
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
    identifier = b"\xe6\xd7R\x7f\xf1e\xe3\x92"
    encoded_args = layout.build(
        {
            "params": args["params"].to_encodable(),
        }
    )
    data = identifier + encoded_args
    return Instruction(program_id, data, keys)
