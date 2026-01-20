"""
Tests for Trade Execution Metrics Tracking

Tests:
- Metric collection
- Statistics calculation
- Slippage categorization
- Performance insights
- Cleanup operations
"""

import pytest
import asyncio
import os
import json
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

from core.trading.execution_metrics import (
    ExecutionMetricsTracker,
    ExecutionMetric,
    ExecutionStatus,
    SlippageImpact,
    ExecutionStats
)


@pytest.fixture
def temp_storage():
    """Create temporary storage file"""
    fd, path = tempfile.mkstemp(suffix='.json')
    os.close(fd)
    yield path
    if os.path.exists(path):
        os.unlink(path)


@pytest.fixture
def tracker(temp_storage):
    """Create metrics tracker with temp storage"""
    return ExecutionMetricsTracker(storage_path=temp_storage)


class TestMetricCollection:
    """Test metric collection operations"""

    def test_start_execution(self, tracker):
        """Test starting execution tracking"""
        metric_id = tracker.start_execution(
            token_symbol="SOL",
            token_mint="So11111111111111111111111111111111111111112",
            direction="BUY",
            requested_amount=10.0
        )

        assert metric_id.startswith("em_")
        assert len(tracker._metrics) == 1

        metric = tracker._get_metric(metric_id)
        assert metric is not None
        assert metric.token_symbol == "SOL"
        assert metric.direction == "BUY"
        assert metric.requested_amount == 10.0

    def test_record_quote_time(self, tracker):
        """Test recording quote retrieval time"""
        metric_id = tracker.start_execution("SOL", "mint123", "BUY", 10.0)

        tracker.record_quote_time(metric_id, 0.5)

        metric = tracker._get_metric(metric_id)
        assert metric.quote_time == 0.5

    def test_record_successful_execution(self, tracker):
        """Test recording successful execution"""
        metric_id = tracker.start_execution("SOL", "mint123", "BUY", 10.0)

        tracker.record_execution_result(
            metric_id=metric_id,
            status=ExecutionStatus.SUCCESS,
            tx_signature="sig123",
            expected_output=100.0,
            actual_output=99.5,
            filled_amount=10.0,
            execution_time=2.3,
            confirmation_time=1.2,
            priority_fee_lamports=10000,
            jupiter_fee_usd=0.25,
            price_impact_pct=0.3
        )

        metric = tracker._get_metric(metric_id)
        assert metric.status == ExecutionStatus.SUCCESS
        assert metric.tx_signature == "sig123"
        assert metric.expected_output == 100.0
        assert metric.actual_output == 99.5
        assert metric.filled_amount == 10.0
        assert metric.execution_time == 2.3
        assert metric.confirmation_time == 1.2
        assert metric.total_latency == 2.3 + 1.2  # quote_time not set
        assert metric.priority_fee_lamports == 10000
        assert metric.jupiter_fee_usd == 0.25

    def test_record_failed_execution(self, tracker):
        """Test recording failed execution"""
        metric_id = tracker.start_execution("SOL", "mint123", "BUY", 10.0)

        tracker.record_execution_result(
            metric_id=metric_id,
            status=ExecutionStatus.FAILED,
            execution_time=1.5,
            error_type="timeout",
            error_message="Transaction timed out"
        )

        metric = tracker._get_metric(metric_id)
        assert metric.status == ExecutionStatus.FAILED
        assert metric.error_type == "timeout"
        assert metric.error_message == "Transaction timed out"
        assert metric.tx_signature is None

    def test_slippage_calculation(self, tracker):
        """Test slippage calculation and categorization"""
        metric_id = tracker.start_execution("SOL", "mint123", "BUY", 10.0)

        # Test 0.3% slippage (LOW)
        tracker.record_execution_result(
            metric_id=metric_id,
            status=ExecutionStatus.SUCCESS,
            expected_output=100.0,
            actual_output=99.7,
            filled_amount=10.0,
            execution_time=1.0
        )

        metric = tracker._get_metric(metric_id)
        assert abs(metric.slippage_pct - 0.3) < 0.01
        assert metric.slippage_impact == SlippageImpact.LOW

    def test_slippage_categorization(self, tracker):
        """Test slippage impact categorization"""
        test_cases = [
            (0.05, SlippageImpact.NONE),
            (0.3, SlippageImpact.LOW),
            (0.7, SlippageImpact.MEDIUM),
            (1.5, SlippageImpact.HIGH),
            (3.0, SlippageImpact.SEVERE)
        ]

        for slippage, expected_impact in test_cases:
            assert tracker._categorize_slippage(slippage) == expected_impact

    def test_fill_rate_calculation(self, tracker):
        """Test fill rate calculation"""
        metric_id = tracker.start_execution("SOL", "mint123", "BUY", 10.0)

        # Partial fill (80%)
        tracker.record_execution_result(
            metric_id=metric_id,
            status=ExecutionStatus.PARTIAL,
            filled_amount=8.0,
            expected_output=100.0,
            actual_output=80.0,
            execution_time=1.0
        )

        metric = tracker._get_metric(metric_id)
        assert metric.fill_rate_pct == 80.0

    def test_cost_calculation(self, tracker):
        """Test cost tracking"""
        metric_id = tracker.start_execution("SOL", "mint123", "BUY", 10.0)

        tracker.record_execution_result(
            metric_id=metric_id,
            status=ExecutionStatus.SUCCESS,
            filled_amount=10.0,
            execution_time=1.0,
            priority_fee_lamports=50000,
            jupiter_fee_usd=0.50
        )

        metric = tracker._get_metric(metric_id)
        assert metric.priority_fee_lamports == 50000
        assert metric.priority_fee_sol == 0.00005  # 50000 / 1e9
        assert metric.jupiter_fee_usd == 0.50


