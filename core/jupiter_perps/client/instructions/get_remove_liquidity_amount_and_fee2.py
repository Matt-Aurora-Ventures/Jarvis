from __future__ import annotations
import typing
from solders.pubkey import Pubkey
from solders.instruction import Instruction, AccountMeta
import borsh_construct as borsh
from .. import types
from ..program_id import PROGRAM_ID


class GetRemoveLiquidityAmountAndFee2Args(typing.TypedDict):
    params: (
        types.get_remove_liquidity_amount_and_fee2_params.GetRemoveLiquidityAmountAndFee2Params
    )


layout = borsh.CStruct(
    "params"
    / types.get_remove_liquidity_amount_and_fee2_params.GetRemoveLiquidityAmountAndFee2Params.layout
)


class GetRemoveLiquidityAmountAndFee2Accounts(typing.TypedDict):
    perpetuals: Pubkey
    pool: Pubkey
    custody: Pubkey
    custody_doves_price_account: Pubkey
    custody_pythnet_price_account: Pubkey
    lp_token_mint: Pubkey


def get_remove_liquidity_amount_and_fee2(
    args: GetRemoveLiquidityAmountAndFee2Args,
    accounts: GetRemoveLiquidityAmountAndFee2Accounts,
    program_id: Pubkey = PROGRAM_ID,
    remaining_accounts: typing.Optional[typing.List[AccountMeta]] = None,
) -> Instruction:
    keys: list[AccountMeta] = [
        AccountMeta(pubkey=accounts["perpetuals"], is_signer=False, is_writable=False),
        AccountMeta(pubkey=accounts["pool"], is_signer=False, is_writable=False),
        AccountMeta(pubkey=accounts["custody"], is_signer=False, is_writable=False),
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
            pubkey=accounts["lp_token_mint"], is_signer=False, is_writable=False
        ),
    ]
    if remaining_accounts is not None:
        keys += remaining_accounts
    identifier = b"\xb7;Hn\xdf\xf3\x96\x8e"
    encoded_args = layout.build(
        {
            "params": args["params"].to_encodable(),
        }
    )
    data = identifier + encoded_args
    return Instruction(program_id, data, keys)
