"""
Dexter Cost Tracking Module

Tracks API costs for Grok/LLM calls per decision.
Provides cost analysis, budget alerts, and monthly projections.

Target: < $0.20 per decision
"""

import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


@dataclass
class CostEntry:
    """Single cost tracking entry."""
    timestamp: str
    symbol: str
    decision: str
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    iterations: int = 0
    model: str = "grok-3"


@dataclass
class CostStats:
    """Aggregate cost statistics."""
    total_decisions: int = 0
    total_cost_usd: float = 0.0
    avg_cost_per_decision: float = 0.0

    # Percentile costs
    p50_cost: float = 0.0
    p95_cost: float = 0.0
    p99_cost: float = 0.0
    max_cost: float = 0.0
    min_cost: float = 0.0

    # Token stats
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    avg_input_tokens: float = 0.0
    avg_output_tokens: float = 0.0

    # Budget stats
    budget_per_decision: float = 0.20
    decisions_over_budget: int = 0
    decisions_over_budget_pct: float = 0.0

    # Projections
    daily_rate: float = 0.0
    monthly_projection: float = 0.0

    # Period
    period_start: str = ""
    period_end: str = ""


class DexterCostTracker:
    """
    Cost tracking for Dexter decisions.

    Tracks input/output tokens, calculates costs, monitors budget,
    and projects monthly spending.
    """

    # Grok-3 pricing (approximate, adjust as needed)
    GROK_INPUT_PRICE_PER_1K = 0.0015  # $0.0015 per 1K input tokens
    GROK_OUTPUT_PRICE_PER_1K = 0.005  # $0.005 per 1K output tokens

    # Budget configuration
    DEFAULT_BUDGET_PER_DECISION = 0.20  # $0.20 target

    def __init__(
        self,
        data_dir: str = "data/dexter/costs",
        budget_per_decision: float = 0.20
    ):
        """
        Initialize cost tracker.

        Args:
            data_dir: Directory to store cost logs
            budget_per_decision: Target budget per decision in USD
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.budget_per_decision = budget_per_decision

        # Cost storage
        self.entries: List[CostEntry] = []

        # File paths
        self.costs_file = self.data_dir / "costs.jsonl"
        self.stats_file = self.data_dir / "cost_stats.json"

        # Load existing entries
        self._load_entries()

        logger.info(f"Cost tracker initialized: budget=${budget_per_decision}/decision")

    def record_cost(
        self,
        symbol: str,
        decision: str,
        input_tokens: int,
        output_tokens: int,
        iterations: int = 1,
        model: str = "grok-3"
    ) -> CostEntry:
        """
        Record cost for a decision.

        Args:
            symbol: Token symbol analyzed
            decision: Decision made (BUY, SELL, HOLD, ERROR)
            input_tokens: Total input tokens used
            output_tokens: Total output tokens used
            iterations: Number of ReAct iterations
            model: LLM model used

        Returns:
            CostEntry with calculated cost
        """
        # Calculate cost
        cost_usd = self._calculate_cost(input_tokens, output_tokens)

        entry = CostEntry(
            timestamp=datetime.now(timezone.utc).isoformat(),
            symbol=symbol,
            decision=decision,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost_usd,
            iterations=iterations,
            model=model
        )

        self.entries.append(entry)
        self._append_entry(entry)

        # Check budget
        if cost_usd > self.budget_per_decision:
            logger.warning(
                f"Cost over budget: ${cost_usd:.4f} > ${self.budget_per_decision:.2f} "
                f"(symbol={symbol}, decision={decision})"
            )

        logger.info(
            f"Cost recorded: {symbol} {decision} - ${cost_usd:.4f} "
            f"({input_tokens} in, {output_tokens} out)"
        )

        return entry

    def get_stats(
        self,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None
    ) -> CostStats:
        """
        Calculate cost statistics for a period.

        Args:
            since: Start of period (default: all time)
            until: End of period (default: now)

        Returns:
            CostStats with aggregate metrics
        """
        stats = CostStats()
        stats.budget_per_decision = self.budget_per_decision

        # Filter entries by period
        entries = self._filter_entries(since, until)

        if not entries:
            stats.period_start = since.isoformat() if since else ""
            stats.period_end = until.isoformat() if until else ""
            return stats

        stats.total_decisions = len(entries)
        stats.period_start = entries[0].timestamp
        stats.period_end = entries[-1].timestamp

        # Calculate totals
        costs = [e.cost_usd for e in entries]
        stats.total_cost_usd = sum(costs)
        stats.avg_cost_per_decision = stats.total_cost_usd / len(costs)

        # Calculate percentiles
        sorted_costs = sorted(costs)
        n = len(sorted_costs)

        stats.p50_cost = self._percentile(sorted_costs, 50)
        stats.p95_cost = self._percentile(sorted_costs, 95)
        stats.p99_cost = self._percentile(sorted_costs, 99)
        stats.max_cost = max(costs)
        stats.min_cost = min(costs)

        # Token stats
        input_tokens = [e.input_tokens for e in entries]
        output_tokens = [e.output_tokens for e in entries]
        stats.total_input_tokens = sum(input_tokens)
        stats.total_output_tokens = sum(output_tokens)
        stats.avg_input_tokens = stats.total_input_tokens / len(input_tokens)
        stats.avg_output_tokens = stats.total_output_tokens / len(output_tokens)

        # Budget compliance
        over_budget = [c for c in costs if c > self.budget_per_decision]
        stats.decisions_over_budget = len(over_budget)
        stats.decisions_over_budget_pct = (len(over_budget) / len(costs)) * 100

        # Projections
        period_days = self._calculate_period_days(entries)
        if period_days > 0:
            stats.daily_rate = stats.total_cost_usd / period_days
            stats.monthly_projection = stats.daily_rate * 30

        return stats

    def check_budget(self) -> Dict[str, Any]:
        """
        Check current budget status and alerts.

        Returns:
            Budget status with alerts
        """
        stats = self.get_stats()

        status = {
            "status": "OK",
            "avg_cost": stats.avg_cost_per_decision,
            "budget": self.budget_per_decision,
            "utilization_pct": (stats.avg_cost_per_decision / self.budget_per_decision) * 100,
            "decisions_over_budget": stats.decisions_over_budget,
            "alerts": []
        }

        # Generate alerts
        if stats.avg_cost_per_decision > self.budget_per_decision:
            status["status"] = "OVER_BUDGET"
            status["alerts"].append(
                f"Average cost (${stats.avg_cost_per_decision:.4f}) exceeds budget "
                f"(${self.budget_per_decision:.2f})"
            )

        if stats.decisions_over_budget_pct > 10:
            status["alerts"].append(
                f"{stats.decisions_over_budget_pct:.1f}% of decisions exceed budget"
            )

        if stats.monthly_projection > 100:  # $100 monthly alert
            status["alerts"].append(
                f"Monthly projection: ${stats.monthly_projection:.2f} (high usage)"
            )

        if stats.p95_cost > self.budget_per_decision * 2:
            status["alerts"].append(
                f"P95 cost (${stats.p95_cost:.4f}) is high - investigate outliers"
            )

        return status

    def get_recent_costs(self, count: int = 10) -> List[CostEntry]:
        """
        Get most recent cost entries.

        Args:
            count: Number of entries to return

        Returns:
            List of recent CostEntry objects
        """
        return self.entries[-count:]

    def get_costs_by_symbol(self, symbol: str) -> List[CostEntry]:
        """
        Get all costs for a specific symbol.

        Args:
            symbol: Token symbol

        Returns:
            List of CostEntry objects for that symbol
        """
        return [e for e in self.entries if e.symbol.upper() == symbol.upper()]

    def generate_report(self) -> str:
        """
        Generate a text cost analysis report.

        Returns:
            Formatted report string
        """
        stats = self.get_stats()
        budget_status = self.check_budget()

        report = f"""
