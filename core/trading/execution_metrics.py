"""
Trade Execution Metrics Tracker

Tracks comprehensive metrics for trade execution including:
- Execution latency (quote to fill)
- Slippage tracking (expected vs actual)
- Success/failure rates
- Gas costs (priority fees)
- Fill rates and partial fills

All metrics stored for analysis and optimization.
"""

import asyncio
import json
import logging
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from collections import defaultdict
import statistics

logger = logging.getLogger(__name__)


class ExecutionStatus(str, Enum):
    """Execution outcome status"""
    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL = "partial"
    TIMEOUT = "timeout"
    REJECTED = "rejected"
    SIMULATED = "simulated"


class SlippageImpact(str, Enum):
    """Slippage severity categorization"""
    NONE = "none"           # < 0.1%
    LOW = "low"             # 0.1% - 0.5%
    MEDIUM = "medium"       # 0.5% - 1.0%
    HIGH = "high"           # 1.0% - 2.0%
    SEVERE = "severe"       # > 2.0%


@dataclass
class ExecutionMetric:
    """Single execution metric record"""
    # Identifiers
    metric_id: str
    tx_signature: Optional[str] = None
    position_id: Optional[str] = None
    token_symbol: str = ""
    token_mint: str = ""

    # Execution details
    direction: str = ""  # BUY/SELL
    status: ExecutionStatus = ExecutionStatus.SUCCESS

    # Timing metrics (all in seconds)
    quote_time: float = 0.0
    execution_time: float = 0.0
    confirmation_time: float = 0.0
    total_latency: float = 0.0

    # Slippage tracking
    expected_output: float = 0.0
    actual_output: float = 0.0
    slippage_pct: float = 0.0
    slippage_impact: SlippageImpact = SlippageImpact.NONE
    price_impact_pct: float = 0.0

    # Fill tracking
    requested_amount: float = 0.0
    filled_amount: float = 0.0
    fill_rate_pct: float = 100.0

    # Cost tracking
    priority_fee_lamports: int = 0
    priority_fee_sol: float = 0.0
    jupiter_fee_usd: float = 0.0
    total_cost_usd: float = 0.0

    # Network conditions
    network_congestion: str = "normal"  # low/normal/high
    retry_count: int = 0

    # Error tracking
    error_type: Optional[str] = None
    error_message: Optional[str] = None

    # Metadata
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ExecutionMetric':
        """Create from dictionary"""
        # Handle enum conversions
        if 'status' in data and isinstance(data['status'], str):
            data['status'] = ExecutionStatus(data['status'])
        if 'slippage_impact' in data and isinstance(data['slippage_impact'], str):
            data['slippage_impact'] = SlippageImpact(data['slippage_impact'])
        return cls(**data)


@dataclass
class ExecutionStats:
    """Aggregated execution statistics"""
    # Overall metrics
    total_executions: int = 0
    successful_executions: int = 0
    failed_executions: int = 0
    success_rate_pct: float = 0.0

    # Latency statistics (seconds)
    avg_latency: float = 0.0
    median_latency: float = 0.0
    p95_latency: float = 0.0
    p99_latency: float = 0.0
    min_latency: float = 0.0
    max_latency: float = 0.0

    # Slippage statistics
    avg_slippage_pct: float = 0.0
    median_slippage_pct: float = 0.0
    max_slippage_pct: float = 0.0
    slippage_impact_distribution: Dict[str, int] = field(default_factory=dict)

    # Fill rate statistics
    avg_fill_rate_pct: float = 100.0
    partial_fills_count: int = 0

    # Cost statistics
    total_gas_cost_sol: float = 0.0
    avg_gas_cost_sol: float = 0.0
    total_fees_usd: float = 0.0
    avg_fees_usd: float = 0.0

    # Error analysis
    error_types: Dict[str, int] = field(default_factory=dict)
    retry_distribution: Dict[int, int] = field(default_factory=dict)

    # Time range
    period_start: Optional[str] = None
    period_end: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)


