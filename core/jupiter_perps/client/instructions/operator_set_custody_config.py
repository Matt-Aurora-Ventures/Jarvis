from __future__ import annotations
import typing
from solders.pubkey import Pubkey
from solders.instruction import Instruction, AccountMeta
import borsh_construct as borsh
from .. import types
from ..program_id import PROGRAM_ID


class OperatorSetCustodyConfigArgs(typing.TypedDict):
    params: types.operator_set_custody_config_params.OperatorSetCustodyConfigParams


layout = borsh.CStruct(
    "params"
    / types.operator_set_custody_config_params.OperatorSetCustodyConfigParams.layout
)


class OperatorSetCustodyConfigAccounts(typing.TypedDict):
    operator: Pubkey
    custody: Pubkey


def operator_set_custody_config(
    args: OperatorSetCustodyConfigArgs,
    accounts: OperatorSetCustodyConfigAccounts,
    program_id: Pubkey = PROGRAM_ID,
    remaining_accounts: typing.Optional[typing.List[AccountMeta]] = None,
) -> Instruction:
    keys: list[AccountMeta] = [
        AccountMeta(pubkey=accounts["operator"], is_signer=True, is_writable=False),
        AccountMeta(pubkey=accounts["custody"], is_signer=False, is_writable=True),
    ]
    if remaining_accounts is not None:
        keys += remaining_accounts
    identifier = b"\xa6\x89\\\xcc\x91\xe0\x18\xda"
    encoded_args = layout.build(
        {
            "params": args["params"].to_encodable(),
        }
    )
    data = identifier + encoded_args
    return Instruction(program_id, data, keys)
