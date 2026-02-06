"""
Cost Report Generation.

Generates daily and monthly cost reports with optional Telegram integration.
"""

import logging
from datetime import date, datetime
from typing import Any, Dict, List, Optional


logger = logging.getLogger(__name__)


def format_currency(amount: float) -> str:
    """
    Format an amount as currency.

    Args:
        amount: Amount in USD

    Returns:
        Formatted string (e.g., "$5.50", "$1,500.00")
    """
    if amount >= 1000:
        return f"${amount:,.2f}"
    elif amount < 0.01:
        return f"${amount:.4f}"
    return f"${amount:.2f}"


def format_percentage(current: float, total: float) -> str:
    """
    Format a value as a percentage of a total.

    Args:
        current: Current value
        total: Total/maximum value

    Returns:
        Formatted percentage string
    """
    if total <= 0:
        return "0%"
    percentage = (current / total) * 100
    return f"{percentage:.0f}%"


def format_tokens(count: int) -> str:
    """
    Format a token count for display.

    Args:
        count: Number of tokens

    Returns:
        Formatted string (e.g., "1K", "1.5M")
    """
    if count >= 1_000_000:
        return f"{count / 1_000_000:.1f}M"
    elif count >= 1000:
        return f"{count / 1000:.0f}K"
    return str(count)


def generate_daily_report(
    tracker: Optional["CostTracker"] = None,
    target_date: Optional[date] = None,
) -> str:
    """
    Generate a daily cost report.

    Args:
        tracker: CostTracker instance (uses global if not provided)
        target_date: Date to report on (defaults to today)

    Returns:
        Formatted report string
    """
    if tracker is None:
        from core.costs.tracker import get_cost_tracker
        tracker = get_cost_tracker()

    if target_date is None:
        target_date = date.today()

    # Get data
    entries = tracker.storage.load_daily(target_date)
    daily_total = tracker.storage.get_daily_total(target_date)
    daily_limit = tracker.daily_limit

    # Aggregate by provider
    by_provider: Dict[str, Dict[str, Any]] = {}
    total_input_tokens = 0
    total_output_tokens = 0

    for entry in entries:
        provider = entry.get("provider", "unknown")
        if provider not in by_provider:
            by_provider[provider] = {
                "cost": 0.0,
                "calls": 0,
                "input_tokens": 0,
                "output_tokens": 0,
            }
        by_provider[provider]["cost"] += entry.get("cost_usd", 0)
        by_provider[provider]["calls"] += 1
        by_provider[provider]["input_tokens"] += entry.get("input_tokens", 0)
        by_provider[provider]["output_tokens"] += entry.get("output_tokens", 0)

        total_input_tokens += entry.get("input_tokens", 0)
        total_output_tokens += entry.get("output_tokens", 0)

    # Build report
    lines = []
    lines.append(f"API Cost Report - Daily")
    lines.append(f"Date: {target_date.isoformat()}")
    lines.append("")
    lines.append(f"Total Spend: {format_currency(daily_total)}")
    lines.append(f"Daily Limit: {format_currency(daily_limit)}")
    lines.append(f"Budget Used: {format_percentage(daily_total, daily_limit)}")
    lines.append("")

    if entries:
        lines.append(f"API Calls: {len(entries)}")
        lines.append(f"Total Tokens: {format_tokens(total_input_tokens + total_output_tokens)}")
        lines.append("")

        lines.append("By Provider:")
        for provider, stats in sorted(by_provider.items(), key=lambda x: -x[1]["cost"]):
            lines.append(
                f"  {provider.capitalize()}: {format_currency(stats['cost'])} "
                f"({stats['calls']} calls, {format_tokens(stats['input_tokens'] + stats['output_tokens'])} tokens)"
            )
    else:
        lines.append("No API calls recorded today.")

    # Budget status
    lines.append("")
    if daily_total >= daily_limit:
        lines.append("Status: OVER BUDGET")
    elif daily_total >= daily_limit * 0.8:
        lines.append("Status: Warning - approaching limit")
    else:
        lines.append("Status: OK")

    return "\n".join(lines)


