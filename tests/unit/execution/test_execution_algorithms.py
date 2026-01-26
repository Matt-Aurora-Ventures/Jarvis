"""
Comprehensive unit tests for TWAP/VWAP/Iceberg Execution Algorithms.

Tests cover:
1. TWAP (Time-Weighted Average Price) - splits orders over time intervals
2. VWAP (Volume-Weighted Average Price) - splits based on volume patterns
3. Iceberg Orders - hides full size, shows chunks
4. Liquidity Analyzer - determines which algorithm to use
5. ExecutionEngine - automatic algorithm selection
6. Integration with Jupiter API

Following TDD: tests written first, then implementation.
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from unittest.mock import AsyncMock, MagicMock, patch
from dataclasses import dataclass
import sys
from pathlib import Path

# Ensure project root is in path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))


# =============================================================================
# Test Data and Fixtures
# =============================================================================

SOL_MINT = "So11111111111111111111111111111111111111112"
USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
BONK_MINT = "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263"


@pytest.fixture
def mock_jupiter():
    """Create a mock Jupiter client for testing."""
    jupiter = AsyncMock()
    jupiter.get_quote = AsyncMock(return_value=MagicMock(
        input_mint=SOL_MINT,
        output_mint=BONK_MINT,
        input_amount=1_000_000_000,
        output_amount=100_000_000_000,
        input_amount_ui=1.0,
        output_amount_ui=100.0,
        price_impact_pct=0.1,
        slippage_bps=50,
        quote_response={}
    ))
    jupiter.execute_swap = AsyncMock(return_value=MagicMock(
        success=True,
        signature="tx_sig_12345"
    ))
    jupiter.get_token_price = AsyncMock(return_value=100.0)
    return jupiter


@pytest.fixture
def mock_wallet():
    """Create a mock wallet for testing."""
    wallet = MagicMock()
    wallet.get_balance = AsyncMock(return_value=(10.0, 1000.0))
    wallet.sign_transaction = MagicMock(return_value=b"signed_tx")
    return wallet


@pytest.fixture
def sample_order():
    """Create a sample order for testing."""
    from core.execution.algorithms import Order, OrderSide
    return Order(
        token_mint=BONK_MINT,
        side=OrderSide.BUY,
        size_usd=1000.0,
        urgency="low",
        max_slippage_bps=100,
    )


@pytest.fixture
def large_order():
    """Create a large order that exceeds 1% of pool liquidity."""
    from core.execution.algorithms import Order, OrderSide
    return Order(
        token_mint=BONK_MINT,
        side=OrderSide.BUY,
        size_usd=50000.0,  # Large order
        urgency="low",
        max_slippage_bps=100,
    )


@pytest.fixture
def mock_pool_data():
    """Create mock pool/liquidity data."""
    return {
        "liquidity_usd": 500_000.0,  # $500k pool
        "volume_24h": 1_000_000.0,   # $1M daily volume
        "volume_pattern": [0.02, 0.03, 0.05, 0.08, 0.10, 0.12,
                          0.10, 0.08, 0.07, 0.06, 0.05, 0.04],  # Hourly % of daily volume
    }


# =============================================================================
# Test Order Data Structures
# =============================================================================

class TestOrderDataStructures:
    """Tests for Order and related data structures."""

    def test_order_creation(self):
        """Test creating an Order with required fields."""
        from core.execution.algorithms import Order, OrderSide

        order = Order(
            token_mint=BONK_MINT,
            side=OrderSide.BUY,
            size_usd=100.0,
            urgency="low",
        )

        assert order.token_mint == BONK_MINT
        assert order.side == OrderSide.BUY
        assert order.size_usd == 100.0
        assert order.urgency == "low"

    def test_order_side_enum(self):
        """Test OrderSide enum values."""
        from core.execution.algorithms import OrderSide

        assert OrderSide.BUY.value == "BUY"
        assert OrderSide.SELL.value == "SELL"

    def test_execution_chunk_creation(self):
        """Test ExecutionChunk data structure."""
        from core.execution.algorithms import ExecutionChunk

        chunk = ExecutionChunk(
            chunk_index=0,
            size_usd=100.0,
            execute_at=datetime.now(),
            status="pending",
        )

        assert chunk.chunk_index == 0
        assert chunk.size_usd == 100.0
        assert chunk.status == "pending"

    def test_execution_result_creation(self):
        """Test ExecutionResult data structure."""
        from core.execution.algorithms import ExecutionResult

        result = ExecutionResult(
            success=True,
            algorithm="TWAP",
            total_size_usd=1000.0,
            executed_size_usd=1000.0,
            chunks_executed=10,
            chunks_total=10,
            avg_price=100.0,
            total_slippage_bps=15,
        )

        assert result.success is True
        assert result.algorithm == "TWAP"
        assert result.fill_rate == 1.0


# =============================================================================
# Test TWAP Algorithm
# =============================================================================

class TestTWAPAlgorithm:
    """Tests for Time-Weighted Average Price algorithm."""

    @pytest.mark.asyncio
    async def test_twap_splits_order_evenly(self, mock_jupiter, sample_order):
        """Test that TWAP splits orders evenly across time intervals."""
        from core.execution.algorithms import TWAPExecutor

        executor = TWAPExecutor(mock_jupiter)

        schedule = executor.create_schedule(
            order=sample_order,
            duration_mins=30,
            intervals=10,
        )

        assert len(schedule.chunks) == 10
        # Each chunk should be ~100 USD (1000 / 10)
        for chunk in schedule.chunks:
            assert abs(chunk.size_usd - 100.0) < 0.01

    @pytest.mark.asyncio
    async def test_twap_spacing_between_chunks(self, mock_jupiter, sample_order):
        """Test that TWAP spaces chunks evenly over duration."""
        from core.execution.algorithms import TWAPExecutor

        executor = TWAPExecutor(mock_jupiter)

        schedule = executor.create_schedule(
            order=sample_order,
            duration_mins=30,
            intervals=6,
        )

        # 30 mins / 6 intervals = 5 min spacing
        for i in range(1, len(schedule.chunks)):
            time_diff = (schedule.chunks[i].execute_at -
                        schedule.chunks[i-1].execute_at).total_seconds()
            assert abs(time_diff - 300) < 1  # 5 minutes = 300 seconds

    @pytest.mark.asyncio
    async def test_twap_execute_single_chunk(self, mock_jupiter, mock_wallet, sample_order):
        """Test executing a single TWAP chunk."""
        from core.execution.algorithms import TWAPExecutor

        executor = TWAPExecutor(mock_jupiter, wallet=mock_wallet)

        result = await executor.execute_chunk(
            order=sample_order,
            chunk_size_usd=100.0,
        )

        assert result.success is True
        mock_jupiter.get_quote.assert_called_once()
        mock_jupiter.execute_swap.assert_called_once()

    @pytest.mark.asyncio
    async def test_twap_full_execution(self, mock_jupiter, mock_wallet, sample_order):
        """Test full TWAP execution with multiple chunks."""
        from core.execution.algorithms import TWAPExecutor

        executor = TWAPExecutor(mock_jupiter, wallet=mock_wallet)

        # Use short interval for testing (0.1 seconds between chunks)
        result = await executor.execute(
            order=sample_order,
            duration_mins=0.01,  # Very short for testing
            intervals=3,
        )

        assert result.success is True
        assert result.algorithm == "TWAP"
        assert result.chunks_executed == 3
        assert mock_jupiter.execute_swap.call_count == 3

    @pytest.mark.asyncio
    async def test_twap_handles_chunk_failure(self, mock_jupiter, mock_wallet, sample_order):
        """Test that TWAP handles individual chunk failures gracefully."""
        from core.execution.algorithms import TWAPExecutor

        # Make second execution fail
        mock_jupiter.execute_swap = AsyncMock(side_effect=[
            MagicMock(success=True, signature="tx1"),
            MagicMock(success=False, error="Slippage exceeded"),
            MagicMock(success=True, signature="tx3"),
        ])

        executor = TWAPExecutor(mock_jupiter, wallet=mock_wallet)

        result = await executor.execute(
            order=sample_order,
            duration_mins=0.01,
            intervals=3,
        )

        # Should still complete with partial success
        assert result.chunks_executed == 2
        assert result.chunks_failed == 1

    @pytest.mark.asyncio
    async def test_twap_respects_minimum_chunk_size(self, mock_jupiter, sample_order):
        """Test that TWAP doesn't create chunks smaller than minimum."""
        from core.execution.algorithms import TWAPExecutor

        executor = TWAPExecutor(mock_jupiter, min_chunk_usd=50.0)

        # Order of $100 with 10 intervals would be $10 chunks
        # But min is $50, so should only create 2 chunks
        small_order = sample_order
        small_order.size_usd = 100.0

        schedule = executor.create_schedule(
            order=small_order,
            duration_mins=10,
            intervals=10,
        )

        assert len(schedule.chunks) == 2  # $50 each
        for chunk in schedule.chunks:
            assert chunk.size_usd >= 50.0


