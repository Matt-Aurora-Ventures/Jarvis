from __future__ import annotations
import typing
from solders.pubkey import Pubkey
from solders.instruction import Instruction, AccountMeta
import borsh_construct as borsh
from .. import types
from ..program_id import PROGRAM_ID


class SetCustodyConfigArgs(typing.TypedDict):
    params: types.set_custody_config_params.SetCustodyConfigParams


layout = borsh.CStruct(
    "params" / types.set_custody_config_params.SetCustodyConfigParams.layout
)


class SetCustodyConfigAccounts(typing.TypedDict):
    admin: Pubkey
    perpetuals: Pubkey
    custody: Pubkey


def set_custody_config(
    args: SetCustodyConfigArgs,
    accounts: SetCustodyConfigAccounts,
    program_id: Pubkey = PROGRAM_ID,
    remaining_accounts: typing.Optional[typing.List[AccountMeta]] = None,
) -> Instruction:
    keys: list[AccountMeta] = [
        AccountMeta(pubkey=accounts["admin"], is_signer=True, is_writable=True),
        AccountMeta(pubkey=accounts["perpetuals"], is_signer=False, is_writable=False),
        AccountMeta(pubkey=accounts["custody"], is_signer=False, is_writable=True),
    ]
    if remaining_accounts is not None:
        keys += remaining_accounts
    identifier = b"\x85a\x82\x8f\xd7\xe5$\xb0"
    encoded_args = layout.build(
        {
            "params": args["params"].to_encodable(),
        }
    )
    data = identifier + encoded_args
    return Instruction(program_id, data, keys)
