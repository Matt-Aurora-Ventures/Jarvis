"""
JARVIS Business Metrics

Custom business metrics for tracking trading performance,
user engagement, bot activity, and system health KPIs.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from enum import Enum
from collections import defaultdict
import logging
import time
import threading

logger = logging.getLogger(__name__)


class MetricType(Enum):
    """Types of business metrics."""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"


@dataclass
class MetricValue:
    """A single metric value with metadata."""
    name: str
    value: float
    metric_type: MetricType
    labels: Dict[str, str] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    description: str = ""


@dataclass
class TradingMetrics:
    """Trading-related metrics."""
    total_trades: int = 0
    successful_trades: int = 0
    failed_trades: int = 0
    total_volume_usd: float = 0.0
    total_fees_usd: float = 0.0
    average_trade_size_usd: float = 0.0
    win_rate: float = 0.0
    profit_loss_usd: float = 0.0
    largest_trade_usd: float = 0.0
    trades_per_hour: float = 0.0


@dataclass
class UserMetrics:
    """User engagement metrics."""
    total_users: int = 0
    active_users_24h: int = 0
    active_users_7d: int = 0
    new_users_24h: int = 0
    messages_sent_24h: int = 0
    commands_used_24h: int = 0
    average_session_length_minutes: float = 0.0
    retention_rate_7d: float = 0.0


@dataclass
class BotMetrics:
    """Bot activity metrics."""
    telegram_messages_24h: int = 0
    telegram_commands_24h: int = 0
    twitter_mentions_24h: int = 0
    twitter_responses_24h: int = 0
    average_response_time_ms: float = 0.0
    error_rate: float = 0.0
    uptime_percentage: float = 100.0


@dataclass
class LLMMetrics:
    """LLM usage metrics."""
    total_requests_24h: int = 0
    total_tokens_24h: int = 0
    total_cost_24h: float = 0.0
    average_latency_ms: float = 0.0
    cache_hit_rate: float = 0.0
    errors_24h: int = 0
    provider_distribution: Dict[str, int] = field(default_factory=dict)


@dataclass
class SystemKPIs:
    """System-wide key performance indicators."""
    uptime_hours: float = 0.0
    api_requests_24h: int = 0
    api_error_rate: float = 0.0
    average_latency_ms: float = 0.0
    database_connections: int = 0
    cache_hit_rate: float = 0.0
    memory_usage_mb: float = 0.0
    cpu_usage_percent: float = 0.0


class BusinessMetricsCollector:
    """
    Collects and aggregates business metrics.

    Usage:
        collector = BusinessMetricsCollector()
        collector.record_trade(symbol="SOL/USDC", volume=1000.0, success=True)
        metrics = collector.get_trading_metrics()
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._trades: List[Dict[str, Any]] = []
        self._user_activity: Dict[str, List[datetime]] = defaultdict(list)
        self._bot_events: List[Dict[str, Any]] = []
        self._llm_requests: List[Dict[str, Any]] = []
        self._api_requests: List[Dict[str, Any]] = []
        self._start_time = datetime.utcnow()

    # =========================================================================
    # Trading Metrics
    # =========================================================================

    def record_trade(
        self,
        symbol: str,
        side: str,
        volume_usd: float,
        fee_usd: float = 0.0,
        success: bool = True,
        profit_loss: float = 0.0,
        **metadata
    ) -> None:
        """Record a trade execution."""
        with self._lock:
            self._trades.append({
                "symbol": symbol,
                "side": side,
                "volume_usd": volume_usd,
                "fee_usd": fee_usd,
                "success": success,
                "profit_loss": profit_loss,
                "timestamp": datetime.utcnow(),
                **metadata,
            })

        logger.debug(f"Recorded trade: {symbol} {side} ${volume_usd}")

    def get_trading_metrics(self, hours: int = 24) -> TradingMetrics:
        """Get aggregated trading metrics for the specified period."""
        cutoff = datetime.utcnow() - timedelta(hours=hours)

        with self._lock:
            recent = [t for t in self._trades if t["timestamp"] > cutoff]

        if not recent:
            return TradingMetrics()

        successful = [t for t in recent if t["success"]]
        failed = [t for t in recent if not t["success"]]

        total_volume = sum(t["volume_usd"] for t in recent)
        total_fees = sum(t["fee_usd"] for t in recent)
        total_pnl = sum(t.get("profit_loss", 0) for t in recent)

        return TradingMetrics(
            total_trades=len(recent),
            successful_trades=len(successful),
            failed_trades=len(failed),
            total_volume_usd=total_volume,
            total_fees_usd=total_fees,
            average_trade_size_usd=total_volume / len(recent) if recent else 0,
            win_rate=len(successful) / len(recent) if recent else 0,
            profit_loss_usd=total_pnl,
            largest_trade_usd=max(t["volume_usd"] for t in recent) if recent else 0,
            trades_per_hour=len(recent) / hours,
        )

    # =========================================================================
    # User Metrics
    # =========================================================================

    def record_user_activity(
        self,
        user_id: str,
        activity_type: str = "message",
        **metadata
    ) -> None:
        """Record user activity."""
        with self._lock:
            self._user_activity[user_id].append(datetime.utcnow())

        logger.debug(f"Recorded user activity: {user_id} - {activity_type}")

    def get_user_metrics(self) -> UserMetrics:
        """Get aggregated user metrics."""
        now = datetime.utcnow()
        cutoff_24h = now - timedelta(hours=24)
        cutoff_7d = now - timedelta(days=7)

        with self._lock:
            active_24h = set()
            active_7d = set()
            messages_24h = 0

            for user_id, activities in self._user_activity.items():
                recent_24h = [a for a in activities if a > cutoff_24h]
                recent_7d = [a for a in activities if a > cutoff_7d]

                if recent_24h:
                    active_24h.add(user_id)
                    messages_24h += len(recent_24h)
                if recent_7d:
                    active_7d.add(user_id)

        return UserMetrics(
            total_users=len(self._user_activity),
            active_users_24h=len(active_24h),
            active_users_7d=len(active_7d),
            messages_sent_24h=messages_24h,
        )

    # =========================================================================
    # Bot Metrics
    # =========================================================================

    def record_bot_event(
        self,
        bot_type: str,
        event_type: str,
        response_time_ms: Optional[float] = None,
        success: bool = True,
        **metadata
    ) -> None:
        """Record a bot event."""
        with self._lock:
            self._bot_events.append({
                "bot_type": bot_type,
                "event_type": event_type,
                "response_time_ms": response_time_ms,
                "success": success,
                "timestamp": datetime.utcnow(),
                **metadata,
            })

    def get_bot_metrics(self, hours: int = 24) -> BotMetrics:
        """Get aggregated bot metrics."""
        cutoff = datetime.utcnow() - timedelta(hours=hours)

        with self._lock:
            recent = [e for e in self._bot_events if e["timestamp"] > cutoff]

        telegram = [e for e in recent if e["bot_type"] == "telegram"]
        twitter = [e for e in recent if e["bot_type"] == "twitter"]
        successful = [e for e in recent if e["success"]]

        response_times = [e["response_time_ms"] for e in recent if e.get("response_time_ms")]

        return BotMetrics(
            telegram_messages_24h=len([e for e in telegram if e["event_type"] == "message"]),
            telegram_commands_24h=len([e for e in telegram if e["event_type"] == "command"]),
            twitter_mentions_24h=len([e for e in twitter if e["event_type"] == "mention"]),
            twitter_responses_24h=len([e for e in twitter if e["event_type"] == "response"]),
            average_response_time_ms=sum(response_times) / len(response_times) if response_times else 0,
            error_rate=1 - (len(successful) / len(recent)) if recent else 0,
        )

    # =========================================================================
    # LLM Metrics
    # =========================================================================

    def record_llm_request(
        self,
        provider: str,
        model: str,
        tokens: int,
        cost: float,
        latency_ms: float,
        cache_hit: bool = False,
        success: bool = True,
        **metadata
    ) -> None:
        """Record an LLM request."""
        with self._lock:
            self._llm_requests.append({
                "provider": provider,
                "model": model,
                "tokens": tokens,
                "cost": cost,
                "latency_ms": latency_ms,
                "cache_hit": cache_hit,
                "success": success,
                "timestamp": datetime.utcnow(),
                **metadata,
            })

    def get_llm_metrics(self, hours: int = 24) -> LLMMetrics:
        """Get aggregated LLM metrics."""
        cutoff = datetime.utcnow() - timedelta(hours=hours)

        with self._lock:
            recent = [r for r in self._llm_requests if r["timestamp"] > cutoff]

        if not recent:
            return LLMMetrics()

        total_tokens = sum(r["tokens"] for r in recent)
        total_cost = sum(r["cost"] for r in recent)
        cache_hits = len([r for r in recent if r["cache_hit"]])
        errors = len([r for r in recent if not r["success"]])
        latencies = [r["latency_ms"] for r in recent]

        provider_dist = defaultdict(int)
        for r in recent:
            provider_dist[r["provider"]] += 1

        return LLMMetrics(
            total_requests_24h=len(recent),
            total_tokens_24h=total_tokens,
            total_cost_24h=total_cost,
            average_latency_ms=sum(latencies) / len(latencies) if latencies else 0,
            cache_hit_rate=cache_hits / len(recent) if recent else 0,
            errors_24h=errors,
            provider_distribution=dict(provider_dist),
        )

    # =========================================================================
    # API Metrics
    # =========================================================================

    def record_api_request(
        self,
        endpoint: str,
        method: str,
        status_code: int,
        latency_ms: float,
        **metadata
    ) -> None:
        """Record an API request."""
        with self._lock:
            self._api_requests.append({
                "endpoint": endpoint,
                "method": method,
                "status_code": status_code,
                "latency_ms": latency_ms,
                "timestamp": datetime.utcnow(),
                **metadata,
            })

    # =========================================================================
    # System KPIs
    # =========================================================================

    def get_system_kpis(self) -> SystemKPIs:
        """Get system-wide KPIs."""
        now = datetime.utcnow()
        uptime = (now - self._start_time).total_seconds() / 3600

        cutoff = now - timedelta(hours=24)

        with self._lock:
            recent_api = [r for r in self._api_requests if r["timestamp"] > cutoff]

        errors = len([r for r in recent_api if r["status_code"] >= 400])
        latencies = [r["latency_ms"] for r in recent_api]

        # Try to get memory usage
        try:
            import psutil
            process = psutil.Process()
            memory_mb = process.memory_info().rss / 1024 / 1024
            cpu_percent = process.cpu_percent()
        except ImportError:
            memory_mb = 0
            cpu_percent = 0

        return SystemKPIs(
            uptime_hours=uptime,
            api_requests_24h=len(recent_api),
            api_error_rate=errors / len(recent_api) if recent_api else 0,
            average_latency_ms=sum(latencies) / len(latencies) if latencies else 0,
            memory_usage_mb=memory_mb,
            cpu_usage_percent=cpu_percent,
        )

    # =========================================================================
    # Export
    # =========================================================================

    def get_all_metrics(self) -> Dict[str, Any]:
        """Get all metrics as a dictionary."""
        trading = self.get_trading_metrics()
        users = self.get_user_metrics()
        bots = self.get_bot_metrics()
        llm = self.get_llm_metrics()
        system = self.get_system_kpis()

        return {
            "timestamp": datetime.utcnow().isoformat(),
            "trading": {
                "total_trades": trading.total_trades,
                "successful_trades": trading.successful_trades,
                "failed_trades": trading.failed_trades,
                "total_volume_usd": trading.total_volume_usd,
                "win_rate": trading.win_rate,
                "profit_loss_usd": trading.profit_loss_usd,
            },
            "users": {
                "total_users": users.total_users,
                "active_24h": users.active_users_24h,
                "active_7d": users.active_users_7d,
                "messages_24h": users.messages_sent_24h,
            },
            "bots": {
                "telegram_messages": bots.telegram_messages_24h,
                "twitter_mentions": bots.twitter_mentions_24h,
                "avg_response_time_ms": bots.average_response_time_ms,
                "error_rate": bots.error_rate,
            },
            "llm": {
                "requests_24h": llm.total_requests_24h,
                "tokens_24h": llm.total_tokens_24h,
                "cost_24h": llm.total_cost_24h,
                "avg_latency_ms": llm.average_latency_ms,
                "cache_hit_rate": llm.cache_hit_rate,
            },
            "system": {
                "uptime_hours": system.uptime_hours,
                "api_requests_24h": system.api_requests_24h,
                "api_error_rate": system.api_error_rate,
                "memory_usage_mb": system.memory_usage_mb,
            },
        }

    def to_prometheus_format(self) -> str:
        """Export metrics in Prometheus format."""
        lines = []
        metrics = self.get_all_metrics()

        # Trading metrics
        lines.append(f'jarvis_trades_total {metrics["trading"]["total_trades"]}')
        lines.append(f'jarvis_trades_successful {metrics["trading"]["successful_trades"]}')
        lines.append(f'jarvis_trading_volume_usd {metrics["trading"]["total_volume_usd"]}')
        lines.append(f'jarvis_trading_win_rate {metrics["trading"]["win_rate"]}')

        # User metrics
        lines.append(f'jarvis_users_total {metrics["users"]["total_users"]}')
        lines.append(f'jarvis_users_active_24h {metrics["users"]["active_24h"]}')
        lines.append(f'jarvis_messages_24h {metrics["users"]["messages_24h"]}')

        # Bot metrics
        lines.append(f'jarvis_telegram_messages {metrics["bots"]["telegram_messages"]}')
        lines.append(f'jarvis_twitter_mentions {metrics["bots"]["twitter_mentions"]}')
        lines.append(f'jarvis_bot_error_rate {metrics["bots"]["error_rate"]}')

        # LLM metrics
        lines.append(f'jarvis_llm_requests_24h {metrics["llm"]["requests_24h"]}')
        lines.append(f'jarvis_llm_tokens_24h {metrics["llm"]["tokens_24h"]}')
        lines.append(f'jarvis_llm_cost_usd_24h {metrics["llm"]["cost_24h"]}')

        # System metrics
        lines.append(f'jarvis_uptime_hours {metrics["system"]["uptime_hours"]}')
        lines.append(f'jarvis_api_requests_24h {metrics["system"]["api_requests_24h"]}')
        lines.append(f'jarvis_memory_usage_mb {metrics["system"]["memory_usage_mb"]}')

        return '\n'.join(lines)

    def cleanup_old_data(self, days: int = 7) -> int:
        """Remove data older than specified days."""
        cutoff = datetime.utcnow() - timedelta(days=days)
        removed = 0

        with self._lock:
            # Clean trades
            original = len(self._trades)
            self._trades = [t for t in self._trades if t["timestamp"] > cutoff]
            removed += original - len(self._trades)

            # Clean bot events
            original = len(self._bot_events)
            self._bot_events = [e for e in self._bot_events if e["timestamp"] > cutoff]
            removed += original - len(self._bot_events)

            # Clean LLM requests
            original = len(self._llm_requests)
            self._llm_requests = [r for r in self._llm_requests if r["timestamp"] > cutoff]
            removed += original - len(self._llm_requests)

            # Clean API requests
            original = len(self._api_requests)
            self._api_requests = [r for r in self._api_requests if r["timestamp"] > cutoff]
            removed += original - len(self._api_requests)

            # Clean user activity
            for user_id in list(self._user_activity.keys()):
                original_len = len(self._user_activity[user_id])
                self._user_activity[user_id] = [
                    a for a in self._user_activity[user_id]
                    if a > cutoff
                ]
                removed += original_len - len(self._user_activity[user_id])

                if not self._user_activity[user_id]:
                    del self._user_activity[user_id]

        logger.info(f"Cleaned up {removed} old metric records")
        return removed


# Global instance
_collector: Optional[BusinessMetricsCollector] = None


def get_business_metrics() -> BusinessMetricsCollector:
    """Get the global business metrics collector."""
    global _collector
    if _collector is None:
        _collector = BusinessMetricsCollector()
    return _collector


# Convenience functions
def record_trade(**kwargs) -> None:
    """Record a trade using the global collector."""
    get_business_metrics().record_trade(**kwargs)


def record_user_activity(**kwargs) -> None:
    """Record user activity using the global collector."""
    get_business_metrics().record_user_activity(**kwargs)


def record_bot_event(**kwargs) -> None:
    """Record a bot event using the global collector."""
    get_business_metrics().record_bot_event(**kwargs)


def record_llm_request(**kwargs) -> None:
    """Record an LLM request using the global collector."""
    get_business_metrics().record_llm_request(**kwargs)


def record_api_request(**kwargs) -> None:
    """Record an API request using the global collector."""
    get_business_metrics().record_api_request(**kwargs)
