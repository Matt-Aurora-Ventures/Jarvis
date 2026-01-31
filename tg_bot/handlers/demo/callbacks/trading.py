"""
Demo Bot - Trading View Callback Handler

Handles: trending, ai_picks, ai_report, quick_trade, token_input, token_search
"""

import logging
from typing import Any, Dict, Tuple

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


async def handle_trading(
    ctx,
    action: str,
    data: str,
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    state: Dict[str, Any],
) -> Tuple[str, InlineKeyboardMarkup]:
    """
    Handle trading view callbacks.

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
    positions = state.get("positions", [])
    sol_balance = state.get("sol_balance", 0.0)

    if action == "trending":
        trending = await ctx.get_trending_with_sentiment()
        if not trending:
            trending = [
                {"symbol": "BONK", "change_24h": 15.2, "volume": 1500000, "address": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263", "sentiment": "bullish", "sentiment_score": 0.72, "signal": "BUY"},
                {"symbol": "WIF", "change_24h": -5.3, "volume": 2300000, "address": "EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm", "sentiment": "neutral", "sentiment_score": 0.45, "signal": "NEUTRAL"},
                {"symbol": "POPCAT", "change_24h": 42.1, "volume": 890000, "address": "7GCihgDB8fe6KNjn2MYtkzZcRjQy3t9GHdC8uHYmW2hr", "sentiment": "very_bullish", "sentiment_score": 0.85, "signal": "STRONG_BUY"},
                {"symbol": "MEW", "change_24h": 8.7, "volume": 650000, "address": "MEW1gQWJ3nEXg2qgERiKu7FAFj79PHvQVREQUzScPP5", "sentiment": "bullish", "sentiment_score": 0.61, "signal": "BUY"},
            ]
        for token in trending:
            token["token_id"] = ctx.register_token_id(context, token.get("address"))
        return DemoMenuBuilder.trending_tokens(
            trending,
            market_regime=market_regime,
        )

    elif action == "ai_picks":
        picks = await ctx.get_conviction_picks()
        trending = await ctx.get_trending_with_sentiment()
        volume_leaders = await ctx.get_bags_top_tokens_with_sentiment(limit=6)
        if not trending and volume_leaders:
            trending = volume_leaders[:6]

        for token in picks:
            token["token_id"] = ctx.register_token_id(context, token.get("address"))
        for token in (trending or []):
            token["token_id"] = ctx.register_token_id(context, token.get("address"))
        for token in volume_leaders:
            token["token_id"] = ctx.register_token_id(context, token.get("address"))

        near_picks = []
        for token in volume_leaders[:6]:
            score = float(token.get("sentiment_score", 0.5) or 0.5)
            if 0.45 <= score < 0.6:
                near_picks.append({
                    "symbol": token.get("symbol", "???"),
                    "missing_criteria": "sentiment",
                    "score": int(round(score * 100)),
                    "change_24h": token.get("change_24h", 0),
                })

        pick_stats = ctx.get_pick_stats()
        return DemoMenuBuilder.ai_picks_menu(
            picks=picks,
            market_regime=market_regime,
            trending=trending,
            volume_leaders=volume_leaders,
            near_picks=near_picks,
            pick_stats=pick_stats,
        )

    elif action == "ai_report":
        return DemoMenuBuilder.ai_report_menu(market_regime=market_regime)

    elif action == "quick_trade":
        trending = await ctx.get_trending_with_sentiment()
        if not trending:
            trending = [
                {"symbol": "BONK", "change_24h": 15.2, "address": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263"},
                {"symbol": "WIF", "change_24h": -5.3, "address": "EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm"},
                {"symbol": "POPCAT", "change_24h": 42.1, "address": "7GCihgDB8fe6KNjn2MYtkzZcRjQy3t9GHdC8uHYmW2hr"},
            ]

        return DemoMenuBuilder.quick_trade_menu(
            trending_tokens=trending,
            positions=positions,
            sol_balance=sol_balance,
            market_regime=market_regime.get("regime", "NEUTRAL"),
        )

    elif action == "token_input":
        context.user_data["awaiting_token"] = True
        return DemoMenuBuilder.token_input_prompt()

    elif action == "token_search":
        text = f"""
{theme.SEARCH} *UNIVERSAL TOKEN SEARCH*
{'=' * 20}

Trade ANY token by contract address or symbol.

*How to use:*
1. Enter token contract address or symbol
2. View detailed token analysis
3. Buy or sell with custom amounts

*Examples:*
- `So11111111111111111111111111111111111111112` (SOL)
- `EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v` (USDC)
- Or just type: `BONK`, `WIF`, `JUP`

{'=' * 20}
_Reply with token address or symbol:_
"""
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(f"{theme.CHART} Popular Tokens", callback_data="demo:trending"),
                InlineKeyboardButton(f"{theme.GEM} Bags Top 15", callback_data="demo:bags_fm"),
            ],
            [
                InlineKeyboardButton(f"{theme.BACK} Main Menu", callback_data="demo:main"),
            ],
        ])
        context.user_data["awaiting_token_search"] = True
        return text, keyboard

    elif action == "copy_ca":
        # Send a copy-friendly contract address message (Telegram users can tap+hold to copy)
        try:
            parts = data.split(":")
            token_ref = parts[2] if len(parts) > 2 else ""
            addr = ctx.resolve_token_ref(context, token_ref)
            query = update.callback_query
            if query and query.message:
                await query.message.reply_text(
                    f"📋 *Contract Address*\n`{addr}`\n\n"
                    f"🔗 Solscan: https://solscan.io/token/{addr}",
                    parse_mode="Markdown",
                )
                return None, None
        except Exception as e:
            logger.warning(f"copy_ca failed: {e}")
            return DemoMenuBuilder.error_message("Failed to copy contract address")

    # Default
    return DemoMenuBuilder.main_menu(
        wallet_address=state.get("wallet_address", "Not configured"),
        sol_balance=sol_balance,
        usd_value=state.get("usd_value", 0.0),
        is_live=state.get("is_live", False),
        open_positions=len(positions),
        total_pnl=state.get("total_pnl", 0.0),
        market_regime=market_regime,
        ai_auto_enabled=state.get("ai_auto_enabled", False),
    )