# =============================================================================
# Test VWAP Algorithm
# =============================================================================

class TestVWAPAlgorithm:
    """Tests for Volume-Weighted Average Price algorithm."""

    @pytest.mark.asyncio
    async def test_vwap_weights_by_volume(self, mock_jupiter, sample_order, mock_pool_data):
        """Test that VWAP weights chunks by historical volume."""
        from core.execution.algorithms import VWAPExecutor

        executor = VWAPExecutor(mock_jupiter)

        schedule = executor.create_schedule(
            order=sample_order,
            volume_pattern=mock_pool_data["volume_pattern"],
            intervals=12,
        )

        # Higher volume hours should have larger chunks
        # Pattern shows hour 5-6 has highest volume (0.10-0.12)
        chunks_by_size = sorted(schedule.chunks, key=lambda c: c.size_usd, reverse=True)

        # Largest chunks should correspond to high-volume periods
        assert chunks_by_size[0].size_usd > chunks_by_size[-1].size_usd

    @pytest.mark.asyncio
    async def test_vwap_total_equals_order_size(self, mock_jupiter, sample_order, mock_pool_data):
        """Test that VWAP chunk sizes sum to total order size."""
        from core.execution.algorithms import VWAPExecutor

        executor = VWAPExecutor(mock_jupiter)

        schedule = executor.create_schedule(
            order=sample_order,
            volume_pattern=mock_pool_data["volume_pattern"],
            intervals=12,
        )

        total = sum(chunk.size_usd for chunk in schedule.chunks)
        assert abs(total - sample_order.size_usd) < 0.01

    @pytest.mark.asyncio
    async def test_vwap_fetches_volume_pattern(self, mock_jupiter, sample_order):
        """Test that VWAP can fetch volume pattern from external source."""
        from core.execution.algorithms import VWAPExecutor

        executor = VWAPExecutor(mock_jupiter)

        # Mock the volume pattern fetcher
        executor.fetch_volume_pattern = AsyncMock(return_value=[
            0.05, 0.08, 0.10, 0.12, 0.15, 0.12,
            0.10, 0.08, 0.07, 0.06, 0.04, 0.03
        ])

        schedule = await executor.create_schedule_async(
            order=sample_order,
            token_mint=BONK_MINT,
            intervals=12,
        )

        executor.fetch_volume_pattern.assert_called_once_with(BONK_MINT)
        assert len(schedule.chunks) == 12

    @pytest.mark.asyncio
    async def test_vwap_full_execution(self, mock_jupiter, mock_wallet, sample_order, mock_pool_data):
        """Test full VWAP execution."""
        from core.execution.algorithms import VWAPExecutor

        executor = VWAPExecutor(mock_jupiter, wallet=mock_wallet)

        result = await executor.execute(
            order=sample_order,
            volume_pattern=mock_pool_data["volume_pattern"],
            interval_seconds=0.01,  # Very short for testing
        )

        assert result.success is True
        assert result.algorithm == "VWAP"

    @pytest.mark.asyncio
    async def test_vwap_uses_default_pattern_if_unavailable(self, mock_jupiter, sample_order):
        """Test VWAP uses uniform distribution if pattern unavailable."""
        from core.execution.algorithms import VWAPExecutor

        executor = VWAPExecutor(mock_jupiter)
        executor.fetch_volume_pattern = AsyncMock(return_value=None)

        schedule = await executor.create_schedule_async(
            order=sample_order,
            token_mint=BONK_MINT,
            intervals=4,
        )

        # Should fall back to uniform distribution
        for chunk in schedule.chunks:
            assert abs(chunk.size_usd - 250.0) < 0.01  # 1000/4


