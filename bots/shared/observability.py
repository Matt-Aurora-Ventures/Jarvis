"""
ClawdBot Observability Module - Lightweight MOLT Monitoring

Provides simple observability for ClawdBots without external dependencies:
- API latency tracking (Telegram, LLM APIs)
- Success/failure rate tracking
- Token usage monitoring
- Simple metrics collection to JSON file
- Health status endpoint helper
- Cost tracking and alerting

Usage:
    from bots.shared.observability import track_api_call, get_health_summary

    # Track an API call
    track_api_call("telegram", latency_ms=150, success=True, tokens_used=0)

    # Get health summary
    summary = get_health_summary()

    # Check if costs exceed threshold
    alert = alert_if_threshold_exceeded(cost_threshold_usd=10.0)
"""

import json
import logging
import os
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("clawdbot.observability")

# Default metrics file path (VPS location)
DEFAULT_METRICS_PATH = "/root/clawdbots/metrics.json"

# Default token rates ($ per 1000 tokens)
DEFAULT_TOKEN_RATES = {
    "openai": 0.002,       # GPT-3.5 input
    "anthropic": 0.003,    # Claude input
    "grok": 0.005,         # xAI Grok
    "telegram": 0.0,       # No token cost
    "default": 0.001,      # Fallback rate
}

# Singleton instance
_default_instance: Optional["ClawdBotObservability"] = None


