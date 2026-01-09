"""
Beautiful Digest Formatter for Telegram.

Creates visually appealing, information-rich reports with:
- Clean formatting using Telegram markdown
- Quick-access links to charts and explorers
- Color-coded signals and risk levels
- Cost tracking summary
"""

from datetime import datetime, timezone
from typing import List, Optional

from tg_bot.services.signal_service import TokenSignal
from tg_bot.services.cost_tracker import get_tracker


# Signal emojis
SIGNAL_EMOJI = {
    "STRONG_BUY": "🟢🟢",
    "BUY": "🟢",
    "NEUTRAL": "⚪",
    "SELL": "🔴",
    "STRONG_SELL": "🔴🔴",
    "AVOID": "☠️",
}

# Risk emojis
RISK_EMOJI = {
    "low": "🛡️",
    "medium": "⚠️",
    "high": "🚨",
    "critical": "☠️",
    "unknown": "❓",
}

# Sentiment emojis
SENTIMENT_EMOJI = {
    "positive": "😀",
    "neutral": "😐",
    "negative": "😟",
    "mixed": "🤔",
}


def format_price(value: float) -> str:
    """Format price for display."""
    if value >= 1000:
        return f"${value:,.0f}"
    elif value >= 1:
        return f"${value:.2f}"
    elif value >= 0.01:
        return f"${value:.4f}"
    else:
        return f"${value:.8f}"


def format_volume(value: float) -> str:
    """Format volume/liquidity for display."""
    if value >= 1_000_000:
        return f"${value/1_000_000:.2f}M"
    elif value >= 1_000:
        return f"${value/1_000:.1f}K"
    else:
        return f"${value:.0f}"


def format_change(value: float) -> str:
    """Format percentage change with arrow."""
    if value > 0:
        return f"📈 +{value:.1f}%"
    elif value < 0:
        return f"📉 {value:.1f}%"
    else:
        return f"➡️ 0%"


def get_dexscreener_link(address: str) -> str:
    """Get DexScreener link for token."""
    return f"https://dexscreener.com/solana/{address}"


def get_birdeye_link(address: str) -> str:
    """Get Birdeye link for token."""
    return f"https://birdeye.so/token/{address}?chain=solana"


def get_solscan_link(address: str) -> str:
    """Get Solscan link for token."""
    return f"https://solscan.io/token/{address}"


def format_token_card(signal: TokenSignal, rank: int = 0) -> str:
    """
    Format a single token as a beautiful card.

    Returns Telegram markdown formatted string.
    """
    lines = []

    # Header with rank and symbol
    sig_emoji = SIGNAL_EMOJI.get(signal.signal, "⚪")
    if rank > 0:
        lines.append(f"*{rank}. {signal.symbol}* {sig_emoji}")
    else:
        lines.append(f"*{signal.symbol}* {sig_emoji}")

    if signal.name:
        lines.append(f"_{signal.name}_")

    lines.append("")

    # Price section
    lines.append(f"💰 *Price:* {format_price(signal.price_usd)}")
    lines.append(f"   1h: {format_change(signal.price_change_1h)} | 24h: {format_change(signal.price_change_24h)}")

    # Volume & Liquidity
    lines.append(f"📊 *Volume:* {format_volume(signal.volume_24h)}/24h")
    lines.append(f"💧 *Liquidity:* {format_volume(signal.liquidity_usd)}")

    # Security
    risk_emoji = RISK_EMOJI.get(signal.risk_level, "❓")
    lines.append(f"🔒 *Security:* {risk_emoji} {signal.risk_level.upper()} ({signal.security_score:.0f}/100)")

    if signal.security_warnings:
        for warning in signal.security_warnings[:2]:
            lines.append(f"   ⚠️ {warning}")

    # Smart money
    if signal.smart_money_signal != "neutral":
        sm_emoji = "🐋" if signal.smart_money_signal == "bullish" else "🦐"
        lines.append(f"{sm_emoji} *Smart Money:* {signal.smart_money_signal.upper()}")
        if signal.insider_buys or signal.insider_sells:
            lines.append(f"   Insiders: {signal.insider_buys}↑ / {signal.insider_sells}↓")

    # Sentiment (if available)
    if signal.sentiment != "neutral" or signal.sentiment_confidence > 0:
        sent_emoji = SENTIMENT_EMOJI.get(signal.sentiment, "❓")
        lines.append(f"{sent_emoji} *Grok Sentiment:* {signal.sentiment.upper()} ({signal.sentiment_confidence:.0%})")
        if signal.sentiment_summary:
            lines.append(f"   _{signal.sentiment_summary[:100]}_")

    # Signal score
    lines.append("")
    lines.append(f"⚡ *Signal:* {signal.signal} (score: {signal.signal_score:+.0f})")

    if signal.signal_reasons:
        for reason in signal.signal_reasons[:3]:
            lines.append(f"   • {reason}")

    # Links
    lines.append("")
    lines.append(f"🔗 [DexScreener]({get_dexscreener_link(signal.address)}) | [Birdeye]({get_birdeye_link(signal.address)}) | [Solscan]({get_solscan_link(signal.address)})")

    # Sources
    if signal.sources_used:
        sources = ", ".join(signal.sources_used)
        lines.append(f"📡 _Sources: {sources}_")

    return "\n".join(lines)