# =============================================================================
# Test Iceberg Orders
# =============================================================================

class TestIcebergOrders:
    """Tests for Iceberg order execution."""

    @pytest.mark.asyncio
    async def test_iceberg_hides_full_size(self, mock_jupiter, large_order, mock_pool_data):
        """Test that iceberg orders hide the full order size."""
        from core.execution.iceberg import IcebergExecutor

        executor = IcebergExecutor(mock_jupiter)

        schedule = executor.create_schedule(
            order=large_order,
            pool_liquidity=mock_pool_data["liquidity_usd"],
            visible_pct=0.10,  # Show only 10% at a time
        )

        # Each visible chunk should be <= 10% of pool liquidity
        max_visible = mock_pool_data["liquidity_usd"] * 0.10
        for chunk in schedule.chunks:
            assert chunk.size_usd <= max_visible

    @pytest.mark.asyncio
    async def test_iceberg_adjusts_chunk_count(self, mock_jupiter, mock_pool_data):
        """Test that iceberg creates correct number of chunks."""
        from core.execution.iceberg import IcebergExecutor
        from core.execution.algorithms import Order, OrderSide

        # Order is 10% of pool liquidity
        order = Order(
            token_mint=BONK_MINT,
            side=OrderSide.BUY,
            size_usd=50000.0,
            urgency="low",
        )

        executor = IcebergExecutor(mock_jupiter)

        schedule = executor.create_schedule(
            order=order,
            pool_liquidity=mock_pool_data["liquidity_usd"],  # 500k
            max_chunk_pct=0.01,  # 1% of pool per chunk
        )

        # Should need at least 10 chunks (50k / (500k * 0.01) = 10)
        assert len(schedule.chunks) >= 10

    @pytest.mark.asyncio
    async def test_iceberg_random_chunk_sizes(self, mock_jupiter, large_order, mock_pool_data):
        """Test that iceberg uses randomized chunk sizes to avoid detection."""
        from core.execution.iceberg import IcebergExecutor

        executor = IcebergExecutor(mock_jupiter, randomize_sizes=True)

        schedule = executor.create_schedule(
            order=large_order,
            pool_liquidity=mock_pool_data["liquidity_usd"],
        )

        # Chunks should have some variance (not all identical)
        sizes = [c.size_usd for c in schedule.chunks]
        if len(sizes) > 1:
            variance = max(sizes) - min(sizes)
            assert variance > 0  # Some randomization

    @pytest.mark.asyncio
    async def test_iceberg_random_delays(self, mock_jupiter, large_order, mock_pool_data):
        """Test that iceberg uses randomized delays between chunks."""
        from core.execution.iceberg import IcebergExecutor

        executor = IcebergExecutor(mock_jupiter, randomize_delays=True)

        schedule = executor.create_schedule(
            order=large_order,
            pool_liquidity=mock_pool_data["liquidity_usd"],
            base_delay_seconds=60,
        )

        # Delays should vary
        delays = []
        for i in range(1, len(schedule.chunks)):
            delay = (schedule.chunks[i].execute_at -
                    schedule.chunks[i-1].execute_at).total_seconds()
            delays.append(delay)

        if len(delays) > 1:
            variance = max(delays) - min(delays)
            assert variance > 0

    @pytest.mark.asyncio
    async def test_iceberg_full_execution(self, mock_jupiter, mock_wallet, large_order, mock_pool_data):
        """Test full iceberg order execution."""
        from core.execution.iceberg import IcebergExecutor

        executor = IcebergExecutor(mock_jupiter, wallet=mock_wallet)

        result = await executor.execute(
            order=large_order,
            pool_liquidity=mock_pool_data["liquidity_usd"],
            delay_seconds=0.01,  # Very short for testing
        )

        assert result.success is True
        assert result.algorithm == "ICEBERG"
        assert result.chunks_executed > 1

    @pytest.mark.asyncio
    async def test_iceberg_stops_on_high_slippage(self, mock_jupiter, mock_wallet, large_order, mock_pool_data):
        """Test that iceberg stops execution if slippage is too high."""
        from core.execution.iceberg import IcebergExecutor

        # Mock high slippage after a few executions
        mock_jupiter.get_quote = AsyncMock(side_effect=[
            MagicMock(price_impact_pct=0.5),
            MagicMock(price_impact_pct=0.8),
            MagicMock(price_impact_pct=5.0),  # High slippage
        ])

        executor = IcebergExecutor(mock_jupiter, wallet=mock_wallet, max_slippage_pct=2.0)

        result = await executor.execute(
            order=large_order,
            pool_liquidity=mock_pool_data["liquidity_usd"],
            delay_seconds=0.01,
        )

        # Should pause/stop due to high slippage
        assert result.paused_reason == "slippage_exceeded" or result.chunks_executed < result.chunks_total


