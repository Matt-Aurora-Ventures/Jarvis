"""
Bot Metrics Module - Core Observability Metrics

Provides centralized metrics tracking for all JARVIS bots:
- API call tracking (provider, latency, success/failure)
- Message tracking (bot, direction, size)
- Error tracking (bot, type, message)
- Prometheus export format
- Thread-safe singleton pattern

Usage:
    from core.observability.metrics import BotMetrics

    metrics = BotMetrics.get_instance()
    metrics.track_api_call(provider="openai", latency_ms=150.5, success=True)
    metrics.track_message(bot="jarvis", direction="inbound", size_bytes=256)
    metrics.track_error(bot="jarvis", error_type="RateLimit", message="Rate limited")

    stats = metrics.get_stats()
    prometheus_output = metrics.export_prometheus()
"""

import logging
import threading
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger("core.observability.metrics")


class BotMetrics:
    """
    Thread-safe singleton for bot metrics collection.

    Tracks API calls, messages, and errors across all bots.
    Supports Prometheus export format.
    """

    _instance: Optional["BotMetrics"] = None
    _lock = threading.RLock()

    def __new__(cls):
        """Singleton pattern - only one instance exists."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """Initialize metrics if not already initialized."""
        if self._initialized:
            return

        self._data_lock = threading.RLock()
        self._started_at = time.time()
        self._api_calls: Dict[str, Dict[str, Any]] = {}
        self._messages: Dict[str, Dict[str, Dict[str, Any]]] = {}
        self._errors: Dict[str, Dict[str, Any]] = {}
        self._total_api_calls = 0
        self._total_messages = 0
        self._total_errors = 0
        self._initialized = True

    @classmethod
    def get_instance(cls) -> "BotMetrics":
        """Get the singleton instance."""
        return cls()

    def reset(self) -> None:
        """Reset all metrics."""
        with self._data_lock:
            self._api_calls = {}
            self._messages = {}
            self._errors = {}
            self._total_api_calls = 0
            self._total_messages = 0
            self._total_errors = 0
            self._started_at = time.time()

    def track_api_call(
        self,
        provider: str,
        latency_ms: float,
        success: bool
    ) -> None:
        """
        Track an API call.

        Args:
            provider: API provider name (e.g., "openai", "anthropic", "grok")
            latency_ms: Latency in milliseconds
            success: Whether the call succeeded
        """
        with self._data_lock:
            if provider not in self._api_calls:
                self._api_calls[provider] = {
                    "success": 0,
                    "failure": 0,
                    "latencies": [],
                }

            if success:
                self._api_calls[provider]["success"] += 1
            else:
                self._api_calls[provider]["failure"] += 1

            # Keep last 1000 latencies for memory efficiency
            self._api_calls[provider]["latencies"].append(latency_ms)
            if len(self._api_calls[provider]["latencies"]) > 1000:
                self._api_calls[provider]["latencies"] = self._api_calls[provider]["latencies"][-1000:]

            self._total_api_calls += 1

    def track_message(
        self,
        bot: str,
        direction: str,
        size_bytes: int
    ) -> None:
        """
        Track a message.

        Args:
            bot: Bot name (e.g., "jarvis", "matt", "friday")
            direction: "inbound" or "outbound"
            size_bytes: Message size in bytes
        """
        with self._data_lock:
            if bot not in self._messages:
                self._messages[bot] = {
                    "inbound": {"count": 0, "bytes": 0},
                    "outbound": {"count": 0, "bytes": 0},
                }

            if direction not in self._messages[bot]:
                self._messages[bot][direction] = {"count": 0, "bytes": 0}

            self._messages[bot][direction]["count"] += 1
            self._messages[bot][direction]["bytes"] += size_bytes
            self._total_messages += 1

    def track_error(
        self,
        bot: str,
        error_type: str,
        message: str
    ) -> None:
        """
        Track an error.

        Args:
            bot: Bot name that encountered the error
            error_type: Type/class of the error
            message: Error message
        """
        with self._data_lock:
            if bot not in self._errors:
                self._errors[bot] = {
                    "by_type": {},
                    "recent": [],
                }

            if error_type not in self._errors[bot]["by_type"]:
                self._errors[bot]["by_type"][error_type] = 0

            self._errors[bot]["by_type"][error_type] += 1

            # Store recent errors (keep last 50)
            self._errors[bot]["recent"].append({
                "type": error_type,
                "message": message,
                "timestamp": datetime.utcnow().isoformat(),
            })
            if len(self._errors[bot]["recent"]) > 50:
                self._errors[bot]["recent"] = self._errors[bot]["recent"][-50:]

            self._total_errors += 1

    def get_stats(self) -> Dict[str, Any]:
        """
        Get current metrics statistics.

        Returns:
            Dict with api_calls, messages, errors, uptime, last_updated
        """
        with self._data_lock:
            # Calculate per-provider stats
            api_by_provider = {}
            for provider, data in self._api_calls.items():
                latencies = data["latencies"]
                avg_latency = sum(latencies) / len(latencies) if latencies else 0

                api_by_provider[provider] = {
                    "success": data["success"],
                    "failure": data["failure"],
                    "avg_latency_ms": avg_latency,
                    "total": data["success"] + data["failure"],
                }

            # Calculate per-bot message stats
            messages_by_bot = {}
            for bot, data in self._messages.items():
                messages_by_bot[bot] = data.copy()

            # Calculate per-bot error stats
            errors_by_bot = {}
            for bot, data in self._errors.items():
                errors_by_bot[bot] = {
                    "by_type": data["by_type"].copy(),
                    "recent": data["recent"][-10:],  # Last 10 errors
                }

            return {
                "api_calls": {
                    "total": self._total_api_calls,
                    "by_provider": api_by_provider,
                },
                "messages": {
                    "total": self._total_messages,
                    "by_bot": messages_by_bot,
                },
                "errors": {
                    "total": self._total_errors,
                    "by_bot": errors_by_bot,
                },
                "uptime_seconds": time.time() - self._started_at,
                "last_updated": datetime.utcnow().isoformat(),
            }

    def export_prometheus(self) -> str:
        """
        Export metrics in Prometheus text format.

        Returns:
            String in Prometheus exposition format
        """
        with self._data_lock:
            lines = []

            # API calls metric
            lines.append("# HELP jarvis_api_calls_total Total number of API calls")
            lines.append("# TYPE jarvis_api_calls_total counter")
            for provider, data in self._api_calls.items():
                total = data["success"] + data["failure"]
                lines.append(f'jarvis_api_calls_total{{provider="{provider}",status="success"}} {data["success"]}')
                lines.append(f'jarvis_api_calls_total{{provider="{provider}",status="failure"}} {data["failure"]}')

            # API latency metric
            lines.append("")
            lines.append("# HELP jarvis_api_latency_ms API call latency in milliseconds")
            lines.append("# TYPE jarvis_api_latency_ms gauge")
            for provider, data in self._api_calls.items():
                latencies = data["latencies"]
                if latencies:
                    avg = sum(latencies) / len(latencies)
                    lines.append(f'jarvis_api_latency_ms{{provider="{provider}",stat="avg"}} {avg:.2f}')

            # Messages metric
            lines.append("")
            lines.append("# HELP jarvis_messages_total Total number of messages")
            lines.append("# TYPE jarvis_messages_total counter")
            for bot, data in self._messages.items():
                for direction, stats in data.items():
                    lines.append(f'jarvis_messages_total{{bot="{bot}",direction="{direction}"}} {stats["count"]}')

            # Message bytes metric
            lines.append("")
            lines.append("# HELP jarvis_message_bytes_total Total message bytes")
            lines.append("# TYPE jarvis_message_bytes_total counter")
            for bot, data in self._messages.items():
                for direction, stats in data.items():
                    lines.append(f'jarvis_message_bytes_total{{bot="{bot}",direction="{direction}"}} {stats["bytes"]}')

            # Errors metric
            lines.append("")
            lines.append("# HELP jarvis_errors_total Total number of errors")
            lines.append("# TYPE jarvis_errors_total counter")
            for bot, data in self._errors.items():
                for error_type, count in data["by_type"].items():
                    lines.append(f'jarvis_errors_total{{bot="{bot}",type="{error_type}"}} {count}')

            # Uptime metric
            lines.append("")
            lines.append("# HELP jarvis_uptime_seconds Uptime in seconds")
            lines.append("# TYPE jarvis_uptime_seconds gauge")
            lines.append(f"jarvis_uptime_seconds {time.time() - self._started_at:.2f}")

            return "\n".join(lines)
