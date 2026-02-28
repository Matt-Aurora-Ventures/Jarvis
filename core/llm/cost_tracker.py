"""
JARVIS LLM Cost Tracker

Comprehensive cost tracking for LLM API usage:
- Per-provider cost tracking
- Per-model cost tracking
- Token counting and pricing
- Budget alerts
- Usage analytics

Pricing based on January 2026 rates.
"""

import asyncio
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

from core.database import get_analytics_db

logger = logging.getLogger("jarvis.llm.cost_tracker")


# =============================================================================
# PRICING DATA
# =============================================================================

# Pricing per 1M tokens (input/output) - January 2026 rates
MODEL_PRICING: Dict[str, Tuple[float, float]] = {
    # OpenAI
    "gpt-4o": (2.50, 10.00),
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4-turbo": (10.00, 30.00),
    "gpt-4": (30.00, 60.00),
    "gpt-3.5-turbo": (0.50, 1.50),
    "o1": (15.00, 60.00),
    "o1-mini": (3.00, 12.00),

    # Anthropic
    "claude-3-opus": (15.00, 75.00),
    "claude-3-sonnet": (3.00, 15.00),
    "claude-3-haiku": (0.25, 1.25),
    "claude-3.5-sonnet": (3.00, 15.00),
    "claude-3.5-haiku": (0.80, 4.00),
    "claude-opus-4": (15.00, 75.00),
    "claude-sonnet-4": (3.00, 15.00),

    # Groq (free tier has limits)
    "llama-3.3-70b-versatile": (0.59, 0.79),
    "llama-3.1-70b-versatile": (0.59, 0.79),
    "llama-3.1-8b-instant": (0.05, 0.08),
    "llama-guard-3-8b": (0.20, 0.20),
    "mixtral-8x7b-32768": (0.24, 0.24),
    "gemma2-9b-it": (0.20, 0.20),

    # xAI
    "grok-2": (2.00, 10.00),
    "grok-2-mini": (0.20, 1.00),
    "grok-beta": (5.00, 15.00),

    # OpenRouter popular models
    "deepseek-r1": (0.55, 2.19),
    "deepseek-chat": (0.14, 0.28),
    "qwen-2.5-72b": (0.35, 0.40),
    "mistral-large": (2.00, 6.00),
    "command-r-plus": (2.50, 10.00),

    # Ollama (local, free)
    "llama3.2": (0.0, 0.0),
    "llama3.1": (0.0, 0.0),
    "llama3": (0.0, 0.0),
    "mistral": (0.0, 0.0),
    "codellama": (0.0, 0.0),
    "phi3": (0.0, 0.0),
    "qwen2.5": (0.0, 0.0),
    "gemma2": (0.0, 0.0),
}

# Provider name normalization
PROVIDER_ALIASES = {
    "openai": "openai",
    "anthropic": "anthropic",
    "claude": "anthropic",
    "groq": "groq",
    "xai": "xai",
    "grok": "xai",
    "openrouter": "openrouter",
    "ollama": "ollama",
    "local": "ollama",
}


# =============================================================================
# MODELS
# =============================================================================

@dataclass
class UsageRecord:
    """A single LLM usage record"""
    timestamp: datetime
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    latency_ms: float
    success: bool
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class UsageStats:
    """Aggregated usage statistics"""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cost_usd: float = 0.0
    avg_latency_ms: float = 0.0
    by_provider: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    by_model: Dict[str, Dict[str, Any]] = field(default_factory=dict)


@dataclass
class BudgetAlert:
    """Budget alert configuration"""
    name: str
    threshold_usd: float
    period: str  # "daily", "weekly", "monthly"
    callback: Optional[Callable] = None
    last_triggered: Optional[datetime] = None


# =============================================================================
# COST TRACKER
# =============================================================================