# =============================================================================
# Test Liquidity Analyzer
# =============================================================================

class TestLiquidityAnalyzer:
    """Tests for liquidity depth analysis."""

    @pytest.mark.asyncio
    async def test_analyzer_fetches_pool_liquidity(self, mock_jupiter):
        """Test that analyzer fetches pool liquidity correctly."""
        from core.execution.liquidity_analyzer import LiquidityAnalyzer

        analyzer = LiquidityAnalyzer(mock_jupiter)

        # Mock the liquidity fetch
        analyzer._fetch_pool_liquidity = AsyncMock(return_value=500_000.0)

        liquidity = await analyzer.get_pool_liquidity(BONK_MINT)

        assert liquidity == 500_000.0

    @pytest.mark.asyncio
    async def test_analyzer_calculates_order_impact(self, mock_jupiter):
        """Test calculating order impact on pool."""
        from core.execution.liquidity_analyzer import LiquidityAnalyzer

        analyzer = LiquidityAnalyzer(mock_jupiter)

        impact = analyzer.calculate_impact(
            order_size_usd=5000.0,
            pool_liquidity_usd=500_000.0,
        )

        assert impact == 0.01  # 1% of pool

    @pytest.mark.asyncio
    async def test_analyzer_recommends_algorithm(self, mock_jupiter):
        """Test algorithm recommendation based on liquidity."""
        from core.execution.liquidity_analyzer import LiquidityAnalyzer

        analyzer = LiquidityAnalyzer(mock_jupiter)

        # Small order: direct market order
        rec = analyzer.recommend_algorithm(
            order_size_usd=100.0,
            pool_liquidity_usd=500_000.0,
            urgency="high",
        )
        assert rec.algorithm == "MARKET"

        # Medium order, low urgency: TWAP
        rec = analyzer.recommend_algorithm(
            order_size_usd=1000.0,
            pool_liquidity_usd=500_000.0,
            urgency="low",
        )
        assert rec.algorithm == "TWAP"

        # Large order (>1% of pool): Iceberg
        rec = analyzer.recommend_algorithm(
            order_size_usd=10000.0,  # 2% of pool
            pool_liquidity_usd=500_000.0,
            urgency="low",
        )
        assert rec.algorithm == "ICEBERG"

    @pytest.mark.asyncio
    async def test_analyzer_vwap_for_predictable_volume(self, mock_jupiter):
        """Test VWAP recommendation when volume pattern is predictable."""
        from core.execution.liquidity_analyzer import LiquidityAnalyzer

        analyzer = LiquidityAnalyzer(mock_jupiter)

        # Mock high volume predictability
        analyzer.get_volume_predictability = AsyncMock(return_value=0.8)

        rec = await analyzer.recommend_algorithm_async(
            order_size_usd=5000.0,
            pool_liquidity_usd=500_000.0,
            token_mint=BONK_MINT,
            urgency="low",
        )

        assert rec.algorithm == "VWAP"

    @pytest.mark.asyncio
    async def test_analyzer_considers_24h_volume(self, mock_jupiter):
        """Test that analyzer considers 24h volume in recommendations."""
        from core.execution.liquidity_analyzer import LiquidityAnalyzer

        analyzer = LiquidityAnalyzer(mock_jupiter)

        # Order is 10% of daily volume - needs splitting
        rec = analyzer.recommend_algorithm(
            order_size_usd=100_000.0,
            pool_liquidity_usd=500_000.0,
            volume_24h=1_000_000.0,
            urgency="medium",
        )

        # Should recommend splitting
        assert rec.algorithm in ["TWAP", "VWAP", "ICEBERG"]
        assert rec.estimated_duration_mins > 0


