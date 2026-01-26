"""
Iceberg Order Execution

Implements iceberg order execution that hides the full order size by
executing in smaller visible chunks to minimize market detection.

Usage:
    from core.execution.iceberg import IcebergExecutor

    executor = IcebergExecutor(jupiter_client, wallet)
    result = await executor.execute(order, pool_liquidity=500_000.0)
"""

import asyncio
import logging
import random
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, List, Optional

from .algorithms import (
    Order,
    OrderSide,
    ExecutionChunk,
    ExecutionSchedule,
    ExecutionResult,
)

logger = logging.getLogger(__name__)


class IcebergExecutor:
    """
    Iceberg Order Executor.

    Hides the full order size by showing only a fraction at a time.
    Uses randomization of sizes and delays to avoid detection.

    Best for:
    - Large orders (>1% of pool liquidity)
    - When market impact must be minimized
    - Avoiding front-running detection
    """

    # Default configuration
    DEFAULT_VISIBLE_PCT = 0.10  # Show 10% of order at a time
    DEFAULT_MAX_CHUNK_PCT = 0.01  # Max 1% of pool per chunk
    DEFAULT_DELAY_SECONDS = 60  # 1 minute between chunks

    def __init__(
        self,
        jupiter_client: Any,
        wallet: Any = None,
        randomize_sizes: bool = True,
        randomize_delays: bool = True,
        max_slippage_pct: float = 2.0,
    ):
        """
        Initialize Iceberg executor.

        Args:
            jupiter_client: Jupiter API client
            wallet: Wallet for transaction signing
            randomize_sizes: Add variance to chunk sizes
            randomize_delays: Add variance to delays between chunks
            max_slippage_pct: Maximum slippage before pausing execution
        """
        self.jupiter = jupiter_client
        self.wallet = wallet
        self.randomize_sizes = randomize_sizes
        self.randomize_delays = randomize_delays
        self.max_slippage_pct = max_slippage_pct
        self.cancelled = False
        self._cancel_event = asyncio.Event()

    def create_schedule(
        self,
        order: Order,
        pool_liquidity: float,
        visible_pct: float = None,
        max_chunk_pct: float = None,
        base_delay_seconds: float = None,
    ) -> ExecutionSchedule:
        """
        Create an iceberg execution schedule.

        Args:
            order: The order to execute
            pool_liquidity: Pool liquidity in USD
            visible_pct: Percentage of order to show at a time
            max_chunk_pct: Maximum chunk as percentage of pool
            base_delay_seconds: Base delay between chunks

        Returns:
            ExecutionSchedule with hidden chunks
        """
        visible_pct = visible_pct or self.DEFAULT_VISIBLE_PCT
        max_chunk_pct = max_chunk_pct or self.DEFAULT_MAX_CHUNK_PCT
        base_delay_seconds = base_delay_seconds or self.DEFAULT_DELAY_SECONDS

        if order.size_usd <= 0 or pool_liquidity <= 0:
            return ExecutionSchedule(order=order, algorithm="ICEBERG", chunks=[])

        # Calculate maximum chunk size based on pool
        max_chunk_usd = pool_liquidity * max_chunk_pct

        # Calculate number of chunks needed
        num_chunks = max(1, int(order.size_usd / max_chunk_usd) + 1)

        # Base chunk size
        base_chunk_size = order.size_usd / num_chunks

        chunks = []
        start_time = datetime.utcnow()
        remaining = order.size_usd

        for i in range(num_chunks):
            if remaining <= 0:
                break

            # Calculate chunk size with optional randomization
            if self.randomize_sizes and i < num_chunks - 1:
                # Add up to 20% variance
                variance = base_chunk_size * 0.2
                chunk_size = base_chunk_size + random.uniform(-variance, variance)
                chunk_size = max(1.0, min(chunk_size, remaining))
            else:
                # Last chunk gets remainder
                chunk_size = remaining

            # Calculate delay with optional randomization
            if self.randomize_delays and i > 0:
                # Add up to 50% variance to delay
                delay = base_delay_seconds * (0.75 + random.random() * 0.5)
            else:
                delay = base_delay_seconds if i > 0 else 0

            execute_at = start_time + timedelta(seconds=sum(
                base_delay_seconds for _ in range(i)
            ))

            if self.randomize_delays and i > 0:
                # Recalculate with actual random delays
                total_delay = sum(
                    base_delay_seconds * (0.75 + random.random() * 0.5)
                    for _ in range(i)
                )
                execute_at = start_time + timedelta(seconds=total_delay)

            chunk = ExecutionChunk(
                chunk_index=i,
                size_usd=chunk_size,
                execute_at=execute_at,
            )
            chunks.append(chunk)
            remaining -= chunk_size

        return ExecutionSchedule(
            order=order,
            algorithm="ICEBERG",
            chunks=chunks,
        )

    async def execute(
        self,
        order: Order,
        pool_liquidity: float,
        delay_seconds: float = None,
        max_chunk_pct: float = None,
    ) -> ExecutionResult:
        """
        Execute an iceberg order.

        Args:
            order: The order to execute
            pool_liquidity: Pool liquidity in USD
            delay_seconds: Delay between chunks
            max_chunk_pct: Maximum chunk as percentage of pool

        Returns:
            ExecutionResult with aggregate results
        """
        self.cancelled = False
        self._cancel_event.clear()

        delay_seconds = delay_seconds or self.DEFAULT_DELAY_SECONDS

        schedule = self.create_schedule(
            order,
            pool_liquidity,
            max_chunk_pct=max_chunk_pct,
            base_delay_seconds=delay_seconds,
        )

        if not schedule.chunks:
            return ExecutionResult(
                success=False,
                algorithm="ICEBERG",
                total_size_usd=order.size_usd,
                executed_size_usd=0.0,
                chunks_executed=0,
                chunks_total=0,
                error="No chunks to execute",
            )

        start_time = datetime.utcnow()
        executed_usd = 0.0
        chunks_executed = 0
        chunks_failed = 0
        paused_reason = None
        executed_chunks = []

        for chunk in schedule.chunks:
            if self.cancelled:
                break

            # Wait until execution time
            now = datetime.utcnow()
            if chunk.execute_at > now:
                wait_seconds = (chunk.execute_at - now).total_seconds()
                try:
                    await asyncio.wait_for(
                        self._cancel_event.wait(),
                        timeout=wait_seconds,
                    )
                except asyncio.TimeoutError:
                    pass

            if self.cancelled:
                break

            # Check slippage before execution
            try:
                quote = await self.jupiter.get_quote(
                    input_mint=order.token_mint if order.side == OrderSide.SELL else "So11111111111111111111111111111111111111112",
                    output_mint="So11111111111111111111111111111111111111112" if order.side == OrderSide.SELL else order.token_mint,
                    amount=int(chunk.size_usd * 1_000_000),
                    slippage_bps=order.max_slippage_bps,
                )

                # Check price impact
                price_impact = getattr(quote, 'price_impact_pct', 0.0) or 0.0
                if price_impact > self.max_slippage_pct:
                    logger.warning(
                        f"Iceberg pausing: price impact {price_impact:.2f}% > max {self.max_slippage_pct:.2f}%"
                    )
                    paused_reason = "slippage_exceeded"
                    break

                # Execute chunk
                chunk.status = "executing"
                result = await self.jupiter.execute_swap(quote, self.wallet)

                if result.success:
                    chunk.status = "completed"
                    chunk.actual_size_usd = chunk.size_usd
                    chunk.signature = getattr(result, 'signature', None)
                    executed_usd += chunk.size_usd
                    chunks_executed += 1
                else:
                    chunk.status = "failed"
                    chunk.error = getattr(result, 'error', 'Swap failed')
                    chunks_failed += 1

            except Exception as e:
                chunk.status = "failed"
                chunk.error = str(e)
                chunks_failed += 1
                logger.error(f"Iceberg chunk {chunk.chunk_index} failed: {e}")

            executed_chunks.append(chunk)

        end_time = datetime.utcnow()

        return ExecutionResult(
            success=chunks_executed > 0,
            algorithm="ICEBERG",
            total_size_usd=order.size_usd,
            executed_size_usd=executed_usd,
            chunks_executed=chunks_executed,
            chunks_total=len(schedule.chunks),
            chunks_failed=chunks_failed,
            paused_reason=paused_reason,
            start_time=start_time,
            end_time=end_time,
            chunks=executed_chunks,
        )

    def cancel(self):
        """Cancel the ongoing execution."""
        self.cancelled = True
        self._cancel_event.set()