class ClawdBotObservability:
    """
    Lightweight observability for ClawdBots.

    Thread-safe metrics collection with JSON persistence.
    """

    def __init__(self, metrics_path: Optional[str] = None):
        """
        Initialize observability with optional custom metrics path.

        Args:
            metrics_path: Path to metrics JSON file. Defaults to /root/clawdbots/metrics.json
        """
        self._lock = threading.RLock()
        self._metrics_path = metrics_path or DEFAULT_METRICS_PATH
        self._token_rates = DEFAULT_TOKEN_RATES.copy()

        # Initialize metrics structure
        self._data = self._create_empty_metrics()

        # Ensure directory exists and load existing data
        self._ensure_directory()
        self._load()

    def _create_empty_metrics(self) -> Dict[str, Any]:
        """Create empty metrics structure."""
        return {
            "api_calls": {
                "total": 0,
                "by_api": {}
            },
            "errors": [],
            "started_at": datetime.utcnow().isoformat(),
            "last_updated": datetime.utcnow().isoformat(),
        }

    def _create_empty_api_stats(self) -> Dict[str, Any]:
        """Create empty API stats structure."""
        return {
            "success_count": 0,
            "failure_count": 0,
            "total_tokens": 0,
            "latencies": [],
        }

    def _ensure_directory(self) -> None:
        """Ensure the metrics directory exists."""
        try:
            path = Path(self._metrics_path)
            path.parent.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.warning(f"Could not create metrics directory: {e}")

    def _load(self) -> None:
        """Load metrics from file if it exists."""
        try:
            if Path(self._metrics_path).exists():
                with open(self._metrics_path, 'r') as f:
                    loaded = json.load(f)
                    # Merge loaded data with defaults to handle schema changes
                    self._data = {**self._create_empty_metrics(), **loaded}
            else:
                # Create file with empty metrics
                self.save()
        except Exception as e:
            logger.warning(f"Could not load metrics: {e}")
            self._data = self._create_empty_metrics()
            self.save()

    def save(self) -> None:
        """Save metrics to file."""
        with self._lock:
            try:
                self._data["last_updated"] = datetime.utcnow().isoformat()
                with open(self._metrics_path, 'w') as f:
                    json.dump(self._data, f, indent=2, default=str)
            except Exception as e:
                logger.error(f"Could not save metrics: {e}")

    def reset(self) -> None:
        """Reset all metrics."""
        with self._lock:
            self._data = self._create_empty_metrics()
            self.save()

    def set_token_rates(self, rates: Dict[str, float]) -> None:
        """
        Set custom token rates for cost calculation.

        Args:
            rates: Dict mapping API names to cost per 1000 tokens
        """
        with self._lock:
            self._token_rates.update(rates)

    def track_api_call(
        self,
        api_name: str,
        latency_ms: float,
        success: bool,
        tokens_used: int = 0
    ) -> None:
        """
        Track an API call.

        Args:
            api_name: Name of the API (e.g., "telegram", "openai", "anthropic")
            latency_ms: Latency in milliseconds
            success: Whether the call succeeded
            tokens_used: Number of tokens used (for LLM APIs)
        """
        with self._lock:
            # Initialize API stats if needed
            if api_name not in self._data["api_calls"]["by_api"]:
                self._data["api_calls"]["by_api"][api_name] = self._create_empty_api_stats()

            api_stats = self._data["api_calls"]["by_api"][api_name]

            # Update counts
            self._data["api_calls"]["total"] += 1
            if success:
                api_stats["success_count"] += 1
            else:
                api_stats["failure_count"] += 1

            # Track tokens
            api_stats["total_tokens"] += tokens_used

            # Track latency (keep last 1000 for memory efficiency)
            api_stats["latencies"].append(latency_ms)
            if len(api_stats["latencies"]) > 1000:
                api_stats["latencies"] = api_stats["latencies"][-1000:]

            self._data["last_updated"] = datetime.utcnow().isoformat()

    def track_error(
        self,
        bot_name: str,
        error_type: str,
        message: str
    ) -> None:
        """
        Track an error.

        Args:
            bot_name: Name of the bot that encountered the error
            error_type: Type/class of the error
            message: Error message
        """
        with self._lock:
            error_entry = {
                "bot": bot_name,
                "type": error_type,
                "message": message,
                "timestamp": datetime.utcnow().isoformat()
            }

            # Keep last 100 errors
            self._data["errors"].append(error_entry)
            if len(self._data["errors"]) > 100:
                self._data["errors"] = self._data["errors"][-100:]

            self._data["last_updated"] = datetime.utcnow().isoformat()

    def get_health_summary(self) -> Dict[str, Any]:
        """
        Get a health summary.

        Returns:
            Dict with health status, API stats, uptime, and errors
        """
        with self._lock:
            # Calculate uptime
            try:
                started = datetime.fromisoformat(self._data["started_at"])
                uptime = (datetime.utcnow() - started).total_seconds()
            except Exception:
                uptime = 0

            # Calculate per-API stats
            api_stats = {}
            total_success = 0
            total_calls = 0
            max_latency = 0

            for api_name, stats in self._data["api_calls"]["by_api"].items():
                calls = stats["success_count"] + stats["failure_count"]
                total_calls += calls
                total_success += stats["success_count"]

                latencies = stats.get("latencies", [])
                avg_latency = sum(latencies) / len(latencies) if latencies else 0
                api_max_latency = max(latencies) if latencies else 0
                max_latency = max(max_latency, api_max_latency)

                api_stats[api_name] = {
                    "success_count": stats["success_count"],
                    "failure_count": stats["failure_count"],
                    "total_tokens": stats["total_tokens"],
                    "success_rate": stats["success_count"] / calls if calls > 0 else 1.0,
                    "avg_latency_ms": avg_latency,
                    "max_latency_ms": api_max_latency,
                }

            # Determine overall status
            overall_success_rate = total_success / total_calls if total_calls > 0 else 1.0
            if overall_success_rate >= 0.9:
                status = "healthy"
            elif overall_success_rate >= 0.5:
                status = "degraded"
            else:
                status = "unhealthy"

            return {
                "status": status,
                "uptime_seconds": uptime,
                "last_updated": self._data["last_updated"],
                "api_calls": {
                    "total": self._data["api_calls"]["total"],
                    "success_rate": overall_success_rate,
                    "max_latency_ms": max_latency,
                    "by_api": api_stats,
                },
                "errors": self._data["errors"][-10:],  # Last 10 errors
            }

    def get_daily_costs(self) -> Dict[str, Any]:
        """
        Calculate daily costs based on token usage.

        Returns:
            Dict with total cost and per-API breakdown
        """
        with self._lock:
            costs_by_api = {}
            total_cost = 0.0

            for api_name, stats in self._data["api_calls"]["by_api"].items():
                tokens = stats.get("total_tokens", 0)
                rate = self._token_rates.get(api_name, self._token_rates["default"])
                cost = (tokens / 1000) * rate

                costs_by_api[api_name] = {
                    "tokens": tokens,
                    "rate_per_1k": rate,
                    "cost_usd": cost,
                }
                total_cost += cost

            return {
                "total_usd": total_cost,
                "by_api": costs_by_api,
                "calculated_at": datetime.utcnow().isoformat(),
            }

    def alert_if_threshold_exceeded(
        self,
        cost_threshold_usd: float = 10.0,
        latency_threshold_ms: float = 5000.0,
        error_rate_threshold: float = 0.3
    ) -> Optional[Dict[str, Any]]:
        """
        Check if any thresholds are exceeded and return alert info.

        Args:
            cost_threshold_usd: Daily cost threshold in USD
            latency_threshold_ms: Maximum acceptable latency in ms
            error_rate_threshold: Maximum acceptable error rate (0-1)

        Returns:
            Alert dict if threshold exceeded, None otherwise
        """
        with self._lock:
            alerts = []

            # Check cost
            costs = self.get_daily_costs()
            if costs["total_usd"] > cost_threshold_usd:
                alerts.append({
                    "type": "cost",
                    "reason": f"Cost threshold exceeded: ${costs['total_usd']:.2f} > ${cost_threshold_usd:.2f}",
                    "value": costs["total_usd"],
                    "threshold": cost_threshold_usd,
                })

            # Check latency and error rate per API
            summary = self.get_health_summary()
            for api_name, stats in summary["api_calls"]["by_api"].items():
                if stats["max_latency_ms"] > latency_threshold_ms:
                    alerts.append({
                        "type": "latency",
                        "reason": f"Latency threshold exceeded for {api_name}: {stats['max_latency_ms']:.0f}ms > {latency_threshold_ms:.0f}ms",
                        "api": api_name,
                        "value": stats["max_latency_ms"],
                        "threshold": latency_threshold_ms,
                    })

                error_rate = 1 - stats["success_rate"]
                if error_rate > error_rate_threshold:
                    alerts.append({
                        "type": "error_rate",
                        "reason": f"Error rate threshold exceeded for {api_name}: {error_rate:.1%} > {error_rate_threshold:.1%}",
                        "api": api_name,
                        "value": error_rate,
                        "threshold": error_rate_threshold,
                    })

            if alerts:
                return {
                    "timestamp": datetime.utcnow().isoformat(),
                    "alert_count": len(alerts),
                    "reason": alerts[0]["reason"],  # Primary alert reason
                    "alerts": alerts,
                }

            return None


