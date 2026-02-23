"""Native Solana RPC submission and confirmation helpers for live mode."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass

from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Confirmed
from solana.rpc.types import TxOpts
from solders.signature import Signature
from solders.transaction import VersionedTransaction


@dataclass(frozen=True)
class SubmitResult:
    signature: str
    slot: int
    block_time: int | None


async def send_and_confirm_transaction(
    signed_tx: VersionedTransaction,
    rpc_url: str,
    timeout_seconds: int = 60,
) -> SubmitResult:
    """Submit a transaction and wait for confirmed status."""
    async with AsyncClient(rpc_url, commitment=Confirmed) as client:
        send_result = await client.send_raw_transaction(
            bytes(signed_tx),
            opts=TxOpts(skip_preflight=False, preflight_commitment=Confirmed, max_retries=3),
        )
        signature = str(send_result.value)
        sig_obj = Signature.from_string(signature)

        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            statuses = await client.get_signature_statuses(
                [sig_obj],
                search_transaction_history=True,
            )
            status = statuses.value[0] if statuses.value else None

            if status is not None:
                if status.err is not None:
                    raise RuntimeError(f"Transaction failed: {status.err}")

                confirmation_status = str(status.confirmation_status or "").lower()
                if confirmation_status in {"confirmed", "finalized"}:
                    tx_info = await client.get_transaction(
                        sig_obj,
                        commitment=Confirmed,
                        max_supported_transaction_version=0,
                    )
                    block_time = None
                    if tx_info.value is not None:
                        block_time = int(tx_info.value.block_time or 0) or None
                    return SubmitResult(
                        signature=signature,
                        slot=int(status.slot),
                        block_time=block_time,
                    )

            await asyncio.sleep(1.0)

    raise TimeoutError(f"Timed out waiting for confirmation: {signature}")