def format_hourly_digest(
    signals: List[TokenSignal],
    title: str = "Hourly Signal Digest",
    include_cost: bool = True,
) -> str:
    """
    Format a complete hourly digest with multiple tokens.

    Returns Telegram markdown formatted string.
    """
    now = datetime.now(timezone.utc)
    lines = []

    # Header
    lines.append("═" * 25)
    lines.append(f"🤖 *JARVIS {title.upper()}*")
    lines.append(f"📅 {now.strftime('%Y-%m-%d %H:%M')} UTC")
    lines.append("═" * 25)
    lines.append("")

    if not signals:
        lines.append("_No signals available at this time._")
        lines.append("")
    else:
        # Summary stats
        bullish = sum(1 for s in signals if s.signal in ["BUY", "STRONG_BUY"])
        bearish = sum(1 for s in signals if s.signal in ["SELL", "STRONG_SELL"])
        avoid = sum(1 for s in signals if s.signal == "AVOID")

        lines.append(f"📊 *Summary:* {len(signals)} tokens analyzed")
        lines.append(f"   🟢 Bullish: {bullish} | 🔴 Bearish: {bearish} | ☠️ Avoid: {avoid}")
        lines.append("")

        # Top picks (if any strong signals)
        strong_buys = [s for s in signals if s.signal == "STRONG_BUY"]
        if strong_buys:
            lines.append("🌟 *TOP PICKS*")
            for sig in strong_buys[:3]:
                lines.append(f"   • {sig.symbol}: {format_price(sig.price_usd)} ({format_change(sig.price_change_1h)})")
            lines.append("")

        # Tokens to avoid
        avoids = [s for s in signals if s.signal == "AVOID"]
        if avoids:
            lines.append("⚠️ *AVOID*")
            for sig in avoids[:3]:
                warnings = sig.security_warnings[:1] if sig.security_warnings else ["High risk"]
                lines.append(f"   • {sig.symbol}: {warnings[0]}")
            lines.append("")

        lines.append("─" * 25)
        lines.append("")

        # Individual token cards
        for i, signal in enumerate(signals[:5], 1):  # Top 5 only
            lines.append(format_token_card(signal, rank=i))
            lines.append("")
            lines.append("─" * 25)
            lines.append("")

    # Cost tracking
    if include_cost:
        tracker = get_tracker()
        stats = tracker.get_today_stats()

        lines.append("💳 *API Costs Today*")
        lines.append(f"   Calls: {stats.total_calls} | Cost: ${stats.total_cost_usd:.4f}")
        lines.append(f"   Sentiment checks: {stats.sentiment_checks}/24")
        lines.append("")

    # Footer
    lines.append("─" * 25)
    lines.append("_Generated by Jarvis AI Trading Assistant_")
    lines.append("_Use /help for commands_")

    return "\n".join(lines)


def format_single_analysis(signal: TokenSignal) -> str:
    """Format a single token analysis response."""
    lines = []

    lines.append("═" * 25)
    lines.append(f"🔍 *TOKEN ANALYSIS*")
    lines.append("═" * 25)
    lines.append("")
    lines.append(format_token_card(signal))

    return "\n".join(lines)


def format_cost_report() -> str:
    """Format cost tracking report."""
    tracker = get_tracker()
    return tracker.get_cost_report()


def format_error(message: str, suggestion: str = "") -> str:
    """Format an error message."""
    lines = [
        "❌ *Error*",
        "",
        message,
    ]

    if suggestion:
        lines.extend(["", f"💡 _{suggestion}_"])

    return "\n".join(lines)


def format_rate_limit(reason: str) -> str:
    """Format rate limit message."""
    return f"⏳ *Rate Limited*\n\n{reason}\n\n_Sentiment checks are limited to preserve API costs._"


