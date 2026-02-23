from __future__ import annotations
import typing
from solders.pubkey import Pubkey
from solders.system_program import ID as SYS_PROGRAM_ID
from spl.token.constants import TOKEN_PROGRAM_ID, ASSOCIATED_TOKEN_PROGRAM_ID
from solders.instruction import Instruction, AccountMeta
from ..program_id import PROGRAM_ID


class ClosePositionRequest2Accounts(typing.TypedDict):
    keeper: typing.Optional[Pubkey]
    owner: Pubkey
    owner_ata: Pubkey
    pool: Pubkey
    position_request: Pubkey
    position_request_ata: Pubkey
    position: Pubkey
    mint: Pubkey
    event_authority: Pubkey
    program: Pubkey


def close_position_request2(
    accounts: ClosePositionRequest2Accounts,
    program_id: Pubkey = PROGRAM_ID,
    remaining_accounts: typing.Optional[typing.List[AccountMeta]] = None,
) -> Instruction:
    keys: list[AccountMeta] = [
        (
            AccountMeta(pubkey=accounts["keeper"], is_signer=True, is_writable=True)
            if accounts["keeper"]
            else AccountMeta(pubkey=program_id, is_signer=False, is_writable=False)
        ),
        AccountMeta(pubkey=accounts["owner"], is_signer=False, is_writable=True),
        AccountMeta(pubkey=accounts["owner_ata"], is_signer=False, is_writable=True),
        AccountMeta(pubkey=accounts["pool"], is_signer=False, is_writable=True),
        AccountMeta(
            pubkey=accounts["position_request"], is_signer=False, is_writable=True
        ),
        AccountMeta(
            pubkey=accounts["position_request_ata"], is_signer=False, is_writable=True
        ),
        AccountMeta(pubkey=accounts["position"], is_signer=False, is_writable=False),
        AccountMeta(pubkey=accounts["mint"], is_signer=False, is_writable=False),
        AccountMeta(pubkey=TOKEN_PROGRAM_ID, is_signer=False, is_writable=False),
        AccountMeta(pubkey=SYS_PROGRAM_ID, is_signer=False, is_writable=False),
        AccountMeta(
            pubkey=ASSOCIATED_TOKEN_PROGRAM_ID, is_signer=False, is_writable=False
        ),
        AccountMeta(
            pubkey=accounts["event_authority"], is_signer=False, is_writable=False
        ),
        AccountMeta(pubkey=accounts["program"], is_signer=False, is_writable=False),
    ]
    if remaining_accounts is not None:
        keys += remaining_accounts
    identifier = b"yD\xa2\x1c\xd8/\xc8B"
    encoded_args = b""
    data = identifier + encoded_args
    return Instruction(program_id, data, keys)
