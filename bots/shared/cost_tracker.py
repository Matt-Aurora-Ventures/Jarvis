"""
ClawdBots API Cost Tracker.

Tracks API costs per bot (OpenAI, Anthropic, X.AI/Grok), enforces daily/monthly
cost limits, alerts when approaching limits, and generates cost reports.

Storage: /root/clawdbots/api_costs.json (VPS) or configurable path

Usage:
    from bots.shared.cost_tracker import (
        track_api_call,
        get_daily_cost,
        get_monthly_cost,
        check_budget,
        get_cost_report,
        set_daily_limit,
    )

    # Track an API call
    track_api_call("clawdmatt", "openai", input_tokens=1000, output_tokens=500)

    # Check if bot is under budget
    if check_budget("clawdmatt"):
        # Make API call
        pass

    # Get cost report
    print(get_cost_report())
"""

import json
import logging
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


logger = logging.getLogger(__name__)


# =============================================================================
# CONSTANTS
# =============================================================================

# Default storage path (VPS deployment)
DEFAULT_STORAGE_PATH = Path("/root/clawdbots/api_costs.json")

# Default daily limit per bot in USD
DEFAULT_DAILY_LIMIT = 10.0

# Alert threshold (percentage of daily limit)
ALERT_THRESHOLD = 0.8  # 80%

# API Pricing: per 1K tokens (as specified in requirements)
# Format: provider -> model -> {input_per_1k, output_per_1k}
API_PRICING: Dict[str, Dict[str, Dict[str, float]]] = {
    "openai": {
        # GPT-4: $0.03/1K input, $0.06/1K output
        "gpt-4": {
            "input_per_1k": 0.03,
            "output_per_1k": 0.06,
        },
        "gpt-4o": {
            "input_per_1k": 0.015,
            "output_per_1k": 0.06,
        },
        "gpt-4o-mini": {
            "input_per_1k": 0.00015,
            "output_per_1k": 0.0006,
        },
        "gpt-3.5-turbo": {
            "input_per_1k": 0.0005,
            "output_per_1k": 0.0015,
        },
    },
    "anthropic": {
        # Claude: $0.015/1K input, $0.075/1K output
        "claude": {
            "input_per_1k": 0.015,
            "output_per_1k": 0.075,
        },
        "claude-opus": {
            "input_per_1k": 0.015,
            "output_per_1k": 0.075,
        },
        "claude-sonnet": {
            "input_per_1k": 0.003,
            "output_per_1k": 0.015,
        },
        "claude-haiku": {
            "input_per_1k": 0.00025,
            "output_per_1k": 0.00125,
        },
    },
    "xai": {
        # Grok: estimated similar to GPT-4
        "grok": {
            "input_per_1k": 0.03,
            "output_per_1k": 0.06,
        },
        "grok-2": {
            "input_per_1k": 0.03,
            "output_per_1k": 0.06,
        },
        "grok-3": {
            "input_per_1k": 0.001,
            "output_per_1k": 0.001,
        },
    },
    "groq": {
        # Groq models (fast inference)
        "llama": {
            "input_per_1k": 0.00059,
            "output_per_1k": 0.00079,
        },
        "mixtral": {
            "input_per_1k": 0.00024,
            "output_per_1k": 0.00024,
        },
    },
}


# =============================================================================
# COST TRACKER CLASS
# =============================================================================

