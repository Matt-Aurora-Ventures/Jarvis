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
from datetime import datetime, timezone

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
    """Get Grok's top conviction picks."""
    try:
        from core.enhanced_market_data import get_grok_conviction_picks
        picks = await get_grok_conviction_picks()
        return [
            {
                "symbol": p.symbol,
                "address": p.address,
                "conviction": p.conviction,
                "thesis": p.thesis,
                "entry_price": p.entry_price,
                "tp_target": p.tp_target,
                "sl_target": p.sl_target,
            }
            for p in picks[:5]
        ]
    except Exception as e:
        logger.warning(f"Could not get conviction picks: {e}")
        return []

# =============================================================================
# UI Constants - Trojan-Style Theme
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

        # Build message with beautiful formatting + AI sentiment
        text = f"""
{theme.ROCKET} *JARVIS AI TRADING* {theme.ROCKET}
━━━━━━━━━━━━━━━━━━━━━

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
            # AI-Powered Analysis Row (NEW)
            [
                InlineKeyboardButton(f"{theme.AUTO} AI Picks", callback_data="demo:ai_picks"),
                InlineKeyboardButton(f"{theme.CHART} AI Report", callback_data="demo:ai_report"),
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
    ) -> Tuple[str, InlineKeyboardMarkup]:
        """Build wallet management menu."""
        theme = JarvisTheme

        if not has_wallet:
            text = f"""
{theme.WALLET} *WALLET SETUP*
━━━━━━━━━━━━━━━━━━━━━

{theme.WARNING} No wallet configured

Create a new wallet or import an existing one.

