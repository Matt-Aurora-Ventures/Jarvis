"""
Smart transaction retry logic for Solana.

Implements intelligent blockhash refresh timing and exponential backoff
for maximum transaction success rate.

References:
- Solana RPC: https://solana.com/docs/rpc
"""

import asyncio
import logging
import random
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional

from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Confirmed
from solana.rpc.types import TxOpts
from solders.transaction import Transaction
from solders.signature import Signature


logger = logging.getLogger(__name__)


class ErrorType(Enum):
    """Classification of Solana transaction errors."""
    RETRYABLE = "retryable"
    NON_RETRYABLE = "non_retryable"
    UNKNOWN = "unknown"


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""
    max_retries: int = 3
    base_delay_ms: int = 1000
    max_delay_ms: int = 8000
    jitter_factor: float = 0.1
    blockhash_valid_percentage: float = 0.75


@dataclass
class RetryStats:
    """Statistics for retry attempts."""
    total_attempts: int = 0
    successful_attempts: int = 0
    failed_attempts: int = 0
    retryable_errors: int = 0
    non_retryable_errors: int = 0
    blockhash_refreshes: int = 0


@dataclass
class BlockhashCache:
    """Cache for recent blockhashes with expiry tracking."""
    blockhash: str
    last_valid_block_height: int
    fetched_at: datetime = field(default_factory=datetime.utcnow)

    def is_valid(self, current_block_height: int, valid_percentage: float = 0.75) -> bool:
        if current_block_height >= self.last_valid_block_height:
            return False
        blocks_remaining = self.last_valid_block_height - current_block_height
        min_blocks_required = int(150 * valid_percentage)
        return blocks_remaining >= min_blocks_required


class TransactionRetryManager:
    """Manages intelligent transaction retries with blockhash refresh."""

    def __init__(self, rpc_client: AsyncClient, config: Optional[RetryConfig] = None):
        self.rpc_client = rpc_client
        self.config = config or RetryConfig()
        self.blockhash_cache: Optional[BlockhashCache] = None
        self.stats = RetryStats()

    def classify_error(self, error: Exception) -> ErrorType:
        error_msg = str(error).lower()
        retryable = ["blockhash", "timeout", "connection", "rpc", "try again"]
        non_retryable = ["insufficient funds", "invalid signature", "account not found"]
        
        for pattern in retryable:
            if pattern in error_msg:
                return ErrorType.RETRYABLE
        for pattern in non_retryable:
            if pattern in error_msg:
                return ErrorType.NON_RETRYABLE
        return ErrorType.UNKNOWN

    async def get_fresh_blockhash(self, force_refresh: bool = False) -> tuple[str, int]:
        if not force_refresh and self.blockhash_cache:
            try:
                slot_resp = await self.rpc_client.get_slot(commitment=Confirmed)
                current_height = slot_resp.value if slot_resp.value else 0
                if self.blockhash_cache.is_valid(current_height, self.config.blockhash_valid_percentage):
                    return (self.blockhash_cache.blockhash, self.blockhash_cache.last_valid_block_height)
            except Exception:
                pass

        resp = await self.rpc_client.get_latest_blockhash(commitment=Confirmed)
        if not resp.value:
            raise ValueError("Failed to fetch blockhash")

        self.blockhash_cache = BlockhashCache(
            blockhash=str(resp.value.blockhash),
            last_valid_block_height=resp.value.last_valid_block_height
        )
        self.stats.blockhash_refreshes += 1
        return (self.blockhash_cache.blockhash, self.blockhash_cache.last_valid_block_height)

    def calculate_delay(self, attempt: int) -> float:
        if attempt == 0:
            return 0.0
        delay_ms = min(self.config.base_delay_ms * (2 ** (attempt - 1)), self.config.max_delay_ms)
        jitter = delay_ms * self.config.jitter_factor * (random.random() * 2 - 1)
        return max(0.0, (delay_ms + jitter) / 1000.0)

    async def send_transaction_with_retry(self, transaction: Transaction, opts: Optional[TxOpts] = None) -> Signature:
        if opts is None:
            opts = TxOpts(skip_preflight=False, preflight_commitment=Confirmed)

        start_time = time.time()
        last_error = None

        for attempt in range(self.config.max_retries + 1):
            self.stats.total_attempts += 1
            try:
                if attempt > 0:
                    await self.get_fresh_blockhash(force_refresh=True)

                resp = await self.rpc_client.send_transaction(transaction, opts)
                if resp.value:
                    self.stats.successful_attempts += 1
                    return resp.value
                raise ValueError("Transaction failed with no signature")

            except Exception as e:
                last_error = e
                error_type = self.classify_error(e)

                if error_type == ErrorType.RETRYABLE:
                    self.stats.retryable_errors += 1
                    if attempt < self.config.max_retries:
                        await asyncio.sleep(self.calculate_delay(attempt))
                        continue
                elif error_type == ErrorType.NON_RETRYABLE:
                    self.stats.non_retryable_errors += 1
                    break
                else:
                    if attempt < self.config.max_retries:
                        await asyncio.sleep(self.calculate_delay(attempt))
                        continue

        self.stats.failed_attempts += 1
        raise last_error if last_error else Exception("Transaction failed")

    def get_stats(self) -> RetryStats:
        return self.stats


async def send_transaction_with_retry(rpc_client: AsyncClient, transaction: Transaction, 
                                      opts: Optional[TxOpts] = None, max_retries: int = 3) -> Signature:
    manager = TransactionRetryManager(rpc_client, RetryConfig(max_retries=max_retries))
    return await manager.send_transaction_with_retry(transaction, opts)
