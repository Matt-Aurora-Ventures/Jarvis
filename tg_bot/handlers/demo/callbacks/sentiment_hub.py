"""
Demo Bot - Sentiment Hub Callback Handler

Handles: hub, hub_*, hub_news, hub_traditional, hub_wallet
"""

import logging
import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, Tuple

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ForceReply
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

logger = logging.getLogger(__name__)


async def handle_sentiment_hub(
    ctx,
    action: str,
    data: str,
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    state: Dict[str, Any],
) -> Tuple[str, InlineKeyboardMarkup]:
    """
    Handle sentiment hub callbacks.

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

    if action == "hub":
        try:
            last_report_time = context.user_data.get("hub_last_report", datetime.now(timezone.utc))
            wallet_connected = bool(context.user_data.get("wallet_address"))

            return DemoMenuBuilder.sentiment_hub_main(
                market_regime=market_regime,
                last_report_time=last_report_time,
                report_interval_minutes=15,
                wallet_connected=wallet_connected,
            )
        except Exception as e:
            logger.error(f"Hub error: {e}")
            return DemoMenuBuilder.error_message(
                error=str(e),
                retry_action="demo:hub",
                context_hint="sentiment_hub",
            )

    elif action == "hub_news":
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

            return DemoMenuBuilder.sentiment_hub_news(
                news_items=mock_news,
                macro_analysis=mock_macro,
            )
        except Exception as e:
            logger.error(f"Hub news error: {e}")
            return DemoMenuBuilder.error_message(
                error=str(e),
                retry_action="demo:hub_news",
                context_hint="hub_news",
            )

    elif action == "hub_traditional":
        try:
            mock_stocks = {"spy_change": 0.45, "qqq_change": 0.72, "dia_change": 0.22, "outlook": "bullish"}
            mock_dxy = {"value": 103.25, "change": -0.15, "trend": "weakening"}
            mock_commodities = [
                {"symbol": "GOLD", "price": 2045.50, "change": 0.8},
                {"symbol": "SILVER", "price": 24.15, "change": 1.2},
                {"symbol": "OIL", "price": 78.50, "change": -0.5},
            ]

            return DemoMenuBuilder.sentiment_hub_traditional(
                stocks_outlook=mock_stocks,
                dxy_data=mock_dxy,
                commodities=mock_commodities,
            )
        except Exception as e:
            logger.error(f"Hub traditional error: {e}")
            return DemoMenuBuilder.error_message(
                error=str(e),
                retry_action="demo:hub_traditional",
                context_hint="hub_traditional",
            )

    elif action == "hub_wallet":
        try:
            wallet_address = context.user_data.get("wallet_address", "")
            sol_balance = context.user_data.get("sol_balance", 0.0)
            usd_value = sol_balance * 225

            return DemoMenuBuilder.sentiment_hub_wallet(
                wallet_address=wallet_address,
                sol_balance=sol_balance,
                usd_value=usd_value,
                has_private_key=bool(context.user_data.get("private_key")),
            )
        except Exception as e:
            logger.error(f"Hub wallet error: {e}")
            return DemoMenuBuilder.error_message(
                error=str(e),
                retry_action="demo:hub_wallet",
                context_hint="hub_wallet",
            )

    elif data.startswith("demo:hub_buy:"):
        try:
            parts = data.split(":")
            if len(parts) >= 3:
                token_ref = parts[2]
                address = ctx.resolve_token_ref(context, token_ref)
                auto_sl_percent = float(parts[3]) if len(parts) > 3 else 15.0
                return DemoMenuBuilder.sentiment_hub_buy_confirm(
                    symbol="TOKEN",
                    address=address,
                    price=0.001,
                    auto_sl_percent=auto_sl_percent,
                    token_ref=token_ref,
                )
            else:
                return DemoMenuBuilder.error_message(
                    error="Invalid buy request",
                    retry_action="demo:hub",
                )
        except Exception as e:
            logger.error(f"Hub buy error: {e}")
            return DemoMenuBuilder.error_message(
                error=str(e),
                retry_action="demo:hub",
                context_hint="hub_buy",
            )

    elif data.startswith("demo:hub_custom:"):
        # Custom amount buy - show inline button grid (NO ForceReply)
        try:
            parts = data.split(":")
            token_ref = parts[2] if len(parts) > 2 else ""
            sl_percent = float(parts[3]) if len(parts) > 3 else 15.0
            address = ctx.resolve_token_ref(context, token_ref)
            
            # Get token symbol if possible
            symbol = "TOKEN"
            try:
                sentiment_data = await ctx.get_ai_sentiment_for_token(address)
                symbol = sentiment_data.get("symbol", "TOKEN")
            except:
                pass
            
            # Escape special markdown characters in symbol
            safe_symbol = symbol.replace("*", "\\*").replace("_", "\\_").replace("`", "\\`")
            
            text = f"""
{theme.COIN} *SELECT BUY AMOUNT*
{'=' * 24}

