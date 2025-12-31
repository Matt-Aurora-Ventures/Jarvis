"""
Cost Tracker - Logs all operational costs.

Tracks:
- API call costs (Claude, GPT, Groq, Gemini)
- Compute costs (local CPU/GPU usage)
- Storage costs (data growth)
- External service costs

Pricing (approximate, USD per 1M tokens as of 2024):
- Claude Sonnet: $3 input, $15 output
- GPT-4o: $5 input, $15 output
- Groq (Llama 70B): $0.70 input, $0.80 output
- Gemini Flash: $0.075 input, $0.30 output
- Ollama: $0 (local compute)
"""

import json
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from core import config


ROOT = Path(__file__).resolve().parents[2]
COSTS_DIR = ROOT / "data" / "economics"
COSTS_LOG = COSTS_DIR / "costs.jsonl"


class CostCategory(str, Enum):
    API_CALL = "api_call"
    COMPUTE = "compute"
    STORAGE = "storage"
    EXTERNAL = "external"


class Provider(str, Enum):
    CLAUDE = "claude"
    OPENAI = "openai"
    GROQ = "groq"
    GEMINI = "gemini"
    OLLAMA = "ollama"
    LOCAL = "local"


# Pricing per 1M tokens (USD)
PRICING = {
    Provider.CLAUDE: {"input": 3.00, "output": 15.00},
    Provider.OPENAI: {"input": 5.00, "output": 15.00},
    Provider.GROQ: {"input": 0.70, "output": 0.80},
    Provider.GEMINI: {"input": 0.075, "output": 0.30},
    Provider.OLLAMA: {"input": 0.00, "output": 0.00},  # Free (local)
    Provider.LOCAL: {"input": 0.00, "output": 0.00},   # Free (local compute)
}

# Estimated compute cost per hour (local)
LOCAL_COMPUTE_COST_PER_HOUR = 0.05  # Electricity + wear


@dataclass
class CostEntry:
    """A single cost entry."""
    timestamp: float
    category: CostCategory
    provider: Provider
    cost_usd: float
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CostSummary:
    """Summary of costs over a period."""
    period_start: float
    period_end: float
    total_usd: float
    by_category: Dict[str, float] = field(default_factory=dict)
    by_provider: Dict[str, float] = field(default_factory=dict)
    api_calls: int = 0
    total_tokens: int = 0


