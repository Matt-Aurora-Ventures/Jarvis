"""
Real-Time Sentiment Feed for Telegram

Broadcasts sentiment updates and market alerts to Telegram channels:
- Live sentiment score updates
- Market sentiment shifts
- Liquidation level updates
- Whale activity alerts
- Trading signal broadcasts
- Grok analysis summaries
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from enum import Enum

from telegram.ext import ContextTypes
from telegram.constants import ParseMode

logger = logging.getLogger(__name__)


class FeedType(Enum):
    """Sentiment feed types."""
    SENTIMENT_UPDATE = "sentiment"
    LIQUIDATION_UPDATE = "liquidation"
    WHALE_ALERT = "whale"
    SIGNAL_ALERT = "signal"
    MARKET_SHIFT = "shift"
    GROK_ANALYSIS = "grok"
    TRADE_ALERT = "trade"


class SentimentFeed:
    """
    Real-time sentiment feed manager for Telegram.

    Broadcasts sentiment updates to configured channels.
    """

    # Feed formatting
    EMOJI = {
        'bull': '🐮',
        'bear': '🐻',
        'sentiment': '🧠',
        'alert': '🚨',
        'whale': '🐋',
        'liquidation': '💥',
        'signal': '📊',
        'grok': '🤖',
        'fire': '🔥',
        'up': '📈',
        'down': '📉',
        'neutral': '➡️',
        'channel': '📡',
        'broadcast': '📢',
    }

    def __init__(self, sentiment_agg=None):
        """
        Initialize sentiment feed.

        Args:
            sentiment_agg: SentimentAggregator instance
        """
        self.sentiment_agg = sentiment_agg
        self._feed_channels: List[int] = []
        self._last_update: Dict[str, datetime] = {}
        self._update_cooldown = 300  # 5 minutes between same-symbol updates

    def add_feed_channel(self, channel_id: int):
        """Add channel to feed."""
        if channel_id not in self._feed_channels:
            self._feed_channels.append(channel_id)
            logger.info(f"Added sentiment feed channel: {channel_id}")

    def remove_feed_channel(self, channel_id: int):
        """Remove channel from feed."""
        if channel_id in self._feed_channels:
            self._feed_channels.remove(channel_id)
            logger.info(f"Removed sentiment feed channel: {channel_id}")

    # ==================== SENTIMENT UPDATES ====================

    async def broadcast_sentiment_update(
        self,
        symbol: str,
        new_score: float,
        previous_score: float,
        context: ContextTypes.DEFAULT_TYPE,
    ):
        """Broadcast sentiment update to channels."""
        # Check cooldown
        update_key = f"sentiment_{symbol}"
        if self._is_on_cooldown(update_key):
            logger.debug(f"Sentiment update for {symbol} on cooldown")
            return

        # Calculate change
        change = new_score - previous_score
        change_pct = (change / max(abs(previous_score), 1)) * 100

        # Determine trend
        if new_score >= 70:
            trend = f"{self.EMOJI['fire']} STRONG BULLISH"
            emoji = self.EMOJI['bull']
        elif new_score >= 55:
            trend = f"{self.EMOJI['up']} BULLISH"
            emoji = self.EMOJI['bull']
        elif new_score >= 45:
            trend = f"{self.EMOJI['neutral']} NEUTRAL"
            emoji = self.EMOJI['neutral']
        elif new_score >= 30:
            trend = f"{self.EMOJI['down']} BEARISH"
            emoji = self.EMOJI['bear']
        else:
            trend = f"{self.EMOJI['fire']} STRONG BEARISH"
            emoji = self.EMOJI['bear']

        message = f"""{emoji} <b>SENTIMENT UPDATE</b>

<b>Symbol:</b> {symbol}
<b>New Score:</b> <code>{new_score:.1f}/100</code>
<b>Previous:</b> <code>{previous_score:.1f}/100</code>
<b>Change:</b> <code>{change:+.1f}</code> ({change_pct:+.1f}%)

<b>Status:</b> {trend}

<i>🔔 Live sentiment tracking across all sources</i>
<i>Updated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}</i>
"""

        await self._broadcast_to_channels(message, context)
        self._record_update(update_key)

    async def broadcast_market_shift(
        self,
        shift_type: str,  # "bull_trap", "capitulation", "accumulation", etc.
        description: str,
        affected_symbols: List[str],
        context: ContextTypes.DEFAULT_TYPE,
    ):
        """Broadcast market shift alert."""
        shift_emojis = {
            'bull_trap': f'{self.EMOJI["alert"]} BULL TRAP',
            'bear_trap': f'{self.EMOJI["alert"]} BEAR TRAP',
            'capitulation': f'{self.EMOJI["fire"]} CAPITULATION',
            'accumulation': f'{self.EMOJI["up"]} ACCUMULATION',
            'breakout': f'{self.EMOJI["bull"]} BREAKOUT',
            'breakdown': f'{self.EMOJI["bear"]} BREAKDOWN',
        }

        shift_name = shift_emojis.get(shift_type, shift_type)

        message = f"""{self.EMOJI['alert']} <b>MARKET SHIFT ALERT</b>

<b>Type:</b> {shift_name}
<b>Description:</b> {description}

<b>Affected Symbols:</b>
"""
        for sym in affected_symbols[:10]:
            message += f"  • {sym}\n"

        if len(affected_symbols) > 10:
            message += f"  ... and {len(affected_symbols) - 10} more\n"

        message += f"""
