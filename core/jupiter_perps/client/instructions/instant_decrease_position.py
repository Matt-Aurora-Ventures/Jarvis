from __future__ import annotations
import typing
from solders.pubkey import Pubkey
from solders.system_program import ID as SYS_PROGRAM_ID
from spl.token.constants import TOKEN_PROGRAM_ID, ASSOCIATED_TOKEN_PROGRAM_ID
from solders.instruction import Instruction, AccountMeta
import borsh_construct as borsh
from .. import types
from ..program_id import PROGRAM_ID


class InstantDecreasePositionArgs(typing.TypedDict):
    params: types.instant_decrease_position_params.InstantDecreasePositionParams


layout = borsh.CStruct(
    "params"
    / types.instant_decrease_position_params.InstantDecreasePositionParams.layout
)


class InstantDecreasePositionAccounts(typing.TypedDict):
    keeper: Pubkey
    api_keeper: Pubkey
    owner: Pubkey
    receiving_account: Pubkey
    transfer_authority: Pubkey
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
    desired_mint: Pubkey
    referral: typing.Optional[Pubkey]
    event_authority: Pubkey
    program: Pubkey


def instant_decrease_position(
    args: InstantDecreasePositionArgs,
    accounts: InstantDecreasePositionAccounts,
    program_id: Pubkey = PROGRAM_ID,
    remaining_accounts: typing.Optional[typing.List[AccountMeta]] = None,
) -> Instruction:
    keys: list[AccountMeta] = [
        AccountMeta(pubkey=accounts["keeper"], is_signer=True, is_writable=False),
        AccountMeta(pubkey=accounts["api_keeper"], is_signer=True, is_writable=False),
        AccountMeta(pubkey=accounts["owner"], is_signer=True, is_writable=True),
        AccountMeta(
            pubkey=accounts["receiving_account"], is_signer=False, is_writable=True
        ),
        AccountMeta(
            pubkey=accounts["transfer_authority"], is_signer=False, is_writable=False
        ),
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
            pubkey=accounts["desired_mint"], is_signer=False, is_writable=False
        ),
        (
            AccountMeta(pubkey=accounts["referral"], is_signer=False, is_writable=False)
            if accounts["referral"]
            else AccountMeta(pubkey=program_id, is_signer=False, is_writable=False)
        ),
        AccountMeta(pubkey=TOKEN_PROGRAM_ID, is_signer=False, is_writable=False),
        AccountMeta(
            pubkey=ASSOCIATED_TOKEN_PROGRAM_ID, is_signer=False, is_writable=False
        ),
        AccountMeta(pubkey=SYS_PROGRAM_ID, is_signer=False, is_writable=False),
        AccountMeta(
            pubkey=accounts["event_authority"], is_signer=False, is_writable=False
        ),
        AccountMeta(pubkey=accounts["program"], is_signer=False, is_writable=False),
    ]
    if remaining_accounts is not None:
        keys += remaining_accounts
    identifier = b".\x17\xf0,\x1e\x8a^\x8c"
    encoded_args = layout.build(
        {
            "params": args["params"].to_encodable(),
        }
    )
    data = identifier + encoded_args
    return Instruction(program_id, data, keys)
