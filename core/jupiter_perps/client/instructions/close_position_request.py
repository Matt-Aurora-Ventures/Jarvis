from __future__ import annotations
import typing
from solders.pubkey import Pubkey
from spl.token.constants import TOKEN_PROGRAM_ID
from solders.instruction import Instruction, AccountMeta
import borsh_construct as borsh
from .. import types
from ..program_id import PROGRAM_ID


class ClosePositionRequestArgs(typing.TypedDict):
    params: types.close_position_request_params.ClosePositionRequestParams


layout = borsh.CStruct(
    "params" / types.close_position_request_params.ClosePositionRequestParams.layout
)


class ClosePositionRequestAccounts(typing.TypedDict):
    keeper: typing.Optional[Pubkey]
    owner: Pubkey
    owner_ata: typing.Optional[Pubkey]
    pool: Pubkey
    position_request: Pubkey
    position_request_ata: Pubkey
    position: Pubkey
    event_authority: Pubkey
    program: Pubkey


def close_position_request(
    args: ClosePositionRequestArgs,
    accounts: ClosePositionRequestAccounts,
    program_id: Pubkey = PROGRAM_ID,
    remaining_accounts: typing.Optional[typing.List[AccountMeta]] = None,
) -> Instruction:
    keys: list[AccountMeta] = [
        (
            AccountMeta(pubkey=accounts["keeper"], is_signer=True, is_writable=False)
            if accounts["keeper"]
            else AccountMeta(pubkey=program_id, is_signer=False, is_writable=False)
        ),
        AccountMeta(pubkey=accounts["owner"], is_signer=False, is_writable=True),
        (
            AccountMeta(pubkey=accounts["owner_ata"], is_signer=False, is_writable=True)
            if accounts["owner_ata"]
            else AccountMeta(pubkey=program_id, is_signer=False, is_writable=False)
        ),
        AccountMeta(pubkey=accounts["pool"], is_signer=False, is_writable=True),
        AccountMeta(
            pubkey=accounts["position_request"], is_signer=False, is_writable=True
        ),
        AccountMeta(
            pubkey=accounts["position_request_ata"], is_signer=False, is_writable=True
        ),
        AccountMeta(pubkey=accounts["position"], is_signer=False, is_writable=False),
        AccountMeta(pubkey=TOKEN_PROGRAM_ID, is_signer=False, is_writable=False),
        AccountMeta(
            pubkey=accounts["event_authority"], is_signer=False, is_writable=False
        ),
        AccountMeta(pubkey=accounts["program"], is_signer=False, is_writable=False),
    ]
    if remaining_accounts is not None:
        keys += remaining_accounts
    identifier = b"(i\xd9\xbc\xdc-mn"
    encoded_args = layout.build(
        {
            "params": args["params"].to_encodable(),
        }
    )
    data = identifier + encoded_args
    return Instruction(program_id, data, keys)
