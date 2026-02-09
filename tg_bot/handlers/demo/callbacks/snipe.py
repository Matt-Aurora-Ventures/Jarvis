"""
Demo Bot - Snipe Callback Handler

Handles: insta_snipe, snipe_mode, snipe_disable, snipe_exec, snipe_confirm, snipe_amount
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Tuple

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

logger = logging.getLogger(__name__)


async def handle_snipe(
    ctx,
    action: str,
    data: str,
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    state: Dict[str, Any],
) -> Tuple[str, InlineKeyboardMarkup]:
    """
    Handle snipe callbacks.

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
    user_id = query.from_user.id if query and query.from_user else 0

    if action == "insta_snipe":
        try:
            hottest_token = None

            # Try DexScreener boosted tokens
            try:
                from core.dexscreener import get_boosted_tokens_with_data
                import asyncio

                boosted = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: get_boosted_tokens_with_data(chain="solana", limit=1, cache_ttl_seconds=60)
                )
                if boosted:
                    top = boosted[0]
                    volume_ratio = top.volume_24h / top.liquidity_usd if top.liquidity_usd > 0 else 0
                    conviction = "VERY HIGH" if volume_ratio > 5 else "HIGH" if volume_ratio > 2 else "MEDIUM"
                    hottest_token = {
                        "symbol": top.base_token_symbol,
                        "address": top.base_token_address,
                        "price": top.price_usd,
                        "change_24h": top.price_change_24h,
                        "volume_24h": top.volume_24h,
                        "liquidity": top.liquidity_usd,
                        "market_cap": 0,
                        "conviction": conviction,
                        "sentiment_score": 75,
                        "entry_timing": "GOOD" if abs(top.price_change_1h) < 10 else "LATE",
                        "sightings": 1,
                    }
            except Exception as api_err:
                logger.warning(f"DexScreener boosted tokens error: {api_err}")

            # Validate token
            if hottest_token:
                symbol_ok = bool(hottest_token.get("symbol")) and hottest_token.get("symbol") != "UNKNOWN"
                price_ok = float(hottest_token.get("price", 0) or 0) > 0
                if not (symbol_ok and price_ok):
                    hottest_token = None

            # Fallback to Bags.fm
            if not hottest_token:
                bags_tokens = await ctx.get_bags_top_tokens_with_sentiment(limit=1)
                if bags_tokens:
                    t = bags_tokens[0]
                    score = float(t.get("sentiment_score", 0.5) or 0.5)
                    conviction_score = int(round(score * 100)) if score <= 1 else int(score)
                    conviction = ctx.conviction_label(conviction_score)
                    entry_timing = "GOOD" if score >= 0.55 else "LATE"
                    hottest_token = {
                        "symbol": t.get("symbol", "UNKNOWN"),
                        "address": t.get("address", ""),
                        "price": float(t.get("price_usd", 0) or 0),
                        "change_24h": float(t.get("change_24h", 0) or 0),
                        "volume_24h": float(t.get("volume_24h", 0) or 0),
                        "liquidity": float(t.get("liquidity", 0) or 0),
                        "market_cap": float(t.get("market_cap", 0) or 0),
                        "conviction": conviction,
                        "sentiment_score": int(round(score * 100)) if score <= 1 else int(score),
                        "entry_timing": entry_timing,
                        "sightings": 1,
                    }

            # Real data only: don't inject placeholder tokens if upstream sources fail.
            if not hottest_token:
                return DemoMenuBuilder.error_message(
                    error=(
                        "Insta Snipe is temporarily unavailable.\n\n"
                        "Could not load boosted tokens from DexScreener or Bags Top tokens.\n"
                        "Try again in ~30-60 seconds."
                    ),
                    retry_action="demo:insta_snipe",
                    context_hint="insta_snipe",
                )

            hottest_token["token_id"] = ctx.register_token_id(context, hottest_token.get("address"))

            return DemoMenuBuilder.insta_snipe_menu(
                hottest_token=hottest_token,
                market_regime=market_regime,
                auto_sl_percent=15.0,
                auto_tp_percent=15.0,
            )
        except Exception as e:
            logger.error(f"Insta snipe error: {e}")
            return DemoMenuBuilder.error_message(
                error=str(e),
                retry_action="demo:insta_snipe",
                context_hint="insta_snipe",
            )

    elif action == "snipe_mode":
        context.user_data["snipe_mode"] = True
        context.user_data["snipe_amount"] = 0.1
        return DemoMenuBuilder.snipe_mode_view()

    elif data.startswith("demo:snipe_amount:"):
        parts = data.split(":")
        amount = float(parts[2]) if len(parts) >= 3 else 0.1
        context.user_data["snipe_amount"] = amount
        return DemoMenuBuilder.snipe_mode_view()

    elif action == "snipe_disable":
        context.user_data["snipe_mode"] = False
        return DemoMenuBuilder.success_message(
            action="Snipe Mode Disabled",
            details="Token addresses will now show analysis instead of instant buy.",
        )

    elif data.startswith("demo:snipe_exec:"):
        try:
            parts = data.split(":")
            if len(parts) >= 4:
                token_ref = parts[2]
                address = ctx.resolve_token_ref(context, token_ref)
                amount = float(parts[3])

                context.user_data["snipe_address"] = address
                context.user_data["snipe_token_ref"] = token_ref
                context.user_data["snipe_amount"] = amount

                sentiment_data = await ctx.get_ai_sentiment_for_token(address)
                symbol = sentiment_data.get("symbol", "TOKEN")
                price = float(sentiment_data.get("price", 0) or 0)
                if price <= 0:
                    price = 0.001
                context.user_data["snipe_symbol"] = symbol
                context.user_data["snipe_price"] = price

                return DemoMenuBuilder.snipe_confirm(
                    symbol=symbol,
                    address=address,
                    amount=amount,
                    price=price,
                    sl_percent=15.0,
                    tp_percent=15.0,
                    token_ref=token_ref,
                )
            else:
                return DemoMenuBuilder.error_message(
                    error="Invalid snipe request",
                    retry_action="demo:insta_snipe",
                )
        except Exception as e:
            logger.error(f"Snipe exec error: {e}")
            return DemoMenuBuilder.error_message(
                error=str(e),
                retry_action="demo:insta_snipe",
                context_hint="snipe_exec",
            )

    elif data.startswith("demo:snipe_confirm:"):
        try:
            parts = data.split(":")
            if len(parts) >= 4:
                token_ref = parts[2]
                address = ctx.resolve_token_ref(context, token_ref)
                amount = float(parts[3])

                # Flow controller validation
                try:
                    from tg_bot.services.flow_controller import get_flow_controller, FlowDecision

                    flow = get_flow_controller()
                    flow_result = await flow.process_command(
                        command="buy",
                        args=[address, str(amount)],
                        user_id=user_id,
                        chat_id=query.message.chat_id,
                        is_admin=True,
                        force_execute=True,
                    )

                    if flow_result.decision == FlowDecision.HOLD:
                        return DemoMenuBuilder.error_message(f"Trade blocked: {flow_result.hold_reason}")
                except ImportError:
                    logger.debug("Flow controller not available, proceeding")
                except Exception as e:
                    logger.warning(f"Flow validation error (continuing): {e}")

                # Execute REAL swap via bags.fm API
                try:
                    engine = await ctx.get_demo_engine()
                    portfolio = await engine.get_portfolio_value()
                    if not portfolio:
                        raise RuntimeError("Portfolio unavailable")
                    balance_sol, balance_usd = portfolio
                    if balance_sol <= 0:
                        return DemoMenuBuilder.error_message("Treasury balance is zero.")
                    if amount > balance_sol:
                        return DemoMenuBuilder.error_message(f"Insufficient balance. Have {balance_sol:.4f} SOL, need {amount} SOL.")

                    sol_usd = balance_usd / balance_sol if balance_sol > 0 else 0
                    amount_usd = amount * sol_usd

                    sentiment_data = await ctx.get_ai_sentiment_for_token(address)
                    token_symbol = sentiment_data.get("symbol", "TOKEN")
                    signal_name = sentiment_data.get("signal", "NEUTRAL")
                    grade = ctx.grade_for_signal_name(signal_name)
                    sentiment_score = sentiment_data.get("score", 0) or 0

                    # ============================================================
                    # REAL SWAP EXECUTION (TREASURY WALLET)
                    # ============================================================
                    wallet_address = await ctx.resolve_wallet_address(context)
                    if not wallet_address:
                        return DemoMenuBuilder.snipe_result(
                            success=False,
                            symbol=token_symbol,
                            amount=amount,
                            error="No treasury wallet configured. Fund/configure treasury wallet and retry.",
                        )

                    # Execute buy with mandatory TP/SL via the centralized path
                    exec_buy = getattr(ctx, "execute_buy_with_tpsl", None)
                    if not callable(exec_buy):
                        # Backwards-compatible fallback in case the context loader is out of sync.
                        from tg_bot.handlers.demo.demo_trading import execute_buy_with_tpsl as exec_buy

                    result = await exec_buy(
                        token_address=address,
                        amount_sol=amount,
                        wallet_address=wallet_address,
                        tp_percent=15.0,
                        sl_percent=15.0,
                    )

                    if not result.get("success"):
                        return DemoMenuBuilder.snipe_result(
                            success=False,
                            symbol=token_symbol,
                            amount=amount,
                            error=result.get("error") or "Swap failed",
                        )

                    # Persist into demo UI portfolio for /positions
                    position = result.get("position", {})
                    positions = context.user_data.get("positions", [])
                    positions.append(position)
                    context.user_data["positions"] = positions

                    return DemoMenuBuilder.snipe_result(
                        success=True,
                        symbol=token_symbol,
                        amount=amount,
                        tx_hash=result.get("tx_hash") or position.get("tx_hash"),
                        error=None,
                        sl_set=True,
                        tp_set=True,
                    )

                except Exception as e:
                    logger.error(f"Snipe confirm error: {e}", exc_info=True)
                    return DemoMenuBuilder.snipe_result(
                        success=False,
                        symbol="TOKEN",
                        amount=amount,
                        error=str(e),
                    )
            else:
                return DemoMenuBuilder.error_message(
                    error="Invalid confirmation",
                    retry_action="demo:insta_snipe",
                )
        except Exception as e:
            logger.error(f"Snipe confirm error: {e}")
            return DemoMenuBuilder.snipe_result(
                success=False,
                symbol="TOKEN",
                amount=0,
                error=str(e),
            )

    # Default
    return DemoMenuBuilder.snipe_mode_view()