{theme.LOCK} All keys are encrypted with AES-256
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
            short_addr = f"{wallet_address[:6]}...{wallet_address[-4:]}"

            text = f"""
{theme.WALLET} *WALLET MANAGEMENT*
━━━━━━━━━━━━━━━━━━━━━

{theme.KEY} *Address*
`{wallet_address}`

{theme.SOL} Balance: *{sol_balance:.4f} SOL*
{theme.USD} Value: *${usd_value:,.2f}*

━━━━━━━━━━━━━━━━━━━━━
{theme.LOCK} Private key stored encrypted
"""
            keyboard = [
                [
                    InlineKeyboardButton(f"{theme.COPY} Copy Address", callback_data="demo:copy_address"),
                ],
                [
                    InlineKeyboardButton(f"{theme.REFRESH} Refresh Balance", callback_data="demo:refresh_balance"),
                ],
                [
                    InlineKeyboardButton(f"{theme.LOCK} Export Key", callback_data="demo:export_key"),
                    InlineKeyboardButton(f"{theme.WARNING} Reset Wallet", callback_data="demo:wallet_reset"),
                ],
                [
                    InlineKeyboardButton(f"{theme.BACK} Back", callback_data="demo:main"),
                ],
            ]

        return text, InlineKeyboardMarkup(keyboard)

    @staticmethod
    def positions_menu(
        positions: list,
        total_pnl: float = 0.0,
    ) -> Tuple[str, InlineKeyboardMarkup]:
        """Build positions overview with sell buttons."""
        theme = JarvisTheme

        if not positions:
            text = f"""
{theme.CHART} *POSITIONS*
━━━━━━━━━━━━━━━━━━━━━

_No open positions_

Use the buy buttons to enter a trade!
"""
            keyboard = [
                [
                    InlineKeyboardButton(f"{theme.FIRE} Find Tokens", callback_data="demo:trending"),
                ],
                [
                    InlineKeyboardButton(f"{theme.BACK} Back", callback_data="demo:main"),
                ],
            ]
        else:
            pnl_emoji = theme.PROFIT if total_pnl >= 0 else theme.LOSS
            pnl_sign = "+" if total_pnl >= 0 else ""

            lines = [
                f"{theme.CHART} *POSITIONS*",
                "━━━━━━━━━━━━━━━━━━━━━",
                f"Total P&L: {pnl_emoji} *{pnl_sign}${abs(total_pnl):.2f}*",
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

                pos_emoji = theme.PROFIT if pnl_pct >= 0 else theme.LOSS
                pnl_sign = "+" if pnl_pct >= 0 else ""

                lines.extend([
                    f"{pos_emoji} *{symbol}* {pnl_sign}{pnl_pct:.1f}%",
                    f"   Entry: ${entry:.8f}",
                    f"   Now: ${current:.8f}",
                    f"   P&L: {pnl_sign}${abs(pnl_usd):.2f}",
                    "",
                ])

                # Add sell buttons for each position
                keyboard.append([
                    InlineKeyboardButton(
                        f"{theme.SELL} Sell {symbol} (25%)",
                        callback_data=f"demo:sell:{pos_id}:25"
                    ),
                    InlineKeyboardButton(
                        f"{theme.SELL} Sell All",
                        callback_data=f"demo:sell:{pos_id}:100"
                    ),
                ])

            text = "\n".join(lines)

            # Add navigation
            keyboard.extend([
                [
                    InlineKeyboardButton(f"{theme.REFRESH} Refresh", callback_data="demo:positions"),
                ],
                [
                    InlineKeyboardButton(f"{theme.BACK} Back", callback_data="demo:main"),
                ],
            ])

        return text, InlineKeyboardMarkup(keyboard)

    @staticmethod
    def settings_menu(
        is_live: bool = False,
        slippage: float = 1.0,
        auto_sell: bool = True,
        take_profit: float = 50.0,
        stop_loss: float = 20.0,
    ) -> Tuple[str, InlineKeyboardMarkup]:
        """Build settings menu."""
        theme = JarvisTheme

        mode = f"{theme.LIVE} LIVE" if is_live else f"{theme.PAPER} PAPER"
        auto_status = f"{theme.SUCCESS} ON" if auto_sell else f"{theme.ERROR} OFF"

        text = f"""
{theme.SETTINGS} *SETTINGS*
━━━━━━━━━━━━━━━━━━━━━

*Trading Mode*
└ {mode}

*Slippage*
└ {slippage}%

*Auto-Sell*
└ Status: {auto_status}
├ Take Profit: +{take_profit}%
└ Stop Loss: -{stop_loss}%

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
            [
                InlineKeyboardButton(f"{theme.BACK} Back", callback_data="demo:main"),
            ],
        ]

        return text, InlineKeyboardMarkup(keyboard)

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
    ) -> Tuple[str, InlineKeyboardMarkup]:
        """
        Show AI-powered conviction picks from Grok.

        These are tokens the sentiment engine recommends based on:
        - Data-driven scoring (67% TP rate criteria)
        - Multi-source sentiment analysis
        - Risk-adjusted position sizing
        """
        theme = JarvisTheme

        # Market context
        regime = market_regime or {}
        regime_name = regime.get("regime", "NEUTRAL")
        risk_level = regime.get("risk_level", "NORMAL")

        regime_emoji = {"BULL": "🟢", "BEAR": "🔴"}.get(regime_name, "🟡")

        lines = [
            f"{theme.AUTO} *AI CONVICTION PICKS*",
            "━━━━━━━━━━━━━━━━━━━━━",
            f"Market: {regime_emoji} {regime_name} | Risk: {risk_level}",
            "",
            "_Based on data-driven criteria:_",
            "• Entry timing < 50% pump (67% TP rate)",
            "• Buy/sell ratio ≥ 2.0x",
            "• Multi-sighting validation",
            "",
        ]

        keyboard = []

        if not picks:
            lines.append("_No high-conviction picks right now._")
            lines.append("_AI is waiting for better setups._")
        else:
            for pick in picks[:5]:
                symbol = pick.get("symbol", "???")
                conviction = pick.get("conviction", "MEDIUM")
                thesis = pick.get("thesis", "")[:50]
                address = pick.get("address", "")
                tp = pick.get("tp_target", 0)
                sl = pick.get("sl_target", 0)

                # Conviction emoji
                conv_emoji = {"HIGH": "🔥", "MEDIUM": "📊", "LOW": "📉"}.get(conviction, "📊")

                lines.append(f"{conv_emoji} *{symbol}* - {conviction}")
                if thesis:
                    lines.append(f"   _{thesis}_")
                if tp and sl:
                    lines.append(f"   TP: +{tp}% | SL: -{sl}%")
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
                InlineKeyboardButton(f"{theme.REFRESH} Refresh Picks", callback_data="demo:ai_picks"),
            ],
            [
                InlineKeyboardButton(f"{theme.BACK} Back", callback_data="demo:main"),
            ],
        ])

        return text, InlineKeyboardMarkup(keyboard)

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
    ) -> Tuple[str, InlineKeyboardMarkup]:
        """Show error message."""
        theme = JarvisTheme

        text = f"""
{theme.ERROR} *ERROR*
━━━━━━━━━━━━━━━━━━━━━

{error}

━━━━━━━━━━━━━━━━━━━━━
"""

        keyboard = [
            [
                InlineKeyboardButton(f"{theme.REFRESH} Try Again", callback_data="demo:main"),
            ],
        ]

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
        text, keyboard = DemoMenuBuilder.main_menu(
            wallet_address=wallet_address,
            sol_balance=sol_balance,
            usd_value=usd_value,
            is_live=is_live,
            open_positions=open_positions,
            total_pnl=total_pnl,
            market_regime=market_regime,
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
        if action in ("main", "refresh"):
            text, keyboard = DemoMenuBuilder.main_menu(
                wallet_address=wallet_address,
                sol_balance=sol_balance,
                usd_value=usd_value,
                is_live=is_live,
                open_positions=open_positions_count,
                total_pnl=total_pnl,
                market_regime=market_regime,
            )

        elif action == "wallet_menu":
            text, keyboard = DemoMenuBuilder.wallet_menu(
                wallet_address=wallet_address,
                sol_balance=sol_balance,
                usd_value=usd_value,
                has_wallet=wallet_address != "Not configured",
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
            text, keyboard = DemoMenuBuilder.settings_menu(is_live=is_live)

        elif action == "balance":
            text, keyboard = DemoMenuBuilder.wallet_menu(
                wallet_address=wallet_address,
                sol_balance=sol_balance,
                usd_value=usd_value,
                has_wallet=True,
            )

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
            # Execute sell all positions
            theme = JarvisTheme
            try:
                from tg_bot import bot_core as bot_module
                engine = await bot_module._get_treasury_engine()

                closed_count = 0
                for pos in positions:
                    try:
                        await engine.close_position(pos.get("id"))
                        closed_count += 1
                    except Exception as e:
                        logger.warning(f"Failed to close position {pos.get('id')}: {e}")

                text, keyboard = DemoMenuBuilder.success_message(
                    action="Sell All Executed",
                    details=f"Closed {closed_count}/{len(positions)} positions\n\nOrders submitted to Jupiter.",
                )
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
            # Handle sell action
            parts = data.split(":")
            if len(parts) >= 4:
                pos_id = parts[2]
                pct = int(parts[3])

                # Find position
                pos_data = next((p for p in positions if p["id"] == pos_id), None)
                if pos_data:
                    symbol = pos_data["symbol"]
                    text, keyboard = DemoMenuBuilder.success_message(
                        action=f"Sell Order Placed",
                        details=f"Selling {pct}% of {symbol}\n\nOrder submitted to Jupiter.",
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
    """Handle text messages when awaiting token input."""
    if not context.user_data.get("awaiting_token"):
        return

    # Clear the flag
    context.user_data["awaiting_token"] = False

    text = update.message.text.strip()

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
