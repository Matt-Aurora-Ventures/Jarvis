from __future__ import annotations
import typing
from solders.pubkey import Pubkey
from solders.instruction import Instruction, AccountMeta
import borsh_construct as borsh
from .. import types
from ..program_id import PROGRAM_ID


class SetMaxGlobalSizesArgs(typing.TypedDict):
    params: types.set_max_global_sizes_params.SetMaxGlobalSizesParams


layout = borsh.CStruct(
    "params" / types.set_max_global_sizes_params.SetMaxGlobalSizesParams.layout
)


class SetMaxGlobalSizesAccounts(typing.TypedDict):
    keeper: Pubkey
    custody: Pubkey
    pool: Pubkey


def set_max_global_sizes(
    args: SetMaxGlobalSizesArgs,
    accounts: SetMaxGlobalSizesAccounts,
    program_id: Pubkey = PROGRAM_ID,
    remaining_accounts: typing.Optional[typing.List[AccountMeta]] = None,
) -> Instruction:
    keys: list[AccountMeta] = [
        AccountMeta(pubkey=accounts["keeper"], is_signer=True, is_writable=False),
        AccountMeta(pubkey=accounts["custody"], is_signer=False, is_writable=True),
        AccountMeta(pubkey=accounts["pool"], is_signer=False, is_writable=False),
    ]
    if remaining_accounts is not None:
        keys += remaining_accounts
    identifier = b"Y\x02\xd2\x18\xa7\xe3\r\xd6"
    encoded_args = layout.build(
        {
            "params": args["params"].to_encodable(),
        }
    )
    data = identifier + encoded_args
    return Instruction(program_id, data, keys)
