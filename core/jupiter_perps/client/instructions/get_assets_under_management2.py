from __future__ import annotations
import typing
from solders.pubkey import Pubkey
from solders.instruction import Instruction, AccountMeta
import borsh_construct as borsh
from .. import types
from ..program_id import PROGRAM_ID


class GetAssetsUnderManagement2Args(typing.TypedDict):
    params: types.get_assets_under_management2_params.GetAssetsUnderManagement2Params


layout = borsh.CStruct(
    "params"
    / types.get_assets_under_management2_params.GetAssetsUnderManagement2Params.layout
)


class GetAssetsUnderManagement2Accounts(typing.TypedDict):
    perpetuals: Pubkey
    pool: Pubkey


def get_assets_under_management2(
    args: GetAssetsUnderManagement2Args,
    accounts: GetAssetsUnderManagement2Accounts,
    program_id: Pubkey = PROGRAM_ID,
    remaining_accounts: typing.Optional[typing.List[AccountMeta]] = None,
) -> Instruction:
    keys: list[AccountMeta] = [
        AccountMeta(pubkey=accounts["perpetuals"], is_signer=False, is_writable=False),
        AccountMeta(pubkey=accounts["pool"], is_signer=False, is_writable=False),
    ]
    if remaining_accounts is not None:
        keys += remaining_accounts
    identifier = b"\xc1\xd2\r\xf9q\x95\x1dT"
    encoded_args = layout.build(
        {
            "params": args["params"].to_encodable(),
        }
    )
    data = identifier + encoded_args
    return Instruction(program_id, data, keys)
