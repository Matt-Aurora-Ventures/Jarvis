"""
Demo Bot - Bags.fm Callback Handler

Handles: bags_fm, bags_info, bags_buy, bags_exec, bags_settings, bags_set_tp, bags_set_sl
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Tuple

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


async def handle_bags(
    ctx,
    action: str,
    data: str,
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    state: Dict[str, Any],
) -> Tuple[str, InlineKeyboardMarkup]:
    """
    Handle Bags.fm callbacks.

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

    if action == "bags_fm":
        try:
            bags_tokens = await ctx.get_bags_top_tokens_with_sentiment(limit=15)
            for token in bags_tokens:
                token["token_id"] = ctx.register_token_id(context, token.get("address"))

            default_tp = context.user_data.get("bags_tp_percent", 15.0)
            default_sl = context.user_data.get("bags_sl_percent", 15.0)

            return DemoMenuBuilder.bags_fm_top_tokens(
                tokens=bags_tokens,
                market_regime=market_regime,
                default_tp_percent=default_tp,
                default_sl_percent=default_sl,
            )
        except Exception as e:
            logger.error(f"Bags.fm error: {e}")
            return DemoMenuBuilder.error_message(
                error=str(e),
                retry_action="demo:bags_fm",
                context_hint="bags_fm",
            )

    elif data.startswith("demo:bags_info:"):
        token_ref = data.split(":")[2]
        address = ctx.resolve_token_ref(context, token_ref)

        bags_tokens = await ctx.get_bags_top_tokens_with_sentiment(limit=15)
        token = next((t for t in bags_tokens if t.get("address") == address), None)

        if token:
            token["token_id"] = token_ref
            default_tp = context.user_data.get("bags_tp_percent", 15.0)
            default_sl = context.user_data.get("bags_sl_percent", 15.0)

            return DemoMenuBuilder.bags_token_detail(
                token=token,
                market_regime=market_regime,
                default_tp_percent=default_tp,
                default_sl_percent=default_sl,
            )
        else:
            return DemoMenuBuilder.error_message(
                error="Token not found",
                retry_action="demo:bags_fm",
            )

    elif data.startswith("demo:bags_buy:"):
        parts = data.split(":")
        token_ref = parts[2]
        address = ctx.resolve_token_ref(context, token_ref)
        tp_percent = float(parts[3]) if len(parts) > 3 else 15.0
        sl_percent = float(parts[4]) if len(parts) > 4 else 15.0

        bags_tokens = await ctx.get_bags_top_tokens_with_sentiment(limit=15)
        token = next((t for t in bags_tokens if t.get("address") == address), None)

        if token:
            token["token_id"] = token_ref
            return DemoMenuBuilder.bags_token_detail(
                token=token,
                market_regime=market_regime,
                default_tp_percent=tp_percent,
                default_sl_percent=sl_percent,
            )
        else:
            return DemoMenuBuilder.error_message(
                error="Token not found",
                retry_action="demo:bags_fm",
            )

    elif data.startswith("demo:bags_exec:"):
        parts = data.split(":")
        token_ref = parts[2]
        address = ctx.resolve_token_ref(context, token_ref)
        amount_sol = float(parts[3]) if len(parts) > 3 else 0.1
        tp_percent = float(parts[4]) if len(parts) > 4 else 15.0
        sl_percent = float(parts[5]) if len(parts) > 5 else 15.0

        bags_tokens = await ctx.get_bags_top_tokens_with_sentiment(limit=15)
        token = next((t for t in bags_tokens if t.get("address") == address), None)

        if token:
            symbol = token.get("symbol", "???")
            price = token.get("price_usd", 0)

            try:
                wallet_address = await ctx.resolve_wallet_address(context)
                if not wallet_address:
                    return DemoMenuBuilder.error_message(
                        "❌ No treasury wallet configured\n\n"
                        "This chat should be using the treasury wallet, but none was found.\n"
                        "(Missing treasury keypair / wallet config.)"
                    )
                slippage_bps = ctx.get_demo_slippage_bps()
                swap = await ctx.execute_swap_with_fallback(
                    from_token="So11111111111111111111111111111111111111112",
                    to_token=address,
                    amount=amount_sol,
                    wallet_address=wallet_address,
                    slippage_bps=slippage_bps,
                )

                if swap.get("success"):
                    tokens_received = swap.get("amount_out") or (
                        (amount_sol * 225 / price) if price > 0 else 0
                    )

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
                        "source": swap.get("source", "bags_fm"),
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                    positions.append(new_position)
                    context.user_data["positions"] = positions

                    return DemoMenuBuilder.bags_buy_result(
                        success=True,
                        symbol=symbol,
                        amount_sol=amount_sol,
                        tokens_received=tokens_received,
                        price=price,
                        tp_percent=tp_percent,
                        sl_percent=sl_percent,
                        tx_hash=swap.get("tx_hash"),
                    )
                else:
                    return DemoMenuBuilder.bags_buy_result(
                        success=False,
                        symbol=symbol,
                        amount_sol=amount_sol,
                        error=swap.get("error") or "Trade execution failed",
                    )
            except Exception as e:
                logger.error(f"Bags buy error: {e}")
                return DemoMenuBuilder.bags_buy_result(
                    success=False,
                    symbol=symbol,
                    amount_sol=amount_sol,
                    error=str(e)[:50],
                )
        else:
            return DemoMenuBuilder.error_message(
                error="Token not found",
                retry_action="demo:bags_fm",
            )

    elif action == "bags_settings":
        default_tp = context.user_data.get("bags_tp_percent", 15.0)
        default_sl = context.user_data.get("bags_sl_percent", 15.0)

        text = f"""
{theme.SETTINGS} *BAGS.FM TRADING SETTINGS*
{'=' * 20}

*Current Settings:*
{theme.SNIPE} Take Profit: +{default_tp:.0f}%
{theme.ERROR} Stop Loss: -{default_sl:.0f}%

*Select new TP/SL presets:*

{'=' * 20}
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
                InlineKeyboardButton(f"{theme.GEM} Back to Bags", callback_data="demo:bags_fm"),
            ],
        ])
        return text, keyboard

    elif data.startswith("demo:bags_set_tp:"):
        tp_value = float(data.split(":")[2])
        context.user_data["bags_tp_percent"] = tp_value
        await query.answer(f"Take Profit set to +{tp_value:.0f}%")

        default_tp = tp_value
        default_sl = context.user_data.get("bags_sl_percent", 15.0)
        text = f"""
{theme.SETTINGS} *BAGS.FM TRADING SETTINGS*
{'=' * 20}

