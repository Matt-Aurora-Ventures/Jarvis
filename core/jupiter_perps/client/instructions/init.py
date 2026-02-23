from __future__ import annotations
import typing
from solders.pubkey import Pubkey
from solders.system_program import ID as SYS_PROGRAM_ID
from spl.token.constants import TOKEN_PROGRAM_ID
from solders.instruction import Instruction, AccountMeta
import borsh_construct as borsh
from .. import types
from ..program_id import PROGRAM_ID


class InitArgs(typing.TypedDict):
    params: types.init_params.InitParams


layout = borsh.CStruct("params" / types.init_params.InitParams.layout)


class InitAccounts(typing.TypedDict):
    upgrade_authority: Pubkey
    admin: Pubkey
    transfer_authority: Pubkey
    perpetuals: Pubkey
    perpetuals_program: Pubkey
    perpetuals_program_data: Pubkey


def init(
    args: InitArgs,
    accounts: InitAccounts,
    program_id: Pubkey = PROGRAM_ID,
    remaining_accounts: typing.Optional[typing.List[AccountMeta]] = None,
) -> Instruction:
    keys: list[AccountMeta] = [
        AccountMeta(
            pubkey=accounts["upgrade_authority"], is_signer=True, is_writable=True
        ),
        AccountMeta(pubkey=accounts["admin"], is_signer=False, is_writable=False),
        AccountMeta(
            pubkey=accounts["transfer_authority"], is_signer=False, is_writable=True
        ),
        AccountMeta(pubkey=accounts["perpetuals"], is_signer=False, is_writable=True),
        AccountMeta(
            pubkey=accounts["perpetuals_program"], is_signer=False, is_writable=False
        ),
        AccountMeta(
            pubkey=accounts["perpetuals_program_data"],
            is_signer=False,
            is_writable=False,
        ),
        AccountMeta(pubkey=SYS_PROGRAM_ID, is_signer=False, is_writable=False),
        AccountMeta(pubkey=TOKEN_PROGRAM_ID, is_signer=False, is_writable=False),
    ]
    if remaining_accounts is not None:
        keys += remaining_accounts
    identifier = b"\xdc;\xcf\xecl\xfa/d"
    encoded_args = layout.build(
        {
            "params": args["params"].to_encodable(),
        }
    )
    data = identifier + encoded_args
    return Instruction(program_id, data, keys)