def format_unauthorized() -> str:
    """Format unauthorized access message."""
    return "🔒 *Unauthorized*\n\n_This command is restricted to admins only._"


def format_master_signal_report(signals: List[TokenSignal]) -> str:
    """
    Format the MASTER SIGNAL REPORT - comprehensive trading intelligence.

    Shows:
    - Top 10 trending tokens with clickable contracts
    - Entry recommendations (long/short term, leverage)
    - Full sentiment analysis
    - Risk assessment
    - All relevant links
    """
    now = datetime.now(timezone.utc)
    lines = []

    # Epic header
    lines.append("🚀" + "═" * 30 + "🚀")
    lines.append("")
    lines.append("⚡ *JARVIS MASTER SIGNAL REPORT* ⚡")
    lines.append(f"🕐 {now.strftime('%Y-%m-%d %H:%M')} UTC")
    lines.append("")
    lines.append("🚀" + "═" * 30 + "🚀")
    lines.append("")

    if not signals:
        lines.append("_No signals available. Markets may be closed or data unavailable._")
        return "\n".join(lines)

    # Quick summary bar
    strong_buys = [s for s in signals if s.signal == "STRONG_BUY"]
    buys = [s for s in signals if s.signal == "BUY"]
    sells = [s for s in signals if s.signal in ["SELL", "STRONG_SELL"]]
    avoids = [s for s in signals if s.signal == "AVOID"]

    lines.append("📊 *MARKET OVERVIEW*")
    lines.append(f"   🟢 Strong Buy: {len(strong_buys)} | 🟢 Buy: {len(buys)}")
    lines.append(f"   🔴 Sell: {len(sells)} | ☠️ Avoid: {len(avoids)}")
    lines.append("")

    # TOP ENTRIES section
    if strong_buys or buys:
        lines.append("🎯 *TOP ENTRIES - WHAT JARVIS WOULD BUY*")
        lines.append("─" * 30)
        for sig in (strong_buys + buys)[:3]:
            entry_type = _get_entry_recommendation(sig)
            lines.append(f"   🏆 *{sig.symbol}* - {entry_type}")
        lines.append("")

    # Main token list
    lines.append("📈 *TOP 10 TRENDING TOKENS*")
    lines.append("─" * 30)
    lines.append("")

    for i, sig in enumerate(signals[:10], 1):
        lines.append(_format_master_token_entry(sig, i))
        lines.append("")

    # Trading recommendations summary
    lines.append("─" * 30)
    lines.append("")
    lines.append("💡 *JARVIS TRADING RECOMMENDATIONS*")
    lines.append("")

    # Best long-term holds
    long_term = [s for s in signals if s.liquidity_usd > 1_000_000 and s.signal in ["BUY", "STRONG_BUY"]]
    if long_term:
        lines.append("📦 *Long-Term Holds (High Liquidity):*")
        for sig in long_term[:3]:
            lines.append(f"   • {sig.symbol} - Liq: {format_volume(sig.liquidity_usd)}")
        lines.append("")

    # Best short-term plays
    short_term = [s for s in signals if s.price_change_1h > 5 and s.signal != "AVOID"]
    if short_term:
        lines.append("⚡ *Short-Term Momentum:*")
        for sig in short_term[:3]:
            lines.append(f"   • {sig.symbol} - 1h: +{sig.price_change_1h:.1f}%")
        lines.append("")

    # Leverage warnings
    high_vol = [s for s in signals if s.volume_1h > 500_000]
    if high_vol:
        lines.append("🔥 *High Volume (Leverage Candidates):*")
        for sig in high_vol[:3]:
            lev = _suggest_leverage(sig)
            lines.append(f"   • {sig.symbol} - Vol: {format_volume(sig.volume_1h)}/1h - Max {lev}x")
        lines.append("")

    # Tokens to AVOID
    if avoids:
        lines.append("☠️ *DO NOT TRADE - HIGH RISK*")
        for sig in avoids[:3]:
            reason = sig.security_warnings[0] if sig.security_warnings else "Security risk"
            lines.append(f"   ⛔ {sig.symbol} - {reason}")
        lines.append("")

    # Footer
    lines.append("─" * 30)
    lines.append("_Powered by: DexScreener, Birdeye, GMGN, Grok AI_")
    lines.append("_Use /analyze <token> for deep dive_")

    return "\n".join(lines)


