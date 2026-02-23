"""
TWAP and VWAP Execution Algorithms

Implements Time-Weighted Average Price (TWAP) and Volume-Weighted Average Price (VWAP)
execution strategies to minimize market impact for large orders.

Usage:
    from core.execution.algorithms import ExecutionEngine, Order, OrderSide

    engine = ExecutionEngine(jupiter_client, wallet)
    order = Order(token_mint="...", side=OrderSide.BUY, size_usd=1000.0, urgency="low")
    result = await engine.execute(order, pool_liquidity=500_000.0)
"""

import asyncio
import logging
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# =============================================================================
# Data Structures
# =============================================================================

class OrderSide(Enum):
    """Order side enum."""
    BUY = "BUY"
    SELL = "SELL"


@dataclass
class Order:
    """Represents an order to be executed."""
    token_mint: str
    side: OrderSide
    size_usd: float
    urgency: str = "medium"  # "low", "medium", "high"
    max_slippage_bps: int = 100  # 1% default

    def __post_init__(self):
        if isinstance(self.side, str):
            self.side = OrderSide(self.side)


@dataclass
class ExecutionChunk:
    """A single chunk of an order to be executed."""
    chunk_index: int
    size_usd: float
    execute_at: datetime
    status: str = "pending"  # "pending", "executing", "completed", "failed"
    signature: Optional[str] = None
    error: Optional[str] = None
    actual_size_usd: Optional[float] = None
    price: Optional[float] = None
    slippage_bps: Optional[float] = None


@dataclass
class ExecutionSchedule:
    """Schedule of chunks for algorithm execution."""
    order: Order
    algorithm: str
    chunks: List[ExecutionChunk]
    created_at: datetime = field(default_factory=datetime.utcnow)

    @property
    def total_size(self) -> float:
        return sum(c.size_usd for c in self.chunks)

    @property
    def duration_seconds(self) -> float:
        if len(self.chunks) < 2:
            return 0.0
        return (self.chunks[-1].execute_at - self.chunks[0].execute_at).total_seconds()


@dataclass
class ExecutionResult:
    """Result of an execution."""
    success: bool
    algorithm: str
    total_size_usd: float
    executed_size_usd: float
    chunks_executed: int
    chunks_total: int
    avg_price: float = 0.0
    total_slippage_bps: float = 0.0
    error: Optional[str] = None
    chunks_failed: int = 0
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    paused_reason: Optional[str] = None
    warnings: List[str] = field(default_factory=list)
    chunks: List[ExecutionChunk] = field(default_factory=list)

    @property
    def fill_rate(self) -> float:
        if self.total_size_usd > 0:
            return self.executed_size_usd / self.total_size_usd
        return 0.0

    @property
    def duration_seconds(self) -> float:
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return 0.0


# =============================================================================
# TWAP Executor
# =============================================================================

