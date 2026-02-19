from __future__ import annotations
import typing
from solders.pubkey import Pubkey
from solders.instruction import Instruction, AccountMeta
import borsh_construct as borsh
from .. import types
from ..program_id import PROGRAM_ID


class SetPoolConfigArgs(typing.TypedDict):
    params: types.set_pool_config_params.SetPoolConfigParams


layout = borsh.CStruct(
    "params" / types.set_pool_config_params.SetPoolConfigParams.layout
)


class SetPoolConfigAccounts(typing.TypedDict):
    admin: Pubkey
    perpetuals: Pubkey
    pool: Pubkey


def set_pool_config(
    args: SetPoolConfigArgs,
    accounts: SetPoolConfigAccounts,
    program_id: Pubkey = PROGRAM_ID,
    remaining_accounts: typing.Optional[typing.List[AccountMeta]] = None,
) -> Instruction:
    keys: list[AccountMeta] = [
        AccountMeta(pubkey=accounts["admin"], is_signer=True, is_writable=False),
        AccountMeta(pubkey=accounts["perpetuals"], is_signer=False, is_writable=False),
        AccountMeta(pubkey=accounts["pool"], is_signer=False, is_writable=True),
    ]
    if remaining_accounts is not None:
        keys += remaining_accounts
    identifier = b"\xd8WA}qn\xb9x"
    encoded_args = layout.build(
        {
            "params": args["params"].to_encodable(),
        }
    )
    data = identifier + encoded_args
    return Instruction(program_id, data, keys)
