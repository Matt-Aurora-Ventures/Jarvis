"""
/analyze Command Handler.

Provides interactive token analysis with:
- Main analysis view with price, volume, sentiment
- Drill-down buttons for detailed views
- Session state management for navigation
"""

import logging
from typing import Optional

from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from tg_bot.handlers import error_handler, admin_only, rate_limited
from tg_bot.services.signal_service import get_signal_service
from tg_bot.sessions.session_manager import get_session_manager
from tg_bot.ui.inline_buttons import TokenAnalysisButtons
from tg_bot.ui.token_analysis_view import TokenAnalysisView

logger = logging.getLogger(__name__)

# Known token address mappings
KNOWN_TOKENS = {
    "SOL": "So11111111111111111111111111111111111111112",
    "BONK": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",
    "WIF": "EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm",
    "JUP": "JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN",
    "PYTH": "HZ1JovNiVvGrGNiiYvEozEVgZ58xaU3RKwX8eACQBCt3",
    "RAY": "4k3Dyjzvzp8eMZWUXbBCjEvwSkkk59S5iCNLY3QrkX6R",
    "ORCA": "orcaEKTdK7LKz57vaAYr9QeNsVEPfiu6QeMU1kektZE",
    "USDC": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
    "USDT": "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB",
}


def resolve_token_address(token: str) -> str:
    """
    Resolve token symbol or address to address.

    Args:
        token: Token symbol (e.g., SOL) or address

    Returns:
        Token address
    """
    upper = token.upper()
    if upper in KNOWN_TOKENS:
        return KNOWN_TOKENS[upper]
    return token


