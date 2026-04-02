"""
Token Analysis View Formatter.

Renders complete token analysis with:
- Current price and 24h change
- Technical signals (MA, RSI, MACD status)
- On-chain metrics (holders, liquidity, risk flags)
- Sentiment breakdown (Twitter, news, whale activity)
- Recent trades if available
"""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class TokenAnalysisView:
    """
    Format token analysis for Telegram display.

    Uses Telegram markdown for clean, readable output.
    """

    def format_main_view(self, signal) -> str:
        """
        Format the main token analysis view.

        Args:
            signal: TokenSignal object with token data

        Returns:
            Formatted markdown string
        """
        lines = []

        # Header
        lines.append("=" * 25)
        lines.append(f"*{signal.symbol}* - {signal.name or 'Token Analysis'}")
        lines.append("=" * 25)
        lines.append("")

        # Price section
        lines.append(f"*Price:* {self._format_price(signal.price_usd)}")
        lines.append(
            f"   1h: {self._format_change(signal.price_change_1h)} | "
            f"24h: {self._format_change(signal.price_change_24h)}"
        )
        lines.append("")

        # Volume and Liquidity
        lines.append(f"*24h Vol:* {self._format_volume(signal.volume_24h)}")
        lines.append(f"*Liquidity:* {self._format_volume(signal.liquidity_usd)}")
        lines.append("")

        # Sentiment
        if signal.sentiment and signal.sentiment != "neutral":
            sentiment_emoji = self._get_sentiment_emoji(signal.sentiment)
            confidence = int(signal.sentiment_confidence * 100) if signal.sentiment_confidence else 0
            lines.append(f"*Sentiment:* {sentiment_emoji} {signal.sentiment.title()} ({confidence}/100)")
        else:
            lines.append("*Sentiment:* Neutral")

        # On-chain Grade
        grade = self._calculate_grade(signal)
        lines.append(f"*On-chain Grade:* {grade}")
        lines.append("")

        # Security/Risk
        risk_emoji = self._get_risk_emoji(signal.risk_level)
        lines.append(f"*Security:* {risk_emoji} {signal.risk_level.upper()}")
        lines.append(f"   Score: {signal.security_score:.0f}/100")

        if signal.security_warnings:
            for warning in signal.security_warnings[:2]:
                lines.append(f"   - {warning}")
        lines.append("")

        # Trading Signal
        signal_emoji = self._get_signal_emoji(signal.signal)
        lines.append(f"*Signal:* {signal_emoji} {signal.signal} (score: {signal.signal_score:+.0f})")

        if signal.signal_reasons:
            for reason in signal.signal_reasons[:3]:
                lines.append(f"   - {reason}")

        lines.append("")
        lines.append("_Tap buttons below to drill down_")

        return "\n".join(lines)

    def format_chart_view(self, token_address: str, symbol: str = "") -> str:
        """Format chart view message."""
        lines = []

        lines.append("*Price Chart*")
        lines.append("")
        lines.append("Select timeframe or open external chart:")
        lines.append("")
        lines.append(f"[DexScreener](https://dexscreener.com/solana/{token_address})")
        lines.append(f"[Birdeye](https://birdeye.so/token/{token_address}?chain=solana)")
        lines.append(f"[TradingView](https://www.tradingview.com/chart/?symbol={symbol})")

        return "\n".join(lines)

    def format_holders_view(
        self,
        token_address: str,
        holders: List[Dict[str, Any]],
        page: int = 1,
        total_pages: int = 1,
    ) -> str:
        """Format holder distribution view."""
        lines = []

        lines.append("*Top Holders*")
        lines.append(f"Page {page}/{total_pages}")
        lines.append("")

        if not holders:
            lines.append("_No holder data available_")
            return "\n".join(lines)

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
            whale = "🐋" if pct >= 10 else ""

            lines.append(f"{i}. `{addr}` {whale}")
            lines.append(f"   {pct:.1f}% ({amount_str})")

        return "\n".join(lines)

    def format_signals_view(self, signal) -> str:
        """Format trading signals view."""
        lines = []

        lines.append(f"*Trading Signals for {signal.symbol}*")
        lines.append("")

        # Sentiment component
        if signal.sentiment == "positive":
            lines.append(f"*Sentiment:* 🟢 Bullish ({int(signal.sentiment_confidence * 100)}/100)")
        elif signal.sentiment == "negative":
            lines.append(f"*Sentiment:* 🔴 Bearish ({int(signal.sentiment_confidence * 100)}/100)")
        else:
            lines.append(f"*Sentiment:* ⚪ Neutral")

        # Security component
        if signal.risk_level == "low":
            lines.append(f"*Security:* 🟢 Safe ({signal.security_score:.0f}/100)")
        elif signal.risk_level == "critical":
            lines.append(f"*Security:* 🔴 Critical ({signal.security_score:.0f}/100)")
        else:
            lines.append(f"*Security:* 🟡 {signal.risk_level.title()} ({signal.security_score:.0f}/100)")

        # Smart money component
        if signal.smart_money_signal == "bullish":
            lines.append("*Smart Money:* 🐋 Bullish (whales accumulating)")
        elif signal.smart_money_signal == "bearish":
            lines.append("*Smart Money:* 🦐 Bearish (whales selling)")
        else:
            lines.append("*Smart Money:* ⚪ Neutral")

        lines.append("")
        lines.append(f"*Overall Signal:* {signal.signal} ({signal.signal_score:+.0f}/100)")

        if signal.signal_reasons:
            lines.append("")
            lines.append("*Key Factors:*")
            for reason in signal.signal_reasons[:5]:
                lines.append(f"   - {reason}")

        return "\n".join(lines)

    def format_risk_view(self, signal) -> str:
        """Format risk assessment view."""
        lines = []

        lines.append(f"*Risk Assessment for {signal.symbol}*")
        lines.append("")

        # Overall risk
        risk_emoji = self._get_risk_emoji(signal.risk_level)
        lines.append(f"*Risk Level:* {risk_emoji} {signal.risk_level.upper()}")
        lines.append(f"*Security Score:* {signal.security_score:.0f}/100")
        lines.append("")

        # Whale risk
        lines.append("*Whale Activity:*")
        if signal.smart_money_signal == "bullish":
            lines.append("   🟢 Whales accumulating - lower dump risk")
        elif signal.smart_money_signal == "bearish":
            lines.append("   🔴 Whales selling - higher dump risk")
        else:
            lines.append("   ⚪ No significant whale activity")

        if signal.insider_buys or signal.insider_sells:
            lines.append(f"   Insider activity: {signal.insider_buys}↑ / {signal.insider_sells}↓")

        lines.append("")

        # Contract risk
        lines.append("*Contract Risks:*")
        if signal.is_honeypot:
            lines.append("   ☠️ HONEYPOT DETECTED - DO NOT TRADE")
        elif signal.security_warnings:
            for warning in signal.security_warnings[:4]:
                lines.append(f"   ⚠️ {warning}")
        else:
            lines.append("   🛡️ No major contract issues detected")

        lines.append("")

        # Liquidity risk
        lines.append("*Liquidity Risk:*")
        if signal.liquidity_usd < 10_000:
            lines.append("   🔴 Very low liquidity - high slippage risk")
        elif signal.liquidity_usd < 100_000:
            lines.append("   🟡 Low liquidity - moderate slippage risk")
        elif signal.liquidity_usd < 1_000_000:
            lines.append("   🟢 Adequate liquidity")
        else:
            lines.append("   🟢 High liquidity - low slippage risk")

        return "\n".join(lines)

    # Helper methods

    def _format_price(self, value: float) -> str:
        """Format price for display."""
        if value >= 1000:
            return f"${value:,.0f}"
        elif value >= 1:
            return f"${value:.2f}"
        elif value >= 0.01:
            return f"${value:.4f}"
        else:
            return f"${value:.8f}"

    def _format_volume(self, value: float) -> str:
        """Format volume/liquidity for display."""
        if value >= 1_000_000_000:
            return f"${value/1_000_000_000:.2f}B"
        elif value >= 1_000_000:
            return f"${value/1_000_000:.2f}M"
        elif value >= 1_000:
            return f"${value/1_000:.1f}K"
        else:
            return f"${value:.0f}"

    def _format_change(self, value: float) -> str:
        """Format percentage change with arrow."""
        if value > 0:
            return f"📈 +{value:.1f}%"
        elif value < 0:
            return f"📉 {value:.1f}%"
        else:
            return "➡️ 0%"

    def _get_sentiment_emoji(self, sentiment: str) -> str:
        """Get emoji for sentiment."""
        mapping = {
            "positive": "🟢",
            "negative": "🔴",
            "neutral": "⚪",
            "mixed": "🟡",
            "bullish": "🟢",
            "bearish": "🔴",
        }
        return mapping.get(sentiment.lower(), "⚪")

    def _get_risk_emoji(self, risk_level: str) -> str:
        """Get emoji for risk level."""
        mapping = {
            "low": "🛡️",
            "medium": "⚠️",
            "high": "🚨",
            "critical": "☠️",
            "unknown": "❓",
        }
        return mapping.get(risk_level.lower(), "❓")

    def _get_signal_emoji(self, signal: str) -> str:
        """Get emoji for trading signal."""
        mapping = {
            "STRONG_BUY": "🟢🟢",
            "BUY": "🟢",
            "NEUTRAL": "⚪",
            "SELL": "🔴",
            "STRONG_SELL": "🔴🔴",
            "AVOID": "☠️",
        }
        return mapping.get(signal.upper(), "⚪")

    def _calculate_grade(self, signal) -> str:
        """Calculate letter grade based on signal data."""
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


__all__ = ["TokenAnalysisView"]