{theme.SUCCESS} *Settings Updated!*

*Current Settings:*
{theme.SNIPE} Take Profit: +{default_tp:.0f}%
{theme.ERROR} Stop Loss: -{default_sl:.0f}%

{'=' * 20}
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
                InlineKeyboardButton(f"{theme.GEM} Back to Bags", callback_data="demo:bags_fm"),
            ],
        ])
        return text, keyboard

    elif data.startswith("demo:bags_set_sl:"):
        sl_value = float(data.split(":")[2])
        context.user_data["bags_sl_percent"] = sl_value
        await query.answer(f"Stop Loss set to -{sl_value:.0f}%")

        default_tp = context.user_data.get("bags_tp_percent", 15.0)
        default_sl = sl_value
        text = f"""
{theme.SETTINGS} *BAGS.FM TRADING SETTINGS*
{'=' * 20}

{theme.SUCCESS} *Settings Updated!*

*Current Settings:*
{theme.SNIPE} Take Profit: +{default_tp:.0f}%
{theme.ERROR} Stop Loss: -{default_sl:.0f}%

{'=' * 20}
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
                InlineKeyboardButton(f"{theme.GEM} Back to Bags", callback_data="demo:bags_fm"),
            ],
        ])
        return text, keyboard

    # Default
    return DemoMenuBuilder.error_message(
        error="Unknown Bags.fm action",
        retry_action="demo:bags_fm",
    )
