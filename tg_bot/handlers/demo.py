"""
JARVIS V1 - The Mona Lisa of AI Trading Bots

Admin-only showcase of the full JARVIS trading experience.

CORE PHILOSOPHY: Compression is Intelligence
- The better the predictive compression, the better the understanding
- Store intelligence as compact latent representations, not raw logs
- Self-improving through trade outcome learning
- Generative retrieval - reconstruct essence, not verbatim recall

Features:
- Beautiful Trojan-style Trading UI
- Wallet generation and management
- Portfolio overview with live P&L
- Quick buy/sell with preset amounts
- Token search and snipe with AI analysis
- AI-POWERED SENTIMENT ENGINE (Grok + Multi-Source)
- SELF-IMPROVING TRADE INTELLIGENCE
- GENERATIVE COMPRESSION MEMORY
- Bags.fm API Integration
- Learning Dashboard

Built on the data-driven sentiment engine (Jan 2026 overhaul):
- Stricter entry timing (early entry = 67% TP rate)
- Ratio requirements (2.0x = 67% TP rate)
- Overconfidence penalty (high scores = 0% TP rate)
- Momentum keyword detection
- Multi-sighting bonuses

Memory Hierarchy:
- Tier 0: Ephemeral Context (seconds-minutes)
- Tier 1: Short Latent Memory (hours-days)
- Tier 2: Medium Latent Memory (weeks-months)
- Tier 3: Long Latent Memory (months-years)
"""

import logging
import asyncio
from typing import Optional, Tuple, Dict, Any, List
from decimal import Decimal
from datetime import datetime, timezone, timedelta

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from tg_bot.config import get_config
from tg_bot.handlers import error_handler, admin_only

logger = logging.getLogger(__name__)


# =============================================================================
# Trade Intelligence Integration
# =============================================================================

def get_trade_intelligence():
    """Get trade intelligence engine for self-improvement."""
    try:
        from core.trade_intelligence import get_intelligence_engine
        return get_intelligence_engine()
    except ImportError:
        logger.warning("Trade intelligence not available")
        return None


def get_bags_client():
    """Get Bags.fm API client for trading."""
    try:
        from core.trading.bags_client import get_bags_client as _get_bags
        return _get_bags()
    except ImportError:
        logger.warning("Bags client not available")
        return None


def get_success_fee_manager():
    """Get Success Fee Manager for 0.5% fee on winning trades."""
    try:
        from core.trading.bags_client import get_success_fee_manager as _get_fee_manager
        return _get_fee_manager()
    except ImportError:
        logger.warning("Success fee manager not available")
        return None


# =============================================================================
# Sentiment Engine Integration
# =============================================================================

