"""
Demo Bot - Buy Callback Handler

Handles: buy:*, execute_buy:*, quick_buy:*, buy_custom:*
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Tuple

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

logger = logging.getLogger(__name__)


async def handle_buy(
    ctx,
    action: str,
    data: str,
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    state: Dict[str, Any],
) -> Tuple[str, InlineKeyboardMarkup]:
    """
    Handle buy callbacks.

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
    query = update.callback_query
    user_id = query.from_user.id if query and query.from_user else 0

    if data.startswith("demo:buy:"):
        # Handle buy amount selection
        parts = data.split(":")
        if len(parts) >= 3:
            amount = float(parts[2])
            context.user_data["buy_amount"] = amount
            context.user_data["awaiting_token"] = True
            return DemoMenuBuilder.token_input_prompt()

    elif data.startswith("demo:buy_custom:"):
        # Show custom amount input prompt
        parts = data.split(":")
        token_ref = parts[2] if len(parts) > 2 else ""

        context.user_data["awaiting_custom_buy_amount"] = True
        context.user_data["custom_buy_token_ref"] = token_ref

        text = f"""
{theme.BUY} *CUSTOM BUY AMOUNT*

Enter the amount of SOL you want to spend:

*Limits:*
- Minimum: 0.01 SOL
- Maximum: 50 SOL

_Send a number like "0.5" or "2.5"_
"""
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"{theme.CLOSE} Cancel", callback_data="demo:main")],
        ])
        return text, keyboard

    elif data.startswith("demo:quick_buy:"):
        # Quick buy from trending - with AI sentiment check
        parts = data.split(":")
        if len(parts) >= 3:
            token_ref = parts[2]
            token_addr = ctx.resolve_token_ref(context, token_ref)
            amount = float(parts[3]) if len(parts) >= 4 else context.user_data.get("buy_amount", 0.1)

            # Get AI sentiment before showing buy confirmation
            sentiment_data = await ctx.get_ai_sentiment_for_token(token_addr)
            sentiment = sentiment_data.get("sentiment", "neutral")
            score = sentiment_data.get("score", 0)
            signal = sentiment_data.get("signal", "NEUTRAL")

            short_addr = f"{token_addr[:6]}...{token_addr[-4:]}"

            # Sentiment emoji
            sent_emoji = {"bullish": "{green}", "bearish": "{red}", "very_bullish": "{rocket}"}.get(
                sentiment.lower(), "{yellow}"
            )
            sig_emoji = {"STRONG_BUY": "{fire}", "BUY": "{green}", "SELL": "{red}"}.get(signal, "{yellow}")

            text = f"""
{theme.BUY} *CONFIRM BUY*
{'=' * 20}

*Address:* `{short_addr}`
*Amount:* {amount} SOL

{theme.AUTO} *AI Analysis*
| Sentiment: {sent_emoji} *{sentiment.upper()}*
| Score: *{score:.2f}*
| Signal: {sig_emoji} *{signal}*

{'=' * 20}
{theme.WARNING} _AI recommends: {signal}_
"""
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton(f"{theme.SUCCESS} Confirm Buy", callback_data=f"demo:execute_buy:{token_ref}:{amount}")],
                [InlineKeyboardButton(f"{theme.CHART} More Analysis", callback_data=f"demo:analyze:{token_ref}")],
                [InlineKeyboardButton(f"{theme.CLOSE} Cancel", callback_data="demo:main")],
            ])
            return text, keyboard

    elif data.startswith("demo:execute_buy:"):
        # Actually execute the buy order
        parts = data.split(":")
        if len(parts) >= 4:
            token_ref = parts[2]
            token_addr = ctx.resolve_token_ref(context, token_ref)
            amount = float(parts[3])

            # Show loading state
            try:
                await query.message.edit_text(
                    theme.loading_text(f"Processing Buy Order for {amount:.2f} SOL"),
                    parse_mode=ParseMode.MARKDOWN,
                )
            except Exception:
                pass

            # Flow controller validation
            try:
                from tg_bot.services.flow_controller import get_flow_controller, FlowDecision

                flow = get_flow_controller()
                flow_result = await flow.process_command(
                    command="buy",
                    args=[token_addr, str(amount)],
                    user_id=user_id,
                    chat_id=query.message.chat_id,
                    is_admin=True,
                    force_execute=True,
                )

                if flow_result.decision == FlowDecision.HOLD:
                    return DemoMenuBuilder.error_message(f"Trade blocked: {flow_result.hold_reason}")

                logger.info(f"Flow approved buy: {token_addr[:8]}... for {amount} SOL")
            except ImportError:
                logger.debug("Flow controller not available, proceeding")
            except Exception as e:
                logger.warning(f"Flow validation error (continuing): {e}")

            # Execute via execute_buy_with_tpsl (centralized TP/SL enforcement)
            try:
                wallet_address = context.user_data.get("wallet_address", "demo_wallet")

                # Get TP/SL from user data or use defaults
                # TODO: Add UI for user customization
                tp_percent = context.user_data.get("tp_percent", 50.0)
                sl_percent = context.user_data.get("sl_percent", 20.0)

                # Execute buy with mandatory TP/SL validation
                result = await ctx.execute_buy_with_tpsl(
                    token_address=token_addr,
                    amount_sol=amount,
                    wallet_address=wallet_address,
                    tp_percent=tp_percent,
                    sl_percent=sl_percent,
                )

                if result.get("success"):
                    position = result.get("position", {})

                    # Add position to portfolio
                    positions = context.user_data.get("positions", [])
                    positions.append(position)
                    context.user_data["positions"] = positions

                    tx_hash = position.get("tx_hash")
                    tx_link = f"[View TX](https://solscan.io/tx/{tx_hash})" if tx_hash else "N/A"
                    token_symbol = position.get("symbol", "TOKEN")
                    tokens_received = position.get("amount", 0)
                    token_price = position.get("entry_price", 0)
                    tp_price = position.get("tp_price", 0)
                    sl_price = position.get("sl_price", 0)

                    return DemoMenuBuilder.success_message(
                        action=(
                            "Buy Order Executed via Bags.fm"
                            if position.get("source") == "bags_fm"
                            else "Buy Order Executed via Jupiter"
                        ),
                        details=(
                            f"Bought {token_symbol} with {amount:.2f} SOL\n"
                            f"Received: {tokens_received:,.0f} {token_symbol}\n"
                            f"Entry: ${token_price:.8f}\n"
                            f"TP: ${tp_price:.8f} (+{tp_percent}%)\n"
                            f"SL: ${sl_price:.8f} (-{sl_percent}%)\n"
                            f"{tx_link}\n\n"
                            "✅ TP/SL monitoring active\n"
                            "Check /positions to monitor."
                        ),
                    )
                else:
                    error_msg = result.get("error", "Unknown error")
                    return DemoMenuBuilder.error_message(f"Buy failed: {error_msg}")

            except Exception as e:
                # Import error classes for checking
                from tg_bot.handlers.demo import demo_trading as ctx

                # Check for our custom user-friendly errors
                if isinstance(e, (ctx.TPSLValidationError, ctx.BagsAPIError, ctx.TradingError)):
                    logger.warning(f"Trading error: {e.message}")
                    return DemoMenuBuilder.error_message(e.format_telegram())
                elif isinstance(e, ValueError):
                    # Legacy validation errors
                    logger.warning(f"Validation error: {e}")
                    return DemoMenuBuilder.error_message(f"❌ {str(e)}")
                else:
                    # Unexpected error
                    logger.error(f"Buy execution failed unexpectedly: {e}", exc_info=True)
                    return DemoMenuBuilder.error_message(
                        "❌ Trade execution failed\n\n"
                        f"💡 Hint: {str(e)[:100] if str(e) else 'Unknown error'}. "
                        "Please try again or contact support if the issue persists."
                    )

    # Default
    return DemoMenuBuilder.token_input_prompt()