# =============================================================================
# Test Execution Engine
# =============================================================================

class TestExecutionEngine:
    """Tests for the main ExecutionEngine that selects algorithms."""

    @pytest.mark.asyncio
    async def test_engine_auto_selects_market_for_small_orders(self, mock_jupiter, mock_wallet):
        """Test engine selects market order for small orders."""
        from core.execution.algorithms import ExecutionEngine, Order, OrderSide

        engine = ExecutionEngine(mock_jupiter, mock_wallet)

        order = Order(
            token_mint=BONK_MINT,
            side=OrderSide.BUY,
            size_usd=50.0,  # Very small
            urgency="high",
        )

        result = await engine.execute(order, pool_liquidity=500_000.0)

        assert result.success is True
        assert result.algorithm == "MARKET"

    @pytest.mark.asyncio
    async def test_engine_auto_selects_iceberg_for_large_orders(self, mock_jupiter, mock_wallet):
        """Test engine selects iceberg for large orders."""
        from core.execution.algorithms import ExecutionEngine, Order, OrderSide

        engine = ExecutionEngine(mock_jupiter, mock_wallet)

        order = Order(
            token_mint=BONK_MINT,
            side=OrderSide.BUY,
            size_usd=10000.0,  # 2% of pool
            urgency="low",
        )

        result = await engine.execute(order, pool_liquidity=500_000.0)

        assert result.algorithm == "ICEBERG"

    @pytest.mark.asyncio
    async def test_engine_auto_selects_twap_for_low_urgency(self, mock_jupiter, mock_wallet):
        """Test engine selects TWAP for low urgency medium orders."""
        from core.execution.algorithms import ExecutionEngine, Order, OrderSide

        engine = ExecutionEngine(mock_jupiter, mock_wallet)

        order = Order(
            token_mint=BONK_MINT,
            side=OrderSide.BUY,
            size_usd=1000.0,
            urgency="low",
        )

        result = await engine.execute(order, pool_liquidity=500_000.0)

        assert result.algorithm == "TWAP"

    @pytest.mark.asyncio
    async def test_engine_respects_manual_algorithm_override(self, mock_jupiter, mock_wallet):
        """Test engine respects manual algorithm selection."""
        from core.execution.algorithms import ExecutionEngine, Order, OrderSide

        engine = ExecutionEngine(mock_jupiter, mock_wallet)

        order = Order(
            token_mint=BONK_MINT,
            side=OrderSide.BUY,
            size_usd=100.0,
            urgency="high",
        )

        # Force TWAP even for small order
        result = await engine.execute(
            order,
            pool_liquidity=500_000.0,
            force_algorithm="TWAP",
            duration_mins=5,
        )

        assert result.algorithm == "TWAP"

    @pytest.mark.asyncio
    async def test_engine_tracks_execution_metrics(self, mock_jupiter, mock_wallet, sample_order):
        """Test that engine tracks execution metrics."""
        from core.execution.algorithms import ExecutionEngine

        engine = ExecutionEngine(mock_jupiter, mock_wallet)

        result = await engine.execute(sample_order, pool_liquidity=500_000.0)

        # Should have timing metrics
        assert result.start_time is not None
        assert result.end_time is not None
        assert result.duration_seconds >= 0

    @pytest.mark.asyncio
    async def test_engine_handles_execution_failure(self, mock_jupiter, mock_wallet, sample_order):
        """Test engine handles execution failures gracefully."""
        from core.execution.algorithms import ExecutionEngine

        mock_jupiter.execute_swap = AsyncMock(return_value=MagicMock(
            success=False,
            error="Insufficient liquidity"
        ))

        engine = ExecutionEngine(mock_jupiter, mock_wallet)

        result = await engine.execute(sample_order, pool_liquidity=500_000.0)

        assert result.success is False
        assert "Insufficient liquidity" in str(result.error)