class TestStatistics:
    """Test statistics calculation"""

    def test_basic_stats(self, tracker):
        """Test basic statistics calculation"""
        # Add 5 successful executions
        for i in range(5):
            metric_id = tracker.start_execution("SOL", "mint123", "BUY", 10.0)
            tracker.record_execution_result(
                metric_id=metric_id,
                status=ExecutionStatus.SUCCESS,
                expected_output=100.0,
                actual_output=99.5,
                filled_amount=10.0,
                execution_time=2.0 + i * 0.5,
                confirmation_time=1.0,
                priority_fee_lamports=10000,
                jupiter_fee_usd=0.25
            )

        # Add 1 failed execution
        metric_id = tracker.start_execution("SOL", "mint123", "BUY", 10.0)
        tracker.record_execution_result(
            metric_id=metric_id,
            status=ExecutionStatus.FAILED,
            execution_time=1.0,
            error_type="timeout"
        )

        stats = tracker.get_stats(hours=24)

        assert stats.total_executions == 6
        assert stats.successful_executions == 5
        assert stats.failed_executions == 1
        assert abs(stats.success_rate_pct - 83.33) < 0.01

    def test_latency_stats(self, tracker):
        """Test latency statistics"""
        latencies = [1.0, 2.0, 3.0, 4.0, 5.0, 10.0]  # One outlier

        for latency in latencies:
            metric_id = tracker.start_execution("SOL", "mint123", "BUY", 10.0)
            tracker.record_execution_result(
                metric_id=metric_id,
                status=ExecutionStatus.SUCCESS,
                filled_amount=10.0,
                execution_time=latency,
                confirmation_time=0.0
            )

        stats = tracker.get_stats(hours=24)

        assert abs(stats.avg_latency - 4.17) < 0.1  # Mean
        assert stats.median_latency == 3.5  # Median of 3.0 and 4.0
        assert stats.min_latency == 1.0
        assert stats.max_latency == 10.0
        assert stats.p95_latency >= 5.0

    def test_slippage_stats(self, tracker):
        """Test slippage statistics"""
        # Slippages: 0.05 (NONE), 0.2 (LOW), 0.3 (LOW), 0.7 (MEDIUM), 1.5 (HIGH), 2.5 (SEVERE)
        slippages = [0.05, 0.2, 0.3, 0.7, 1.5, 2.5]

        for slippage in slippages:
            metric_id = tracker.start_execution("SOL", "mint123", "BUY", 10.0)
            tracker.record_execution_result(
                metric_id=metric_id,
                status=ExecutionStatus.SUCCESS,
                expected_output=100.0,
                actual_output=100.0 - slippage,
                filled_amount=10.0,
                execution_time=1.0
            )

        stats = tracker.get_stats(hours=24)

        assert abs(stats.avg_slippage_pct - 0.875) < 0.1  # (0.05+0.2+0.3+0.7+1.5+2.5)/6
        assert stats.max_slippage_pct == 2.5
        assert stats.slippage_impact_distribution[SlippageImpact.NONE.value] == 1
        assert stats.slippage_impact_distribution[SlippageImpact.LOW.value] == 2
        assert stats.slippage_impact_distribution[SlippageImpact.MEDIUM.value] == 1
        assert stats.slippage_impact_distribution[SlippageImpact.HIGH.value] == 1
        assert stats.slippage_impact_distribution[SlippageImpact.SEVERE.value] == 1

    def test_cost_stats(self, tracker):
        """Test cost statistics"""
        for i in range(3):
            metric_id = tracker.start_execution("SOL", "mint123", "BUY", 10.0)
            tracker.record_execution_result(
                metric_id=metric_id,
                status=ExecutionStatus.SUCCESS,
                filled_amount=10.0,
                execution_time=1.0,
                priority_fee_lamports=10000 * (i + 1),
                jupiter_fee_usd=0.25 * (i + 1)
            )

        stats = tracker.get_stats(hours=24)

        assert stats.total_gas_cost_sol == 0.00006  # (10000 + 20000 + 30000) / 1e9
        assert abs(stats.avg_gas_cost_sol - 0.00002) < 0.000001
        assert stats.total_fees_usd == 1.5  # 0.25 + 0.50 + 0.75
        assert abs(stats.avg_fees_usd - 0.5) < 0.01

    def test_error_analysis(self, tracker):
        """Test error analysis"""
        errors = ["timeout", "timeout", "slippage", "blockhash"]

        for error in errors:
            metric_id = tracker.start_execution("SOL", "mint123", "BUY", 10.0)
            tracker.record_execution_result(
                metric_id=metric_id,
                status=ExecutionStatus.FAILED,
                execution_time=1.0,
                error_type=error
            )

        stats = tracker.get_stats(hours=24)

        assert stats.error_types["timeout"] == 2
        assert stats.error_types["slippage"] == 1
        assert stats.error_types["blockhash"] == 1

    def test_token_filter(self, tracker):
        """Test filtering by token"""
        # Add SOL trades
        for _ in range(3):
            metric_id = tracker.start_execution("SOL", "mint1", "BUY", 10.0)
            tracker.record_execution_result(
                metric_id=metric_id,
                status=ExecutionStatus.SUCCESS,
                filled_amount=10.0,
                execution_time=1.0
            )

        # Add BONK trades
        for _ in range(2):
            metric_id = tracker.start_execution("BONK", "mint2", "BUY", 10.0)
            tracker.record_execution_result(
                metric_id=metric_id,
                status=ExecutionStatus.SUCCESS,
                filled_amount=10.0,
                execution_time=1.0
            )

        sol_stats = tracker.get_token_stats("SOL", hours=24)
        bonk_stats = tracker.get_token_stats("BONK", hours=24)

        assert sol_stats.total_executions == 3
        assert bonk_stats.total_executions == 2


