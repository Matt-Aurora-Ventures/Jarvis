"""Circle CCTP Bridge Controller — 10-state machine for bridging USDC from Base to Solana.

Manages the complete lifecycle of a cross-chain fee transfer:
  Base (EVM): collect fees -> approve USDC -> burn via CCTP TokenMessenger
  Circle:     poll attestation API until message is attested
  Solana:     receive message -> mint USDC -> deposit to staking pool

State machine:
  FEE_COLLECTED -> USDC_APPROVED -> BURN_SUBMITTED -> BURN_CONFIRMED ->
  ATTESTATION_REQUESTED -> ATTESTATION_RECEIVED -> MINT_SUBMITTED ->
  MINT_CONFIRMED -> DEPOSITED_TO_POOL
  (any state) -> FAILED (terminal)

All state transitions are persisted to the ``inv_bridge_jobs`` table and
broadcast to Redis channel ``investments:bridge_events``.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import struct
import time
from datetime import datetime, timezone
from typing import Any, Optional

import asyncpg
import redis.asyncio as aioredis
from eth_account import Account
from eth_account.signers.local import LocalAccount
from web3 import AsyncWeb3
from web3.providers import AsyncHTTPProvider
from web3.contract import AsyncContract
from web3.types import TxParams

from services.investments.config import InvestmentConfig

logger = logging.getLogger("investments.bridge")

# ---------------------------------------------------------------------------
# CCTP Contract Addresses (Mainnet)
# ---------------------------------------------------------------------------

# Base (EVM) side
BASE_TOKEN_MESSENGER = "0x1682Ae6375C4E4A97e4B583BC394c861A46D8962"
BASE_MESSAGE_TRANSMITTER = "0xAD09780d193884d503182aD4F75D22B7d6f36EFe"
BASE_USDC = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"

# Solana side
SOLANA_MESSAGE_TRANSMITTER = "CCTPmbSD7gX1bxKPAmg77w8oFzNFpaQiQUWD43TKaecd"
SOLANA_USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"

# Circle CCTP domains
DOMAIN_SOLANA = 5
DOMAIN_BASE = 6

# Circle Attestation Service
CIRCLE_ATTESTATION_URL = "https://iris-api.circle.com/attestations/{message_hash}"

# Base chain
BASE_CHAIN_ID = 8453
USDC_DECIMALS = 6

# ---------------------------------------------------------------------------
# Timing constants
# ---------------------------------------------------------------------------
ATTESTATION_POLL_INTERVAL_S = 15
ATTESTATION_TIMEOUT_S = 30 * 60  # 30 minutes
MAX_RETRIES_PER_STATE = 3
RETRY_BASE_DELAY_S = 5  # exponential backoff base

# ---------------------------------------------------------------------------
# Minimal ABIs
# ---------------------------------------------------------------------------

ERC20_APPROVE_ABI: list[dict[str, Any]] = [
    {
        "name": "approve",
        "type": "function",
        "stateMutability": "nonpayable",
        "inputs": [
            {"name": "spender", "type": "address"},
            {"name": "amount", "type": "uint256"},
        ],
        "outputs": [{"name": "", "type": "bool"}],
    },
    {
        "name": "allowance",
        "type": "function",
        "stateMutability": "view",
        "inputs": [
            {"name": "owner", "type": "address"},
            {"name": "spender", "type": "address"},
        ],
        "outputs": [{"name": "", "type": "uint256"}],
    },
    {
        "name": "balanceOf",
        "type": "function",
        "stateMutability": "view",
        "inputs": [{"name": "account", "type": "address"}],
        "outputs": [{"name": "", "type": "uint256"}],
    },
]

TOKEN_MESSENGER_ABI: list[dict[str, Any]] = [
    {
        "name": "depositForBurn",
        "type": "function",
        "stateMutability": "nonpayable",
        "inputs": [
            {"name": "amount", "type": "uint256"},
            {"name": "destinationDomain", "type": "uint32"},
            {"name": "mintRecipient", "type": "bytes32"},
            {"name": "burnToken", "type": "address"},
        ],
        "outputs": [{"name": "_nonce", "type": "uint64"}],
    },
]

# MessageSent event emitted by MessageTransmitter when TokenMessenger calls sendMessage
MESSAGE_SENT_EVENT_ABI: list[dict[str, Any]] = [
    {
        "name": "MessageSent",
        "type": "event",
        "inputs": [
            {"name": "message", "type": "bytes", "indexed": False},
        ],
    },
]

# ---------------------------------------------------------------------------
# Terminal and non-terminal states
# ---------------------------------------------------------------------------

_TERMINAL_STATES = {"DEPOSITED_TO_POOL", "FAILED"}

_STATE_ORDER = [
    "FEE_COLLECTED",
    "USDC_APPROVED",
    "BURN_SUBMITTED",
    "BURN_CONFIRMED",
    "ATTESTATION_REQUESTED",
    "ATTESTATION_RECEIVED",
    "MINT_SUBMITTED",
    "MINT_CONFIRMED",
    "DEPOSITED_TO_POOL",
]


class BridgeController:
    """10-state CCTP bridge state machine for Base -> Solana USDC transfers."""

    def __init__(
        self,
        config: InvestmentConfig,
        db: asyncpg.Pool,
        redis: aioredis.Redis,
    ) -> None:
        self.cfg = config
        self.db = db
        self.redis = redis

        # Web3 async provider for Base chain
        self.w3 = AsyncWeb3(AsyncHTTPProvider(config.base_rpc_url))

        # CCTP contracts on Base
        self.usdc_contract: AsyncContract = self.w3.eth.contract(
            address=AsyncWeb3.to_checksum_address(BASE_USDC),
            abi=ERC20_APPROVE_ABI,
        )
        self.token_messenger: AsyncContract = self.w3.eth.contract(
            address=AsyncWeb3.to_checksum_address(BASE_TOKEN_MESSENGER),
            abi=TOKEN_MESSENGER_ABI,
        )
        self.message_transmitter: AsyncContract = self.w3.eth.contract(
            address=AsyncWeb3.to_checksum_address(BASE_MESSAGE_TRANSMITTER),
            abi=MESSAGE_SENT_EVENT_ABI,
        )

        # Management wallet
        self.account: Optional[LocalAccount] = None
        if config.management_wallet_key:
            self.account = Account.from_key(config.management_wallet_key)
            logger.info("Bridge wallet loaded: %s", self.account.address)

        # Lazy HTTP client for attestation polling and Solana RPC
        self._http_session: Optional[Any] = None

        # State -> handler mapping
        self._handlers: dict[str, Any] = {
            "FEE_COLLECTED": self._approve_usdc,
            "USDC_APPROVED": self._submit_burn,
            "BURN_SUBMITTED": self._confirm_burn,
            "BURN_CONFIRMED": self._request_attestation,
            "ATTESTATION_REQUESTED": self._poll_attestation,
            "ATTESTATION_RECEIVED": self._submit_mint,
            "MINT_SUBMITTED": self._confirm_mint,
            "MINT_CONFIRMED": self._deposit_to_pool,
        }

    # ------------------------------------------------------------------
    # HTTP session management
    # ------------------------------------------------------------------

    async def _ensure_http(self) -> Any:
        """Lazy-init an aiohttp session for attestation polling and Solana RPC."""
        if self._http_session is None or self._http_session.closed:
            import aiohttp

            self._http_session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30)
            )
        return self._http_session

    async def close(self) -> None:
        """Clean up HTTP session."""
        if self._http_session and not self._http_session.closed:
            await self._http_session.close()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def start_bridge(self, amount_usdc: float) -> int:
        """Create a new bridge job and return its ID.

        The job starts in FEE_COLLECTED state.  Call ``advance()`` or
        ``advance_all_pending()`` to progress it through the state machine.

        Args:
            amount_usdc: Amount of USDC to bridge (human-readable, e.g. 100.50).

        Returns:
            The new job ID (serial primary key from inv_bridge_jobs).
        """
        amount_raw = int(amount_usdc * 10**USDC_DECIMALS)

        row = await self.db.fetchrow(
            """
            INSERT INTO inv_bridge_jobs (amount_usdc, amount_raw, state)
            VALUES ($1, $2, 'FEE_COLLECTED')
            RETURNING id
            """,
            amount_usdc,
            amount_raw,
        )
        job_id = row["id"]

        logger.info(
            "Bridge job #%d created: $%.2f USDC (%d raw)",
            job_id,
            amount_usdc,
            amount_raw,
        )
        await self._publish_event(job_id, "FEE_COLLECTED", {
            "amount_usdc": amount_usdc,
            "amount_raw": amount_raw,
        })

        return job_id

    async def advance(self, job_id: int) -> str:
        """Advance a bridge job by one state.

        Looks up the current state, invokes the appropriate handler, and
        transitions to the next state on success.  On failure, retries up
        to MAX_RETRIES_PER_STATE times with exponential backoff, then
        transitions to FAILED.

        Args:
            job_id: The bridge job to advance.

        Returns:
            The new state after the transition attempt.
        """
        job = await self.get_job(job_id)
        if job is None:
            raise ValueError(f"Bridge job #{job_id} not found")

        current_state = job["state"]
        if current_state in _TERMINAL_STATES:
            logger.info("Job #%d already in terminal state: %s", job_id, current_state)
            return current_state

        handler = self._handlers.get(current_state)
        if handler is None:
            error = f"No handler for state {current_state}"
            await self._fail_job(job_id, error)
            return "FAILED"

        retry_count = job.get("retry_count", 0) or 0

        try:
            new_state, updates = await handler(job)
            # Transition succeeded
            await self._transition(job_id, new_state, updates)
            return new_state

        except Exception as exc:
            retry_count += 1
            error_msg = f"State {current_state} failed (attempt {retry_count}/{MAX_RETRIES_PER_STATE}): {exc}"
            logger.error("Job #%d: %s", job_id, error_msg)

            if retry_count >= MAX_RETRIES_PER_STATE:
                await self._fail_job(job_id, error_msg)
                return "FAILED"

            # Update retry count and schedule backoff
            delay = RETRY_BASE_DELAY_S * (2 ** (retry_count - 1))
            logger.info(
                "Job #%d: retrying state %s in %ds (attempt %d/%d)",
                job_id, current_state, delay, retry_count, MAX_RETRIES_PER_STATE,
            )
            await self.db.execute(
                """
                UPDATE inv_bridge_jobs
                SET retry_count = $2, error = $3, updated_at = NOW()
                WHERE id = $1
                """,
                job_id,
                retry_count,
                error_msg,
            )
            await asyncio.sleep(delay)

            # Retry the same state
            return await self.advance(job_id)

    async def advance_all_pending(self) -> list[dict]:
        """Find all non-terminal jobs and try to advance each one.

        Returns a list of dicts with job_id, old_state, new_state for each
        job that was processed.
        """
        pending = await self.get_pending_jobs()
        results: list[dict] = []

        for job in pending:
            job_id = job["id"]
            old_state = job["state"]

            try:
                new_state = await self.advance(job_id)
                results.append({
                    "job_id": job_id,
                    "old_state": old_state,
                    "new_state": new_state,
                    "success": True,
                })
            except Exception as exc:
                logger.exception("Failed to advance job #%d", job_id)
                results.append({
                    "job_id": job_id,
                    "old_state": old_state,
                    "new_state": "FAILED",
                    "success": False,
                    "error": str(exc),
                })

        return results

    async def get_job(self, job_id: int) -> Optional[dict]:
        """Fetch a single bridge job by ID."""
        row = await self.db.fetchrow(
            "SELECT * FROM inv_bridge_jobs WHERE id = $1", job_id
        )
        return dict(row) if row else None

    async def get_pending_jobs(self) -> list[dict]:
        """Fetch all non-terminal bridge jobs, ordered by creation time."""
        rows = await self.db.fetch(
            """
            SELECT * FROM inv_bridge_jobs
            WHERE state NOT IN ('DEPOSITED_TO_POOL', 'FAILED')
            ORDER BY created_at ASC
            """
        )
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # State handlers — each returns (new_state, update_dict)
    # ------------------------------------------------------------------

    async def _approve_usdc(self, job: dict) -> tuple[str, dict]:
        """FEE_COLLECTED -> USDC_APPROVED: approve CCTP TokenMessenger to spend USDC."""
        amount_raw = int(job["amount_raw"])
        job_id = job["id"]

        if self.cfg.dry_run:
            logger.info(
                "[DRY RUN] Job #%d: Would approve %d USDC-raw for TokenMessenger",
                job_id, amount_raw,
            )
            return "USDC_APPROVED", {
                "approve_tx_hash": f"0x_dry_run_approve_{job_id}",
            }

        self._require_wallet()
        assert self.account is not None

        # Check current allowance — skip approval if already sufficient
        current_allowance = await self.usdc_contract.functions.allowance(
            self.account.address,
            AsyncWeb3.to_checksum_address(BASE_TOKEN_MESSENGER),
        ).call()

        if current_allowance >= amount_raw:
            logger.info(
                "Job #%d: Allowance already sufficient (%d >= %d), skipping approve",
                job_id, current_allowance, amount_raw,
            )
            return "USDC_APPROVED", {"approve_tx_hash": "allowance_sufficient"}

        # Build and send approve tx
        tx_hash = await self._build_and_send_evm(
            self.usdc_contract.functions.approve(
                AsyncWeb3.to_checksum_address(BASE_TOKEN_MESSENGER),
                amount_raw,
            )
        )
        logger.info("Job #%d: USDC approve tx sent: %s", job_id, tx_hash)

        return "USDC_APPROVED", {"approve_tx_hash": tx_hash}

    async def _submit_burn(self, job: dict) -> tuple[str, dict]:
        """USDC_APPROVED -> BURN_SUBMITTED: call depositForBurn on TokenMessenger."""
        amount_raw = int(job["amount_raw"])
        job_id = job["id"]

        # Build the mintRecipient: Solana wallet pubkey zero-padded to 32 bytes.
        # For CCTP, this is the associated token account (ATA) for USDC on Solana,
        # but the protocol accepts the wallet pubkey and resolves internally.
        mint_recipient = self._solana_address_to_bytes32(self.cfg.solana_wallet_key)

        if self.cfg.dry_run:
            logger.info(
                "[DRY RUN] Job #%d: Would call depositForBurn(%d, domain=%d, recipient=%s, token=%s)",
                job_id, amount_raw, DOMAIN_SOLANA,
                mint_recipient.hex(), BASE_USDC,
            )
            return "BURN_SUBMITTED", {
                "burn_tx_hash": f"0x_dry_run_burn_{job_id}",
            }

        self._require_wallet()

        tx_hash = await self._build_and_send_evm(
            self.token_messenger.functions.depositForBurn(
                amount_raw,
                DOMAIN_SOLANA,
                mint_recipient,
                AsyncWeb3.to_checksum_address(BASE_USDC),
            )
        )
        logger.info("Job #%d: depositForBurn tx sent: %s", job_id, tx_hash)

        return "BURN_SUBMITTED", {"burn_tx_hash": tx_hash}

    async def _confirm_burn(self, job: dict) -> tuple[str, dict]:
        """BURN_SUBMITTED -> BURN_CONFIRMED: confirm burn tx and extract message bytes + nonce."""
        job_id = job["id"]
        burn_tx_hash = job.get("burn_tx_hash", "")

        if self.cfg.dry_run:
            logger.info(
                "[DRY RUN] Job #%d: Would confirm burn tx %s and extract CCTP message",
                job_id, burn_tx_hash,
            )
            fake_nonce = int(time.time()) % 1_000_000
            fake_message = b"\x00" * 248  # placeholder
            fake_hash = self.w3.keccak(fake_message).hex()
            return "BURN_CONFIRMED", {
                "cctp_nonce": fake_nonce,
                "message_hash": fake_hash,
            }

        # Get the transaction receipt
        receipt = await self.w3.eth.get_transaction_receipt(burn_tx_hash)
        if receipt is None:
            raise RuntimeError(f"Burn tx {burn_tx_hash} not found — may still be pending")

        if receipt["status"] == 0:
            raise RuntimeError(f"Burn tx {burn_tx_hash} reverted on-chain")

        # Parse MessageSent event from the MessageTransmitter contract logs.
        # The event is emitted by MessageTransmitter, not TokenMessenger.
        message_bytes: Optional[bytes] = None
        cctp_nonce: Optional[int] = None

        message_sent_topic = self.w3.keccak(text="MessageSent(bytes)").hex()

        for log_entry in receipt["logs"]:
            log_address = log_entry["address"].lower()
            if log_address != BASE_MESSAGE_TRANSMITTER.lower():
                continue

            topic0 = log_entry["topics"][0].hex() if log_entry["topics"] else None
            if topic0 != message_sent_topic:
                continue

            # Decode the message bytes from the log data.
            # ABI encoding: offset (32 bytes) + length (32 bytes) + data (padded)
            raw_data = log_entry["data"]
            if isinstance(raw_data, str):
                raw_data = bytes.fromhex(raw_data[2:] if raw_data.startswith("0x") else raw_data)

            # Skip the ABI offset (first 32 bytes) and read length (next 32 bytes)
            if len(raw_data) < 64:
                continue

            offset = int.from_bytes(raw_data[:32], "big")
            length = int.from_bytes(raw_data[offset : offset + 32], "big")
            message_bytes = raw_data[offset + 32 : offset + 32 + length]

            # Extract nonce from the CCTP message format.
            # CCTP message structure: version(4) + sourceDomain(4) + destDomain(4) + nonce(8) + ...
            if len(message_bytes) >= 20:
                cctp_nonce = int.from_bytes(message_bytes[12:20], "big")

            break

        if message_bytes is None:
            raise RuntimeError(
                f"MessageSent event not found in burn tx {burn_tx_hash} receipt"
            )

        # Hash the message with keccak256 for attestation lookup
        message_hash = self.w3.keccak(message_bytes).hex()

        logger.info(
            "Job #%d: Burn confirmed — nonce=%s, message_hash=%s",
            job_id, cctp_nonce, message_hash,
        )

        return "BURN_CONFIRMED", {
            "cctp_nonce": cctp_nonce,
            "message_hash": message_hash,
        }

    async def _request_attestation(self, job: dict) -> tuple[str, dict]:
        """BURN_CONFIRMED -> ATTESTATION_REQUESTED: begin polling Circle attestation API.

        This is an immediate transition; the actual polling happens in
        _poll_attestation on the next advance() call.
        """
        job_id = job["id"]
        message_hash = job.get("message_hash", "")

        if not message_hash:
            raise RuntimeError("Cannot request attestation without message_hash")

        logger.info(
            "Job #%d: Attestation requested for message_hash=%s",
            job_id, message_hash,
        )

        return "ATTESTATION_REQUESTED", {}

    async def _poll_attestation(self, job: dict) -> tuple[str, dict]:
        """ATTESTATION_REQUESTED -> ATTESTATION_RECEIVED: poll Circle API until attested.

        Polls every ATTESTATION_POLL_INTERVAL_S seconds, up to ATTESTATION_TIMEOUT_S.
        """
        job_id = job["id"]
        message_hash = job.get("message_hash", "")

        if not message_hash:
            raise RuntimeError("Cannot poll attestation without message_hash")

        if self.cfg.dry_run:
            logger.info(
                "[DRY RUN] Job #%d: Would poll attestation for %s",
                job_id, message_hash,
            )
            return "ATTESTATION_RECEIVED", {
                "attestation": "0x_dry_run_attestation_" + message_hash[:16],
            }

        # Ensure message_hash starts with 0x for the URL
        hash_for_url = message_hash if message_hash.startswith("0x") else f"0x{message_hash}"
        url = CIRCLE_ATTESTATION_URL.format(message_hash=hash_for_url)

        session = await self._ensure_http()
        start_time = time.monotonic()

        while True:
            elapsed = time.monotonic() - start_time
            if elapsed > ATTESTATION_TIMEOUT_S:
                raise TimeoutError(
                    f"Attestation not received after {ATTESTATION_TIMEOUT_S}s "
                    f"for message_hash={message_hash}"
                )

            try:
                async with session.get(url) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        status = data.get("status", "")

                        if status == "complete":
                            attestation = data.get("attestation", "")
                            logger.info(
                                "Job #%d: Attestation received after %.0fs",
                                job_id, elapsed,
                            )
                            return "ATTESTATION_RECEIVED", {
                                "attestation": attestation,
                            }

                        logger.debug(
                            "Job #%d: Attestation status=%s (%.0fs elapsed)",
                            job_id, status, elapsed,
                        )

                    elif resp.status == 404:
                        logger.debug(
                            "Job #%d: Attestation not yet available (%.0fs elapsed)",
                            job_id, elapsed,
                        )
                    else:
                        body = await resp.text()
                        logger.warning(
                            "Job #%d: Attestation API returned %d: %s",
                            job_id, resp.status, body[:200],
                        )

            except TimeoutError:
                raise
            except Exception as exc:
                logger.warning(
                    "Job #%d: Attestation poll error (%.0fs elapsed): %s",
                    job_id, elapsed, exc,
                )

            await asyncio.sleep(ATTESTATION_POLL_INTERVAL_S)

    async def _submit_mint(self, job: dict) -> tuple[str, dict]:
        """ATTESTATION_RECEIVED -> MINT_SUBMITTED: call receiveMessage on Solana MessageTransmitter.

        Sends the CCTP message + attestation to the Solana MessageTransmitter
        program via an RPC transaction.
        """
        job_id = job["id"]
        attestation = job.get("attestation", "")
        message_hash = job.get("message_hash", "")

        if not attestation:
            raise RuntimeError("Cannot submit mint without attestation")

        if self.cfg.dry_run:
            logger.info(
                "[DRY RUN] Job #%d: Would call receiveMessage on Solana MessageTransmitter "
                "(message_hash=%s, attestation=%s...)",
                job_id, message_hash, attestation[:32],
            )
            return "MINT_SUBMITTED", {
                "mint_tx_hash": f"dry_run_mint_{job_id}",
            }

        # Build and submit the Solana receiveMessage transaction.
        # We use httpx-style direct RPC calls to keep dependencies minimal.
        mint_tx_hash = await self._submit_solana_receive_message(job)

        logger.info("Job #%d: receiveMessage tx submitted: %s", job_id, mint_tx_hash)

        return "MINT_SUBMITTED", {"mint_tx_hash": mint_tx_hash}

    async def _confirm_mint(self, job: dict) -> tuple[str, dict]:
        """MINT_SUBMITTED -> MINT_CONFIRMED: verify the Solana mint tx succeeded."""
        job_id = job["id"]
        mint_tx_hash = job.get("mint_tx_hash", "")

        if self.cfg.dry_run:
            logger.info(
                "[DRY RUN] Job #%d: Would confirm Solana mint tx %s",
                job_id, mint_tx_hash,
            )
            return "MINT_CONFIRMED", {}

        if not mint_tx_hash:
            raise RuntimeError("Cannot confirm mint without mint_tx_hash")

        # Poll Solana RPC for transaction confirmation
        session = await self._ensure_http()
        confirmed = False
        poll_start = time.monotonic()
        max_wait = 120  # 2 minutes

        while time.monotonic() - poll_start < max_wait:
            try:
                payload = {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "getTransaction",
                    "params": [
                        mint_tx_hash,
                        {"encoding": "json", "commitment": "confirmed"},
                    ],
                }
                async with session.post(self.cfg.solana_rpc_url, json=payload) as resp:
                    data = await resp.json()
                    result = data.get("result")

                    if result is not None:
                        # Transaction found
                        meta = result.get("meta", {})
                        err = meta.get("err")
                        if err is not None:
                            raise RuntimeError(
                                f"Solana mint tx {mint_tx_hash} failed: {err}"
                            )
                        confirmed = True
                        break

            except RuntimeError:
                raise
            except Exception as exc:
                logger.warning(
                    "Job #%d: Error polling Solana tx %s: %s",
                    job_id, mint_tx_hash, exc,
                )

            await asyncio.sleep(5)

        if not confirmed:
            raise TimeoutError(
                f"Solana mint tx {mint_tx_hash} not confirmed within {max_wait}s"
            )

        logger.info("Job #%d: Solana mint confirmed: %s", job_id, mint_tx_hash)
        return "MINT_CONFIRMED", {}

    async def _deposit_to_pool(self, job: dict) -> tuple[str, dict]:
        """MINT_CONFIRMED -> DEPOSITED_TO_POOL: transfer minted USDC to the staking rewards pool."""
        job_id = job["id"]
        amount_usdc = float(job["amount_usdc"])
        amount_raw = int(job["amount_raw"])

        if self.cfg.dry_run:
            logger.info(
                "[DRY RUN] Job #%d: Would deposit $%.2f USDC to staking pool %s",
                job_id, amount_usdc, self.cfg.staking_pool_address,
            )
            return "DEPOSITED_TO_POOL", {
                "deposit_tx_hash": f"dry_run_deposit_{job_id}",
                "net_deposited_usdc": amount_usdc,
            }

        # Transfer USDC from our Solana wallet to the staking pool's
        # authority reward account via a standard SPL token transfer.
        deposit_tx_hash = await self._submit_solana_spl_transfer(
            mint=SOLANA_USDC_MINT,
            destination=self.cfg.authority_reward_account,
            amount_raw=amount_raw,
        )

        logger.info(
            "Job #%d: Deposited $%.2f USDC to staking pool — tx: %s",
            job_id, amount_usdc, deposit_tx_hash,
        )

        return "DEPOSITED_TO_POOL", {
            "deposit_tx_hash": deposit_tx_hash,
            "net_deposited_usdc": amount_usdc,
        }

    # ------------------------------------------------------------------
    # Solana RPC helpers (minimal, httpx-style via aiohttp)
    # ------------------------------------------------------------------

    async def _submit_solana_receive_message(self, job: dict) -> str:
        """Build and submit the CCTP receiveMessage transaction on Solana.

        This constructs the instruction data for the MessageTransmitter program
        and submits it via Solana RPC.

        Returns the transaction signature string.
        """
        # In production, this would construct the full Anchor instruction
        # with proper account metas for:
        #   - payer (our wallet, signer)
        #   - caller (our wallet)
        #   - authorityPda (derived from MessageTransmitter)
        #   - messageTransmitter (state account)
        #   - usedNonces (PDA based on nonce)
        #   - receiver (TokenMessengerMinter on Solana)
        #   - systemProgram, etc.
        #
        # For now, we use the Circle CCTP SDK pattern via direct RPC calls.
        # A full Anchor CPI build would go here in a production deployment.

        attestation_hex = job.get("attestation", "")
        message_hash = job.get("message_hash", "")

        if not attestation_hex or not message_hash:
            raise RuntimeError(
                "Cannot build receiveMessage without attestation and message_hash"
            )

        # Strip 0x prefix if present
        attestation_bytes = bytes.fromhex(
            attestation_hex[2:] if attestation_hex.startswith("0x") else attestation_hex
        )

        # The actual Solana transaction construction requires:
        # 1. Derive all required PDAs (usedNonces, authorityPda, etc.)
        # 2. Build the instruction with serialized message + attestation
        # 3. Sign with our Solana wallet keypair
        # 4. Submit via sendTransaction RPC
        #
        # This is a placeholder for the full implementation which would use
        # solders.Keypair, solders.Transaction, etc.
        # For production, integrate with the @circlefin/solana-cctp SDK or
        # construct the raw instruction manually.

        session = await self._ensure_http()

        # Build base64-encoded transaction (would be constructed from instruction data)
        # For now, raise a clear error if someone tries to run this without the
        # full Solana transaction builder implemented.
        raise NotImplementedError(
            "Full Solana receiveMessage transaction builder not yet implemented. "
            "Integrate with @circlefin/solana-cctp SDK or build the raw Anchor "
            "instruction with proper PDA derivation. "
            f"Message hash: {message_hash}, Attestation length: {len(attestation_bytes)} bytes"
        )

    async def _submit_solana_spl_transfer(
        self, mint: str, destination: str, amount_raw: int
    ) -> str:
        """Submit an SPL token transfer on Solana via RPC.

        Args:
            mint: The SPL token mint address (e.g. USDC).
            destination: The destination token account address.
            amount_raw: Amount in raw units (e.g. 1_000_000 for 1 USDC).

        Returns:
            Transaction signature string.
        """
        # Similar to receiveMessage, this requires:
        # 1. Derive source ATA from our wallet + mint
        # 2. Build SPL Token transfer instruction
        # 3. Sign with our Solana keypair
        # 4. Submit via sendTransaction RPC
        #
        # Placeholder for full implementation.
        raise NotImplementedError(
            "Full Solana SPL token transfer builder not yet implemented. "
            "Use solders + spl-token to construct the transfer instruction. "
            f"Mint: {mint}, Destination: {destination}, Amount: {amount_raw}"
        )

    # ------------------------------------------------------------------
    # EVM transaction helpers (reused from alvara_manager pattern)
    # ------------------------------------------------------------------

    def _require_wallet(self) -> None:
        """Raise if the management wallet is not loaded."""
        if self.account is None:
            raise RuntimeError(
                "Management wallet not configured — set MANAGEMENT_WALLET_KEY"
            )

    async def _build_and_send_evm(self, contract_fn: Any) -> str:
        """Build an EVM transaction, estimate gas, sign, broadcast, and wait for receipt.

        Returns the transaction hash hex string.
        """
        self._require_wallet()
        assert self.account is not None

        nonce = await self.w3.eth.get_transaction_count(self.account.address)

        # EIP-1559 gas pricing
        latest_block = await self.w3.eth.get_block("latest")
        base_fee = latest_block.get("baseFeePerGas", 0)
        max_priority_fee = await self.w3.eth.max_priority_fee
        max_fee = base_fee * 2 + max_priority_fee

        tx_params: TxParams = {
            "from": self.account.address,
            "nonce": nonce,
            "chainId": BASE_CHAIN_ID,
            "maxFeePerGas": max_fee,
            "maxPriorityFeePerGas": max_priority_fee,
        }

        # Estimate gas with 20% buffer
        try:
            gas_estimate = await contract_fn.estimate_gas(tx_params)
            tx_params["gas"] = int(gas_estimate * 1.2)
        except Exception as exc:
            logger.warning(
                "Gas estimation failed (%s), using 200k default", exc
            )
            tx_params["gas"] = 200_000

        logger.info(
            "EVM TX: gas=%s, maxFee=%.2f gwei, nonce=%d",
            tx_params.get("gas"),
            max_fee / 10**9 if max_fee else 0,
            nonce,
        )

        # Build, sign, send
        built_tx = await contract_fn.build_transaction(tx_params)
        signed = self.account.sign_transaction(built_tx)
        tx_hash = await self.w3.eth.send_raw_transaction(signed.raw_transaction)
        hex_hash = tx_hash.hex()

        # Wait for confirmation (up to 120s)
        try:
            receipt = await self.w3.eth.wait_for_transaction_receipt(
                tx_hash, timeout=120
            )
            if receipt["status"] == 0:
                raise RuntimeError(
                    f"Transaction reverted: {hex_hash} "
                    f"(gasUsed={receipt.get('gasUsed')})"
                )
            logger.info(
                "EVM TX confirmed in block %d (gas used: %s)",
                receipt["blockNumber"],
                receipt.get("gasUsed"),
            )
        except RuntimeError:
            raise
        except Exception as exc:
            logger.warning(
                "Could not confirm tx %s within timeout: %s", hex_hash, exc
            )

        return hex_hash

    # ------------------------------------------------------------------
    # Database helpers
    # ------------------------------------------------------------------

    async def _transition(self, job_id: int, new_state: str, updates: dict) -> None:
        """Persist a state transition to the database and publish event."""
        # Build dynamic SET clause from updates dict
        set_clauses = ["state = $2", "retry_count = 0", "error = NULL", "updated_at = NOW()"]
        params: list[Any] = [job_id, new_state]
        param_idx = 3

        # Map of column names to their values
        column_map: dict[str, Any] = {
            "approve_tx_hash": updates.get("approve_tx_hash"),
            "burn_tx_hash": updates.get("burn_tx_hash"),
            "cctp_nonce": updates.get("cctp_nonce"),
            "message_hash": updates.get("message_hash"),
            "attestation": updates.get("attestation"),
            "mint_tx_hash": updates.get("mint_tx_hash"),
            "deposit_tx_hash": updates.get("deposit_tx_hash"),
            "net_deposited_usdc": updates.get("net_deposited_usdc"),
        }

        for col, val in column_map.items():
            if val is not None:
                set_clauses.append(f"{col} = ${param_idx}")
                params.append(val)
                param_idx += 1

        query = f"UPDATE inv_bridge_jobs SET {', '.join(set_clauses)} WHERE id = $1"
        await self.db.execute(query, *params)

        logger.info("Job #%d: %s -> %s", job_id, "(prev)", new_state)
        await self._publish_event(job_id, new_state, updates)

    async def _fail_job(self, job_id: int, error: str) -> None:
        """Move a job to the terminal FAILED state."""
        await self.db.execute(
            """
            UPDATE inv_bridge_jobs
            SET state = 'FAILED', error = $2, updated_at = NOW()
            WHERE id = $1
            """,
            job_id,
            error,
        )

        logger.error("Job #%d: FAILED — %s", job_id, error)
        await self._publish_event(job_id, "FAILED", {"error": error})

        # Alert via Redis
        await self.redis.publish(
            "telegram:alerts",
            f"BRIDGE FAILED: Job #{job_id} — {error}",
        )

    async def _publish_event(self, job_id: int, state: str, data: dict) -> None:
        """Publish a bridge event to Redis for real-time subscribers."""
        event = {
            "job_id": job_id,
            "state": state,
            "data": data,
            "ts": datetime.now(timezone.utc).isoformat(),
        }
        await self.redis.publish(
            "investments:bridge_events",
            json.dumps(event, default=str),
        )

    # ------------------------------------------------------------------
    # Utility helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _solana_address_to_bytes32(pubkey_str: str) -> bytes:
        """Convert a Solana base58 public key string to a 32-byte CCTP mintRecipient.

        CCTP expects mintRecipient as a bytes32. For Solana, this is the raw
        32-byte public key (not base58 encoded).
        """
        import base58

        decoded = base58.b58decode(pubkey_str)
        if len(decoded) != 32:
            raise ValueError(
                f"Expected 32-byte Solana pubkey, got {len(decoded)} bytes "
                f"from '{pubkey_str}'"
            )
        return decoded