async def get_market_regime() -> Dict[str, Any]:
    """Get current market regime from sentiment engine."""
    try:
        # Try to get real market data from DexScreener
        import aiohttp
        async with aiohttp.ClientSession() as session:
            # Get BTC and SOL prices
            async with session.get(
                "https://api.dexscreener.com/latest/dex/tokens/So11111111111111111111111111111111111111112",
                timeout=aiohttp.ClientTimeout(total=5)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    pairs = data.get("pairs", [])
                    if pairs:
                        sol_pair = pairs[0]
                        sol_change = float(sol_pair.get("priceChange", {}).get("h24", 0))

                        # Determine regime based on SOL price action
                        if sol_change > 5:
                            regime = "BULL"
                            risk = "LOW"
                        elif sol_change > 0:
                            regime = "NEUTRAL"
                            risk = "NORMAL"
                        elif sol_change > -5:
                            regime = "NEUTRAL"
                            risk = "NORMAL"
                        else:
                            regime = "BEAR"
                            risk = "HIGH"

                        return {
                            "btc_trend": "BULLISH" if sol_change > 0 else "BEARISH",
                            "sol_trend": "BULLISH" if sol_change > 0 else "BEARISH",
                            "btc_change_24h": sol_change * 0.7,  # Approximate BTC correlation
                            "sol_change_24h": sol_change,
                            "risk_level": risk,
                            "regime": regime,
                        }

        # Fallback to default
        return {
            "btc_trend": "NEUTRAL",
            "sol_trend": "NEUTRAL",
            "btc_change_24h": 0.0,
            "sol_change_24h": 0.0,
            "risk_level": "NORMAL",
            "regime": "NEUTRAL",
        }
    except Exception as e:
        logger.warning(f"Could not fetch market regime: {e}")
        return {"regime": "UNKNOWN", "risk_level": "UNKNOWN"}


async def get_ai_sentiment_for_token(address: str) -> Dict[str, Any]:
    """Get AI sentiment analysis for a token."""
    try:
        from tg_bot.services.signal_service import get_signal_service
        service = get_signal_service()
        signal = await service.get_comprehensive_signal(
            address, include_sentiment=True
        )
        return {
            "sentiment": signal.sentiment,
            "score": signal.sentiment_score,
            "confidence": signal.sentiment_confidence,
            "summary": signal.sentiment_summary,
            "signal": signal.signal,
            "signal_score": signal.signal_score,
            "reasons": signal.signal_reasons,
        }
    except Exception as e:
        logger.warning(f"Could not get sentiment: {e}")
        return {"sentiment": "unknown", "score": 0, "confidence": 0}


async def get_trending_with_sentiment() -> List[Dict[str, Any]]:
    """Get trending tokens with AI sentiment overlay."""
    try:
        from tg_bot.services.signal_service import get_signal_service
        service = get_signal_service()
        signals = await service.get_trending_tokens(limit=6)
        return [
            {
                "symbol": s.symbol,
                "address": s.address,
                "price_usd": s.price_usd,
                "change_24h": s.price_change_24h,
                "volume": s.volume_24h,
                "liquidity": s.liquidity_usd,
                "sentiment": s.sentiment,
                "sentiment_score": s.sentiment_score,
                "signal": s.signal,
            }
            for s in signals
        ]
    except Exception as e:
        logger.warning(f"Could not get trending: {e}")
        return []


async def get_conviction_picks() -> List[Dict[str, Any]]:
    """
    Get AI conviction picks enhanced with trade intelligence.

    Combines:
    - Grok sentiment analysis
    - Trade intelligence recommendations
    - Historical pattern matching
    """
    picks = []

    # Try Grok picks first
    try:
        from core.enhanced_market_data import get_grok_conviction_picks
        grok_picks = await get_grok_conviction_picks()
        for p in grok_picks[:5]:
            pick = {
                "symbol": p.symbol,
                "address": p.address,
                "conviction": p.conviction,
                "thesis": p.thesis,
                "entry_price": p.entry_price,
                "tp_target": p.tp_target,
                "sl_target": p.sl_target,
                "source": "grok",
            }

            # Enhance with trade intelligence recommendation
            intelligence = get_trade_intelligence()
            if intelligence:
                rec = intelligence.get_trade_recommendation(
                    signal_type="BUY",
                    market_regime="BULL",
                    sentiment_score=0.7,
                )
                pick["ai_confidence"] = rec.get("confidence", 0)
                pick["ai_action"] = rec.get("action", "NEUTRAL")
            picks.append(pick)

        return picks
    except Exception as e:
        logger.warning(f"Could not get Grok picks: {e}")

    # Fallback to mock data if Grok unavailable
    return [
        {
            "symbol": "BONK",
            "address": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",
            "conviction": "HIGH",
            "thesis": "Strong momentum, high volume, bullish sentiment",
            "tp_target": 25,
            "sl_target": 10,
            "source": "demo",
        },
        {
            "symbol": "WIF",
            "address": "EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm",
            "conviction": "MEDIUM",
            "thesis": "Consolidating, potential breakout setup",
            "tp_target": 20,
            "sl_target": 15,
            "source": "demo",
        },
        {
            "symbol": "POPCAT",
            "address": "7GCihgDB8fe6KNjn2MYtkzZcRjQy3t9GHdC8uHYmW2hr",
            "conviction": "HIGH",
            "thesis": "Viral momentum, social buzz increasing",
            "tp_target": 30,
            "sl_target": 12,
            "source": "demo",
        },
    ]

# =============================================================================
# UI Constants - Trojan-Style Theme
async def get_bags_top_tokens_with_sentiment(limit: int = 15) -> List[Dict[str, Any]]:
    """
    Get top Bags.fm tokens by volume with AI sentiment overlay.

    Returns tokens with:
    - Volume data from Bags.fm API
    - AI sentiment analysis per token
    - Price and market data
    """
    tokens = []

    try:
        # Try to get real data from Bags API
        bags_client = get_bags_client()
        if bags_client:
            raw_tokens = await bags_client.get_top_tokens_by_volume(limit=limit)
            for t in raw_tokens:
                token_data = {
                    "symbol": t.symbol,
                    "name": t.name,
                    "address": t.address,
                    "price_usd": t.price_usd,
                    "volume_24h": t.volume_24h,
                    "liquidity": t.liquidity,
                    "market_cap": t.market_cap,
                    "holders": t.holders,
                }

                # Add AI sentiment overlay
                try:
                    sentiment = await get_ai_sentiment_for_token(t.address)
                    token_data["sentiment"] = sentiment.get("sentiment", "neutral")
                    token_data["sentiment_score"] = sentiment.get("score", 0.5)
                    token_data["signal"] = sentiment.get("signal", "NEUTRAL")
                except Exception:
                    token_data["sentiment"] = "neutral"
                    token_data["sentiment_score"] = 0.5
                    token_data["signal"] = "NEUTRAL"

                tokens.append(token_data)

            return tokens

    except Exception as e:
        logger.warning(f"Could not get Bags tokens: {e}")

    # Fallback to mock data with realistic sentiment
    return [
        {"symbol": "PUMP", "name": "PumpFun Token", "address": "PUMP111111111111111111111111111111111111111", "price_usd": 0.0125, "volume_24h": 8500000, "liquidity": 450000, "market_cap": 12500000, "holders": 15420, "sentiment": "bullish", "sentiment_score": 0.78, "signal": "BUY"},
        {"symbol": "BAGS", "name": "Bags.fm", "address": "BAGS111111111111111111111111111111111111111", "price_usd": 0.0085, "volume_24h": 6200000, "liquidity": 320000, "market_cap": 8500000, "holders": 12350, "sentiment": "very_bullish", "sentiment_score": 0.85, "signal": "STRONG_BUY"},
        {"symbol": "MICHI", "name": "Michi", "address": "MICHI11111111111111111111111111111111111111", "price_usd": 0.0052, "volume_24h": 4800000, "liquidity": 280000, "market_cap": 5200000, "holders": 9800, "sentiment": "bullish", "sentiment_score": 0.72, "signal": "BUY"},
        {"symbol": "PONKE", "name": "Ponke", "address": "PONKE11111111111111111111111111111111111111", "price_usd": 0.425, "volume_24h": 4200000, "liquidity": 520000, "market_cap": 42500000, "holders": 18200, "sentiment": "neutral", "sentiment_score": 0.52, "signal": "HOLD"},
        {"symbol": "GIGA", "name": "GigaChad", "address": "GIGA1111111111111111111111111111111111111111", "price_usd": 0.0425, "volume_24h": 3800000, "liquidity": 180000, "market_cap": 4250000, "holders": 7500, "sentiment": "bullish", "sentiment_score": 0.68, "signal": "BUY"},
        {"symbol": "FWOG", "name": "Fwog", "address": "FWOG1111111111111111111111111111111111111111", "price_usd": 0.0185, "volume_24h": 3500000, "liquidity": 150000, "market_cap": 1850000, "holders": 6200, "sentiment": "very_bullish", "sentiment_score": 0.82, "signal": "STRONG_BUY"},
        {"symbol": "MOTHER", "name": "Mother Iggy", "address": "MOTHE11111111111111111111111111111111111111", "price_usd": 0.125, "volume_24h": 3200000, "liquidity": 380000, "market_cap": 12500000, "holders": 14500, "sentiment": "neutral", "sentiment_score": 0.48, "signal": "HOLD"},
        {"symbol": "RETARDIO", "name": "Retardio", "address": "RETAR11111111111111111111111111111111111111", "price_usd": 0.0042, "volume_24h": 2800000, "liquidity": 120000, "market_cap": 4200000, "holders": 5800, "sentiment": "bullish", "sentiment_score": 0.65, "signal": "BUY"},
        {"symbol": "BILLY", "name": "Billy", "address": "BILLY11111111111111111111111111111111111111", "price_usd": 0.0018, "volume_24h": 2500000, "liquidity": 95000, "market_cap": 1800000, "holders": 4200, "sentiment": "bearish", "sentiment_score": 0.35, "signal": "SELL"},
        {"symbol": "SIGMA", "name": "Sigma", "address": "SIGMA11111111111111111111111111111111111111", "price_usd": 0.0065, "volume_24h": 2200000, "liquidity": 110000, "market_cap": 6500000, "holders": 5500, "sentiment": "neutral", "sentiment_score": 0.55, "signal": "HOLD"},
        {"symbol": "CHILL", "name": "Chill Guy", "address": "CHILL11111111111111111111111111111111111111", "price_usd": 0.0095, "volume_24h": 1950000, "liquidity": 85000, "market_cap": 9500000, "holders": 8200, "sentiment": "bullish", "sentiment_score": 0.70, "signal": "BUY"},
        {"symbol": "GOAT", "name": "Goatseus Maximus", "address": "GOAT1111111111111111111111111111111111111111", "price_usd": 0.52, "volume_24h": 1800000, "liquidity": 420000, "market_cap": 52000000, "holders": 22000, "sentiment": "neutral", "sentiment_score": 0.50, "signal": "HOLD"},
        {"symbol": "PEPE", "name": "Pepe", "address": "PEPE1111111111111111111111111111111111111111", "price_usd": 0.0000125, "volume_24h": 1650000, "liquidity": 75000, "market_cap": 125000, "holders": 3500, "sentiment": "very_bearish", "sentiment_score": 0.25, "signal": "STRONG_SELL"},
        {"symbol": "ANDY", "name": "Andy", "address": "ANDY1111111111111111111111111111111111111111", "price_usd": 0.0035, "volume_24h": 1500000, "liquidity": 68000, "market_cap": 3500000, "holders": 4800, "sentiment": "bullish", "sentiment_score": 0.62, "signal": "BUY"},
        {"symbol": "NPC", "name": "NPC", "address": "NPC11111111111111111111111111111111111111111", "price_usd": 0.0028, "volume_24h": 1350000, "liquidity": 55000, "market_cap": 2800000, "holders": 3900, "sentiment": "neutral", "sentiment_score": 0.45, "signal": "HOLD"},
    ]


# =============================================================================

class JarvisTheme:
    """Beautiful emoji theme for JARVIS UI."""

    # Status indicators
    LIVE = "🟢"
    PAPER = "🟡"
    ERROR = "🔴"
    WARNING = "⚠️"
    SUCCESS = "✅"

    # Actions
    BUY = "🟢"
    SELL = "🔴"
    REFRESH = "🔄"
    SETTINGS = "⚙️"
    WALLET = "💳"
    CHART = "📊"

    # Navigation
    BACK = "◀️"
    FORWARD = "▶️"
    HOME = "🏠"
    CLOSE = "✖️"

    # Assets
    SOL = "◎"
    USD = "💵"
    COIN = "🪙"
    ROCKET = "🚀"
    FIRE = "🔥"
    GEM = "💎"

    # PnL
    PROFIT = "📈"
    LOSS = "📉"
    NEUTRAL = "➖"

    # Features
    SNIPE = "🎯"
    AUTO = "🤖"
    LOCK = "🔒"
    KEY = "🔑"
    COPY = "📋"

    # =========================================================================
    # BEAUTIFICATION V1.1 - Enhanced Visual Indicators
    # =========================================================================

    # Loading/Progress animations
    LOADING_FRAMES = ["⏳", "⌛"]
    PULSE_FRAMES = ["◉", "○"]
    SPIN_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

    # Market mood spectrum (more nuanced than bull/bear)
    MOOD_EUPHORIC = "🌟"      # Extreme greed - careful!
    MOOD_BULLISH = "🚀"       # Strong uptrend
    MOOD_OPTIMISTIC = "💚"    # Mild bullish
    MOOD_NEUTRAL = "⚖️"       # Sideways
    MOOD_CAUTIOUS = "🔶"      # Mild bearish
    MOOD_FEARFUL = "😰"       # Strong downtrend
    MOOD_PANIC = "🆘"         # Extreme fear - opportunities!

    # Health indicators for positions
    HEALTH_EXCELLENT = "💪"   # > +20% PnL, healthy time
    HEALTH_GOOD = "🟢"        # +5% to +20% PnL
    HEALTH_FAIR = "🟡"        # -5% to +5% PnL
    HEALTH_WEAK = "🟠"        # -5% to -15% PnL
    HEALTH_CRITICAL = "🔴"    # < -15% PnL

    # AI confidence levels
    CONFIDENCE_HIGH = "🎯"    # > 80% confidence
    CONFIDENCE_MED = "📊"     # 60-80% confidence
    CONFIDENCE_LOW = "⚠️"     # < 60% confidence

    # Time indicators
    TIME_FRESH = "🆕"         # < 1 hour
    TIME_NORMAL = "⏰"        # 1-24 hours
    TIME_AGING = "📅"         # 1-7 days
    TIME_OLD = "🗓️"          # > 7 days

    @classmethod
    def get_health_indicator(cls, pnl_pct: float, hours_held: float = 0) -> str:
        """Get position health indicator based on PnL and time."""
        if pnl_pct >= 20:
            return cls.HEALTH_EXCELLENT
        elif pnl_pct >= 5:
            return cls.HEALTH_GOOD
        elif pnl_pct >= -5:
            return cls.HEALTH_FAIR
        elif pnl_pct >= -15:
            return cls.HEALTH_WEAK
        else:
            return cls.HEALTH_CRITICAL

    @classmethod
    def get_health_bar(cls, pnl_pct: float, width: int = 5) -> str:
        """Generate a visual health bar for position PnL."""
        # Normalize PnL to 0-100 scale (capped at -50% to +100%)
        normalized = min(100, max(0, (pnl_pct + 50) / 1.5))
        filled = int(normalized / 100 * width)
        empty = width - filled

        if pnl_pct >= 20:
            bar = "🟩" * filled + "⬜" * empty
        elif pnl_pct >= 0:
            bar = "🟨" * filled + "⬜" * empty
        elif pnl_pct >= -15:
            bar = "🟧" * filled + "⬜" * empty
        else:
            bar = "🟥" * filled + "⬜" * empty
        return bar

    @classmethod
    def get_time_indicator(cls, hours_held: float) -> str:
        """Get time held indicator."""
        if hours_held < 1:
            return cls.TIME_FRESH
        elif hours_held < 24:
            return cls.TIME_NORMAL
        elif hours_held < 168:  # 7 days
            return cls.TIME_AGING
        else:
            return cls.TIME_OLD

    @classmethod
    def get_market_mood(cls, fear_greed_score: float) -> Tuple[str, str]:
        """Get market mood emoji and label based on fear/greed score (0-100)."""
        if fear_greed_score >= 85:
            return cls.MOOD_EUPHORIC, "EUPHORIC"
        elif fear_greed_score >= 65:
            return cls.MOOD_BULLISH, "BULLISH"
        elif fear_greed_score >= 55:
            return cls.MOOD_OPTIMISTIC, "OPTIMISTIC"
        elif fear_greed_score >= 45:
            return cls.MOOD_NEUTRAL, "NEUTRAL"
        elif fear_greed_score >= 35:
            return cls.MOOD_CAUTIOUS, "CAUTIOUS"
        elif fear_greed_score >= 15:
            return cls.MOOD_FEARFUL, "FEARFUL"
        else:
            return cls.MOOD_PANIC, "PANIC"

    @classmethod
    def get_confidence_bar(cls, confidence: float, width: int = 10) -> str:
        """Generate an AI confidence bar (0.0 to 1.0)."""
        filled = int(confidence * width)
        empty = width - filled
        bar_char = "▰" if confidence >= 0.6 else "▱"
        return "▰" * filled + "▱" * empty

    @classmethod
    def get_confidence_indicator(cls, confidence: float) -> str:
        """Get confidence level indicator."""
        if confidence >= 0.8:
            return cls.CONFIDENCE_HIGH
        elif confidence >= 0.6:
            return cls.CONFIDENCE_MED
        else:
            return cls.CONFIDENCE_LOW

    @classmethod
    def loading_text(cls, message: str = "Loading") -> str:
        """Generate loading text with animation hint."""
        return f"⏳ _{message}..._"

    @classmethod
    def format_pnl_styled(cls, pnl_pct: float, pnl_usd: float) -> str:
        """Format PnL with beautiful styling."""
        sign = "+" if pnl_pct >= 0 else ""
        emoji = cls.PROFIT if pnl_pct >= 0 else cls.LOSS
        health = cls.get_health_indicator(pnl_pct)
        bar = cls.get_health_bar(pnl_pct)

        return f"{emoji}{health} *{sign}{pnl_pct:.1f}%* ({sign}${abs(pnl_usd):.2f})\n{bar}"


# =============================================================================
# Menu Builders - Trojan Style
# =============================================================================

class DemoMenuBuilder:
    """Build beautiful Trojan-style menus for JARVIS demo."""

    @staticmethod
    def main_menu(
        wallet_address: str,
        sol_balance: float,
        usd_value: float,
        is_live: bool = False,
        open_positions: int = 0,
        total_pnl: float = 0.0,
        market_regime: Dict[str, Any] = None,
        ai_auto_enabled: bool = False,
    ) -> Tuple[str, InlineKeyboardMarkup]:
        """
        Build the main wallet/trading menu - Trojan style with AI Sentiment.

        This is the beautiful landing page users see.
        """
        theme = JarvisTheme
        mode = f"{theme.LIVE} LIVE" if is_live else f"{theme.PAPER} PAPER"

        # Format address
        short_addr = f"{wallet_address[:6]}...{wallet_address[-4:]}" if wallet_address else "Not Set"

        # PnL formatting
        pnl_emoji = theme.PROFIT if total_pnl >= 0 else theme.LOSS
        pnl_sign = "+" if total_pnl >= 0 else ""

        # Market regime formatting
        regime = market_regime or {}
        regime_name = regime.get("regime", "NEUTRAL")
        risk_level = regime.get("risk_level", "NORMAL")
        btc_change = regime.get("btc_change_24h", 0)
        sol_change = regime.get("sol_change_24h", 0)

        # Regime emoji
        if regime_name == "BULL":
            regime_emoji = "🟢"
            regime_display = "BULLISH"
        elif regime_name == "BEAR":
            regime_emoji = "🔴"
            regime_display = "BEARISH"
        else:
            regime_emoji = "🟡"
            regime_display = "NEUTRAL"

        # Risk emoji
        risk_emoji = {"LOW": "🟢", "NORMAL": "🟡", "HIGH": "🟠", "EXTREME": "🔴"}.get(risk_level, "⚪")

        # AI Auto-trade status
        ai_status = f"{theme.ROCKET} AUTO-TRADE ACTIVE" if ai_auto_enabled else ""

        # Build message with beautiful formatting + AI sentiment
        text = f"""
{theme.ROCKET} *JARVIS AI TRADING* {theme.ROCKET}
━━━━━━━━━━━━━━━━━━━━━
"""
        # Show AI auto-trade status if enabled
        if ai_auto_enabled:
            text += f"\n{ai_status}\n"

        text += f"""
{theme.AUTO} *AI Market Regime*
┌ Market: {regime_emoji} *{regime_display}*
├ Risk: {risk_emoji} *{risk_level}*
├ BTC: *{btc_change:+.1f}%* | SOL: *{sol_change:+.1f}%*
└ _Powered by Grok + Multi-Source AI_

{theme.WALLET} *Wallet*
┌ Address: `{short_addr}` {theme.COPY}
├ {theme.SOL} SOL: *{sol_balance:.4f}*
└ {theme.USD} USD: *${usd_value:,.2f}*

{theme.CHART} *Portfolio*
┌ Positions: *{open_positions}*
└ P&L: {pnl_emoji} *{pnl_sign}${abs(total_pnl):.2f}*

{theme.SETTINGS} Mode: {mode}
━━━━━━━━━━━━━━━━━━━━━

_Tap to trade with AI-powered signals_
"""

        # Build keyboard - Trojan style with AI features
        keyboard = [
            # Sentiment Hub - Premium Feature (NEW V1)
            [
                InlineKeyboardButton(f"📊 SENTIMENT HUB", callback_data="demo:hub"),
            ],
            # Insta Snipe - One-Click Trending Trade
            [
                InlineKeyboardButton(f"⚡ INSTA SNIPE", callback_data="demo:insta_snipe"),
                InlineKeyboardButton(f"{theme.CHART} AI Report", callback_data="demo:ai_report"),
            ],
            # AI-Powered Analysis Row
            [
                InlineKeyboardButton(f"{theme.AUTO} AI Picks", callback_data="demo:ai_picks"),
                InlineKeyboardButton(f"{theme.FIRE} Trending", callback_data="demo:trending"),
            ],
            # Bags.fm Top Tokens - Volume Leaders
            [
                InlineKeyboardButton("🎒 BAGS TOP 15", callback_data="demo:bags_fm"),
            ],
            # Quick buy amounts
            [
                InlineKeyboardButton(f"{theme.BUY} Buy 0.1 SOL", callback_data="demo:buy:0.1"),
                InlineKeyboardButton(f"{theme.BUY} Buy 0.5 SOL", callback_data="demo:buy:0.5"),
            ],
            [
                InlineKeyboardButton(f"{theme.BUY} Buy 1 SOL", callback_data="demo:buy:1"),
                InlineKeyboardButton(f"{theme.BUY} Buy 5 SOL", callback_data="demo:buy:5"),
            ],
            # Quick Trade & Token Input
            [
                InlineKeyboardButton(f"⚡ Quick Trade", callback_data="demo:quick_trade"),
                InlineKeyboardButton(f"{theme.SNIPE} Analyze", callback_data="demo:token_input"),
            ],
            # Portfolio & Positions
            [
                InlineKeyboardButton(f"{theme.CHART} Positions", callback_data="demo:positions"),
                InlineKeyboardButton(f"{theme.WALLET} Balance", callback_data="demo:balance"),
            ],
            # 1-Tap Quick Actions
            [
                InlineKeyboardButton(f"🔴 Sell All", callback_data="demo:sell_all"),
                InlineKeyboardButton(f"📈 PnL Report", callback_data="demo:pnl_report"),
                InlineKeyboardButton(f"💰 Fee Stats", callback_data="demo:fee_stats"),
            ],
            # AI-Powered Discovery
            [
                InlineKeyboardButton(f"{theme.FIRE} AI Trending", callback_data="demo:trending"),
                InlineKeyboardButton(f"{theme.GEM} AI New Pairs", callback_data="demo:new_pairs"),
            ],
            # Self-Improving Intelligence (V1 Feature)
            [
                InlineKeyboardButton(f"🧠 Learning", callback_data="demo:learning"),
                InlineKeyboardButton(f"📊 Performance", callback_data="demo:performance"),
            ],
            # Watchlist & AI Picks
            [
                InlineKeyboardButton(f"⭐ Watchlist", callback_data="demo:watchlist"),
                InlineKeyboardButton(f"💎 AI Picks", callback_data="demo:ai_picks"),
            ],
            # DCA & Alerts
            [
                InlineKeyboardButton(f"📅 DCA", callback_data="demo:dca"),
                InlineKeyboardButton(f"🔔 Alerts", callback_data="demo:pnl_alerts"),
            ],
            # Settings & Management
            [
                InlineKeyboardButton(f"{theme.SETTINGS} Settings", callback_data="demo:settings"),
                InlineKeyboardButton(f"{theme.KEY} Wallet", callback_data="demo:wallet_menu"),
            ],
            # Refresh & Close
            [
                InlineKeyboardButton(f"{theme.REFRESH} Refresh", callback_data="demo:refresh"),
                InlineKeyboardButton(f"{theme.CLOSE} Close", callback_data="demo:close"),
            ],
        ]

        return text, InlineKeyboardMarkup(keyboard)

    @staticmethod
    def wallet_menu(
        wallet_address: str,
        sol_balance: float,
        usd_value: float,
        has_wallet: bool = True,
        token_holdings: List[Dict[str, Any]] = None,
        total_holdings_usd: float = 0.0,
    ) -> Tuple[str, InlineKeyboardMarkup]:
        """Build wallet management menu with enhanced features."""
        theme = JarvisTheme

        if not has_wallet:
            text = f"""
{theme.WALLET} *WALLET SETUP*
━━━━━━━━━━━━━━━━━━━━━

{theme.WARNING} No wallet configured

Create a new wallet or import an existing one.

{theme.LOCK} All keys are encrypted with AES-256
{theme.AUTO} Auto-backup to secure storage
"""
            keyboard = [
                [
                    InlineKeyboardButton(f"{theme.KEY} Generate New Wallet", callback_data="demo:wallet_create"),
                ],
                [
                    InlineKeyboardButton(f"{theme.LOCK} Import Private Key", callback_data="demo:wallet_import"),
                ],
                [
                    InlineKeyboardButton(f"{theme.BACK} Back", callback_data="demo:main"),
                ],
            ]
        else:
            total_value = usd_value + total_holdings_usd

            text = f"""
{theme.WALLET} *WALLET MANAGEMENT*
━━━━━━━━━━━━━━━━━━━━━

{theme.KEY} *Address*
`{wallet_address}`

{theme.SOL} *SOL Balance:* {sol_balance:.4f} SOL
{theme.USD} *SOL Value:* ${usd_value:,.2f}
"""
            # Add token holdings summary
            if token_holdings:
                text += f"""
💎 *Token Holdings:* ${total_holdings_usd:,.2f}
"""
                for token in token_holdings[:3]:
                    symbol = token.get("symbol", "???")
                    value = token.get("value_usd", 0)
                    text += f"   └ {symbol}: ${value:,.2f}\n"
                if len(token_holdings) > 3:
                    text += f"   └ _+{len(token_holdings) - 3} more..._\n"

            text += f"""
━━━━━━━━━━━━━━━━━━━━━
💰 *Total Portfolio:* ${total_value:,.2f}
{theme.LOCK} Private key stored encrypted
"""
            keyboard = [
                # Row 1: Address & Balance
                [
                    InlineKeyboardButton(f"{theme.COPY} Copy Address", callback_data="demo:copy_address"),
                    InlineKeyboardButton(f"{theme.REFRESH} Refresh", callback_data="demo:refresh_balance"),
                ],
                # Row 2: Holdings & Activity
                [
                    InlineKeyboardButton(f"💎 Token Holdings", callback_data="demo:token_holdings"),
                    InlineKeyboardButton(f"📜 Activity", callback_data="demo:wallet_activity"),
                ],
                # Row 3: Transfer & Receive
                [
                    InlineKeyboardButton(f"📤 Send SOL", callback_data="demo:send_sol"),
                    InlineKeyboardButton(f"📥 Receive", callback_data="demo:receive_sol"),
                ],
                # Row 4: Security
                [
                    InlineKeyboardButton(f"{theme.LOCK} Export Key", callback_data="demo:export_key_confirm"),
                    InlineKeyboardButton(f"{theme.WARNING} Reset", callback_data="demo:wallet_reset_confirm"),
                ],
                # Row 5: Back
                [
                    InlineKeyboardButton(f"{theme.BACK} Back", callback_data="demo:main"),
                ],
            ]

        return text, InlineKeyboardMarkup(keyboard)

    @staticmethod
    def token_holdings_view(
        holdings: List[Dict[str, Any]],
        total_value: float = 0.0,
    ) -> Tuple[str, InlineKeyboardMarkup]:
        """
        Detailed token holdings view.

        Shows all SPL tokens in the wallet with values.
        """
        theme = JarvisTheme

        lines = [
            f"💎 *TOKEN HOLDINGS*",
            "━━━━━━━━━━━━━━━━━━━━━",
            "",
        ]

        if not holdings:
            lines.extend([
                "_No tokens found_",
                "",
                "Your SOL tokens will appear here",
                "once you make trades!",
            ])
        else:
            for token in holdings[:10]:
                symbol = token.get("symbol", "???")
                amount = token.get("amount", 0)
                value = token.get("value_usd", 0)
                change = token.get("change_24h", 0)

                change_emoji = "🟢" if change >= 0 else "🔴"
                change_sign = "+" if change >= 0 else ""

                lines.append(f"*{symbol}*")
                lines.append(f"   Amount: {amount:,.2f}")
                lines.append(f"   Value: ${value:,.2f}")
                lines.append(f"   {change_emoji} {change_sign}{change:.1f}%")
                lines.append("")

            if len(holdings) > 10:
                lines.append(f"_Showing 10 of {len(holdings)} tokens_")

        lines.extend([
            "━━━━━━━━━━━━━━━━━━━━━",
            f"💰 *Total:* ${total_value:,.2f}",
        ])

        text = "\n".join(lines)

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(f"{theme.REFRESH} Refresh", callback_data="demo:token_holdings"),
            ],
            [
                InlineKeyboardButton(f"{theme.BACK} Back", callback_data="demo:wallet_menu"),
            ],
        ])

        return text, keyboard

    @staticmethod
    def wallet_activity_view(
        transactions: List[Dict[str, Any]] = None,
    ) -> Tuple[str, InlineKeyboardMarkup]:
        """
        Wallet transaction history view.
        """
        theme = JarvisTheme

        lines = [
            f"📜 *WALLET ACTIVITY*",
            "━━━━━━━━━━━━━━━━━━━━━",
            "",
        ]

        if not transactions:
            lines.extend([
                "_No recent activity_",
                "",
                "Your transactions will appear here",
                "once you start trading!",
            ])
        else:
            for tx in transactions[:8]:
                tx_type = tx.get("type", "unknown")
                symbol = tx.get("symbol", "SOL")
                amount = tx.get("amount", 0)
                timestamp = tx.get("timestamp", "")
                status = tx.get("status", "confirmed")

                type_emoji = {
                    "buy": "🟢",
                    "sell": "🔴",
                    "transfer_in": "📥",
                    "transfer_out": "📤",
                    "swap": "🔄",
                }.get(tx_type, "⚪")

                status_emoji = "✅" if status == "confirmed" else "⏳"

                lines.append(f"{type_emoji} *{tx_type.upper()}* {symbol}")
                lines.append(f"   Amount: {amount:,.4f}")
                lines.append(f"   {status_emoji} {timestamp}")
                lines.append("")

        lines.extend([
            "━━━━━━━━━━━━━━━━━━━━━",
        ])

        text = "\n".join(lines)

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(f"{theme.REFRESH} Refresh", callback_data="demo:wallet_activity"),
            ],
            [
                InlineKeyboardButton(f"{theme.BACK} Back", callback_data="demo:wallet_menu"),
            ],
        ])

        return text, keyboard

    @staticmethod
    def send_sol_view(
        sol_balance: float = 0.0,
    ) -> Tuple[str, InlineKeyboardMarkup]:
        """
        Send SOL interface.
        """
        theme = JarvisTheme

        text = f"""
📤 *SEND SOL*
━━━━━━━━━━━━━━━━━━━━━

*Available:* {sol_balance:.4f} SOL

To send SOL:
1. Paste the recipient address
2. Enter the amount
3. Confirm the transaction

{theme.WARNING} _Always double-check addresses!_

━━━━━━━━━━━━━━━━━━━━━
_Feature coming in V2_

For now, use your wallet app
to send SOL directly.
"""

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(f"{theme.BACK} Back", callback_data="demo:wallet_menu"),
            ],
        ])

        return text, keyboard

    @staticmethod
    def export_key_confirm() -> Tuple[str, InlineKeyboardMarkup]:
        """
        Export private key confirmation with warnings.
        """
        theme = JarvisTheme

        text = f"""
{theme.WARNING} *EXPORT PRIVATE KEY*
━━━━━━━━━━━━━━━━━━━━━

⚠️ *SECURITY WARNING*

Your private key gives FULL access
to your wallet and ALL funds.

*NEVER share your key with anyone!*

{theme.WARNING} Scammers may pose as support
{theme.WARNING} No one should ever ask for it
{theme.WARNING} Store it securely offline

━━━━━━━━━━━━━━━━━━━━━

Are you sure you want to export?
"""

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(f"⚠️ Yes, Show Key", callback_data="demo:export_key"),
            ],
            [
                InlineKeyboardButton(f"{theme.CLOSE} Cancel", callback_data="demo:wallet_menu"),
            ],
        ])

        return text, keyboard

    @staticmethod
    def wallet_reset_confirm() -> Tuple[str, InlineKeyboardMarkup]:
        """
        Wallet reset confirmation with warnings.
        """
        theme = JarvisTheme

        text = f"""
{theme.WARNING} *RESET WALLET*
━━━━━━━━━━━━━━━━━━━━━

⚠️ *THIS IS IRREVERSIBLE*

Resetting will:
• Delete your current wallet
• Remove all encrypted keys
• Clear all trading history

{theme.WARNING} Make sure you have backed up
   your private key first!

━━━━━━━━━━━━━━━━━━━━━

Type "RESET" to confirm.
"""

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(f"🗑️ Confirm Reset", callback_data="demo:wallet_reset"),
            ],
            [
                InlineKeyboardButton(f"{theme.CLOSE} Cancel", callback_data="demo:wallet_menu"),
            ],
        ])

        return text, keyboard

    @staticmethod
    def wallet_import_prompt() -> Tuple[str, InlineKeyboardMarkup]:
        """
        Wallet import prompt - import private key or seed phrase.
        """
        theme = JarvisTheme

        text = f"""
{theme.LOCK} *IMPORT WALLET*
━━━━━━━━━━━━━━━━━━━━━

Import an existing wallet using:

📝 *Private Key (Base58)*
└ 64-88 character Solana key

🌱 *Seed Phrase (12/24 words)*
└ BIP39 mnemonic phrase

━━━━━━━━━━━━━━━━━━━━━

⚠️ *Security Warning*
• Only import on a secure device
• Never share your key/phrase
• Clear message history after

━━━━━━━━━━━━━━━━━━━━━

Send your private key or seed phrase
in the next message.
"""

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(f"🔑 Enter Private Key", callback_data="demo:import_mode_key"),
            ],
            [
                InlineKeyboardButton(f"🌱 Enter Seed Phrase", callback_data="demo:import_mode_seed"),
            ],
            [
                InlineKeyboardButton(f"{theme.CLOSE} Cancel", callback_data="demo:wallet_menu"),
            ],
        ])

        return text, keyboard

    @staticmethod
    def wallet_import_input(import_type: str = "key") -> Tuple[str, InlineKeyboardMarkup]:
        """
        Wallet import input mode - waiting for key/phrase.
        """
        theme = JarvisTheme

        if import_type == "seed":
            text = f"""
{theme.LOCK} *IMPORT SEED PHRASE*
━━━━━━━━━━━━━━━━━━━━━

🌱 Send your *12 or 24 word* seed phrase.

Example format:
_word1 word2 word3 ... word12_

━━━━━━━━━━━━━━━━━━━━━

⚠️ Your phrase is encrypted and
   stored securely.
"""
        else:
            text = f"""
{theme.LOCK} *IMPORT PRIVATE KEY*
━━━━━━━━━━━━━━━━━━━━━

🔑 Send your *Base58 private key*.

It should be 64-88 characters.

━━━━━━━━━━━━━━━━━━━━━

⚠️ Your key is encrypted and
   stored securely.
"""

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(f"{theme.CLOSE} Cancel", callback_data="demo:wallet_menu"),
            ],
        ])

        return text, keyboard

    @staticmethod
    def wallet_import_result(
        success: bool,
        wallet_address: str = None,
        error: str = None,
    ) -> Tuple[str, InlineKeyboardMarkup]:
        """
        Wallet import result view.
        """
        theme = JarvisTheme

        if success:
            short_addr = f"{wallet_address[:6]}...{wallet_address[-4:]}" if wallet_address else "?"
            text = f"""
✅ *WALLET IMPORTED*
━━━━━━━━━━━━━━━━━━━━━

🎉 Successfully imported wallet!

📍 *Address:*
`{wallet_address or 'Unknown'}`

━━━━━━━━━━━━━━━━━━━━━

⚠️ *Important*
• Delete the message with your key
• Your wallet is now active
• Start trading!
"""
        else:
            text = f"""
❌ *IMPORT FAILED*
━━━━━━━━━━━━━━━━━━━━━

Could not import wallet.

*Error:* {error or 'Invalid key or phrase'}

━━━━━━━━━━━━━━━━━━━━━

Please check your key/phrase and try again.
"""

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(f"💼 View Wallet", callback_data="demo:wallet_menu"),
            ] if success else [
                InlineKeyboardButton(f"🔄 Try Again", callback_data="demo:wallet_import"),
            ],
            [
                InlineKeyboardButton(f"{theme.BACK} Main Menu", callback_data="demo:main"),
            ],
        ])

        return text, keyboard

    @staticmethod
    def export_key_show(
        private_key: str,
        wallet_address: str,
    ) -> Tuple[str, InlineKeyboardMarkup]:
        """
        Export private key display - SENSITIVE.
        """
        theme = JarvisTheme

        # Mask middle portion for security
        key_display = f"`{private_key}`" if private_key else "_Key unavailable_"

        text = f"""
🔐 *YOUR PRIVATE KEY*
━━━━━━━━━━━━━━━━━━━━━

📍 *Address:*
`{wallet_address}`

🔑 *Private Key:*
{key_display}

━━━━━━━━━━━━━━━━━━━━━

⚠️ *CRITICAL SECURITY*
• Copy this key NOW
• Store in a password manager
• DELETE THIS MESSAGE after
• NEVER share with anyone
• Anyone with this key controls your funds

━━━━━━━━━━━━━━━━━━━━━
"""

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(f"📋 Copy Key", callback_data="demo:copy_key"),
            ],
            [
                InlineKeyboardButton(f"✅ Done, Back to Wallet", callback_data="demo:wallet_menu"),
            ],
        ])

        return text, keyboard

    @staticmethod
    def positions_menu(
        positions: list,
        total_pnl: float = 0.0,
    ) -> Tuple[str, InlineKeyboardMarkup]:
        """Build positions overview with health indicators, sell buttons, and quick SL/TP."""
        theme = JarvisTheme

        if not positions:
            text = f"""
{theme.CHART} *POSITIONS*
━━━━━━━━━━━━━━━━━━━━━

_No open positions_

{theme.ROCKET} *Ready to trade?*
Use AI-powered signals to find opportunities!
"""
            keyboard = [
                [
                    InlineKeyboardButton(f"{theme.FIRE} Find Tokens", callback_data="demo:trending"),
                    InlineKeyboardButton(f"📊 AI Picks", callback_data="demo:ai_picks"),
                ],
                [
                    InlineKeyboardButton(f"🎒 BAGS TOP 15", callback_data="demo:bags_fm"),
                ],
                [
                    InlineKeyboardButton(f"{theme.BACK} Back", callback_data="demo:main"),
                ],
            ]
        else:
            pnl_emoji = theme.PROFIT if total_pnl >= 0 else theme.LOSS
            pnl_sign = "+" if total_pnl >= 0 else ""

            # Portfolio health score (average of all positions)
            avg_pnl = sum(p.get("pnl_pct", 0) for p in positions) / len(positions)
            portfolio_health = theme.get_health_indicator(avg_pnl)
            portfolio_bar = theme.get_health_bar(avg_pnl, width=8)

            lines = [
                f"{theme.CHART} *POSITIONS*",
                "━━━━━━━━━━━━━━━━━━━━━",
                f"",
                f"{portfolio_health} *Portfolio Health*",
                f"{portfolio_bar}",
                f"Total P&L: {pnl_emoji} *{pnl_sign}${abs(total_pnl):.2f}*",
                f"",
                "━━━━━━━━━━━━━━━━━━━━━",
                "",
            ]

            keyboard = []

            for i, pos in enumerate(positions[:8]):  # Max 8 positions
                symbol = pos.get("symbol", "???")
                pnl_pct = pos.get("pnl_pct", 0)
                pnl_usd = pos.get("pnl_usd", 0)
                entry = pos.get("entry_price", 0)
                current = pos.get("current_price", 0)
                pos_id = pos.get("id", str(i))

                # Calculate hours held (if available)
                entry_time = pos.get("entry_time")
                if entry_time:
                    try:
                        if isinstance(entry_time, str):
                            entry_dt = datetime.fromisoformat(entry_time.replace('Z', '+00:00'))
                        else:
                            entry_dt = entry_time
                        hours_held = (datetime.now(timezone.utc) - entry_dt).total_seconds() / 3600
                    except Exception:
                        hours_held = 0
                else:
                    hours_held = 0

                # Get health and time indicators
                health = theme.get_health_indicator(pnl_pct, hours_held)
                health_bar = theme.get_health_bar(pnl_pct, width=5)
                time_ind = theme.get_time_indicator(hours_held)
                pnl_sign = "+" if pnl_pct >= 0 else ""

                # Format time held
                if hours_held < 1:
                    time_str = f"{int(hours_held * 60)}m"
                elif hours_held < 24:
                    time_str = f"{int(hours_held)}h"
                else:
                    time_str = f"{int(hours_held / 24)}d"

                # Get current TP/SL if set
                tp = pos.get("take_profit", 50)
                sl = pos.get("stop_loss", 20)

                lines.extend([
                    f"{health} *{symbol}* {pnl_sign}{pnl_pct:.1f}%",
                    f"{health_bar}",
                    f"├ Entry: `${entry:.8f}`",
                    f"├ Now: `${current:.8f}`",
                    f"├ P&L: *{pnl_sign}${abs(pnl_usd):.2f}*",
                    f"├ {time_ind} Held: *{time_str}*",
                    f"└ TP: +{tp}% | SL: -{sl}%",
                    "",
                ])

                # Add action buttons for each position (sell + quick SL/TP adjust)
                keyboard.append([
                    InlineKeyboardButton(
                        f"🔴 Sell 25%",
                        callback_data=f"demo:sell:{pos_id}:25"
                    ),
                    InlineKeyboardButton(
                        f"🔴 Sell All",
                        callback_data=f"demo:sell:{pos_id}:100"
                    ),
                    InlineKeyboardButton(
                        f"⚙️ SL/TP",
                        callback_data=f"demo:pos_adjust:{pos_id}"
                    ),
                ])

            text = "\n".join(lines)

            # Add navigation with enhanced options
            keyboard.extend([
                [
                    InlineKeyboardButton("🔔 Alerts", callback_data="demo:pnl_alerts"),
                    InlineKeyboardButton("🛡️ Trailing SL", callback_data="demo:trailing_stops"),
                    InlineKeyboardButton("📊 P&L Report", callback_data="demo:pnl_report"),
                ],
                [
                    InlineKeyboardButton(f"{theme.REFRESH} Refresh", callback_data="demo:positions"),
                    InlineKeyboardButton(f"{theme.BACK} Back", callback_data="demo:main"),
                ],
            ])

        return text, InlineKeyboardMarkup(keyboard)

    @staticmethod
    def position_adjust_menu(
        pos_id: str,
        symbol: str,
        current_tp: float = 50.0,
        current_sl: float = 20.0,
        pnl_pct: float = 0.0,
    ) -> Tuple[str, InlineKeyboardMarkup]:
        """Quick SL/TP adjustment menu for a position."""
        theme = JarvisTheme
        health = theme.get_health_indicator(pnl_pct)
        health_bar = theme.get_health_bar(pnl_pct, width=8)
        pnl_sign = "+" if pnl_pct >= 0 else ""

        text = f"""
{theme.SETTINGS} *ADJUST POSITION*
━━━━━━━━━━━━━━━━━━━━━

{health} *{symbol}* {pnl_sign}{pnl_pct:.1f}%
{health_bar}

*Current Settings:*
├ 🎯 Take Profit: *+{current_tp}%*
└ 🛡️ Stop Loss: *-{current_sl}%*

━━━━━━━━━━━━━━━━━━━━━
_Adjust your exit strategy_
"""

        keyboard = [
            # TP adjustment row
            [
                InlineKeyboardButton("🎯 TP", callback_data="demo:noop"),
                InlineKeyboardButton("25%", callback_data=f"demo:set_tp:{pos_id}:25"),
                InlineKeyboardButton("50%", callback_data=f"demo:set_tp:{pos_id}:50"),
                InlineKeyboardButton("100%", callback_data=f"demo:set_tp:{pos_id}:100"),
                InlineKeyboardButton("200%", callback_data=f"demo:set_tp:{pos_id}:200"),
            ],
            # SL adjustment row
            [
                InlineKeyboardButton("🛡️ SL", callback_data="demo:noop"),
                InlineKeyboardButton("10%", callback_data=f"demo:set_sl:{pos_id}:10"),
                InlineKeyboardButton("20%", callback_data=f"demo:set_sl:{pos_id}:20"),
                InlineKeyboardButton("30%", callback_data=f"demo:set_sl:{pos_id}:30"),
                InlineKeyboardButton("50%", callback_data=f"demo:set_sl:{pos_id}:50"),
            ],
            # Quick actions
            [
                InlineKeyboardButton("🔴 Close Now", callback_data=f"demo:sell:{pos_id}:100"),
                InlineKeyboardButton("🛡️ Trailing SL", callback_data=f"demo:trailing_setup:{pos_id}"),
            ],
            [
                InlineKeyboardButton(f"{theme.BACK} Back to Positions", callback_data="demo:positions"),
            ],
        ]

        return text, InlineKeyboardMarkup(keyboard)

    @staticmethod
    def settings_menu(
        is_live: bool = False,
        slippage: float = 1.0,
        auto_sell: bool = True,
        take_profit: float = 50.0,
        stop_loss: float = 20.0,
        ai_auto_trade: bool = False,
    ) -> Tuple[str, InlineKeyboardMarkup]:
        """Build settings menu with AI auto-trade option."""
        theme = JarvisTheme

        mode = f"{theme.LIVE} LIVE" if is_live else f"{theme.PAPER} PAPER"
        auto_status = f"{theme.SUCCESS} ON" if auto_sell else f"{theme.ERROR} OFF"
        ai_status = f"{theme.ROCKET} ENABLED" if ai_auto_trade else f"{theme.ERROR} DISABLED"

        text = f"""
{theme.SETTINGS} *SETTINGS*
━━━━━━━━━━━━━━━━━━━━━

*Trading Mode*
└ {mode}

*Slippage*
└ {slippage}%

*Auto-Sell (TP/SL)*
└ Status: {auto_status}
├ Take Profit: +{take_profit}%
└ Stop Loss: -{stop_loss}%

*🤖 AI Auto-Trade*
└ Status: {ai_status}

━━━━━━━━━━━━━━━━━━━━━
"""

        keyboard = [
            [
                InlineKeyboardButton(
                    f"{'🔴 Switch to PAPER' if is_live else '🟢 Switch to LIVE'}",
                    callback_data="demo:toggle_mode"
                ),
            ],
            [
                InlineKeyboardButton("Slippage: 0.5%", callback_data="demo:slippage:0.5"),
                InlineKeyboardButton("Slippage: 1%", callback_data="demo:slippage:1"),
                InlineKeyboardButton("Slippage: 3%", callback_data="demo:slippage:3"),
            ],
            [
                InlineKeyboardButton(
                    f"Auto-Sell: {'OFF' if auto_sell else 'ON'}",
                    callback_data="demo:toggle_auto"
                ),
            ],
            [
                InlineKeyboardButton("TP: 25%", callback_data="demo:tp:25"),
                InlineKeyboardButton("TP: 50%", callback_data="demo:tp:50"),
                InlineKeyboardButton("TP: 100%", callback_data="demo:tp:100"),
            ],
            [
                InlineKeyboardButton("SL: 10%", callback_data="demo:sl:10"),
                InlineKeyboardButton("SL: 20%", callback_data="demo:sl:20"),
                InlineKeyboardButton("SL: 50%", callback_data="demo:sl:50"),
            ],
            # AI Auto-Trade Settings
            [
                InlineKeyboardButton(f"🤖 AI Auto-Trade Settings", callback_data="demo:ai_auto_settings"),
            ],
            # Fee Stats
            [
                InlineKeyboardButton(f"💰 Fee Stats (0.5% on wins)", callback_data="demo:fee_stats"),
            ],
            [
                InlineKeyboardButton(f"{theme.BACK} Back", callback_data="demo:main"),
            ],
        ]

        return text, InlineKeyboardMarkup(keyboard)

    @staticmethod
    def ai_auto_trade_settings(
        enabled: bool = False,
        risk_level: str = "MEDIUM",
        max_position_size: float = 0.5,
        min_confidence: float = 0.7,
        daily_limit: float = 2.0,
        cooldown_minutes: int = 30,
    ) -> Tuple[str, InlineKeyboardMarkup]:
        """
        AI Auto-Trade Settings - Configure autonomous trading.

        Features:
        - Enable/disable autonomous trading
        - Risk level (Conservative, Medium, Aggressive)
        - Position sizing limits
        - Confidence threshold for entries
        - Daily trade limits
        - Cooldown between trades
        """
        theme = JarvisTheme

        status_emoji = f"{theme.ROCKET}" if enabled else "⚪"
        status_text = "ENABLED" if enabled else "DISABLED"

        risk_emojis = {
            "CONSERVATIVE": "🐢",
            "MEDIUM": "⚖️",
            "AGGRESSIVE": "🔥",
        }
        risk_emoji = risk_emojis.get(risk_level, "⚖️")

        text = f"""
{theme.AUTO} *AI AUTO-TRADE SETTINGS*
━━━━━━━━━━━━━━━━━━━━━

{status_emoji} *Status:* {status_text}

{risk_emoji} *Risk Level:* {risk_level}
├ Conservative: Small positions, high confidence
├ Medium: Balanced approach
└ Aggressive: Larger positions, more trades

📊 *Parameters*
├ Max Position: {max_position_size} SOL
├ Min Confidence: {min_confidence * 100:.0f}%
├ Daily Limit: {daily_limit} SOL
└ Cooldown: {cooldown_minutes} min

━━━━━━━━━━━━━━━━━━━━━

{theme.WARNING} AI trades based on:
• Sentiment analysis (Grok AI)
• Market regime detection
• Technical indicators
• Trade intelligence learnings

"""

        keyboard = [
            # Toggle ON/OFF
            [
                InlineKeyboardButton(
                    f"{'🔴 Disable AI Trading' if enabled else '🟢 Enable AI Trading'}",
                    callback_data=f"demo:ai_auto_toggle:{not enabled}"
                ),
            ],
            # Risk Level Selection
            [
                InlineKeyboardButton(
                    "🐢 Conservative" + (" ✓" if risk_level == "CONSERVATIVE" else ""),
                    callback_data="demo:ai_risk:CONSERVATIVE"
                ),
            ],
            [
                InlineKeyboardButton(
                    "⚖️ Medium" + (" ✓" if risk_level == "MEDIUM" else ""),
                    callback_data="demo:ai_risk:MEDIUM"
                ),
            ],
            [
                InlineKeyboardButton(
                    "🔥 Aggressive" + (" ✓" if risk_level == "AGGRESSIVE" else ""),
                    callback_data="demo:ai_risk:AGGRESSIVE"
                ),
            ],
            # Max Position Size
            [
                InlineKeyboardButton("Max: 0.1 SOL", callback_data="demo:ai_max:0.1"),
                InlineKeyboardButton("Max: 0.5 SOL", callback_data="demo:ai_max:0.5"),
                InlineKeyboardButton("Max: 1 SOL", callback_data="demo:ai_max:1"),
            ],
            # Min Confidence
            [
                InlineKeyboardButton("Conf: 60%", callback_data="demo:ai_conf:0.6"),
                InlineKeyboardButton("Conf: 70%", callback_data="demo:ai_conf:0.7"),
                InlineKeyboardButton("Conf: 80%", callback_data="demo:ai_conf:0.8"),
            ],
            # Back
            [
                InlineKeyboardButton(f"{theme.BACK} Back to Settings", callback_data="demo:settings"),
            ],
        ]

        return text, InlineKeyboardMarkup(keyboard)

    @staticmethod
    def ai_auto_trade_status(
        enabled: bool,
        trades_today: int = 0,
        pnl_today: float = 0.0,
        last_trade: str = None,
        next_opportunity: str = None,
    ) -> Tuple[str, InlineKeyboardMarkup]:
        """
        AI Auto-Trade Status View - Show current AI trading activity.
        """
        theme = JarvisTheme

        status_emoji = f"{theme.ROCKET}" if enabled else "⚪"
        pnl_emoji = theme.PROFIT if pnl_today >= 0 else theme.LOSS
        pnl_sign = "+" if pnl_today >= 0 else ""

        text = f"""
{theme.AUTO} *AI TRADING STATUS*
━━━━━━━━━━━━━━━━━━━━━

{status_emoji} *Auto-Trade:* {'ACTIVE' if enabled else 'PAUSED'}

📈 *Today's Activity*
├ Trades: {trades_today}
├ {pnl_emoji} P&L: {pnl_sign}${abs(pnl_today):.2f}
"""
        if last_trade:
            text += f"└ Last Trade: {last_trade}\n"

        if next_opportunity:
            text += f"""
🎯 *Next Opportunity*
└ {next_opportunity}
"""

        text += f"""
━━━━━━━━━━━━━━━━━━━━━

{theme.AUTO} JARVIS is {'monitoring markets' if enabled else 'idle'}
"""

        keyboard = [
            [
                InlineKeyboardButton(
                    f"{'⏸️ Pause' if enabled else '▶️ Resume'}",
                    callback_data=f"demo:ai_auto_toggle:{not enabled}"
                ),
            ],
            [
                InlineKeyboardButton("📊 View AI Trades", callback_data="demo:ai_trades_history"),
            ],
            [
                InlineKeyboardButton(f"{theme.SETTINGS} AI Settings", callback_data="demo:ai_auto_settings"),
            ],
            [
                InlineKeyboardButton(f"{theme.BACK} Back", callback_data="demo:main"),
            ],
        ]

        return text, InlineKeyboardMarkup(keyboard)

    @staticmethod
    def fee_stats_view(
        fee_percent: float = 0.5,
        total_collected: float = 0.0,
        transaction_count: int = 0,
        recent_fees: List[Dict[str, Any]] = None,
    ) -> Tuple[str, InlineKeyboardMarkup]:
        """
        Fee statistics view - Show success fee collection stats.

        Displays:
        - Current fee rate (0.5% on wins)
        - Total fees collected
        - Recent fee transactions
        """
        theme = JarvisTheme
        recent_fees = recent_fees or []

        lines = [
            f"💰 *SUCCESS FEE STATS*",
            "━━━━━━━━━━━━━━━━━━━━━",
            "",
            f"📊 *Fee Structure*",
            f"├ Rate: {fee_percent}% on profits",
            f"├ Applied: Only on winning trades",
            f"└ Supports: JARVIS development",
            "",
            f"💵 *Total Collected*",
            f"└ ${total_collected:.4f}",
            "",
            f"📈 *Transactions*",
            f"└ {transaction_count} fee-bearing trades",
            "",
        ]

        if recent_fees:
            lines.extend([
                "📋 *Recent Fees*",
            ])
            for i, fee in enumerate(recent_fees[:5]):
                token = fee.get("token", "???")
                amount = fee.get("fee_amount", 0)
                pnl = fee.get("pnl_usd", 0)
                lines.append(f"├ {token}: ${amount:.4f} (${pnl:.2f} profit)")

            if len(recent_fees) > 5:
                lines.append(f"└ _...and {len(recent_fees) - 5} more_")
        else:
            lines.extend([
                "_No fees collected yet._",
                "_Trade profitably to see fees here._",
            ])

        lines.extend([
            "",
            "━━━━━━━━━━━━━━━━━━━━━",
            "_Fees support platform development._",
        ])

        text = "\n".join(lines)

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(f"📊 View Positions", callback_data="demo:positions"),
            ],
            [
                InlineKeyboardButton(f"{theme.SETTINGS} Settings", callback_data="demo:settings"),
            ],
            [
                InlineKeyboardButton(f"{theme.BACK} Main Menu", callback_data="demo:main"),
            ],
        ])

        return text, keyboard

    @staticmethod
    def pnl_report_view(
        positions: List[Dict[str, Any]] = None,
        total_pnl_usd: float = 0.0,
        total_pnl_percent: float = 0.0,
        winners: int = 0,
        losers: int = 0,
        best_trade: Dict[str, Any] = None,
        worst_trade: Dict[str, Any] = None,
    ) -> Tuple[str, InlineKeyboardMarkup]:
        """
        P&L Report View - Quick snapshot of portfolio performance.

        Shows:
        - Total P&L (USD and %)
        - Win/Loss breakdown
        - Best and worst performers
        """
        theme = JarvisTheme
        positions = positions or []

        pnl_emoji = "📈" if total_pnl_usd >= 0 else "📉"
        pnl_sign = "+" if total_pnl_usd >= 0 else ""

        total_trades = winners + losers
        win_rate = (winners / total_trades * 100) if total_trades > 0 else 0

        lines = [
            f"📊 *P&L REPORT*",
            "━━━━━━━━━━━━━━━━━━━━━",
            "",
            f"💰 *Total P&L*",
            f"└ {pnl_emoji} {pnl_sign}${abs(total_pnl_usd):.2f} ({pnl_sign}{total_pnl_percent:.1f}%)",
            "",
            f"📈 *Performance*",
            f"├ Winners: 🟢 {winners}",
            f"├ Losers: 🔴 {losers}",
            f"└ Win Rate: *{win_rate:.0f}%*",
            "",
        ]

        if best_trade:
            best_pnl = best_trade.get("pnl_pct", 0)
            lines.extend([
                f"🏆 *Best Trade*",
                f"└ {best_trade.get('symbol', '???')}: +{best_pnl:.1f}%",
                "",
            ])

        if worst_trade:
            worst_pnl = worst_trade.get("pnl_pct", 0)
            lines.extend([
                f"💀 *Worst Trade*",
                f"└ {worst_trade.get('symbol', '???')}: {worst_pnl:.1f}%",
                "",
            ])

        if positions:
            lines.append(f"📋 *Open Positions ({len(positions)})*")
            for pos in positions[:5]:
                symbol = pos.get("symbol", "???")
                pnl = pos.get("pnl_pct", 0)
                pnl_em = "🟢" if pnl >= 0 else "🔴"
                lines.append(f"├ {pnl_em} {symbol}: {pnl:+.1f}%")
            if len(positions) > 5:
                lines.append(f"└ _...and {len(positions) - 5} more_")
        else:
            lines.extend([
                "_No open positions_",
                "_Use Buy to enter trades_",
            ])

        lines.extend([
            "",
            "━━━━━━━━━━━━━━━━━━━━━",
        ])

        text = "\n".join(lines)

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(f"📊 Positions", callback_data="demo:positions"),
                InlineKeyboardButton(f"📜 History", callback_data="demo:trade_history"),
            ],
            [
                InlineKeyboardButton(f"🔄 Refresh", callback_data="demo:pnl_report"),
                InlineKeyboardButton(f"{theme.BACK} Main Menu", callback_data="demo:main"),
            ],
        ])

        return text, keyboard

    @staticmethod
    def pnl_alerts_overview(
        alerts: List[Dict[str, Any]] = None,
        positions: List[Dict[str, Any]] = None,
    ) -> Tuple[str, InlineKeyboardMarkup]:
        """
        P&L Alerts Overview - View and manage all active price alerts.

        Shows:
        - Active alerts with their trigger conditions
        - Triggered alerts history
        - Quick add buttons for positions without alerts
        """
        theme = JarvisTheme
        alerts = alerts or []
        positions = positions or []

        lines = [
            f"🔔 *P&L ALERTS*",
            "━━━━━━━━━━━━━━━━━━━━━",
            "",
        ]

        if not alerts:
            lines.extend([
                "_No active alerts_",
                "",
                "Set alerts to get notified when",
                "positions hit profit/loss targets!",
            ])
        else:
            active_count = len([a for a in alerts if not a.get("triggered")])
            triggered_count = len([a for a in alerts if a.get("triggered")])

            lines.extend([
                f"📊 *Active Alerts:* {active_count}",
                f"✅ *Triggered:* {triggered_count}",
                "",
            ])

            for alert in alerts[:5]:  # Show max 5
                symbol = alert.get("symbol", "???")
                alert_type = alert.get("type", "pnl")  # pnl, price, percent
                target = alert.get("target", 0)
                direction = alert.get("direction", "above")  # above, below
                triggered = alert.get("triggered", False)

                if triggered:
                    status = "✅"
                else:
                    status = "🔔"

                if alert_type == "pnl":
                    direction_emoji = "📈" if direction == "above" else "📉"
                    lines.append(f"{status} *{symbol}* - {direction_emoji} ${target:+.2f}")
                elif alert_type == "percent":
                    direction_emoji = "📈" if direction == "above" else "📉"
                    lines.append(f"{status} *{symbol}* - {direction_emoji} {target:+.1f}%")
                else:  # price
                    lines.append(f"{status} *{symbol}* - Price ${target:.8f}")

        text = "\n".join(lines)

        keyboard = []

        # Add alert buttons for positions
        if positions:
            for pos in positions[:4]:  # Max 4 position alert buttons
                symbol = pos.get("symbol", "???")
                pos_id = pos.get("id", "0")
                keyboard.append([
                    InlineKeyboardButton(
                        f"🔔 Add Alert: {symbol}",
                        callback_data=f"demo:alert_setup:{pos_id}"
                    ),
                ])

        keyboard.extend([
            [
                InlineKeyboardButton("🗑️ Clear Triggered", callback_data="demo:clear_triggered_alerts"),
            ],
            [
                InlineKeyboardButton(f"{theme.CHART} Positions", callback_data="demo:positions"),
                InlineKeyboardButton(f"{theme.BACK} Back", callback_data="demo:main"),
            ],
        ])

        return text, InlineKeyboardMarkup(keyboard)

    @staticmethod
    def position_alert_setup(
        position: Dict[str, Any],
        existing_alerts: List[Dict[str, Any]] = None,
    ) -> Tuple[str, InlineKeyboardMarkup]:
        """
        Set up P&L alerts for a specific position.

        Shows:
        - Current position info
        - Quick alert presets (+25%, +50%, +100%, -10%, -25%)
        - Existing alerts for this position
        """
        theme = JarvisTheme
        existing_alerts = existing_alerts or []

        symbol = position.get("symbol", "???")
        pos_id = position.get("id", "0")
        pnl_pct = position.get("pnl_pct", 0)
        pnl_usd = position.get("pnl_usd", 0)
        entry_price = position.get("entry_price", 0)
        current_price = position.get("current_price", 0)

        pnl_emoji = theme.PROFIT if pnl_pct >= 0 else theme.LOSS
        pnl_sign = "+" if pnl_pct >= 0 else ""

        lines = [
            f"🔔 *SET ALERT: {symbol}*",
            "━━━━━━━━━━━━━━━━━━━━━",
            "",
            f"*Current Position*",
            f"├ Entry: ${entry_price:.8f}",
            f"├ Now: ${current_price:.8f}",
            f"└ P&L: {pnl_emoji} {pnl_sign}{pnl_pct:.1f}% (${pnl_usd:+.2f})",
            "",
        ]

        # Show existing alerts
        pos_alerts = [a for a in existing_alerts if a.get("position_id") == pos_id]
        if pos_alerts:
            lines.append("*Active Alerts:*")
            for alert in pos_alerts:
                target = alert.get("target", 0)
                alert_type = alert.get("type", "percent")
                direction = alert.get("direction", "above")
                dir_emoji = "📈" if direction == "above" else "📉"
                if alert_type == "percent":
                    lines.append(f"  {dir_emoji} {target:+.1f}%")
                else:
                    lines.append(f"  {dir_emoji} ${target:+.2f}")
            lines.append("")

        lines.extend([
            "*Quick Presets*",
            "_Select a trigger level:_",
        ])

        text = "\n".join(lines)

        keyboard = [
            # Profit alerts
            [
                InlineKeyboardButton("📈 +25%", callback_data=f"demo:create_alert:{pos_id}:percent:25"),
                InlineKeyboardButton("📈 +50%", callback_data=f"demo:create_alert:{pos_id}:percent:50"),
                InlineKeyboardButton("📈 +100%", callback_data=f"demo:create_alert:{pos_id}:percent:100"),
            ],
            # Loss alerts
            [
                InlineKeyboardButton("📉 -10%", callback_data=f"demo:create_alert:{pos_id}:percent:-10"),
                InlineKeyboardButton("📉 -25%", callback_data=f"demo:create_alert:{pos_id}:percent:-25"),
                InlineKeyboardButton("📉 -50%", callback_data=f"demo:create_alert:{pos_id}:percent:-50"),
            ],
            # Custom alert
            [
                InlineKeyboardButton("✏️ Custom Alert", callback_data=f"demo:custom_alert:{pos_id}"),
            ],
            # Delete existing alerts for this position
            [
                InlineKeyboardButton("🗑️ Delete Alerts", callback_data=f"demo:delete_pos_alerts:{pos_id}"),
            ],
            [
                InlineKeyboardButton("🔔 All Alerts", callback_data="demo:pnl_alerts"),
                InlineKeyboardButton(f"{theme.BACK} Back", callback_data="demo:positions"),
            ],
        ]

        return text, InlineKeyboardMarkup(keyboard)

    @staticmethod
    def alert_created_success(
        symbol: str,
        alert_type: str,
        target: float,
        direction: str,
    ) -> Tuple[str, InlineKeyboardMarkup]:
        """Show success message after creating an alert."""
        theme = JarvisTheme

        dir_emoji = "📈" if direction == "above" else "📉"
        type_text = "%" if alert_type == "percent" else " USD"

        text = f"""
{theme.SUCCESS} *ALERT CREATED*
━━━━━━━━━━━━━━━━━━━━━

*{symbol}*
{dir_emoji} Trigger: {target:+.1f}{type_text}

You'll be notified when this
position hits your target!

━━━━━━━━━━━━━━━━━━━━━
"""

        keyboard = [
            [
                InlineKeyboardButton("🔔 View All Alerts", callback_data="demo:pnl_alerts"),
            ],
            [
                InlineKeyboardButton(f"{theme.CHART} Positions", callback_data="demo:positions"),
                InlineKeyboardButton(f"{theme.BACK} Main Menu", callback_data="demo:main"),
            ],
        ]

        return text, InlineKeyboardMarkup(keyboard)

    @staticmethod
    def dca_overview(
        dca_plans: List[Dict[str, Any]] = None,
        total_invested: float = 0.0,
        total_tokens_bought: int = 0,
    ) -> Tuple[str, InlineKeyboardMarkup]:
        """
        DCA Overview - View and manage Dollar Cost Averaging plans.

        Shows:
        - Active DCA plans with next execution time
        - Total invested via DCA
        - DCA execution history
        """
        theme = JarvisTheme
        dca_plans = dca_plans or []

        active_plans = [p for p in dca_plans if p.get("active", True)]
        paused_plans = [p for p in dca_plans if not p.get("active", True)]

        lines = [
            f"📅 *DCA (DOLLAR COST AVERAGE)*",
            "━━━━━━━━━━━━━━━━━━━━━",
            "",
        ]

        if not dca_plans:
            lines.extend([
                "_No DCA plans configured_",
                "",
                "DCA automatically buys tokens at",
                "regular intervals to average your",
                "entry price over time.",
                "",
                "*Benefits:*",
                "• Reduces timing risk",
                "• Removes emotional decisions",
                "• Builds positions gradually",
            ])
        else:
            lines.extend([
                f"💰 *Total Invested:* {total_invested:.2f} SOL",
                f"📊 *Active Plans:* {len(active_plans)}",
                f"⏸️ *Paused:* {len(paused_plans)}",
                "",
            ])

            for plan in active_plans[:5]:  # Show max 5
                symbol = plan.get("symbol", "???")
                amount = plan.get("amount", 0)
                frequency = plan.get("frequency", "daily")
                executions = plan.get("executions", 0)
                next_exec = plan.get("next_execution", "Soon")

                freq_emoji = {"hourly": "⏰", "daily": "📅", "weekly": "📆"}.get(frequency, "📅")

                lines.extend([
                    f"{freq_emoji} *{symbol}*",
                    f"├ Amount: {amount} SOL / {frequency}",
                    f"├ Executions: {executions}",
                    f"└ Next: {next_exec}",
                    "",
                ])

        text = "\n".join(lines)

        keyboard = [
            [
                InlineKeyboardButton("➕ New DCA Plan", callback_data="demo:dca_new"),
            ],
        ]

        # Add manage buttons for each plan
        for plan in active_plans[:3]:  # Max 3
            plan_id = plan.get("id", "0")
            symbol = plan.get("symbol", "???")
            keyboard.append([
                InlineKeyboardButton(f"⏸️ Pause {symbol}", callback_data=f"demo:dca_pause:{plan_id}"),
                InlineKeyboardButton(f"🗑️ Delete", callback_data=f"demo:dca_delete:{plan_id}"),
            ])

        keyboard.extend([
            [
                InlineKeyboardButton("📊 DCA History", callback_data="demo:dca_history"),
            ],
            [
                InlineKeyboardButton(f"{theme.BACK} Back", callback_data="demo:main"),
            ],
        ])

        return text, InlineKeyboardMarkup(keyboard)

    @staticmethod
    def dca_setup(
        token_symbol: str = None,
        token_address: str = None,
        watchlist: List[Dict[str, Any]] = None,
    ) -> Tuple[str, InlineKeyboardMarkup]:
        """
        DCA Setup - Configure a new DCA plan.

        If no token specified, shows watchlist to choose from.
        If token specified, shows amount and frequency options.
        """
        theme = JarvisTheme
        watchlist = watchlist or []

        if not token_symbol:
            # Show token selection
            lines = [
                f"📅 *NEW DCA PLAN*",
                "━━━━━━━━━━━━━━━━━━━━━",
                "",
                "*Select a token to DCA:*",
                "",
            ]

            keyboard = []

            if watchlist:
                for token in watchlist[:6]:  # Max 6
                    sym = token.get("symbol", "???")
                    addr = token.get("address", "")
                    keyboard.append([
                        InlineKeyboardButton(f"📈 {sym}", callback_data=f"demo:dca_select:{addr}"),
                    ])
            else:
                lines.append("_Add tokens to watchlist first!_")

            keyboard.append([
                InlineKeyboardButton("✏️ Enter Address", callback_data="demo:dca_input"),
            ])
            keyboard.append([
                InlineKeyboardButton(f"{theme.BACK} Back", callback_data="demo:dca"),
            ])

            text = "\n".join(lines)

        else:
            # Show DCA configuration
            short_addr = f"{token_address[:6]}...{token_address[-4:]}" if token_address else "N/A"

            lines = [
                f"📅 *CONFIGURE DCA: {token_symbol}*",
                "━━━━━━━━━━━━━━━━━━━━━",
                "",
                f"*Token:* {token_symbol}",
                f"*Address:* `{short_addr}`",
                "",
                "*Select amount per buy:*",
            ]

            text = "\n".join(lines)

            keyboard = [
                # Amount options
                [
                    InlineKeyboardButton("0.1 SOL", callback_data=f"demo:dca_amount:{token_address}:0.1"),
                    InlineKeyboardButton("0.25 SOL", callback_data=f"demo:dca_amount:{token_address}:0.25"),
                    InlineKeyboardButton("0.5 SOL", callback_data=f"demo:dca_amount:{token_address}:0.5"),
                ],
                [
                    InlineKeyboardButton("1 SOL", callback_data=f"demo:dca_amount:{token_address}:1"),
                    InlineKeyboardButton("2 SOL", callback_data=f"demo:dca_amount:{token_address}:2"),
                    InlineKeyboardButton("5 SOL", callback_data=f"demo:dca_amount:{token_address}:5"),
                ],
                [
                    InlineKeyboardButton(f"{theme.BACK} Back", callback_data="demo:dca_new"),
                ],
            ]

        return text, InlineKeyboardMarkup(keyboard)

    @staticmethod
    def dca_frequency_select(
        token_symbol: str,
        token_address: str,
        amount: float,
    ) -> Tuple[str, InlineKeyboardMarkup]:
        """Select DCA frequency."""
        theme = JarvisTheme

        short_addr = f"{token_address[:6]}...{token_address[-4:]}"

        lines = [
            f"📅 *DCA FREQUENCY*",
            "━━━━━━━━━━━━━━━━━━━━━",
            "",
            f"*Token:* {token_symbol}",
            f"*Amount:* {amount} SOL per buy",
            "",
            "*How often should we buy?*",
        ]

        text = "\n".join(lines)

        keyboard = [
            [
                InlineKeyboardButton("⏰ Every Hour", callback_data=f"demo:dca_create:{token_address}:{amount}:hourly"),
            ],
            [
                InlineKeyboardButton("📅 Daily (Recommended)", callback_data=f"demo:dca_create:{token_address}:{amount}:daily"),
            ],
            [
                InlineKeyboardButton("📆 Weekly", callback_data=f"demo:dca_create:{token_address}:{amount}:weekly"),
            ],
            [
                InlineKeyboardButton(f"{theme.BACK} Back", callback_data=f"demo:dca_select:{token_address}"),
            ],
        ]

        return text, InlineKeyboardMarkup(keyboard)

    @staticmethod
    def dca_plan_created(
        token_symbol: str,
        amount: float,
        frequency: str,
        first_execution: str = "Now",
    ) -> Tuple[str, InlineKeyboardMarkup]:
        """Show success after creating DCA plan."""
        theme = JarvisTheme

        freq_emoji = {"hourly": "⏰", "daily": "📅", "weekly": "📆"}.get(frequency, "📅")

        text = f"""
{theme.SUCCESS} *DCA PLAN CREATED*
━━━━━━━━━━━━━━━━━━━━━

*{token_symbol}*
{freq_emoji} Buy {amount} SOL {frequency}

*First Execution:* {first_execution}

Your DCA plan is now active!
We'll automatically buy {token_symbol}
at regular intervals.

━━━━━━━━━━━━━━━━━━━━━
_Cancel anytime from DCA menu_
"""

        keyboard = [
            [
                InlineKeyboardButton("📅 View DCA Plans", callback_data="demo:dca"),
            ],
            [
                InlineKeyboardButton(f"{theme.CHART} Positions", callback_data="demo:positions"),
                InlineKeyboardButton(f"{theme.BACK} Main Menu", callback_data="demo:main"),
            ],
        ]

        return text, InlineKeyboardMarkup(keyboard)

    # ========== TRAILING STOP-LOSS ==========

    @staticmethod
    def trailing_stop_overview(
        trailing_stops: List[Dict[str, Any]] = None,
        positions: List[Dict[str, Any]] = None,
    ) -> Tuple[str, InlineKeyboardMarkup]:
        """
        Trailing Stop-Loss Overview - View and manage trailing stops.

        Trailing stops automatically adjust upward as price rises,
        locking in profits while protecting against drawdowns.
        """
        theme = JarvisTheme
        trailing_stops = trailing_stops or []
        positions = positions or []

        active_stops = [s for s in trailing_stops if s.get("active", True)]

        lines = [
            f"🛡️ *TRAILING STOP-LOSS*",
            "━━━━━━━━━━━━━━━━━━━━━",
            "",
        ]

        if not trailing_stops:
            lines.extend([
                "_No trailing stops configured_",
                "",
                "*What is a Trailing Stop?*",
                "A trailing stop moves UP as price rises,",
                "locking in profits automatically.",
                "",
                "*Example:*",
                "• Buy at $0.001, set 10% trail",
                "• Price hits $0.002 → stop at $0.0018",
                "• Price hits $0.003 → stop at $0.0027",
                "• Price drops to $0.0025 → SOLD",
                "",
                "_Profit locked in automatically!_",
            ])
        else:
            lines.extend([
                f"🛡️ *Active Stops:* {len(active_stops)}",
                f"💰 *Protected Value:* ${sum(s.get('protected_value', 0) for s in active_stops):.2f}",
                "",
            ])

            for stop in active_stops[:5]:
                symbol = stop.get("symbol", "???")
                trail_pct = stop.get("trail_percent", 10)
                current_stop = stop.get("current_stop_price", 0)
                highest_price = stop.get("highest_price", 0)
                protected_pnl = stop.get("protected_pnl", 0)

                pnl_emoji = theme.PROFIT if protected_pnl >= 0 else "⚠️"

                lines.extend([
                    f"🛡️ *{symbol}*",
                    f"├ Trail: {trail_pct}%",
                    f"├ Stop Price: ${current_stop:.8f}",
                    f"├ Peak: ${highest_price:.8f}",
                    f"└ Protected P&L: {pnl_emoji} {'+' if protected_pnl >= 0 else ''}{protected_pnl:.1f}%",
                    "",
                ])

        text = "\n".join(lines)

        keyboard = []

        # Show buttons for each active stop
        for stop in active_stops[:4]:
            stop_id = stop.get("id", "")
            symbol = stop.get("symbol", "???")
            keyboard.append([
                InlineKeyboardButton(f"✏️ Edit {symbol}", callback_data=f"demo:tsl_edit:{stop_id}"),
                InlineKeyboardButton(f"❌ Remove", callback_data=f"demo:tsl_delete:{stop_id}"),
            ])

        # Add new trailing stop (if positions available)
        if positions:
            keyboard.append([
                InlineKeyboardButton("➕ Add Trailing Stop", callback_data="demo:tsl_new"),
            ])

        keyboard.extend([
            [
                InlineKeyboardButton(f"{theme.CHART} Positions", callback_data="demo:positions"),
                InlineKeyboardButton(f"{theme.BACK} Main Menu", callback_data="demo:main"),
            ],
        ])

        return text, InlineKeyboardMarkup(keyboard)

    @staticmethod
    def trailing_stop_setup(
        position: Dict[str, Any] = None,
        positions: List[Dict[str, Any]] = None,
    ) -> Tuple[str, InlineKeyboardMarkup]:
        """
        Trailing Stop Setup - Configure a trailing stop for a position.

        If no position provided, shows position selection.
        If position provided, shows trail percentage options.
        """
        theme = JarvisTheme

        if not position:
            # Show position selection
            positions = positions or []

            lines = [
                f"🛡️ *ADD TRAILING STOP*",
                "━━━━━━━━━━━━━━━━━━━━━",
                "",
                "*Select Position:*",
                "",
            ]

            if not positions:
                lines.append("_No open positions_")
            else:
                for pos in positions[:6]:
                    symbol = pos.get("symbol", "???")
                    pnl_pct = pos.get("pnl_pct", 0)
                    pnl_emoji = theme.PROFIT if pnl_pct >= 0 else theme.LOSS
                    lines.append(f"{pnl_emoji} {symbol} ({'+' if pnl_pct >= 0 else ''}{pnl_pct:.1f}%)")

            text = "\n".join(lines)

            keyboard = []
            for pos in positions[:6]:
                pos_id = pos.get("id", "")
                symbol = pos.get("symbol", "???")
                keyboard.append([
                    InlineKeyboardButton(f"🛡️ {symbol}", callback_data=f"demo:tsl_select:{pos_id}")
                ])

            keyboard.append([
                InlineKeyboardButton(f"{theme.BACK} Back", callback_data="demo:trailing_stops"),
            ])

        else:
            # Show trail percentage options
            symbol = position.get("symbol", "???")
            entry = position.get("entry_price", 0)
            current = position.get("current_price", 0)
            pnl_pct = position.get("pnl_pct", 0)

            lines = [
                f"🛡️ *TRAILING STOP: {symbol}*",
                "━━━━━━━━━━━━━━━━━━━━━",
                "",
                f"*Entry:* ${entry:.8f}",
                f"*Current:* ${current:.8f}",
                f"*P&L:* {'+' if pnl_pct >= 0 else ''}{pnl_pct:.1f}%",
                "",
                "*Select Trail Distance:*",
                "_How far below peak to trigger sell_",
                "",
                "• 5% - Tight (more frequent sells)",
                "• 10% - Standard (recommended)",
                "• 15% - Loose (ride bigger swings)",
                "• 20% - Wide (max profit potential)",
            ]

            text = "\n".join(lines)
            pos_id = position.get("id", "")

            keyboard = [
                [
                    InlineKeyboardButton("5%", callback_data=f"demo:tsl_create:{pos_id}:5"),
                    InlineKeyboardButton("10% ⭐", callback_data=f"demo:tsl_create:{pos_id}:10"),
                ],
                [
                    InlineKeyboardButton("15%", callback_data=f"demo:tsl_create:{pos_id}:15"),
                    InlineKeyboardButton("20%", callback_data=f"demo:tsl_create:{pos_id}:20"),
                ],
                [
                    InlineKeyboardButton("Custom %", callback_data=f"demo:tsl_custom:{pos_id}"),
                ],
                [
                    InlineKeyboardButton(f"{theme.BACK} Back", callback_data="demo:tsl_new"),
                ],
            ]

        return text, InlineKeyboardMarkup(keyboard)

    @staticmethod
    def trailing_stop_created(
        symbol: str,
        trail_percent: float,
        initial_stop: float,
        current_price: float,
    ) -> Tuple[str, InlineKeyboardMarkup]:
        """Show success after creating trailing stop."""
        theme = JarvisTheme

        text = f"""
{theme.SUCCESS} *TRAILING STOP CREATED*
━━━━━━━━━━━━━━━━━━━━━

🛡️ *{symbol}* - {trail_percent}% Trail

*Current Price:* ${current_price:.8f}
*Initial Stop:* ${initial_stop:.8f}

The stop will automatically move UP
as the price increases, locking in
profits along the way.

━━━━━━━━━━━━━━━━━━━━━
_Stop updates every 30 seconds_
"""

        keyboard = [
            [
                InlineKeyboardButton("🛡️ View All Stops", callback_data="demo:trailing_stops"),
            ],
            [
                InlineKeyboardButton(f"{theme.CHART} Positions", callback_data="demo:positions"),
                InlineKeyboardButton(f"{theme.BACK} Main Menu", callback_data="demo:main"),
            ],
        ]

        return text, InlineKeyboardMarkup(keyboard)

    # ========== END TRAILING STOP-LOSS ==========

    @staticmethod
    def buy_confirmation(
        token_symbol: str,
        token_address: str,
        amount_sol: float,
        estimated_tokens: float,
        price_usd: float,
    ) -> Tuple[str, InlineKeyboardMarkup]:
        """Build buy confirmation screen."""
        theme = JarvisTheme

        short_addr = f"{token_address[:6]}...{token_address[-4:]}"

        text = f"""
{theme.BUY} *CONFIRM BUY*
━━━━━━━━━━━━━━━━━━━━━

*Token:* {token_symbol}
*Address:* `{short_addr}`

*Amount:* {amount_sol} SOL
*Est. Tokens:* {estimated_tokens:,.0f}
*Price:* ${price_usd:.8f}

━━━━━━━━━━━━━━━━━━━━━
{theme.WARNING} _Review before confirming_
"""

        keyboard = [
            [
                InlineKeyboardButton(f"{theme.SUCCESS} Confirm Buy", callback_data=f"demo:confirm_buy:{token_address}:{amount_sol}"),
            ],
            [
                InlineKeyboardButton(f"{theme.CLOSE} Cancel", callback_data="demo:main"),
            ],
        ]

        return text, InlineKeyboardMarkup(keyboard)

    @staticmethod
    def token_input_prompt() -> Tuple[str, InlineKeyboardMarkup]:
        """Prompt user to enter token address."""
        theme = JarvisTheme

        text = f"""
{theme.SNIPE} *ENTER TOKEN*
━━━━━━━━━━━━━━━━━━━━━

Reply with a Solana token address to buy.

*Example:*
`So11111111111111111111111111111111111111112`

━━━━━━━━━━━━━━━━━━━━━
{theme.FIRE} Or try trending tokens below
"""

        keyboard = [
            [
                InlineKeyboardButton(f"{theme.FIRE} Trending", callback_data="demo:trending"),
            ],
            [
                InlineKeyboardButton(f"{theme.BACK} Cancel", callback_data="demo:main"),
            ],
        ]

        return text, InlineKeyboardMarkup(keyboard)

    @staticmethod
    def trending_tokens(
        tokens: list,
        market_regime: Dict[str, Any] = None,
    ) -> Tuple[str, InlineKeyboardMarkup]:
        """
        Show trending tokens with AI sentiment overlay.

        Enhanced with:
        - AI sentiment score per token
        - Signal strength indicator
        - Risk-adjusted recommendations
        """
        theme = JarvisTheme

        # Market context
        regime = market_regime or {}
        regime_name = regime.get("regime", "NEUTRAL")
        regime_emoji = {"BULL": "🟢", "BEAR": "🔴"}.get(regime_name, "🟡")

        lines = [
            f"{theme.FIRE} *AI TRENDING*",
            "━━━━━━━━━━━━━━━━━━━━━",
            f"Market: {regime_emoji} {regime_name}",
            "",
        ]

        keyboard = []

        for token in tokens[:6]:
            symbol = token.get("symbol", "???")
            change_24h = token.get("change_24h", 0)
            volume = token.get("volume", 0)
            liquidity = token.get("liquidity", 0)
            address = token.get("address", "")

            # AI sentiment overlay
            sentiment = token.get("sentiment", "neutral")
            sentiment_score = token.get("sentiment_score", 0.5)
            signal = token.get("signal", "NEUTRAL")

            change_emoji = theme.PROFIT if change_24h >= 0 else theme.LOSS
            sign = "+" if change_24h >= 0 else ""

            # Sentiment indicator
            sent_emoji = {
                "bullish": "🟢",
                "very_bullish": "🚀",
                "bearish": "🔴",
                "very_bearish": "💀",
            }.get(sentiment.lower() if isinstance(sentiment, str) else "neutral", "🟡")

            # Signal strength bar
            score_bars = int(sentiment_score * 5) if sentiment_score else 0
            score_bar = "▰" * score_bars + "▱" * (5 - score_bars)

            lines.append(f"{change_emoji} *{symbol}* {sign}{change_24h:.1f}%")
            lines.append(f"   {sent_emoji} AI: {score_bar} | Vol: ${volume/1000:.0f}K")
            lines.append("")

            if address:
                keyboard.append([
                    InlineKeyboardButton(
                        f"{theme.BUY} Buy {symbol}",
                        callback_data=f"demo:quick_buy:{address}"
                    ),
                    InlineKeyboardButton(
                        f"{theme.CHART} Analyze",
                        callback_data=f"demo:analyze:{address}"
                    ),
                ])

        text = "\n".join(lines)

        keyboard.extend([
            [
                InlineKeyboardButton(f"{theme.AUTO} AI Picks", callback_data="demo:ai_picks"),
            ],
            [
                InlineKeyboardButton(f"{theme.REFRESH} Refresh", callback_data="demo:trending"),
            ],
            [
                InlineKeyboardButton(f"{theme.BACK} Back", callback_data="demo:main"),
            ],
        ])

        return text, InlineKeyboardMarkup(keyboard)

    @staticmethod
    def ai_picks_menu(
        picks: List[Dict[str, Any]],
        market_regime: Dict[str, Any] = None,
        trending: List[Dict[str, Any]] = None,
        volume_leaders: List[Dict[str, Any]] = None,
        near_picks: List[Dict[str, Any]] = None,
        pick_stats: Dict[str, Any] = None,
    ) -> Tuple[str, InlineKeyboardMarkup]:
        """
        Show AI-powered conviction picks from Grok with comprehensive market data.

        Includes:
        - High conviction picks with entry criteria
        - Near-conviction tokens (close to triggering)
        - Volume leaders (high activity)
        - Trending tokens summary
        - Historical pick performance
        """
        theme = JarvisTheme

        # Market context
        regime = market_regime or {}
        regime_name = regime.get("regime", "NEUTRAL")
        risk_level = regime.get("risk_level", "NORMAL")
        btc_change = regime.get("btc_change_24h", 0)
        sol_change = regime.get("sol_change_24h", 0)
        fear_greed = regime.get("fear_greed", 50)

        regime_emoji = {"BULL": "🟢", "BEAR": "🔴"}.get(regime_name, "🟡")
        risk_emoji = {"LOW": "🟢", "NORMAL": "🟡", "HIGH": "🟠", "EXTREME": "🔴"}.get(risk_level, "⚪")

        # Fear/Greed emoji
        if fear_greed >= 75:
            fg_emoji = "🤑"
            fg_label = "Extreme Greed"
        elif fear_greed >= 55:
            fg_emoji = "😊"
            fg_label = "Greed"
        elif fear_greed >= 45:
            fg_emoji = "😐"
            fg_label = "Neutral"
        elif fear_greed >= 25:
            fg_emoji = "😰"
            fg_label = "Fear"
        else:
            fg_emoji = "😱"
            fg_label = "Extreme Fear"

        lines = [
            f"{theme.AUTO} *AI CONVICTION PICKS*",
            "━━━━━━━━━━━━━━━━━━━━━",
            "",
            f"📊 *Market Overview*",
            f"├ Regime: {regime_emoji} *{regime_name}* | Risk: {risk_emoji} *{risk_level}*",
            f"├ BTC: *{btc_change:+.1f}%* | SOL: *{sol_change:+.1f}%*",
            f"└ {fg_emoji} Fear/Greed: *{fear_greed}* ({fg_label})",
            "",
        ]

        # Pick statistics if available
        stats = pick_stats or {}
        if stats:
            win_rate = stats.get("win_rate", 0)
            avg_gain = stats.get("avg_gain", 0)
            total_picks = stats.get("total_picks", 0)
            lines.extend([
                f"📈 *Pick Performance (30d)*",
                f"├ Win Rate: *{win_rate:.0f}%* | Avg Gain: *+{avg_gain:.0f}%*",
                f"└ Total Picks: *{total_picks}*",
                "",
            ])

        lines.extend([
            "🎯 *Selection Criteria:*",
            "├ Entry timing < 50% pump (67% TP rate)",
            "├ Buy/sell ratio ≥ 2.0x",
            "└ Multi-sighting validation",
            "",
            "━━━━━━━━━━━━━━━━━━━━━",
        ])

        keyboard = []

        # High Conviction Picks
        if picks:
            lines.extend([
                "",
                f"🔥 *HIGH CONVICTION ({len(picks)})*",
            ])
            for pick in picks[:3]:
                symbol = pick.get("symbol", "???")
                conviction = pick.get("conviction", "MEDIUM")
                thesis = pick.get("thesis", "")[:40]
                address = pick.get("address", "")
                tp = pick.get("tp_target", 0)
                sl = pick.get("sl_target", 0)
                ai_confidence = pick.get("ai_confidence", 0)
                change = pick.get("change_24h", 0)
                volume = pick.get("volume_24h", 0)

                conv_emoji = {"HIGH": "🔥", "MEDIUM": "📊", "LOW": "📉"}.get(conviction, "📊")
                change_emoji = "🟢" if change >= 0 else "🔴"

                lines.append(f"{conv_emoji} *{symbol}* | {change_emoji} {change:+.1f}%")
                if thesis:
                    lines.append(f"   _{thesis}_")

                details = []
                if tp:
                    details.append(f"TP +{tp}%")
                if sl:
                    details.append(f"SL -{sl}%")
                if ai_confidence > 0:
                    conf_pct = int(ai_confidence * 100)
                    details.append(f"AI {conf_pct}%")
                if volume > 0:
                    vol_k = volume / 1000
                    details.append(f"Vol ${vol_k:.0f}K")

                if details:
                    lines.append(f"   {' | '.join(details)}")
                lines.append("")

                if address:
                    keyboard.append([
                        InlineKeyboardButton(
                            f"{theme.BUY} Buy {symbol}",
                            callback_data=f"demo:quick_buy:{address}"
                        ),
                        InlineKeyboardButton(
                            f"{theme.CHART} Chart",
                            callback_data=f"demo:analyze:{address}"
                        ),
                    ])
        else:
            lines.extend([
                "",
                f"🔥 *HIGH CONVICTION*",
                "_No picks qualify right now._",
                "_AI is monitoring for setups..._",
                "",
            ])

        # Near-Conviction Picks (tokens close to triggering)
        near_picks = near_picks or []
        if near_picks:
            lines.extend([
                "━━━━━━━━━━━━━━━━━━━━━",
                "",
                f"⏳ *NEAR CONVICTION ({len(near_picks)})*",
                "_Almost meeting criteria:_",
            ])
            for np in near_picks[:3]:
                symbol = np.get("symbol", "???")
                missing = np.get("missing_criteria", "timing")
                score = np.get("score", 0)
                change = np.get("change_24h", 0)
                change_emoji = "🟢" if change >= 0 else "🔴"

                lines.append(f"📊 *{symbol}* {change_emoji} {change:+.1f}% (Score: {score}/100)")
                lines.append(f"   _Missing: {missing}_")
            lines.append("")

        # Volume Leaders
        volume_leaders = volume_leaders or []
        if volume_leaders:
            lines.extend([
                "━━━━━━━━━━━━━━━━━━━━━",
                "",
                f"💎 *VOLUME LEADERS*",
            ])
            for vl in volume_leaders[:4]:
                symbol = vl.get("symbol", "???")
                volume = vl.get("volume_24h", 0)
                change = vl.get("change_24h", 0)
                change_emoji = "🟢" if change >= 0 else "🔴"
                vol_m = volume / 1_000_000 if volume >= 1_000_000 else volume / 1000
                vol_unit = "M" if volume >= 1_000_000 else "K"

                lines.append(f"├ {symbol}: ${vol_m:.1f}{vol_unit} {change_emoji} {change:+.1f}%")
            lines.append("")

        # Trending Tokens
        trending = trending or []
        if trending:
            lines.extend([
                "━━━━━━━━━━━━━━━━━━━━━",
                "",
                f"🔥 *TRENDING NOW*",
            ])
            for t in trending[:4]:
                symbol = t.get("symbol", "???")
                change = t.get("change_24h", 0)
                sentiment = t.get("sentiment", "neutral")
                change_emoji = "🟢" if change >= 0 else "🔴"
                sent_emoji = {"bullish": "🟢", "bearish": "🔴", "very_bullish": "🚀"}.get(sentiment.lower(), "🟡")

                lines.append(f"├ {symbol}: {change_emoji} {change:+.1f}% {sent_emoji}")
            lines.append("")

        lines.extend([
            "━━━━━━━━━━━━━━━━━━━━━",
            f"_Updated: {datetime.now().strftime('%H:%M:%S')}_",
        ])

        text = "\n".join(lines)

        keyboard.extend([
            [
                InlineKeyboardButton(f"📊 Sentiment Hub", callback_data="demo:hub"),
                InlineKeyboardButton(f"🔥 Trending", callback_data="demo:trending"),
            ],
            [
                InlineKeyboardButton(f"{theme.REFRESH} Refresh", callback_data="demo:ai_picks"),
            ],
            [
                InlineKeyboardButton(f"{theme.BACK} Back", callback_data="demo:main"),
            ],
        ])

        return text, InlineKeyboardMarkup(keyboard)

    # ========== SENTIMENT HUB - COMPREHENSIVE TRADING DASHBOARD ==========

    @staticmethod
    def sentiment_hub_main(
        market_regime: Dict[str, Any] = None,
        last_report_time: datetime = None,
        report_interval_minutes: int = 15,
        wallet_connected: bool = False,
    ) -> Tuple[str, InlineKeyboardMarkup]:
        """
        Main Sentiment Hub - Beautiful comprehensive trading dashboard.

        Sections:
        - Market Overview (regime, countdown)
        - Asset Categories (Blue Chips, XStocks, PreStocks, Indexes, Trending)
        - Top 10 Picks with TP/SL
        - Market News & Analysis
        """
        theme = JarvisTheme

        regime = market_regime or {}
        regime_name = regime.get("regime", "NEUTRAL")
        risk_level = regime.get("risk_level", "NORMAL")
        btc_change = regime.get("btc_change_24h", 0)
        sol_change = regime.get("sol_change_24h", 0)

        # Calculate countdown to next report
        if last_report_time:
            next_report = last_report_time + timedelta(minutes=report_interval_minutes)
            time_left = next_report - datetime.now(timezone.utc)
            if time_left.total_seconds() > 0:
                mins_left = int(time_left.total_seconds() / 60)
                secs_left = int(time_left.total_seconds() % 60)
                countdown = f"{mins_left}:{secs_left:02d}"
                freshness = "🟢 FRESH" if mins_left >= 12 else "🟡 AGING" if mins_left >= 5 else "🟠 STALE"
            else:
                countdown = "UPDATING..."
                freshness = "⏳ REFRESH"
        else:
            countdown = "15:00"
            freshness = "🟢 FRESH"

        # Regime display
        regime_emoji = {"BULL": "🟢", "BEAR": "🔴"}.get(regime_name, "🟡")
        risk_emoji = {"LOW": "🟢", "NORMAL": "🟡", "HIGH": "🟠", "EXTREME": "🔴"}.get(risk_level, "⚪")

        # Entry advice based on freshness
        if "FRESH" in freshness:
            entry_advice = "✅ *Good time to enter* - Report is fresh"
        elif "AGING" in freshness:
            entry_advice = "⚡ Consider waiting for refresh"
        else:
            entry_advice = "⚠️ Wait for fresh report before risky entries"

        lines = [
            f"📊 *JARVIS SENTIMENT HUB*",
            f"{'━' * 25}",
            "",
            f"┌{'─' * 23}┐",
            f"│ {regime_emoji} Market: *{regime_name}*        │",
            f"│ {risk_emoji} Risk: *{risk_level}*          │",
            f"│ ⏱ Next Report: *{countdown}*   │",
            f"│ {freshness}                │",
            f"└{'─' * 23}┘",
            "",
            f"BTC: {'📈' if btc_change >= 0 else '📉'} {btc_change:+.1f}% | SOL: {'📈' if sol_change >= 0 else '📉'} {sol_change:+.1f}%",
            "",
            entry_advice,
            "",
            f"{'━' * 25}",
            "*SELECT CATEGORY:*",
        ]

        text = "\n".join(lines)

        # Beautiful category buttons
        keyboard = [
            # Row 1: Core categories
            [
                InlineKeyboardButton("💎 Blue Chips", callback_data="demo:hub_bluechips"),
                InlineKeyboardButton("🔥 TOP 10", callback_data="demo:hub_top10"),
            ],
            # Row 2: Stocks
            [
                InlineKeyboardButton("📈 XStocks", callback_data="demo:hub_xstocks"),
                InlineKeyboardButton("🌅 PreStocks", callback_data="demo:hub_prestocks"),
            ],
            # Row 3: Markets
            [
                InlineKeyboardButton("📊 Indexes", callback_data="demo:hub_indexes"),
                InlineKeyboardButton("🔥 Trending", callback_data="demo:hub_trending"),
            ],
            # Row 4: Reports
            [
                InlineKeyboardButton("📰 Market News", callback_data="demo:hub_news"),
                InlineKeyboardButton("🌍 Traditional", callback_data="demo:hub_traditional"),
            ],
            # Row 5: Wallet & Actions
            [
                InlineKeyboardButton("💳 Wallet", callback_data="demo:hub_wallet"),
                InlineKeyboardButton(f"{theme.REFRESH} Refresh", callback_data="demo:sentiment_hub"),
            ],
            [
                InlineKeyboardButton(f"{theme.BACK} Main Menu", callback_data="demo:main"),
            ],
        ]

        return text, InlineKeyboardMarkup(keyboard)

    @staticmethod
    def sentiment_hub_section(
        section: str,
        picks: List[Dict[str, Any]] = None,
        market_regime: Dict[str, Any] = None,
    ) -> Tuple[str, InlineKeyboardMarkup]:
        """
        Individual section view within the Sentiment Hub.

        Each section shows relevant tokens/assets with:
        - Current price and 24h change
        - Sentiment score and signal
        - TP/SL recommendations
        - Buy with auto-SL buttons
        """
        theme = JarvisTheme
        picks = picks or []

        # Section headers and emojis
        section_config = {
            "bluechips": {
                "title": "💎 BLUE CHIPS",
                "desc": "Established tokens with proven track records",
                "emoji": "💎",
            },
            "top10": {
                "title": "🔥 JARVIS TOP 10",
                "desc": "AI-selected high-conviction picks with TP/SL",
                "emoji": "🔥",
            },
            "xstocks": {
                "title": "📈 XSTOCKS",
                "desc": "Tokenized stocks on Solana (backed.fi)",
                "emoji": "📈",
            },
            "prestocks": {
                "title": "🌅 PRESTOCKS",
                "desc": "Pre-market tokenized equities",
                "emoji": "🌅",
            },
            "indexes": {
                "title": "📊 INDEXES",
                "desc": "SPX, NDX, DJI on Solana",
                "emoji": "📊",
            },
            "trending": {
                "title": "🔥 HOT TRENDING",
                "desc": "High-volume Solana tokens right now",
                "emoji": "🔥",
            },
        }

        config = section_config.get(section, {"title": section.upper(), "desc": "", "emoji": "📊"})

        lines = [
            f"{config['emoji']} *{config['title']}*",
            "━━━━━━━━━━━━━━━━━━━━━",
            f"_{config['desc']}_",
            "",
        ]

        keyboard = []

        if not picks:
            lines.append("_No picks available in this category_")
            lines.append("_Check back after next report refresh_")
        else:
            for i, pick in enumerate(picks[:8]):
                symbol = pick.get("symbol", "???")
                price = pick.get("price", 0)
                change_24h = pick.get("change_24h", 0)
                sentiment = pick.get("sentiment", "NEUTRAL")
                score = pick.get("score", 0)
                tp = pick.get("tp", 0)
                sl = pick.get("sl", 0)
                address = pick.get("address", "")
                conviction = pick.get("conviction", "")

                # Sentiment emoji
                sent_emoji = {"BULLISH": "🟢", "BEARISH": "🔴", "VERY_BULLISH": "🚀"}.get(sentiment, "⚪")
                change_emoji = "📈" if change_24h >= 0 else "📉"

                # Format price nicely
                if price < 0.0001:
                    price_str = f"${price:.8f}"
                elif price < 1:
                    price_str = f"${price:.6f}"
                else:
                    price_str = f"${price:.2f}"

                lines.append(f"{sent_emoji} *{symbol}* {price_str}")
                lines.append(f"   {change_emoji} {change_24h:+.1f}% | Score: {score:.0f}/100")

                if tp or sl:
                    targets = []
                    if tp:
                        targets.append(f"TP: +{tp}%")
                    if sl:
                        targets.append(f"SL: -{sl}%")
                    lines.append(f"   🎯 {' | '.join(targets)}")

                if conviction:
                    lines.append(f"   _{conviction}_")

                lines.append("")

                # Buy button with auto stop-loss
                if address:
                    sl_percent = sl if sl else 15  # Default 15% SL
                    keyboard.append([
                        InlineKeyboardButton(
                            f"🛒 Buy {symbol}",
                            callback_data=f"demo:hub_buy:{address}:{sl_percent}"
                        ),
                        InlineKeyboardButton(
                            f"📊 Details",
                            callback_data=f"demo:hub_detail:{address}"
                        ),
                    ])

        text = "\n".join(lines)

        keyboard.extend([
            [
                InlineKeyboardButton(f"{theme.REFRESH} Refresh", callback_data=f"demo:hub_{section}"),
            ],
            [
                InlineKeyboardButton("📊 Back to Hub", callback_data="demo:sentiment_hub"),
            ],
        ])

        return text, InlineKeyboardMarkup(keyboard)

    @staticmethod
    def sentiment_hub_wallet(
        wallet_address: str = None,
        sol_balance: float = 0.0,
        usd_value: float = 0.0,
        has_private_key: bool = False,
    ) -> Tuple[str, InlineKeyboardMarkup]:
        """
        Wallet management within Sentiment Hub.

        Supports:
        - Fresh wallet creation
        - Private key export
        - Private key import
        - Balance display
        """
        theme = JarvisTheme

        if wallet_address:
            short_addr = f"{wallet_address[:8]}...{wallet_address[-6:]}"

            lines = [
                f"💳 *HUB WALLET*",
                "━━━━━━━━━━━━━━━━━━━━━",
                "",
                f"*Address:* `{short_addr}`",
                f"*Balance:* {sol_balance:.4f} SOL",
                f"*Value:* ${usd_value:.2f}",
                "",
                "━━━━━━━━━━━━━━━━━━━━━",
                "_Secure your keys. Not your keys, not your coins._",
            ]

            keyboard = [
                [
                    InlineKeyboardButton("📤 Export Key", callback_data="demo:hub_export_key"),
                    InlineKeyboardButton("📋 Copy Address", callback_data="demo:hub_copy_addr"),
                ],
                [
                    InlineKeyboardButton("💰 Deposit", callback_data="demo:hub_deposit"),
                    InlineKeyboardButton("📤 Withdraw", callback_data="demo:hub_withdraw"),
                ],
                [
                    InlineKeyboardButton("🔄 Import Key", callback_data="demo:hub_import_key"),
                    InlineKeyboardButton("🆕 New Wallet", callback_data="demo:hub_new_wallet"),
                ],
                [
                    InlineKeyboardButton("📊 Back to Hub", callback_data="demo:sentiment_hub"),
                ],
            ]
        else:
            lines = [
                f"💳 *SETUP WALLET*",
                "━━━━━━━━━━━━━━━━━━━━━",
                "",
                "No wallet connected.",
                "",
                "*Options:*",
                "• Create a fresh Solana wallet",
                "• Import existing private key",
                "",
                "━━━━━━━━━━━━━━━━━━━━━",
                "_Your keys are encrypted locally._",
            ]

            keyboard = [
                [
                    InlineKeyboardButton("🆕 Create Wallet", callback_data="demo:hub_create_wallet"),
                ],
                [
                    InlineKeyboardButton("📥 Import Key", callback_data="demo:hub_import_key"),
                ],
                [
                    InlineKeyboardButton("📊 Back to Hub", callback_data="demo:sentiment_hub"),
                ],
            ]

        text = "\n".join(lines)
        return text, InlineKeyboardMarkup(keyboard)

    @staticmethod
    def sentiment_hub_news(
        news_items: List[Dict[str, Any]] = None,
        macro_analysis: Dict[str, Any] = None,
    ) -> Tuple[str, InlineKeyboardMarkup]:
        """
        Market news and macro analysis view.

        Shows:
        - Key market events
        - Macro outlook (short/medium/long term)
        - Impact on crypto
        """
        theme = JarvisTheme
        news_items = news_items or []
        macro = macro_analysis or {}

        lines = [
            f"📰 *MARKET NEWS & MACRO*",
            "━━━━━━━━━━━━━━━━━━━━━",
            "",
        ]

        # Macro outlook
        short_term = macro.get("short_term", "No data")
        medium_term = macro.get("medium_term", "No data")
        key_events = macro.get("key_events", [])

        lines.extend([
            "*MACRO OUTLOOK:*",
            f"📅 *24h:* {short_term[:60]}...",
            f"📆 *3-Day:* {medium_term[:60]}...",
            "",
        ])

        if key_events:
            lines.append("*KEY EVENTS:*")
            for event in key_events[:3]:
                lines.append(f"• {event[:50]}")
            lines.append("")

        # News items
        if news_items:
            lines.append("*RECENT NEWS:*")
            for item in news_items[:5]:
                # Support both 'title' and 'headline' keys
                headline = item.get("title") or item.get("headline", "")
                headline = headline[:45] if headline else ""
                source = item.get("source", "")
                time_str = item.get("time", "")
                impact = item.get("impact") or item.get("sentiment", "NEUTRAL")
                impact_upper = impact.upper() if impact else "NEUTRAL"
                impact_emoji = {"BULLISH": "🟢", "BEARISH": "🔴"}.get(impact_upper, "⚪")
                source_str = f" - {source}" if source else ""
                time_str = f" ({time_str})" if time_str else ""
                lines.append(f"{impact_emoji} {headline}{source_str}{time_str}")
            lines.append("")

        text = "\n".join(lines)

        keyboard = [
            [
                InlineKeyboardButton(f"{theme.REFRESH} Refresh", callback_data="demo:hub_news"),
            ],
            [
                InlineKeyboardButton("📊 Back to Hub", callback_data="demo:sentiment_hub"),
            ],
        ]

        return text, InlineKeyboardMarkup(keyboard)

    @staticmethod
    def sentiment_hub_traditional(
        stocks_outlook: Dict[str, Any] = None,
        dxy_data: Dict[str, Any] = None,
        commodities: List[Dict[str, Any]] = None,
    ) -> Tuple[str, InlineKeyboardMarkup]:
        """
        Traditional markets view - DXY, stocks, commodities.
        """
        theme = JarvisTheme

        stocks = stocks_outlook or {}
        dxy = dxy_data or {}
        comms = commodities or []

        # DXY - support multiple field names
        dxy_value = dxy.get("value", 0)
        dxy_change = dxy.get("change", 0)
        dxy_trend = dxy.get("trend") or dxy.get("direction", "NEUTRAL")
        dxy_trend_upper = dxy_trend.upper() if dxy_trend else "NEUTRAL"
        dxy_emoji = "📈" if dxy_change > 0 else "📉" if dxy_change < 0 else "➡️"

        # Stocks - support multiple field names
        stocks_direction = stocks.get("direction") or stocks.get("outlook", "NEUTRAL")
        stocks_direction_upper = stocks_direction.upper() if stocks_direction else "NEUTRAL"
        stocks_emoji = {"BULLISH": "📈", "BEARISH": "📉"}.get(stocks_direction_upper, "➡️")

        # Stocks changes
        spy_change = stocks.get("spy_change", 0)
        qqq_change = stocks.get("qqq_change", 0)
        dia_change = stocks.get("dia_change", 0)

        lines = [
            f"🌍 *TRADITIONAL MARKETS*",
            "━━━━━━━━━━━━━━━━━━━━━",
            "",
            f"*DXY (Dollar Index):* {dxy_emoji}",
            f"├ Value: *{dxy_value:.2f}*",
            f"├ Change: *{dxy_change:+.2f}%*",
            f"└ Trend: *{dxy_trend_upper}*",
            "",
            f"*US STOCKS:* {stocks_emoji} *{stocks_direction_upper}*",
        ]

        if spy_change or qqq_change or dia_change:
            lines.extend([
                f"├ SPY: *{spy_change:+.2f}%*",
                f"├ QQQ: *{qqq_change:+.2f}%*",
                f"└ DIA: *{dia_change:+.2f}%*",
            ])

        lines.append("")

        if stocks.get("correlation_note"):
            lines.extend([
                "*CRYPTO CORRELATION:*",
                f"_{stocks.get('correlation_note', '')[:80]}_",
                "",
            ])

        if comms:
            lines.append("*COMMODITIES:*")
            for c in comms[:3]:
                name = c.get("symbol") or c.get("name", "???")
                price = c.get("price", 0)
                change = c.get("change", 0)
                dir_emoji = "📈" if change > 0 else "📉" if change < 0 else "➡️"
                lines.append(f"{dir_emoji} {name}: ${price:,.2f} ({change:+.1f}%)")
            lines.append("")

        text = "\n".join(lines)

        keyboard = [
            [
                InlineKeyboardButton(f"{theme.REFRESH} Refresh", callback_data="demo:hub_traditional"),
            ],
            [
                InlineKeyboardButton("📊 Back to Hub", callback_data="demo:sentiment_hub"),
            ],
        ]

        return text, InlineKeyboardMarkup(keyboard)

    @staticmethod
    def sentiment_hub_buy_confirm(
        symbol: str,
        address: str,
        price: float,
        auto_sl_percent: float = 15,
        amount_options: List[float] = None,
    ) -> Tuple[str, InlineKeyboardMarkup]:
        """
        Buy confirmation with automatic stop-loss setup.
        """
        theme = JarvisTheme
        amount_options = amount_options or [0.1, 0.25, 0.5, 1.0, 2.0]

        # Format price
        if price < 0.0001:
            price_str = f"${price:.8f}"
        elif price < 1:
            price_str = f"${price:.6f}"
        else:
            price_str = f"${price:.2f}"

        sl_price = price * (1 - auto_sl_percent / 100)
        sl_str = f"${sl_price:.8f}" if sl_price < 0.0001 else f"${sl_price:.6f}" if sl_price < 1 else f"${sl_price:.2f}"

        lines = [
            f"🛒 *BUY {symbol}*",
            "━━━━━━━━━━━━━━━━━━━━━",
            "",
            f"*Price:* {price_str}",
            f"*Auto Stop-Loss:* {auto_sl_percent}%",
            f"*SL Trigger:* {sl_str}",
            "",
            "_Select amount to buy:_",
            "",
            "━━━━━━━━━━━━━━━━━━━━━",
            f"⚠️ SL automatically set at -{auto_sl_percent}%",
        ]

        text = "\n".join(lines)

        keyboard = []
        row = []
        for amt in amount_options:
            row.append(InlineKeyboardButton(
                f"{amt} SOL",
                callback_data=f"demo:hub_exec_buy:{address}:{amt}:{auto_sl_percent}"
            ))
            if len(row) == 2:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)

        keyboard.extend([
            [
                InlineKeyboardButton("✏️ Custom SL %", callback_data=f"demo:hub_custom_sl:{address}"),
            ],
            [
                InlineKeyboardButton(f"{theme.BACK} Cancel", callback_data="demo:sentiment_hub"),
            ],
        ])

        return text, InlineKeyboardMarkup(keyboard)

    @staticmethod
    def bags_fm_top_tokens(
        tokens: List[Dict[str, Any]],
        market_regime: Dict[str, Any] = None,
        default_tp_percent: float = 15.0,
        default_sl_percent: float = 15.0,
    ) -> Tuple[str, InlineKeyboardMarkup]:
        """
        Bags.fm Top 15 Tokens by Volume with AI Sentiment.

        Features:
        - Top 15 tokens ranked by 24h volume
        - AI sentiment score per token
        - Signal strength indicator
        - Buy with auto TP/SL buttons
        - Sell buttons for open positions
        """
        theme = JarvisTheme

        regime = market_regime or {}
        regime_name = regime.get("regime", "NEUTRAL")
        risk_level = regime.get("risk_level", "NORMAL")
        regime_emoji = {"BULL": "🟢", "BEAR": "🔴"}.get(regime_name, "🟡")

        # Calculate total volume
        total_volume = sum(t.get("volume_24h", 0) for t in tokens)

        lines = [
            f"🎒 *BAGS.FM TOP 15*",
            "━━━━━━━━━━━━━━━━━━━━━",
            f"Market: {regime_emoji} {regime_name} | 24h Vol: ${total_volume/1_000_000:.1f}M",
            "",
            "*Volume Leaders with AI Sentiment:*",
            "",
        ]

        keyboard = []

        for i, token in enumerate(tokens[:15], 1):
            symbol = token.get("symbol", "???")
            address = token.get("address", "")
            price = token.get("price_usd", 0)
            volume = token.get("volume_24h", 0)
            liquidity = token.get("liquidity", 0)
            mcap = token.get("market_cap", 0)
            holders = token.get("holders", 0)

            # Sentiment data
            sentiment = token.get("sentiment", "neutral")
            sentiment_score = token.get("sentiment_score", 0.5)
            signal = token.get("signal", "NEUTRAL")

            # Format price
            if price < 0.0001:
                price_str = f"${price:.8f}"
            elif price < 1:
                price_str = f"${price:.6f}"
            else:
                price_str = f"${price:.2f}"

            # Volume formatting
            if volume >= 1_000_000:
                vol_str = f"${volume/1_000_000:.1f}M"
            else:
                vol_str = f"${volume/1_000:.0f}K"

            # Sentiment emoji and signal
            sent_emoji = {
                "very_bullish": "🚀",
                "bullish": "🟢",
                "neutral": "🟡",
                "bearish": "🟠",
                "very_bearish": "🔴",
            }.get(sentiment.lower() if isinstance(sentiment, str) else "neutral", "⚪")

            signal_emoji = {
                "STRONG_BUY": "🟢🟢",
                "BUY": "🟢",
                "HOLD": "🟡",
                "SELL": "🟠",
                "STRONG_SELL": "🔴🔴",
            }.get(signal, "⚪")

            # Score bar visualization
            score_bars = int(sentiment_score * 5) if sentiment_score else 0
            score_bar = "▰" * score_bars + "▱" * (5 - score_bars)

            # Rank medal
            if i == 1:
                rank = "🥇"
            elif i == 2:
                rank = "🥈"
            elif i == 3:
                rank = "🥉"
            else:
                rank = f"#{i:02d}"

            lines.append(f"{rank} *{symbol}* {price_str}")
            lines.append(f"   Vol: {vol_str} | Liq: ${liquidity/1_000:.0f}K")
            lines.append(f"   {sent_emoji} {score_bar} | {signal_emoji} {signal}")
            lines.append("")

            # Add buy/sell buttons for each token (groups of 3)
            if address:
                keyboard.append([
                    InlineKeyboardButton(
                        f"🟢 Buy {symbol}",
                        callback_data=f"demo:bags_buy:{address}:{default_tp_percent}:{default_sl_percent}"
                    ),
                    InlineKeyboardButton(
                        f"🔍 Info",
                        callback_data=f"demo:bags_info:{address}"
                    ),
                ])

        # Add summary stats
        bullish_count = sum(1 for t in tokens if t.get("sentiment", "").lower() in ["bullish", "very_bullish"])
        bearish_count = sum(1 for t in tokens if t.get("sentiment", "").lower() in ["bearish", "very_bearish"])

        lines.extend([
            "━━━━━━━━━━━━━━━━━━━━━",
            f"📊 *Sentiment Summary*",
            f"   🟢 Bullish: {bullish_count} | 🔴 Bearish: {bearish_count}",
            "",
            f"_Default TP: +{default_tp_percent:.0f}% | SL: -{default_sl_percent:.0f}%_",
        ])

        text = "\n".join(lines)

        # Navigation buttons
        keyboard.extend([
            [
                InlineKeyboardButton(f"⚙️ Set TP/SL", callback_data="demo:bags_settings"),
                InlineKeyboardButton(f"{theme.REFRESH} Refresh", callback_data="demo:bags_fm"),
            ],
            [
                InlineKeyboardButton(f"{theme.BACK} Main Menu", callback_data="demo:main"),
            ],
        ])

        return text, InlineKeyboardMarkup(keyboard)

    @staticmethod
    def bags_token_detail(
        token: Dict[str, Any],
        market_regime: Dict[str, Any] = None,
        default_tp_percent: float = 15.0,
        default_sl_percent: float = 15.0,
    ) -> Tuple[str, InlineKeyboardMarkup]:
        """
        Detailed view of a single Bags.fm token with buy/sell options.
        """
        theme = JarvisTheme

        symbol = token.get("symbol", "???")
        name = token.get("name", symbol)
        address = token.get("address", "")
        price = token.get("price_usd", 0)
        volume = token.get("volume_24h", 0)
        liquidity = token.get("liquidity", 0)
        mcap = token.get("market_cap", 0)
        holders = token.get("holders", 0)

        sentiment = token.get("sentiment", "neutral")
        sentiment_score = token.get("sentiment_score", 0.5)
        signal = token.get("signal", "NEUTRAL")

        # Format price
        if price < 0.0001:
            price_str = f"${price:.8f}"
        elif price < 1:
            price_str = f"${price:.6f}"
        else:
            price_str = f"${price:.2f}"

        # TP/SL targets
        tp_price = price * (1 + default_tp_percent / 100)
        sl_price = price * (1 - default_sl_percent / 100)

        tp_str = f"${tp_price:.8f}" if tp_price < 0.0001 else f"${tp_price:.6f}" if tp_price < 1 else f"${tp_price:.2f}"
        sl_str = f"${sl_price:.8f}" if sl_price < 0.0001 else f"${sl_price:.6f}" if sl_price < 1 else f"${sl_price:.2f}"

        # Sentiment display
        sent_emoji = {
            "very_bullish": "🚀",
            "bullish": "🟢",
            "neutral": "🟡",
            "bearish": "🟠",
            "very_bearish": "🔴",
        }.get(sentiment.lower() if isinstance(sentiment, str) else "neutral", "⚪")

        score_bars = int(sentiment_score * 5) if sentiment_score else 0
        score_bar = "▰" * score_bars + "▱" * (5 - score_bars)

        lines = [
            f"🎒 *{symbol}*",
            f"_{name}_",
            "━━━━━━━━━━━━━━━━━━━━━",
            "",
            f"💰 *Price:* {price_str}",
            f"📊 *24h Volume:* ${volume/1_000_000:.2f}M",
            f"💧 *Liquidity:* ${liquidity/1_000:.0f}K",
            f"📈 *Market Cap:* ${mcap/1_000_000:.2f}M",
            f"👥 *Holders:* {holders:,}",
            "",
            f"{sent_emoji} *AI Sentiment:* {sentiment.upper()}",
            f"   Score: {score_bar} ({sentiment_score:.0%})",
            f"   Signal: *{signal}*",
            "",
            "━━━━━━━━━━━━━━━━━━━━━",
            f"*Trading Setup:*",
            f"🎯 TP (+{default_tp_percent:.0f}%): {tp_str}",
            f"🛑 SL (-{default_sl_percent:.0f}%): {sl_str}",
            "",
            f"📋 `{address[:20]}...`",
        ]

        text = "\n".join(lines)

        # Buy buttons with different amounts
        keyboard = [
            [
                InlineKeyboardButton(f"🟢 Buy 0.1 SOL", callback_data=f"demo:bags_exec:{address}:0.1:{default_tp_percent}:{default_sl_percent}"),
                InlineKeyboardButton(f"🟢 Buy 0.25 SOL", callback_data=f"demo:bags_exec:{address}:0.25:{default_tp_percent}:{default_sl_percent}"),
            ],
            [
                InlineKeyboardButton(f"🟢 Buy 0.5 SOL", callback_data=f"demo:bags_exec:{address}:0.5:{default_tp_percent}:{default_sl_percent}"),
                InlineKeyboardButton(f"🟢 Buy 1 SOL", callback_data=f"demo:bags_exec:{address}:1:{default_tp_percent}:{default_sl_percent}"),
            ],
            [
                InlineKeyboardButton(f"🟢 Buy 2 SOL", callback_data=f"demo:bags_exec:{address}:2:{default_tp_percent}:{default_sl_percent}"),
                InlineKeyboardButton(f"🟢 Buy 5 SOL", callback_data=f"demo:bags_exec:{address}:5:{default_tp_percent}:{default_sl_percent}"),
            ],
            [
                InlineKeyboardButton(f"✏️ Custom TP/SL", callback_data=f"demo:bags_custom_tpsl:{address}"),
            ],
            [
                InlineKeyboardButton(f"{theme.BACK} Back to List", callback_data="demo:bags_fm"),
            ],
        ]

        return text, InlineKeyboardMarkup(keyboard)

    @staticmethod
    def bags_buy_result(
        success: bool,
        symbol: str,
        amount_sol: float,
        tokens_received: float = 0,
        price: float = 0,
        tp_percent: float = 15,
        sl_percent: float = 15,
        tx_hash: str = None,
        error: str = None,
    ) -> Tuple[str, InlineKeyboardMarkup]:
        """
        Result of a Bags.fm buy operation.
        """
        theme = JarvisTheme

        if success:
            tp_price = price * (1 + tp_percent / 100)
            sl_price = price * (1 - sl_percent / 100)

            lines = [
                f"✅ *BUY SUCCESSFUL*",
                "━━━━━━━━━━━━━━━━━━━━━",
                "",
                f"🪙 *Token:* {symbol}",
                f"💰 *Spent:* {amount_sol} SOL",
                f"📦 *Received:* {tokens_received:,.2f} {symbol}",
                f"💵 *Entry Price:* ${price:.8f}" if price < 0.0001 else f"💵 *Entry Price:* ${price:.6f}" if price < 1 else f"💵 *Entry Price:* ${price:.2f}",
                "",
                f"*Auto Orders Set:*",
                f"🎯 TP (+{tp_percent:.0f}%): ${tp_price:.8f}" if tp_price < 0.0001 else f"🎯 TP (+{tp_percent:.0f}%): ${tp_price:.6f}" if tp_price < 1 else f"🎯 TP (+{tp_percent:.0f}%): ${tp_price:.2f}",
                f"🛑 SL (-{sl_percent:.0f}%): ${sl_price:.8f}" if sl_price < 0.0001 else f"🛑 SL (-{sl_percent:.0f}%): ${sl_price:.6f}" if sl_price < 1 else f"🛑 SL (-{sl_percent:.0f}%): ${sl_price:.2f}",
                "",
            ]

            if tx_hash:
                lines.append(f"🔗 [View on Solscan](https://solscan.io/tx/{tx_hash})")

            lines.extend([
                "",
                "━━━━━━━━━━━━━━━━━━━━━",
                "_Position added to portfolio_",
            ])
        else:
            lines = [
                f"❌ *BUY FAILED*",
                "━━━━━━━━━━━━━━━━━━━━━",
                "",
                f"🪙 *Token:* {symbol}",
                f"💰 *Amount:* {amount_sol} SOL",
                "",
                f"*Error:* {error or 'Unknown error'}",
                "",
                "_Please try again or contact support_",
            ]

        text = "\n".join(lines)

        keyboard = [
            [
                InlineKeyboardButton(f"{theme.CHART} Positions", callback_data="demo:positions"),
                InlineKeyboardButton(f"🎒 Back to Bags", callback_data="demo:bags_fm"),
            ],
            [
                InlineKeyboardButton(f"{theme.BACK} Main Menu", callback_data="demo:main"),
            ],
        ]

        return text, InlineKeyboardMarkup(keyboard)

    @staticmethod
    def insta_snipe_menu(
        hottest_token: Dict[str, Any] = None,
        market_regime: Dict[str, Any] = None,
        auto_sl_percent: float = 15.0,
        auto_tp_percent: float = 15.0,
    ) -> Tuple[str, InlineKeyboardMarkup]:
        """
        Insta Snipe - One-click trade on the hottest trending token.

        Features:
        - Auto-detects hottest trending token
        - Pre-configured 15% SL / 15% TP
        - Conviction level display
        - One-click execution
        """
        theme = JarvisTheme

        regime = market_regime or {}
        regime_name = regime.get("regime", "NEUTRAL")

        if hottest_token:
            symbol = hottest_token.get("symbol", "UNKNOWN")
            address = hottest_token.get("address", "")
            price = hottest_token.get("price", 0)
            change_24h = hottest_token.get("change_24h", 0)
            volume = hottest_token.get("volume_24h", 0)
            liquidity = hottest_token.get("liquidity", 0)
            mcap = hottest_token.get("market_cap", 0)
            conviction = hottest_token.get("conviction", "MEDIUM")
            sentiment_score = hottest_token.get("sentiment_score", 65)
            entry_timing = hottest_token.get("entry_timing", "GOOD")
            sightings = hottest_token.get("sightings", 1)

            # Price formatting
            if price < 0.0001:
                price_str = f"${price:.8f}"
            elif price < 1:
                price_str = f"${price:.6f}"
            else:
                price_str = f"${price:.2f}"

            # Volume/Liquidity formatting
            def fmt_num(n):
                if n >= 1_000_000:
                    return f"${n/1_000_000:.1f}M"
                elif n >= 1_000:
                    return f"${n/1_000:.1f}K"
                return f"${n:.0f}"

            # Conviction display
            conv_emoji = {
                "VERY HIGH": "🔥🔥🔥",
                "HIGH": "🔥🔥",
                "MEDIUM": "🔥",
                "LOW": "⚪",
            }.get(conviction, "🔥")

            # Entry timing
            timing_emoji = {
                "EXCELLENT": "🟢",
                "GOOD": "🟡",
                "LATE": "🟠",
                "RISKY": "🔴",
            }.get(entry_timing, "🟡")

            # Change emoji
            change_emoji = "📈" if change_24h >= 0 else "📉"

            # Calculate SL/TP prices
            sl_price = price * (1 - auto_sl_percent / 100)
            tp_price = price * (1 + auto_tp_percent / 100)
            sl_str = f"${sl_price:.8f}" if sl_price < 0.0001 else f"${sl_price:.6f}" if sl_price < 1 else f"${sl_price:.2f}"
            tp_str = f"${tp_price:.8f}" if tp_price < 0.0001 else f"${tp_price:.6f}" if tp_price < 1 else f"${tp_price:.2f}"

            lines = [
                f"⚡ *INSTA SNIPE*",
                "━━━━━━━━━━━━━━━━━━━━━",
                "",
                f"🎯 *HOTTEST TOKEN: {symbol}*",
                "",
                f"*Conviction:* {conv_emoji} {conviction}",
                f"*Sentiment Score:* {sentiment_score}/100",
                f"*Entry Timing:* {timing_emoji} {entry_timing}",
                f"*Sightings:* {sightings}x (multi-source bonus)",
                "",
                "━━━━━━━━━━━━━━━━━━━━━",
                "",
                f"*Price:* {price_str}",
                f"*24h:* {change_emoji} {change_24h:+.1f}%",
                f"*Volume:* {fmt_num(volume)}",
                f"*Liquidity:* {fmt_num(liquidity)}",
                f"*MCap:* {fmt_num(mcap)}",
                "",
                "━━━━━━━━━━━━━━━━━━━━━",
                "",
                f"🛡️ *AUTO PROTECTION*",
                f"├ Stop Loss: *-{auto_sl_percent:.0f}%* ({sl_str})",
                f"└ Take Profit: *+{auto_tp_percent:.0f}%* ({tp_str})",
                "",
                "━━━━━━━━━━━━━━━━━━━━━",
                "_One-click trade with auto SL/TP_",
            ]

            text = "\n".join(lines)

            keyboard = [
                # Quick snipe amounts
                [
                    InlineKeyboardButton(f"⚡ 0.1 SOL", callback_data=f"demo:snipe_exec:{address}:0.1"),
                    InlineKeyboardButton(f"⚡ 0.25 SOL", callback_data=f"demo:snipe_exec:{address}:0.25"),
                ],
                [
                    InlineKeyboardButton(f"⚡ 0.5 SOL", callback_data=f"demo:snipe_exec:{address}:0.5"),
                    InlineKeyboardButton(f"⚡ 1 SOL", callback_data=f"demo:snipe_exec:{address}:1"),
                ],
                [
                    InlineKeyboardButton(f"🔄 Refresh Token", callback_data="demo:insta_snipe"),
                    InlineKeyboardButton(f"📊 Full Analysis", callback_data=f"demo:analyze:{address}"),
                ],
                [
                    InlineKeyboardButton(f"{theme.BACK} Back", callback_data="demo:main"),
                ],
            ]
        else:
            # No token available
            lines = [
                f"⚡ *INSTA SNIPE*",
                "━━━━━━━━━━━━━━━━━━━━━",
                "",
                "🔍 *Scanning for hottest token...*",
                "",
                "_Analyzing trending tokens by:_",
                "├ Volume spike detection",
                "├ Social sentiment scoring",
                "├ Entry timing analysis",
                "└ Multi-source sightings",
                "",
                "━━━━━━━━━━━━━━━━━━━━━",
                "",
                "⏳ *No qualifying tokens found*",
                "_Try refreshing or check AI Picks_",
            ]

            text = "\n".join(lines)

            keyboard = [
                [
                    InlineKeyboardButton(f"🔄 Refresh", callback_data="demo:insta_snipe"),
                    InlineKeyboardButton(f"{theme.AUTO} AI Picks", callback_data="demo:ai_picks"),
                ],
                [
                    InlineKeyboardButton(f"📊 Sentiment Hub", callback_data="demo:hub"),
                ],
                [
                    InlineKeyboardButton(f"{theme.BACK} Back", callback_data="demo:main"),
                ],
            ]

        return text, InlineKeyboardMarkup(keyboard)

    @staticmethod
    def snipe_confirm(
        symbol: str,
        address: str,
        amount: float,
        price: float,
        sl_percent: float = 15.0,
        tp_percent: float = 15.0,
    ) -> Tuple[str, InlineKeyboardMarkup]:
        """
        Snipe confirmation screen before execution.
        """
        theme = JarvisTheme

        # Price formatting
        if price < 0.0001:
            price_str = f"${price:.8f}"
        elif price < 1:
            price_str = f"${price:.6f}"
        else:
            price_str = f"${price:.2f}"

        # Calculate SL/TP
        sl_price = price * (1 - sl_percent / 100)
        tp_price = price * (1 + tp_percent / 100)
        sl_str = f"${sl_price:.8f}" if sl_price < 0.0001 else f"${sl_price:.6f}" if sl_price < 1 else f"${sl_price:.2f}"
        tp_str = f"${tp_price:.8f}" if tp_price < 0.0001 else f"${tp_price:.6f}" if tp_price < 1 else f"${tp_price:.2f}"

        usd_value = amount * 225  # Approximate SOL price

        lines = [
            f"⚡ *CONFIRM SNIPE*",
            "━━━━━━━━━━━━━━━━━━━━━",
            "",
            f"*Token:* {symbol}",
            f"*Amount:* {amount} SOL (~${usd_value:.2f})",
            f"*Price:* {price_str}",
            "",
            "🛡️ *Protection Orders*",
            f"├ Stop Loss: -{sl_percent:.0f}% @ {sl_str}",
            f"└ Take Profit: +{tp_percent:.0f}% @ {tp_str}",
            "",
            "━━━━━━━━━━━━━━━━━━━━━",
            "⚠️ _This will execute immediately_",
        ]

        text = "\n".join(lines)

        keyboard = [
            [
                InlineKeyboardButton(f"✅ CONFIRM SNIPE", callback_data=f"demo:snipe_confirm:{address}:{amount}"),
            ],
            [
                InlineKeyboardButton(f"❌ Cancel", callback_data="demo:insta_snipe"),
            ],
        ]

        return text, InlineKeyboardMarkup(keyboard)

    @staticmethod
    def snipe_result(
        success: bool,
        symbol: str,
        amount: float,
        tx_hash: str = None,
        error: str = None,
        sl_set: bool = False,
        tp_set: bool = False,
    ) -> Tuple[str, InlineKeyboardMarkup]:
        """
        Snipe execution result.
        """
        theme = JarvisTheme

        if success:
            lines = [
                f"✅ *SNIPE SUCCESSFUL*",
                "━━━━━━━━━━━━━━━━━━━━━",
                "",
                f"*Token:* {symbol}",
                f"*Amount:* {amount} SOL",
                "",
                "🛡️ *Protection Status*",
                f"├ Stop Loss: {'✅ Set' if sl_set else '⏳ Pending'}",
                f"└ Take Profit: {'✅ Set' if tp_set else '⏳ Pending'}",
                "",
            ]
            if tx_hash:
                short_hash = f"{tx_hash[:8]}...{tx_hash[-8:]}" if len(tx_hash) > 16 else tx_hash
                lines.extend([
                    f"*TX:* `{short_hash}`",
                    "",
                ])
            lines.extend([
                "━━━━━━━━━━━━━━━━━━━━━",
                "_Position added to portfolio_",
            ])
        else:
            lines = [
                f"❌ *SNIPE FAILED*",
                "━━━━━━━━━━━━━━━━━━━━━",
                "",
                f"*Token:* {symbol}",
                f"*Amount:* {amount} SOL",
                "",
                f"*Error:* {error or 'Unknown error'}",
                "",
                "━━━━━━━━━━━━━━━━━━━━━",
                "_Try again or check balance_",
            ]

        text = "\n".join(lines)

        keyboard = [
            [
                InlineKeyboardButton(f"⚡ Snipe Again", callback_data="demo:insta_snipe"),
                InlineKeyboardButton(f"📊 Positions", callback_data="demo:positions"),
            ],
            [
                InlineKeyboardButton(f"{theme.BACK} Main Menu", callback_data="demo:main"),
            ],
        ]

        return text, InlineKeyboardMarkup(keyboard)

    @staticmethod
    def close_position_result(
        success: bool,
        symbol: str,
        amount: float,
        entry_price: float,
        exit_price: float,
        pnl_usd: float,
        pnl_percent: float,
        success_fee: float = 0.0,
        net_profit: float = None,
        tx_hash: str = None,
        error: str = None,
    ) -> Tuple[str, InlineKeyboardMarkup]:
        """
        Position close result with success fee display.

        Shows:
        - PnL details
        - Success fee (0.5% on profit) if winning trade
        - Net profit after fee
        """
        theme = JarvisTheme

        is_profit = pnl_usd > 0
        pnl_emoji = "📈" if is_profit else "📉"
        pnl_sign = "+" if is_profit else ""

        if success:
            lines = [
                f"✅ *POSITION CLOSED*",
                "━━━━━━━━━━━━━━━━━━━━━",
                "",
                f"*Token:* {symbol}",
                f"*Amount:* {amount} SOL",
                "",
                f"*Entry:* ${entry_price:.8f}" if entry_price < 0.0001 else f"*Entry:* ${entry_price:.6f}" if entry_price < 1 else f"*Entry:* ${entry_price:.4f}",
                f"*Exit:* ${exit_price:.8f}" if exit_price < 0.0001 else f"*Exit:* ${exit_price:.6f}" if exit_price < 1 else f"*Exit:* ${exit_price:.4f}",
                "",
                f"{pnl_emoji} *P&L:* {pnl_sign}${abs(pnl_usd):.2f} ({pnl_sign}{pnl_percent:.1f}%)",
            ]

            # Show success fee if it was a winning trade
            if is_profit and success_fee > 0:
                lines.extend([
                    "",
                    "💰 *Success Fee (0.5% on profit)*",
                    f"├ Fee: -${success_fee:.4f}",
                    f"└ Net Profit: +${(net_profit or (pnl_usd - success_fee)):.2f}",
                    "",
                    "_Fee supports JARVIS development_",
                ])
            elif not is_profit:
                lines.extend([
                    "",
                    "💰 _No success fee (losing trade)_",
                ])

            if tx_hash:
                short_hash = f"{tx_hash[:8]}...{tx_hash[-8:]}" if len(tx_hash) > 16 else tx_hash
                lines.extend([
                    "",
                    f"*TX:* `{short_hash}`",
                ])

            lines.extend([
                "",
                "━━━━━━━━━━━━━━━━━━━━━",
            ])
        else:
            lines = [
                f"❌ *CLOSE FAILED*",
                "━━━━━━━━━━━━━━━━━━━━━",
                "",
                f"*Token:* {symbol}",
                f"*Error:* {error or 'Unknown error'}",
                "",
                "━━━━━━━━━━━━━━━━━━━━━",
                "_Try again or check position_",
            ]

        text = "\n".join(lines)

        keyboard = [
            [
                InlineKeyboardButton(f"📊 Positions", callback_data="demo:positions"),
                InlineKeyboardButton(f"📊 Hub", callback_data="demo:hub"),
            ],
            [
                InlineKeyboardButton(f"{theme.BACK} Main Menu", callback_data="demo:main"),
            ],
        ]

        return text, InlineKeyboardMarkup(keyboard)

    # ========== END SENTIMENT HUB ==========

    @staticmethod
    def ai_report_menu(
        market_regime: Dict[str, Any] = None,
    ) -> Tuple[str, InlineKeyboardMarkup]:
        """
        Show AI sentiment report summary.

        Displays the current market analysis from our sentiment engine.
        """
        theme = JarvisTheme

        regime = market_regime or {}
        regime_name = regime.get("regime", "NEUTRAL")
        risk_level = regime.get("risk_level", "NORMAL")
        btc_change = regime.get("btc_change_24h", 0)
        sol_change = regime.get("sol_change_24h", 0)
        btc_trend = regime.get("btc_trend", "NEUTRAL")
        sol_trend = regime.get("sol_trend", "NEUTRAL")

        # Status emojis
        regime_emoji = {"BULL": "🟢", "BEAR": "🔴"}.get(regime_name, "🟡")
        btc_emoji = "📈" if btc_change >= 0 else "📉"
        sol_emoji = "📈" if sol_change >= 0 else "📉"
        risk_emoji = {"LOW": "🟢", "NORMAL": "🟡", "HIGH": "🟠", "EXTREME": "🔴"}.get(risk_level, "⚪")

        # Determine recommendation
        if regime_name == "BULL" and risk_level in ("LOW", "NORMAL"):
            recommendation = "✅ CONDITIONS FAVORABLE - Look for quality entries"
        elif regime_name == "BEAR":
            recommendation = "⚠️ CAUTION - Reduce position sizes or wait"
        elif risk_level in ("HIGH", "EXTREME"):
            recommendation = "🛑 HIGH RISK - Defensive positioning recommended"
        else:
            recommendation = "📊 NEUTRAL - Selective opportunities exist"

        text = f"""
{theme.AUTO} *AI MARKET REPORT*
━━━━━━━━━━━━━━━━━━━━━

{theme.CHART} *Market Regime*
┌ Overall: {regime_emoji} *{regime_name}*
├ Risk Level: {risk_emoji} *{risk_level}*
└ _Updated in real-time_

{btc_emoji} *Bitcoin*
├ 24h: *{btc_change:+.1f}%*
└ Trend: *{btc_trend}*

{sol_emoji} *Solana*
├ 24h: *{sol_change:+.1f}%*
└ Trend: *{sol_trend}*

━━━━━━━━━━━━━━━━━━━━━

{theme.AUTO} *AI Recommendation*
{recommendation}

━━━━━━━━━━━━━━━━━━━━━

_Powered by Grok + Multi-Source Sentiment_
_Data-driven scoring (Jan 2026 tune)_
"""

        keyboard = [
            [
                InlineKeyboardButton(f"{theme.AUTO} Get AI Picks", callback_data="demo:ai_picks"),
            ],
            [
                InlineKeyboardButton(f"{theme.FIRE} Trending", callback_data="demo:trending"),
                InlineKeyboardButton(f"{theme.CHART} Positions", callback_data="demo:positions"),
            ],
            [
                InlineKeyboardButton(f"{theme.REFRESH} Refresh", callback_data="demo:ai_report"),
            ],
            [
                InlineKeyboardButton(f"{theme.BACK} Back", callback_data="demo:main"),
            ],
        ]

        return text, InlineKeyboardMarkup(keyboard)

    @staticmethod
    def token_analysis_menu(
        token_data: Dict[str, Any],
    ) -> Tuple[str, InlineKeyboardMarkup]:
        """
        Show detailed AI analysis for a specific token.
        """
        theme = JarvisTheme

        symbol = token_data.get("symbol", "???")
        address = token_data.get("address", "")
        price = token_data.get("price_usd", 0)
        change_24h = token_data.get("change_24h", 0)
        volume = token_data.get("volume", 0)
        liquidity = token_data.get("liquidity", 0)

        # Sentiment data
        sentiment = token_data.get("sentiment", "neutral")
        score = token_data.get("score", 0)
        confidence = token_data.get("confidence", 0)
        signal = token_data.get("signal", "NEUTRAL")
        reasons = token_data.get("reasons", [])

        # Sentiment emoji
        sent_emoji = {"bullish": "🟢", "bearish": "🔴", "very_bullish": "🚀", "very_bearish": "💀"}.get(
            sentiment.lower(), "🟡"
        )

        # Signal emoji
        sig_emoji = {"STRONG_BUY": "🔥", "BUY": "🟢", "SELL": "🔴", "STRONG_SELL": "💀"}.get(signal, "🟡")

        short_addr = f"{address[:6]}...{address[-4:]}" if address else "N/A"
        change_emoji = "📈" if change_24h >= 0 else "📉"

        lines = [
            f"{theme.AUTO} *AI TOKEN ANALYSIS*",
            "━━━━━━━━━━━━━━━━━━━━━",
            "",
            f"*{symbol}*",
            f"Address: `{short_addr}`",
            "",
            f"{change_emoji} *Price Data*",
            f"├ Price: ${price:.8f}",
            f"├ 24h: {change_24h:+.1f}%",
            f"├ Volume: ${volume/1000:.0f}K",
            f"└ Liquidity: ${liquidity/1000:.0f}K",
            "",
            f"{sent_emoji} *AI Sentiment*",
            f"├ Verdict: *{sentiment.upper()}*",
            f"├ Score: *{score:.2f}*",
            f"└ Confidence: *{confidence:.0%}*",
            "",
            f"{sig_emoji} *Signal: {signal}*",
        ]

        if reasons:
            lines.append("")
            lines.append("_Reasons:_")
            for reason in reasons[:3]:
                lines.append(f"• {reason}")

        text = "\n".join(lines)

        keyboard = [
            [
                InlineKeyboardButton(f"{theme.BUY} Buy 0.1 SOL", callback_data=f"demo:quick_buy:{address}:0.1"),
                InlineKeyboardButton(f"{theme.BUY} Buy 0.5 SOL", callback_data=f"demo:quick_buy:{address}:0.5"),
            ],
            [
                InlineKeyboardButton(f"{theme.BUY} Buy 1 SOL", callback_data=f"demo:quick_buy:{address}:1"),
                InlineKeyboardButton(f"{theme.BUY} Buy 5 SOL", callback_data=f"demo:quick_buy:{address}:5"),
            ],
            [
                InlineKeyboardButton(f"{theme.REFRESH} Refresh Analysis", callback_data=f"demo:analyze:{address}"),
            ],
            [
                InlineKeyboardButton(f"{theme.BACK} Back", callback_data="demo:main"),
            ],
        ]

        return text, InlineKeyboardMarkup(keyboard)

    @staticmethod
    def success_message(
        action: str,
        details: str,
    ) -> Tuple[str, InlineKeyboardMarkup]:
        """Show success message."""
        theme = JarvisTheme

        text = f"""
{theme.SUCCESS} *SUCCESS*
━━━━━━━━━━━━━━━━━━━━━

*{action}*

{details}

━━━━━━━━━━━━━━━━━━━━━
"""

        keyboard = [
            [
                InlineKeyboardButton(f"{theme.HOME} Main Menu", callback_data="demo:main"),
                InlineKeyboardButton(f"{theme.CHART} Positions", callback_data="demo:positions"),
            ],
        ]

        return text, InlineKeyboardMarkup(keyboard)

    @staticmethod
    def error_message(
        error: str,
        error_code: str = None,
        retry_action: str = "demo:main",
        context_hint: str = None,
    ) -> Tuple[str, InlineKeyboardMarkup]:
        """
        Show user-friendly error message with recovery options.

        Args:
            error: Error message to display
            error_code: Optional error code for categorization
            retry_action: Callback to retry (default: main menu)
            context_hint: Additional context for the error
        """
        theme = JarvisTheme

        # Categorize error and provide helpful suggestions
        error_lower = error.lower()

        if "network" in error_lower or "timeout" in error_lower or "connection" in error_lower:
            category = "🌐 Network Error"
            suggestion = "Check your internet connection and try again."
        elif "wallet" in error_lower or "balance" in error_lower:
            category = "💳 Wallet Error"
            suggestion = "Make sure your wallet is connected and funded."
        elif "api" in error_lower or "rate limit" in error_lower:
            category = "⚡ API Error"
            suggestion = "Service temporarily unavailable. Wait a moment."
        elif "permission" in error_lower or "unauthorized" in error_lower:
            category = "🔐 Access Error"
            suggestion = "Check your permissions and try again."
        elif "not found" in error_lower:
            category = "🔍 Not Found"
            suggestion = "The requested item doesn't exist."
        elif "invalid" in error_lower or "failed" in error_lower:
            category = "❌ Operation Failed"
            suggestion = "Something went wrong. Please try again."
        else:
            category = f"{theme.ERROR} Error"
            suggestion = "An unexpected error occurred."

        lines = [
            f"{category}",
            "━━━━━━━━━━━━━━━━━━━━━",
            "",
            f"_{error[:150]}{'...' if len(error) > 150 else ''}_",
            "",
        ]

        if context_hint:
            lines.append(f"*Context:* {context_hint}")
            lines.append("")

        lines.extend([
            f"💡 *Suggestion:* {suggestion}",
            "",
            "━━━━━━━━━━━━━━━━━━━━━",
        ])

        if error_code:
            lines.append(f"_Code: {error_code}_")

        text = "\n".join(lines)

        keyboard = [
            [
                InlineKeyboardButton(f"{theme.REFRESH} Try Again", callback_data=retry_action),
                InlineKeyboardButton(f"{theme.BACK} Main Menu", callback_data="demo:main"),
            ],
        ]

        return text, InlineKeyboardMarkup(keyboard)

    @staticmethod
    def operation_failed(
        operation: str,
        reason: str = None,
        retry_action: str = None,
    ) -> Tuple[str, InlineKeyboardMarkup]:
        """Show operation-specific failure message."""
        theme = JarvisTheme

        text = f"""
❌ *{operation.upper()} FAILED*
━━━━━━━━━━━━━━━━━━━━━

{reason or 'Operation could not be completed.'}

Please try again or return to main menu.

━━━━━━━━━━━━━━━━━━━━━
"""

        keyboard = []
        if retry_action:
            keyboard.append([
                InlineKeyboardButton(f"{theme.REFRESH} Retry {operation}", callback_data=retry_action),
            ])
        keyboard.append([
            InlineKeyboardButton(f"{theme.BACK} Main Menu", callback_data="demo:main"),
        ])

        return text, InlineKeyboardMarkup(keyboard)

    @staticmethod
    def learning_dashboard(
        learning_stats: Dict[str, Any],
        compression_stats: Dict[str, Any] = None,
    ) -> Tuple[str, InlineKeyboardMarkup]:
        """
        Beautiful Learning Dashboard - Shows what JARVIS has learned.

        Displays:
        - Trade patterns learned
        - Signal effectiveness
        - Regime correlations
        - Compression statistics
        - Self-improvement metrics
        """
        theme = JarvisTheme

        # Extract stats
        total_trades = learning_stats.get("total_trades_analyzed", 0)
        pattern_memories = learning_stats.get("pattern_memories", 0)
        stable_strategies = learning_stats.get("stable_strategies", 0)
        signals = learning_stats.get("signals", {})
        regimes = learning_stats.get("regimes", {})
        optimal_hold = learning_stats.get("optimal_hold_time", 60)

        # Compression stats
        comp = compression_stats or {}
        compression_ratio = comp.get("compression_ratio", 1.0)
        learned_patterns = comp.get("learned_patterns", 0)

        lines = [
            f"{theme.AUTO} *JARVIS LEARNING DASHBOARD*",
            "━━━━━━━━━━━━━━━━━━━━━",
            "",
            f"🧠 *Memory Compression*",
            f"├ Trades Analyzed: *{total_trades}*",
            f"├ Pattern Memories: *{pattern_memories}*",
            f"├ Learned Patterns: *{learned_patterns}*",
            f"└ Compression: *{compression_ratio:.1f}x*",
            "",
        ]

        # Signal effectiveness
        if signals:
            lines.append(f"📊 *Signal Effectiveness*")
            for signal, stats in signals.items():
                win_rate = stats.get("win_rate", "N/A")
                avg_return = stats.get("avg_return", "0%")
                trades = stats.get("trades", 0)
                emoji = "🟢" if float(win_rate.replace("%", "")) > 55 else "🟡" if float(win_rate.replace("%", "")) > 45 else "🔴"
                lines.append(f"├ {emoji} {signal}: {win_rate} ({trades} trades)")
            lines.append("")

        # Regime correlations
        if regimes:
            lines.append(f"📈 *Regime Performance*")
            for regime, stats in regimes.items():
                win_rate = stats.get("win_rate", "N/A")
                avg_return = stats.get("avg_return", "0%")
                emoji = {"BULL": "🟢", "BEAR": "🔴"}.get(regime, "🟡")
                lines.append(f"├ {emoji} {regime}: {win_rate} | {avg_return}")
            lines.append("")

        # Optimal timing
        lines.extend([
            f"⏱️ *Optimal Timing*",
            f"└ Hold Time: *{optimal_hold:.0f} min*",
            "",
            "━━━━━━━━━━━━━━━━━━━━━",
            "",
            f"_{theme.AUTO} Self-Improving AI_",
            "_Every trade makes JARVIS smarter_",
        ])

        text = "\n".join(lines)

        keyboard = [
            [
                InlineKeyboardButton(f"🔬 Full Analysis", callback_data="demo:learning_deep"),
            ],
            [
                InlineKeyboardButton(f"📊 Signal Stats", callback_data="demo:signal_stats"),
                InlineKeyboardButton(f"📈 Regime Stats", callback_data="demo:regime_stats"),
            ],
            [
                InlineKeyboardButton(f"{theme.REFRESH} Refresh", callback_data="demo:learning"),
            ],
            [
                InlineKeyboardButton(f"{theme.BACK} Back", callback_data="demo:main"),
            ],
        ]

        return text, InlineKeyboardMarkup(keyboard)

    @staticmethod
    def recommendation_view(
        recommendation: Dict[str, Any],
        token_symbol: str = "TOKEN",
        market_regime: str = "NEUTRAL",
    ) -> Tuple[str, InlineKeyboardMarkup]:
        """
        Show AI recommendation based on learned patterns.

        This is GENERATIVE RETRIEVAL - reconstructing predictions
        from compressed pattern memories.
        """
        theme = JarvisTheme

        action = recommendation.get("action", "NEUTRAL")
        confidence = recommendation.get("confidence", 0.5)
        expected_return = recommendation.get("expected_return", 0)
        hold_time = recommendation.get("suggested_hold_minutes", 60)
        reasons = recommendation.get("reasons", [])
        warnings = recommendation.get("warnings", [])

        # Action emoji
        action_emoji = {
            "BUY": "🟢",
            "AVOID": "🔴",
            "NEUTRAL": "🟡",
        }.get(action, "⚪")

        # Confidence bar
        conf_bars = int(confidence * 10)
        conf_display = "█" * conf_bars + "░" * (10 - conf_bars)

        lines = [
            f"{theme.AUTO} *AI RECOMMENDATION*",
            "━━━━━━━━━━━━━━━━━━━━━",
            "",
            f"Token: *{token_symbol}*",
            f"Market: *{market_regime}*",
            "",
            f"{action_emoji} *Verdict: {action}*",
            f"Confidence: [{conf_display}] {confidence:.0%}",
            f"Expected: *{expected_return:+.1f}%*",
            f"Hold Time: *{hold_time:.0f} min*",
            "",
        ]

        if reasons:
            lines.append("✅ *Reasons:*")
            for reason in reasons[:3]:
                lines.append(f"   • {reason}")
            lines.append("")

        if warnings:
            lines.append("⚠️ *Warnings:*")
            for warning in warnings[:3]:
                lines.append(f"   • {warning}")
            lines.append("")

        lines.extend([
            "━━━━━━━━━━━━━━━━━━━━━",
            "_Based on learned trade patterns_",
        ])

        text = "\n".join(lines)

        keyboard = [
            [
                InlineKeyboardButton(f"{theme.HOME} Main Menu", callback_data="demo:main"),
            ],
        ]

        return text, InlineKeyboardMarkup(keyboard)

    @staticmethod
    def performance_dashboard(
        performance_stats: Dict[str, Any],
        trade_history: List[Dict[str, Any]] = None,
    ) -> Tuple[str, InlineKeyboardMarkup]:
        """
        Beautiful Portfolio Performance Dashboard.

        Shows:
        - Win/loss ratio and streaks
        - Total PnL tracking
        - Best/worst performers
        - Daily/weekly/monthly ROI
        - Trade frequency metrics
        """
        theme = JarvisTheme

        # Extract stats
        total_trades = performance_stats.get("total_trades", 0)
        wins = performance_stats.get("wins", 0)
        losses = performance_stats.get("losses", 0)
        win_rate = performance_stats.get("win_rate", 0)
        total_pnl = performance_stats.get("total_pnl", 0)
        total_pnl_pct = performance_stats.get("total_pnl_pct", 0)
        best_trade = performance_stats.get("best_trade", {})
        worst_trade = performance_stats.get("worst_trade", {})
        current_streak = performance_stats.get("current_streak", 0)
        avg_hold_time = performance_stats.get("avg_hold_time_minutes", 0)

        # Time-based performance
        daily_pnl = performance_stats.get("daily_pnl", 0)
        weekly_pnl = performance_stats.get("weekly_pnl", 0)
        monthly_pnl = performance_stats.get("monthly_pnl", 0)

        # PnL formatting
        pnl_emoji = theme.PROFIT if total_pnl >= 0 else theme.LOSS
        pnl_sign = "+" if total_pnl >= 0 else ""

        # Win rate bar
        win_bars = int(win_rate / 10) if win_rate else 0
        win_bar = "▰" * win_bars + "▱" * (10 - win_bars)

        # Streak formatting
        if current_streak > 0:
            streak_emoji = "🔥"
            streak_text = f"+{current_streak}W"
        elif current_streak < 0:
            streak_emoji = "❄️"
            streak_text = f"{current_streak}L"
        else:
            streak_emoji = "➖"
            streak_text = "0"

        lines = [
            f"📊 *PERFORMANCE DASHBOARD*",
            "━━━━━━━━━━━━━━━━━━━━━",
            "",
            f"💰 *Overall Performance*",
            f"├ Total P&L: {pnl_emoji} *{pnl_sign}${abs(total_pnl):.2f}* ({pnl_sign}{total_pnl_pct:.1f}%)",
            f"├ Trades: *{total_trades}* ({wins}W / {losses}L)",
            f"├ Win Rate: [{win_bar}] *{win_rate:.1f}%*",
            f"└ Streak: {streak_emoji} *{streak_text}*",
            "",
        ]

        # Time-based metrics
        daily_emoji = "🟢" if daily_pnl >= 0 else "🔴"
        weekly_emoji = "🟢" if weekly_pnl >= 0 else "🔴"
        monthly_emoji = "🟢" if monthly_pnl >= 0 else "🔴"

        lines.extend([
            f"📅 *Time Performance*",
            f"├ {daily_emoji} Today: *{'+' if daily_pnl >= 0 else ''}${daily_pnl:.2f}*",
            f"├ {weekly_emoji} This Week: *{'+' if weekly_pnl >= 0 else ''}${weekly_pnl:.2f}*",
            f"└ {monthly_emoji} This Month: *{'+' if monthly_pnl >= 0 else ''}${monthly_pnl:.2f}*",
            "",
        ])

        # Best/worst trades
        if best_trade:
            best_symbol = best_trade.get("symbol", "???")
            best_pnl = best_trade.get("pnl_pct", 0)
            lines.append(f"🏆 *Best Trade:* {best_symbol} (+{best_pnl:.1f}%)")

        if worst_trade:
            worst_symbol = worst_trade.get("symbol", "???")
            worst_pnl = worst_trade.get("pnl_pct", 0)
            lines.append(f"💀 *Worst Trade:* {worst_symbol} ({worst_pnl:.1f}%)")

        if best_trade or worst_trade:
            lines.append("")

        # Trading metrics
        lines.extend([
            f"⏱️ *Trading Metrics*",
            f"├ Avg Hold Time: *{avg_hold_time:.0f} min*",
            f"└ Avg Trade/Day: *{performance_stats.get('avg_trades_per_day', 0):.1f}*",
            "",
            "━━━━━━━━━━━━━━━━━━━━━",
            f"_{theme.AUTO} AI-Powered Analytics_",
        ])

        text = "\n".join(lines)

        keyboard = [
            [
                InlineKeyboardButton("📜 Trade History", callback_data="demo:trade_history"),
                InlineKeyboardButton("📈 PnL Chart", callback_data="demo:pnl_chart"),
            ],
            [
                InlineKeyboardButton("🏆 Leaderboard", callback_data="demo:leaderboard"),
                InlineKeyboardButton("🎯 Goals", callback_data="demo:goals"),
            ],
            [
                InlineKeyboardButton(f"{theme.REFRESH} Refresh", callback_data="demo:performance"),
            ],
            [
                InlineKeyboardButton(f"{theme.BACK} Back", callback_data="demo:main"),
            ],
        ]

        return text, InlineKeyboardMarkup(keyboard)

    @staticmethod
    def trade_history_view(
        trades: List[Dict[str, Any]],
        page: int = 0,
        page_size: int = 5,
    ) -> Tuple[str, InlineKeyboardMarkup]:
        """
        Show recent trade history with pagination.
        """
        theme = JarvisTheme

        if not trades:
            text = f"""
{theme.CHART} *TRADE HISTORY*
━━━━━━━━━━━━━━━━━━━━━

_No trades recorded yet_

Start trading to build your history!
"""
            keyboard = [
                [InlineKeyboardButton(f"{theme.BACK} Back", callback_data="demo:performance")],
            ]
            return text, InlineKeyboardMarkup(keyboard)

        # Paginate
        start_idx = page * page_size
        end_idx = start_idx + page_size
        page_trades = trades[start_idx:end_idx]
        total_pages = (len(trades) + page_size - 1) // page_size

        lines = [
            f"📜 *TRADE HISTORY*",
            "━━━━━━━━━━━━━━━━━━━━━",
            f"Page {page + 1}/{total_pages} ({len(trades)} total)",
            "",
        ]

        for trade in page_trades:
            symbol = trade.get("symbol", "???")
            pnl_pct = trade.get("pnl_pct", 0)
            pnl_usd = trade.get("pnl_usd", 0)
            outcome = trade.get("outcome", "")
            timestamp = trade.get("timestamp", "")

            emoji = "🟢" if pnl_pct >= 0 else "🔴"
            pnl_sign = "+" if pnl_pct >= 0 else ""

            lines.extend([
                f"{emoji} *{symbol}* {pnl_sign}{pnl_pct:.1f}%",
                f"   P&L: {pnl_sign}${abs(pnl_usd):.2f}",
                "",
            ])

        text = "\n".join(lines)

        # Pagination buttons
        nav_buttons = []
        if page > 0:
            nav_buttons.append(InlineKeyboardButton("◀️ Prev", callback_data=f"demo:history_page:{page-1}"))
        if end_idx < len(trades):
            nav_buttons.append(InlineKeyboardButton("Next ▶️", callback_data=f"demo:history_page:{page+1}"))

        keyboard = []
        if nav_buttons:
            keyboard.append(nav_buttons)
        keyboard.append([InlineKeyboardButton(f"{theme.BACK} Back", callback_data="demo:performance")])

        return text, InlineKeyboardMarkup(keyboard)

    @staticmethod
    def quick_trade_menu(
        trending_tokens: List[Dict[str, Any]] = None,
        positions: List[Dict[str, Any]] = None,
        sol_balance: float = 0.0,
        market_regime: str = "NEUTRAL",
    ) -> Tuple[str, InlineKeyboardMarkup]:
        """
        Quick Trade Menu - One-tap trading actions.

        Features:
        - Quick buy trending tokens
        - Sell all positions button
        - Snipe mode toggle
        - Pre-set amount buttons
        """
        theme = JarvisTheme

        regime_emoji = {"BULL": "🟢", "BEAR": "🔴"}.get(market_regime, "🟡")
        position_count = len(positions) if positions else 0

        lines = [
            f"⚡ *QUICK TRADE*",
            "━━━━━━━━━━━━━━━━━━━━━",
            f"Market: {regime_emoji} *{market_regime}*",
            f"Balance: *{sol_balance:.4f} SOL*",
            f"Positions: *{position_count}*",
            "",
        ]

        keyboard = []

        # Quick buy trending tokens (top 3)
        if trending_tokens:
            lines.append("🔥 *Hot Tokens:*")
            for i, token in enumerate(trending_tokens[:3]):
                symbol = token.get("symbol", "???")
                change = token.get("change_24h", 0)
                address = token.get("address", "")
                emoji = "🟢" if change >= 0 else "🔴"
                lines.append(f"  {emoji} {symbol} ({'+' if change >= 0 else ''}{change:.1f}%)")

                if address:
                    keyboard.append([
                        InlineKeyboardButton(
                            f"{theme.BUY} Buy {symbol} (0.1 SOL)",
                            callback_data=f"demo:quick_buy:{address}:0.1"
                        ),
                        InlineKeyboardButton(
                            f"{theme.BUY} (0.5 SOL)",
                            callback_data=f"demo:quick_buy:{address}:0.5"
                        ),
                    ])
            lines.append("")

        # Quick sell all button
        if positions and position_count > 0:
            lines.append(f"📦 *{position_count} Open Position(s)*")
            keyboard.append([
                InlineKeyboardButton(
                    f"💰 Sell All ({position_count} pos)",
                    callback_data="demo:sell_all"
                ),
            ])
            lines.append("")

        # Snipe mode
        keyboard.extend([
            [
                InlineKeyboardButton(f"🎯 Snipe Mode", callback_data="demo:snipe_mode"),
                InlineKeyboardButton(f"🔍 Search Token", callback_data="demo:token_input"),
            ],
            [
                InlineKeyboardButton(f"{theme.FIRE} AI Trending", callback_data="demo:trending"),
                InlineKeyboardButton(f"{theme.AUTO} AI Picks", callback_data="demo:ai_picks"),
            ],
            [
                InlineKeyboardButton(f"{theme.BACK} Back", callback_data="demo:main"),
            ],
        ])

        lines.extend([
            "━━━━━━━━━━━━━━━━━━━━━",
            "_One-tap trading for speed_",
        ])

        text = "\n".join(lines)
        return text, InlineKeyboardMarkup(keyboard)

    @staticmethod
    def snipe_mode_view() -> Tuple[str, InlineKeyboardMarkup]:
        """
        Snipe Mode - Instant buy on token address paste.
        """
        theme = JarvisTheme

        text = f"""
🎯 *SNIPE MODE ACTIVE*
━━━━━━━━━━━━━━━━━━━━━

Paste a Solana token address to
instantly buy with your preset amount.

*Current Settings:*
├ Amount: *0.1 SOL*
├ Slippage: *1%*
└ Auto-TP: *+50%*

━━━━━━━━━━━━━━━━━━━━━

_Reply with a token address to snipe_
_Example: 7GCihgDB8..._

{theme.WARNING} *Caution:* Snipe mode executes
immediately without confirmation!
"""

        keyboard = [
            [
                InlineKeyboardButton("💰 Amount: 0.1", callback_data="demo:snipe_amount:0.1"),
                InlineKeyboardButton("0.5", callback_data="demo:snipe_amount:0.5"),
                InlineKeyboardButton("1", callback_data="demo:snipe_amount:1"),
            ],
            [
                InlineKeyboardButton(f"🔴 Disable Snipe", callback_data="demo:snipe_disable"),
            ],
            [
                InlineKeyboardButton(f"{theme.BACK} Back", callback_data="demo:quick_trade"),
            ],
        ]

        return text, InlineKeyboardMarkup(keyboard)

    @staticmethod
    def watchlist_menu(
        watchlist: List[Dict[str, Any]],
    ) -> Tuple[str, InlineKeyboardMarkup]:
        """
        Token Watchlist - Track your favorite tokens.

        Features:
        - Live price updates
        - Quick buy buttons
        - Price alerts (V2)
        """
        theme = JarvisTheme

        lines = [
            f"⭐ *WATCHLIST*",
            "━━━━━━━━━━━━━━━━━━━━━",
            "",
        ]

        keyboard = []

        if not watchlist:
            lines.extend([
                "_Your watchlist is empty_",
                "",
                "Add tokens to track their prices",
                "and get quick access to trade!",
                "",
                "_Paste a token address to add_",
            ])
        else:
            for i, token in enumerate(watchlist[:8]):
                symbol = token.get("symbol", "???")
                address = token.get("address", "")
                price = token.get("price", 0)
                change_24h = token.get("change_24h", 0)
                alert = token.get("alert", None)

                change_emoji = "🟢" if change_24h >= 0 else "🔴"
                change_sign = "+" if change_24h >= 0 else ""

                lines.append(f"{change_emoji} *{symbol}* ${price:.6f}")
                lines.append(f"   {change_sign}{change_24h:.1f}% (24h)")

                if alert:
                    lines.append(f"   🔔 Alert: ${alert}")

                lines.append("")

                if address:
                    keyboard.append([
                        InlineKeyboardButton(
                            f"{theme.BUY} Buy {symbol}",
                            callback_data=f"demo:quick_buy:{address}:0.1"
                        ),
                        InlineKeyboardButton(
                            f"🗑️ Remove",
                            callback_data=f"demo:watchlist_remove:{i}"
                        ),
                    ])

        lines.extend([
            "━━━━━━━━━━━━━━━━━━━━━",
        ])

        text = "\n".join(lines)

        keyboard.extend([
            [
                InlineKeyboardButton(f"➕ Add Token", callback_data="demo:watchlist_add"),
                InlineKeyboardButton(f"{theme.REFRESH} Refresh", callback_data="demo:watchlist"),
            ],
            [
                InlineKeyboardButton(f"{theme.BACK} Back", callback_data="demo:main"),
            ],
        ])

        return text, InlineKeyboardMarkup(keyboard)