class TestAnalysis:
    """Test analysis features"""

    def test_get_recent_failures(self, tracker):
        """Test getting recent failures"""
        # Add failures
        for i in range(5):
            metric_id = tracker.start_execution("SOL", "mint123", "BUY", 10.0)
            tracker.record_execution_result(
                metric_id=metric_id,
                status=ExecutionStatus.FAILED,
                execution_time=1.0,
                error_type=f"error_{i}"
            )

        failures = tracker.get_recent_failures(limit=3)

        assert len(failures) == 3
        # Should be in reverse chronological order
        assert failures[0].error_type == "error_4"

    def test_get_high_slippage_trades(self, tracker):
        """Test finding high slippage trades"""
        slippages = [0.1, 0.5, 1.5, 2.5, 3.0]

        for slippage in slippages:
            metric_id = tracker.start_execution("SOL", "mint123", "BUY", 10.0)
            tracker.record_execution_result(
                metric_id=metric_id,
                status=ExecutionStatus.SUCCESS,
                expected_output=100.0,
                actual_output=100.0 - slippage,
                filled_amount=10.0,
                execution_time=1.0
            )

        high_slippage = tracker.get_high_slippage_trades(threshold_pct=1.0, limit=10)

        assert len(high_slippage) == 3  # 1.5%, 2.5%, 3.0%
        # Should be sorted by slippage descending
        assert abs(high_slippage[0].slippage_pct - 3.0) < 0.01

    def test_get_slow_executions(self, tracker):
        """Test finding slow executions"""
        latencies = [1.0, 5.0, 12.0, 15.0, 20.0]

        for latency in latencies:
            metric_id = tracker.start_execution("SOL", "mint123", "BUY", 10.0)
            tracker.record_execution_result(
                metric_id=metric_id,
                status=ExecutionStatus.SUCCESS,
                filled_amount=10.0,
                execution_time=latency,
                confirmation_time=0.0
            )

        slow = tracker.get_slow_executions(threshold_seconds=10.0, limit=10)

        assert len(slow) == 3  # 12s, 15s, 20s
        # Should be sorted by latency descending
        assert slow[0].total_latency == 20.0

    def test_optimization_insights(self, tracker):
        """Test optimization insights generation"""
        # Add metrics with various issues
        for i in range(100):
            metric_id = tracker.start_execution("SOL", "mint123", "BUY", 10.0)

            # High latency
            latency = 6.0 if i % 20 == 0 else 2.0

            # Some failures
            status = ExecutionStatus.FAILED if i % 10 == 0 else ExecutionStatus.SUCCESS

            # High slippage
            slippage = 1.0 if i % 15 == 0 else 0.2

            if status == ExecutionStatus.SUCCESS:
                tracker.record_execution_result(
                    metric_id=metric_id,
                    status=status,
                    expected_output=100.0,
                    actual_output=100.0 - slippage,
                    filled_amount=10.0,
                    execution_time=latency,
                    confirmation_time=0.5,
                    priority_fee_lamports=50000
                )
            else:
                tracker.record_execution_result(
                    metric_id=metric_id,
                    status=status,
                    execution_time=latency,
                    error_type="timeout"
                )

        insights = tracker.get_optimization_insights(hours=24)

        # Should have insights for all categories
        assert 'success_rate' in insights
        assert 'latency' in insights
        assert 'slippage' in insights
        assert 'costs' in insights

        # Success rate should be flagged (90%)
        assert insights['success_rate']['status'] == 'needs_improvement'
        assert insights['success_rate']['recommendation'] is not None


