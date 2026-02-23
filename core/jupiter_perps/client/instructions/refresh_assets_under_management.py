from __future__ import annotations
import typing
from solders.pubkey import Pubkey
from solders.instruction import Instruction, AccountMeta
import borsh_construct as borsh
from .. import types
from ..program_id import PROGRAM_ID


class RefreshAssetsUnderManagementArgs(typing.TypedDict):
    params: (
        types.refresh_assets_under_management_params.RefreshAssetsUnderManagementParams
    )


layout = borsh.CStruct(
    "params"
    / types.refresh_assets_under_management_params.RefreshAssetsUnderManagementParams.layout
)


class RefreshAssetsUnderManagementAccounts(typing.TypedDict):
    keeper: Pubkey
    perpetuals: Pubkey
    pool: Pubkey


def refresh_assets_under_management(
    args: RefreshAssetsUnderManagementArgs,
    accounts: RefreshAssetsUnderManagementAccounts,
    program_id: Pubkey = PROGRAM_ID,
    remaining_accounts: typing.Optional[typing.List[AccountMeta]] = None,
) -> Instruction:
    keys: list[AccountMeta] = [
        AccountMeta(pubkey=accounts["keeper"], is_signer=True, is_writable=False),
        AccountMeta(pubkey=accounts["perpetuals"], is_signer=False, is_writable=False),
        AccountMeta(pubkey=accounts["pool"], is_signer=False, is_writable=True),
    ]
    if remaining_accounts is not None:
        keys += remaining_accounts
    identifier = b"\xa2\x00\xd77\xe1\x0f\xb9\x00"
    encoded_args = layout.build(
        {
            "params": args["params"].to_encodable(),
        }
    )
    data = identifier + encoded_args
    return Instruction(program_id, data, keys)