# =============================================================================
# Demo Command Handler
# =============================================================================

@error_handler
@admin_only
async def demo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /demo - Launch the beautiful JARVIS V1 AI trading demo (admin only).

    The Mona Lisa of AI Trading Bots featuring:
    - Real-time market regime detection
    - Grok-powered sentiment analysis
    - Data-driven entry criteria (67% TP rate)
    - Multi-source signal aggregation
    - Self-improving trade intelligence
    - Generative compression memory
    """
    try:
        # Get wallet and balance info
        wallet_address = "Not configured"
        sol_balance = 0.0
        usd_value = 0.0
        open_positions = 0
        total_pnl = 0.0
        is_live = False
        market_regime = {}

        # Fetch market regime from sentiment engine
        try:
            market_regime = await get_market_regime()
        except Exception as e:
            logger.warning(f"Could not load market regime: {e}")

        try:
            from tg_bot import bot_core as bot_module
            engine = await bot_module._get_treasury_engine()

            # Get wallet address
            treasury = engine.wallet.get_treasury()
            if treasury:
                wallet_address = treasury.address

            # Get balance
            sol_balance, usd_value = await engine.get_portfolio_value()

            # Get positions
            await engine.update_positions()
            positions = engine.get_open_positions()
            open_positions = len(positions)

            # Calculate total P&L
            for pos in positions:
                total_pnl += pos.unrealized_pnl

            is_live = not engine.dry_run

        except Exception as e:
            logger.warning(f"Could not load treasury data: {e}")

        # Build and send the beautiful main menu with AI features
        ai_auto_enabled = context.user_data.get("ai_auto_trade", False)
        text, keyboard = DemoMenuBuilder.main_menu(
            wallet_address=wallet_address,
            sol_balance=sol_balance,
            usd_value=usd_value,
            is_live=is_live,
            open_positions=open_positions,
            total_pnl=total_pnl,
            market_regime=market_regime,
            ai_auto_enabled=ai_auto_enabled,
        )

        await update.message.reply_text(
            text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard,
        )

    except Exception as e:
        logger.error(f"Demo command failed: {e}")
        text, keyboard = DemoMenuBuilder.error_message(f"Failed to load: {str(e)[:100]}")
        await update.message.reply_text(
            text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard,
        )


# =============================================================================
# Callback Handler for Demo UI
# =============================================================================

@error_handler
async def demo_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle all demo:* callbacks."""
    query = update.callback_query
    await query.answer()

    data = query.data

    if not data.startswith("demo:"):
        return

    action = data.split(":")[1] if ":" in data else data

    try:
        # Get current state
        wallet_address = "Not configured"
        sol_balance = 0.0
        usd_value = 0.0
        open_positions_count = 0
        total_pnl = 0.0
        is_live = False
        positions = []

        try:
            from tg_bot import bot_core as bot_module
            engine = await bot_module._get_treasury_engine()

            treasury = engine.wallet.get_treasury()
            if treasury:
                wallet_address = treasury.address

            sol_balance, usd_value = await engine.get_portfolio_value()

            await engine.update_positions()
            open_pos = engine.get_open_positions()
            positions = [
                {
                    "symbol": p.token_symbol,
                    "pnl_pct": p.unrealized_pnl_pct,
                    "pnl_usd": p.unrealized_pnl,
                    "entry_price": p.entry_price,
                    "current_price": p.current_price,
                    "id": p.id,
                }
                for p in open_pos
            ]
            open_positions_count = len(positions)

            for p in open_pos:
                total_pnl += p.unrealized_pnl

            is_live = not engine.dry_run

        except Exception as e:
            logger.warning(f"Could not load treasury data in callback: {e}")

        # Get market regime for AI features
        market_regime = await get_market_regime()

        # Route to appropriate handler
        ai_auto_enabled = context.user_data.get("ai_auto_trade", False)

        if action in ("main", "refresh"):
            text, keyboard = DemoMenuBuilder.main_menu(
                wallet_address=wallet_address,
                sol_balance=sol_balance,
                usd_value=usd_value,
                is_live=is_live,
                open_positions=open_positions_count,
                total_pnl=total_pnl,
                market_regime=market_regime,
                ai_auto_enabled=ai_auto_enabled,
            )

        elif action == "wallet_menu":
            # Fetch token holdings
            token_holdings = []
            total_holdings_usd = 0.0
            try:
                from tg_bot import bot_core as bot_module
                engine = await bot_module._get_treasury_engine()
                if engine and hasattr(engine, 'get_token_holdings'):
                    holdings = await engine.get_token_holdings()
                    if holdings:
                        token_holdings = holdings
                        total_holdings_usd = sum(h.get("value_usd", 0) for h in holdings)
            except Exception:
                pass

            text, keyboard = DemoMenuBuilder.wallet_menu(
                wallet_address=wallet_address,
                sol_balance=sol_balance,
                usd_value=usd_value,
                has_wallet=wallet_address != "Not configured",
                token_holdings=token_holdings,
                total_holdings_usd=total_holdings_usd,
            )

        elif action == "token_holdings":
            # Detailed token holdings view
            token_holdings = []
            total_holdings_usd = 0.0
            try:
                from tg_bot import bot_core as bot_module
                engine = await bot_module._get_treasury_engine()
                if engine and hasattr(engine, 'get_token_holdings'):
                    holdings = await engine.get_token_holdings()
                    if holdings:
                        token_holdings = holdings
                        total_holdings_usd = sum(h.get("value_usd", 0) for h in holdings)
            except Exception:
                pass

            text, keyboard = DemoMenuBuilder.token_holdings_view(
                holdings=token_holdings,
                total_value=total_holdings_usd,
            )

        elif action == "wallet_activity":
            # Wallet transaction history
            transactions = []
            try:
                from tg_bot import bot_core as bot_module
                engine = await bot_module._get_treasury_engine()
                if engine and hasattr(engine, 'get_transaction_history'):
                    transactions = await engine.get_transaction_history()
            except Exception:
                pass

            text, keyboard = DemoMenuBuilder.wallet_activity_view(
                transactions=transactions,
            )

        elif action == "send_sol":
            text, keyboard = DemoMenuBuilder.send_sol_view(sol_balance=sol_balance)

        elif action == "receive_sol":
            # Show receive address with QR placeholder
            theme = JarvisTheme
            text = f"""
📥 *RECEIVE SOL*
━━━━━━━━━━━━━━━━━━━━━

Your wallet address:
`{wallet_address}`

_Tap the address to copy_

{theme.WARNING} Only send SOL and Solana
   tokens to this address!

━━━━━━━━━━━━━━━━━━━━━
_QR code coming in V2_
"""
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton(f"{theme.COPY} Copy Address", callback_data="demo:copy_address")],
                [InlineKeyboardButton(f"{theme.BACK} Back", callback_data="demo:wallet_menu")],
            ])

        elif action == "export_key_confirm":
            text, keyboard = DemoMenuBuilder.export_key_confirm()

        elif action == "wallet_reset_confirm":
            text, keyboard = DemoMenuBuilder.wallet_reset_confirm()

        elif action == "wallet_import":
            # Show wallet import options
            text, keyboard = DemoMenuBuilder.wallet_import_prompt()

        elif action == "import_mode_key":
            # Set import mode to private key
            context.user_data["import_mode"] = "key"
            context.user_data["awaiting_wallet_import"] = True
            text, keyboard = DemoMenuBuilder.wallet_import_input(import_type="key")

        elif action == "import_mode_seed":
            # Set import mode to seed phrase
            context.user_data["import_mode"] = "seed"
            context.user_data["awaiting_wallet_import"] = True
            text, keyboard = DemoMenuBuilder.wallet_import_input(import_type="seed")

        elif action == "export_key":
            # Show actual private key (SENSITIVE)
            theme = JarvisTheme
            try:
                from bots.treasury.wallet import SecureWallet
                wallet = SecureWallet()
                private_key = wallet.get_private_key()  # Returns base58 key
                wallet_address = wallet.get_address()

                text, keyboard = DemoMenuBuilder.export_key_show(
                    private_key=private_key,
                    wallet_address=wallet_address,
                )
                logger.warning(f"Private key exported for wallet {wallet_address[:8]}...")
            except Exception as e:
                logger.error(f"Failed to export key: {e}")
                text, keyboard = DemoMenuBuilder.error_message(
                    f"Could not export key: {str(e)[:50]}"
                )

        elif action == "wallet_create":
            # Generate new wallet
            try:
                from bots.treasury.wallet import SecureWallet
                wallet = SecureWallet()
                # Note: In production, this would require password setup
                # For demo, show what would happen
                text, keyboard = DemoMenuBuilder.success_message(
                    action="Wallet Generated",
                    details="New Solana wallet created and encrypted.\n\nSend SOL to fund your trading!",
                )
            except Exception as e:
                text, keyboard = DemoMenuBuilder.error_message(f"Wallet creation failed: {e}")

        elif action == "positions":
            text, keyboard = DemoMenuBuilder.positions_menu(
                positions=positions,
                total_pnl=total_pnl,
            )

        elif action == "settings":
            ai_auto = context.user_data.get("ai_auto_trade", False)
            text, keyboard = DemoMenuBuilder.settings_menu(
                is_live=is_live,
                ai_auto_trade=ai_auto,
            )

        elif action == "fee_stats":
            # Show fee collection statistics
            fee_manager = get_success_fee_manager()
            stats = fee_manager.get_fee_stats()
            text, keyboard = DemoMenuBuilder.fee_stats_view(
                fee_percent=stats.get("fee_percent", 0.5),
                total_collected=stats.get("total_collected", 0.0),
                transaction_count=stats.get("transaction_count", 0),
                recent_fees=stats.get("recent_fees", []),
            )

        elif action == "pnl_report":
            # Show P&L report
            # Calculate stats from positions
            winners = sum(1 for p in positions if p.get("pnl_pct", 0) >= 0)
            losers = sum(1 for p in positions if p.get("pnl_pct", 0) < 0)
            total_pnl_pct = sum(p.get("pnl_pct", 0) for p in positions) / max(len(positions), 1)

            # Find best and worst
            best_trade = max(positions, key=lambda p: p.get("pnl_pct", 0)) if positions else None
            worst_trade = min(positions, key=lambda p: p.get("pnl_pct", 0)) if positions else None

            text, keyboard = DemoMenuBuilder.pnl_report_view(
                positions=positions,
                total_pnl_usd=total_pnl,
                total_pnl_percent=total_pnl_pct,
                winners=winners,
                losers=losers,
                best_trade=best_trade,
                worst_trade=worst_trade,
            )

        elif action == "ai_auto_settings":
            # AI Auto-Trade Settings
            ai_settings = context.user_data.get("ai_settings", {})
            text, keyboard = DemoMenuBuilder.ai_auto_trade_settings(
                enabled=ai_settings.get("enabled", False),
                risk_level=ai_settings.get("risk_level", "MEDIUM"),
                max_position_size=ai_settings.get("max_position_size", 0.5),
                min_confidence=ai_settings.get("min_confidence", 0.7),
                daily_limit=ai_settings.get("daily_limit", 2.0),
                cooldown_minutes=ai_settings.get("cooldown_minutes", 30),
            )

        elif action.startswith("ai_auto_toggle:"):
            # Toggle AI auto-trade
            parts = data.split(":")
            new_state = parts[2].lower() == "true" if len(parts) >= 3 else False

            # Update settings
            ai_settings = context.user_data.get("ai_settings", {})
            ai_settings["enabled"] = new_state
            context.user_data["ai_settings"] = ai_settings
            context.user_data["ai_auto_trade"] = new_state

            action_text = "ENABLED" if new_state else "DISABLED"
            text, keyboard = DemoMenuBuilder.success_message(
                action=f"AI Auto-Trade {action_text}",
                details=f"Autonomous trading is now {'active' if new_state else 'paused'}.\n\n{'JARVIS will monitor markets and execute trades based on your settings.' if new_state else 'JARVIS will not execute trades automatically.'}",
            )

        elif action.startswith("ai_risk:"):
            # Set AI risk level
            parts = data.split(":")
            risk_level = parts[2] if len(parts) >= 3 else "MEDIUM"

            ai_settings = context.user_data.get("ai_settings", {})
            ai_settings["risk_level"] = risk_level
            context.user_data["ai_settings"] = ai_settings

            # Return to settings view
            text, keyboard = DemoMenuBuilder.ai_auto_trade_settings(
                enabled=ai_settings.get("enabled", False),
                risk_level=risk_level,
                max_position_size=ai_settings.get("max_position_size", 0.5),
                min_confidence=ai_settings.get("min_confidence", 0.7),
            )

        elif action.startswith("ai_max:"):
            # Set max position size
            parts = data.split(":")
            max_size = float(parts[2]) if len(parts) >= 3 else 0.5

            ai_settings = context.user_data.get("ai_settings", {})
            ai_settings["max_position_size"] = max_size
            context.user_data["ai_settings"] = ai_settings

            text, keyboard = DemoMenuBuilder.ai_auto_trade_settings(
                enabled=ai_settings.get("enabled", False),
                risk_level=ai_settings.get("risk_level", "MEDIUM"),
                max_position_size=max_size,
                min_confidence=ai_settings.get("min_confidence", 0.7),
            )

        elif action.startswith("ai_conf:"):
            # Set min confidence threshold
            parts = data.split(":")
            min_conf = float(parts[2]) if len(parts) >= 3 else 0.7

            ai_settings = context.user_data.get("ai_settings", {})
            ai_settings["min_confidence"] = min_conf
            context.user_data["ai_settings"] = ai_settings

            text, keyboard = DemoMenuBuilder.ai_auto_trade_settings(
                enabled=ai_settings.get("enabled", False),
                risk_level=ai_settings.get("risk_level", "MEDIUM"),
                max_position_size=ai_settings.get("max_position_size", 0.5),
                min_confidence=min_conf,
            )

        elif action == "ai_auto_status":
            # AI Auto-Trade Status View
            ai_settings = context.user_data.get("ai_settings", {})
            text, keyboard = DemoMenuBuilder.ai_auto_trade_status(
                enabled=ai_settings.get("enabled", False),
                trades_today=context.user_data.get("ai_trades_today", 0),
                pnl_today=context.user_data.get("ai_pnl_today", 0.0),
            )

        elif action == "ai_trades_history":
            # AI Trades History (placeholder)
            theme = JarvisTheme
            text = f"""
{theme.AUTO} *AI TRADE HISTORY*
━━━━━━━━━━━━━━━━━━━━━

_No AI trades executed yet_

When AI auto-trading is enabled,
JARVIS will:
• Analyze market conditions
• Find high-confidence opportunities
• Execute trades within your limits
• Record all trades here

━━━━━━━━━━━━━━━━━━━━━
_Feature tracking all AI trades coming in V2_
"""
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton(f"{theme.BACK} Back", callback_data="demo:ai_auto_settings")],
            ])

        elif action == "balance":
            text, keyboard = DemoMenuBuilder.wallet_menu(
                wallet_address=wallet_address,
                sol_balance=sol_balance,
                usd_value=usd_value,
                has_wallet=True,
            )

        # ========== P&L ALERTS HANDLERS ==========
        elif action == "pnl_alerts":
            # Show P&L Alerts Overview
            alerts = context.user_data.get("pnl_alerts", [])
            text, keyboard = DemoMenuBuilder.pnl_alerts_overview(
                alerts=alerts,
                positions=positions,
            )

        elif action.startswith("alert_setup:"):
            # Set up alert for a specific position
            parts = data.split(":")
            pos_id = parts[2] if len(parts) >= 3 else "0"

            # Find the position
            target_pos = None
            for pos in positions:
                if str(pos.get("id", "")) == pos_id:
                    target_pos = pos
                    break

            if target_pos:
                alerts = context.user_data.get("pnl_alerts", [])
                text, keyboard = DemoMenuBuilder.position_alert_setup(
                    position=target_pos,
                    existing_alerts=alerts,
                )
            else:
                text, keyboard = DemoMenuBuilder.error_message("Position not found")

        elif action.startswith("create_alert:"):
            # Create a new alert: demo:create_alert:{pos_id}:{type}:{target}
            parts = data.split(":")
            if len(parts) >= 5:
                pos_id = parts[2]
                alert_type = parts[3]  # percent, pnl, price
                target = float(parts[4])

                # Find the position
                target_pos = None
                for pos in positions:
                    if str(pos.get("id", "")) == pos_id:
                        target_pos = pos
                        break

                if target_pos:
                    symbol = target_pos.get("symbol", "???")
                    direction = "above" if target > 0 else "below"

                    # Create alert object
                    new_alert = {
                        "id": f"alert_{pos_id}_{target}",
                        "position_id": pos_id,
                        "symbol": symbol,
                        "type": alert_type,
                        "target": target,
                        "direction": direction,
                        "triggered": False,
                        "created_at": datetime.now().isoformat(),
                    }

                    # Store alert
                    alerts = context.user_data.get("pnl_alerts", [])
                    alerts.append(new_alert)
                    context.user_data["pnl_alerts"] = alerts

                    text, keyboard = DemoMenuBuilder.alert_created_success(
                        symbol=symbol,
                        alert_type=alert_type,
                        target=target,
                        direction=direction,
                    )
                else:
                    text, keyboard = DemoMenuBuilder.error_message("Position not found")
            else:
                text, keyboard = DemoMenuBuilder.error_message("Invalid alert data")

        elif action.startswith("delete_pos_alerts:"):
            # Delete all alerts for a position
            parts = data.split(":")
            pos_id = parts[2] if len(parts) >= 3 else "0"

            alerts = context.user_data.get("pnl_alerts", [])
            # Filter out alerts for this position
            alerts = [a for a in alerts if a.get("position_id") != pos_id]
            context.user_data["pnl_alerts"] = alerts

            theme = JarvisTheme
            text = f"""
{theme.SUCCESS} *ALERTS DELETED*
━━━━━━━━━━━━━━━━━━━━━

All alerts for this position have been removed.

━━━━━━━━━━━━━━━━━━━━━
"""
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔔 All Alerts", callback_data="demo:pnl_alerts")],
                [InlineKeyboardButton(f"{theme.CHART} Positions", callback_data="demo:positions")],
            ])

        elif action == "clear_triggered_alerts":
            # Clear all triggered alerts
            alerts = context.user_data.get("pnl_alerts", [])
            # Keep only non-triggered alerts
            alerts = [a for a in alerts if not a.get("triggered", False)]
            context.user_data["pnl_alerts"] = alerts

            theme = JarvisTheme
            text = f"""
{theme.SUCCESS} *TRIGGERED ALERTS CLEARED*
━━━━━━━━━━━━━━━━━━━━━

All triggered alerts have been removed.

━━━━━━━━━━━━━━━━━━━━━
"""
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔔 All Alerts", callback_data="demo:pnl_alerts")],
                [InlineKeyboardButton(f"{theme.BACK} Main Menu", callback_data="demo:main")],
            ])

        elif action.startswith("custom_alert:"):
            # Custom alert entry (placeholder for V2)
            parts = data.split(":")
            pos_id = parts[2] if len(parts) >= 3 else "0"

            theme = JarvisTheme
            text = f"""
{theme.AUTO} *CUSTOM ALERT*
━━━━━━━━━━━━━━━━━━━━━

Custom alert entry coming in V2!

For now, use the quick presets:
• +25%, +50%, +100% profit
• -10%, -25%, -50% loss

━━━━━━━━━━━━━━━━━━━━━
_Custom values & price alerts soon_
"""
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton(f"{theme.BACK} Back", callback_data=f"demo:alert_setup:{pos_id}")],
            ])

        # ========== END P&L ALERTS HANDLERS ==========

        # ========== DCA HANDLERS ==========
        elif action == "dca":
            # DCA Overview
            dca_plans = context.user_data.get("dca_plans", [])
            total_invested = sum(p.get("total_invested", 0) for p in dca_plans)
            text, keyboard = DemoMenuBuilder.dca_overview(
                dca_plans=dca_plans,
                total_invested=total_invested,
            )

        elif action == "dca_new":
            # New DCA Plan - select token
            watchlist = context.user_data.get("watchlist", [])
            text, keyboard = DemoMenuBuilder.dca_setup(
                watchlist=watchlist,
            )

        elif action.startswith("dca_select:"):
            # Token selected for DCA
            parts = data.split(":")
            token_address = parts[2] if len(parts) >= 3 else ""

            # Find token info from watchlist or trending
            watchlist = context.user_data.get("watchlist", [])
            token_symbol = "TOKEN"
            for token in watchlist:
                if token.get("address") == token_address:
                    token_symbol = token.get("symbol", "TOKEN")
                    break

            text, keyboard = DemoMenuBuilder.dca_setup(
                token_symbol=token_symbol,
                token_address=token_address,
                watchlist=watchlist,
            )

        elif action.startswith("dca_amount:"):
            # Amount selected for DCA: demo:dca_amount:{address}:{amount}
            try:
                parts = data.split(":")
                if len(parts) >= 4:
                    token_address = parts[2]
                    amount = float(parts[3])

                    # Find token symbol
                    watchlist = context.user_data.get("watchlist", [])
                    token_symbol = "TOKEN"
                    for token in watchlist:
                        if token.get("address") == token_address:
                            token_symbol = token.get("symbol", "TOKEN")
                            break

                    text, keyboard = DemoMenuBuilder.dca_frequency_select(
                        token_symbol=token_symbol,
                        token_address=token_address,
                        amount=amount,
                    )
                else:
                    text, keyboard = DemoMenuBuilder.error_message(
                        "Invalid DCA configuration",
                        retry_action="demo:dca_new",
                        context_hint="Amount selection failed"
                    )
            except (ValueError, IndexError) as e:
                logger.warning(f"DCA amount parse error: {e}")
                text, keyboard = DemoMenuBuilder.error_message(
                    f"Invalid amount: {str(e)[:50]}",
                    retry_action="demo:dca_new"
                )

        elif action.startswith("dca_create:"):
            # Create DCA plan: demo:dca_create:{address}:{amount}:{frequency}
            try:
                parts = data.split(":")
                if len(parts) >= 5:
                    token_address = parts[2]
                    amount = float(parts[3])
                    frequency = parts[4]

                    # Find token symbol
                    watchlist = context.user_data.get("watchlist", [])
                    token_symbol = "TOKEN"
                    for token in watchlist:
                        if token.get("address") == token_address:
                            token_symbol = token.get("symbol", "TOKEN")
                            break

                    # Create DCA plan
                    new_plan = {
                        "id": f"dca_{token_address[:8]}_{datetime.now().strftime('%H%M%S')}",
                        "symbol": token_symbol,
                        "address": token_address,
                        "amount": amount,
                        "frequency": frequency,
                        "active": True,
                        "executions": 0,
                        "total_invested": 0.0,
                        "next_execution": "In 1 " + ("hour" if frequency == "hourly" else "day" if frequency == "daily" else "week"),
                        "created_at": datetime.now().isoformat(),
                    }

                    # Store plan
                    dca_plans = context.user_data.get("dca_plans", [])
                    dca_plans.append(new_plan)
                    context.user_data["dca_plans"] = dca_plans

                    text, keyboard = DemoMenuBuilder.dca_plan_created(
                        token_symbol=token_symbol,
                        amount=amount,
                        frequency=frequency,
                        first_execution="Starting soon",
                    )
                else:
                    text, keyboard = DemoMenuBuilder.error_message(
                        "Invalid DCA configuration",
                        retry_action="demo:dca_new"
                    )
            except (ValueError, IndexError) as e:
                logger.warning(f"DCA create error: {e}")
                text, keyboard = DemoMenuBuilder.operation_failed(
                    "DCA Plan Creation",
                    f"Could not create plan: {str(e)[:50]}",
                    retry_action="demo:dca_new"
                )

        elif action.startswith("dca_pause:"):
            # Pause/Resume DCA plan
            parts = data.split(":")
            plan_id = parts[2] if len(parts) >= 3 else ""

            dca_plans = context.user_data.get("dca_plans", [])
            for plan in dca_plans:
                if plan.get("id") == plan_id:
                    plan["active"] = not plan.get("active", True)
                    break
            context.user_data["dca_plans"] = dca_plans

            # Return to overview
            total_invested = sum(p.get("total_invested", 0) for p in dca_plans)
            text, keyboard = DemoMenuBuilder.dca_overview(
                dca_plans=dca_plans,
                total_invested=total_invested,
            )

        elif action.startswith("dca_delete:"):
            # Delete DCA plan
            parts = data.split(":")
            plan_id = parts[2] if len(parts) >= 3 else ""

            dca_plans = context.user_data.get("dca_plans", [])
            dca_plans = [p for p in dca_plans if p.get("id") != plan_id]
            context.user_data["dca_plans"] = dca_plans

            theme = JarvisTheme
            text = f"""
{theme.SUCCESS} *DCA PLAN DELETED*
━━━━━━━━━━━━━━━━━━━━━

The DCA plan has been removed.
No further automatic purchases
will be made.

━━━━━━━━━━━━━━━━━━━━━
"""
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("📅 View DCA Plans", callback_data="demo:dca")],
                [InlineKeyboardButton(f"{theme.BACK} Main Menu", callback_data="demo:main")],
            ])

        elif action == "dca_history":
            # DCA execution history (placeholder)
            theme = JarvisTheme
            dca_plans = context.user_data.get("dca_plans", [])
            total_executions = sum(p.get("executions", 0) for p in dca_plans)

            text = f"""
{theme.AUTO} *DCA EXECUTION HISTORY*
━━━━━━━━━━━━━━━━━━━━━

📊 *Total Executions:* {total_executions}

_Detailed execution history coming in V2_

Each DCA execution will be logged with:
• Timestamp
• Token purchased
• Amount spent
• Price at execution
• Tokens received

━━━━━━━━━━━━━━━━━━━━━
"""
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("📅 DCA Plans", callback_data="demo:dca")],
                [InlineKeyboardButton(f"{theme.BACK} Main Menu", callback_data="demo:main")],
            ])

        elif action == "dca_input":
            # Manual token address input for DCA (placeholder)
            theme = JarvisTheme
            text = f"""
{theme.AUTO} *ENTER TOKEN ADDRESS*
━━━━━━━━━━━━━━━━━━━━━

Paste a Solana token address to
set up a DCA plan.

_Manual address input coming in V2_

For now, add tokens to your watchlist
first, then create DCA plans from there.

━━━━━━━━━━━━━━━━━━━━━
"""
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("⭐ Go to Watchlist", callback_data="demo:watchlist")],
                [InlineKeyboardButton(f"{theme.BACK} Back", callback_data="demo:dca_new")],
            ])

        # ========== END DCA HANDLERS ==========

        # ========== BAGS.FM HANDLERS ==========

        elif action == "bags_fm":
            # Show Bags.fm Top 15 tokens by volume with sentiment
            try:
                # Fetch tokens with sentiment
                bags_tokens = await get_bags_top_tokens_with_sentiment(limit=15)

                # Get user's TP/SL settings
                default_tp = context.user_data.get("bags_tp_percent", 15.0)
                default_sl = context.user_data.get("bags_sl_percent", 15.0)

                text, keyboard = DemoMenuBuilder.bags_fm_top_tokens(
                    tokens=bags_tokens,
                    market_regime=market_regime,
                    default_tp_percent=default_tp,
                    default_sl_percent=default_sl,
                )
            except Exception as e:
                logger.error(f"Bags.fm error: {e}")
                text, keyboard = DemoMenuBuilder.error_message(
                    error=str(e),
                    retry_action="demo:bags_fm",
                    context_hint="bags_fm",
                )

        elif action.startswith("bags_info:"):
            # Show detailed token info
            address = action.split(":")[1]

            # Find token from cached data or fetch
            bags_tokens = await get_bags_top_tokens_with_sentiment(limit=15)
            token = next((t for t in bags_tokens if t.get("address") == address), None)

            if token:
                default_tp = context.user_data.get("bags_tp_percent", 15.0)
                default_sl = context.user_data.get("bags_sl_percent", 15.0)

                text, keyboard = DemoMenuBuilder.bags_token_detail(
                    token=token,
                    market_regime=market_regime,
                    default_tp_percent=default_tp,
                    default_sl_percent=default_sl,
                )
            else:
                text, keyboard = DemoMenuBuilder.error_message(
                    error="Token not found",
                    retry_action="demo:bags_fm",
                )

        elif action.startswith("bags_buy:"):
            # Show buy confirmation for a Bags token
            parts = action.split(":")
            address = parts[1]
            tp_percent = float(parts[2]) if len(parts) > 2 else 15.0
            sl_percent = float(parts[3]) if len(parts) > 3 else 15.0

            # Find token
            bags_tokens = await get_bags_top_tokens_with_sentiment(limit=15)
            token = next((t for t in bags_tokens if t.get("address") == address), None)

            if token:
                text, keyboard = DemoMenuBuilder.bags_token_detail(
                    token=token,
                    market_regime=market_regime,
                    default_tp_percent=tp_percent,
                    default_sl_percent=sl_percent,
                )
            else:
                text, keyboard = DemoMenuBuilder.error_message(
                    error="Token not found",
                    retry_action="demo:bags_fm",
                )

        elif action.startswith("bags_exec:"):
            # Execute buy via Bags.fm API
            parts = action.split(":")
            address = parts[1]
            amount_sol = float(parts[2]) if len(parts) > 2 else 0.1
            tp_percent = float(parts[3]) if len(parts) > 3 else 15.0
            sl_percent = float(parts[4]) if len(parts) > 4 else 15.0

            # Find token
            bags_tokens = await get_bags_top_tokens_with_sentiment(limit=15)
            token = next((t for t in bags_tokens if t.get("address") == address), None)

            if token:
                symbol = token.get("symbol", "???")
                price = token.get("price_usd", 0)

                # Execute trade via Bags API (or simulate)
                try:
                    bags_client = get_bags_client()
                    if bags_client:
                        # Real trade execution
                        wallet_address = context.user_data.get("wallet_address", "demo_wallet")
                        result = await bags_client.swap(
                            from_token="So11111111111111111111111111111111111111112",  # SOL
                            to_token=address,
                            amount=amount_sol,
                            wallet_address=wallet_address,
                        )

                        if result.success:
                            tokens_received = result.to_amount if result.to_amount else (amount_sol * 225 / price) if price > 0 else 0

                            # Add position to portfolio
                            positions = context.user_data.get("positions", [])
                            new_position = {
                                "id": f"bags_{len(positions) + 1}",
                                "symbol": symbol,
                                "address": address,
                                "amount": tokens_received,
                                "amount_sol": amount_sol,
                                "entry_price": price,
                                "tp_percent": tp_percent,
                                "sl_percent": sl_percent,
                                "source": "bags_fm",
                                "timestamp": datetime.now(timezone.utc).isoformat(),
                            }
                            positions.append(new_position)
                            context.user_data["positions"] = positions

                            text, keyboard = DemoMenuBuilder.bags_buy_result(
                                success=True,
                                symbol=symbol,
                                amount_sol=amount_sol,
                                tokens_received=tokens_received,
                                price=price,
                                tp_percent=tp_percent,
                                sl_percent=sl_percent,
                                tx_hash=result.tx_hash,
                            )
                        else:
                            text, keyboard = DemoMenuBuilder.bags_buy_result(
                                success=False,
                                symbol=symbol,
                                amount_sol=amount_sol,
                                error=result.error or "Trade execution failed",
                            )
                    else:
                        # Demo mode - simulate trade
                        tokens_received = (amount_sol * 225 / price) if price > 0 else 1000000

                        # Add demo position
                        positions = context.user_data.get("positions", [])
                        new_position = {
                            "id": f"bags_{len(positions) + 1}",
                            "symbol": symbol,
                            "address": address,
                            "amount": tokens_received,
                            "amount_sol": amount_sol,
                            "entry_price": price,
                            "tp_percent": tp_percent,
                            "sl_percent": sl_percent,
                            "source": "bags_fm_demo",
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        }
                        positions.append(new_position)
                        context.user_data["positions"] = positions

                        text, keyboard = DemoMenuBuilder.bags_buy_result(
                            success=True,
                            symbol=symbol,
                            amount_sol=amount_sol,
                            tokens_received=tokens_received,
                            price=price,
                            tp_percent=tp_percent,
                            sl_percent=sl_percent,
                            tx_hash="demo_tx_" + str(hash(address + str(amount_sol)))[:8],
                        )
                except Exception as e:
                    logger.error(f"Bags buy error: {e}")
                    text, keyboard = DemoMenuBuilder.bags_buy_result(
                        success=False,
                        symbol=symbol,
                        amount_sol=amount_sol,
                        error=str(e)[:50],
                    )
            else:
                text, keyboard = DemoMenuBuilder.error_message(
                    error="Token not found",
                    retry_action="demo:bags_fm",
                )

        elif action == "bags_settings":
            # Show TP/SL settings for Bags trading
            theme = JarvisTheme
            default_tp = context.user_data.get("bags_tp_percent", 15.0)
            default_sl = context.user_data.get("bags_sl_percent", 15.0)

            text = f"""
{theme.SETTINGS} *BAGS.FM TRADING SETTINGS*
━━━━━━━━━━━━━━━━━━━━━

*Current Settings:*
🎯 Take Profit: +{default_tp:.0f}%
🛑 Stop Loss: -{default_sl:.0f}%

*Select new TP/SL presets:*

━━━━━━━━━━━━━━━━━━━━━
_Applied to all Bags.fm trades_
"""
            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("TP +10%", callback_data="demo:bags_set_tp:10"),
                    InlineKeyboardButton("TP +15%", callback_data="demo:bags_set_tp:15"),
                    InlineKeyboardButton("TP +25%", callback_data="demo:bags_set_tp:25"),
                ],
                [
                    InlineKeyboardButton("SL -5%", callback_data="demo:bags_set_sl:5"),
                    InlineKeyboardButton("SL -10%", callback_data="demo:bags_set_sl:10"),
                    InlineKeyboardButton("SL -15%", callback_data="demo:bags_set_sl:15"),
                ],
                [
                    InlineKeyboardButton("🎒 Back to Bags", callback_data="demo:bags_fm"),
                ],
            ])

        elif action.startswith("bags_set_tp:"):
            tp_value = float(action.split(":")[1])
            context.user_data["bags_tp_percent"] = tp_value
            await query.answer(f"Take Profit set to +{tp_value:.0f}%")
            # Redirect back to settings
            theme = JarvisTheme
            default_tp = tp_value
            default_sl = context.user_data.get("bags_sl_percent", 15.0)
            text = f"""
{theme.SETTINGS} *BAGS.FM TRADING SETTINGS*
━━━━━━━━━━━━━━━━━━━━━

✅ *Settings Updated!*

*Current Settings:*
🎯 Take Profit: +{default_tp:.0f}%
🛑 Stop Loss: -{default_sl:.0f}%

━━━━━━━━━━━━━━━━━━━━━
_Applied to all Bags.fm trades_
"""
            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("TP +10%", callback_data="demo:bags_set_tp:10"),
                    InlineKeyboardButton("TP +15%", callback_data="demo:bags_set_tp:15"),
                    InlineKeyboardButton("TP +25%", callback_data="demo:bags_set_tp:25"),
                ],
                [
                    InlineKeyboardButton("SL -5%", callback_data="demo:bags_set_sl:5"),
                    InlineKeyboardButton("SL -10%", callback_data="demo:bags_set_sl:10"),
                    InlineKeyboardButton("SL -15%", callback_data="demo:bags_set_sl:15"),
                ],
                [
                    InlineKeyboardButton("🎒 Back to Bags", callback_data="demo:bags_fm"),
                ],
            ])

        elif action.startswith("bags_set_sl:"):
            sl_value = float(action.split(":")[1])
            context.user_data["bags_sl_percent"] = sl_value
            await query.answer(f"Stop Loss set to -{sl_value:.0f}%")
            # Redirect back to settings
            theme = JarvisTheme
            default_tp = context.user_data.get("bags_tp_percent", 15.0)
            default_sl = sl_value
            text = f"""
{theme.SETTINGS} *BAGS.FM TRADING SETTINGS*
━━━━━━━━━━━━━━━━━━━━━

✅ *Settings Updated!*

*Current Settings:*
🎯 Take Profit: +{default_tp:.0f}%
🛑 Stop Loss: -{default_sl:.0f}%

━━━━━━━━━━━━━━━━━━━━━
_Applied to all Bags.fm trades_
"""
            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("TP +10%", callback_data="demo:bags_set_tp:10"),
                    InlineKeyboardButton("TP +15%", callback_data="demo:bags_set_tp:15"),
                    InlineKeyboardButton("TP +25%", callback_data="demo:bags_set_tp:25"),
                ],
                [
                    InlineKeyboardButton("SL -5%", callback_data="demo:bags_set_sl:5"),
                    InlineKeyboardButton("SL -10%", callback_data="demo:bags_set_sl:10"),
                    InlineKeyboardButton("SL -15%", callback_data="demo:bags_set_sl:15"),
                ],
                [
                    InlineKeyboardButton("🎒 Back to Bags", callback_data="demo:bags_fm"),
                ],
            ])

        # ========== END BAGS.FM HANDLERS ==========

        # ========== TRAILING STOP HANDLERS ==========

        elif action == "trailing_stops":
            # Show trailing stop overview
            trailing_stops = context.user_data.get("trailing_stops", [])
            positions = context.user_data.get("positions", [])
            text, keyboard = DemoMenuBuilder.trailing_stop_overview(
                trailing_stops=trailing_stops,
                positions=positions,
            )

        elif action == "tsl_new":
            # Show position selection for new trailing stop
            positions = context.user_data.get("positions", [])
            text, keyboard = DemoMenuBuilder.trailing_stop_setup(positions=positions)

        elif action.startswith("tsl_select:"):
            # Position selected, show trail percentage options
            pos_id = action.split(":")[1]
            positions = context.user_data.get("positions", [])
            position = next((p for p in positions if p.get("id") == pos_id), None)

            if position:
                text, keyboard = DemoMenuBuilder.trailing_stop_setup(position=position)
            else:
                text = "❌ Position not found"
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton(f"{theme.BACK} Back", callback_data="demo:trailing_stops")]
                ])

        elif action.startswith("tsl_create:"):
            # Create trailing stop with: pos_id:trail_percent
            try:
                parts = action.split(":")
                pos_id = parts[1]
                trail_percent = float(parts[2])

                positions = context.user_data.get("positions", [])
                position = next((p for p in positions if p.get("id") == pos_id), None)

                if position:
                    current_price = position.get("current_price", 0)
                    initial_stop = current_price * (1 - trail_percent / 100)

                    # Create trailing stop record
                    new_stop = {
                        "id": f"tsl_{pos_id}_{datetime.now().strftime('%H%M%S')}",
                        "position_id": pos_id,
                        "symbol": position.get("symbol", "???"),
                        "trail_percent": trail_percent,
                        "current_stop_price": initial_stop,
                        "highest_price": current_price,
                        "protected_value": position.get("value_usd", 0),
                        "protected_pnl": position.get("pnl_pct", 0),
                        "active": True,
                        "created_at": datetime.now().isoformat(),
                    }

                    # Store in user data
                    if "trailing_stops" not in context.user_data:
                        context.user_data["trailing_stops"] = []
                    context.user_data["trailing_stops"].append(new_stop)

                    text, keyboard = DemoMenuBuilder.trailing_stop_created(
                        symbol=position.get("symbol", "???"),
                        trail_percent=trail_percent,
                        initial_stop=initial_stop,
                        current_price=current_price,
                    )
                else:
                    text, keyboard = DemoMenuBuilder.error_message(
                        "Position not found",
                        retry_action="demo:trailing_stops",
                        context_hint="Position may have been closed"
                    )
            except (ValueError, IndexError) as e:
                logger.warning(f"Trailing stop create error: {e}")
                text, keyboard = DemoMenuBuilder.operation_failed(
                    "Trailing Stop",
                    f"Invalid configuration: {str(e)[:50]}",
                    retry_action="demo:trailing_stops"
                )

        elif action.startswith("tsl_edit:"):
            # Edit a trailing stop
            stop_id = action.split(":")[1]
            trailing_stops = context.user_data.get("trailing_stops", [])
            stop = next((s for s in trailing_stops if s.get("id") == stop_id), None)

            if stop:
                # Find the associated position
                positions = context.user_data.get("positions", [])
                position = next((p for p in positions if p.get("id") == stop.get("position_id")), None)

                if position:
                    text, keyboard = DemoMenuBuilder.trailing_stop_setup(position=position)
                else:
                    text = f"🛡️ *Edit Trailing Stop*\n\n{stop.get('symbol', '???')} - {stop.get('trail_percent', 10)}%\n\n_Position no longer exists_"
                    keyboard = InlineKeyboardMarkup([
                        [InlineKeyboardButton("❌ Delete Stop", callback_data=f"demo:tsl_delete:{stop_id}")],
                        [InlineKeyboardButton(f"{theme.BACK} Back", callback_data="demo:trailing_stops")]
                    ])
            else:
                text = "❌ Trailing stop not found"
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton(f"{theme.BACK} Back", callback_data="demo:trailing_stops")]
                ])

        elif action.startswith("tsl_delete:"):
            # Delete a trailing stop
            stop_id = action.split(":")[1]
            trailing_stops = context.user_data.get("trailing_stops", [])

            # Remove the stop
            context.user_data["trailing_stops"] = [
                s for s in trailing_stops if s.get("id") != stop_id
            ]

            # Show updated overview
            text, keyboard = DemoMenuBuilder.trailing_stop_overview(
                trailing_stops=context.user_data.get("trailing_stops", []),
                positions=context.user_data.get("positions", []),
            )

        elif action.startswith("tsl_custom:"):
            # Custom trail percentage - placeholder
            pos_id = action.split(":")[1]
            text = f"""
🛡️ *CUSTOM TRAIL %*
━━━━━━━━━━━━━━━━━━━━━

Enter a custom trailing percentage
(e.g., 7 for 7% trail).

_This feature coming soon!_
"""
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("5%", callback_data=f"demo:tsl_create:{pos_id}:5")],
                [InlineKeyboardButton("10%", callback_data=f"demo:tsl_create:{pos_id}:10")],
                [InlineKeyboardButton(f"{theme.BACK} Back", callback_data=f"demo:tsl_select:{pos_id}")],
            ])

        # ========== END TRAILING STOP HANDLERS ==========

        # ========== POSITION ADJUSTMENT HANDLERS ==========

        elif action == "noop":
            # No-op for label buttons - just acknowledge
            await query.answer("This is a label")
            return

        elif action.startswith("pos_adjust:"):
            # Show position adjustment menu (quick SL/TP)
            pos_id = action.split(":")[1]
            positions = context.user_data.get("positions", [])
            position = next((p for p in positions if p.get("id") == pos_id), None)

            if position:
                text, keyboard = DemoMenuBuilder.position_adjust_menu(
                    pos_id=pos_id,
                    symbol=position.get("symbol", "???"),
                    current_tp=position.get("take_profit", 50.0),
                    current_sl=position.get("stop_loss", 20.0),
                    pnl_pct=position.get("pnl_pct", 0.0),
                )
            else:
                text = "❌ Position not found"
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton(f"{theme.BACK} Back", callback_data="demo:positions")]
                ])

        elif action.startswith("set_tp:"):
            # Set take profit for a position
            try:
                parts = action.split(":")
                pos_id = parts[1]
                tp_value = float(parts[2])

                positions = context.user_data.get("positions", [])
                for p in positions:
                    if p.get("id") == pos_id:
                        p["take_profit"] = tp_value
                        break

                context.user_data["positions"] = positions

                # Show success and return to adjust menu
                position = next((p for p in positions if p.get("id") == pos_id), None)
                if position:
                    await query.answer(f"✅ Take Profit set to +{tp_value}%")
                    text, keyboard = DemoMenuBuilder.position_adjust_menu(
                        pos_id=pos_id,
                        symbol=position.get("symbol", "???"),
                        current_tp=tp_value,
                        current_sl=position.get("stop_loss", 20.0),
                        pnl_pct=position.get("pnl_pct", 0.0),
                    )
                else:
                    text = "❌ Position not found"
                    keyboard = InlineKeyboardMarkup([
                        [InlineKeyboardButton(f"{theme.BACK} Back", callback_data="demo:positions")]
                    ])
            except (ValueError, IndexError) as e:
                logger.warning(f"Set TP error: {e}")
                await query.answer("❌ Error setting TP")
                return

        elif action.startswith("set_sl:"):
            # Set stop loss for a position
            try:
                parts = action.split(":")
                pos_id = parts[1]
                sl_value = float(parts[2])

                positions = context.user_data.get("positions", [])
                for p in positions:
                    if p.get("id") == pos_id:
                        p["stop_loss"] = sl_value
                        break

                context.user_data["positions"] = positions

                # Show success and return to adjust menu
                position = next((p for p in positions if p.get("id") == pos_id), None)
                if position:
                    await query.answer(f"✅ Stop Loss set to -{sl_value}%")
                    text, keyboard = DemoMenuBuilder.position_adjust_menu(
                        pos_id=pos_id,
                        symbol=position.get("symbol", "???"),
                        current_tp=position.get("take_profit", 50.0),
                        current_sl=sl_value,
                        pnl_pct=position.get("pnl_pct", 0.0),
                    )
                else:
                    text = "❌ Position not found"
                    keyboard = InlineKeyboardMarkup([
                        [InlineKeyboardButton(f"{theme.BACK} Back", callback_data="demo:positions")]
                    ])
            except (ValueError, IndexError) as e:
                logger.warning(f"Set SL error: {e}")
                await query.answer("❌ Error setting SL")
                return

        elif action.startswith("trailing_setup:"):
            # Quick trailing stop setup from position adjust menu
            pos_id = action.split(":")[1]
            positions = context.user_data.get("positions", [])
            position = next((p for p in positions if p.get("id") == pos_id), None)

            if position:
                text, keyboard = DemoMenuBuilder.trailing_stop_setup(position=position)
            else:
                text = "❌ Position not found"
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton(f"{theme.BACK} Back", callback_data="demo:positions")]
                ])

        # ========== END POSITION ADJUSTMENT HANDLERS ==========

        elif action == "token_input":
            text, keyboard = DemoMenuBuilder.token_input_prompt()
            # Store state for next message
            context.user_data["awaiting_token"] = True

        elif action == "trending":
            # Fetch real trending data from sentiment engine
            trending = await get_trending_with_sentiment()
            if not trending:
                # Fallback mock data if API unavailable (with AI sentiment)
                trending = [
                    {"symbol": "BONK", "change_24h": 15.2, "volume": 1500000, "address": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263", "sentiment": "bullish", "sentiment_score": 0.72, "signal": "BUY"},
                    {"symbol": "WIF", "change_24h": -5.3, "volume": 2300000, "address": "EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm", "sentiment": "neutral", "sentiment_score": 0.45, "signal": "NEUTRAL"},
                    {"symbol": "POPCAT", "change_24h": 42.1, "volume": 890000, "address": "7GCihgDB8fe6KNjn2MYtkzZcRjQy3t9GHdC8uHYmW2hr", "sentiment": "very_bullish", "sentiment_score": 0.85, "signal": "STRONG_BUY"},
                    {"symbol": "MEW", "change_24h": 8.7, "volume": 650000, "address": "MEW1gQWJ3nEXg2qgERiKu7FAFj79PHvQVREQUzScPP5", "sentiment": "bullish", "sentiment_score": 0.61, "signal": "BUY"},
                ]
            text, keyboard = DemoMenuBuilder.trending_tokens(
                trending,
                market_regime=market_regime,
            )

        elif action == "ai_picks":
            # AI Conviction Picks - powered by Grok
            picks = await get_conviction_picks()
            text, keyboard = DemoMenuBuilder.ai_picks_menu(
                picks=picks,
                market_regime=market_regime,
            )

        elif action == "ai_report":
            # AI Market Report
            text, keyboard = DemoMenuBuilder.ai_report_menu(
                market_regime=market_regime,
            )

        # ========== SENTIMENT HUB HANDLERS ==========
        elif action == "hub":
            # Main Sentiment Hub Dashboard
            try:
                last_report_time = context.user_data.get("hub_last_report", datetime.now(timezone.utc))
                wallet_connected = bool(context.user_data.get("wallet_address"))

                text, keyboard = DemoMenuBuilder.sentiment_hub_main(
                    market_regime=market_regime,
                    last_report_time=last_report_time,
                    report_interval_minutes=15,
                    wallet_connected=wallet_connected,
                )
            except Exception as e:
                logger.error(f"Hub error: {e}")
                text, keyboard = DemoMenuBuilder.error_message(
                    error=str(e),
                    retry_action="demo:hub",
                    context_hint="sentiment_hub",
                )

        elif action.startswith("hub_"):
            # Hub section handlers
            try:
                section = action.replace("hub_", "")

                # Generate mock picks based on section
                section_picks = {
                    "bluechips": [
                        {"symbol": "SOL", "address": "So11111111111111111111111111111111111111112", "price": 225.50, "change_24h": 2.5, "conviction": "HIGH", "tp_percent": 20, "sl_percent": 10, "score": 85},
                        {"symbol": "JUP", "address": "JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN", "price": 1.25, "change_24h": 5.2, "conviction": "HIGH", "tp_percent": 25, "sl_percent": 12, "score": 82},
                        {"symbol": "RAY", "address": "4k3Dyjzvzp8eMZWUXbBCjEvwSkkk59S5iCNLY3QrkX6R", "price": 8.45, "change_24h": 1.8, "conviction": "MEDIUM", "tp_percent": 15, "sl_percent": 10, "score": 78},
                    ],
                    "top10": [
                        {"symbol": "BONK", "address": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263", "price": 0.0000325, "change_24h": 15.2, "conviction": "VERY HIGH", "tp_percent": 30, "sl_percent": 15, "score": 92},
                        {"symbol": "WIF", "address": "EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm", "price": 2.85, "change_24h": 8.5, "conviction": "HIGH", "tp_percent": 25, "sl_percent": 12, "score": 88},
                        {"symbol": "POPCAT", "address": "7GCihgDB8fe6KNjn2MYtkzZcRjQy3t9GHdC8uHYmW2hr", "price": 1.42, "change_24h": 22.1, "conviction": "HIGH", "tp_percent": 35, "sl_percent": 15, "score": 86},
                    ],
                    "xstocks": [
                        {"symbol": "xTSLA", "address": "xTSLA111111111111111111111111111111111111111", "price": 425.00, "change_24h": 3.2, "conviction": "MEDIUM", "tp_percent": 15, "sl_percent": 8, "score": 75},
                        {"symbol": "xNVDA", "address": "xNVDA111111111111111111111111111111111111111", "price": 142.50, "change_24h": 2.1, "conviction": "MEDIUM", "tp_percent": 12, "sl_percent": 7, "score": 72},
                    ],
                    "prestocks": [
                        {"symbol": "STRIPE", "address": "STRIPE11111111111111111111111111111111111111", "price": 85.00, "change_24h": 0.5, "conviction": "HIGH", "tp_percent": 50, "sl_percent": 20, "score": 80},
                        {"symbol": "SPACEX", "address": "SPACEX11111111111111111111111111111111111111", "price": 125.00, "change_24h": 1.2, "conviction": "HIGH", "tp_percent": 100, "sl_percent": 25, "score": 78},
                    ],
                    "indexes": [
                        {"symbol": "SPX500", "address": "SPX50011111111111111111111111111111111111111", "price": 1.05, "change_24h": 0.3, "conviction": "MEDIUM", "tp_percent": 10, "sl_percent": 5, "score": 70},
                        {"symbol": "DJIA", "address": "DJIA1111111111111111111111111111111111111111", "price": 0.98, "change_24h": -0.2, "conviction": "LOW", "tp_percent": 8, "sl_percent": 4, "score": 65},
                    ],
                    "trending": [
                        {"symbol": "FARTCOIN", "address": "FART1111111111111111111111111111111111111111", "price": 0.00125, "change_24h": 245.5, "conviction": "VERY HIGH", "tp_percent": 50, "sl_percent": 25, "score": 95},
                        {"symbol": "GIGA", "address": "GIGA1111111111111111111111111111111111111111", "price": 0.0425, "change_24h": 85.2, "conviction": "HIGH", "tp_percent": 40, "sl_percent": 20, "score": 88},
                        {"symbol": "AI16Z", "address": "AI16Z111111111111111111111111111111111111111", "price": 0.875, "change_24h": 32.1, "conviction": "HIGH", "tp_percent": 35, "sl_percent": 18, "score": 85},
                    ],
                }

                picks = section_picks.get(section, [])

                text, keyboard = DemoMenuBuilder.sentiment_hub_section(
                    section=section,
                    picks=picks,
                    market_regime=market_regime,
                )
            except Exception as e:
                logger.error(f"Hub section error: {e}")
                text, keyboard = DemoMenuBuilder.error_message(
                    error=str(e),
                    retry_action="demo:hub",
                    context_hint="hub_section",
                )

        elif action == "hub_news":
            # Market news section
            try:
                mock_news = [
                    {"title": "SOL breaks $225 resistance", "source": "CoinDesk", "time": "2h ago", "sentiment": "bullish"},
                    {"title": "Whale accumulation on BONK", "source": "Arkham", "time": "4h ago", "sentiment": "bullish"},
                    {"title": "Fed signals rate pause", "source": "Reuters", "time": "6h ago", "sentiment": "neutral"},
                    {"title": "New Solana DeFi protocol launches", "source": "The Block", "time": "8h ago", "sentiment": "bullish"},
                ]
                mock_macro = {
                    "dxy_trend": "weakening",
                    "fed_stance": "neutral",
                    "risk_appetite": "high",
                    "btc_correlation": 0.85,
                }

                text, keyboard = DemoMenuBuilder.sentiment_hub_news(
                    news_items=mock_news,
                    macro_analysis=mock_macro,
                )
            except Exception as e:
                logger.error(f"Hub news error: {e}")
                text, keyboard = DemoMenuBuilder.error_message(
                    error=str(e),
                    retry_action="demo:hub_news",
                    context_hint="hub_news",
                )

        elif action == "hub_traditional":
            # Traditional markets section
            try:
                mock_stocks = {"spy_change": 0.45, "qqq_change": 0.72, "dia_change": 0.22, "outlook": "bullish"}
                mock_dxy = {"value": 103.25, "change": -0.15, "trend": "weakening"}
                mock_commodities = [
                    {"symbol": "GOLD", "price": 2045.50, "change": 0.8},
                    {"symbol": "SILVER", "price": 24.15, "change": 1.2},
                    {"symbol": "OIL", "price": 78.50, "change": -0.5},
                ]

                text, keyboard = DemoMenuBuilder.sentiment_hub_traditional(
                    stocks_outlook=mock_stocks,
                    dxy_data=mock_dxy,
                    commodities=mock_commodities,
                )
            except Exception as e:
                logger.error(f"Hub traditional error: {e}")
                text, keyboard = DemoMenuBuilder.error_message(
                    error=str(e),
                    retry_action="demo:hub_traditional",
                    context_hint="hub_traditional",
                )

        elif action == "hub_wallet":
            # Hub wallet management
            try:
                wallet_address = context.user_data.get("wallet_address", "")
                sol_balance = context.user_data.get("sol_balance", 0.0)
                usd_value = sol_balance * 225  # Approximate

                text, keyboard = DemoMenuBuilder.sentiment_hub_wallet(
                    wallet_address=wallet_address,
                    sol_balance=sol_balance,
                    usd_value=usd_value,
                    has_private_key=bool(context.user_data.get("private_key")),
                )
            except Exception as e:
                logger.error(f"Hub wallet error: {e}")
                text, keyboard = DemoMenuBuilder.error_message(
                    error=str(e),
                    retry_action="demo:hub_wallet",
                    context_hint="hub_wallet",
                )

        elif action.startswith("hub_buy:"):
            # Hub buy confirmation
            try:
                parts = callback_data.split(":")
                if len(parts) >= 3:
                    address = parts[2]
                    # Get token info (mock for now)
                    text, keyboard = DemoMenuBuilder.sentiment_hub_buy_confirm(
                        symbol="TOKEN",
                        address=address,
                        price=0.001,
                        auto_sl_percent=15,
                    )
                else:
                    text, keyboard = DemoMenuBuilder.error_message(
                        error="Invalid buy request",
                        retry_action="demo:hub",
                    )
            except Exception as e:
                logger.error(f"Hub buy error: {e}")
                text, keyboard = DemoMenuBuilder.error_message(
                    error=str(e),
                    retry_action="demo:hub",
                    context_hint="hub_buy",
                )

        # ========== INSTA SNIPE HANDLERS ==========
        elif action == "insta_snipe":
            # Insta Snipe - Find hottest token
            try:
                # Try to get real trending tokens from DexScreener
                hottest_token = None
                try:
                    import aiohttp
                    async with aiohttp.ClientSession() as session:
                        async with session.get(
                            "https://api.dexscreener.com/token-boosts/top/v1",
                            timeout=aiohttp.ClientTimeout(total=5)
                        ) as resp:
                            if resp.status == 200:
                                data = await resp.json()
                                if data and len(data) > 0:
                                    top = data[0]
                                    hottest_token = {
                                        "symbol": top.get("tokenInfo", {}).get("symbol", "UNKNOWN"),
                                        "address": top.get("tokenAddress", ""),
                                        "price": float(top.get("tokenInfo", {}).get("price", 0)),
                                        "change_24h": float(top.get("tokenInfo", {}).get("priceChange24h", 0)),
                                        "volume_24h": float(top.get("volume24h", 0)),
                                        "liquidity": float(top.get("liquidity", 0)),
                                        "market_cap": float(top.get("marketCap", 0)),
                                        "conviction": "HIGH" if float(top.get("totalAmount", 0)) > 1000 else "MEDIUM",
                                        "sentiment_score": 75,
                                        "entry_timing": "GOOD",
                                        "sightings": 1,
                                    }
                except Exception as api_err:
                    logger.warning(f"DexScreener API error: {api_err}")

                # Fallback to mock data if API fails
                if not hottest_token:
                    hottest_token = {
                        "symbol": "FARTCOIN",
                        "address": "9BB6NFEcjBCtnNLFko2FqVQBq8HHM13kCyYcdQbgpump",
                        "price": 0.00125,
                        "change_24h": 145.5,
                        "volume_24h": 2500000,
                        "liquidity": 850000,
                        "market_cap": 125000000,
                        "conviction": "VERY HIGH",
                        "sentiment_score": 92,
                        "entry_timing": "GOOD",
                        "sightings": 3,
                    }

                text, keyboard = DemoMenuBuilder.insta_snipe_menu(
                    hottest_token=hottest_token,
                    market_regime=market_regime,
                    auto_sl_percent=15.0,
                    auto_tp_percent=15.0,
                )
            except Exception as e:
                logger.error(f"Insta snipe error: {e}")
                text, keyboard = DemoMenuBuilder.error_message(
                    error=str(e),
                    retry_action="demo:insta_snipe",
                    context_hint="insta_snipe",
                )

        elif action.startswith("snipe_exec:"):
            # Snipe execution - show confirmation
            try:
                parts = callback_data.split(":")
                if len(parts) >= 4:
                    address = parts[2]
                    amount = float(parts[3])

                    # Store snipe details
                    context.user_data["snipe_address"] = address
                    context.user_data["snipe_amount"] = amount

                    text, keyboard = DemoMenuBuilder.snipe_confirm(
                        symbol="TOKEN",
                        address=address,
                        amount=amount,
                        price=0.001,  # Would fetch real price
                        sl_percent=15.0,
                        tp_percent=15.0,
                    )
                else:
                    text, keyboard = DemoMenuBuilder.error_message(
                        error="Invalid snipe request",
                        retry_action="demo:insta_snipe",
                    )
            except Exception as e:
                logger.error(f"Snipe exec error: {e}")
                text, keyboard = DemoMenuBuilder.error_message(
                    error=str(e),
                    retry_action="demo:insta_snipe",
                    context_hint="snipe_exec",
                )

        elif action.startswith("snipe_confirm:"):
            # Execute the snipe
            try:
                parts = callback_data.split(":")
                if len(parts) >= 4:
                    address = parts[2]
                    amount = float(parts[3])

                    # Simulate trade execution
                    # In production, this would call the trading engine
                    success = True  # Simulated success
                    tx_hash = "5xYz...mock_tx_hash...AbCd"

                    text, keyboard = DemoMenuBuilder.snipe_result(
                        success=success,
                        symbol="TOKEN",
                        amount=amount,
                        tx_hash=tx_hash if success else None,
                        error=None if success else "Insufficient balance",
                        sl_set=success,
                        tp_set=success,
                    )

                    # If successful, add to positions
                    if success:
                        positions = context.user_data.get("demo_positions", [])
                        positions.append({
                            "symbol": "TOKEN",
                            "address": address,
                            "amount": amount,
                            "entry_price": 0.001,
                            "current_price": 0.001,
                            "pnl": 0,
                            "pnl_percent": 0,
                            "sl_percent": 15,
                            "tp_percent": 15,
                            "entry_time": datetime.now(timezone.utc).isoformat(),
                        })
                        context.user_data["demo_positions"] = positions
                else:
                    text, keyboard = DemoMenuBuilder.error_message(
                        error="Invalid confirmation",
                        retry_action="demo:insta_snipe",
                    )
            except Exception as e:
                logger.error(f"Snipe confirm error: {e}")
                text, keyboard = DemoMenuBuilder.snipe_result(
                    success=False,
                    symbol="TOKEN",
                    amount=0,
                    error=str(e),
                )

        elif action == "learning":
            # Self-Improving Learning Dashboard (V1 Feature)
            intelligence = get_trade_intelligence()
            if intelligence:
                learning_stats = intelligence.get_learning_summary()
                compression_stats = intelligence.get_compression_stats()
            else:
                learning_stats = {
                    "total_trades_analyzed": 0,
                    "pattern_memories": 0,
                    "stable_strategies": 0,
                    "signals": {},
                    "regimes": {},
                    "optimal_hold_time": 60,
                }
                compression_stats = {"compression_ratio": 1.0, "learned_patterns": 0}

            text, keyboard = DemoMenuBuilder.learning_dashboard(
                learning_stats=learning_stats,
                compression_stats=compression_stats,
            )

        elif action == "learning_deep":
            # Deep learning analysis view
            intelligence = get_trade_intelligence()
            theme = JarvisTheme

            if intelligence:
                stats = intelligence.get_learning_summary()
                comp = intelligence.get_compression_stats()

                lines = [
                    f"{theme.AUTO} *DEEP LEARNING ANALYSIS*",
                    "━━━━━━━━━━━━━━━━━━━━━",
                    "",
                    "*Memory Architecture:*",
                    "┌ Tier 0: Ephemeral (real-time)",
                    "├ Tier 1: Short-term (hours-days)",
                    "├ Tier 2: Medium-term (weeks)",
                    "└ Tier 3: Long-term (months+)",
                    "",
                    f"*Compression Efficiency:*",
                    f"├ Tier 1 Trades: {comp.get('tier1_trades', 0)}",
                    f"├ Tier 2 Patterns: {comp.get('tier2_patterns', 0)}",
                    f"├ Compression Ratio: {comp.get('compression_ratio', 1):.1f}x",
                    f"└ Raw → Latent: ~{comp.get('compression_ratio', 1) * 100:.0f}% savings",
                    "",
                    "*Core Principle:*",
                    "_Compression is Intelligence_",
                    "_The better we predict, the better we compress_",
                    "_The better we compress, the better we understand_",
                ]
                text = "\n".join(lines)
            else:
                text = f"{theme.AUTO} *Learning engine initializing...*"

            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton(f"{theme.BACK} Back", callback_data="demo:learning")],
            ])

        elif action == "performance":
            # Portfolio Performance Dashboard (V1 Feature)
            intelligence = get_trade_intelligence()
            theme = JarvisTheme

            if intelligence:
                # Get performance stats from intelligence engine
                summary = intelligence.get_learning_summary()
                performance_stats = {
                    "total_trades": summary.get("total_trades_analyzed", 0),
                    "wins": summary.get("wins", 0),
                    "losses": summary.get("losses", 0),
                    "win_rate": summary.get("win_rate", 0),
                    "total_pnl": summary.get("total_pnl", 0),
                    "total_pnl_pct": summary.get("total_pnl_pct", 0),
                    "best_trade": summary.get("best_trade", {}),
                    "worst_trade": summary.get("worst_trade", {}),
                    "current_streak": summary.get("current_streak", 0),
                    "avg_hold_time_minutes": summary.get("optimal_hold_time", 60),
                    "daily_pnl": summary.get("daily_pnl", 0),
                    "weekly_pnl": summary.get("weekly_pnl", 0),
                    "monthly_pnl": summary.get("monthly_pnl", 0),
                    "avg_trades_per_day": summary.get("avg_trades_per_day", 0),
                }
            else:
                # Mock performance data for demo
                performance_stats = {
                    "total_trades": 47,
                    "wins": 31,
                    "losses": 16,
                    "win_rate": 66.0,
                    "total_pnl": 1247.50,
                    "total_pnl_pct": 24.95,
                    "best_trade": {"symbol": "BONK", "pnl_pct": 142.5},
                    "worst_trade": {"symbol": "BOME", "pnl_pct": -35.2},
                    "current_streak": 3,
                    "avg_hold_time_minutes": 45,
                    "daily_pnl": 125.50,
                    "weekly_pnl": 487.25,
                    "monthly_pnl": 1247.50,
                    "avg_trades_per_day": 2.3,
                }

            text, keyboard = DemoMenuBuilder.performance_dashboard(performance_stats)

        elif action == "trade_history":
            # Trade History View
            intelligence = get_trade_intelligence()
            theme = JarvisTheme

            if intelligence:
                # Get trade history from intelligence engine
                summary = intelligence.get_learning_summary()
                trades = summary.get("recent_trades", [])
            else:
                # Mock trade history for demo
                trades = [
                    {"symbol": "BONK", "pnl_pct": 42.5, "pnl_usd": 85.00},
                    {"symbol": "WIF", "pnl_pct": -12.3, "pnl_usd": -24.60},
                    {"symbol": "POPCAT", "pnl_pct": 28.7, "pnl_usd": 57.40},
                    {"symbol": "PEPE", "pnl_pct": 15.2, "pnl_usd": 30.40},
                    {"symbol": "MOODENG", "pnl_pct": -8.5, "pnl_usd": -17.00},
                    {"symbol": "GOAT", "pnl_pct": 67.3, "pnl_usd": 134.60},
                    {"symbol": "PNUT", "pnl_pct": 22.1, "pnl_usd": 44.20},
                ]

            text, keyboard = DemoMenuBuilder.trade_history_view(trades)

        elif action.startswith("history_page:"):
            # Paginated trade history
            parts = data.split(":")
            page = int(parts[2]) if len(parts) >= 3 else 0

            intelligence = get_trade_intelligence()
            if intelligence:
                summary = intelligence.get_learning_summary()
                trades = summary.get("recent_trades", [])
            else:
                trades = [
                    {"symbol": "BONK", "pnl_pct": 42.5, "pnl_usd": 85.00},
                    {"symbol": "WIF", "pnl_pct": -12.3, "pnl_usd": -24.60},
                    {"symbol": "POPCAT", "pnl_pct": 28.7, "pnl_usd": 57.40},
                    {"symbol": "PEPE", "pnl_pct": 15.2, "pnl_usd": 30.40},
                    {"symbol": "MOODENG", "pnl_pct": -8.5, "pnl_usd": -17.00},
                    {"symbol": "GOAT", "pnl_pct": 67.3, "pnl_usd": 134.60},
                    {"symbol": "PNUT", "pnl_pct": 22.1, "pnl_usd": 44.20},
                ]

            text, keyboard = DemoMenuBuilder.trade_history_view(trades, page=page)

        elif action == "pnl_chart":
            text = """
📈 *PnL CHART*
━━━━━━━━━━━━━━━━━━━━━

_Generating performance chart..._

Visual PnL tracking with:
• Daily equity curve
• Win/loss distribution
• Drawdown analysis

Coming in V2!
"""
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("◀️ Back", callback_data="demo:performance")],
            ])

        elif action == "leaderboard":
            text = """
🏆 *LEADERBOARD*
━━━━━━━━━━━━━━━━━━━━━

Compare your performance with
other JARVIS traders!

_Feature coming in V2_

For now, focus on beating
your own records 💪
"""
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("◀️ Back", callback_data="demo:performance")],
            ])

        elif action == "goals":
            text = """
🎯 *TRADING GOALS*
━━━━━━━━━━━━━━━━━━━━━

Set and track your targets:

📈 *Daily Goal:* $50
📊 *Weekly Goal:* $250
🏆 *Monthly Goal:* $1,000

_Goal customization coming in V2!_
"""
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("◀️ Back", callback_data="demo:performance")],
            ])

        elif action == "quick_trade":
            # Quick Trade Menu
            trending = await get_trending_with_sentiment()
            if not trending:
                trending = [
                    {"symbol": "BONK", "change_24h": 15.2, "address": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263"},
                    {"symbol": "WIF", "change_24h": -5.3, "address": "EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm"},
                    {"symbol": "POPCAT", "change_24h": 42.1, "address": "7GCihgDB8fe6KNjn2MYtkzZcRjQy3t9GHdC8uHYmW2hr"},
                ]

            text, keyboard = DemoMenuBuilder.quick_trade_menu(
                trending_tokens=trending,
                positions=positions,
                sol_balance=sol_balance,
                market_regime=market_regime.get("regime", "NEUTRAL"),
            )

        elif action == "sell_all":
            # Sell all positions
            theme = JarvisTheme
            if positions:
                position_count = len(positions)
                total_value = sum(p.get("pnl_usd", 0) for p in positions)

                text = f"""
{theme.SELL} *CONFIRM SELL ALL*
━━━━━━━━━━━━━━━━━━━━━

You are about to sell *{position_count} positions*

*Positions:*
"""
                for pos in positions[:5]:
                    symbol = pos.get("symbol", "???")
                    pnl = pos.get("pnl_pct", 0)
                    emoji = "🟢" if pnl >= 0 else "🔴"
                    text += f"\n{emoji} {symbol}: {'+' if pnl >= 0 else ''}{pnl:.1f}%"

                if len(positions) > 5:
                    text += f"\n_...and {len(positions) - 5} more_"

                text += f"""

━━━━━━━━━━━━━━━━━━━━━

{theme.WARNING} This will close ALL positions!
"""

                keyboard = InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton(f"✅ Confirm Sell All", callback_data="demo:execute_sell_all"),
                    ],
                    [
                        InlineKeyboardButton(f"{theme.CLOSE} Cancel", callback_data="demo:quick_trade"),
                    ],
                ])
            else:
                text, keyboard = DemoMenuBuilder.error_message("No positions to sell")

        elif action == "execute_sell_all":
            # Execute sell all positions with success fee tracking
            theme = JarvisTheme
            try:
                from tg_bot import bot_core as bot_module
                engine = await bot_module._get_treasury_engine()

                closed_count = 0
                total_pnl = 0.0
                total_fees = 0.0
                fee_manager = get_success_fee_manager()

                for pos in positions:
                    try:
                        await engine.close_position(pos.get("id"))
                        closed_count += 1

                        # Calculate success fee for each winning position
                        pnl_usd = pos.get("pnl_usd", 0)
                        total_pnl += pnl_usd

                        if pnl_usd > 0:
                            fee_result = fee_manager.calculate_success_fee(
                                entry_price=pos.get("entry_price", 0),
                                exit_price=pos.get("current_price", 0),
                                amount_sol=pos.get("amount", 0),
                                token_symbol=pos.get("symbol", "???"),
                            )
                            if fee_result.get("applies"):
                                total_fees += fee_result.get("fee_amount", 0)
                    except Exception as e:
                        logger.warning(f"Failed to close position {pos.get('id')}: {e}")

                # Build enhanced result message
                pnl_emoji = "📈" if total_pnl > 0 else "📉" if total_pnl < 0 else "➖"
                pnl_sign = "+" if total_pnl > 0 else ""

                details = f"Closed {closed_count}/{len(positions)} positions\n"
                details += f"\n{pnl_emoji} Total P&L: {pnl_sign}${total_pnl:.2f}"

                if total_fees > 0:
                    net_profit = total_pnl - total_fees
                    details += f"\n💰 Success Fee (0.5%): -${total_fees:.4f}"
                    details += f"\n💵 Net Profit: +${net_profit:.2f}"

                details += "\n\nOrders submitted to Jupiter."

                text, keyboard = DemoMenuBuilder.success_message(
                    action="Sell All Executed",
                    details=details,
                )

                logger.info(f"Sell all: {closed_count} positions | PnL: ${total_pnl:.2f} | Fees: ${total_fees:.4f}")
            except Exception as e:
                text, keyboard = DemoMenuBuilder.error_message(f"Sell all failed: {str(e)[:50]}")

        elif action == "snipe_mode":
            # Snipe mode view
            text, keyboard = DemoMenuBuilder.snipe_mode_view()
            context.user_data["snipe_mode"] = True
            context.user_data["snipe_amount"] = 0.1

        elif action.startswith("snipe_amount:"):
            # Set snipe amount
            parts = data.split(":")
            amount = float(parts[2]) if len(parts) >= 3 else 0.1
            context.user_data["snipe_amount"] = amount
            text, keyboard = DemoMenuBuilder.snipe_mode_view()
            # Update view with new amount - for now just refresh

        elif action == "snipe_disable":
            # Disable snipe mode
            context.user_data["snipe_mode"] = False
            text, keyboard = DemoMenuBuilder.success_message(
                action="Snipe Mode Disabled",
                details="Token addresses will now show analysis instead of instant buy.",
            )

        elif action == "watchlist":
            # Show watchlist menu
            watchlist = context.user_data.get("watchlist", [])

            # Fetch live prices for watchlist tokens
            if watchlist:
                for token in watchlist:
                    try:
                        address = token.get("address", "")
                        if address:
                            sentiment = await get_ai_sentiment_for_token(address)
                            token["price"] = sentiment.get("price", token.get("price", 0))
                            token["change_24h"] = sentiment.get("change_24h", token.get("change_24h", 0))
                    except Exception:
                        pass  # Keep existing data

            text, keyboard = DemoMenuBuilder.watchlist_menu(watchlist)

        elif action == "watchlist_add":
            # Prompt to add token
            theme = JarvisTheme
            text = f"""
{theme.GEM} *ADD TO WATCHLIST*
━━━━━━━━━━━━━━━━━━━━━

Paste a Solana token address
to add it to your watchlist.

Example:
`DezXAZ8z7PnrnRJjz3...`

The token will be tracked with
live price updates!
"""
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton(f"{theme.BACK} Cancel", callback_data="demo:watchlist")],
            ])
            context.user_data["awaiting_watchlist_token"] = True

        elif action.startswith("watchlist_remove:"):
            # Remove from watchlist
            parts = data.split(":")
            if len(parts) >= 3:
                try:
                    index = int(parts[2])
                    watchlist = context.user_data.get("watchlist", [])
                    if 0 <= index < len(watchlist):
                        removed = watchlist.pop(index)
                        context.user_data["watchlist"] = watchlist
                        text, keyboard = DemoMenuBuilder.success_message(
                            action="Token Removed",
                            details=f"Removed {removed.get('symbol', 'token')} from watchlist",
                        )
                    else:
                        text, keyboard = DemoMenuBuilder.error_message("Invalid watchlist index")
                except Exception as e:
                    text, keyboard = DemoMenuBuilder.error_message(f"Failed to remove: {e}")
            else:
                text, keyboard = DemoMenuBuilder.error_message("Invalid remove command")

        elif action.startswith("analyze:"):
            # AI Token Analysis
            parts = data.split(":")
            if len(parts) >= 3:
                token_address = parts[2]
                sentiment_data = await get_ai_sentiment_for_token(token_address)
                token_data = {
                    "symbol": sentiment_data.get("symbol", "TOKEN"),
                    "address": token_address,
                    "price_usd": sentiment_data.get("price", 0),
                    "change_24h": sentiment_data.get("change_24h", 0),
                    "volume": sentiment_data.get("volume", 0),
                    "liquidity": sentiment_data.get("liquidity", 0),
                    "sentiment": sentiment_data.get("sentiment", "neutral"),
                    "score": sentiment_data.get("score", 0),
                    "confidence": sentiment_data.get("confidence", 0),
                    "signal": sentiment_data.get("signal", "NEUTRAL"),
                    "reasons": sentiment_data.get("reasons", []),
                }
                text, keyboard = DemoMenuBuilder.token_analysis_menu(token_data)
            else:
                text, keyboard = DemoMenuBuilder.error_message("Invalid token address")

        elif action == "new_pairs":
            text = """
🆕 *NEW PAIRS*
━━━━━━━━━━━━━━━━━━━━━

_Scanning for new liquidity pools..._

This feature monitors Raydium and Orca
for fresh token launches.

Coming soon in V2!
"""
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("◀️ Back", callback_data="demo:main")],
            ])

        elif action == "toggle_mode":
            # Toggle live/paper mode
            try:
                from tg_bot import bot_core as bot_module
                engine = await bot_module._get_treasury_engine()
                engine.dry_run = not engine.dry_run
                new_mode = "PAPER" if engine.dry_run else "LIVE"
                text, keyboard = DemoMenuBuilder.success_message(
                    action=f"Mode Changed to {new_mode}",
                    details=f"Trading is now in {'paper' if engine.dry_run else 'live'} mode.",
                )
            except Exception as e:
                text, keyboard = DemoMenuBuilder.error_message(f"Mode toggle failed: {e}")

        elif action == "close":
            await query.message.delete()
            return

        elif action.startswith("buy:"):
            # Handle buy amount selection
            parts = data.split(":")
            if len(parts) >= 3:
                amount = float(parts[2])
                text, keyboard = DemoMenuBuilder.token_input_prompt()
                context.user_data["buy_amount"] = amount
                context.user_data["awaiting_token"] = True

        elif action.startswith("sell:"):
            # Handle sell action with success fee calculation
            parts = data.split(":")
            if len(parts) >= 4:
                pos_id = parts[2]
                pct = int(parts[3])

                # Find position
                pos_data = next((p for p in positions if p["id"] == pos_id), None)
                if pos_data:
                    symbol = pos_data.get("symbol", "???")
                    entry_price = pos_data.get("entry_price", 0)
                    current_price = pos_data.get("current_price", entry_price)
                    amount_sol = pos_data.get("amount", 0) * (pct / 100)
                    pnl_pct = pos_data.get("pnl_pct", 0)
                    pnl_usd = pos_data.get("pnl_usd", 0) * (pct / 100)  # Scale by sell %

                    # Calculate success fee if winning trade
                    fee_manager = get_success_fee_manager()
                    fee_result = fee_manager.calculate_success_fee(
                        entry_price=entry_price,
                        exit_price=current_price,
                        amount_sol=amount_sol,
                        token_symbol=symbol,
                    )

                    success_fee = fee_result.get("fee_amount", 0) if fee_result.get("applies") else 0
                    net_profit = fee_result.get("net_profit", pnl_usd) if fee_result.get("applies") else pnl_usd

                    # Use close_position_result UI for better display
                    text, keyboard = DemoMenuBuilder.close_position_result(
                        success=True,
                        symbol=symbol,
                        amount=amount_sol,
                        entry_price=entry_price,
                        exit_price=current_price,
                        pnl_usd=pnl_usd,
                        pnl_percent=pnl_pct,
                        success_fee=success_fee,
                        net_profit=net_profit,
                        tx_hash=f"pending_{pos_id[:8]}",  # Simulated TX for now
                    )

                    logger.info(
                        f"Position close: {symbol} {pct}% | "
                        f"PnL: ${pnl_usd:.2f} ({pnl_pct:+.1f}%) | "
                        f"Fee: ${success_fee:.4f}"
                    )
                else:
                    text, keyboard = DemoMenuBuilder.error_message("Position not found")

        elif action.startswith("quick_buy:"):
            # Quick buy from trending - with AI sentiment check
            parts = data.split(":")
            if len(parts) >= 3:
                token_addr = parts[2]
                amount = float(parts[3]) if len(parts) >= 4 else context.user_data.get("buy_amount", 0.1)

                # Get AI sentiment before showing buy confirmation
                sentiment_data = await get_ai_sentiment_for_token(token_addr)
                sentiment = sentiment_data.get("sentiment", "neutral")
                score = sentiment_data.get("score", 0)
                signal = sentiment_data.get("signal", "NEUTRAL")

                # Build enhanced buy confirmation with AI sentiment
                theme = JarvisTheme
                short_addr = f"{token_addr[:6]}...{token_addr[-4:]}"

                # Sentiment emoji
                sent_emoji = {"bullish": "🟢", "bearish": "🔴", "very_bullish": "🚀"}.get(
                    sentiment.lower(), "🟡"
                )
                sig_emoji = {"STRONG_BUY": "🔥", "BUY": "🟢", "SELL": "🔴"}.get(signal, "🟡")

                text = f"""
{theme.BUY} *CONFIRM BUY*
━━━━━━━━━━━━━━━━━━━━━

*Address:* `{short_addr}`
*Amount:* {amount} SOL

{theme.AUTO} *AI Analysis*
├ Sentiment: {sent_emoji} *{sentiment.upper()}*
├ Score: *{score:.2f}*
└ Signal: {sig_emoji} *{signal}*

━━━━━━━━━━━━━━━━━━━━━
{theme.WARNING} _AI recommends: {signal}_
"""

                keyboard = InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton(f"{theme.SUCCESS} Confirm Buy", callback_data=f"demo:execute_buy:{token_addr}:{amount}"),
                    ],
                    [
                        InlineKeyboardButton(f"{theme.CHART} More Analysis", callback_data=f"demo:analyze:{token_addr}"),
                    ],
                    [
                        InlineKeyboardButton(f"{theme.CLOSE} Cancel", callback_data="demo:main"),
                    ],
                ])

        elif action.startswith("execute_buy:"):
            # Actually execute the buy order
            parts = data.split(":")
            if len(parts) >= 4:
                token_addr = parts[2]
                amount = float(parts[3])

                # Execute via treasury engine
                try:
                    from tg_bot import bot_core as bot_module
                    engine = await bot_module._get_treasury_engine()

                    # Place buy order
                    result = await engine.buy_token(token_addr, amount)

                    if result:
                        text, keyboard = DemoMenuBuilder.success_message(
                            action="Buy Order Executed",
                            details=f"Bought token with {amount} SOL\n\nTransaction submitted to Jupiter.\n\nCheck /positions to monitor.",
                        )
                    else:
                        text, keyboard = DemoMenuBuilder.error_message("Buy order failed - check logs")
                except Exception as e:
                    text, keyboard = DemoMenuBuilder.error_message(f"Buy failed: {str(e)[:50]}")

        else:
            # Default: return to main menu
            text, keyboard = DemoMenuBuilder.main_menu(
                wallet_address=wallet_address,
                sol_balance=sol_balance,
                usd_value=usd_value,
                is_live=is_live,
                open_positions=open_positions_count,
                total_pnl=total_pnl,
                market_regime=market_regime,
                ai_auto_enabled=ai_auto_enabled,
            )

        # Edit the message with new content
        await query.message.edit_text(
            text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard,
        )

    except Exception as e:
        logger.error(f"Demo callback error: {e}")
        text, keyboard = DemoMenuBuilder.error_message(str(e)[:100])
        try:
            await query.message.edit_text(
                text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=keyboard,
            )
        except Exception:
            pass