class TWAPExecutor:
    """
    Time-Weighted Average Price (TWAP) Executor.

    Splits an order evenly across time intervals to minimize market impact.

    Best for:
    - Medium-sized orders
    - Low urgency trades
    - When volume patterns are unpredictable
    """

    def __init__(
        self,
        jupiter_client: Any,
        wallet: Any = None,
        min_chunk_usd: float = 10.0,
        max_chunk_usd: float = 10000.0,
    ):
        self.jupiter = jupiter_client
        self.wallet = wallet
        self.min_chunk_usd = min_chunk_usd
        self.max_chunk_usd = max_chunk_usd
        self.cancelled = False
        self._cancel_event = asyncio.Event()

    def create_schedule(
        self,
        order: Order,
        duration_mins: float,
        intervals: int,
    ) -> ExecutionSchedule:
        """
        Create a TWAP execution schedule.

        Args:
            order: The order to execute
            duration_mins: Total duration in minutes
            intervals: Number of intervals to split across

        Returns:
            ExecutionSchedule with evenly sized chunks
        """
        if order.size_usd <= 0:
            return ExecutionSchedule(order=order, algorithm="TWAP", chunks=[])

        # Adjust intervals based on minimum chunk size
        max_intervals = int(order.size_usd / self.min_chunk_usd)
        if max_intervals < 1:
            max_intervals = 1
        intervals = max(1, min(intervals, max_intervals))

        # Calculate chunk size
        chunk_size = order.size_usd / intervals

        # Calculate interval duration
        interval_seconds = (duration_mins * 60) / intervals

        # Create chunks
        chunks = []
        start_time = datetime.utcnow()

        for i in range(intervals):
            execute_at = start_time + timedelta(seconds=i * interval_seconds)
            chunk = ExecutionChunk(
                chunk_index=i,
                size_usd=chunk_size,
                execute_at=execute_at,
            )
            chunks.append(chunk)

        return ExecutionSchedule(
            order=order,
            algorithm="TWAP",
            chunks=chunks,
        )

    async def execute_chunk(
        self,
        order: Order,
        chunk_size_usd: float,
        slippage_bps: int = 100,
    ) -> ExecutionResult:
        """
        Execute a single chunk of the order.

        Args:
            order: The order being executed
            chunk_size_usd: Size of this chunk in USD
            slippage_bps: Maximum slippage in basis points

        Returns:
            ExecutionResult for this chunk
        """
        try:
            # Get quote
            quote = await self.jupiter.get_quote(
                input_mint=order.token_mint if order.side == OrderSide.SELL else "So11111111111111111111111111111111111111112",
                output_mint="So11111111111111111111111111111111111111112" if order.side == OrderSide.SELL else order.token_mint,
                amount=int(chunk_size_usd * 1_000_000),  # Convert to smallest unit
                slippage_bps=slippage_bps,
            )

            if not quote:
                return ExecutionResult(
                    success=False,
                    algorithm="TWAP",
                    total_size_usd=chunk_size_usd,
                    executed_size_usd=0.0,
                    chunks_executed=0,
                    chunks_total=1,
                    error="Failed to get quote",
                )

            # Execute swap
            result = await self.jupiter.execute_swap(quote, self.wallet)

            if result.success:
                return ExecutionResult(
                    success=True,
                    algorithm="TWAP",
                    total_size_usd=chunk_size_usd,
                    executed_size_usd=chunk_size_usd,
                    chunks_executed=1,
                    chunks_total=1,
                    avg_price=getattr(quote, 'price', 0.0) or 0.0,
                )
            else:
                return ExecutionResult(
                    success=False,
                    algorithm="TWAP",
                    total_size_usd=chunk_size_usd,
                    executed_size_usd=0.0,
                    chunks_executed=0,
                    chunks_total=1,
                    error=result.error if hasattr(result, 'error') else "Swap failed",
                )

        except Exception as e:
            logger.error(f"TWAP chunk execution failed: {e}")
            return ExecutionResult(
                success=False,
                algorithm="TWAP",
                total_size_usd=chunk_size_usd,
                executed_size_usd=0.0,
                chunks_executed=0,
                chunks_total=1,
                error=str(e),
            )

    async def execute(
        self,
        order: Order,
        duration_mins: float,
        intervals: int,
    ) -> ExecutionResult:
        """
        Execute a full TWAP order.

        Args:
            order: The order to execute
            duration_mins: Total duration in minutes
            intervals: Number of intervals

        Returns:
            ExecutionResult with aggregate results
        """
        self.cancelled = False
        self._cancel_event.clear()

        schedule = self.create_schedule(order, duration_mins, intervals)

        if not schedule.chunks:
            return ExecutionResult(
                success=False,
                algorithm="TWAP",
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
        total_price = 0.0
        executed_chunks = []

        for i, chunk in enumerate(schedule.chunks):
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
                    pass  # Normal timeout, proceed with execution

            if self.cancelled:
                break

            # Execute chunk
            chunk.status = "executing"
            result = await self.execute_chunk(order, chunk.size_usd)

            if result.success:
                chunk.status = "completed"
                chunk.actual_size_usd = chunk.size_usd
                chunk.price = result.avg_price
                executed_usd += chunk.size_usd
                chunks_executed += 1
                total_price += result.avg_price if result.avg_price else 0.0
            else:
                chunk.status = "failed"
                chunk.error = result.error
                chunks_failed += 1

            executed_chunks.append(chunk)

        end_time = datetime.utcnow()
        avg_price = total_price / chunks_executed if chunks_executed > 0 else 0.0

        return ExecutionResult(
            success=chunks_executed > 0,
            algorithm="TWAP",
            total_size_usd=order.size_usd,
            executed_size_usd=executed_usd,
            chunks_executed=chunks_executed,
            chunks_total=len(schedule.chunks),
            chunks_failed=chunks_failed,
            avg_price=avg_price,
            start_time=start_time,
            end_time=end_time,
            chunks=executed_chunks,
        )

    def cancel(self):
        """Cancel the ongoing execution."""
        self.cancelled = True
        self._cancel_event.set()


# =============================================================================
# VWAP Executor
# =============================================================================

class VWAPExecutor:
    """
    Volume-Weighted Average Price (VWAP) Executor.

    Splits an order based on historical volume patterns to minimize market impact.

    Best for:
    - Large orders
    - When volume patterns are predictable
    - Tokens with sufficient trading history
    """

    def __init__(
        self,
        jupiter_client: Any,
        wallet: Any = None,
        min_chunk_usd: float = 10.0,
    ):
        self.jupiter = jupiter_client
        self.wallet = wallet
        self.min_chunk_usd = min_chunk_usd
        self.cancelled = False
        self._cancel_event = asyncio.Event()

    def create_schedule(
        self,
        order: Order,
        volume_pattern: List[float],
        intervals: int,
    ) -> ExecutionSchedule:
        """
        Create a VWAP execution schedule based on volume pattern.

        Args:
            order: The order to execute
            volume_pattern: List of volume weights (percentages)
            intervals: Number of intervals

        Returns:
            ExecutionSchedule with volume-weighted chunks
        """
        if order.size_usd <= 0:
            return ExecutionSchedule(order=order, algorithm="VWAP", chunks=[])

        intervals = max(1, intervals)

        # Normalize volume pattern
        pattern = volume_pattern[:intervals] if len(volume_pattern) >= intervals else volume_pattern
        if not pattern:
            pattern = [1.0 / intervals] * intervals

        total_weight = sum(pattern)
        if total_weight <= 0:
            pattern = [1.0 / intervals] * intervals
            total_weight = 1.0

        normalized = [w / total_weight for w in pattern]

        # Create chunks based on weights
        chunks = []
        start_time = datetime.utcnow()

        # Calculate interval duration (spread over next hour by default)
        interval_seconds = 3600 / len(normalized)

        for i, weight in enumerate(normalized):
            chunk_size = order.size_usd * weight
            execute_at = start_time + timedelta(seconds=i * interval_seconds)

            chunk = ExecutionChunk(
                chunk_index=i,
                size_usd=chunk_size,
                execute_at=execute_at,
            )
            chunks.append(chunk)

        return ExecutionSchedule(
            order=order,
            algorithm="VWAP",
            chunks=chunks,
        )

    async def fetch_volume_pattern(self, token_mint: str) -> Optional[List[float]]:
        """
        Fetch historical volume pattern for a token.

        Args:
            token_mint: Token mint address

        Returns:
            List of hourly volume percentages, or None if unavailable
        """
        # This would typically fetch from an external API
        # For now, return None to indicate unavailable
        logger.debug(f"Fetching volume pattern for {token_mint[:8]}...")
        return None

    async def create_schedule_async(
        self,
        order: Order,
        token_mint: str,
        intervals: int,
    ) -> ExecutionSchedule:
        """
        Create a VWAP schedule, fetching volume pattern if needed.

        Args:
            order: The order to execute
            token_mint: Token mint address
            intervals: Number of intervals

        Returns:
            ExecutionSchedule with volume-weighted chunks
        """
        intervals = max(1, intervals)
        pattern = await self.fetch_volume_pattern(token_mint)

        if pattern is None:
            # Fall back to uniform distribution
            logger.info(f"No volume pattern available for {token_mint[:8]}..., using uniform")
            pattern = [1.0 / intervals] * intervals

        return self.create_schedule(order, pattern, intervals)

    async def execute(
        self,
        order: Order,
        volume_pattern: List[float],
        interval_seconds: float = 300,  # 5 minutes default
    ) -> ExecutionResult:
        """
        Execute a full VWAP order.

        Args:
            order: The order to execute
            volume_pattern: List of volume weights
            interval_seconds: Seconds between intervals

        Returns:
            ExecutionResult with aggregate results
        """
        self.cancelled = False
        self._cancel_event.clear()

        schedule = self.create_schedule(order, volume_pattern, len(volume_pattern))

        if not schedule.chunks:
            return ExecutionResult(
                success=False,
                algorithm="VWAP",
                total_size_usd=order.size_usd,
                executed_size_usd=0.0,
                chunks_executed=0,
                chunks_total=0,
                error="No chunks to execute",
            )

        # Adjust timing
        start_time = datetime.utcnow()
        for i, chunk in enumerate(schedule.chunks):
            chunk.execute_at = start_time + timedelta(seconds=i * interval_seconds)

        executed_usd = 0.0
        chunks_executed = 0
        chunks_failed = 0
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

            # Execute chunk
            chunk.status = "executing"
            try:
                quote = await self.jupiter.get_quote(
                    input_mint=order.token_mint if order.side == OrderSide.SELL else "So11111111111111111111111111111111111111112",
                    output_mint="So11111111111111111111111111111111111111112" if order.side == OrderSide.SELL else order.token_mint,
                    amount=int(chunk.size_usd * 1_000_000),
                    slippage_bps=order.max_slippage_bps,
                )

                result = await self.jupiter.execute_swap(quote, self.wallet)

                if result.success:
                    chunk.status = "completed"
                    chunk.actual_size_usd = chunk.size_usd
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

            executed_chunks.append(chunk)

        end_time = datetime.utcnow()

        return ExecutionResult(
            success=chunks_executed > 0,
            algorithm="VWAP",
            total_size_usd=order.size_usd,
            executed_size_usd=executed_usd,
            chunks_executed=chunks_executed,
            chunks_total=len(schedule.chunks),
            chunks_failed=chunks_failed,
            start_time=start_time,
            end_time=end_time,
            chunks=executed_chunks,
        )

    def cancel(self):
        """Cancel the ongoing execution."""
        self.cancelled = True
        self._cancel_event.set()


# =============================================================================
# Execution Engine
# =============================================================================

class ExecutionEngine:
    """
    Main execution engine that selects and runs the appropriate algorithm.

    Automatically selects between:
    - MARKET: Direct execution for small orders
    - TWAP: Time-weighted execution for medium orders
    - VWAP: Volume-weighted execution when patterns are available
    - ICEBERG: Hidden execution for large orders (>1% of pool)

    Usage:
        engine = ExecutionEngine(jupiter_client, wallet)
        result = await engine.execute(order, pool_liquidity=500_000.0)
    """

    # Thresholds for algorithm selection
    MARKET_THRESHOLD_PCT = 0.001  # 0.1% of pool - use market order
    TWAP_THRESHOLD_PCT = 0.01    # 1% of pool - use TWAP
    # Above TWAP_THRESHOLD_PCT - use ICEBERG

    def __init__(
        self,
        jupiter_client: Any,
        wallet: Any = None,
    ):
        self.jupiter = jupiter_client
        self.wallet = wallet
        self.twap_executor = TWAPExecutor(jupiter_client, wallet)
        self.vwap_executor = VWAPExecutor(jupiter_client, wallet)
        self._iceberg_executor = None  # Lazy load

    @property
    def iceberg_executor(self):
        """Lazy load iceberg executor."""
        if self._iceberg_executor is None:
            from .iceberg import IcebergExecutor
            self._iceberg_executor = IcebergExecutor(self.jupiter, wallet=self.wallet)
        return self._iceberg_executor

    def select_algorithm(
        self,
        order: Order,
        pool_liquidity: float,
    ) -> str:
        """
        Select the appropriate algorithm based on order size and urgency.

        Args:
            order: The order to execute
            pool_liquidity: Pool liquidity in USD

        Returns:
            Algorithm name: "MARKET", "TWAP", "VWAP", or "ICEBERG"
        """
        if order.size_usd <= 0:
            return "MARKET"

        if pool_liquidity <= 0:
            return "MARKET"

        impact = order.size_usd / pool_liquidity

        if impact <= self.MARKET_THRESHOLD_PCT:
            return "MARKET"

        if order.urgency == "high":
            return "MARKET"

        if impact > self.TWAP_THRESHOLD_PCT:
            return "ICEBERG"

        return "TWAP"

    def calculate_priority_fee(self, order: Order) -> int:
        """
        Calculate priority fee based on urgency.

        Args:
            order: The order

        Returns:
            Priority fee in microlamports
        """
        base_fee = 10000  # 10k microlamports

        if order.urgency == "high":
            return base_fee * 5  # 50k
        elif order.urgency == "low":
            return base_fee  # 10k
        else:
            return base_fee * 2  # 20k (medium)

    async def execute_market(
        self,
        order: Order,
    ) -> ExecutionResult:
        """Execute a market order directly."""
        start_time = datetime.utcnow()

        if order.size_usd <= 0:
            return ExecutionResult(
                success=False,
                algorithm="MARKET",
                total_size_usd=order.size_usd,
                executed_size_usd=0.0,
                chunks_executed=0,
                chunks_total=1,
                error="Invalid order size: zero or negative",
                start_time=start_time,
                end_time=datetime.utcnow(),
            )

        try:
            quote = await self.jupiter.get_quote(
                input_mint=order.token_mint if order.side == OrderSide.SELL else "So11111111111111111111111111111111111111112",
                output_mint="So11111111111111111111111111111111111111112" if order.side == OrderSide.SELL else order.token_mint,
                amount=int(order.size_usd * 1_000_000),
                slippage_bps=order.max_slippage_bps,
            )

            if not quote:
                return ExecutionResult(
                    success=False,
                    algorithm="MARKET",
                    total_size_usd=order.size_usd,
                    executed_size_usd=0.0,
                    chunks_executed=0,
                    chunks_total=1,
                    error="Failed to get quote",
                    start_time=start_time,
                    end_time=datetime.utcnow(),
                )

            result = await self.jupiter.execute_swap(quote, self.wallet)

            end_time = datetime.utcnow()

            if result.success:
                return ExecutionResult(
                    success=True,
                    algorithm="MARKET",
                    total_size_usd=order.size_usd,
                    executed_size_usd=order.size_usd,
                    chunks_executed=1,
                    chunks_total=1,
                    start_time=start_time,
                    end_time=end_time,
                )
            else:
                return ExecutionResult(
                    success=False,
                    algorithm="MARKET",
                    total_size_usd=order.size_usd,
                    executed_size_usd=0.0,
                    chunks_executed=0,
                    chunks_total=1,
                    error=getattr(result, 'error', 'Swap failed'),
                    start_time=start_time,
                    end_time=end_time,
                )

        except Exception as e:
            return ExecutionResult(
                success=False,
                algorithm="MARKET",
                total_size_usd=order.size_usd,
                executed_size_usd=0.0,
                chunks_executed=0,
                chunks_total=1,
                error=str(e),
                start_time=start_time,
                end_time=datetime.utcnow(),
            )

    async def execute(
        self,
        order: Order,
        pool_liquidity: float,
        force_algorithm: Optional[str] = None,
        duration_mins: float = 30.0,
        intervals: int = 10,
    ) -> ExecutionResult:
        """
        Execute an order using the appropriate algorithm.

        Args:
            order: The order to execute
            pool_liquidity: Pool liquidity in USD
            force_algorithm: Force a specific algorithm
            duration_mins: Duration for TWAP execution
            intervals: Number of intervals for TWAP/VWAP

        Returns:
            ExecutionResult
        """
        # Validate order
        if order.size_usd <= 0:
            return ExecutionResult(
                success=False,
                algorithm="NONE",
                total_size_usd=order.size_usd,
                executed_size_usd=0.0,
                chunks_executed=0,
                chunks_total=0,
                error="Invalid order size: zero or negative",
            )

        intervals = max(1, intervals)

        # Check pool liquidity
        warnings = []
        if pool_liquidity <= 0:
            warnings.append("Pool liquidity is zero or unavailable")

        # Select algorithm
        algorithm = force_algorithm or self.select_algorithm(order, pool_liquidity)

        logger.info(f"Executing order with {algorithm} algorithm: ${order.size_usd:.2f}")

        if algorithm == "MARKET":
            result = await self.execute_market(order)
        elif algorithm == "TWAP":
            result = await self.twap_executor.execute(order, duration_mins, intervals)
        elif algorithm == "VWAP":
            # Use uniform pattern if no specific pattern provided
            pattern = [1.0 / intervals] * intervals
            result = await self.vwap_executor.execute(order, pattern, duration_mins * 60 / intervals)
        elif algorithm == "ICEBERG":
            result = await self.iceberg_executor.execute(
                order,
                pool_liquidity,
                delay_seconds=duration_mins * 60 / intervals,
            )
        else:
            return ExecutionResult(
                success=False,
                algorithm=algorithm,
                total_size_usd=order.size_usd,
                executed_size_usd=0.0,
                chunks_executed=0,
                chunks_total=0,
                error=f"Unknown algorithm: {algorithm}",
            )

        result.warnings = warnings
        return result