# Module-level convenience functions that use a singleton instance

def _get_default_instance() -> ClawdBotObservability:
    """Get or create the default singleton instance."""
    global _default_instance
    if _default_instance is None:
        _default_instance = ClawdBotObservability()
    return _default_instance


def track_api_call(
    api_name: str,
    latency_ms: float,
    success: bool,
    tokens_used: int = 0
) -> None:
    """
    Track an API call using the default instance.

    Args:
        api_name: Name of the API (e.g., "telegram", "openai", "anthropic")
        latency_ms: Latency in milliseconds
        success: Whether the call succeeded
        tokens_used: Number of tokens used (for LLM APIs)
    """
    _get_default_instance().track_api_call(api_name, latency_ms, success, tokens_used)


def track_error(bot_name: str, error_type: str, message: str) -> None:
    """
    Track an error using the default instance.

    Args:
        bot_name: Name of the bot that encountered the error
        error_type: Type/class of the error
        message: Error message
    """
    _get_default_instance().track_error(bot_name, error_type, message)


def get_health_summary() -> Dict[str, Any]:
    """
    Get a health summary using the default instance.

    Returns:
        Dict with health status, API stats, uptime, and errors
    """
    return _get_default_instance().get_health_summary()


def get_daily_costs() -> Dict[str, Any]:
    """
    Calculate daily costs using the default instance.

    Returns:
        Dict with total cost and per-API breakdown
    """
    return _get_default_instance().get_daily_costs()


def alert_if_threshold_exceeded(
    cost_threshold_usd: float = 10.0,
    latency_threshold_ms: float = 5000.0,
    error_rate_threshold: float = 0.3
) -> Optional[Dict[str, Any]]:
    """
    Check if any thresholds are exceeded using the default instance.

    Args:
        cost_threshold_usd: Daily cost threshold in USD
        latency_threshold_ms: Maximum acceptable latency in ms
        error_rate_threshold: Maximum acceptable error rate (0-1)

    Returns:
        Alert dict if threshold exceeded, None otherwise
    """
    return _get_default_instance().alert_if_threshold_exceeded(
        cost_threshold_usd, latency_threshold_ms, error_rate_threshold
    )


def save_metrics() -> None:
    """Save metrics to file using the default instance."""
    _get_default_instance().save()


def reset_metrics() -> None:
    """Reset all metrics using the default instance."""
    _get_default_instance().reset()


def set_token_rates(rates: Dict[str, float]) -> None:
    """
    Set custom token rates for cost calculation using the default instance.

    Args:
        rates: Dict mapping API names to cost per 1000 tokens
    """
    _get_default_instance().set_token_rates(rates)