class ExecutionMetricsTracker:
    """
    Track and analyze trade execution metrics.

    Features:
    - Real-time metric collection
    - Historical analysis
    - Performance benchmarking
    - Cost optimization insights
    """

    def __init__(self, storage_path: str = "data/execution_metrics.json"):
        self.storage_path = storage_path
        self._metrics: List[ExecutionMetric] = []
        self._metrics_by_token: Dict[str, List[str]] = defaultdict(list)
        self._load()

    def _load(self):
        """Load metrics from storage"""
        try:
            if os.path.exists(self.storage_path):
                with open(self.storage_path, 'r') as f:
                    data = json.load(f)

                for item in data.get('metrics', []):
                    metric = ExecutionMetric.from_dict(item)
                    self._metrics.append(metric)

                    if metric.token_symbol:
                        self._metrics_by_token[metric.token_symbol].append(metric.metric_id)

                logger.info(f"Loaded {len(self._metrics)} execution metrics")

        except Exception as e:
            logger.error(f"Failed to load execution metrics: {e}")

    def _save(self):
        """Save metrics to storage"""
        try:
            os.makedirs(os.path.dirname(self.storage_path) or ".", exist_ok=True)

            with open(self.storage_path, 'w') as f:
                json.dump({
                    'metrics': [m.to_dict() for m in self._metrics],
                    'last_updated': datetime.utcnow().isoformat()
                }, f, indent=2)

        except Exception as e:
            logger.error(f"Failed to save execution metrics: {e}")

    # =========================================================================
    # METRIC COLLECTION
    # =========================================================================

    def start_execution(
        self,
        token_symbol: str,
        token_mint: str,
        direction: str,
        requested_amount: float,
        position_id: Optional[str] = None
    ) -> str:
        """
        Start tracking a new execution.

        Returns:
            metric_id to use for recording results
        """
        import secrets
        metric_id = f"em_{secrets.token_hex(8)}"

        metric = ExecutionMetric(
            metric_id=metric_id,
            position_id=position_id,
            token_symbol=token_symbol,
            token_mint=token_mint,
            direction=direction,
            requested_amount=requested_amount
        )

        self._metrics.append(metric)
        self._metrics_by_token[token_symbol].append(metric_id)

        return metric_id

    def record_quote_time(self, metric_id: str, duration: float):
        """Record quote retrieval time"""
        metric = self._get_metric(metric_id)
        if metric:
            metric.quote_time = duration

    def record_execution_result(
        self,
        metric_id: str,
        status: ExecutionStatus,
        tx_signature: Optional[str] = None,
        expected_output: float = 0.0,
        actual_output: float = 0.0,
        filled_amount: float = 0.0,
        execution_time: float = 0.0,
        confirmation_time: float = 0.0,
        priority_fee_lamports: int = 0,
        jupiter_fee_usd: float = 0.0,
        price_impact_pct: float = 0.0,
        retry_count: int = 0,
        error_type: Optional[str] = None,
        error_message: Optional[str] = None
    ):
        """Record execution result with comprehensive metrics"""
        metric = self._get_metric(metric_id)
        if not metric:
            logger.warning(f"Metric {metric_id} not found")
            return

        # Update basic fields
        metric.status = status
        metric.tx_signature = tx_signature
        metric.execution_time = execution_time
        metric.confirmation_time = confirmation_time
        metric.total_latency = metric.quote_time + execution_time + confirmation_time
        metric.retry_count = retry_count

        # Calculate slippage
        if expected_output > 0 and actual_output > 0:
            metric.expected_output = expected_output
            metric.actual_output = actual_output
            metric.slippage_pct = ((expected_output - actual_output) / expected_output) * 100
            metric.slippage_impact = self._categorize_slippage(metric.slippage_pct)

        metric.price_impact_pct = price_impact_pct

        # Calculate fill rate
        if metric.requested_amount > 0:
            metric.filled_amount = filled_amount
            metric.fill_rate_pct = (filled_amount / metric.requested_amount) * 100

        # Calculate costs
        metric.priority_fee_lamports = priority_fee_lamports
        metric.priority_fee_sol = priority_fee_lamports / 1_000_000_000  # lamports to SOL
        metric.jupiter_fee_usd = jupiter_fee_usd
        # TODO: Convert SOL fee to USD using current price
        metric.total_cost_usd = jupiter_fee_usd  # + (priority_fee_sol * sol_price)

        # Error tracking
        if error_type or error_message:
            metric.error_type = error_type
            metric.error_message = error_message

        self._save()

        logger.info(
            f"Execution metric recorded: {metric_id} - "
            f"Status: {status.value}, "
            f"Latency: {metric.total_latency:.3f}s, "
            f"Slippage: {metric.slippage_pct:.2f}%, "
            f"Fill: {metric.fill_rate_pct:.1f}%"
        )

    def _categorize_slippage(self, slippage_pct: float) -> SlippageImpact:
        """Categorize slippage severity"""
        abs_slippage = abs(slippage_pct)

        if abs_slippage < 0.1:
            return SlippageImpact.NONE
        elif abs_slippage < 0.5:
            return SlippageImpact.LOW
        elif abs_slippage < 1.0:
            return SlippageImpact.MEDIUM
        elif abs_slippage < 2.0:
            return SlippageImpact.HIGH
        else:
            return SlippageImpact.SEVERE

    def _get_metric(self, metric_id: str) -> Optional[ExecutionMetric]:
        """Get metric by ID"""
        for metric in self._metrics:
            if metric.metric_id == metric_id:
                return metric
        return None

    # =========================================================================
    # ANALYTICS
    # =========================================================================

    def get_stats(
        self,
        hours: int = 24,
        token_symbol: Optional[str] = None,
        direction: Optional[str] = None
    ) -> ExecutionStats:
        """
        Get execution statistics for a time period.

        Args:
            hours: Number of hours to analyze
            token_symbol: Filter by token (optional)
            direction: Filter by direction BUY/SELL (optional)
        """
        cutoff = datetime.utcnow() - timedelta(hours=hours)

        # Filter metrics
        filtered = [
            m for m in self._metrics
            if datetime.fromisoformat(m.timestamp) >= cutoff
        ]

        if token_symbol:
            filtered = [m for m in filtered if m.token_symbol == token_symbol]

        if direction:
            filtered = [m for m in filtered if m.direction == direction]

        if not filtered:
            return ExecutionStats()

        stats = ExecutionStats()
        stats.total_executions = len(filtered)
        stats.period_start = min(m.timestamp for m in filtered)
        stats.period_end = max(m.timestamp for m in filtered)

        # Success metrics
        successful = [m for m in filtered if m.status == ExecutionStatus.SUCCESS]
        failed_statuses = {
            ExecutionStatus.FAILED,
            ExecutionStatus.TIMEOUT,
            ExecutionStatus.REJECTED,
            ExecutionStatus.SIMULATED,
        }
        failed = [m for m in filtered if m.status in failed_statuses]

        stats.successful_executions = len(successful)
        stats.failed_executions = len(failed)
        stats.success_rate_pct = (len(successful) / len(filtered)) * 100 if filtered else 0

        # Latency statistics (only successful)
        if successful:
            latencies = [m.total_latency for m in successful]
            stats.avg_latency = statistics.mean(latencies)
            stats.median_latency = statistics.median(latencies)
            stats.min_latency = min(latencies)
            stats.max_latency = max(latencies)

            # Percentiles
            sorted_latencies = sorted(latencies)
            p95_idx = int(len(sorted_latencies) * 0.95)
            p99_idx = int(len(sorted_latencies) * 0.99)
            stats.p95_latency = sorted_latencies[p95_idx] if p95_idx < len(sorted_latencies) else stats.max_latency
            stats.p99_latency = sorted_latencies[p99_idx] if p99_idx < len(sorted_latencies) else stats.max_latency

        # Slippage statistics
        with_slippage = [m for m in successful if m.expected_output > 0]
        if with_slippage:
            slippages = [m.slippage_pct for m in with_slippage]
            stats.avg_slippage_pct = statistics.mean(slippages)
            stats.median_slippage_pct = statistics.median(slippages)
            stats.max_slippage_pct = max(slippages)

            # Distribution
            stats.slippage_impact_distribution = defaultdict(int)
            for m in with_slippage:
                stats.slippage_impact_distribution[m.slippage_impact.value] += 1

        # Fill rate statistics
        fill_rates = [m.fill_rate_pct for m in successful if m.requested_amount > 0]
        if fill_rates:
            stats.avg_fill_rate_pct = statistics.mean(fill_rates)
            stats.partial_fills_count = sum(1 for rate in fill_rates if rate < 100)

        # Cost statistics
        stats.total_gas_cost_sol = sum(m.priority_fee_sol for m in successful)
        stats.total_fees_usd = sum(m.total_cost_usd for m in successful)

        if successful:
            stats.avg_gas_cost_sol = stats.total_gas_cost_sol / len(successful)
            stats.avg_fees_usd = stats.total_fees_usd / len(successful)

        # Error analysis
        stats.error_types = defaultdict(int)
        for m in failed:
            if m.error_type:
                stats.error_types[m.error_type] += 1

        # Retry distribution
        stats.retry_distribution = defaultdict(int)
        for m in filtered:
            stats.retry_distribution[m.retry_count] += 1

        return stats

    def get_token_stats(self, token_symbol: str, hours: int = 24) -> ExecutionStats:
        """Get stats for a specific token"""
        return self.get_stats(hours=hours, token_symbol=token_symbol)

    def get_recent_failures(self, limit: int = 10) -> List[ExecutionMetric]:
        """Get recent failed executions for debugging"""
        failed = [
            m for m in self._metrics
            if m.status in [ExecutionStatus.FAILED, ExecutionStatus.TIMEOUT, ExecutionStatus.REJECTED]
        ]

        # Sort by timestamp descending
        failed.sort(key=lambda m: m.timestamp, reverse=True)

        return failed[:limit]

    def get_high_slippage_trades(
        self,
        threshold_pct: float = 1.0,
        limit: int = 20
    ) -> List[ExecutionMetric]:
        """Get trades with high slippage for analysis"""
        high_slippage = [
            m for m in self._metrics
            if abs(m.slippage_pct) >= threshold_pct
        ]

        # Sort by slippage descending
        high_slippage.sort(key=lambda m: abs(m.slippage_pct), reverse=True)

        return high_slippage[:limit]

    def get_slow_executions(
        self,
        threshold_seconds: float = 10.0,
        limit: int = 20
    ) -> List[ExecutionMetric]:
        """Get slow executions for optimization"""
        slow = [
            m for m in self._metrics
            if m.total_latency >= threshold_seconds
        ]

        # Sort by latency descending
        slow.sort(key=lambda m: m.total_latency, reverse=True)

        return slow[:limit]

    def get_optimization_insights(self, hours: int = 24) -> Dict[str, Any]:
        """
        Get actionable optimization insights.

        Returns:
            Dictionary with optimization recommendations
        """
        stats = self.get_stats(hours=hours)

        insights = {
            'success_rate': {
                'value': stats.success_rate_pct,
                'status': 'good' if stats.success_rate_pct >= 95 else 'needs_improvement',
                'recommendation': None
            },
            'latency': {
                'avg': stats.avg_latency,
                'p95': stats.p95_latency,
                'status': 'good' if stats.p95_latency < 5.0 else 'slow',
                'recommendation': None
            },
            'slippage': {
                'avg': stats.avg_slippage_pct,
                'max': stats.max_slippage_pct,
                'status': 'good' if stats.avg_slippage_pct < 0.5 else 'high',
                'recommendation': None
            },
            'costs': {
                'avg_fee_usd': stats.avg_fees_usd,
                'total_gas_sol': stats.total_gas_cost_sol,
                'recommendation': None
            }
        }

        # Add recommendations
        if stats.success_rate_pct < 95:
            insights['success_rate']['recommendation'] = (
                "Success rate below 95%. Review failed executions and consider "
                "increasing retry attempts or adjusting slippage tolerance."
            )

        if stats.p95_latency > 5.0:
            insights['latency']['recommendation'] = (
                f"P95 latency is {stats.p95_latency:.2f}s. Consider increasing "
                "priority fees or using a faster RPC endpoint."
            )

        if stats.avg_slippage_pct > 0.5:
            insights['slippage']['recommendation'] = (
                f"Average slippage is {stats.avg_slippage_pct:.2f}%. Consider "
                "splitting large orders or trading during less volatile periods."
            )

        if stats.avg_gas_cost_sol > 0.01:
            insights['costs']['recommendation'] = (
                f"Average gas cost is {stats.avg_gas_cost_sol:.4f} SOL. "
                "Review priority fee settings for potential savings."
            )

        return insights

    # =========================================================================
    # CLEANUP
    # =========================================================================

    def cleanup_old_metrics(self, days: int = 30):
        """Remove metrics older than specified days"""
        cutoff = datetime.utcnow() - timedelta(days=days)

        initial_count = len(self._metrics)

        self._metrics = [
            m for m in self._metrics
            if datetime.fromisoformat(m.timestamp) >= cutoff
        ]

        # Rebuild token index
        self._metrics_by_token = defaultdict(list)
        for metric in self._metrics:
            if metric.token_symbol:
                self._metrics_by_token[metric.token_symbol].append(metric.metric_id)

        removed = initial_count - len(self._metrics)
        if removed > 0:
            self._save()
            logger.info(f"Cleaned up {removed} old execution metrics")