@error_handler
@admin_only
@rate_limited
async def analyze_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle /analyze command - interactive token analysis.

    Usage: /analyze SOL or /analyze <address>
    """
    if not context.args:
        await update.message.reply_text(
            "*Usage:* `/analyze <token>`\n\n"
            "*Examples:*\n"
            "`/analyze SOL` - Analyze Solana\n"
            "`/analyze BONK` - Analyze Bonk\n"
            "`/analyze <address>` - Analyze by address\n\n"
            "_This command provides interactive drill-down analysis._",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    token = context.args[0]
    address = resolve_token_address(token)
    symbol = token.upper() if token.upper() in KNOWN_TOKENS else ""

    # Send loading message
    loading_msg = await update.message.reply_text(
        f"_Analyzing {token}..._",
        parse_mode=ParseMode.MARKDOWN,
    )

    try:
        service = get_signal_service()
        signal = await service.get_comprehensive_signal(
            address,
            symbol=symbol,
            include_sentiment=True,
        )

        # Create session for drill-down
        user_id = update.effective_user.id if update.effective_user else 0
        if user_id:
            session_manager = get_session_manager()
            session_manager.create_session(
                user_id=user_id,
                token_address=address,
                token_symbol=signal.symbol or symbol or token,
                current_view="main",
            )

        # Format main view
        view = TokenAnalysisView()
        message = view.format_main_view(signal)

        # Build interactive keyboard
        buttons = TokenAnalysisButtons()
        keyboard = buttons.build_main_keyboard(address, signal.symbol or symbol)

        # Delete loading message and send analysis
        await loading_msg.delete()

        await update.message.reply_text(
            message,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard,
            disable_web_page_preview=True,
        )

    except Exception as e:
        logger.error(f"Analysis failed: {e}")
        await loading_msg.edit_text(
            f"*Analysis Error*\n\n_Failed to analyze {token}_\n\n`{str(e)[:100]}`",
            parse_mode=ParseMode.MARKDOWN,
        )


async def handle_analyze_callback(query, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle analyze drill-down callbacks.

    Callback formats:
    - analyze_chart:<address>
    - analyze_holders:<address>
    - analyze_signals:<address>
    - analyze_risk:<address>
    - analyze_community:<address>
    - analyze_back:<address>
    """
    try:
        await query.answer()
    except Exception:
        pass

    data = query.data
    user_id = query.from_user.id if query.from_user else 0

    # Parse callback data
    parts = data.split(":", 1)
    action = parts[0]
    token_address = parts[1] if len(parts) > 1 else ""

    session_manager = get_session_manager()
    view = TokenAnalysisView()
    buttons = TokenAnalysisButtons()

    try:
        if action == "analyze_chart":
            # Update session
            session_manager.update_session(user_id, current_view="chart")

            # Format chart view
            message = view.format_chart_view(token_address)
            keyboard = buttons.build_chart_keyboard(token_address)

            await query.message.edit_text(
                message,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=keyboard,
                disable_web_page_preview=True,
            )

        elif action == "analyze_holders":
            # Update session
            session_manager.update_session(user_id, current_view="holders")

            # Fetch holder data
            holders = await fetch_holder_data(token_address)
            total_pages = max(1, (len(holders) + 24) // 25)

            message = view.format_holders_view(token_address, holders[:25], page=1, total_pages=total_pages)
            keyboard = buttons.build_holders_keyboard(token_address, page=1, total_pages=total_pages)

            await query.message.edit_text(
                message,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=keyboard,
            )

        elif action == "analyze_signals":
            # Update session
            session_manager.update_session(user_id, current_view="signals")

            # Fetch signal data
            service = get_signal_service()
            signal = await service.get_comprehensive_signal(token_address, include_sentiment=True)

            message = view.format_signals_view(signal)
            keyboard = buttons.build_signals_keyboard(token_address)

            await query.message.edit_text(
                message,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=keyboard,
            )

        elif action == "analyze_risk":
            # Update session
            session_manager.update_session(user_id, current_view="risk")

            # Fetch signal data for risk info
            service = get_signal_service()
            signal = await service.get_comprehensive_signal(token_address, include_sentiment=False)

            message = view.format_risk_view(signal)
            keyboard = buttons.build_risk_keyboard(token_address)

            await query.message.edit_text(
                message,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=keyboard,
            )

        elif action == "analyze_community":
            # Update session
            session_manager.update_session(user_id, current_view="community")

            # Community view (placeholder)
            message = (
                "*Community Sentiment*\n\n"
                "_Community data aggregation coming soon._\n\n"
                "For now, check:\n"
                f"- [Twitter Search](https://twitter.com/search?q=${token_address[:8]})\n"
                f"- [Discord](https://discord.com)\n"
            )

            keyboard = buttons.build_main_keyboard(token_address, "")

            await query.message.edit_text(
                message,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=keyboard,
                disable_web_page_preview=True,
            )

        elif action == "analyze_back":
            # Update session back to main
            session_manager.update_session(user_id, current_view="main")

            # Fetch fresh data for main view
            service = get_signal_service()
            signal = await service.get_comprehensive_signal(
                token_address,
                include_sentiment=False,  # Don't use API on back
            )

            message = view.format_main_view(signal)
            keyboard = buttons.build_main_keyboard(token_address, signal.symbol)

            await query.message.edit_text(
                message,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=keyboard,
                disable_web_page_preview=True,
            )

        elif action == "ui_close":
            # Clear session
            session_manager.clear_session(user_id)

            try:
                await query.message.delete()
            except Exception:
                await query.message.edit_text(
                    "_Analysis closed._",
                    parse_mode=ParseMode.MARKDOWN,
                )

    except Exception as e:
        logger.error(f"Callback error: {e}")
        try:
            await query.message.edit_text(
                f"*Error*\n\n_Failed to load view_\n\n`{str(e)[:100]}`",
                parse_mode=ParseMode.MARKDOWN,
            )
        except Exception:
            pass


async def fetch_holder_data(token_address: str) -> list:
    """
    Fetch holder distribution data for a token.

    Returns list of holder entries with address, percentage, and amount.
    """
    try:
        # Import from existing module if available
        from tg_bot.handlers.analyze_drill_down import fetch_holder_data as _fetch
        return await _fetch(token_address)
    except ImportError:
        pass

    # Generate mock data
    import hashlib

    h = int(hashlib.md5(token_address.encode()).hexdigest()[:8], 16)

    holders = []
    remaining = 100.0

    for i in range(100):
        if remaining <= 0.01:
            break

        pct = min(remaining, max(0.01, remaining * (0.5 - i * 0.004)))
        remaining -= pct

        addr_seed = (h + i) % 0xFFFFFFFF
        mock_addr = f"0x{addr_seed:08x}...{(addr_seed ^ 0xFFFF):04x}"

        holders.append({
            "address": mock_addr,
            "percentage": round(pct, 2),
            "amount": int(pct * 1_000_000),
        })

    return holders


__all__ = [
    "analyze_command",
    "handle_analyze_callback",
    "resolve_token_address",
    "fetch_holder_data",
]
