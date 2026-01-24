"""
Demo Bot - Sell Callback Handler

Handles: sell:*, sell_all, execute_sell_all
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Tuple

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

logger = logging.getLogger(__name__)


async def handle_sell(
    ctx,
    action: str,
    data: str,
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    state: Dict[str, Any],
) -> Tuple[str, InlineKeyboardMarkup]:
    """
    Handle sell callbacks.

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
    positions = state.get("positions", [])

    if action == "sell_all":
        if positions:
            position_count = len(positions)

            text = f"""
{theme.SELL} *CONFIRM SELL ALL*
{'=' * 20}

You are about to sell *{position_count} positions*

*Positions:*
"""
            for pos in positions[:5]:
                symbol = pos.get("symbol", "???")
                pnl = pos.get("pnl_pct", 0)
                emoji = "{green}" if pnl >= 0 else "{red}"
                text += f"\n{emoji} {symbol}: {'+' if pnl >= 0 else ''}{pnl:.1f}%"

            if len(positions) > 5:
                text += f"\n_...and {len(positions) - 5} more_"

            text += f"""

{'=' * 20}

{theme.WARNING} This will close ALL positions!
"""
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton(f"{theme.SUCCESS} Confirm Sell All", callback_data="demo:execute_sell_all")],
                [InlineKeyboardButton(f"{theme.CLOSE} Cancel", callback_data="demo:quick_trade")],
            ])
            return text, keyboard
        else:
            return DemoMenuBuilder.error_message("No positions to sell")

    elif action == "execute_sell_all":
        # Execute sell all positions with success fee tracking
        # Show loading state
        try:
            position_count = len(positions)
            await query.message.edit_text(
                theme.loading_text(f"Processing Sell All ({position_count} positions)"),
                parse_mode=ParseMode.MARKDOWN,
            )
        except Exception:
            pass

        # Flow controller validation
        try:
            from tg_bot.services.flow_controller import get_flow_controller, FlowDecision

            flow = get_flow_controller()
            flow_result = await flow.process_command(
                command="sell",
                args=["all"],
                user_id=user_id,
                chat_id=query.message.chat_id,
                is_admin=True,
                force_execute=True,
            )

            if flow_result.decision == FlowDecision.HOLD:
                return DemoMenuBuilder.error_message(f"Sell blocked: {flow_result.hold_reason}")

            logger.info(f"Flow approved sell all (checks: {flow_result.checks_performed})")
        except ImportError:
            pass
        except Exception as e:
            logger.warning(f"Flow validation error (continuing): {e}")

        try:
            wallet_address = context.user_data.get("wallet_address", "demo_wallet")
            slippage_bps = ctx.get_demo_slippage_bps()

            closed_count = 0
            failed_count = 0
            total_pnl = 0.0
            total_fees = 0.0
            fee_manager = ctx.get_success_fee_manager()

            for pos in positions:
                try:
                    token_address = pos.get("address")
                    token_amount = pos.get("amount", 0)
                    symbol = pos.get("symbol", "???")

                    swap = await ctx.execute_swap_with_fallback(
                        from_token=token_address,
                        to_token="So11111111111111111111111111111111111111112",
                        amount=token_amount,
                        wallet_address=wallet_address,
                        slippage_bps=slippage_bps,
                    )

                    if swap.get("success"):
                        closed_count += 1
                        logger.info(f"Sold {symbol} via {swap.get('source', 'bags_fm')}: {swap.get('tx_hash')}")

                        pnl_usd = pos.get("pnl_usd", 0)
                        total_pnl += pnl_usd

                        if pnl_usd > 0 and fee_manager:
                            fee_result = fee_manager.calculate_success_fee(
                                entry_price=pos.get("entry_price", 0),
                                exit_price=pos.get("current_price", 0),
                                amount_sol=pos.get("amount_sol", 0),
                                token_symbol=symbol,
                            )
                            if fee_result.get("applies"):
                                total_fees += fee_result.get("fee_amount", 0)
                    else:
                        failed_count += 1
                        logger.warning(f"Failed to sell {symbol}: {swap.get('error')}")
                except Exception as e:
                    failed_count += 1
                    logger.warning(f"Failed to sell position {pos.get('symbol')}: {e}")

            # Clear positions after sell
            context.user_data["positions"] = []

            # Build result message
            pnl_emoji = "{chart_up}" if total_pnl > 0 else "{chart_down}" if total_pnl < 0 else "{dash}"
            pnl_sign = "+" if total_pnl > 0 else ""

            details = f"Sold {closed_count}/{len(positions)} positions via Bags.fm"
            if failed_count > 0:
                details += f"\n{theme.WARNING} {failed_count} failed"
            details += f"\n\n{pnl_emoji} Total P&L: {pnl_sign}${total_pnl:.2f}"

            if total_fees > 0:
                net_profit = total_pnl - total_fees
                details += f"\n{theme.COIN} Success Fee (0.5%): -${total_fees:.4f}"
                details += f"\n{theme.COIN} Net Profit: +${net_profit:.2f}"

            logger.info(f"Sell all: {closed_count} sold, {failed_count} failed | PnL: ${total_pnl:.2f} | Fees: ${total_fees:.4f}")
            return DemoMenuBuilder.success_message(
                action="Sell All Executed",
                details=details,
            )
        except Exception as e:
            logger.error(f"Sell all error: {e}")
            return DemoMenuBuilder.error_message(f"Sell all failed: {str(e)[:50]}")

    elif data.startswith("demo:sell:"):
        # Handle sell action via Bags API with success fee calculation
        parts = data.split(":")
        if len(parts) >= 4:
            pos_id = parts[2]
            pct = int(parts[3])

            pos_data = next((p for p in positions if p["id"] == pos_id), None)
            if pos_data:
                # Show loading state
                try:
                    symbol_preview = ctx.safe_symbol(pos_data.get("symbol", "TOKEN"))
                    await query.message.edit_text(
                        theme.loading_text(f"Processing Sell Order for {pct}% of {symbol_preview}"),
                        parse_mode=ParseMode.MARKDOWN,
                    )
                except Exception:
                    pass

                try:
                    symbol = pos_data.get("symbol", "???")
                    token_address = pos_data.get("address")
                    entry_price = pos_data.get("entry_price", 0)
                    current_price = pos_data.get("current_price", entry_price)
                    token_amount = pos_data.get("amount", 0) * (pct / 100)
                    amount_sol = pos_data.get("amount_sol", 0) * (pct / 100)
                    pnl_pct = pos_data.get("pnl_pct", 0)
                    pnl_usd = pos_data.get("pnl_usd", 0) * (pct / 100)

                    wallet_address = context.user_data.get("wallet_address", "demo_wallet")
                    slippage_bps = ctx.get_demo_slippage_bps()

                    swap = await ctx.execute_swap_with_fallback(
                        from_token=token_address,
                        to_token="So11111111111111111111111111111111111111112",
                        amount=token_amount,
                        wallet_address=wallet_address,
                        slippage_bps=slippage_bps,
                    )

                    if swap.get("success"):
                        # Calculate success fee if winning trade
                        fee_manager = ctx.get_success_fee_manager()
                        fee_result = {}
                        if fee_manager:
                            fee_result = fee_manager.calculate_success_fee(
                                entry_price=entry_price,
                                exit_price=current_price,
                                amount_sol=amount_sol,
                                token_symbol=symbol,
                            )

                        success_fee = fee_result.get("fee_amount", 0) if fee_result.get("applies") else 0
                        net_profit = fee_result.get("net_profit", pnl_usd) if fee_result.get("applies") else pnl_usd

                        # Update position (reduce amount or remove if 100%)
                        if pct >= 100:
                            positions.remove(pos_data)
                        else:
                            current_amount = pos_data.get("amount", pos_data.get("amount_sol", 0))
                            current_amount_sol = pos_data.get("amount_sol", pos_data.get("amount", 0))
                            pos_data["amount"] = current_amount * (1 - pct / 100)
                            pos_data["amount_sol"] = current_amount_sol * (1 - pct / 100)
                        context.user_data["positions"] = positions

                        logger.info(
                            f"Sold {pct}% of {symbol} via {swap.get('source', 'bags_fm')} | "
                            f"PnL: ${pnl_usd:.2f} ({pnl_pct:+.1f}%) | "
                            f"Fee: ${success_fee:.4f} | TX: {swap.get('tx_hash')}"
                        )

                        return DemoMenuBuilder.close_position_result(
                            success=True,
                            symbol=symbol,
                            amount=amount_sol,
                            entry_price=entry_price,
                            exit_price=current_price,
                            pnl_usd=pnl_usd,
                            pnl_percent=pnl_pct,
                            success_fee=success_fee,
                            net_profit=net_profit,
                            tx_hash=swap.get("tx_hash") or "pending",
                        )
                    else:
                        return DemoMenuBuilder.error_message(
                            f"Sell failed: {swap.get('error') or 'Unknown error'}"
                        )
                except Exception as e:
                    logger.error(f"Sell position error: {e}")
                    return DemoMenuBuilder.error_message(f"Sell failed: {str(e)[:50]}")
            else:
                return DemoMenuBuilder.error_message("Position not found")

    # Default
    return DemoMenuBuilder.positions_menu(positions=positions)