# Singleton
_tracker: Optional[ExecutionMetricsTracker] = None


def get_execution_metrics_tracker() -> ExecutionMetricsTracker:
    """Get the execution metrics tracker singleton"""
    global _tracker
    if _tracker is None:
        _tracker = ExecutionMetricsTracker()
    return _tracker


# Testing
if __name__ == "__main__":
    # Test the metrics tracker
    tracker = ExecutionMetricsTracker("data/test_execution_metrics.json")

    # Simulate an execution
    metric_id = tracker.start_execution(
        token_symbol="SOL",
        token_mint="So11111111111111111111111111111111111111112",
        direction="BUY",
        requested_amount=10.0
    )

    tracker.record_quote_time(metric_id, 0.5)

    tracker.record_execution_result(
        metric_id=metric_id,
        status=ExecutionStatus.SUCCESS,
        tx_signature="abc123",
        expected_output=100.0,
        actual_output=99.5,
        filled_amount=10.0,
        execution_time=2.3,
        confirmation_time=1.2,
        priority_fee_lamports=10000,
        jupiter_fee_usd=0.25,
        price_impact_pct=0.3
    )

    # Get stats
    stats = tracker.get_stats(hours=24)
    print(f"Total executions: {stats.total_executions}")
    print(f"Success rate: {stats.success_rate_pct:.2f}%")
    print(f"Avg latency: {stats.avg_latency:.3f}s")
    print(f"Avg slippage: {stats.avg_slippage_pct:.2f}%")

    # Get insights
    insights = tracker.get_optimization_insights()
    print("\nOptimization Insights:")
    for category, data in insights.items():
        print(f"\n{category.upper()}:")
        for key, value in data.items():
            print(f"  {key}: {value}")
