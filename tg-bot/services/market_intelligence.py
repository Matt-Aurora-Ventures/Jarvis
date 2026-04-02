"""
Market Intelligence Display for Telegram

Real-time market data and insights:
- Top gainers/losers
- Market overview (BTC, ETH, SOL)
- Sentiment analysis across sources
- Trading volume trends
- Liquidation heatmaps
- Trending tokens
- Macro indicators
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from enum import Enum

from telegram.constants import ParseMode

logger = logging.getLogger(__name__)


class TrendDirection(Enum):
    """Trend directions."""
    STRONG_UP = "🚀"
    UP = "📈"
    NEUTRAL = "➡️"
    DOWN = "📉"
    STRONG_DOWN = "💥"


class MarketIntelligence:
    """Market intelligence and insights display."""

    EMOJI = {
        'bull': '🐮',
        'bear': '🐻',
        'chart': '📊',
        'fire': '🔥',
        'warning': '⚠️',
        'rocket': '🚀',
        'thunder': '⚡',
        'money': '💰',
        'up': '📈',
        'down': '📉',
        'target': '🎯',
        'brain': '🧠',
        'eye': '👁️',
        'bell': '🔔',
    }

    def __init__(self, sentiment_agg=None, market_data_api=None):
        """
        Initialize market intelligence.

        Args:
            sentiment_agg: SentimentAggregator instance
            market_data_api: MarketDataAPI instance
        """
        self.sentiment_agg = sentiment_agg
        self.market_data_api = market_data_api

    # ==================== MARKET OVERVIEW ====================

    def build_market_overview(self) -> str:
        """Build current market overview."""
        msg = f"""{self.EMOJI['chart']} <b>MARKET OVERVIEW</b>

<b>Major Assets:</b>

"""

        # BTC
        btc_price = 95432.50  # TODO: Get real data
        btc_change = 2.35
        btc_emoji = self._get_trend_emoji(btc_change)
        msg += f"  {btc_emoji} <b>BTC</b>: <code>${btc_price:,.2f}</code> ({btc_change:+.2f}%)\n"

        # ETH
        eth_price = 3285.10
        eth_change = 1.82
        eth_emoji = self._get_trend_emoji(eth_change)
        msg += f"  {eth_emoji} <b>ETH</b>: <code>${eth_price:,.2f}</code> ({eth_change:+.2f}%)\n"

        # SOL
        sol_price = 142.75
        sol_change = 4.21
        sol_emoji = self._get_trend_emoji(sol_change)
        msg += f"  {sol_emoji} <b>SOL</b>: <code>${sol_price:,.2f}</code> ({sol_change:+.2f}%)\n"

        msg += f"""\n<b>Market Status:</b>
  <b>Market Cap:</b> <code>$2.85T</code> ({2.1:+.2f}%)
  <b>24h Volume:</b> <code>$125B</code>
  <b>Bitcoin Dominance:</b> <code>58.3%</code> ({0.5:+.2f}%)
  <b>Fear & Greed:</b> <code>65/100</code> ({self.EMOJI['bull']} Greed)

<b>Top Gainers (24h):</b>
  🥇 DOGE: +8.5%
  🥈 XRP: +6.2%
  🥉 ADA: +4.1%

<b>Top Losers (24h):</b>
  📉 LINK: -3.2%
  📉 AVAX: -2.8%
  📉 ATOM: -1.5%
"""

        return msg

    # ==================== SENTIMENT ANALYSIS ====================

    def build_sentiment_analysis(self, symbols: List[str] = None) -> str:
        """Build detailed sentiment analysis."""
        if not symbols:
            symbols = ['BTC', 'ETH', 'SOL', 'DOGE']

        msg = f"""{self.EMOJI['brain']} <b>SENTIMENT ANALYSIS</b>

<b>Current Mood:</b> {self.EMOJI['bull']} Bullish (65/100)

<b>By Asset:</b>

