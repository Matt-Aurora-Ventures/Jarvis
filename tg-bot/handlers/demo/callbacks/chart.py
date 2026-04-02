"""
Demo Bot - Chart Callback Handler

Handles: chart:*, view_chart
"""

import logging
from datetime import datetime, timezone, timedelta
import time
from typing import Any, Dict, Tuple

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

logger = logging.getLogger(__name__)

_COINGECKO_BASE = "https://api.coingecko.com/api/v3"
_COINGECKO_CACHE_TTL_S = 5 * 60
_COINGECKO_CACHE: dict[str, tuple[float, list[float], list[datetime], list[float]]] = {}


async def _fetch_coingecko_market_chart(
    *,
    coin_id: str,
    days: int = 1,
    max_points: int = 72,
) -> tuple[list[float], list[datetime], list[float]]:
    """
    Fetch a USD market chart series from CoinGecko.

    Returns (prices, timestamps, volumes). Empty lists on failure.
    """
    now = time.time()
    cached = _COINGECKO_CACHE.get(coin_id)
    if cached and now - cached[0] <= _COINGECKO_CACHE_TTL_S:
        _, prices, ts, vols = cached
        return prices, ts, vols

    try:
        import aiohttp

        timeout = aiohttp.ClientTimeout(total=8)
        headers = {"Accept": "application/json", "User-Agent": "JarvisBot/1.0"}
        url = f"{_COINGECKO_BASE}/coins/{coin_id}/market_chart"
        params = {"vs_currency": "usd", "days": str(days)}
        async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
            async with session.get(url, params=params) as resp:
                if resp.status != 200:
                    logger.warning("CoinGecko market_chart failed: %s (%s)", coin_id, resp.status)
                    return [], [], []
                data = await resp.json()

        raw_prices = data.get("prices") or []
        raw_vols = data.get("total_volumes") or []
        if not raw_prices:
            return [], [], []

        # Parse and align (CoinGecko returns [ts_ms, value]).
        pts: list[tuple[datetime, float]] = []
        for it in raw_prices:
            try:
                ts_ms, price = it
                pts.append((datetime.fromtimestamp(float(ts_ms) / 1000.0, tz=timezone.utc), float(price)))
            except Exception:
                continue

        vol_pts: list[tuple[datetime, float]] = []
        for it in raw_vols:
            try:
                ts_ms, vol = it
                vol_pts.append((datetime.fromtimestamp(float(ts_ms) / 1000.0, tz=timezone.utc), float(vol)))
            except Exception:
                continue

        if not pts:
            return [], [], []

        # Downsample to keep Telegram charts readable.
        if max_points and len(pts) > max_points:
            step = max(1, len(pts) // max_points)
            pts = pts[::step]
        if vol_pts:
            # Best-effort: match volume cadence to prices after downsampling.
            if len(vol_pts) > len(pts):
                step = max(1, len(vol_pts) // len(pts))
                vol_pts = vol_pts[::step]

        ts = [t for (t, _p) in pts]
        prices = [p for (_t, p) in pts]

        # Align volumes to timestamps (may be empty).
        vols: list[float] = []
        if vol_pts:
            vols = [v for (_t, v) in vol_pts[: len(prices)]]

        _COINGECKO_CACHE[coin_id] = (now, prices, ts, vols)
        return prices, ts, vols
    except Exception as exc:
        logger.warning("CoinGecko market_chart exception (%s): %s", coin_id, exc)
        return [], [], []


async def handle_chart(
    ctx,
    action: str,
    data: str,
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    state: Dict[str, Any],
) -> Tuple[str, InlineKeyboardMarkup]:
    """
    Handle chart callbacks.

    Args:
        ctx: DemoContextLoader instance
        action: The action
        data: Full callback data
        update: Telegram update
        context: Bot context
        state: Shared state dict

    Returns:
        Tuple of (text, keyboard)
    """
    theme = ctx.JarvisTheme
    DemoMenuBuilder = ctx.DemoMenuBuilder
    market_regime = state.get("market_regime", {})
    query = update.callback_query

    if action == "view_chart":
        try:
            from tg_bot.handlers.demo.demo_ui import MATPLOTLIB_AVAILABLE, generate_price_chart

            if not MATPLOTLIB_AVAILABLE:
                return DemoMenuBuilder.error_message(
                    error="Chart generation not available",
                    retry_action="demo:ai_report",
                    context_hint="Install matplotlib to enable charts: pip install matplotlib"
                )

            # Real data: CoinGecko 24h market chart.
            btc_prices, btc_ts, btc_vols = await _fetch_coingecko_market_chart(coin_id="bitcoin", days=1, max_points=72)
            sol_prices, sol_ts, sol_vols = await _fetch_coingecko_market_chart(coin_id="solana", days=1, max_points=72)

            if not btc_prices or not btc_ts or not sol_prices or not sol_ts:
                return DemoMenuBuilder.error_message(
                    error="Market charts temporarily unavailable",
                    retry_action="demo:view_chart",
                    context_hint="Could not fetch BTC/SOL chart data from CoinGecko. Try again in a minute.",
                )

            btc_chart = generate_price_chart(
                prices=btc_prices,
                timestamps=btc_ts,
                symbol="BTC",
                timeframe="24H",
                volume=btc_vols or None,
            )

            sol_chart = generate_price_chart(
                prices=sol_prices,
                timestamps=sol_ts,
                symbol="SOL",
                timeframe="24H",
                volume=sol_vols or None,
            )

            if btc_chart and sol_chart:
                # Use UTC timestamp from the data so users can trust what they’re seeing.
                updated_at = max(btc_ts[-1], sol_ts[-1]).strftime("%H:%M UTC")
                await query.message.reply_photo(
                    photo=btc_chart,
                    caption=f"{theme.CHART} *Bitcoin (BTC) - 24H Price Chart*\n_Source: CoinGecko • Updated {updated_at}_\n\n_Generated by JARVIS AI_",
                    parse_mode=ParseMode.MARKDOWN
                )
                await query.message.reply_photo(
                    photo=sol_chart,
                    caption=f"{theme.CHART} *Solana (SOL) - 24H Price Chart*\n_Source: CoinGecko • Updated {updated_at}_\n\n_Generated by JARVIS AI_",
                    parse_mode=ParseMode.MARKDOWN
                )
                return DemoMenuBuilder.ai_report_menu(market_regime=market_regime)
            else:
                return DemoMenuBuilder.error_message(
                    error="Failed to generate charts",
                    retry_action="demo:view_chart",
                    context_hint="chart_generation"
                )
        except Exception as e:
            logger.error(f"Chart generation error: {e}", exc_info=True)
            from core.logging.error_tracker import error_tracker
            error_id = error_tracker.track_error(
                e,
                context=f"demo_callback action=view_chart",
                component="telegram_demo",
                metadata={"action": "view_chart"}
            )
            return DemoMenuBuilder.error_message(
                error=str(e)[:100],
                retry_action="demo:view_chart",
                context_hint=f"Error ID: {error_id}"
            )

    elif data.startswith("demo:chart:"):
        parts = data.split(":")
        token_ref = parts[2] if len(parts) > 2 else ""
        interval = parts[3] if len(parts) > 3 else "1h"

        token_addr = ctx.resolve_token_ref(context, token_ref)
        sentiment_data = await ctx.get_ai_sentiment_for_token(token_addr)
        token_symbol = sentiment_data.get("symbol", "TOKEN")

        # Show loading state
        try:
            await query.message.edit_text(
                theme.loading_text(f"Generating {token_symbol} chart"),
                parse_mode=ParseMode.MARKDOWN,
            )
        except Exception:
            pass

        try:
            from tg_bot.handlers.demo_charts import handle_chart_callback

            success, result = await handle_chart_callback(
                token_mint=token_addr,
                token_symbol=token_symbol,
                interval=interval,
            )

            if success:
                await context.bot.send_photo(
                    chat_id=query.message.chat_id,
                    photo=result,
                    caption=f"{theme.CHART} *{ctx.safe_symbol(token_symbol)}* Price Chart ({interval})",
                    parse_mode=ParseMode.MARKDOWN,
                )
                text = f"{theme.SUCCESS} Chart generated for *{ctx.safe_symbol(token_symbol)}*"
                keyboard = InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("1h", callback_data=f"demo:chart:{token_ref}:1h"),
                        InlineKeyboardButton("4h", callback_data=f"demo:chart:{token_ref}:4h"),
                        InlineKeyboardButton("1d", callback_data=f"demo:chart:{token_ref}:1d"),
                    ],
                    [
                        InlineKeyboardButton(f"{theme.BACK} Back", callback_data="demo:main"),
                    ],
                ])
                return text, keyboard
            else:
                return DemoMenuBuilder.error_message(result)
        except ImportError:
            return DemoMenuBuilder.error_message(
                "Chart feature requires mplfinance. Install with: pip install mplfinance pandas"
            )
        except Exception as e:
            logger.error(f"Chart generation error: {e}")
            return DemoMenuBuilder.error_message(f"Chart failed: {str(e)[:50]}")

    # Default
    return DemoMenuBuilder.ai_report_menu(market_regime=market_regime)