*Token:* {safe_symbol}
*Address:*
`{address}`

💰 *Choose SOL amount to buy:*
"""
            # Inline button grid for preset amounts - NO ForceReply
            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("0.05 SOL", callback_data=f"demo:hub_exec_buy:{token_ref}:0.05:{sl_percent}"),
                    InlineKeyboardButton("0.1 SOL", callback_data=f"demo:hub_exec_buy:{token_ref}:0.1:{sl_percent}"),
                ],
                [
                    InlineKeyboardButton("0.25 SOL", callback_data=f"demo:hub_exec_buy:{token_ref}:0.25:{sl_percent}"),
                    InlineKeyboardButton("0.5 SOL", callback_data=f"demo:hub_exec_buy:{token_ref}:0.5:{sl_percent}"),
                ],
                [
                    InlineKeyboardButton("1 SOL", callback_data=f"demo:hub_exec_buy:{token_ref}:1:{sl_percent}"),
                    InlineKeyboardButton("2 SOL", callback_data=f"demo:hub_exec_buy:{token_ref}:2:{sl_percent}"),
                ],
                [
                    InlineKeyboardButton(f"{theme.BACK} Back", callback_data="demo:hub_bluechips"),
                ],
            ])
            
            return text, keyboard
        except Exception as e:
            logger.error(f"Hub custom amount error: {e}")
            return DemoMenuBuilder.error_message(
                error=str(e),
                retry_action="demo:hub",
                context_hint="hub_custom",
            )

    elif data.startswith("demo:hub_detail:"):
        try:
            parts = data.split(":")
            token_ref = parts[2] if len(parts) > 2 else ""
            address = ctx.resolve_token_ref(context, token_ref)
            sentiment_data = await ctx.get_ai_sentiment_for_token(address)
            token_data = {
                "symbol": sentiment_data.get("symbol", "TOKEN"),
                "address": address,
                "token_id": token_ref,
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
            return DemoMenuBuilder.token_analysis_menu(token_data)
        except Exception as e:
            logger.error(f"Hub detail error: {e}")
            return DemoMenuBuilder.error_message(
                error=str(e),
                retry_action="demo:hub",
                context_hint="hub_detail",
            )

    elif data.startswith("demo:hub_custom_sl:"):
        try:
            parts = data.split(":")
            token_ref = parts[2] if len(parts) > 2 else ""
            text = f"""
{theme.WARNING} *CUSTOM STOP LOSS*
{'=' * 20}

