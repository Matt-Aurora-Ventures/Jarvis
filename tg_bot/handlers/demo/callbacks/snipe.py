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

            # Fallback to mock data
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
                    # REAL BAGS.FM SWAP EXECUTION (USER WALLET)
                    # ============================================================
                    from core.trading.bags_client import BagsAPIClient
                    from tg_bot.core.wallet_manager import get_wallet_manager
                    import uuid

                    SOL_MINT = "So11111111111111111111111111111111111111112"

                    # Get user's wallet (or create one)
                    wallet_manager = get_wallet_manager()
                    user_wallet = await wallet_manager.get_wallet(user_id)
                    
                    if not user_wallet:
                        # Auto-create wallet for user
                        user_wallet, private_key = await wallet_manager.create_wallet(user_id)
                        logger.info(f"Auto-created wallet for user {user_id}: {user_wallet.public_key}")
                        
                        # Try to DM them their private key
                        try:
                            dm_text = (
                                "🔐 *WALLET CREATED FOR TRADING*\n"
                                "━━━━━━━━━━━━━━━━━━━━━\n\n"
                                f"*Address:*\n`{user_wallet.public_key}`\n\n"
                                "⚠️ *SAVE YOUR PRIVATE KEY*\n\n"
                                f"`{private_key}`\n\n"
                                "━━━━━━━━━━━━━━━━━━━━━\n"
                                "🛡️ Store safely! Use /wallet to manage."
                            )
                            await context.bot.send_message(
                                chat_id=user_id,
                                text=dm_text,
                                parse_mode="Markdown"
                            )
                        except Exception as dm_err:
                            logger.warning(f"Couldn't DM user {user_id}: {dm_err}")

                    USER_WALLET = user_wallet.public_key

                    # Check user wallet balance before trading
                    user_balance = await wallet_manager.get_balance_sol(user_id)
                    if user_balance is None or user_balance < amount:
                        return DemoMenuBuilder.snipe_result(
                            success=False,
                            symbol=token_symbol,
                            amount=amount,
                            error=f"Insufficient balance. You have {user_balance or 0:.4f} SOL, need {amount} SOL. Fund your wallet: {USER_WALLET}",
                        )

                    # Get user's keypair for signing
                    user_keypair = await wallet_manager.get_keypair(user_id)
                    if not user_keypair:
                        return DemoMenuBuilder.snipe_result(
                            success=False,
                            symbol=token_symbol,
                            amount=amount,
                            error="Failed to load wallet keypair. Try /wallet to recreate.",
                        )

                    # Initialize bags client
                    bags_client = BagsAPIClient()

                    # Execute the swap using USER's wallet and keypair
                    logger.info(f"Executing bags.fm swap for user {user_id}: {amount} SOL -> {token_symbol} ({address})")
                    
                    swap_result = await bags_client.swap(
                        from_token=SOL_MINT,
                        to_token=address,
                        amount=amount,
                        wallet_address=USER_WALLET,
                        slippage_bps=200,  # 2% slippage for volatile tokens
                        keypair=user_keypair,  # User's keypair for signing
                    )

                    if not swap_result.success:
                        logger.error(f"Bags.fm swap failed: {swap_result.error}")
                        return DemoMenuBuilder.snipe_result(
                            success=False,
                            symbol=token_symbol,
                            amount=amount,
                            error=swap_result.error or "Swap failed",
                        )

                    # Real transaction hash from bags.fm
                    real_tx_hash = swap_result.tx_hash
                    logger.info(f"Bags.fm swap successful! TX: {real_tx_hash}")

                    # Now record the position in the engine for tracking
                    from bots.treasury.trading import TradeDirection, Position, TradeStatus

                    # Get current token price for position tracking
                    current_price = await engine.jupiter.get_token_price(address)
                    if current_price <= 0:
                        current_price = swap_result.price if swap_result.price > 0 else 0.001

                    # Calculate TP/SL prices
                    tp_pct = 15.0 / 100.0
                    sl_pct = 15.0 / 100.0
                    tp_price = current_price * (1 + tp_pct)
                    sl_price = current_price * (1 - sl_pct)

                    # Create position record
                    position_id = str(uuid.uuid4())[:8]
                    token_amount = swap_result.to_amount if swap_result.to_amount > 0 else (amount_usd / current_price)

                    position = Position(
                        id=position_id,
                        token_mint=address,
                        token_symbol=token_symbol,
                        direction=TradeDirection.LONG,
                        entry_price=current_price,
                        current_price=current_price,
                        amount=token_amount,
                        amount_usd=amount_usd,
                        take_profit_price=tp_price,
                        stop_loss_price=sl_price,
                        status=TradeStatus.OPEN,
                        opened_at=datetime.now(timezone.utc).isoformat(),
                        sentiment_grade=grade,
                        sentiment_score=sentiment_score,
                        peak_price=current_price,
                    )

                    # Add to engine tracking
                    engine.positions[position_id] = position
                    engine._save_state()

                    # Track in scorekeeper
                    try:
                        from bots.treasury.scorekeeper import get_scorekeeper
                        scorekeeper = get_scorekeeper()
                        scorekeeper.open_position(
                            position_id=position_id,
                            symbol=token_symbol,
                            token_mint=address,
                            entry_price=current_price,
                            entry_amount_sol=amount,
                            entry_amount_tokens=token_amount,
                            take_profit_price=tp_price,
                            stop_loss_price=sl_price,
                            tx_signature=real_tx_hash,
                            user_id=user_id or 0,
                        )
                    except Exception as sk_err:
                        logger.warning(f"Failed to track in scorekeeper: {sk_err}")

                    return DemoMenuBuilder.snipe_result(
                        success=True,
                        symbol=token_symbol,
                        amount=amount,
                        tx_hash=real_tx_hash,
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
