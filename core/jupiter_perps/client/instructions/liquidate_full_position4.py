from __future__ import annotations
import typing
from solders.pubkey import Pubkey
from solders.instruction import Instruction, AccountMeta
import borsh_construct as borsh
from .. import types
from ..program_id import PROGRAM_ID


class LiquidateFullPosition4Args(typing.TypedDict):
    params: types.liquidate_full_position4_params.LiquidateFullPosition4Params


layout = borsh.CStruct(
    "params" / types.liquidate_full_position4_params.LiquidateFullPosition4Params.layout
)


class LiquidateFullPosition4Accounts(typing.TypedDict):
    signer: Pubkey
    perpetuals: Pubkey
    pool: Pubkey
    position: Pubkey
    custody: Pubkey
    custody_doves_price_account: Pubkey
    custody_pythnet_price_account: Pubkey
    collateral_custody: Pubkey
    collateral_custody_doves_price_account: Pubkey
    collateral_custody_pythnet_price_account: Pubkey
    collateral_custody_token_account: Pubkey
    event_authority: Pubkey
    program: Pubkey


def liquidate_full_position4(
    args: LiquidateFullPosition4Args,
    accounts: LiquidateFullPosition4Accounts,
    program_id: Pubkey = PROGRAM_ID,
    remaining_accounts: typing.Optional[typing.List[AccountMeta]] = None,
) -> Instruction:
    keys: list[AccountMeta] = [
        AccountMeta(pubkey=accounts["signer"], is_signer=True, is_writable=False),
        AccountMeta(pubkey=accounts["perpetuals"], is_signer=False, is_writable=False),
        AccountMeta(pubkey=accounts["pool"], is_signer=False, is_writable=True),
        AccountMeta(pubkey=accounts["position"], is_signer=False, is_writable=True),
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
            pubkey=accounts["collateral_custody"], is_signer=False, is_writable=True
        ),
        AccountMeta(
            pubkey=accounts["collateral_custody_doves_price_account"],
            is_signer=False,
            is_writable=False,
        ),
        AccountMeta(
            pubkey=accounts["collateral_custody_pythnet_price_account"],
            is_signer=False,
            is_writable=False,
        ),
        AccountMeta(
            pubkey=accounts["collateral_custody_token_account"],
            is_signer=False,
            is_writable=True,
        ),
        AccountMeta(
            pubkey=accounts["event_authority"], is_signer=False, is_writable=False
        ),
        AccountMeta(pubkey=accounts["program"], is_signer=False, is_writable=False),
    ]
    if remaining_accounts is not None:
        keys += remaining_accounts
    identifier = b"@\xb0X3\xa8\xbc\x9c\xaf"
    encoded_args = layout.build(
        {
            "params": args["params"].to_encodable(),
        }
    )
    data = identifier + encoded_args
    return Instruction(program_id, data, keys)