# =============================================================================
# Test Jupiter Integration
# =============================================================================

class TestJupiterIntegration:
    """Tests for Jupiter API integration with execution algorithms."""

    @pytest.mark.asyncio
    async def test_quote_fetching_per_chunk(self, mock_jupiter, mock_wallet, sample_order):
        """Test that each chunk fetches a fresh quote."""
        from core.execution.algorithms import TWAPExecutor

        executor = TWAPExecutor(mock_jupiter, wallet=mock_wallet)

        await executor.execute(
            order=sample_order,
            duration_mins=0.01,
            intervals=3,
        )

        # Should have fetched 3 quotes
        assert mock_jupiter.get_quote.call_count == 3

    @pytest.mark.asyncio
    async def test_slippage_adjustment_per_chunk(self, mock_jupiter, mock_wallet, sample_order):
        """Test that slippage is adjusted based on chunk size."""
        from core.execution.algorithms import TWAPExecutor

        executor = TWAPExecutor(mock_jupiter, wallet=mock_wallet)

        await executor.execute(
            order=sample_order,
            duration_mins=0.01,
            intervals=2,
        )

        # Check slippage in quote calls
        calls = mock_jupiter.get_quote.call_args_list
        for call in calls:
            # Smaller chunks should use lower slippage
            assert 'slippage_bps' in str(call) or call.kwargs.get('slippage_bps', 50) <= 100

    @pytest.mark.asyncio
    async def test_priority_fee_calculation(self, mock_jupiter, mock_wallet, sample_order):
        """Test priority fee calculation for execution."""
        from core.execution.algorithms import ExecutionEngine

        engine = ExecutionEngine(mock_jupiter, mock_wallet)

        # High urgency should use higher priority fee
        high_urgency_order = sample_order
        high_urgency_order.urgency = "high"

        priority_fee = engine.calculate_priority_fee(high_urgency_order)

        assert priority_fee > 0
        assert priority_fee >= 10000  # At least 10k microlamports


