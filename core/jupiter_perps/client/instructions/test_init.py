from __future__ import annotations
import typing
from solders.pubkey import Pubkey
from solders.system_program import ID as SYS_PROGRAM_ID
from spl.token.constants import TOKEN_PROGRAM_ID
from solders.instruction import Instruction, AccountMeta
import borsh_construct as borsh
from .. import types
from ..program_id import PROGRAM_ID


class TestInitArgs(typing.TypedDict):
    params: types.test_init_params.TestInitParams


layout = borsh.CStruct("params" / types.test_init_params.TestInitParams.layout)


class TestInitAccounts(typing.TypedDict):
    upgrade_authority: Pubkey
    admin: Pubkey
    transfer_authority: Pubkey
    perpetuals: Pubkey


def test_init(
    args: TestInitArgs,
    accounts: TestInitAccounts,
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
        AccountMeta(pubkey=SYS_PROGRAM_ID, is_signer=False, is_writable=False),
        AccountMeta(pubkey=TOKEN_PROGRAM_ID, is_signer=False, is_writable=False),
    ]
    if remaining_accounts is not None:
        keys += remaining_accounts
    identifier = b"03\\zQ\x13p)"
    encoded_args = layout.build(
        {
            "params": args["params"].to_encodable(),
        }
    )
    data = identifier + encoded_args
    return Instruction(program_id, data, keys)
