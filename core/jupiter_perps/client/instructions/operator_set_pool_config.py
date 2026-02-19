from __future__ import annotations
import typing
from solders.pubkey import Pubkey
from solders.instruction import Instruction, AccountMeta
import borsh_construct as borsh
from .. import types
from ..program_id import PROGRAM_ID


class OperatorSetPoolConfigArgs(typing.TypedDict):
    params: types.operator_set_pool_config_params.OperatorSetPoolConfigParams


layout = borsh.CStruct(
    "params" / types.operator_set_pool_config_params.OperatorSetPoolConfigParams.layout
)


class OperatorSetPoolConfigAccounts(typing.TypedDict):
    operator: Pubkey
    pool: Pubkey


def operator_set_pool_config(
    args: OperatorSetPoolConfigArgs,
    accounts: OperatorSetPoolConfigAccounts,
    program_id: Pubkey = PROGRAM_ID,
    remaining_accounts: typing.Optional[typing.List[AccountMeta]] = None,
) -> Instruction:
    keys: list[AccountMeta] = [
        AccountMeta(pubkey=accounts["operator"], is_signer=True, is_writable=False),
        AccountMeta(pubkey=accounts["pool"], is_signer=False, is_writable=True),
    ]
    if remaining_accounts is not None:
        keys += remaining_accounts
    identifier = b"L\xc9P\x12\xc7\\\xf6i"
    encoded_args = layout.build(
        {
            "params": args["params"].to_encodable(),
        }
    )
    data = identifier + encoded_args
    return Instruction(program_id, data, keys)