# =============================================================================
# Test Edge Cases
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    @pytest.mark.asyncio
    async def test_zero_order_size(self, mock_jupiter):
        """Test handling of zero-size order."""
        from core.execution.algorithms import ExecutionEngine, Order, OrderSide

        engine = ExecutionEngine(mock_jupiter, None)

        order = Order(
            token_mint=BONK_MINT,
            side=OrderSide.BUY,
            size_usd=0.0,
            urgency="low",
        )

        result = await engine.execute(order, pool_liquidity=500_000.0)

        assert result.success is False
        assert "zero" in result.error.lower() or "invalid" in result.error.lower()

    @pytest.mark.asyncio
    async def test_negative_order_size(self, mock_jupiter):
        """Test handling of negative order size."""
        from core.execution.algorithms import ExecutionEngine, Order, OrderSide

        engine = ExecutionEngine(mock_jupiter, None)

        order = Order(
            token_mint=BONK_MINT,
            side=OrderSide.BUY,
            size_usd=-100.0,
            urgency="low",
        )

        result = await engine.execute(order, pool_liquidity=500_000.0)

        assert result.success is False

    @pytest.mark.asyncio
    async def test_zero_pool_liquidity(self, mock_jupiter, sample_order):
        """Test handling of zero pool liquidity."""
        from core.execution.algorithms import ExecutionEngine

        engine = ExecutionEngine(mock_jupiter, None)

        result = await engine.execute(sample_order, pool_liquidity=0.0)

        # Should fail or use direct execution with warning
        assert result.success is False or result.warnings

    @pytest.mark.asyncio
    async def test_very_small_intervals(self, mock_jupiter, sample_order):
        """Test TWAP with very small intervals."""
        from core.execution.algorithms import TWAPExecutor

        executor = TWAPExecutor(mock_jupiter)

        # 1 minute with 100 intervals = 0.6 seconds each
        schedule = executor.create_schedule(
            order=sample_order,
            duration_mins=1,
            intervals=100,
        )

        # Should cap intervals or adjust
        assert len(schedule.chunks) <= 100

    @pytest.mark.asyncio
    async def test_order_larger_than_pool(self, mock_jupiter, mock_wallet):
        """Test handling order larger than pool liquidity."""
        from core.execution.algorithms import ExecutionEngine, Order, OrderSide

        engine = ExecutionEngine(mock_jupiter, mock_wallet)

        huge_order = Order(
            token_mint=BONK_MINT,
            side=OrderSide.BUY,
            size_usd=1_000_000.0,  # Larger than pool
            urgency="low",
        )

        result = await engine.execute(huge_order, pool_liquidity=500_000.0)

        # Should warn or split extensively
        assert result.algorithm == "ICEBERG"
        assert len(result.chunks) > 10