<i>🔔 Critical market condition detected
Updated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}</i>
"""

        await self._broadcast_to_channels(message, context)

    # ==================== LIQUIDATION UPDATES ====================

    async def broadcast_liquidation_alert(
        self,
        symbol: str,
        level_type: str,  # "support", "resistance"
        price: float,
        amount: float,
        context: ContextTypes.DEFAULT_TYPE,
    ):
        """Broadcast liquidation level alert."""
        emoji = f'{self.EMOJI["alert"]} {self.EMOJI["liquidation"]}'

        message = f"""{emoji} <b>LIQUIDATION ALERT</b>

<b>Symbol:</b> <code>{symbol}</code>
<b>Level:</b> <code>${price:.6f}</code>
<b>Type:</b> {level_type.upper()} (Liquidation Wall)
<b>Amount:</b> <code>${amount/1e6:.1f}M</code>

<i>⚠️ Critical liquidation concentration
Monitor price action carefully</i>
"""

        await self._broadcast_to_channels(message, context)

    # ==================== WHALE ALERTS ====================

    async def broadcast_whale_alert(
        self,
        action: str,  # "buy", "sell"
        symbol: str,
        amount: float,
        price: float,
        exchange: Optional[str],
        context: ContextTypes.DEFAULT_TYPE,
    ):
        """Broadcast whale activity alert."""
        action_emoji = f'{self.EMOJI["up"]}' if action == "buy" else f'{self.EMOJI["down"]}'
        emoji = f'{self.EMOJI["whale"]} {action_emoji}'

        message = f"""{emoji} <b>WHALE ACTIVITY DETECTED</b>

<b>Action:</b> {action.upper()}
<b>Symbol:</b> <code>{symbol}</code>
<b>Amount:</b> <code>${amount:,.0f}</code>
<b>Price:</b> <code>${price:.6f}</code>
"""

        if exchange:
            message += f"<b>Exchange:</b> {exchange}\n"

        message += f"""
<i>🐋 Institutional activity marker
{datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}</i>
"""

        await self._broadcast_to_channels(message, context)

    # ==================== GROK ANALYSIS BROADCASTS ====================

    async def broadcast_grok_analysis(
        self,
        symbol: str,
        analysis: str,
        confidence: float,
        action: str,  # "BUY", "HOLD", "SELL"
        context: ContextTypes.DEFAULT_TYPE,
    ):
        """Broadcast Grok AI analysis."""
        confidence_emoji = self._get_confidence_emoji(confidence)
        action_emoji = self._get_action_emoji(action)

        message = f"""{self.EMOJI['grok']} <b>GROK AI ANALYSIS</b>

<b>Symbol:</b> <code>{symbol}</code>
<b>Recommendation:</b> {action_emoji} {action}
<b>Confidence:</b> {confidence_emoji} <code>{confidence:.0f}%</code>

<b>Analysis:</b>
{analysis}

<i>🤖 AI-powered sentiment analysis
{datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}</i>
"""

        await self._broadcast_to_channels(message, context)

    # ==================== TRADING SIGNAL BROADCASTS ====================

    async def broadcast_trading_signal(
        self,
        symbol: str,
        signal_type: str,  # "entry", "exit", "rebalance"
        action: str,  # "BUY", "SELL", "HOLD"
        reason: str,
        confidence: float,
        context: ContextTypes.DEFAULT_TYPE,
    ):
        """Broadcast trading signal."""
        signal_emoji = {
            'entry': f'{self.EMOJI["signal"]} 🎯',
            'exit': f'{self.EMOJI["signal"]} 🏁',
            'rebalance': f'{self.EMOJI["signal"]} ⚖️',
        }.get(signal_type, self.EMOJI['signal'])

        message = f"""{signal_emoji} <b>TRADING SIGNAL</b>

<b>Symbol:</b> <code>{symbol}</code>
<b>Type:</b> {signal_type.upper()}
<b>Action:</b> {action}
<b>Confidence:</b> <code>{confidence:.0f}%</code>

<b>Reason:</b>
{reason}

<i>📊 Decision Matrix Alert
{datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}</i>
"""

        await self._broadcast_to_channels(message, context)

    # ==================== BROADCAST METHODS ====================

    async def _broadcast_to_channels(
        self,
        message: str,
        context: ContextTypes.DEFAULT_TYPE,
    ):
        """Broadcast message to all configured channels."""
        if not self._feed_channels:
            logger.debug("No feed channels configured")
            return

        for channel_id in self._feed_channels:
            try:
                await context.bot.send_message(
                    chat_id=channel_id,
                    text=message,
                    parse_mode=ParseMode.HTML,
                )
            except Exception as e:
                logger.warning(f"Failed to send to channel {channel_id}: {e}")

    def _is_on_cooldown(self, update_key: str) -> bool:
        """Check if update is on cooldown."""
        if update_key not in self._last_update:
            return False

        time_since_last = datetime.utcnow() - self._last_update[update_key]
        return time_since_last.total_seconds() < self._update_cooldown

    def _record_update(self, update_key: str):
        """Record update timestamp."""
        self._last_update[update_key] = datetime.utcnow()

    # ==================== HELPER METHODS ====================

    def _get_confidence_emoji(self, confidence: float) -> str:
        """Get confidence emoji."""
        if confidence >= 80:
            return "🟢"
        elif confidence >= 60:
            return "🟡"
        else:
            return "🔴"

    def _get_action_emoji(self, action: str) -> str:
        """Get action emoji."""
        if action == "BUY":
            return "📈"
        elif action == "SELL":
            return "📉"
        else:
            return "➡️"

    def get_channel_status(self) -> str:
        """Get feed status."""
        return f"""
<b>Sentiment Feed Status</b>

Channels: {len(self._feed_channels)}
Status: {'🟢 Active' if self._feed_channels else '🔴 No channels'}
Updates: {len(self._last_update)}
Update Cooldown: {self._update_cooldown}s

{self.EMOJI['broadcast']} Broadcasting real-time sentiment updates
"""
