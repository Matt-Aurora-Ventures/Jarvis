"""
Drill-down analysis handlers for interactive token analysis.

Provides formatting and data fetching for:
- Holder distribution views
- Recent trades views
- Chart views
- Trading signal views
- Detailed tokenomics views
"""

import logging
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# =============================================================================
# Data Fetching
# =============================================================================


async def fetch_holder_data(token_address: str) -> List[Dict[str, Any]]:
    """
    Fetch holder distribution data for a token.

    Returns list of holder entries with address, percentage, and amount.
    """
    try:
        from core.data.solscan_api import get_solscan_api

        api = get_solscan_api()
        holders = await api.get_token_holders(token_address, limit=100)
        if not holders:
            return []

        results: List[Dict[str, Any]] = []
        for holder in holders:
            amount_tokens = int(getattr(holder, "amount_formatted", 0) or 0)
            results.append(
                {
                    "address": getattr(holder, "owner", ""),
                    "percentage": round(float(getattr(holder, "percentage", 0) or 0), 2),
                    "amount": amount_tokens,
                }
            )

        return results

    except Exception as e:
        logger.warning(f"Failed to fetch holder data: {e}")
        return []


async def fetch_recent_trades(token_address: str, limit: int = 20) -> List[Dict[str, Any]]:
    """
    Fetch recent trades for a token.

    Returns list of trade entries with type, amount, time, and whale status.
    """
    try:
        from core.data.solscan_api import get_solscan_api

        api = get_solscan_api()
        txs = await api.get_recent_transactions(token_address, limit=limit)
        if not txs:
            return []

        trades: List[Dict[str, Any]] = []
        for tx in txs:
            tx_type = str(getattr(tx, "tx_type", "") or "").lower()
            trade_type = "sell" if "sell" in tx_type else "buy"
            amount = int(abs(float(getattr(tx, "amount", 0) or 0)))
            trades.append(
                {
                    "type": trade_type,
                    "amount_usd": amount,
                    "time": _format_time_ago(int(getattr(tx, "block_time", 0) or 0)),
                    "is_whale": amount >= 50_000,
                }
            )

        return trades[:limit]

    except Exception as e:
        logger.warning(f"Failed to fetch trades: {e}")
        return []


async def fetch_token_details(token_address: str) -> Dict[str, Any]:
    """Fetch detailed tokenomics for a token."""
    try:
        from tg_bot.services.signal_service import get_signal_service

        service = get_signal_service()
        signal = await service.get_comprehensive_signal(token_address, include_sentiment=False)

        return {
            "symbol": signal.symbol,
            "name": signal.name,
            "price_usd": signal.price_usd,
            "price_change_1h": signal.price_change_1h,
            "price_change_24h": signal.price_change_24h,
            "volume_24h": signal.volume_24h,
            "liquidity_usd": signal.liquidity_usd,
            "security_score": signal.security_score,
            "risk_level": signal.risk_level,
            "smart_money_signal": signal.smart_money_signal,
            "address": token_address,
        }

    except Exception as e:
        logger.warning(f"Failed to fetch token details: {e}")
        return {
            "symbol": "???",
            "name": "Unknown",
            "price_usd": 0.0,
            "address": token_address,
        }


def _generate_mock_holders(token_address: str) -> List[Dict[str, Any]]:
    """Generate mock holder data for testing."""
    import hashlib

    # Deterministic mock data based on address
    h = int(hashlib.md5(token_address.encode()).hexdigest()[:8], 16)

    holders = []
    remaining = 100.0

    for i in range(100):
        if remaining <= 0.01:
            break

        # Decreasing percentages
        pct = min(remaining, max(0.01, remaining * (0.5 - i * 0.004)))
        remaining -= pct

        addr_seed = (h + i) % 0xFFFFFFFF
        mock_addr = f"0x{addr_seed:08x}...{(addr_seed ^ 0xFFFF):04x}"

        holders.append({
            "address": mock_addr,
            "percentage": round(pct, 2),
            "amount": int(pct * 1_000_000),  # Mock amount
        })

    return holders


