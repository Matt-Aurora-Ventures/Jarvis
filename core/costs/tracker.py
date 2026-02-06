"""
Cost Tracker for API usage monitoring.

Tracks API calls, manages budgets, and triggers alerts.
"""

import logging
from datetime import date, datetime
from typing import Any, Callable, Dict, Optional


logger = logging.getLogger(__name__)


# Default daily limit (from tg_bot/config.py daily_cost_limit_usd)
DEFAULT_DAILY_LIMIT = 10.0


class CostTracker:
    """
    Track API costs and enforce budget limits.

    Usage:
        tracker = CostTracker(daily_limit=10.0)

        # Track a call
        cost = tracker.track_call(
            provider="openai",
            model="gpt-4o",
            input_tokens=1000,
            output_tokens=500
        )

        # Check budget
        if not tracker.check_budget():
            print("Over daily budget!")

        # Alert if over
        tracker.alert_if_over_budget()
    """

    def __init__(
        self,
        storage: Optional["CostStorage"] = None,
        calculator: Optional["CostCalculator"] = None,
        daily_limit: float = DEFAULT_DAILY_LIMIT,
        alert_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    ):
        """
        Initialize the tracker.

        Args:
            storage: CostStorage instance (creates default if None)
            calculator: CostCalculator instance (creates default if None)
            daily_limit: Daily spending limit in USD
            alert_callback: Optional callback for budget alerts
        """
        # Lazy imports to avoid circular dependencies
        if storage is None:
            from core.costs.storage import CostStorage
            storage = CostStorage()
        if calculator is None:
            from core.costs.calculator import CostCalculator
            calculator = CostCalculator()

        self._storage = storage
        self._calculator = calculator
        self._daily_limit = daily_limit
        self._alert_callback = alert_callback
        self._alert_sent_today = False
        self._last_alert_date: Optional[date] = None

    @property
    def storage(self) -> "CostStorage":
        """Get the storage instance."""
        return self._storage

    @property
    def calculator(self) -> "CostCalculator":
        """Get the calculator instance."""
        return self._calculator

    @property
    def daily_limit(self) -> float:
        """Get the daily spending limit."""
        return self._daily_limit

    @daily_limit.setter
    def daily_limit(self, value: float) -> None:
        """Set the daily spending limit."""
        self._daily_limit = max(0.0, value)

    def track_call(
        self,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cost: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> float:
        """
        Track an API call.

        Args:
            provider: Provider name (e.g., "openai", "anthropic")
            model: Model name (e.g., "gpt-4o")
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            cost: Pre-calculated cost (calculated if not provided)
            metadata: Optional additional metadata

        Returns:
            The cost of the call in USD
        """
        # Calculate cost if not provided
        if cost is None:
            cost = self._calculator.calculate_cost(
                provider=provider,
                model=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )

        # Build entry
        entry = {
            "timestamp": datetime.now().isoformat(),
            "provider": provider,
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_usd": cost,
        }

        if metadata:
            entry.update(metadata)

        # Save to storage
        self._storage.save_entry(entry)

        logger.debug(
            f"Tracked API call: {provider}/{model} "
            f"({input_tokens}in/{output_tokens}out) = ${cost:.4f}"
        )

        return cost

    def get_daily_cost(self, provider: Optional[str] = None) -> float:
        """
        Get today's total cost.

        Args:
            provider: Optional provider to filter by

        Returns:
            Total cost in USD
        """
        return self._storage.get_daily_total(date.today(), provider=provider)

    def get_monthly_cost(self, provider: Optional[str] = None) -> float:
        """
        Get current month's total cost.

        Args:
            provider: Optional provider to filter by

        Returns:
            Total cost in USD
        """
        return self._storage.get_monthly_total(provider=provider)

    def check_budget(self, provider: Optional[str] = None) -> bool:
        """
        Check if currently under daily budget.

        Args:
            provider: Optional provider to check specific limit

        Returns:
            True if under budget, False if at or over limit
        """
        current = self.get_daily_cost(provider=provider)
        return current < self._daily_limit

    def check_budget_warning(
        self,
        threshold: float = 0.8,
        provider: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Check budget and return detailed warning status.

        Args:
            threshold: Percentage of limit to trigger warning (0.0-1.0)
            provider: Optional provider to check

        Returns:
            Dict with budget status information
        """
        current = self.get_daily_cost(provider=provider)
        percentage = current / self._daily_limit if self._daily_limit > 0 else 0

        status = {
            "current_spend": current,
            "daily_limit": self._daily_limit,
            "percentage": percentage,
            "under_budget": current < self._daily_limit,
            "warning": percentage >= threshold,
            "status": "ok",
        }

        if current >= self._daily_limit:
            status["status"] = "over_limit"
        elif percentage >= threshold:
            status["status"] = "warning"

        return status

    def alert_if_over_budget(self) -> Dict[str, Any]:
        """
        Send alert if over daily budget.

        Returns:
            Dict with budget status and alert info
        """
        current = self.get_daily_cost()
        over_budget = current >= self._daily_limit

        result = {
            "over_budget": over_budget,
            "current_spend": current,
            "daily_limit": self._daily_limit,
            "alert_sent": False,
        }

        if over_budget:
            # Reset alert flag if it's a new day
            today = date.today()
            if self._last_alert_date != today:
                self._alert_sent_today = False
                self._last_alert_date = today

            # Send alert if not already sent today
            if not self._alert_sent_today:
                self._send_alert(result)
                self._alert_sent_today = True
                result["alert_sent"] = True

        return result

    def _send_alert(self, budget_info: Dict[str, Any]) -> None:
        """
        Send a budget alert.

        Args:
            budget_info: Dict with budget status information
        """
        message = (
            f"API Cost Alert: Daily budget exceeded!\n"
            f"Current spend: ${budget_info['current_spend']:.2f}\n"
            f"Daily limit: ${budget_info['daily_limit']:.2f}"
        )

        logger.warning(message)

        if self._alert_callback:
            try:
                self._alert_callback(budget_info)
            except Exception as e:
                logger.error(f"Alert callback failed: {e}")

    def get_summary(self) -> Dict[str, Any]:
        """
        Get a summary of current cost status.

        Returns:
            Dict with comprehensive cost summary
        """
        daily = self.get_daily_cost()
        monthly = self.get_monthly_cost()
        by_provider = self._storage.get_monthly_by_provider()

        return {
            "daily_cost": daily,
            "daily_limit": self._daily_limit,
            "daily_remaining": max(0, self._daily_limit - daily),
            "daily_percentage": (daily / self._daily_limit * 100) if self._daily_limit > 0 else 0,
            "monthly_cost": monthly,
            "by_provider": by_provider,
            "under_budget": daily < self._daily_limit,
        }


# Global tracker instance
_global_tracker: Optional[CostTracker] = None


def get_cost_tracker(
    daily_limit: Optional[float] = None,
    force_new: bool = False,
) -> CostTracker:
    """
    Get the global CostTracker instance.

    Args:
        daily_limit: Optional daily limit override
        force_new: Create a new instance even if one exists

    Returns:
        CostTracker instance
    """
    global _global_tracker

    if _global_tracker is None or force_new:
        limit = daily_limit if daily_limit is not None else DEFAULT_DAILY_LIMIT
        _global_tracker = CostTracker(daily_limit=limit)

    return _global_tracker
