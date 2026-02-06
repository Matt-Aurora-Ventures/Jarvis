"""
Bot Metrics Collection Module.

Provides per-bot metrics collection for tracking:
- Messages received/sent
- Commands processed
- Errors total
- Response times
"""

import threading
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import logging

logger = logging.getLogger(__name__)


# Global registry for bot metrics instances
_metrics_registry: Dict[str, "BotMetrics"] = {}
_registry_lock = threading.Lock()


def get_bot_metrics(bot_name: str) -> "BotMetrics":
    """
    Get or create a BotMetrics instance for a specific bot.

    Thread-safe factory function that returns the same instance
    for the same bot name across multiple calls.

    Args:
        bot_name: Unique identifier for the bot

    Returns:
        BotMetrics instance for the specified bot
    """
    with _registry_lock:
        if bot_name not in _metrics_registry:
            _metrics_registry[bot_name] = BotMetrics(bot_name=bot_name)
        return _metrics_registry[bot_name]


def list_all_bots() -> List[str]:
    """
    List all registered bot names.

    Returns:
        List of bot names with registered metrics
    """
    with _registry_lock:
        return list(_metrics_registry.keys())


def _reset_registry():
    """
    Reset the global metrics registry.

    Used for testing purposes only.
    """
    global _metrics_registry
    with _registry_lock:
        _metrics_registry = {}


class BotMetrics:
    """
    Metrics collection for a single bot.

    Collects and tracks:
    - messages_received: Counter of incoming messages
    - messages_sent: Counter of outgoing messages
    - commands_processed: Counter of commands handled
    - errors_total: Counter of errors encountered
    - response_times: List of response durations in seconds

    Thread-safe implementation using internal locking.
    """

    # Valid metric names for increment()
    VALID_METRICS = {
        "messages_received",
        "messages_sent",
        "commands_processed",
        "errors_total",
    }

    def __init__(self, bot_name: str):
        """
        Initialize BotMetrics for a specific bot.

        Args:
            bot_name: Unique identifier for the bot
        """
        self.bot_name = bot_name
        self._lock = threading.Lock()

        # Counters
        self.messages_received: int = 0
        self.messages_sent: int = 0
        self.commands_processed: int = 0
        self.errors_total: int = 0

        # Timing data
        self.response_times: List[float] = []

        # Timestamp for creation
        self._created_at = time.time()

        logger.debug(f"BotMetrics initialized for bot: {bot_name}")

    def increment(self, metric: str, amount: int = 1) -> None:
        """
        Increment a counter metric.

        Args:
            metric: Name of the metric to increment (messages_received,
                   messages_sent, commands_processed, errors_total)
            amount: Amount to increment by (default: 1)

        Raises:
            ValueError: If metric name is not valid
        """
        if metric not in self.VALID_METRICS:
            raise ValueError(f"Unknown metric: {metric}. Valid metrics: {self.VALID_METRICS}")

        with self._lock:
            current = getattr(self, metric)
            setattr(self, metric, current + amount)

    def record_timing(self, operation: str, duration: float) -> None:
        """
        Record a timing measurement.

        Args:
            operation: Name of the operation (for logging/debugging)
            duration: Duration in seconds
        """
        with self._lock:
            self.response_times.append(duration)

        logger.debug(f"Bot {self.bot_name} - {operation}: {duration:.3f}s")

    def get_stats(self) -> Dict:
        """
        Get summary statistics for this bot.

        Returns:
            Dictionary containing all metrics and computed statistics
        """
        with self._lock:
            response_count = len(self.response_times)
            avg_response = 0.0

            if response_count > 0:
                avg_response = sum(self.response_times) / response_count

            return {
                "bot_name": self.bot_name,
                "messages_received": self.messages_received,
                "messages_sent": self.messages_sent,
                "commands_processed": self.commands_processed,
                "errors_total": self.errors_total,
                "response_times_count": response_count,
                "avg_response_time": avg_response,
                "created_at": self._created_at,
            }

    def reset(self) -> None:
        """
        Reset all metrics to initial state.

        Useful for periodic resets or testing.
        """
        with self._lock:
            self.messages_received = 0
            self.messages_sent = 0
            self.commands_processed = 0
            self.errors_total = 0
            self.response_times = []

        logger.info(f"BotMetrics reset for bot: {self.bot_name}")

    def __repr__(self) -> str:
        return (
            f"BotMetrics(bot_name={self.bot_name!r}, "
            f"messages_received={self.messages_received}, "
            f"messages_sent={self.messages_sent}, "
            f"errors_total={self.errors_total})"
        )