================================================================================
                    DEXTER COST ANALYSIS REPORT
================================================================================
Period: {stats.period_start[:19]} to {stats.period_end[:19]}
Total Decisions: {stats.total_decisions}

COST SUMMARY
------------
Total Cost:     ${stats.total_cost_usd:.4f}
Avg Cost:       ${stats.avg_cost_per_decision:.4f}
Budget Target:  ${stats.budget_per_decision:.2f}
Budget Status:  {budget_status['status']}

COST DISTRIBUTION
-----------------
P50 (Median): ${stats.p50_cost:.4f}
P95:          ${stats.p95_cost:.4f}
P99:          ${stats.p99_cost:.4f}
Max:          ${stats.max_cost:.4f}
Min:          ${stats.min_cost:.4f}

TOKEN USAGE
-----------
Total Input Tokens:  {stats.total_input_tokens:,}
Total Output Tokens: {stats.total_output_tokens:,}
Avg Input/Decision:  {stats.avg_input_tokens:,.0f}
Avg Output/Decision: {stats.avg_output_tokens:,.0f}

BUDGET COMPLIANCE
-----------------
Decisions Over Budget: {stats.decisions_over_budget} ({stats.decisions_over_budget_pct:.1f}%)

PROJECTIONS
-----------
Daily Rate:         ${stats.daily_rate:.2f}
Monthly Projection: ${stats.monthly_projection:.2f}
"""

        if budget_status['alerts']:
            report += "\nALERTS\n------\n"
            for alert in budget_status['alerts']:
                report += f"  ! {alert}\n"

        report += "\n" + "=" * 80

        return report

    def save_stats(self) -> str:
        """
        Save current statistics to JSON file.

        Returns:
            Path to stats file
        """
        stats = self.get_stats()
        with open(self.stats_file, 'w') as f:
            json.dump(asdict(stats), f, indent=2)
        logger.info(f"Cost stats saved to {self.stats_file}")
        return str(self.stats_file)

    def _calculate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Calculate USD cost from token counts."""
        input_cost = (input_tokens / 1000) * self.GROK_INPUT_PRICE_PER_1K
        output_cost = (output_tokens / 1000) * self.GROK_OUTPUT_PRICE_PER_1K
        return round(input_cost + output_cost, 6)

    def _percentile(self, sorted_data: List[float], percentile: int) -> float:
        """Calculate percentile from sorted data."""
        if not sorted_data:
            return 0.0
        n = len(sorted_data)
        idx = int((percentile / 100) * n) - 1
        idx = max(0, min(idx, n - 1))
        return sorted_data[idx]

    def _filter_entries(
        self,
        since: Optional[datetime],
        until: Optional[datetime]
    ) -> List[CostEntry]:
        """Filter entries by time period."""
        entries = self.entries

        if since:
            entries = [
                e for e in entries
                if datetime.fromisoformat(e.timestamp.replace('Z', '+00:00')) >= since
            ]

        if until:
            entries = [
                e for e in entries
                if datetime.fromisoformat(e.timestamp.replace('Z', '+00:00')) <= until
            ]

        return entries

    def _calculate_period_days(self, entries: List[CostEntry]) -> float:
        """Calculate the number of days spanned by entries."""
        if len(entries) < 2:
            return 1.0

        start = datetime.fromisoformat(entries[0].timestamp.replace('Z', '+00:00'))
        end = datetime.fromisoformat(entries[-1].timestamp.replace('Z', '+00:00'))

        days = (end - start).total_seconds() / 86400
        return max(days, 1/24)  # At least 1 hour

    def _append_entry(self, entry: CostEntry):
        """Append entry to JSONL file."""
        with open(self.costs_file, 'a') as f:
            f.write(json.dumps(asdict(entry)) + '\n')

    def _load_entries(self):
        """Load existing entries from file."""
        if not self.costs_file.exists():
            return

        with open(self.costs_file) as f:
            for line in f:
                if line.strip():
                    entry_dict = json.loads(line)
                    self.entries.append(CostEntry(**entry_dict))

        logger.info(f"Loaded {len(self.entries)} cost entries")
