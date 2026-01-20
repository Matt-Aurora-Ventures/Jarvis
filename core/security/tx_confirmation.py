"""
Transaction On-Chain Confirmation System for Solana transactions.

Ensures transactions are confirmed on-chain before marking complete,
with retry logic for temporary failures and comprehensive logging.
"""

import asyncio
import logging
import time
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, List, Tuple
import aiohttp
import json
import os

logger = logging.getLogger(__name__)


class TransactionStatus(Enum):
    """Transaction status enumeration."""
    PENDING = "pending"
    CONFIRMED = "confirmed"
    FINALIZED = "finalized"
    FAILED = "failed"
    TIMEOUT = "timeout"
    UNKNOWN = "unknown"


class CommitmentLevel(Enum):
    """Solana commitment levels."""
    PROCESSED = "processed"  # Fastest, least secure
    CONFIRMED = "confirmed"  # Balance of speed/security
    FINALIZED = "finalized"  # Slowest, most secure


@dataclass
class TransactionResult:
    """Result of transaction verification."""
    success: bool
    signature: str
    status: TransactionStatus
    slot: Optional[int] = None
    block_time: Optional[int] = None
    error: Optional[str] = None
    confirmations: int = 0
    retry_count: int = 0
    verification_time_ms: float = 0


@dataclass
class TransactionHistoryEntry:
    """Transaction history log entry."""
    signature: str
    timestamp: datetime
    status: TransactionStatus
    input_mint: str
    output_mint: str
    input_amount: float
    output_amount: float
    slot: Optional[int]
    block_time: Optional[int]
    error: Optional[str]
    retry_count: int
    verification_time_ms: float


