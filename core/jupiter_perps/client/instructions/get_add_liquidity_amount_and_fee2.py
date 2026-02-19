from __future__ import annotations
import typing
from solders.pubkey import Pubkey
from solders.instruction import Instruction, AccountMeta
import borsh_construct as borsh
from .. import types
from ..program_id import PROGRAM_ID


class GetAddLiquidityAmountAndFee2Args(typing.TypedDict):
    params: (
        types.get_add_liquidity_amount_and_fee2_params.GetAddLiquidityAmountAndFee2Params
    )


layout = borsh.CStruct(
    "params"
    / types.get_add_liquidity_amount_and_fee2_params.GetAddLiquidityAmountAndFee2Params.layout
)


class GetAddLiquidityAmountAndFee2Accounts(typing.TypedDict):
    perpetuals: Pubkey
    pool: Pubkey
    custody: Pubkey
    custody_doves_price_account: Pubkey
    custody_pythnet_price_account: Pubkey
    lp_token_mint: Pubkey


def get_add_liquidity_amount_and_fee2(
    args: GetAddLiquidityAmountAndFee2Args,
    accounts: GetAddLiquidityAmountAndFee2Accounts,
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
    identifier = b"m\x9d7\xa9\x08Q\x04v"
    encoded_args = layout.build(
        {
            "params": args["params"].to_encodable(),
        }
    )
    data = identifier + encoded_args
    return Instruction(program_id, data, keys)