Select your stop-loss %
for this trade:
"""
            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("SL -5%", callback_data=f"demo:hub_buy:{token_ref}:5"),
                    InlineKeyboardButton("SL -10%", callback_data=f"demo:hub_buy:{token_ref}:10"),
                ],
                [
                    InlineKeyboardButton("SL -15%", callback_data=f"demo:hub_buy:{token_ref}:15"),
                    InlineKeyboardButton("SL -20%", callback_data=f"demo:hub_buy:{token_ref}:20"),
                ],
                [
                    InlineKeyboardButton("SL -30%", callback_data=f"demo:hub_buy:{token_ref}:30"),
                ],
                [
                    InlineKeyboardButton(f"{theme.BACK} Back", callback_data=f"demo:hub_buy:{token_ref}:15"),
                ],
            ])
            return text, keyboard
        except Exception as e:
            logger.error(f"Hub custom SL error: {e}")
            return DemoMenuBuilder.error_message(
                error=str(e),
                retry_action="demo:hub",
                context_hint="hub_custom_sl",
            )

    elif data.startswith("demo:hub_exec_buy:"):
        try:
            parts = data.split(":")
            token_ref = parts[2] if len(parts) > 2 else ""
            address = ctx.resolve_token_ref(context, token_ref)
            amount_sol = float(parts[3]) if len(parts) > 3 else 0.1
            sl_percent = float(parts[4]) if len(parts) > 4 else 15.0

            engine = await ctx.get_demo_engine()
            portfolio = await engine.get_portfolio_value()
            if not portfolio:
                raise RuntimeError("Portfolio unavailable")
            balance_sol, balance_usd = portfolio
            if balance_sol <= 0:
                return DemoMenuBuilder.error_message("Treasury balance is zero.")

            sol_usd = balance_usd / balance_sol if balance_sol > 0 else 0
            amount_usd = amount_sol * sol_usd

            sentiment_data = await ctx.get_ai_sentiment_for_token(address)
            signal_name = sentiment_data.get("signal", "NEUTRAL")
            grade = ctx.grade_for_signal_name(signal_name)
            sentiment_score = sentiment_data.get("score", 0) or 0
            token_symbol = sentiment_data.get("symbol", "TOKEN")

            tp_percent = context.user_data.get("hub_tp_percent", 25.0)
            custom_tp = tp_percent / 100.0
            custom_sl = sl_percent / 100.0

            # ========== REAL BAGS.FM SWAP (not fake engine.open_position) ==========
            import uuid
            from core.trading.bags_client import BagsAPIClient
            from core.wallets.wallet_manager import get_treasury_keypair
            from bots.treasury.trading import TradeDirection, Position, TradeStatus

            SOL_MINT = "So11111111111111111111111111111111111111112"
            USER_WALLET = "BFhTj4TGKC77C7s3HLnLbCiVd6dXQSqGvtD8sJY5egVR"

            # Get keypair for signing
            user_keypair = get_treasury_keypair()
            if not user_keypair:
                return DemoMenuBuilder.error_message(
                    error="Treasury keypair not configured",
                    retry_action="demo:hub",
                )

            # Execute real swap via bags.fm
            bags = BagsAPIClient()
            swap_result = await bags.swap(
                from_token=SOL_MINT,
                to_token=address,
                amount=amount_sol,  # in SOL, not lamports
                wallet_address=USER_WALLET,
                slippage_bps=200,  # 2% slippage
                keypair=user_keypair,
            )

            if not swap_result.success:
                logger.error(f"Hub trade bags.fm swap failed: {swap_result.error}")
                return DemoMenuBuilder.error_message(
                    error=swap_result.error or "Swap failed",
                    retry_action="demo:hub",
                )

            # Real transaction hash from bags.fm
            real_tx_hash = swap_result.tx_hash
            logger.info(f"Hub trade bags.fm swap successful! TX: {real_tx_hash}")

            # Get current token price for position tracking
            current_price = await engine.jupiter.get_token_price(address)
            if current_price <= 0:
                current_price = swap_result.price if swap_result.price > 0 else 0.001

            # Calculate TP/SL prices
            tp_price = current_price * (1 + custom_tp)
            sl_price = current_price * (1 - custom_sl)

            # Create position record for tracking
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
                    entry_amount_sol=amount_sol,
                    entry_amount_tokens=token_amount,
                    take_profit_price=tp_price,
                    stop_loss_price=sl_price,
                    tx_signature=real_tx_hash,
                    user_id=user_id or 0,
                )
            except Exception as sk_err:
                logger.warning(f"Failed to track in scorekeeper: {sk_err}")

            # SUCCESS with REAL TX hash
            return DemoMenuBuilder.success_message(
                action="Hub Trade Executed",
                details=(
                    f"✅ Bought {token_symbol} with {amount_sol:.2f} SOL\n"
                    f"TP: +{tp_percent:.0f}% | SL: -{sl_percent:.0f}%\n"
                    f"TX: https://solscan.io/tx/{real_tx_hash}"
                ),
            )
        except Exception as e:
            logger.error(f"Hub exec buy error: {e}")
            return DemoMenuBuilder.error_message(
                error=str(e),
                retry_action="demo:hub",
                context_hint="hub_exec_buy",
            )

    # Handle hub section callbacks (demo:hub_bluechips, demo:hub_top10, etc.)
    elif data.startswith("demo:hub_"):
        section = action.replace("hub_", "")
        return await _handle_hub_section(ctx, section, context, market_regime)

    # Default
    return DemoMenuBuilder.sentiment_hub_main(
        market_regime=market_regime,
        last_report_time=datetime.now(timezone.utc),
        report_interval_minutes=15,
        wallet_connected=bool(context.user_data.get("wallet_address")),
    )


async def _handle_hub_section(ctx, section: str, context, market_regime: dict):
    """Handle hub section callbacks."""
    DemoMenuBuilder = ctx.DemoMenuBuilder

    try:
        # Fetch real data instead of using hardcoded mock data
        picks = []

        if section == "top10":
            # Get real AI conviction picks
            conviction_picks = await ctx.get_conviction_picks()
            picks = [
                {
                    "symbol": p.get("symbol", "???"),
                    "address": p.get("address", ""),
                    "price": p.get("entry_price", 0),
                    "change_24h": 0,  # Not available in conviction picks
                    "conviction": p.get("conviction", "MEDIUM"),
                    "tp_percent": p.get("tp_percent", 25),
                    "sl_percent": p.get("sl_percent", 15),
                    "score": int(p.get("score", 0)),
                }
                for p in conviction_picks[:10]  # Show all 10 picks
            ]
        elif section == "trending":
            # Get real trending tokens
            trending_tokens = await ctx.get_trending_with_sentiment()
            picks = [
                {
                    "symbol": t.get("symbol", "???"),
                    "address": t.get("address", ""),
                    "price": t.get("price_usd", 0),
                    "change_24h": t.get("change_24h", 0),
                    "conviction": "MEDIUM",  # Default conviction for trending
                    "tp_percent": 30,
                    "sl_percent": 15,
                    "score": int((t.get("sentiment_score", 0.5) or 0.5) * 100),
                }
                for t in trending_tokens[:10]
            ]
        elif section == "bluechips":
            # Top 10 Solana blue chips by volume and market cap
            # Includes DexTools links, market cap, sentiment
            picks = [
                {
                    "symbol": "SOL",
                    "address": "So11111111111111111111111111111111111111112",
                    "price": 225.50,
                    "change_24h": 2.5,
                    "conviction": "HIGH",
                    "tp_percent": 20,
                    "sl_percent": 10,
                    "score": 92,
                    "market_cap": 108_000_000_000,
                    "volume_24h": 4_500_000_000,
                    "sentiment": "VERY_BULLISH",
                    "dextools": "https://www.dextools.io/app/en/solana/pair-explorer/So11111111111111111111111111111111111111112",
                },
                {
                    "symbol": "JUP",
                    "address": "JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN",
                    "price": 1.25,
                    "change_24h": 5.2,
                    "conviction": "HIGH",
                    "tp_percent": 25,
                    "sl_percent": 12,
                    "score": 88,
                    "market_cap": 1_700_000_000,
                    "volume_24h": 180_000_000,
                    "sentiment": "BULLISH",
                    "dextools": "https://www.dextools.io/app/en/solana/pair-explorer/JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN",
                },
                {
                    "symbol": "RAY",
                    "address": "4k3Dyjzvzp8eMZWUXbBCjEvwSkkk59S5iCNLY3QrkX6R",
                    "price": 8.45,
                    "change_24h": 1.8,
                    "conviction": "HIGH",
                    "tp_percent": 20,
                    "sl_percent": 10,
                    "score": 85,
                    "market_cap": 2_200_000_000,
                    "volume_24h": 95_000_000,
                    "sentiment": "BULLISH",
                    "dextools": "https://www.dextools.io/app/en/solana/pair-explorer/4k3Dyjzvzp8eMZWUXbBCjEvwSkkk59S5iCNLY3QrkX6R",
                },
                {
                    "symbol": "BONK",
                    "address": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",
                    "price": 0.0000285,
                    "change_24h": 8.5,
                    "conviction": "MEDIUM",
                    "tp_percent": 35,
                    "sl_percent": 15,
                    "score": 82,
                    "market_cap": 1_900_000_000,
                    "volume_24h": 320_000_000,
                    "sentiment": "BULLISH",
                    "dextools": "https://www.dextools.io/app/en/solana/pair-explorer/DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",
                },
                {
                    "symbol": "WIF",
                    "address": "EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm",
                    "price": 2.85,
                    "change_24h": 12.3,
                    "conviction": "MEDIUM",
                    "tp_percent": 40,
                    "sl_percent": 18,
                    "score": 80,
                    "market_cap": 2_800_000_000,
                    "volume_24h": 450_000_000,
                    "sentiment": "VERY_BULLISH",
                    "dextools": "https://www.dextools.io/app/en/solana/pair-explorer/EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm",
                },
                {
                    "symbol": "PYTH",
                    "address": "HZ1JovNiVvGrGNiiYvEozEVgZ58xaU3RKwX8eACQBCt3",
                    "price": 0.48,
                    "change_24h": 3.2,
                    "conviction": "HIGH",
                    "tp_percent": 25,
                    "sl_percent": 12,
                    "score": 84,
                    "market_cap": 850_000_000,
                    "volume_24h": 75_000_000,
                    "sentiment": "BULLISH",
                    "dextools": "https://www.dextools.io/app/en/solana/pair-explorer/HZ1JovNiVvGrGNiiYvEozEVgZ58xaU3RKwX8eACQBCt3",
                },
                {
                    "symbol": "JTO",
                    "address": "jtojtomepa8beP8AuQc6eXt5FriJwfFMwQx2v2f9mCL",
                    "price": 3.65,
                    "change_24h": 4.8,
                    "conviction": "HIGH",
                    "tp_percent": 22,
                    "sl_percent": 10,
                    "score": 83,
                    "market_cap": 420_000_000,
                    "volume_24h": 55_000_000,
                    "sentiment": "BULLISH",
                    "dextools": "https://www.dextools.io/app/en/solana/pair-explorer/jtojtomepa8beP8AuQc6eXt5FriJwfFMwQx2v2f9mCL",
                },
                {
                    "symbol": "ORCA",
                    "address": "orcaEKTdK7LKz57vaAYr9QeNsVEPfiu6QeMU1kektZE",
                    "price": 5.20,
                    "change_24h": 2.1,
                    "conviction": "MEDIUM",
                    "tp_percent": 18,
                    "sl_percent": 10,
                    "score": 79,
                    "market_cap": 280_000_000,
                    "volume_24h": 28_000_000,
                    "sentiment": "NEUTRAL",
                    "dextools": "https://www.dextools.io/app/en/solana/pair-explorer/orcaEKTdK7LKz57vaAYr9QeNsVEPfiu6QeMU1kektZE",
                },
                {
                    "symbol": "RENDER",
                    "address": "rndrizKT3MK1iimdxRdWabcF7Zg7AR5T4nud4EkHBof",
                    "price": 8.95,
                    "change_24h": 6.7,
                    "conviction": "HIGH",
                    "tp_percent": 28,
                    "sl_percent": 12,
                    "score": 86,
                    "market_cap": 3_500_000_000,
                    "volume_24h": 185_000_000,
                    "sentiment": "BULLISH",
                    "dextools": "https://www.dextools.io/app/en/solana/pair-explorer/rndrizKT3MK1iimdxRdWabcF7Zg7AR5T4nud4EkHBof",
                },
                {
                    "symbol": "TENSOR",
                    "address": "TNSRxcUxoT9xBG3de7PiJyTDYu7kskLqcpddxnEJAS6",
                    "price": 1.15,
                    "change_24h": 9.4,
                    "conviction": "MEDIUM",
                    "tp_percent": 30,
                    "sl_percent": 15,
                    "score": 78,
                    "market_cap": 145_000_000,
                    "volume_24h": 22_000_000,
                    "sentiment": "BULLISH",
                    "dextools": "https://www.dextools.io/app/en/solana/pair-explorer/TNSRxcUxoT9xBG3de7PiJyTDYu7kskLqcpddxnEJAS6",
                },
            ]
        elif section in ("xstocks", "prestocks", "indexes"):
            picks = []  # Will be populated below

        # Try to fetch backed assets for xstocks/indexes
        if section in ("xstocks", "indexes"):
            try:
                from core.enhanced_market_data import fetch_backed_stocks, fetch_backed_indexes

                if section == "xstocks":
                    assets, warnings = await asyncio.to_thread(fetch_backed_stocks)
                else:
                    assets, warnings = await asyncio.to_thread(fetch_backed_indexes)

                if warnings:
                    logger.warning(f"Backed asset warnings: {warnings[:3]}")

                picks = [
                    {
                        "symbol": asset.symbol,
                        "address": asset.mint_address,
                        "price": asset.price_usd,
                        "change_24h": 0.0,
                        "conviction": "MEDIUM",
                        "tp_percent": 12,
                        "sl_percent": 8,
                        "score": 70,
                    }
                    for asset in assets
                ]
            except Exception as exc:
                logger.warning(f"Backed asset fetch failed for {section}: {exc}")

        for pick in picks:
            pick["token_id"] = ctx.register_token_id(context, pick.get("address"))

        return DemoMenuBuilder.sentiment_hub_section(
            section=section,
            picks=picks,
            market_regime=market_regime,
        )
    except Exception as e:
        logger.error(f"Hub section error: {e}")
        return DemoMenuBuilder.error_message(
            error=str(e),
            retry_action="demo:hub",
            context_hint="hub_section",
        )