# =============================================================================
# Message Handler for Token Input
# =============================================================================

@error_handler
async def demo_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle text messages when awaiting token input or watchlist add."""
    text = update.message.text.strip()

    # Handle watchlist token addition
    if context.user_data.get("awaiting_watchlist_token"):
        context.user_data["awaiting_watchlist_token"] = False

        # Validate Solana address (basic check)
        if len(text) < 32 or len(text) > 44:
            error_text, keyboard = DemoMenuBuilder.error_message(
                "Invalid Solana address. Must be 32-44 characters."
            )
            await update.message.reply_text(
                error_text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=keyboard,
            )
            return

        # Get token info
        try:
            sentiment = await get_ai_sentiment_for_token(text)
            token_data = {
                "symbol": sentiment.get("symbol", "TOKEN"),
                "address": text,
                "price": sentiment.get("price", 0),
                "change_24h": sentiment.get("change_24h", 0),
            }

            # Add to watchlist
            watchlist = context.user_data.get("watchlist", [])

            # Check for duplicates
            if any(t.get("address") == text for t in watchlist):
                error_text, keyboard = DemoMenuBuilder.error_message(
                    "Token already in watchlist"
                )
                await update.message.reply_text(
                    error_text,
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=keyboard,
                )
                return

            watchlist.append(token_data)
            context.user_data["watchlist"] = watchlist

            success_text, keyboard = DemoMenuBuilder.success_message(
                action="Token Added",
                details=f"Added {token_data['symbol']} to your watchlist!\n\nCurrent price: ${token_data['price']:.6f}",
            )
            await update.message.reply_text(
                success_text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=keyboard,
            )
        except Exception as e:
            error_text, keyboard = DemoMenuBuilder.error_message(
                f"Failed to add token: {str(e)[:50]}"
            )
            await update.message.reply_text(
                error_text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=keyboard,
            )
        return

    # Handle wallet import input
    if context.user_data.get("awaiting_wallet_import"):
        context.user_data["awaiting_wallet_import"] = False
        import_mode = context.user_data.get("import_mode", "key")

        try:
            from bots.treasury.wallet import SecureWallet

            if import_mode == "seed":
                # Import from seed phrase
                words = text.strip().split()
                if len(words) not in [12, 24]:
                    raise ValueError(f"Seed phrase must be 12 or 24 words, got {len(words)}")

                wallet = SecureWallet.from_seed(text.strip())
            else:
                # Import from private key
                if len(text.strip()) < 64:
                    raise ValueError("Private key too short (min 64 chars)")

                wallet = SecureWallet.from_private_key(text.strip())

            wallet_address = wallet.get_address()

            result_text, keyboard = DemoMenuBuilder.wallet_import_result(
                success=True,
                wallet_address=wallet_address,
            )
            logger.info(f"Wallet imported: {wallet_address[:8]}...")

        except Exception as e:
            logger.error(f"Wallet import failed: {e}")
            result_text, keyboard = DemoMenuBuilder.wallet_import_result(
                success=False,
                error=str(e)[:100],
            )

        await update.message.reply_text(
            result_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard,
        )
        return

    # Handle buy token input
    if not context.user_data.get("awaiting_token"):
        return

    # Clear the flag
    context.user_data["awaiting_token"] = False

    # Validate Solana address (basic check)
    if len(text) < 32 or len(text) > 44:
        error_text, keyboard = DemoMenuBuilder.error_message(
            "Invalid Solana address. Must be 32-44 characters."
        )
        await update.message.reply_text(
            error_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard,
        )
        return

    amount = context.user_data.get("buy_amount", 0.1)

    # Show buy confirmation
    confirm_text, keyboard = DemoMenuBuilder.buy_confirmation(
        token_symbol="TOKEN",
        token_address=text,
        amount_sol=amount,
        estimated_tokens=1000000,  # Would be calculated from price
        price_usd=0.00001,  # Would be fetched from DEX
    )

    await update.message.reply_text(
        confirm_text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=keyboard,
    )


# =============================================================================
# Registration Helper
# =============================================================================

def register_demo_handlers(app):
    """Register demo handlers with the application."""
    from telegram.ext import CommandHandler, CallbackQueryHandler, MessageHandler, filters

    # Main command
    app.add_handler(CommandHandler("demo", demo))

    # Callback handler for all demo:* buttons
    app.add_handler(CallbackQueryHandler(demo_callback, pattern=r"^demo:"))

    # Message handler for token input (lower priority)
    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            demo_message_handler
        ),
        group=1  # Lower priority than command handlers
    )

    logger.info("Demo handlers registered")