class LLMCostTracker:
    """
    Tracks LLM usage and costs across all providers.

    Features:
    - Real-time cost calculation
    - Historical usage data
    - Budget alerts
    - Provider/model analytics
    """

    def __init__(
        self,
        db_path: str = None,
        pricing: Dict[str, Tuple[float, float]] = None,
    ):
        # Unified database layer (db_path parameter kept for backward compatibility but ignored)
        self.pricing = pricing or MODEL_PRICING

        # Budget alerts
        self._alerts: Dict[str, BudgetAlert] = {}
        self.daily_budget: Optional[float] = None
        self.weekly_budget: Optional[float] = None
        self.monthly_budget: Optional[float] = None

        # Runtime stats
        self._session_stats = UsageStats()
        self._latencies: List[float] = []

        self._init_database()

    def _init_database(self):
        """Initialize cost tracking database"""
        db = get_analytics_db()
        with db.cursor() as cursor:
            # Usage records
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS llm_usage (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    model TEXT NOT NULL,
                    input_tokens INTEGER NOT NULL,
                    output_tokens INTEGER NOT NULL,
                    cost_usd REAL NOT NULL,
                    latency_ms REAL,
                    success INTEGER NOT NULL,
                    error TEXT,
                    metadata TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Daily aggregates for faster queries
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS llm_daily_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    model TEXT NOT NULL,
                    total_requests INTEGER NOT NULL,
                    successful_requests INTEGER NOT NULL,
                    total_input_tokens INTEGER NOT NULL,
                    total_output_tokens INTEGER NOT NULL,
                    total_cost_usd REAL NOT NULL,
                    avg_latency_ms REAL,
                    UNIQUE(date, provider, model)
                )
            """)

            # Budget alerts log
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS budget_alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    alert_name TEXT NOT NULL,
                    threshold_usd REAL NOT NULL,
                    actual_usd REAL NOT NULL,
                    period TEXT NOT NULL,
                    triggered_at TEXT NOT NULL
                )
            """)

            # Indexes
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_llm_usage_timestamp
                ON llm_usage(timestamp)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_llm_usage_provider
                ON llm_usage(provider)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_llm_daily_date
                ON llm_daily_stats(date)
            """)
            # Connection pool automatically commits on context exit

    # =========================================================================
    # COST CALCULATION
    # =========================================================================

    def calculate_cost(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
    ) -> float:
        """
        Calculate cost for a request.

        Args:
            model: Model name
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens

        Returns:
            Cost in USD
        """
        # Normalize model name
        model_lower = model.lower()

        # Find matching pricing
        pricing = None
        for model_key, prices in self.pricing.items():
            if model_key.lower() in model_lower or model_lower in model_key.lower():
                pricing = prices
                break

        if pricing is None:
            # Default to free (unknown model)
            logger.warning(f"Unknown model pricing: {model}")
            return 0.0

        input_price, output_price = pricing

        # Calculate cost (prices are per 1M tokens)
        input_cost = (input_tokens / 1_000_000) * input_price
        output_cost = (output_tokens / 1_000_000) * output_price

        return round(input_cost + output_cost, 6)

    # =========================================================================
    # RECORDING
    # =========================================================================

    def record_usage(
        self,
        provider: Any,
        model: str,
        input_tokens: int,
        output_tokens: int,
        latency_ms: float = 0.0,
        success: bool = True,
        error: str = None,
        metadata: Dict[str, Any] = None,
    ) -> UsageRecord:
        """
        Record LLM usage.

        Args:
            provider: Provider name
            model: Model name
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            latency_ms: Request latency in milliseconds
            success: Whether request succeeded
            error: Error message if failed
            metadata: Additional metadata

        Returns:
            UsageRecord
        """
        # Normalize provider
        if isinstance(provider, Enum):
            provider_name = str(provider.value)
        else:
            provider_name = str(provider)
        provider = PROVIDER_ALIASES.get(provider_name.lower(), provider_name.lower())

        # Calculate cost
        cost = self.calculate_cost(model, input_tokens, output_tokens) if success else 0.0

        record = UsageRecord(
            timestamp=datetime.now(timezone.utc),
            provider=provider,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost,
            latency_ms=latency_ms,
            success=success,
            error=error,
            metadata=metadata or {},
        )

        # Save to database
        self._save_record(record)

        # Update session stats
        self._update_session_stats(record)

        # Check budget alerts
        self._check_alerts(record)

        return record

    def _save_record(self, record: UsageRecord):
        """Save record to database"""
        import json

        db = get_analytics_db()
        with db.cursor() as cursor:
            cursor.execute("""
                INSERT INTO llm_usage
                (timestamp, provider, model, input_tokens, output_tokens,
                 cost_usd, latency_ms, success, error, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                record.timestamp.isoformat(),
                record.provider,
                record.model,
                record.input_tokens,
                record.output_tokens,
                record.cost_usd,
                record.latency_ms,
                1 if record.success else 0,
                record.error,
                json.dumps(record.metadata) if record.metadata else None,
            ))

            # Update daily aggregates
            date_str = record.timestamp.strftime("%Y-%m-%d")
            cursor.execute("""
                INSERT INTO llm_daily_stats
                (date, provider, model, total_requests, successful_requests,
                 total_input_tokens, total_output_tokens, total_cost_usd, avg_latency_ms)
                VALUES (?, ?, ?, 1, ?, ?, ?, ?, ?)
                ON CONFLICT(date, provider, model) DO UPDATE SET
                    total_requests = total_requests + 1,
                    successful_requests = successful_requests + excluded.successful_requests,
                    total_input_tokens = total_input_tokens + excluded.total_input_tokens,
                    total_output_tokens = total_output_tokens + excluded.total_output_tokens,
                    total_cost_usd = total_cost_usd + excluded.total_cost_usd,
                    avg_latency_ms = (avg_latency_ms + excluded.avg_latency_ms) / 2
            """, (
                date_str,
                record.provider,
                record.model,
                1 if record.success else 0,
                record.input_tokens,
                record.output_tokens,
                record.cost_usd,
                record.latency_ms,
            ))

    def _update_session_stats(self, record: UsageRecord):
        """Update session statistics"""
        self._session_stats.total_requests += 1

        if record.success:
            self._session_stats.successful_requests += 1
            self._session_stats.total_input_tokens += record.input_tokens
            self._session_stats.total_output_tokens += record.output_tokens
            self._session_stats.total_cost_usd += record.cost_usd
        else:
            self._session_stats.failed_requests += 1

        # Update latency
        if record.latency_ms > 0:
            self._latencies.append(record.latency_ms)
            if len(self._latencies) > 1000:
                self._latencies.pop(0)
            self._session_stats.avg_latency_ms = sum(self._latencies) / len(self._latencies)

    # =========================================================================
    # BUDGET ALERTS
    # =========================================================================

    def add_budget_alert(
        self,
        name: str,
        threshold_usd: float,
        period: str = "daily",
        callback: Callable = None,
    ):
        """
        Add a budget alert.

        Args:
            name: Alert name
            threshold_usd: Threshold in USD
            period: "daily", "weekly", or "monthly"
            callback: Optional callback function
        """
        self._alerts[name] = BudgetAlert(
            name=name,
            threshold_usd=threshold_usd,
            period=period,
            callback=callback,
        )
        logger.info(f"Added budget alert: {name} (${threshold_usd}/{period})")

    def remove_budget_alert(self, name: str):
        """Remove a budget alert"""
        if name in self._alerts:
            del self._alerts[name]

    def set_budget(
        self,
        daily_limit: Optional[float] = None,
        monthly_limit: Optional[float] = None,
        weekly_limit: Optional[float] = None,
    ) -> None:
        """
        Backward-compatible budget setter used by integration tests.

        Args:
            daily_limit: Daily USD cap
            monthly_limit: Monthly USD cap
            weekly_limit: Weekly USD cap
        """
        self.daily_budget = daily_limit
        self.monthly_budget = monthly_limit
        self.weekly_budget = weekly_limit

        # Clear previous auto-generated budget alerts.
        for alert_name in ("budget_daily", "budget_weekly", "budget_monthly"):
            self.remove_budget_alert(alert_name)

        if daily_limit is not None:
            self.add_budget_alert("budget_daily", float(daily_limit), period="daily")
        if weekly_limit is not None:
            self.add_budget_alert("budget_weekly", float(weekly_limit), period="weekly")
        if monthly_limit is not None:
            self.add_budget_alert("budget_monthly", float(monthly_limit), period="monthly")

    def _check_alerts(self, record: UsageRecord):
        """Check budget alerts"""
        for name, alert in self._alerts.items():
            # Get period cost
            period_cost = self._get_period_cost(alert.period)

            if period_cost >= alert.threshold_usd:
                # Check if already triggered recently
                if alert.last_triggered:
                    cooldown = timedelta(hours=1)
                    if datetime.now(timezone.utc) - alert.last_triggered < cooldown:
                        continue

                # Trigger alert
                alert.last_triggered = datetime.now(timezone.utc)

                logger.warning(
                    f"Budget alert '{name}': ${period_cost:.2f} >= ${alert.threshold_usd:.2f} ({alert.period})"
                )

                # Log to database
                self._log_alert(name, alert.threshold_usd, period_cost, alert.period)

                # Call callback if set
                if alert.callback:
                    try:
                        alert.callback(name, period_cost, alert.threshold_usd)
                    except Exception as e:
                        logger.error(f"Alert callback error: {e}")

    def _get_period_cost(self, period: str) -> float:
        """Get cost for a time period"""
        now = datetime.now(timezone.utc)

        if period == "daily":
            since = now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif period == "weekly":
            since = now - timedelta(days=now.weekday())
            since = since.replace(hour=0, minute=0, second=0, microsecond=0)
        elif period == "monthly":
            since = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        else:
            since = now - timedelta(days=1)

        db = get_analytics_db()
        with db.cursor() as cursor:
            cursor.execute("""
                SELECT COALESCE(SUM(cost_usd), 0) FROM llm_usage
                WHERE timestamp >= ? AND success = 1
            """, (since.isoformat(),))

            result = cursor.fetchone()[0]

        return result

    def _log_alert(self, name: str, threshold: float, actual: float, period: str):
        """Log alert to database"""
        db = get_analytics_db()
        with db.cursor() as cursor:
            cursor.execute("""
                INSERT INTO budget_alerts (alert_name, threshold_usd, actual_usd, period, triggered_at)
                VALUES (?, ?, ?, ?, ?)
            """, (name, threshold, actual, period, datetime.now(timezone.utc).isoformat()))

    # =========================================================================
    # STATISTICS
    # =========================================================================

    def get_session_stats(self) -> UsageStats:
        """Get current session statistics"""
        return self._session_stats

    def get_stats(
        self,
        hours: int = 24,
        provider: str = None,
        model: str = None,
    ) -> UsageStats:
        """
        Get usage statistics.

        Args:
            hours: Number of hours to look back
            provider: Filter by provider
            model: Filter by model

        Returns:
            UsageStats
        """
        db = get_analytics_db()

        since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()

        # Build query
        query = """
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successful,
                SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) as failed,
                SUM(input_tokens) as input_tokens,
                SUM(output_tokens) as output_tokens,
                SUM(cost_usd) as cost,
                AVG(latency_ms) as latency
            FROM llm_usage
            WHERE timestamp >= ?
        """
        params = [since]

        if provider:
            query += " AND provider = ?"
            params.append(provider)
        if model:
            query += " AND model = ?"
            params.append(model)

        with db.cursor() as cursor:
            cursor.execute(query, params)
            row = cursor.fetchone()

            stats = UsageStats(
                total_requests=row[0] or 0,
                successful_requests=row[1] or 0,
                failed_requests=row[2] or 0,
                total_input_tokens=row[3] or 0,
                total_output_tokens=row[4] or 0,
                total_cost_usd=row[5] or 0.0,
                avg_latency_ms=row[6] or 0.0,
            )

            # Get by-provider breakdown
            cursor.execute("""
                SELECT provider, COUNT(*), SUM(input_tokens), SUM(output_tokens), SUM(cost_usd)
                FROM llm_usage
                WHERE timestamp >= ? AND success = 1
                GROUP BY provider
            """, (since,))

            for row in cursor.fetchall():
                stats.by_provider[row[0]] = {
                    "requests": row[1],
                    "input_tokens": row[2],
                    "output_tokens": row[3],
                    "cost_usd": row[4],
                }

            # Get by-model breakdown
            cursor.execute("""
                SELECT model, COUNT(*), SUM(input_tokens), SUM(output_tokens), SUM(cost_usd)
                FROM llm_usage
                WHERE timestamp >= ? AND success = 1
                GROUP BY model
            """, (since,))

            for row in cursor.fetchall():
                stats.by_model[row[0]] = {
                    "requests": row[1],
                    "input_tokens": row[2],
                    "output_tokens": row[3],
                    "cost_usd": row[4],
                }

        return stats

    def get_daily_costs(self, days: int = 30) -> List[Dict[str, Any]]:
        """Get daily cost breakdown"""
        db = get_analytics_db()

        since = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")

        with db.cursor() as cursor:
            cursor.execute("""
                SELECT date, SUM(total_cost_usd), SUM(total_requests),
                       SUM(total_input_tokens), SUM(total_output_tokens)
                FROM llm_daily_stats
                WHERE date >= ?
                GROUP BY date
                ORDER BY date DESC
            """, (since,))

            results = []
            for row in cursor.fetchall():
                results.append({
                    "date": row[0],
                    "cost_usd": row[1],
                    "requests": row[2],
                    "input_tokens": row[3],
                    "output_tokens": row[4],
                })

        return results

    def get_top_models(
        self,
        hours: int = 24,
        limit: int = 10,
        sort_by: str = "cost",
    ) -> List[Dict[str, Any]]:
        """Get top models by usage or cost"""
        db = get_analytics_db()

        since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()

        order_by = "SUM(cost_usd)" if sort_by == "cost" else "COUNT(*)"

        with db.cursor() as cursor:
            cursor.execute(f"""
                SELECT model, provider, COUNT(*), SUM(input_tokens + output_tokens), SUM(cost_usd)
                FROM llm_usage
                WHERE timestamp >= ? AND success = 1
                GROUP BY model, provider
                ORDER BY {order_by} DESC
                LIMIT ?
            """, (since, limit))

            results = []
            for row in cursor.fetchall():
                results.append({
                    "model": row[0],
                    "provider": row[1],
                    "requests": row[2],
                    "tokens": row[3],
                    "cost_usd": row[4],
                })

        return results

    def get_cost_projection(self) -> Dict[str, float]:
        """Get cost projections based on current usage"""
        # Get last 7 days of daily costs
        daily_costs = self.get_daily_costs(days=7)

        if not daily_costs:
            return {"daily": 0, "weekly": 0, "monthly": 0}

        avg_daily = sum(d["cost_usd"] for d in daily_costs) / len(daily_costs)

        return {
            "daily": round(avg_daily, 2),
            "weekly": round(avg_daily * 7, 2),
            "monthly": round(avg_daily * 30, 2),
        }

    def to_dict(self) -> Dict[str, Any]:
        """Export current stats as dictionary"""
        stats = self.get_stats(hours=24)

        return {
            "24h_stats": {
                "total_requests": stats.total_requests,
                "successful_requests": stats.successful_requests,
                "failed_requests": stats.failed_requests,
                "total_tokens": stats.total_input_tokens + stats.total_output_tokens,
                "total_cost_usd": round(stats.total_cost_usd, 4),
                "avg_latency_ms": round(stats.avg_latency_ms, 2),
            },
            "by_provider": stats.by_provider,
            "by_model": stats.by_model,
            "projections": self.get_cost_projection(),
        }