class CostTracker:
    """
    Tracks all operational costs for the economic loop.

    Usage:
        tracker = CostTracker()

        # Log an API call
        tracker.log_api_call(
            provider=Provider.CLAUDE,
            input_tokens=1000,
            output_tokens=500,
            model="claude-3-5-sonnet",
            purpose="research"
        )

        # Get daily costs
        summary = tracker.get_summary(days=1)
    """

    def __init__(self):
        COSTS_DIR.mkdir(parents=True, exist_ok=True)
        self._session_costs: List[CostEntry] = []

    def log_api_call(
        self,
        provider: Provider,
        input_tokens: int,
        output_tokens: int,
        model: str = "",
        purpose: str = "",
        agent: str = "",
    ) -> float:
        """
        Log an API call and calculate cost.

        Returns the cost in USD.
        """
        pricing = PRICING.get(provider, PRICING[Provider.LOCAL])

        # Calculate cost
        input_cost = (input_tokens / 1_000_000) * pricing["input"]
        output_cost = (output_tokens / 1_000_000) * pricing["output"]
        total_cost = input_cost + output_cost

        entry = CostEntry(
            timestamp=time.time(),
            category=CostCategory.API_CALL,
            provider=provider,
            cost_usd=total_cost,
            details={
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": input_tokens + output_tokens,
                "model": model,
                "purpose": purpose,
                "agent": agent,
            },
        )

        self._log_entry(entry)
        return total_cost

    def log_compute(
        self,
        duration_seconds: float,
        purpose: str = "",
        cpu_percent: float = 0,
        gpu_used: bool = False,
    ) -> float:
        """Log local compute usage."""
        hours = duration_seconds / 3600
        cost = hours * LOCAL_COMPUTE_COST_PER_HOUR

        if gpu_used:
            cost *= 3  # GPU is more expensive

        entry = CostEntry(
            timestamp=time.time(),
            category=CostCategory.COMPUTE,
            provider=Provider.LOCAL,
            cost_usd=cost,
            details={
                "duration_seconds": duration_seconds,
                "purpose": purpose,
                "cpu_percent": cpu_percent,
                "gpu_used": gpu_used,
            },
        )

        self._log_entry(entry)
        return cost

    def log_storage(self, bytes_added: int, purpose: str = "") -> float:
        """Log storage cost (minimal but tracked)."""
        # $0.02 per GB per month, prorated per day
        gb = bytes_added / (1024 ** 3)
        daily_cost = (0.02 / 30) * gb

        entry = CostEntry(
            timestamp=time.time(),
            category=CostCategory.STORAGE,
            provider=Provider.LOCAL,
            cost_usd=daily_cost,
            details={
                "bytes": bytes_added,
                "purpose": purpose,
            },
        )

        self._log_entry(entry)
        return daily_cost

    def log_external(
        self,
        cost_usd: float,
        service: str,
        description: str = "",
    ) -> float:
        """Log external service cost."""
        entry = CostEntry(
            timestamp=time.time(),
            category=CostCategory.EXTERNAL,
            provider=Provider.LOCAL,
            cost_usd=cost_usd,
            details={
                "service": service,
                "description": description,
            },
        )

        self._log_entry(entry)
        return cost_usd

    def _log_entry(self, entry: CostEntry) -> None:
        """Write entry to log."""
        self._session_costs.append(entry)

        log_data = {
            "timestamp": entry.timestamp,
            "category": entry.category.value,
            "provider": entry.provider.value,
            "cost_usd": entry.cost_usd,
            **entry.details,
        }

        with open(COSTS_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_data) + "\n")

        try:
            from core.economics.database import get_economics_db

            get_economics_db().record_cost(
                category=entry.category.value,
                provider=entry.provider.value,
                cost_usd=entry.cost_usd,
                details=entry.details,
            )
        except Exception:
            pass

    def get_summary(self, days: int = 1) -> CostSummary:
        """Get cost summary for the last N days."""
        cutoff = time.time() - (days * 86400)

        by_category: Dict[str, float] = {}
        by_provider: Dict[str, float] = {}
        total = 0.0
        api_calls = 0
        total_tokens = 0

        # Read from log
        if COSTS_LOG.exists():
            with open(COSTS_LOG, "r") as f:
                for line in f:
                    try:
                        entry = json.loads(line)
                        if entry.get("timestamp", 0) < cutoff:
                            continue

                        cost = entry.get("cost_usd", 0)
                        category = entry.get("category", "unknown")
                        provider = entry.get("provider", "unknown")

                        total += cost
                        by_category[category] = by_category.get(category, 0) + cost
                        by_provider[provider] = by_provider.get(provider, 0) + cost

                        if category == "api_call":
                            api_calls += 1
                            total_tokens += entry.get("total_tokens", 0)

                    except json.JSONDecodeError:
                        continue

        return CostSummary(
            period_start=cutoff,
            period_end=time.time(),
            total_usd=total,
            by_category=by_category,
            by_provider=by_provider,
            api_calls=api_calls,
            total_tokens=total_tokens,
        )

    def get_today_costs(self) -> float:
        """Quick accessor for today's costs."""
        summary = self.get_summary(days=1)
        return summary.total_usd

    def get_session_costs(self) -> float:
        """Get costs for this session only."""
        return sum(e.cost_usd for e in self._session_costs)


# Global instance
_cost_tracker: Optional[CostTracker] = None


def get_cost_tracker() -> CostTracker:
    """Get the global cost tracker."""
    global _cost_tracker
    if _cost_tracker is None:
        _cost_tracker = CostTracker()
    return _cost_tracker


def log_api_cost(
    provider: str,
    input_tokens: int,
    output_tokens: int,
    **kwargs,
) -> float:
    """Convenience function to log an API cost."""
    try:
        prov = Provider(provider)
    except ValueError:
        prov = Provider.LOCAL

    return get_cost_tracker().log_api_call(
        provider=prov,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        **kwargs,
    )
