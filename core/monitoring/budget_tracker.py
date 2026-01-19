"""
Budget Tracker - API cost and spending monitoring.

Track spending:
- Grok API: daily spend + monthly projection
- Helius RPC: usage + cost
- Other APIs: costs per service

Alerts:
- If daily > 50% of monthly budget -> WARNING
- If daily > 100% of monthly budget -> CRITICAL

Prevent: runaway API costs
"""

import json
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, date, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("jarvis.monitoring.budget_tracker")


@dataclass
class CostRecord:
    """A single API cost record."""
    timestamp: datetime
    service: str
    cost_usd: float
    calls: int = 1
    metadata: Dict[str, Any] = field(default_factory=dict)


class BudgetTracker:
    """
    Tracks API costs and budget usage.

    Features:
    - Per-service cost tracking
    - Daily and monthly projections
    - Budget alerts
    """

    # Default monthly budgets (USD)
    DEFAULT_BUDGETS = {
        "grok": 10.0,
        "helius": 5.0,
        "anthropic": 20.0,
        "jupiter": 1.0,  # Usually free, but for any premium features
    }

    def __init__(
        self,
        data_dir: str = "data/budget",
        monthly_budgets: Optional[Dict[str, float]] = None,
    ):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.monthly_budgets = monthly_budgets or self.DEFAULT_BUDGETS.copy()

        # Cost records by date
        self._costs: Dict[str, List[CostRecord]] = defaultdict(list)

        # Load existing data
        self._load_data()

    def _get_date_key(self, dt: Optional[datetime] = None) -> str:
        """Get date key for storage."""
        if dt is None:
            dt = datetime.now(timezone.utc)
        return dt.strftime("%Y-%m-%d")

    def _load_data(self):
        """Load persisted budget data."""
        data_path = self.data_dir / "budget_data.json"
        if data_path.exists():
            try:
                with open(data_path) as f:
                    data = json.load(f)

                for date_key, records in data.get("costs", {}).items():
                    for record in records:
                        self._costs[date_key].append(CostRecord(
                            timestamp=datetime.fromisoformat(record["timestamp"]),
                            service=record["service"],
                            cost_usd=record["cost_usd"],
                            calls=record.get("calls", 1),
                            metadata=record.get("metadata", {})
                        ))

                # Prune old data (keep 90 days)
                self._prune_old_data()

            except Exception as e:
                logger.warning(f"Failed to load budget data: {e}")

    def _save_data(self):
        """Save budget data to disk."""
        self._prune_old_data()

        data = {
            "costs": {
                date_key: [
                    {
                        "timestamp": r.timestamp.isoformat(),
                        "service": r.service,
                        "cost_usd": r.cost_usd,
                        "calls": r.calls,
                        "metadata": r.metadata
                    }
                    for r in records
                ]
                for date_key, records in self._costs.items()
            },
            "budgets": self.monthly_budgets
        }

        data_path = self.data_dir / "budget_data.json"
        try:
            with open(data_path, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save budget data: {e}")

    def _prune_old_data(self):
        """Remove data older than 90 days."""
        cutoff = (datetime.now(timezone.utc) - timedelta(days=90)).strftime("%Y-%m-%d")
        old_keys = [k for k in self._costs.keys() if k < cutoff]
        for key in old_keys:
            del self._costs[key]

    def record_api_cost(
        self,
        service: str,
        cost_usd: float,
        calls: int = 1,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Record an API cost."""
        now = datetime.now(timezone.utc)
        date_key = self._get_date_key(now)

        record = CostRecord(
            timestamp=now,
            service=service,
            cost_usd=cost_usd,
            calls=calls,
            metadata=metadata or {}
        )

        self._costs[date_key].append(record)
        self._save_data()

        logger.debug(f"Recorded cost: {service} ${cost_usd:.4f} ({calls} calls)")

    def get_daily_spend(self, service: str, date_key: Optional[str] = None) -> float:
        """Get total spend for a service today (or specified date)."""
        if date_key is None:
            date_key = self._get_date_key()

        records = self._costs.get(date_key, [])
        return sum(r.cost_usd for r in records if r.service == service)

    def get_service_usage(self, service: str, date_key: Optional[str] = None) -> Dict[str, Any]:
        """Get usage statistics for a service today."""
        if date_key is None:
            date_key = self._get_date_key()

        records = [r for r in self._costs.get(date_key, []) if r.service == service]

        if not records:
            return {"calls": 0, "cost_usd": 0.0}

        return {
            "calls": sum(r.calls for r in records),
            "cost_usd": sum(r.cost_usd for r in records),
            "record_count": len(records)
        }

    def get_total_daily_spend(self, date_key: Optional[str] = None) -> float:
        """Get total spend across all services today."""
        if date_key is None:
            date_key = self._get_date_key()

        records = self._costs.get(date_key, [])
        return sum(r.cost_usd for r in records)

    def get_monthly_projection(self, service: str) -> float:
        """Project monthly spend based on current daily average."""
        # Get last 7 days of data
        now = datetime.now(timezone.utc)
        total = 0.0
        days_with_data = 0

        for i in range(7):
            date_key = (now - timedelta(days=i)).strftime("%Y-%m-%d")
            daily = self.get_daily_spend(service, date_key)
            if daily > 0:
                total += daily
                days_with_data += 1

        if days_with_data == 0:
            return 0.0

        avg_daily = total / days_with_data
        return avg_daily * 30  # Project to 30 days

    def check_budgets(self) -> List[Dict[str, Any]]:
        """
        Check if any service is over budget.

        Returns list of alerts for budget issues.
        """
        alerts = []

        for service, monthly_budget in self.monthly_budgets.items():
            daily_spend = self.get_daily_spend(service)

            # Check if daily > 100% of monthly budget (critical)
            if daily_spend > monthly_budget:
                alerts.append({
                    "severity": "critical",
                    "service": service,
                    "message": f"{service} daily spend (${daily_spend:.2f}) exceeds monthly budget (${monthly_budget:.2f})",
                    "daily_spend": daily_spend,
                    "monthly_budget": monthly_budget,
                    "percent_of_budget": (daily_spend / monthly_budget) * 100
                })
            # Check if daily > 50% of monthly budget (warning)
            elif daily_spend > (monthly_budget * 0.5):
                alerts.append({
                    "severity": "warning",
                    "service": service,
                    "message": f"{service} daily spend (${daily_spend:.2f}) is {(daily_spend/monthly_budget)*100:.0f}% of monthly budget",
                    "daily_spend": daily_spend,
                    "monthly_budget": monthly_budget,
                    "percent_of_budget": (daily_spend / monthly_budget) * 100
                })

        return alerts

    def get_all_stats(self) -> Dict[str, Any]:
        """Get comprehensive budget statistics."""
        today = self._get_date_key()

        services_stats = {}
        for service in set(self.monthly_budgets.keys()) | set(
            r.service for records in self._costs.values() for r in records
        ):
            usage = self.get_service_usage(service, today)
            monthly_budget = self.monthly_budgets.get(service, 0)
            projection = self.get_monthly_projection(service)

            services_stats[service] = {
                "daily_spend": usage["cost_usd"],
                "daily_calls": usage["calls"],
                "monthly_budget": monthly_budget,
                "monthly_projection": round(projection, 2),
                "budget_percent_used": round(
                    (usage["cost_usd"] / monthly_budget * 100) if monthly_budget > 0 else 0,
                    1
                )
            }

        return {
            "date": today,
            "total_daily_spend": round(self.get_total_daily_spend(), 4),
            "services": services_stats,
            "alerts": self.check_budgets()
        }


# Singleton
_tracker: Optional[BudgetTracker] = None


def get_budget_tracker() -> BudgetTracker:
    """Get or create the budget tracker singleton."""
    global _tracker
    if _tracker is None:
        _tracker = BudgetTracker()
    return _tracker
