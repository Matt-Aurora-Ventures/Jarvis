from __future__ import annotations
import typing
from solders.pubkey import Pubkey
from solders.instruction import Instruction, AccountMeta
import borsh_construct as borsh
from .. import types
from ..program_id import PROGRAM_ID


class TransferAdminArgs(typing.TypedDict):
    params: types.transfer_admin_params.TransferAdminParams


layout = borsh.CStruct(
    "params" / types.transfer_admin_params.TransferAdminParams.layout
)


class TransferAdminAccounts(typing.TypedDict):
    admin: Pubkey
    new_admin: Pubkey
    perpetuals: Pubkey


def transfer_admin(
    args: TransferAdminArgs,
    accounts: TransferAdminAccounts,
    program_id: Pubkey = PROGRAM_ID,
    remaining_accounts: typing.Optional[typing.List[AccountMeta]] = None,
) -> Instruction:
    keys: list[AccountMeta] = [
        AccountMeta(pubkey=accounts["admin"], is_signer=True, is_writable=False),
        AccountMeta(pubkey=accounts["new_admin"], is_signer=False, is_writable=False),
        AccountMeta(pubkey=accounts["perpetuals"], is_signer=False, is_writable=True),
    ]
    if remaining_accounts is not None:
        keys += remaining_accounts
    identifier = b"*\xf2Bj\xe4\no\x9c"
    encoded_args = layout.build(
        {
            "params": args["params"].to_encodable(),
        }
    )
    data = identifier + encoded_args
    return Instruction(program_id, data, keys)