# =============================================================================
# Test Concurrency and Cancellation
# =============================================================================

class TestConcurrencyAndCancellation:
    """Tests for concurrent execution and cancellation."""

    @pytest.mark.asyncio
    async def test_cancel_ongoing_execution(self, mock_jupiter, mock_wallet, sample_order):
        """Test cancelling an ongoing TWAP execution."""
        from core.execution.algorithms import TWAPExecutor

        executor = TWAPExecutor(mock_jupiter, wallet=mock_wallet)

        # Start execution in background
        async def slow_execute():
            await executor.execute(
                order=sample_order,
                duration_mins=1,
                intervals=10,
            )

        task = asyncio.create_task(slow_execute())

        # Cancel after short delay
        await asyncio.sleep(0.1)
        executor.cancel()

        try:
            await asyncio.wait_for(task, timeout=1.0)
        except asyncio.CancelledError:
            pass

        assert executor.cancelled is True

    @pytest.mark.asyncio
    async def test_multiple_concurrent_orders(self, mock_jupiter, mock_wallet):
        """Test executing multiple orders concurrently."""
        from core.execution.algorithms import ExecutionEngine, Order, OrderSide

        engine = ExecutionEngine(mock_jupiter, mock_wallet)

        orders = [
            Order(token_mint=BONK_MINT, side=OrderSide.BUY, size_usd=100.0, urgency="high"),
            Order(token_mint=SOL_MINT, side=OrderSide.BUY, size_usd=200.0, urgency="high"),
        ]

        # Execute concurrently
        results = await asyncio.gather(*[
            engine.execute(order, pool_liquidity=500_000.0)
            for order in orders
        ])

        assert len(results) == 2
        assert all(r.success for r in results)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
