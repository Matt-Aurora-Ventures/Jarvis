"""
Jarvis Economic Loop.

This module tracks costs and revenue to ensure Jarvis pays for itself.

Components:
- CostTracker: Logs all API calls, compute, and operational costs
- RevenueTracker: Tracks trading profits and time savings
- PnLDatabase: SQLite storage for economic metrics
- EconomicDashboard: Real-time P&L visibility

The goal: Jarvis generates more value than it costs to run.
"""

from core.economics.costs import CostTracker, get_cost_tracker, log_api_cost
from core.economics.revenue import RevenueTracker, get_revenue_tracker, log_revenue
from core.economics.database import EconomicsDB, get_economics_db
from core.economics.dashboard import EconomicsDashboard, get_pnl_summary

__all__ = [
    "CostTracker",
    "get_cost_tracker",
    "log_api_cost",
    "RevenueTracker",
    "get_revenue_tracker",
    "log_revenue",
    "EconomicsDB",
    "get_economics_db",
    "EconomicsDashboard",
    "get_pnl_summary",
]