def generate_monthly_report(
    tracker: Optional["CostTracker"] = None,
    year: Optional[int] = None,
    month: Optional[int] = None,
) -> str:
    """
    Generate a monthly cost report.

    Args:
        tracker: CostTracker instance (uses global if not provided)
        year: Year to report on (defaults to current)
        month: Month to report on (defaults to current)

    Returns:
        Formatted report string
    """
    if tracker is None:
        from core.costs.tracker import get_cost_tracker
        tracker = get_cost_tracker()

    today = date.today()
    if year is None:
        year = today.year
    if month is None:
        month = today.month

    # Get month name
    month_name = datetime(year, month, 1).strftime("%B %Y")

    # Get data
    monthly_total = tracker.storage.get_monthly_total(year, month)
    by_provider = tracker.storage.get_monthly_by_provider(year, month)
    by_day = tracker.storage.get_monthly_by_day(year, month)

    # Calculate stats
    days_with_data = len(by_day)
    average_daily = monthly_total / days_with_data if days_with_data > 0 else 0

    # Build report
    lines = []
    lines.append(f"API Cost Report - Monthly")
    lines.append(f"Month: {month_name}")
    lines.append("")
    lines.append(f"Total Spend: {format_currency(monthly_total)}")
    lines.append(f"Days Tracked: {days_with_data}")
    lines.append(f"Average Daily: {format_currency(average_daily)}")
    lines.append("")

    if by_provider:
        lines.append("By Provider:")
        for provider, cost in sorted(by_provider.items(), key=lambda x: -x[1]):
            percentage = (cost / monthly_total * 100) if monthly_total > 0 else 0
            lines.append(f"  {provider.capitalize()}: {format_currency(cost)} ({percentage:.1f}%)")
    else:
        lines.append("No cost data for this month.")

    # Daily trend (last 7 days of the month)
    if by_day:
        lines.append("")
        lines.append("Recent Daily Trend:")
        sorted_days = sorted(by_day.items(), reverse=True)[:7]
        for day_str, cost in sorted_days:
            lines.append(f"  {day_str}: {format_currency(cost)}")

    return "\n".join(lines)


async def send_daily_report_telegram(
    chat_id: int,
    tracker: Optional["CostTracker"] = None,
) -> bool:
    """
    Send daily report to Telegram.

    Args:
        chat_id: Telegram chat ID to send to
        tracker: CostTracker instance (uses global if not provided)

    Returns:
        True if sent successfully, False otherwise
    """
    try:
        client = get_telegram_client()
        if client is None:
            logger.warning("Telegram client not available for cost report")
            return False

        report = generate_daily_report(tracker=tracker)
        await client.send_message(chat_id=chat_id, text=report)
        return True

    except Exception as e:
        logger.error(f"Failed to send daily cost report to Telegram: {e}")
        return False


async def send_monthly_report_telegram(
    chat_id: int,
    tracker: Optional["CostTracker"] = None,
) -> bool:
    """
    Send monthly report to Telegram.

    Args:
        chat_id: Telegram chat ID to send to
        tracker: CostTracker instance (uses global if not provided)

    Returns:
        True if sent successfully, False otherwise
    """
    try:
        client = get_telegram_client()
        if client is None:
            logger.warning("Telegram client not available for cost report")
            return False

        report = generate_monthly_report(tracker=tracker)
        await client.send_message(chat_id=chat_id, text=report)
        return True

    except Exception as e:
        logger.error(f"Failed to send monthly cost report to Telegram: {e}")
        return False


def get_telegram_client():
    """
    Get a Telegram client instance.

    Returns:
        Telegram client or None if not available
    """
    try:
        # Try to import Telegram bot
        from telegram import Bot
        from tg_bot.config import get_config

        config = get_config()
        if config.telegram_token:
            return Bot(token=config.telegram_token)
    except ImportError:
        pass
    except Exception as e:
        logger.debug(f"Could not get Telegram client: {e}")

    return None
