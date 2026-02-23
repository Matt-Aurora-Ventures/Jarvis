from __future__ import annotations
import typing
from solders.pubkey import Pubkey
from solders.instruction import Instruction, AccountMeta
import borsh_construct as borsh
from .. import types
from ..program_id import PROGRAM_ID


class SetTestTimeArgs(typing.TypedDict):
    params: types.set_test_time_params.SetTestTimeParams


layout = borsh.CStruct("params" / types.set_test_time_params.SetTestTimeParams.layout)


class SetTestTimeAccounts(typing.TypedDict):
    admin: Pubkey
    perpetuals: Pubkey


def set_test_time(
    args: SetTestTimeArgs,
    accounts: SetTestTimeAccounts,
    program_id: Pubkey = PROGRAM_ID,
    remaining_accounts: typing.Optional[typing.List[AccountMeta]] = None,
) -> Instruction:
    keys: list[AccountMeta] = [
        AccountMeta(pubkey=accounts["admin"], is_signer=True, is_writable=False),
        AccountMeta(pubkey=accounts["perpetuals"], is_signer=False, is_writable=True),
    ]
    if remaining_accounts is not None:
        keys += remaining_accounts
    identifier = b"\xf2\xe7\xb1\xfb~\x91\x9fh"
    encoded_args = layout.build(
        {
            "params": args["params"].to_encodable(),
        }
    )
    data = identifier + encoded_args
    return Instruction(program_id, data, keys)
