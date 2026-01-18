"""
Token Dashboard UI components.

Provides:
- Token dashboard formatting
- Token comparison formatting
- Watchlist display formatting
"""

import logging
from typing import Any, Dict, List

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

logger = logging.getLogger(__name__)


def format_token_dashboard(token_data: Dict[str, Any]) -> str:
    """
    Format a token dashboard message.

    Shows key metrics in a compact dashboard format.
    """
    lines = []

    symbol = token_data.get("symbol", "???")
    grade = token_data.get("grade", "?")
    score = token_data.get("score", 0)
    price = token_data.get("price_usd", 0)
    volume = token_data.get("volume_24h", 0)
    liquidity = token_data.get("liquidity_usd", 0)

    # Header with grade
    lines.append(f"*{symbol} Analysis* (Grade: {grade})")
    lines.append("")

    # Price formatting
    if price >= 1:
        price_str = f"${price:.2f}"
    elif price >= 0.01:
        price_str = f"${price:.4f}"
    else:
        price_str = f"${price:.8f}"

    # Volume/Liquidity formatting
    if volume >= 1_000_000_000:
        vol_str = f"${volume / 1_000_000_000:.1f}B"
    elif volume >= 1_000_000:
        vol_str = f"${volume / 1_000_000:.1f}M"
    else:
        vol_str = f"${volume / 1_000:.0f}K"

    if liquidity >= 1_000_000_000:
        liq_str = f"${liquidity / 1_000_000_000:.1f}B"
    elif liquidity >= 1_000_000:
        liq_str = f"${liquidity / 1_000_000:.1f}M"
    else:
        liq_str = f"${liquidity / 1_000:.0f}K"

    lines.append(f"Price: {price_str} | Vol: {vol_str} | Liq: {liq_str}")

    if score:
        lines.append(f"Score: {score}/100")

    return "\n".join(lines)


def format_token_comparison(tokens: List[Dict[str, Any]]) -> str:
    """
    Format a token comparison table.

    Shows side-by-side comparison of multiple tokens.
    """
    lines = []

    lines.append("*Token Comparison*")
    lines.append("")

    # Header row
    lines.append("```")
    lines.append(f"{'Token':<8} {'Grade':<6} {'Score':<6} {'Vol(24h)':<10} {'Liq':<8} {'Risk':<10}")
    lines.append("-" * 58)

    for token in tokens:
        symbol = token.get("symbol", "???")[:7]
        grade = token.get("grade", "?")
        score = token.get("score", 0)
        volume = token.get("volume_24h", 0)
        liquidity = token.get("liquidity_usd", 0)
        risk = token.get("risk", "Unknown")

        # Format volume
        if volume >= 1_000_000_000:
            vol_str = f"${volume / 1_000_000_000:.1f}B"
        elif volume >= 1_000_000:
            vol_str = f"${volume / 1_000_000:.1f}M"
        else:
            vol_str = f"${volume / 1_000:.0f}K"

        # Format liquidity
        if liquidity >= 1_000_000_000:
            liq_str = f"${liquidity / 1_000_000_000:.1f}B"
        elif liquidity >= 1_000_000:
            liq_str = f"${liquidity / 1_000_000:.1f}M"
        else:
            liq_str = f"${liquidity / 1_000:.0f}K"

        lines.append(f"{symbol:<8} {grade:<6} {score:<6} {vol_str:<10} {liq_str:<8} {risk:<10}")

    lines.append("```")

    return "\n".join(lines)


def format_watchlist(
    watchlist: List[Dict[str, Any]],
    prices: Dict[str, Dict[str, Any]] = None,
) -> str:
    """
    Format watchlist display.

    Shows saved tokens with current status.
    """
    lines = []

    lines.append(f"*Your Watchlist* ({len(watchlist)} tokens)")
    lines.append("")

    if not watchlist:
        lines.append("_Your watchlist is empty_")
        lines.append("")
        lines.append("Add tokens with the button below")
        return "\n".join(lines)

    prices = prices or {}

    for item in watchlist:
        symbol = item.get("symbol", "???")
        address = item.get("address", "")

        # Get current price data if available
        price_data = prices.get(address, {})
        price = price_data.get("price_usd", 0)
        change = price_data.get("price_change_24h", 0)

        # Status indicator based on change
        if change > 5:
            status = ""
        elif change > 0:
            status = ""
        elif change < -5:
            status = ""
        elif change < 0:
            status = ""
        else:
            status = ""

        # Format price
        if price > 0:
            if price >= 1:
                price_str = f"${price:.2f}"
            elif price >= 0.01:
                price_str = f"${price:.4f}"
            else:
                price_str = f"${price:.6f}"

            change_str = f"{'+'if change >= 0 else ''}{change:.1f}%"
            lines.append(f"{status} *{symbol}* - {price_str} {change_str}")
        else:
            lines.append(f"{status} *{symbol}*")

    return "\n".join(lines)


def build_compare_keyboard(token_symbols: List[str]) -> InlineKeyboardMarkup:
    """Build keyboard for compare command."""
    token_str = ",".join(token_symbols[:5])

    keyboard = [
        [
            InlineKeyboardButton("Sort by Grade", callback_data=f"compare_sort:grade:{token_str}"),
            InlineKeyboardButton("Sort by Risk", callback_data=f"compare_sort:risk:{token_str}"),
        ],
        [
            InlineKeyboardButton("Compare Details", callback_data=f"compare_details:{token_str}"),
            InlineKeyboardButton("Close", callback_data="ui_close:compare"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


async def get_grade_for_token(token_address: str) -> str:
    """
    Calculate a letter grade for a token based on various metrics.

    Returns: A+, A, B, C, D, or F
    """
    try:
        from tg_bot.services.signal_service import get_signal_service

        service = get_signal_service()
        signal = await service.get_comprehensive_signal(token_address, include_sentiment=False)

        # Calculate grade based on signal score and other factors
        score = signal.signal_score

        # Adjust based on risk
        if signal.risk_level == "critical":
            return "F"
        elif signal.risk_level == "high":
            score -= 20

        # Adjust based on liquidity
        if signal.liquidity_usd < 10_000:
            score -= 30
        elif signal.liquidity_usd < 100_000:
            score -= 10
        elif signal.liquidity_usd > 10_000_000:
            score += 10

        # Grade thresholds
        if score >= 60:
            return "A+"
        elif score >= 40:
            return "A"
        elif score >= 20:
            return "B"
        elif score >= 0:
            return "C"
        elif score >= -20:
            return "D"
        else:
            return "F"

    except Exception as e:
        logger.warning(f"Failed to calculate grade: {e}")
        return "?"


async def get_risk_for_token(token_address: str) -> str:
    """Get risk assessment for a token."""
    try:
        from tg_bot.services.signal_service import get_signal_service

        service = get_signal_service()
        signal = await service.get_comprehensive_signal(token_address, include_sentiment=False)

        risk_level = signal.risk_level

        # Map to display string
        risk_map = {
            "low": "Low",
            "medium": "Medium",
            "high": "High",
            "critical": "Very High",
        }

        return risk_map.get(risk_level, "Unknown")

    except Exception as e:
        logger.warning(f"Failed to get risk: {e}")
        return "Unknown"


__all__ = [
    "format_token_dashboard",
    "format_token_comparison",
    "format_watchlist",
    "build_compare_keyboard",
    "get_grade_for_token",
    "get_risk_for_token",
]
