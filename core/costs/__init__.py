"""
API Cost Tracking System for Jarvis.

Provides:
- CostCalculator: Calculate API costs based on model pricing
- CostStorage: Persist daily cost data to JSON files
- CostTracker: Track API calls and check budget limits
- Report functions: Generate daily/monthly cost reports

Usage:
    from core.costs import get_cost_tracker, CostCalculator

    # Track an API call
    tracker = get_cost_tracker()
    cost = tracker.track_call(
        provider="openai",
        model="gpt-4o",
        input_tokens=1000,
        output_tokens=500
    )

    # Check if under budget
    if tracker.check_budget():
        # Safe to make more API calls
        pass

    # Generate a report
    from core.costs.report import generate_daily_report
    report = generate_daily_report()
"""

from core.costs.calculator import CostCalculator, MODEL_PRICING
from core.costs.storage import CostStorage, DEFAULT_STORAGE_DIR
from core.costs.tracker import CostTracker, get_cost_tracker
from core.costs.report import (
    generate_daily_report,
    generate_monthly_report,
    format_currency,
    format_percentage,
    format_tokens,
)

__all__ = [
    # Calculator
    "CostCalculator",
    "MODEL_PRICING",
    # Storage
    "CostStorage",
    "DEFAULT_STORAGE_DIR",
    # Tracker
    "CostTracker",
    "get_cost_tracker",
    # Report
    "generate_daily_report",
    "generate_monthly_report",
    "format_currency",
    "format_percentage",
    "format_tokens",
]