class TestPersistence:
    """Test data persistence"""

    def test_save_and_load(self, temp_storage):
        """Test saving and loading metrics"""
        # Create tracker and add metrics
        tracker1 = ExecutionMetricsTracker(storage_path=temp_storage)

        metric_id = tracker1.start_execution("SOL", "mint123", "BUY", 10.0)
        tracker1.record_execution_result(
            metric_id=metric_id,
            status=ExecutionStatus.SUCCESS,
            expected_output=100.0,
            actual_output=99.5,
            filled_amount=10.0,
            execution_time=2.0
        )

        # Create new tracker from same storage
        tracker2 = ExecutionMetricsTracker(storage_path=temp_storage)

        assert len(tracker2._metrics) == 1
        metric = tracker2._metrics[0]
        assert metric.token_symbol == "SOL"
        assert metric.status == ExecutionStatus.SUCCESS

    def test_cleanup_old_metrics(self, tracker):
        """Test cleanup of old metrics"""
        # Add old metric (40 days ago)
        old_metric_id = tracker.start_execution("SOL", "mint123", "BUY", 10.0)
        old_metric = tracker._get_metric(old_metric_id)
        old_metric.timestamp = (datetime.utcnow() - timedelta(days=40)).isoformat()

        # Add recent metric
        new_metric_id = tracker.start_execution("BONK", "mint456", "BUY", 10.0)

        assert len(tracker._metrics) == 2

        # Cleanup metrics older than 30 days
        tracker.cleanup_old_metrics(days=30)

        assert len(tracker._metrics) == 1
        assert tracker._metrics[0].metric_id == new_metric_id


class TestIntegration:
    """Integration tests"""

    def test_full_workflow(self, tracker):
        """Test complete execution workflow"""
        # Start execution
        metric_id = tracker.start_execution(
            token_symbol="SOL",
            token_mint="So11111111111111111111111111111111111111112",
            direction="BUY",
            requested_amount=10.0,
            position_id="pos_123"
        )

        # Record quote time
        tracker.record_quote_time(metric_id, 0.8)

        # Record successful execution
        tracker.record_execution_result(
            metric_id=metric_id,
            status=ExecutionStatus.SUCCESS,
            tx_signature="abc123xyz",
            expected_output=100.0,
            actual_output=99.2,
            filled_amount=10.0,
            execution_time=2.5,
            confirmation_time=1.5,
            priority_fee_lamports=15000,
            jupiter_fee_usd=0.30,
            price_impact_pct=0.4,
            retry_count=0
        )

        # Verify metric
        metric = tracker._get_metric(metric_id)
        assert metric.status == ExecutionStatus.SUCCESS
        assert metric.position_id == "pos_123"
        assert metric.quote_time == 0.8
        assert metric.execution_time == 2.5
        assert metric.confirmation_time == 1.5
        assert metric.total_latency == 4.8
        assert abs(metric.slippage_pct - 0.8) < 0.01
        assert metric.fill_rate_pct == 100.0

        # Get stats
        stats = tracker.get_stats(hours=24)
        assert stats.total_executions == 1
        assert stats.success_rate_pct == 100.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