class ClawdBotCostTracker:
    """
    Tracks API costs for ClawdBots.

    Stores data in JSON format with structure:
    {
        "daily": {
            "2026-02-02": [
                {
                    "bot_name": "clawdmatt",
                    "api": "openai",
                    "input_tokens": 1000,
                    "output_tokens": 500,
                    "cost_usd": 0.06,
                    "timestamp": "2026-02-02T10:30:00"
                },
                ...
            ]
        },
        "limits": {
            "clawdmatt": 10.0,
            "clawdjarvis": 10.0,
            ...
        }
    }
    """

    def __init__(
        self,
        storage_path: Optional[Path] = None,
        alert_callback: Optional[Callable[[str, float, float, float], None]] = None,
    ):
        """
        Initialize the cost tracker.

        Args:
            storage_path: Path to JSON storage file.
                         Defaults to /root/clawdbots/api_costs.json
            alert_callback: Optional callback for budget alerts.
                           Signature: (bot_name, current_cost, limit, percentage) -> None
        """
        self._storage_path = storage_path or DEFAULT_STORAGE_PATH
        self._alert_callback = alert_callback
        self._data: Dict[str, Any] = {}
        self._limits: Dict[str, float] = {}
        self._alerted_today: Dict[str, bool] = {}

        self._load_data()

    def _load_data(self) -> None:
        """Load data from storage file."""
        if self._storage_path.exists():
            try:
                with open(self._storage_path, "r", encoding="utf-8") as f:
                    self._data = json.load(f)
                    self._limits = self._data.get("limits", {})
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Failed to load cost data from {self._storage_path}: {e}")
                self._data = {"daily": {}, "limits": {}}
        else:
            self._data = {"daily": {}, "limits": {}}

        # Ensure structure
        if "daily" not in self._data:
            self._data["daily"] = {}
        if "limits" not in self._data:
            self._data["limits"] = {}

    def _save_data(self) -> None:
        """Save data to storage file."""
        # Update limits in data
        self._data["limits"] = self._limits

        # Ensure parent directory exists
        self._storage_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            with open(self._storage_path, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2, ensure_ascii=False)
        except IOError as e:
            logger.error(f"Failed to save cost data to {self._storage_path}: {e}")

    def _calculate_cost(self, api: str, input_tokens: int, output_tokens: int) -> float:
        """
        Calculate cost for an API call.

        Args:
            api: API provider name (openai, anthropic, xai)
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens

        Returns:
            Cost in USD
        """
        api_lower = api.lower()

        if api_lower not in API_PRICING:
            logger.warning(f"Unknown API provider: {api}")
            return 0.0

        # Get first model's pricing as default
        provider_pricing = API_PRICING[api_lower]
        pricing = list(provider_pricing.values())[0]

        input_cost = (input_tokens / 1000) * pricing["input_per_1k"]
        output_cost = (output_tokens / 1000) * pricing["output_per_1k"]

        return input_cost + output_cost

    def track_api_call(
        self,
        bot_name: str,
        api: str,
        input_tokens: int,
        output_tokens: int,
        model: Optional[str] = None,
    ) -> float:
        """
        Track an API call.

        Args:
            bot_name: Name of the bot (e.g., "clawdmatt")
            api: API provider (e.g., "openai", "anthropic", "xai")
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            model: Optional model name for more specific pricing

        Returns:
            Cost of the call in USD
        """
        # Calculate cost
        cost = self._calculate_cost(api, input_tokens, output_tokens)

        # Create entry
        today = date.today().isoformat()
        entry = {
            "bot_name": bot_name,
            "api": api,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_usd": cost,
            "timestamp": datetime.now().isoformat(),
        }

        if model:
            entry["model"] = model

        # Add to daily data
        if today not in self._data["daily"]:
            self._data["daily"][today] = []

        self._data["daily"][today].append(entry)

        # Save to file
        self._save_data()

        # Check for budget alerts
        self._check_alerts(bot_name)

        logger.debug(
            f"Tracked API call: {bot_name}/{api} "
            f"({input_tokens}in/{output_tokens}out) = ${cost:.4f}"
        )

        return cost

    def _check_alerts(self, bot_name: str) -> None:
        """Check if budget alert should be triggered."""
        today = date.today().isoformat()
        alert_key = f"{bot_name}:{today}"

        # Skip if already alerted today for this bot
        if self._alerted_today.get(alert_key):
            return

        daily_cost = self.get_daily_cost(bot_name=bot_name)
        limit = self._limits.get(bot_name, DEFAULT_DAILY_LIMIT)
        percentage = daily_cost / limit if limit > 0 else 0

        if percentage >= ALERT_THRESHOLD:
            self._alerted_today[alert_key] = True

            logger.warning(
                f"Budget alert for {bot_name}: ${daily_cost:.2f} / ${limit:.2f} "
                f"({percentage*100:.1f}%)"
            )

            if self._alert_callback:
                try:
                    self._alert_callback(bot_name, daily_cost, limit, percentage)
                except Exception as e:
                    logger.error(f"Alert callback failed: {e}")

    def get_daily_cost(self, bot_name: Optional[str] = None) -> float:
        """
        Get total cost for today.

        Args:
            bot_name: Optional bot to filter by

        Returns:
            Total cost in USD
        """
        today = date.today().isoformat()
        entries = self._data["daily"].get(today, [])

        if bot_name:
            entries = [e for e in entries if e.get("bot_name") == bot_name]

        return sum(e.get("cost_usd", 0) for e in entries)

    def get_monthly_cost(self, bot_name: Optional[str] = None) -> float:
        """
        Get total cost for current month.

        Args:
            bot_name: Optional bot to filter by

        Returns:
            Total cost in USD
        """
        today = date.today()
        month_prefix = today.strftime("%Y-%m")

        total = 0.0
        for day_key, entries in self._data["daily"].items():
            if day_key.startswith(month_prefix):
                if bot_name:
                    entries = [e for e in entries if e.get("bot_name") == bot_name]
                total += sum(e.get("cost_usd", 0) for e in entries)

        return total

    def check_budget(self, bot_name: str) -> bool:
        """
        Check if bot is under daily budget.

        Args:
            bot_name: Name of the bot

        Returns:
            True if under budget, False if at or over limit
        """
        daily_cost = self.get_daily_cost(bot_name=bot_name)
        limit = self._limits.get(bot_name, DEFAULT_DAILY_LIMIT)

        return daily_cost < limit

    def set_daily_limit(self, bot_name: str, limit: float) -> None:
        """
        Set daily cost limit for a bot.

        Args:
            bot_name: Name of the bot
            limit: Daily limit in USD
        """
        self._limits[bot_name] = max(0.0, limit)
        self._save_data()

        logger.info(f"Set daily limit for {bot_name}: ${limit:.2f}")

    def set_alert_callback(
        self,
        callback: Callable[[str, float, float, float], None],
    ) -> None:
        """
        Set the alert callback function.

        Args:
            callback: Function with signature (bot_name, current, limit, percent)
        """
        self._alert_callback = callback

    def get_cost_report(self) -> str:
        """
        Generate human-readable cost report.

        Returns:
            Formatted cost report string
        """
        lines = [
            "ClawdBots API Cost Report",
            "=" * 30,
            "",
        ]

        # Today's costs
        today = date.today().isoformat()
        daily_total = self.get_daily_cost()

        lines.append(f"Date: {today}")
        lines.append(f"Daily Total: ${daily_total:.4f}")
        lines.append("")

        # Per-bot breakdown
        lines.append("Per-Bot Breakdown:")
        lines.append("-" * 20)

        today_entries = self._data["daily"].get(today, [])
        bots_seen: Dict[str, float] = {}

        for entry in today_entries:
            bot = entry.get("bot_name", "unknown")
            cost = entry.get("cost_usd", 0)
            bots_seen[bot] = bots_seen.get(bot, 0) + cost

        if bots_seen:
            for bot, cost in sorted(bots_seen.items()):
                limit = self._limits.get(bot, DEFAULT_DAILY_LIMIT)
                pct = (cost / limit * 100) if limit > 0 else 0
                lines.append(f"  {bot}: ${cost:.4f} / ${limit:.2f} ({pct:.1f}%)")
        else:
            lines.append("  No API calls today")

        # Monthly total
        lines.append("")
        monthly_total = self.get_monthly_cost()
        lines.append(f"Monthly Total: ${monthly_total:.4f}")

        # Per-API breakdown
        lines.append("")
        lines.append("Per-API Breakdown (today):")
        lines.append("-" * 20)

        apis_seen: Dict[str, Dict[str, Any]] = {}
        for entry in today_entries:
            api = entry.get("api", "unknown")
            if api not in apis_seen:
                apis_seen[api] = {"cost": 0, "calls": 0, "tokens": 0}
            apis_seen[api]["cost"] += entry.get("cost_usd", 0)
            apis_seen[api]["calls"] += 1
            apis_seen[api]["tokens"] += entry.get("input_tokens", 0) + entry.get("output_tokens", 0)

        if apis_seen:
            for api, stats in sorted(apis_seen.items()):
                lines.append(
                    f"  {api}: ${stats['cost']:.4f} "
                    f"({stats['calls']} calls, {stats['tokens']} tokens)"
                )
        else:
            lines.append("  No API calls today")

        return "\n".join(lines)


