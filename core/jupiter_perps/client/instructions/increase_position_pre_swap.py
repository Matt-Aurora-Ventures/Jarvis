from __future__ import annotations
import typing
from solders.pubkey import Pubkey
from spl.token.constants import TOKEN_PROGRAM_ID
from solders.instruction import Instruction, AccountMeta
import borsh_construct as borsh
from .. import types
from ..program_id import PROGRAM_ID


class IncreasePositionPreSwapArgs(typing.TypedDict):
    params: types.increase_position_pre_swap_params.IncreasePositionPreSwapParams


layout = borsh.CStruct(
    "params"
    / types.increase_position_pre_swap_params.IncreasePositionPreSwapParams.layout
)


class IncreasePositionPreSwapAccounts(typing.TypedDict):
    keeper: Pubkey
    keeper_ata: Pubkey
    position_request: Pubkey
    position_request_ata: Pubkey
    position: Pubkey
    collateral_custody: Pubkey
    collateral_custody_token_account: Pubkey
    instruction: Pubkey
    event_authority: Pubkey
    program: Pubkey


def increase_position_pre_swap(
    args: IncreasePositionPreSwapArgs,
    accounts: IncreasePositionPreSwapAccounts,
    program_id: Pubkey = PROGRAM_ID,
    remaining_accounts: typing.Optional[typing.List[AccountMeta]] = None,
) -> Instruction:
    keys: list[AccountMeta] = [
        AccountMeta(pubkey=accounts["keeper"], is_signer=True, is_writable=False),
        AccountMeta(pubkey=accounts["keeper_ata"], is_signer=False, is_writable=True),
        AccountMeta(
            pubkey=accounts["position_request"], is_signer=False, is_writable=True
        ),
        AccountMeta(
            pubkey=accounts["position_request_ata"], is_signer=False, is_writable=True
        ),
        AccountMeta(pubkey=accounts["position"], is_signer=False, is_writable=False),
        AccountMeta(
            pubkey=accounts["collateral_custody"], is_signer=False, is_writable=False
        ),
        AccountMeta(
            pubkey=accounts["collateral_custody_token_account"],
            is_signer=False,
            is_writable=False,
        ),
        AccountMeta(pubkey=accounts["instruction"], is_signer=False, is_writable=False),
        AccountMeta(pubkey=TOKEN_PROGRAM_ID, is_signer=False, is_writable=False),
        AccountMeta(
            pubkey=accounts["event_authority"], is_signer=False, is_writable=False
        ),
        AccountMeta(pubkey=accounts["program"], is_signer=False, is_writable=False),
    ]
    if remaining_accounts is not None:
        keys += remaining_accounts
    identifier = b"\x1a\x88\xe1\xd9\x16\x15S\x14"
    encoded_args = layout.build(
        {
            "params": args["params"].to_encodable(),
        }
    )
    data = identifier + encoded_args
    return Instruction(program_id, data, keys)