# =============================================================================
# SINGLETON
# =============================================================================

_cost_tracker: Optional[LLMCostTracker] = None


def get_cost_tracker() -> LLMCostTracker:
    """Get or create the cost tracker singleton"""
    global _cost_tracker
    if _cost_tracker is None:
        _cost_tracker = LLMCostTracker()
    return _cost_tracker


# =============================================================================
# DECORATOR
# =============================================================================

def track_llm_cost(provider: str, model: str):
    """
    Decorator to track LLM costs for a function.

    The decorated function should return a tuple of (response, input_tokens, output_tokens)
    or a dict with 'input_tokens' and 'output_tokens' keys.

    Usage:
        @track_llm_cost("openai", "gpt-4o")
        async def generate_response(prompt):
            response = await openai.chat(...)
            return response, input_tokens, output_tokens
    """
    def decorator(func: Callable) -> Callable:
        async def wrapper(*args, **kwargs):
            tracker = get_cost_tracker()
            start = time.time()

            try:
                result = await func(*args, **kwargs)
                latency = (time.time() - start) * 1000

                # Extract token counts
                if isinstance(result, tuple) and len(result) >= 3:
                    response, input_tokens, output_tokens = result[:3]
                elif isinstance(result, dict):
                    response = result.get("response")
                    input_tokens = result.get("input_tokens", 0)
                    output_tokens = result.get("output_tokens", 0)
                else:
                    # Can't track without token counts
                    return result

                # Record usage
                tracker.record_usage(
                    provider=provider,
                    model=model,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    latency_ms=latency,
                    success=True,
                )

                return result

            except Exception as e:
                latency = (time.time() - start) * 1000

                # Record failure
                tracker.record_usage(
                    provider=provider,
                    model=model,
                    input_tokens=0,
                    output_tokens=0,
                    latency_ms=latency,
                    success=False,
                    error=str(e),
                )

                raise

        return wrapper
    return decorator