# =============================================================================
# GLOBAL INSTANCE AND MODULE-LEVEL FUNCTIONS
# =============================================================================

_tracker: Optional[ClawdBotCostTracker] = None


def get_tracker(
    storage_path: Optional[Path] = None,
    force_new: bool = False,
) -> ClawdBotCostTracker:
    """
    Get the global tracker instance.

    Args:
        storage_path: Optional storage path override
        force_new: Force create a new instance

    Returns:
        ClawdBotCostTracker instance
    """
    global _tracker

    if _tracker is None or force_new:
        _tracker = ClawdBotCostTracker(storage_path=storage_path)

    return _tracker


def track_api_call(
    bot_name: str,
    api: str,
    input_tokens: int,
    output_tokens: int,
    model: Optional[str] = None,
) -> float:
    """
    Track an API call.

    Args:
        bot_name: Name of the bot (e.g., "clawdmatt")
        api: API provider (e.g., "openai", "anthropic", "xai")
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens
        model: Optional model name

    Returns:
        Cost of the call in USD
    """
    tracker = get_tracker()
    return tracker.track_api_call(bot_name, api, input_tokens, output_tokens, model)


def get_daily_cost(bot_name: Optional[str] = None) -> float:
    """
    Get today's total cost.

    Args:
        bot_name: Optional bot to filter by

    Returns:
        Total cost in USD
    """
    tracker = get_tracker()
    return tracker.get_daily_cost(bot_name=bot_name)


def get_monthly_cost(bot_name: Optional[str] = None) -> float:
    """
    Get current month's total cost.

    Args:
        bot_name: Optional bot to filter by

    Returns:
        Total cost in USD
    """
    tracker = get_tracker()
    return tracker.get_monthly_cost(bot_name=bot_name)


def check_budget(bot_name: str) -> bool:
    """
    Check if bot is under daily budget.

    Args:
        bot_name: Name of the bot

    Returns:
        True if under budget, False if at or over limit
    """
    tracker = get_tracker()
    return tracker.check_budget(bot_name)


def get_cost_report() -> str:
    """
    Generate cost report.

    Returns:
        Formatted cost report string
    """
    tracker = get_tracker()
    return tracker.get_cost_report()


def set_daily_limit(bot_name: str, limit: float) -> None:
    """
    Set daily cost limit for a bot.

    Args:
        bot_name: Name of the bot
        limit: Daily limit in USD
    """
    tracker = get_tracker()
    tracker.set_daily_limit(bot_name, limit)