def _format_master_token_entry(signal: TokenSignal, rank: int) -> str:
    """Format a single token entry for master report."""
    lines = []

    # Signal emoji and rank
    sig_emoji = SIGNAL_EMOJI.get(signal.signal, "⚪")
    entry_rec = _get_entry_recommendation(signal)

    lines.append(f"*{rank}. {signal.symbol}* {sig_emoji}")

    # Contract address (clickable)
    if signal.address:
        short_addr = f"{signal.address[:6]}...{signal.address[-4:]}"
        lines.append(f"   📋 `{signal.address}`")

    # Price and changes
    lines.append(f"   💰 {format_price(signal.price_usd)} | 1h: {_format_change_compact(signal.price_change_1h)} | 24h: {_format_change_compact(signal.price_change_24h)}")

    # Volume and liquidity
    lines.append(f"   📊 Vol: {format_volume(signal.volume_24h)} | Liq: {format_volume(signal.liquidity_usd)}")

    # Security status
    risk_emoji = RISK_EMOJI.get(signal.risk_level, "❓")
    lines.append(f"   🔒 {risk_emoji} {signal.risk_level.upper()} | Score: {signal.security_score:.0f}/100")

    # Sentiment if available
    if signal.sentiment != "neutral" and signal.sentiment_confidence > 0:
        sent_emoji = SENTIMENT_EMOJI.get(signal.sentiment, "❓")
        lines.append(f"   {sent_emoji} Grok: {signal.sentiment.upper()} ({signal.sentiment_confidence:.0%})")

    # Smart money
    if signal.smart_money_signal != "neutral":
        sm = "🐋 WHALES IN" if signal.smart_money_signal == "bullish" else "🦐 WHALES OUT"
        lines.append(f"   {sm}")

    # Entry recommendation
    lines.append(f"   ⚡ *{signal.signal}* | {entry_rec}")

    # Quick links
    links = f"   🔗 [DEX]({get_dexscreener_link(signal.address)}) | [Bird]({get_birdeye_link(signal.address)}) | [Scan]({get_solscan_link(signal.address)})"
    lines.append(links)

    return "\n".join(lines)


def _get_entry_recommendation(signal: TokenSignal) -> str:
    """Generate entry recommendation based on signal data."""
    if signal.signal == "AVOID":
        return "❌ DO NOT ENTER"
    if signal.signal == "STRONG_SELL":
        return "📉 EXIT/SHORT"
    if signal.signal == "SELL":
        return "⚠️ REDUCE POSITION"

    # For buy signals, determine type
    liq = signal.liquidity_usd
    vol_ratio = signal.volume_1h / max(signal.liquidity_usd, 1) if signal.liquidity_usd > 0 else 0

    if signal.signal == "STRONG_BUY":
        if liq > 5_000_000:
            return "🎯 STRONG ENTRY - Long Term"
        elif vol_ratio > 0.5:
            return "⚡ SCALP/DAY TRADE"
        else:
            return "🎯 STRONG ENTRY"
    elif signal.signal == "BUY":
        if liq > 1_000_000:
            return "📈 ACCUMULATE"
        else:
            return "👀 SMALL POSITION"
    else:
        return "⏳ WATCH & WAIT"


def _suggest_leverage(signal: TokenSignal) -> int:
    """Suggest max leverage based on liquidity and volatility."""
    liq = signal.liquidity_usd
    vol = abs(signal.price_change_1h)

    if liq < 100_000 or vol > 20:
        return 2  # Very risky, low leverage
    elif liq < 500_000 or vol > 10:
        return 3
    elif liq < 1_000_000 or vol > 5:
        return 5
    elif liq < 5_000_000:
        return 10
    else:
        return 20  # High liquidity, can handle more


def _format_change_compact(value: float) -> str:
    """Compact format for percentage change."""
    if value > 0:
        return f"🟢+{value:.1f}%"
    elif value < 0:
        return f"🔴{value:.1f}%"
    else:
        return "⚪0%"


def format_status(
    available_sources: List[str],
    missing_config: List[str],
) -> str:
    """Format bot status message."""
    lines = [
        "🤖 *Jarvis Bot Status*",
        "",
        "*Available Data Sources:*",
    ]

    if available_sources:
        for source in available_sources:
            lines.append(f"   ✅ {source}")
    else:
        lines.append("   ❌ No sources available")

    if missing_config:
        lines.append("")
        lines.append("*Missing Configuration:*")
        for cfg in missing_config:
            lines.append(f"   ⚠️ {cfg}")

    tracker = get_tracker()
    can_sentiment, reason = tracker.can_make_sentiment_call()

    lines.append("")
    lines.append("*Sentiment Status:*")
    if can_sentiment:
        lines.append("   ✅ Ready for sentiment check")
    else:
        lines.append(f"   ⏳ {reason}")

    return "\n".join(lines)