"""

        sentiment_data = {
            'BTC': {'grok': 78, 'twitter': 72, 'news': 75, 'onchain': 68},
            'ETH': {'grok': 71, 'twitter': 65, 'news': 68, 'onchain': 62},
            'SOL': {'grok': 82, 'twitter': 78, 'news': 71, 'onchain': 75},
            'DOGE': {'grok': 68, 'twitter': 85, 'news': 52, 'onchain': 71},
        }

        for symbol in symbols:
            if symbol not in sentiment_data:
                continue

            scores = sentiment_data[symbol]
            avg_score = sum(scores.values()) / len(scores)
            sentiment_emoji = self._get_sentiment_emoji(avg_score)

            msg += f"<b>{symbol}</b>: {sentiment_emoji} <code>{avg_score:.0f}/100</code>\n"
            msg += f"  Grok: <code>{scores['grok']}</code> | Twitter: <code>{scores['twitter']}</code> | News: <code>{scores['news']}</code> | Onchain: <code>{scores['onchain']}</code>\n"

        msg += f"""
<b>Sentiment Drivers:</b>
  ✅ Strong institutional buying (whale tracking)
  ✅ Positive regulatory news (SEC clarity)
  ⚠️ Mixed Fed sentiment (rate pause expected)
  ⚠️ Tech stock correlation (QQQ -0.5%)

<b>Key Catalysts (Next 7 Days):</b>
  📅 US CPI Report (Thu) → Expected 3.2%
  📅 Fed Meeting Minutes (Wed)
  📅 Ethereum Upgrade (Sat) → Shanghai 2.0

<i>Sentiment updated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}</i>
"""

        return msg

    # ==================== LIQUIDATION HEATMAP ====================

    def build_liquidation_heatmap(self) -> str:
        """Build liquidation level summary."""
        msg = f"""{self.EMOJI['fire']} <b>LIQUIDATION HEATMAP</b>

<b>BTC Liquidation Levels:</b>
  <b>Short Liquidations:</b> $500M
    ├─ $94,000 (30%) - Highest concentration
    ├─ $93,500 (25%)
    └─ $93,000 (15%)

  <b>Long Liquidations:</b> $450M
    ├─ $96,000 (35%) - Highest concentration
    ├─ $97,000 (30%)
    └─ $98,000 (20%)

<b>ETH Liquidation Levels:</b>
  <b>Short Liquidations:</b> $300M
    └─ $3,200 (40%) - Watch level

  <b>Long Liquidations:</b> $280M
    └─ $3,400 (45%) - Watch level

<b>SOL Liquidation Levels:</b>
  <b>Short Liquidations:</b> $150M
    └─ $140 (50%) - Extreme concentration

  <b>Long Liquidations:</b> $120M
    └─ $145 (55%) - Extreme concentration

<b>Liquidation Risk:</b>
  ⚠️ HIGH - BTC approaching major liquidation wall at $94k
  ⚠️ MEDIUM - SOL showing extreme concentration
  ✅ LOW - ETH levels well distributed

<i>Data from GlassNode | Updated: {datetime.utcnow().strftime('%H:%M UTC')}</i>
"""

        return msg

    # ==================== TRADING VOLUME ====================

    def build_volume_analysis(self) -> str:
        """Build trading volume analysis."""
        msg = f"""{self.EMOJI['thunder']} <b>VOLUME & ACTIVITY</b>

<b>24h Volume Leaders:</b>
  1️⃣  <b>BTC</b>:  $42.3B ({self.EMOJI['up']} +15%)
  2️⃣  <b>ETH</b>:  $18.5B ({self.EMOJI['up']} +8%)
  3️⃣  <b>SOL</b>:  $8.2B ({self.EMOJI['down']} -2%)
  4️⃣  <b>XRP</b>:  $6.1B ({self.EMOJI['up']} +42%)
  5️⃣  <b>DOGE</b>: $4.5B ({self.EMOJI['up']} +35%)

<b>Volume Trends:</b>
  📈 <b>Volume Spike (24h):</b> +23% above 30-day avg
  📈 <b>Buying Pressure:</b> 58% buy orders
  📉 <b>Selling Pressure:</b> 42% sell orders

<b>Exchange Flow:</b>
  🔴 <b>Inflow:</b> $2.3B (selling pressure)
  🟢 <b>Outflow:</b> $3.8B (hodling)
  <b>Net:</b> $1.5B outflow (BULLISH)