class TransactionConfirmationService:
    """
    Verifies Solana transactions on-chain before marking complete.

    Features:
    - On-chain confirmation before success
    - Automatic retry on temporary failures
    - Transaction history logging
    - Alert system for failed transactions
    - Configurable commitment levels
    """

    # Verification timeouts (seconds)
    DEFAULT_TIMEOUT = 60
    PROCESSED_TIMEOUT = 30
    CONFIRMED_TIMEOUT = 60
    FINALIZED_TIMEOUT = 120

    # Retry configuration
    MAX_RETRIES = 5
    RETRY_DELAY = 2.0  # Base delay, uses exponential backoff

    # History file
    HISTORY_FILE = os.path.expanduser("~/.lifeos/trading/transaction_history.json")

    def __init__(
        self,
        rpc_url: str,
        commitment: CommitmentLevel = CommitmentLevel.CONFIRMED,
        alert_callback: Optional[callable] = None
    ):
        """
        Initialize transaction confirmation service.

        Args:
            rpc_url: Solana RPC endpoint
            commitment: Desired commitment level
            alert_callback: Optional callback for failed transactions
        """
        self.rpc_url = rpc_url
        self.commitment = commitment
        self.alert_callback = alert_callback
        self._session: Optional[aiohttp.ClientSession] = None

        # Ensure history directory exists
        os.makedirs(os.path.dirname(self.HISTORY_FILE), exist_ok=True)

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self):
        """Close aiohttp session."""
        if self._session and not self._session.closed:
            await self._session.close()

    async def verify_transaction(
        self,
        signature: str,
        timeout: Optional[int] = None,
        commitment: Optional[CommitmentLevel] = None
    ) -> TransactionResult:
        """
        Verify a transaction is confirmed on-chain.

        Args:
            signature: Transaction signature
            timeout: Custom timeout in seconds
            commitment: Custom commitment level

        Returns:
            TransactionResult with verification details
        """
        start_time = time.time()
        commitment = commitment or self.commitment
        timeout = timeout or self._get_timeout_for_commitment(commitment)

        retry_count = 0
        last_error = None

        for attempt in range(self.MAX_RETRIES):
            try:
                # Check transaction status
                result = await self._check_transaction_status(
                    signature,
                    timeout,
                    commitment
                )

                if result.success or result.status == TransactionStatus.FAILED:
                    # Success or definitive failure - return
                    result.retry_count = retry_count
                    result.verification_time_ms = (time.time() - start_time) * 1000

                    # Alert on failure
                    if not result.success and self.alert_callback:
                        await self.alert_callback(result)

                    return result

                # Temporary failure - retry
                retry_count += 1
                last_error = result.error

                if attempt < self.MAX_RETRIES - 1:
                    delay = self.RETRY_DELAY * (2 ** attempt)
                    logger.warning(
                        f"Transaction verification attempt {attempt + 1} failed: {result.error}. "
                        f"Retrying in {delay}s..."
                    )
                    await asyncio.sleep(delay)

            except Exception as e:
                retry_count += 1
                last_error = str(e)

                if attempt < self.MAX_RETRIES - 1:
                    delay = self.RETRY_DELAY * (2 ** attempt)
                    logger.warning(
                        f"Transaction verification error (attempt {attempt + 1}): {e}. "
                        f"Retrying in {delay}s..."
                    )
                    await asyncio.sleep(delay)

        # All retries exhausted
        result = TransactionResult(
            success=False,
            signature=signature,
            status=TransactionStatus.UNKNOWN,
            error=f"Verification failed after {self.MAX_RETRIES} attempts: {last_error}",
            retry_count=retry_count,
            verification_time_ms=(time.time() - start_time) * 1000
        )

        if self.alert_callback:
            await self.alert_callback(result)

        return result

    async def _check_transaction_status(
        self,
        signature: str,
        timeout: int,
        commitment: CommitmentLevel
    ) -> TransactionResult:
        """
        Check transaction status with timeout.

        Args:
            signature: Transaction signature
            timeout: Timeout in seconds
            commitment: Commitment level

        Returns:
            TransactionResult
        """
        session = await self._get_session()
        start_time = asyncio.get_event_loop().time()

        while True:
            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed >= timeout:
                return TransactionResult(
                    success=False,
                    signature=signature,
                    status=TransactionStatus.TIMEOUT,
                    error=f"Transaction confirmation timeout after {timeout}s"
                )

            try:
                # Get signature status
                async with session.post(self.rpc_url, json={
                    'jsonrpc': '2.0',
                    'id': 1,
                    'method': 'getSignatureStatuses',
                    'params': [[signature], {'searchTransactionHistory': True}]
                }) as resp:
                    data = await resp.json()
                    result = data.get('result', {})
                    statuses = result.get('value', [])

                    if not statuses or not statuses[0]:
                        # Transaction not found yet, keep polling
                        await asyncio.sleep(0.5)
                        continue

                    status = statuses[0]

                    # Check for error
                    if status.get('err'):
                        return TransactionResult(
                            success=False,
                            signature=signature,
                            status=TransactionStatus.FAILED,
                            slot=status.get('slot'),
                            error=f"Transaction failed on-chain: {status['err']}",
                            confirmations=status.get('confirmations', 0)
                        )

                    # Check confirmation level
                    conf_status = status.get('confirmationStatus', '')
                    slot = status.get('slot')
                    confirmations = status.get('confirmations', 0)

                    # Determine if confirmed at desired level
                    is_confirmed = False
                    tx_status = TransactionStatus.PENDING

                    if commitment == CommitmentLevel.PROCESSED and conf_status:
                        is_confirmed = True
                        tx_status = TransactionStatus.CONFIRMED
                    elif commitment == CommitmentLevel.CONFIRMED and conf_status in ['confirmed', 'finalized']:
                        is_confirmed = True
                        tx_status = TransactionStatus.CONFIRMED
                    elif commitment == CommitmentLevel.FINALIZED and conf_status == 'finalized':
                        is_confirmed = True
                        tx_status = TransactionStatus.FINALIZED

                    if is_confirmed:
                        # Get transaction details for block time
                        block_time = await self._get_block_time(signature)

                        return TransactionResult(
                            success=True,
                            signature=signature,
                            status=tx_status,
                            slot=slot,
                            block_time=block_time,
                            confirmations=confirmations
                        )

            except Exception as e:
                logger.warning(f"Error checking transaction status: {e}")

            await asyncio.sleep(0.5)

    async def _get_block_time(self, signature: str) -> Optional[int]:
        """Get block time for a transaction."""
        try:
            session = await self._get_session()
            async with session.post(self.rpc_url, json={
                'jsonrpc': '2.0',
                'id': 1,
                'method': 'getTransaction',
                'params': [signature, {'encoding': 'json'}]
            }) as resp:
                data = await resp.json()
                result = data.get('result', {})
                return result.get('blockTime')
        except Exception as e:
            logger.warning(f"Failed to get block time: {e}")
            return None

    def _get_timeout_for_commitment(self, commitment: CommitmentLevel) -> int:
        """Get appropriate timeout for commitment level."""
        timeouts = {
            CommitmentLevel.PROCESSED: self.PROCESSED_TIMEOUT,
            CommitmentLevel.CONFIRMED: self.CONFIRMED_TIMEOUT,
            CommitmentLevel.FINALIZED: self.FINALIZED_TIMEOUT
        }
        return timeouts.get(commitment, self.DEFAULT_TIMEOUT)

    async def log_transaction(
        self,
        result: TransactionResult,
        input_mint: str,
        output_mint: str,
        input_amount: float,
        output_amount: float
    ):
        """
        Log transaction to history file.

        Args:
            result: TransactionResult from verification
            input_mint: Input token mint
            output_mint: Output token mint
            input_amount: Input token amount
            output_amount: Output token amount
        """
        try:
            entry = TransactionHistoryEntry(
                signature=result.signature,
                timestamp=datetime.utcnow(),
                status=result.status,
                input_mint=input_mint,
                output_mint=output_mint,
                input_amount=input_amount,
                output_amount=output_amount,
                slot=result.slot,
                block_time=result.block_time,
                error=result.error,
                retry_count=result.retry_count,
                verification_time_ms=result.verification_time_ms
            )

            # Load existing history
            history = []
            if os.path.exists(self.HISTORY_FILE):
                with open(self.HISTORY_FILE, 'r') as f:
                    history = json.load(f)

            # Add new entry
            history.append({
                'signature': entry.signature,
                'timestamp': entry.timestamp.isoformat(),
                'status': entry.status.value,
                'input_mint': entry.input_mint,
                'output_mint': entry.output_mint,
                'input_amount': entry.input_amount,
                'output_amount': entry.output_amount,
                'slot': entry.slot,
                'block_time': entry.block_time,
                'error': entry.error,
                'retry_count': entry.retry_count,
                'verification_time_ms': entry.verification_time_ms
            })

            # Keep last 1000 transactions
            history = history[-1000:]

            # Save
            with open(self.HISTORY_FILE, 'w') as f:
                json.dump(history, f, indent=2)

            logger.info(f"Transaction logged: {result.signature[:12]}... ({result.status.value})")

        except Exception as e:
            logger.error(f"Failed to log transaction: {e}")

    async def get_transaction_history(
        self,
        limit: int = 100,
        status_filter: Optional[TransactionStatus] = None
    ) -> List[TransactionHistoryEntry]:
        """
        Get transaction history.

        Args:
            limit: Maximum number of entries to return
            status_filter: Optional filter by status

        Returns:
            List of TransactionHistoryEntry
        """
        try:
            if not os.path.exists(self.HISTORY_FILE):
                return []

            with open(self.HISTORY_FILE, 'r') as f:
                history = json.load(f)

            # Convert to entries
            entries = []
            for item in history:
                entry = TransactionHistoryEntry(
                    signature=item['signature'],
                    timestamp=datetime.fromisoformat(item['timestamp']),
                    status=TransactionStatus(item['status']),
                    input_mint=item['input_mint'],
                    output_mint=item['output_mint'],
                    input_amount=item['input_amount'],
                    output_amount=item['output_amount'],
                    slot=item.get('slot'),
                    block_time=item.get('block_time'),
                    error=item.get('error'),
                    retry_count=item.get('retry_count', 0),
                    verification_time_ms=item.get('verification_time_ms', 0)
                )

                # Apply filter
                if status_filter is None or entry.status == status_filter:
                    entries.append(entry)

            # Return most recent first
            entries.reverse()
            return entries[:limit]

        except Exception as e:
            logger.error(f"Failed to get transaction history: {e}")
            return []

    async def get_failed_transactions(
        self,
        limit: int = 50
    ) -> List[TransactionHistoryEntry]:
        """Get recent failed transactions."""
        return await self.get_transaction_history(
            limit=limit,
            status_filter=TransactionStatus.FAILED
        )


# Singleton instance
_confirmation_service: Optional[TransactionConfirmationService] = None


def get_confirmation_service(
    rpc_url: Optional[str] = None,
    commitment: CommitmentLevel = CommitmentLevel.CONFIRMED
) -> TransactionConfirmationService:
    """Get or create the transaction confirmation service singleton."""
    global _confirmation_service
    if _confirmation_service is None:
        if rpc_url is None:
            raise ValueError("rpc_url required for first initialization")
        _confirmation_service = TransactionConfirmationService(rpc_url, commitment)
    return _confirmation_service