def _generate_mock_trades(token_address: str, limit: int = 20) -> List[Dict[str, Any]]:
    """Generate mock trade data for testing."""
    import hashlib
    import random

    h = int(hashlib.md5(token_address.encode()).hexdigest()[:8], 16)
    random.seed(h)

    trades = []
    times = ["1m ago", "2m ago", "5m ago", "10m ago", "15m ago", "30m ago", "1h ago"]

    for i in range(limit):
        trade_type = "buy" if random.random() > 0.45 else "sell"
        amount = random.randint(100, 100000)
        is_whale = amount > 50000

        trades.append({
            "type": trade_type,
            "amount_usd": amount,
            "time": times[min(i // 3, len(times) - 1)],
            "is_whale": is_whale,
        })

    return trades


def _format_time_ago(block_time: int) -> str:
    """Format unix timestamp into short relative age string."""
    if block_time <= 0:
        return "unknown"

    age_s = max(0, int(time.time()) - block_time)
    if age_s < 60:
        return f"{age_s}s ago"
    if age_s < 3600:
        return f"{age_s // 60}m ago"
    if age_s < 86400:
        return f"{age_s // 3600}h ago"
    return f"{age_s // 86400}d ago"


# =============================================================================
# View Formatting
# =============================================================================


def format_holders_view(
    token_address: str,
    holders: List[Dict[str, Any]],
    page: int = 1,
    total_pages: int = 1,
) -> str:
    """
    Format holder distribution view.

    Shows ranked list of holders with percentages.
    """
    lines = []

    # Header
    lines.append("*Top Holders*")
    lines.append(f"Page {page}/{total_pages}")
    lines.append("")

    if not holders:
        lines.append("_No holder data available_")
        return "\n".join(lines)

    # Calculate starting rank based on page
    start_rank = (page - 1) * 25 + 1

    for i, holder in enumerate(holders, start_rank):
        addr = holder.get("address", "???")
        pct = holder.get("percentage", 0)
        amount = holder.get("amount", 0)

        # Format amount
        if amount >= 1_000_000:
            amount_str = f"{amount / 1_000_000:.1f}M"
        elif amount >= 1_000:
            amount_str = f"{amount / 1_000:.1f}K"
        else:
            amount_str = str(amount)

        # Whale emoji for top holders
        whale = "" if pct >= 10 else ""

        lines.append(f"{i}. `{addr}` {whale}")
        lines.append(f"   {pct:.1f}% ({amount_str})")

    return "\n".join(lines)


def format_trades_view(
    token_address: str,
    trades: List[Dict[str, Any]],
) -> str:
    """
    Format recent trades view.

    Shows list of recent trades with type, amount, and whale indicators.
    """
    lines = []

    lines.append("*Recent Trades*")
    lines.append("")

    if not trades:
        lines.append("_No trade data available_")
        return "\n".join(lines)

    for trade in trades:
        trade_type = trade.get("type", "unknown")
        amount = trade.get("amount_usd", 0)
        time = trade.get("time", "")
        is_whale = trade.get("is_whale", False)

        # Type emoji
        type_emoji = "" if trade_type == "buy" else ""

        # Whale indicator
        whale = " " if is_whale else ""

        # Format amount
        if amount >= 1_000_000:
            amount_str = f"${amount / 1_000_000:.1f}M"
        elif amount >= 1_000:
            amount_str = f"${amount / 1_000:.1f}K"
        else:
            amount_str = f"${amount:.0f}"

        lines.append(f"{type_emoji} {trade_type.upper()} {amount_str}{whale} - {time}")

    return "\n".join(lines)


def format_chart_view(token_address: str) -> str:
    """Format chart view message."""
    lines = []

    lines.append("*Price Chart*")
    lines.append("")
    lines.append("Select timeframe or open external chart:")
    lines.append("")
    lines.append(f"[DexScreener](https://dexscreener.com/solana/{token_address})")
    lines.append(f"[Birdeye](https://birdeye.so/token/{token_address}?chain=solana)")

    return "\n".join(lines)


async def format_signal_view(token_address: str) -> str:
    """
    Format trading signal view.

    Shows breakdown of signal sources and overall recommendation.
    """
    try:
        from tg_bot.services.signal_service import get_signal_service

        service = get_signal_service()
        signal = await service.get_comprehensive_signal(token_address, include_sentiment=True)

        lines = []

        lines.append(f"*Trading Signals for {signal.symbol}*")
        lines.append("")

        # Signal components
        lines.append("Sentiment: ", end="")
        if signal.sentiment == "positive":
            lines.append(f"{int(signal.sentiment_confidence * 100)}/100 ")
        elif signal.sentiment == "negative":
            lines.append(f"{int(signal.sentiment_confidence * 100)}/100 ")
        else:
            lines.append("Neutral")

        # Security
        if signal.risk_level == "low":
            lines.append(f"Security: {signal.security_score:.0f}/100 ")
        elif signal.risk_level == "critical":
            lines.append(f"Security: {signal.security_score:.0f}/100 ")
        else:
            lines.append(f"Security: {signal.security_score:.0f}/100 ")

        # Smart money
        if signal.smart_money_signal == "bullish":
            lines.append("Smart Money: Bullish ")
        elif signal.smart_money_signal == "bearish":
            lines.append("Smart Money: Bearish ")
        else:
            lines.append("Smart Money: Neutral")

        lines.append("")
        lines.append(f"*Overall: {signal.signal}* ({signal.signal_score:+.0f}/100)")

        if signal.signal_reasons:
            lines.append("")
            for reason in signal.signal_reasons[:5]:
                lines.append(f"- {reason}")

        return "\n".join(lines)

    except Exception as e:
        logger.warning(f"Failed to format signal view: {e}")
        return "*Trading Signals*\n\n_Unable to load signal data_"


async def format_details_view(token_address: str) -> str:
    """Format detailed tokenomics view."""
    details = await fetch_token_details(token_address)

    lines = []

    symbol = details.get("symbol", "???")
    name = details.get("name", "Unknown")

    lines.append(f"*{symbol} - {name}*")
    lines.append("")

    # Address
    lines.append(f"`{token_address}`")
    lines.append("")

    # Price
    price = details.get("price_usd", 0)
    if price >= 1:
        lines.append(f"*Price:* ${price:.4f}")
    else:
        lines.append(f"*Price:* ${price:.8f}")

    # Changes
    change_1h = details.get("price_change_1h", 0)
    change_24h = details.get("price_change_24h", 0)
    lines.append(f"*1H Change:* {change_1h:+.1f}%")
    lines.append(f"*24H Change:* {change_24h:+.1f}%")

    lines.append("")

    # Volume and liquidity
    volume = details.get("volume_24h", 0)
    liquidity = details.get("liquidity_usd", 0)

    if volume >= 1_000_000:
        lines.append(f"*Volume 24H:* ${volume / 1_000_000:.1f}M")
    elif volume >= 1_000:
        lines.append(f"*Volume 24H:* ${volume / 1_000:.1f}K")
    else:
        lines.append(f"*Volume 24H:* ${volume:.0f}")

    if liquidity >= 1_000_000:
        lines.append(f"*Liquidity:* ${liquidity / 1_000_000:.1f}M")
    elif liquidity >= 1_000:
        lines.append(f"*Liquidity:* ${liquidity / 1_000:.1f}K")
    else:
        lines.append(f"*Liquidity:* ${liquidity:.0f}")

    lines.append("")

    # Security
    security_score = details.get("security_score", 0)
    risk_level = details.get("risk_level", "unknown")
    smart_money = details.get("smart_money_signal", "neutral")

    lines.append(f"*Security Score:* {security_score:.0f}/100")
    lines.append(f"*Risk Level:* {risk_level.upper()}")
    lines.append(f"*Smart Money:* {smart_money.capitalize()}")

    lines.append("")

    # Links
    lines.append("*Links:*")
    lines.append(f"[DexScreener](https://dexscreener.com/solana/{token_address})")
    lines.append(f"[Birdeye](https://birdeye.so/token/{token_address}?chain=solana)")
    lines.append(f"[Solscan](https://solscan.io/token/{token_address})")

    return "\n".join(lines)


async def format_main_analysis(token_address: str, token_symbol: str = "") -> str:
    """Format main analysis view (the initial dashboard)."""
    try:
        from tg_bot.services.signal_service import get_signal_service
        from tg_bot.services.digest_formatter import format_single_analysis

        service = get_signal_service()
        signal = await service.get_comprehensive_signal(
            token_address,
            symbol=token_symbol,
            include_sentiment=False,  # Don't use API on back navigation
        )

        # Use existing formatter but add interactive hint
        base_message = format_single_analysis(signal)

        # Add interactive hint
        lines = [base_message, "", "_Use buttons below to drill down_"]

        return "\n".join(lines)

    except Exception as e:
        logger.warning(f"Failed to format main analysis: {e}")
        return f"*Analysis*\n\n`{token_address}`\n\n_Unable to load data_"


__all__ = [
    "fetch_holder_data",
    "fetch_recent_trades",
    "fetch_token_details",
    "format_holders_view",
    "format_trades_view",
    "format_chart_view",
    "format_signal_view",
    "format_details_view",
    "format_main_analysis",
]