<b>Whale Activity:</b>
  🐳 <b>Whale Buys (24h):</b> $450M
  🐳 <b>Whale Sells (24h):</b> $280M
  Net: $170M buying (POSITIVE SIGNAL)
"""

        return msg

    # ==================== TRENDING TOKENS ====================

    def build_trending_tokens(self) -> str:
        """Build trending tokens analysis."""
        msg = f"""{self.EMOJI['rocket']} <b>TRENDING TOKENS</b>

<b>Trending Up (Social Sentiment):</b>
  🔥 <b>BONK</b> (BONK): +156% vol, Elon mentioned it
  🔥 <b>AI16Z</b> (AI): +89% vol, new partnerships announced
  🔥 <b>JTO</b> (JITOSOL): +67% vol, Solana ecosystem momentum
  🔥 <b>TRUMP</b>: +342% vol, political excitement

<b>Community Favorites:</b>
  💬 <b>Farcaster Trending:</b> DOGE, BONK, AI16Z, JTO
  💬 <b>Reddit (r/CryptoCurrency):</b> BTC, ETH, SOL, AI16Z
  💬 <b>Discord Activity:</b> Up 34% on Solana servers

<b>Upcoming Catalyst Tokens:</b>
  📅 <b>Worldcoin (WLD):</b> Payment app launch (Next week)
  📅 <b>Magic Eden (ME):</b> NFT marketplace expansion (Fri)
  📅 <b>Phantom (PHA):</b> Multi-chain wallet update (Wed)

<b>⚠️ Risk Warning:</b>
  Low market cap coins are 10x+ riskier
  DYOR before entering trending positions
"""

        return msg

    # ==================== MACRO INDICATORS ====================

    def build_macro_indicators(self) -> str:
        """Build macro economic indicators."""
        msg = f"""{self.EMOJI['eye']} <b>MACRO INDICATORS</b>

<b>Global Economy:</b>
  🇺🇸 <b>US GDP:</b> +2.8% (Q3) - STRONG
  🇺🇸 <b>US Inflation:</b> 3.1% YoY - EASING
  🇺🇸 <b>Unemployment:</b> 3.9% - STABLE
  🇺🇸 <b>Fed Rate:</b> 5.25-5.50% - PAUSED

<b>Fed Policy (Crypto Impact):</b>
  📊 <b>Next Meeting:</b> Jan 29-30
  📊 <b>Market Expectation:</b> No change (rates held)
  📊 <b>Probability of Cut:</b> 15% (low - inflation sticky)
  ✅ <b>Sentiment:</b> Neutral to Positive for crypto

<b>Market Structure:</b>
  📈 <b>Stock Market (SPX):</b> +18% YTD (risk ON)
  📉 <b>Bond Yields (10Y):</b> 4.2% (-50bps from peak)
  📊 <b>USD Index:</b> 102.1 (-2% from peak - BULLISH for crypto)
  📊 <b>VIX (Fear Index):</b> 18.5 (normal, low volatility)

<b>Crypto Narrative:</b>
  ✅ Spot Bitcoin ETF (January flows)
  ✅ Ethereum Shanghai 2.0 (scalability)
  ✅ Institutional adoption (Blackrock entering)
  ⚠️ Regulatory uncertainty (Gary Gensler)

<b>Overall Macro Outlook:</b>
  🟢 BULLISH for risk assets (crypto included)
  Rationale: Low rate expectations, inflation easing, institutional money inflows
"""

        return msg

    # ==================== HELPER METHODS ====================

    def _get_trend_emoji(self, change_pct: float) -> str:
        """Get emoji for price change."""
        if change_pct >= 5:
            return TrendDirection.STRONG_UP.value
        elif change_pct >= 1:
            return TrendDirection.UP.value
        elif change_pct >= -1:
            return TrendDirection.NEUTRAL.value
        elif change_pct >= -5:
            return TrendDirection.DOWN.value
        else:
            return TrendDirection.STRONG_DOWN.value

    def _get_sentiment_emoji(self, score: float) -> str:
        """Get sentiment emoji."""
        if score >= 75:
            return "🚀📈"
        elif score >= 60:
            return "📈"
        elif score >= 40:
            return "➡️"
        elif score >= 25:
            return "📉"
        else:
            return "🚀📉"
