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
import json
import hashlib
import os
import tempfile
import time
from pathlib import Path
from typing import Optional, Tuple, Dict, Any, List
from decimal import Decimal
from datetime import datetime, timezone, timedelta
from io import BytesIO

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import BadRequest

# Chart generation imports (optional - fallback if not available)
try:
    import matplotlib
    matplotlib.use('Agg')  # Non-interactive backend for servers
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    logging.warning("Matplotlib not available - chart features disabled")
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from tg_bot.config import get_config
from tg_bot.handlers import error_handler, admin_only
from tg_bot.services.digest_formatter import escape_markdown_v1 as escape_md

logger = logging.getLogger(__name__)

DEMO_PROFILE = (os.environ.get("DEMO_TRADING_PROFILE", "demo") or "demo").strip().lower()
DEMO_DEFAULT_SLIPPAGE_BPS = 100  # 1% default, override via env


# =============================================================================
# Symbol Sanitization (Bug Fix US-033)
# =============================================================================

def safe_symbol(symbol: str) -> str:
    """
    Sanitize token symbol for safe display in Telegram messages.

    Removes special characters that could break Telegram Markdown formatting
    or cause display issues. Only allows alphanumeric, hyphen, and underscore.

    Args:
        symbol: Raw token symbol (may contain special chars)

    Returns:
        Sanitized symbol, uppercase, max 10 chars. Returns "UNKNOWN" if empty.
    """
    if not symbol:
        return "UNKNOWN"
    # Keep only alphanumeric, hyphen, and underscore
    sanitized = ''.join(c for c in str(symbol) if c.isalnum() or c in ['_', '-'])
    # Truncate to 10 chars and uppercase
    return sanitized[:10].upper() if sanitized else "UNKNOWN"


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
        return _get_bags(profile=DEMO_PROFILE)
    except ImportError:
        logger.warning("Bags client not available")
        return None


_JUPITER_CLIENT = None


def _get_demo_slippage_bps() -> int:
    """Resolve slippage for demo swaps (basis points)."""
    raw_bps = os.environ.get("DEMO_SWAP_SLIPPAGE_BPS")
    if raw_bps:
        try:
            return max(1, int(float(raw_bps)))
        except ValueError:
            pass
    raw_pct = os.environ.get("DEMO_SWAP_SLIPPAGE_PCT")
    if raw_pct:
        try:
            return max(1, int(float(raw_pct) * 100))
        except ValueError:
            pass
    return DEMO_DEFAULT_SLIPPAGE_BPS


def _get_jupiter_client():
    """Lazy Jupiter client init for fallback swaps."""
    global _JUPITER_CLIENT
    if _JUPITER_CLIENT is None:
        from bots.treasury.jupiter import JupiterClient
        _JUPITER_CLIENT = JupiterClient()
    return _JUPITER_CLIENT


def _load_demo_wallet(wallet_address: Optional[str] = None):
    """Load secure wallet for demo trading (required for Jupiter fallback)."""
    try:
        from bots.treasury.wallet import SecureWallet
        wallet_password = _get_demo_wallet_password()
        if not wallet_password:
            return None
        wallet = SecureWallet(
            master_password=wallet_password,
            wallet_dir=_get_demo_wallet_dir(),
        )
        if wallet_address:
            try:
                wallet.set_active(wallet_address)
            except Exception:
                # Ignore if address isn't registered; treasury wallet may still exist
                pass
        return wallet
    except Exception as exc:
        logger.warning(f"Demo wallet unavailable: {exc}")
        return None


async def _get_token_decimals(mint: str, jupiter) -> int:
    if mint == "So11111111111111111111111111111111111111112":
        return 9
    try:
        info = await jupiter.get_token_info(mint)
        if info and getattr(info, "decimals", None) is not None:
            return int(info.decimals)
    except Exception:
        pass
    return 6


async def _to_base_units(mint: str, amount: float, jupiter) -> int:
    decimals = await _get_token_decimals(mint, jupiter)
    return int(float(amount) * (10 ** decimals))


async def _from_base_units(mint: str, amount: int, jupiter) -> float:
    decimals = await _get_token_decimals(mint, jupiter)
    return float(amount) / (10 ** decimals)


# =============================================================================
# Sentiment Data Cache (US-008: 15-Minute Update Cycle)
# =============================================================================

_SENTIMENT_CACHE = {"tokens": [], "last_update": None, "macro": {}}
_SENTIMENT_LOCK = asyncio.Lock()


async def _update_sentiment_cache(context: Any = None) -> None:
    """
    Update sentiment data cache from sentiment_report_data.json.

    US-008: This function is called every 15 minutes to refresh the cached
    sentiment data displayed in the demo bot.

    Data source: bots/twitter/sentiment_report_data.json (updated by sentiment_report.py)
    """
    async with _SENTIMENT_LOCK:
        try:
            sentiment_file = Path(__file__).resolve().parents[2] / "bots" / "twitter" / "sentiment_report_data.json"
            if not sentiment_file.exists():
                logger.debug("Sentiment report data not available yet")
                return

            with open(sentiment_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            _SENTIMENT_CACHE["tokens"] = data.get("tokens_raw", [])
            _SENTIMENT_CACHE["last_update"] = datetime.now(timezone.utc)
            _SENTIMENT_CACHE["macro"] = {
                "stocks": data.get("stocks", ""),
                "commodities": data.get("commodities", ""),
                "metals": data.get("metals", ""),
                "solana": data.get("solana", ""),
            }

            logger.info(f"Sentiment cache updated: {len(_SENTIMENT_CACHE['tokens'])} tokens")

        except Exception as e:
            logger.warning(f"Failed to update sentiment cache: {e}")


def get_cached_sentiment_tokens() -> List[Dict[str, Any]]:
    """Get cached sentiment tokens (updated every 15 min)."""
    return _SENTIMENT_CACHE.get("tokens", [])


def get_cached_macro_sentiment() -> Dict[str, str]:
    """Get cached macro sentiment data."""
    return _SENTIMENT_CACHE.get("macro", {})


def get_sentiment_cache_age() -> Optional[timedelta]:
    """Get age of sentiment cache."""
    last_update = _SENTIMENT_CACHE.get("last_update")
    if not last_update:
        return None
    return datetime.now(timezone.utc) - last_update


# =============================================================================
# TP/SL Background Monitoring (US-006)
# =============================================================================

async def _background_tp_sl_monitor(context: Any) -> None:
    """
    Background job to monitor TP/SL triggers for all users.

    US-006: This runs every 5 minutes to check if any positions have hit
    their take-profit or stop-loss levels and auto-executes exits.

    Note: Individual callbacks also run exit checks for real-time responsiveness.
    """
    try:
        # Note: context.application.user_data is a mapping of user_id -> user_data
        # We need to iterate through all users' positions
        if not context or not hasattr(context, 'application'):
            return

        user_data_dict = getattr(context.application, 'user_data', {})
        if not user_data_dict:
            return

        checked_count = 0
        triggered_count = 0

        for user_id, user_data in user_data_dict.items():
            positions = user_data.get("positions", [])
            if not positions:
                continue

            checked_count += 1

            try:
                alerts = await asyncio.wait_for(
                    _check_demo_exit_triggers(user_data, positions),
                    timeout=2.0,
                )
            except asyncio.TimeoutError:
                logger.warning(f"TP/SL check timed out for user {user_id}")
                continue

            if not alerts:
                continue

            triggered_count += len(alerts)
            closed_ids: List[str] = []

            for alert in alerts:
                try:
                    executed = await asyncio.wait_for(
                        _maybe_execute_exit(user_data, alert),
                        timeout=5.0,
                    )
                except asyncio.TimeoutError:
                    logger.warning(f"TP/SL auto-exit timed out for user {user_id}")
                    continue
                except Exception as exc:
                    logger.warning(f"TP/SL auto-exit failed for user {user_id}: {exc}")
                    continue

                position = alert.get("position", {})
                if executed and position.get("id"):
                    closed_ids.append(position.get("id"))

                # Send alert to user
                try:
                    message = _format_exit_alert_message(alert, executed)
                    await context.bot.send_message(
                        chat_id=user_id,
                        text=message,
                        parse_mode=ParseMode.MARKDOWN,
                    )
                except Exception as exc:
                    logger.debug(f"Failed to send TP/SL alert to user {user_id}: {exc}")

            # Update positions after exits
            if closed_ids:
                user_data["positions"] = [
                    p for p in positions if p.get("id") not in closed_ids
                ]
                trailing_stops = user_data.get("trailing_stops", [])
                if trailing_stops:
                    user_data["trailing_stops"] = [
                        s for s in trailing_stops if s.get("position_id") not in closed_ids
                    ]

        if checked_count > 0:
            logger.info(f"TP/SL monitor: checked {checked_count} users, {triggered_count} triggers")

    except Exception as exc:
        logger.warning(f"Background TP/SL monitor failed: {exc}")


async def _execute_swap_with_fallback(
    *,
    from_token: str,
    to_token: str,
    amount: float,
    wallet_address: str,
    slippage_bps: int,
) -> Dict[str, Any]:
    """Execute swap via Bags.fm with Jupiter fallback."""
    last_error = None

    bags_client = get_bags_client()
    if bags_client and getattr(bags_client, "api_key", None) and getattr(bags_client, "partner_key", None):
        try:
            bags_result = await bags_client.swap(
                from_token=from_token,
                to_token=to_token,
                amount=amount,
                wallet_address=wallet_address,
                slippage_bps=slippage_bps,
            )
            if bags_result and bags_result.success:
                return {
                    "success": True,
                    "source": "bags_fm",
                    "tx_hash": bags_result.tx_hash,
                    "amount_out": bags_result.to_amount,
                }
            last_error = getattr(bags_result, "error", None) or "Bags.fm swap failed"
        except Exception as exc:
            last_error = str(exc)

    # Jupiter fallback
    try:
        jupiter = _get_jupiter_client()
        wallet = _load_demo_wallet(wallet_address)
        if not wallet:
            return {
                "success": False,
                "error": last_error or "Wallet not configured for Jupiter fallback",
            }

        amount_base = await _to_base_units(from_token, amount, jupiter)
        quote = await jupiter.get_quote(
            input_mint=from_token,
            output_mint=to_token,
            amount=amount_base,
            slippage_bps=slippage_bps,
        )
        if not quote:
            return {"success": False, "error": last_error or "Jupiter quote failed"}
        jup_result = await jupiter.execute_swap(quote, wallet)
        if jup_result and getattr(jup_result, "success", False):
            amount_out_ui = await _from_base_units(
                to_token,
                getattr(jup_result, "output_amount", 0),
                jupiter,
            )
            return {
                "success": True,
                "source": "jupiter",
                "tx_hash": getattr(jup_result, "signature", None),
                "amount_out": amount_out_ui,
            }
        return {
            "success": False,
            "error": getattr(jup_result, "error", None) or last_error or "Jupiter swap failed",
        }
    except Exception as exc:
        return {"success": False, "error": last_error or str(exc)}


async def execute_buy_with_tpsl(
    token_address: str,
    amount_sol: float,
    wallet_address: str,
    tp_percent: float = 50.0,
    sl_percent: float = 20.0,
    slippage_bps: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Execute a buy order with TP/SL via Bags.fm with Jupiter fallback.

    US-005: Dual execution with default TP/SL values.

    This function:
    1. Tries Bags.fm first for partner fee collection
    2. Falls back to Jupiter on Bags.fm failure
    3. Creates a position with TP/SL metadata

    Args:
        token_address: Token mint address to buy
        amount_sol: Amount of SOL to spend
        wallet_address: User's wallet address
        tp_percent: Take-profit percentage (default 50%)
        sl_percent: Stop-loss percentage (default 20%)
        slippage_bps: Slippage in basis points (default from env)

    Returns:
        Dict with:
            - success: bool
            - position: Position dict with TP/SL (on success)
            - error: Error message (on failure)

    Example:
        result = await execute_buy_with_tpsl(
            token_address="TokenMint...",
            amount_sol=0.5,
            wallet_address="WalletAddr...",
            tp_percent=100.0,  # 2x
            sl_percent=25.0,   # -25%
        )
        if result["success"]:
            position = result["position"]
            print(f"Bought {position['symbol']} with TP at {position['tp_price']}")
    """
    import uuid

    if slippage_bps is None:
        slippage_bps = _get_demo_slippage_bps()

    # Get token info for the position
    try:
        sentiment_data = await get_ai_sentiment_for_token(token_address)
        token_symbol = sentiment_data.get("symbol", "TOKEN")
        token_price = float(sentiment_data.get("price", 0) or 0)
    except Exception as e:
        logger.warning(f"Failed to get token info: {e}")
        token_symbol = "UNKNOWN"
        token_price = 0.0

    # Execute swap via Bags.fm with Jupiter fallback
    swap = await _execute_swap_with_fallback(
        from_token="So11111111111111111111111111111111111111112",  # SOL
        to_token=token_address,
        amount=amount_sol,
        wallet_address=wallet_address,
        slippage_bps=slippage_bps,
    )

    if not swap.get("success"):
        return {
            "success": False,
            "error": swap.get("error", "Swap failed"),
        }

    # Calculate tokens received
    tokens_received = swap.get("amount_out")
    if not tokens_received and token_price > 0:
        # Estimate based on SOL price (~$225) if not returned
        tokens_received = (amount_sol * 225) / token_price

    # Calculate TP/SL prices
    tp_price = token_price * (1 + tp_percent / 100) if token_price > 0 else 0
    sl_price = token_price * (1 - sl_percent / 100) if token_price > 0 else 0

    # Create position with TP/SL
    position = {
        "id": f"buy_{uuid.uuid4().hex[:8]}",
        "symbol": token_symbol,
        "address": token_address,
        "amount": tokens_received or 0,
        "amount_sol": amount_sol,
        "entry_price": token_price,
        "current_price": token_price,
        "tp_percent": tp_percent,
        "sl_percent": sl_percent,
        "tp_price": tp_price,
        "sl_price": sl_price,
        "source": swap.get("source", "bags_api"),
        "tx_hash": swap.get("tx_hash"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    return {
        "success": True,
        "position": position,
        "tx_hash": swap.get("tx_hash"),
        "source": swap.get("source"),
    }


def _exit_checks_enabled() -> bool:
    return os.environ.get("DEMO_EXIT_CHECKS", "1").strip().lower() not in ("0", "false", "off")


def _auto_exit_enabled(context: ContextTypes.DEFAULT_TYPE) -> bool:
    if os.environ.get("DEMO_TPSL_AUTO_EXECUTE", "1").strip().lower() in ("0", "false", "off"):
        return False
    return bool(context.user_data.get("ai_auto_trade", False))


def _get_exit_check_interval_seconds() -> int:
    raw = os.environ.get("DEMO_EXIT_CHECK_INTERVAL_SECONDS", "30")
    try:
        return max(5, int(float(raw)))
    except ValueError:
        return 30


def _should_run_exit_checks(context: ContextTypes.DEFAULT_TYPE) -> bool:
    if not _exit_checks_enabled():
        return False
    positions = context.user_data.get("positions", [])
    if not positions:
        return False
    interval = _get_exit_check_interval_seconds()
    now = time.time()
    last = context.user_data.get("last_exit_check_ts")
    if last and (now - last) < interval:
        return False
    context.user_data["last_exit_check_ts"] = now
    return True


async def _check_demo_exit_triggers(
    context: ContextTypes.DEFAULT_TYPE,
    positions: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Check TP/SL/trailing stops for demo positions."""
    if not positions or not _exit_checks_enabled():
        return []

    alerts: List[Dict[str, Any]] = []
    jupiter = _get_jupiter_client()
    trailing_stops = context.user_data.get("trailing_stops", [])

    for pos in positions:
        token_mint = pos.get("address")
        entry_price = float(pos.get("entry_price", 0) or 0)
        current_price = float(pos.get("current_price", 0) or 0)
        if not current_price and token_mint:
            try:
                current_price = await jupiter.get_token_price(token_mint)
                pos["current_price"] = current_price
            except Exception:
                continue

        if entry_price <= 0 or current_price <= 0:
            continue

        tp_pct = pos.get("tp_percent", pos.get("take_profit"))
        sl_pct = pos.get("sl_percent", pos.get("stop_loss"))
        if tp_pct is not None:
            tp_price = entry_price * (1 + float(tp_pct) / 100)
            if current_price >= tp_price and not pos.get("tp_triggered"):
                pos["tp_triggered"] = True
                alerts.append({"type": "take_profit", "position": pos, "price": current_price})
        if sl_pct is not None:
            sl_price = entry_price * (1 - float(sl_pct) / 100)
            if current_price <= sl_price and not pos.get("sl_triggered"):
                pos["sl_triggered"] = True
                alerts.append({"type": "stop_loss", "position": pos, "price": current_price})

    # Update trailing stops
    for stop in trailing_stops:
        if not stop.get("active", True):
            continue
        pos_id = stop.get("position_id")
        position = next((p for p in positions if p.get("id") == pos_id), None)
        if not position:
            continue
        current_price = float(position.get("current_price", 0) or 0)
        if current_price <= 0:
            continue
        highest = float(stop.get("highest_price", 0) or 0)
        trail_pct = float(stop.get("trail_percent", 10) or 10) / 100
        if current_price > highest:
            highest = current_price
            stop["highest_price"] = highest
            stop["current_stop_price"] = highest * (1 - trail_pct)
        current_stop = float(stop.get("current_stop_price", 0) or 0)
        if current_stop and current_price <= current_stop and not stop.get("triggered"):
            stop["triggered"] = True
            stop["active"] = False
            alerts.append({"type": "trailing_stop", "position": position, "price": current_price})

    context.user_data["trailing_stops"] = trailing_stops
    return alerts


async def _maybe_execute_exit(
    context: ContextTypes.DEFAULT_TYPE,
    alert: Dict[str, Any],
) -> bool:
    """Execute an auto-exit if enabled. Returns True if position closed."""
    if not _auto_exit_enabled(context):
        return False

    position = alert.get("position", {})
    token_mint = position.get("address")
    token_amount = position.get("amount", 0)
    wallet_address = context.user_data.get("wallet_address", "demo_wallet")
    slippage_bps = _get_demo_slippage_bps()
    swap = await _execute_swap_with_fallback(
        from_token=token_mint,
        to_token="So11111111111111111111111111111111111111112",
        amount=token_amount,
        wallet_address=wallet_address,
        slippage_bps=slippage_bps,
    )
    if swap.get("success"):
        position["closed_at"] = datetime.now(timezone.utc).isoformat()
        position["exit_tx"] = swap.get("tx_hash")
        position["exit_source"] = swap.get("source")
        position["exit_reason"] = alert.get("type")
        return True
    return False


def _format_exit_alert_message(alert: Dict[str, Any], auto_executed: bool) -> str:
    position = alert.get("position", {})
    symbol = escape_md(position.get("symbol", "TOKEN"))
    entry_price = float(position.get("entry_price", 0) or 0)
    current_price = float(alert.get("price", 0) or position.get("current_price", 0) or 0)
    alert_type = alert.get("type", "alert")

    reason_map = {
        "take_profit": "🎯 Take-profit hit",
        "stop_loss": "🛑 Stop-loss hit",
        "trailing_stop": "🛡️ Trailing stop hit",
    }
    reason = reason_map.get(alert_type, "⚠️ Exit alert")

    lines = [f"{reason} — *{symbol}*"]
    if entry_price:
        lines.append(f"Entry: ${entry_price:.6f}")
    if current_price:
        lines.append(f"Now: ${current_price:.6f}")
    if entry_price and current_price:
        pnl_pct = ((current_price - entry_price) / entry_price) * 100
        lines.append(f"P&L: {pnl_pct:+.1f}%")

    if auto_executed:
        source = position.get("exit_source", "swap")
        tx_hash = position.get("exit_tx")
        tx_display = f"{tx_hash[:8]}...{tx_hash[-8:]}" if tx_hash else "N/A"
        lines.append(f"Auto-exit: {source}")
        lines.append(f"TX: {tx_display}")
    else:
        lines.append("_Auto-exit disabled — review position._")

    return "\n".join(lines)


async def _process_demo_exit_checks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Run TP/SL/trailing checks with throttling and optional auto-exit."""
    try:
        if not _should_run_exit_checks(context):
            return

        positions = context.user_data.get("positions", [])
        if not positions:
            return

        try:
            alerts = await asyncio.wait_for(
                _check_demo_exit_triggers(context, positions),
                timeout=2.0,
            )
        except asyncio.TimeoutError:
            logger.warning("Demo exit checks timed out")
            return

        if not alerts:
            return

        closed_ids: List[str] = []
        chat_id = update.effective_chat.id if update and update.effective_chat else None

        for alert in alerts:
            executed = False
            try:
                executed = await asyncio.wait_for(
                    _maybe_execute_exit(context, alert),
                    timeout=5.0,
                )
            except asyncio.TimeoutError:
                logger.warning("Demo auto-exit timed out")
            except Exception as exc:
                logger.warning(f"Demo auto-exit failed: {exc}")

            position = alert.get("position", {})
            if executed and position.get("id"):
                closed_ids.append(position.get("id"))

            if chat_id:
                message = _format_exit_alert_message(alert, executed)
                try:
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text=message,
                        parse_mode=ParseMode.MARKDOWN,
                    )
                except Exception as exc:
                    logger.warning(f"Failed to send demo exit alert: {exc}")

        if closed_ids:
            context.user_data["positions"] = [
                p for p in positions if p.get("id") not in closed_ids
            ]
            trailing_stops = context.user_data.get("trailing_stops", [])
            if trailing_stops:
                context.user_data["trailing_stops"] = [
                    s for s in trailing_stops if s.get("position_id") not in closed_ids
                ]
        else:
            context.user_data["positions"] = positions

    except Exception as exc:
        logger.warning(f"Exit check processing failed: {exc}")

def get_success_fee_manager():
    """Get Success Fee Manager for 0.5% fee on winning trades."""
    try:
        from core.trading.bags_client import get_success_fee_manager as _get_fee_manager
        return _get_fee_manager(profile=DEMO_PROFILE)
    except ImportError:
        logger.warning("Success fee manager not available")
        return None


def _register_token_id(context, token_address: str) -> str:
    """Register a short callback-safe token id for a given address."""
    if not token_address:
        return ""
    token_map = context.user_data.setdefault("token_id_map", {})
    reverse_map = context.user_data.setdefault("token_id_reverse", {})
    if token_address in reverse_map:
        return reverse_map[token_address]
    token_id = hashlib.sha1(token_address.encode("utf-8")).hexdigest()[:10]
    token_map[token_id] = token_address
    reverse_map[token_address] = token_id
    return token_id


def _resolve_token_ref(context, token_ref: str) -> str:
    """Resolve short token id back to full address (fallback to ref)."""
    if not token_ref:
        return token_ref
    if len(token_ref) >= 32:
        return token_ref
    return context.user_data.get("token_id_map", {}).get(token_ref, token_ref)


def generate_price_chart(
    prices: List[float],
    timestamps: Optional[List[datetime]] = None,
    symbol: str = "TOKEN",
    timeframe: str = "24H",
    volume: Optional[List[float]] = None,
) -> Optional[BytesIO]:
    """
    Generate a price chart image using matplotlib.

    Args:
        prices: List of price values
        timestamps: List of datetime objects (optional, uses indices if not provided)
        symbol: Token symbol for chart title
        timeframe: Timeframe label (e.g., "24H", "7D", "1M")
        volume: Optional volume data for subplot

    Returns:
        BytesIO buffer containing PNG image, or None if matplotlib unavailable
    """
    if not MATPLOTLIB_AVAILABLE:
        logger.warning("Cannot generate chart - matplotlib not available")
        return None

    if not prices:
        logger.warning("Cannot generate chart - no price data")
        return None

    try:
        # Create figure with optional volume subplot
        if volume:
            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 7),
                                           gridspec_kw={'height_ratios': [3, 1]})
        else:
            fig, ax1 = plt.subplots(figsize=(10, 6))

        # Use timestamps if provided, otherwise use indices
        x_data = timestamps if timestamps else list(range(len(prices)))

        # Plot price line
        ax1.plot(x_data, prices, color='#00D4AA', linewidth=2, label='Price')
        ax1.fill_between(x_data, prices, alpha=0.1, color='#00D4AA')
        ax1.set_title(f'{symbol} Price Chart ({timeframe})', fontsize=14, fontweight='bold')
        ax1.set_ylabel('Price (USD)', fontsize=11)
        ax1.grid(True, alpha=0.3, linestyle='--')
        ax1.legend(loc='upper left')

        # Format x-axis for timestamps
        if timestamps:
            ax1.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
            plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45)

        # Plot volume if provided
        if volume and volume:
            ax2.bar(x_data, volume, color='#4A90E2', alpha=0.6)
            ax2.set_ylabel('Volume', fontsize=11)
            ax2.set_xlabel('Time', fontsize=11)
            ax2.grid(True, alpha=0.3, linestyle='--')
            if timestamps:
                ax2.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
                plt.setp(ax2.xaxis.get_majorticklabels(), rotation=45)

        # Styling
        fig.patch.set_facecolor('#1E1E1E')
        ax1.set_facecolor('#2C2C2C')
        ax1.spines['top'].set_visible(False)
        ax1.spines['right'].set_visible(False)
        ax1.tick_params(colors='white')
        ax1.yaxis.label.set_color('white')
        ax1.title.set_color('white')

        if volume:
            ax2.set_facecolor('#2C2C2C')
            ax2.spines['top'].set_visible(False)
            ax2.spines['right'].set_visible(False)
            ax2.tick_params(colors='white')
            ax2.yaxis.label.set_color('white')
            ax2.xaxis.label.set_color('white')

        plt.tight_layout()

        # Save to BytesIO buffer
        buf = BytesIO()
        plt.savefig(buf, format='png', dpi=100, facecolor=fig.get_facecolor())
        buf.seek(0)
        plt.close(fig)

        return buf
    except Exception as e:
        logger.error(f"Error generating chart: {e}")
        plt.close('all')  # Clean up on error
        return None


def _get_demo_wallet_password() -> Optional[str]:
    """Resolve demo wallet password with fallback to treasury envs."""
    candidates = (
        "DEMO_TREASURY_WALLET_PASSWORD",
        "DEMO_WALLET_PASSWORD",
        "DEMO_JARVIS_WALLET_PASSWORD",
        "TREASURY_WALLET_PASSWORD",
        "JARVIS_WALLET_PASSWORD",
        "WALLET_PASSWORD",
    )
    for key in candidates:
        value = os.environ.get(key)
        if value:
            return value
    return None


def _get_demo_wallet_dir() -> Path:
    """Resolve wallet directory for demo profile."""
    custom_dir = os.environ.get("DEMO_WALLET_DIR", "").strip()
    if custom_dir:
        return Path(custom_dir).expanduser()
    root = Path(__file__).resolve().parents[2]
    return root / "bots" / "treasury" / f".wallets-{DEMO_PROFILE}"


async def _get_demo_engine():
    """Get demo trading engine (separate keys/state from treasury)."""
    from tg_bot import bot_core as bot_module
    try:
        return await bot_module._get_treasury_engine(profile=DEMO_PROFILE)
    except RuntimeError as exc:
        fallback_profile = (os.environ.get("DEMO_FALLBACK_PROFILE", "treasury") or "treasury").strip().lower()
        if fallback_profile and fallback_profile != DEMO_PROFILE:
            logger.warning(
                "Demo engine unavailable (%s). Falling back to '%s' profile.",
                exc,
                fallback_profile,
            )
            return await bot_module._get_treasury_engine(profile=fallback_profile)
        raise


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
        # Try cached regime from sentiment engine (if available)
        try:
            from core.caching.sentiment_cache import get_sentiment_cache
            cache = get_sentiment_cache()
            cached = await cache.get_market_regime()
            if cached:
                return cached
        except Exception as e:
            logger.warning(f"Could not load cached regime: {e}")

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
            "symbol": signal.symbol,
            "price": signal.price_usd,
            "change_24h": signal.price_change_24h,
            "volume": signal.volume_24h,
            "liquidity": signal.liquidity_usd,
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

    # Fallback to Bags token info if signal service is unavailable
    try:
        bags_client = get_bags_client()
        if bags_client:
            token = await bags_client.get_token_info(address)
            if token:
                return {
                    "symbol": token.symbol or address[:6],
                    "price": token.price_usd,
                    "change_24h": token.price_change_24h,
                    "volume": token.volume_24h,
                    "liquidity": token.liquidity,
                    "sentiment": "neutral",
                    "score": 0.5,
                    "confidence": 0.0,
                    "summary": "Bags price data",
                    "signal": "NEUTRAL",
                    "signal_score": 0.5,
                    "reasons": ["Bags fallback"],
                }
    except Exception as e:
        logger.warning(f"Could not get Bags fallback sentiment: {e}")

    # Fallback to Jupiter/DexScreener token data for price + symbol
    try:
        from bots.treasury.jupiter import JupiterClient
        jupiter = JupiterClient()
        token = await jupiter.get_token_info(address)
        if token:
            return {
                "symbol": token.symbol or address[:6],
                "price": token.price_usd,
                "change_24h": getattr(token, "price_change_24h", 0),
                "volume": getattr(token, "volume_24h", 0),
                "liquidity": getattr(token, "liquidity", 0),
                "sentiment": "neutral",
                "score": 0.5,
                "confidence": 0.0,
                "summary": "Jupiter/Dex fallback",
                "signal": "NEUTRAL",
                "signal_score": 0.5,
                "reasons": ["Jupiter fallback"],
            }
    except Exception as e:
        logger.warning(f"Could not get Jupiter fallback sentiment: {e}")

    return {"sentiment": "unknown", "score": 0, "confidence": 0}


async def get_trending_with_sentiment(limit: int = 15) -> List[Dict[str, Any]]:
    """Get trending tokens with AI sentiment overlay."""
    try:
        from tg_bot.services.signal_service import get_signal_service
        service = get_signal_service()
        signals = await service.get_trending_tokens(limit=limit)
        if signals:
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

    # DexScreener fallback - reliable trending token data
    try:
        from core.dexscreener import get_solana_trending
        dex_tokens = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: get_solana_trending(
                min_liquidity=10_000,
                min_volume_24h=50_000,
                limit=limit
            )
        )
        if dex_tokens:
            return [
                {
                    "symbol": t.base_token_symbol,
                    "address": t.base_token_address,
                    "price_usd": t.price_usd,
                    "change_24h": t.price_change_24h,
                    "volume": t.volume_24h,
                    "liquidity": t.liquidity_usd,
                    "sentiment": "neutral",  # No AI sentiment in fallback
                    "sentiment_score": 0.5,
                    "signal": "NEUTRAL",
                    "chart_url": f"https://dexscreener.com/solana/{t.base_token_address}",
                }
                for t in dex_tokens
            ]
    except Exception as e:
        logger.warning(f"Could not get DexScreener trending fallback: {e}")
    return []


def _conviction_label(score: float) -> str:
    if score >= 80:
        return "HIGH"
    if score >= 60:
        return "MEDIUM"
    return "LOW"


def _default_tp_sl(conviction: str) -> Tuple[int, int]:
    if conviction == "HIGH":
        return 30, 12
    if conviction == "MEDIUM":
        return 22, 12
    return 15, 15


def _grade_for_signal_name(signal_name: str) -> str:
    mapping = {
        "STRONG_BUY": "A",
        "BUY": "B+",
        "NEUTRAL": "C+",
        "SELL": "C",
        "STRONG_SELL": "C",
        "AVOID": "C",
    }
    return mapping.get((signal_name or "").upper(), "B")


def _pick_key(pick: Dict[str, Any]) -> str:
    address = (pick.get("address") or "").lower().strip()
    if address:
        return address
    return (pick.get("symbol") or "").lower().strip()


def _load_treasury_top_picks(limit: int = 5) -> List[Dict[str, Any]]:
    try:
        picks_file = Path(tempfile.gettempdir()) / "jarvis_top_picks.json"
        if not picks_file.exists():
            return []
        with open(picks_file, "r") as handle:
            data = json.load(handle) or []
        picks = []
        for entry in data[:limit]:
            symbol = entry.get("symbol", "???")
            address = entry.get("contract") or ""
            conviction_score = float(entry.get("conviction", 0) or 0)
            conviction = _conviction_label(conviction_score)
            entry_price = float(entry.get("entry_price", 0) or 0)
            target_price = float(entry.get("target_price", 0) or 0)
            stop_loss = float(entry.get("stop_loss", 0) or 0)
            tp_pct = 0
            sl_pct = 0
            if entry_price > 0 and target_price > 0:
                tp_pct = int(round(((target_price - entry_price) / entry_price) * 100))
            if entry_price > 0 and stop_loss > 0:
                sl_pct = int(round(((entry_price - stop_loss) / entry_price) * 100))
            if not tp_pct or not sl_pct:
                tp_pct, sl_pct = _default_tp_sl(conviction)
            picks.append({
                "symbol": symbol,
                "address": address,
                "conviction": conviction,
                "thesis": entry.get("reasoning", ""),
                "entry_price": entry_price,
                "tp_target": tp_pct,
                "sl_target": sl_pct,
                "source": "treasury",
                "conviction_score": conviction_score,
            })
        return picks
    except Exception as e:
        logger.warning(f"Could not load treasury top picks: {e}")
        return []


def _get_pick_stats() -> Dict[str, Any]:
    intelligence = get_trade_intelligence()
    if not intelligence:
        return {}
    summary = intelligence.get_learning_summary()
    total = summary.get("total_trades_analyzed", 0) or 0
    if total == 0:
        return {}

    def _parse_percent(value: str) -> float:
        try:
            return float(str(value).replace("%", "").replace("+", "").strip())
        except Exception:
            return 0.0

    signal_stats = summary.get("signals", {})
    stats = signal_stats.get("STRONG_BUY") or signal_stats.get("BUY") or {}
    win_rate = _parse_percent(stats.get("win_rate", 0))
    avg_gain = _parse_percent(stats.get("avg_return", 0))

    return {
        "win_rate": win_rate,
        "avg_gain": avg_gain,
        "total_picks": total,
    }


async def get_conviction_picks() -> List[Dict[str, Any]]:
    """
    Get AI conviction picks enhanced with trade intelligence.

    Combines:
    - Grok sentiment analysis
    - Trade intelligence recommendations
    - Historical pattern matching
    """
    picks: List[Dict[str, Any]] = []
    seen = set()

    def add_pick(pick: Dict[str, Any]) -> None:
        key = _pick_key(pick)
        if not key or key in seen:
            return
        seen.add(key)
        picks.append(pick)

    # Always fetch Bags tokens (required data source)
    bags_tokens = []
    try:
        bags_tokens = await get_bags_top_tokens_with_sentiment(limit=12)
    except Exception as e:
        logger.warning(f"Could not get Bags tokens for picks: {e}")

    bags_lookup = {t.get("address", ""): t for t in bags_tokens if t.get("address")}

    # 1) Treasury picks (if present) - align with treasury dashboard
    for pick in _load_treasury_top_picks(limit=5):
        bags_match = bags_lookup.get(pick.get("address", ""))
        if bags_match:
            pick["price_usd"] = bags_match.get("price_usd", pick.get("entry_price", 0))
            pick["volume_24h"] = bags_match.get("volume_24h", 0)
            pick["liquidity"] = bags_match.get("liquidity", 0)
            pick["sentiment"] = bags_match.get("sentiment", "neutral")
            pick["sentiment_score"] = bags_match.get("sentiment_score", 0.5)
            pick["signal"] = bags_match.get("signal", "NEUTRAL")
        add_pick(pick)

    # 2) Grok picks (optional overlay)
    try:
        from core.enhanced_market_data import (
            fetch_trending_solana_tokens,
            fetch_backed_stocks,
            fetch_backed_indexes,
            get_grok_conviction_picks,
        )
        from bots.twitter.grok_client import get_grok_client

        grok_client = get_grok_client()
        if not getattr(grok_client, "api_key", None):
            raise RuntimeError("Grok API key not configured")

        tokens, _ = await fetch_trending_solana_tokens(limit=12)
        stocks, _ = await asyncio.to_thread(fetch_backed_stocks)
        indexes, _ = await asyncio.to_thread(fetch_backed_indexes)

        grok_picks, _warnings = await get_grok_conviction_picks(
            tokens=tokens,
            stocks=stocks,
            indexes=indexes,
            grok_client=grok_client,
            top_n=5,
            historical_learnings="",
            save_picks=False,
        )
        for p in grok_picks[:5]:
            pick = {
                "symbol": p.symbol,
                "address": p.address,
                "conviction": p.conviction,
                "thesis": p.thesis,
                "entry_price": p.entry_price,
                "tp_target": p.tp_target,
                "sl_target": p.sl_target,
                "source": "grok",
            }
            bags_match = bags_lookup.get(p.address)
            if bags_match:
                pick["price_usd"] = bags_match.get("price_usd", p.entry_price)
                pick["volume_24h"] = bags_match.get("volume_24h", 0)
                pick["liquidity"] = bags_match.get("liquidity", 0)
                pick["sentiment"] = bags_match.get("sentiment", "neutral")
                pick["sentiment_score"] = bags_match.get("sentiment_score", 0.5)
                pick["signal"] = bags_match.get("signal", "NEUTRAL")
            add_pick(pick)
    except Exception as e:
        logger.warning(f"Could not get Grok picks: {e}")

    # 3) Fill with Bags volume leaders
    for token in bags_tokens:
        sentiment_score = token.get("sentiment_score", 0.5)
        conviction_score = int(round(sentiment_score * 100)) if sentiment_score <= 1 else int(sentiment_score)
        conviction = _conviction_label(conviction_score)
        tp_target, sl_target = _default_tp_sl(conviction)
        add_pick({
            "symbol": token.get("symbol", "???"),
            "address": token.get("address", ""),
            "conviction": conviction,
            "thesis": f"Volume leader with {token.get('sentiment', 'neutral')} sentiment",
            "entry_price": token.get("price_usd", 0),
            "tp_target": tp_target,
            "sl_target": sl_target,
            "source": "bags",
            "volume_24h": token.get("volume_24h", 0),
            "liquidity": token.get("liquidity", 0),
            "sentiment": token.get("sentiment", "neutral"),
            "sentiment_score": token.get("sentiment_score", 0.5),
            "signal": token.get("signal", "NEUTRAL"),
        })

    # Enhance with trade intelligence recommendations
    intelligence = get_trade_intelligence()
    if intelligence:
        for pick in picks:
            rec = intelligence.get_trade_recommendation(
                signal_type=pick.get("signal", "BUY"),
                market_regime="BULL",
                sentiment_score=pick.get("sentiment_score", 0.6),
            )
            pick["ai_confidence"] = rec.get("confidence", 0)
            pick["ai_action"] = rec.get("action", "NEUTRAL")

    if picks:
        return picks[:5]

    # Final safety net
    return [
        {
            "symbol": "BONK",
            "address": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",
            "conviction": "HIGH",
            "thesis": "Strong momentum, high volume, bullish sentiment",
            "tp_target": 25,
            "sl_target": 10,
            "source": "demo",
        }
    ]

# =============================================================================
# UI Constants - Trojan-Style Theme
async def get_bags_top_tokens_with_sentiment(limit: int = 15) -> List[Dict[str, Any]]:
    """
    Get top trending tokens by volume with AI sentiment overlay.

    Now uses DexScreener for reliable token data.
    Bags API is reserved for trade execution only.
    """
    tokens = []

    try:
        # Use DexScreener for token data (more reliable than Bags API)
        from core.dexscreener import get_solana_trending
        raw_tokens = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: get_solana_trending(
                min_liquidity=10_000,
                min_volume_24h=50_000,
                limit=limit
            )
        )

        if raw_tokens:
            for t in raw_tokens:
                token_data = {
                    "symbol": t.base_token_symbol,
                    "name": t.base_token_name or t.base_token_symbol,
                    "address": t.base_token_address,
                    "price_usd": t.price_usd,
                    "change_24h": t.price_change_24h,
                    "volume_24h": t.volume_24h,
                    "liquidity": t.liquidity_usd,
                    "market_cap": 0,  # DexScreener doesn't provide market cap directly
                    "holders": 0,  # DexScreener doesn't provide holder count
                    "chart_url": f"https://dexscreener.com/solana/{t.base_token_address}",
                }

                # Add AI sentiment overlay
                try:
                    sentiment = await get_ai_sentiment_for_token(t.base_token_address)
                    token_data["sentiment"] = sentiment.get("sentiment", "neutral")
                    token_data["sentiment_score"] = sentiment.get("score", 0.5)
                    token_data["signal"] = sentiment.get("signal", "NEUTRAL")
                except Exception:
                    token_data["sentiment"] = "neutral"
                    token_data["sentiment_score"] = 0.5
                    token_data["signal"] = "NEUTRAL"

                tokens.append(token_data)

            if tokens:
                return tokens

    except Exception as e:
        logger.error(f"Could not get DexScreener tokens: {e}", exc_info=True)

    # Fallback to real trending tokens (DexScreener or signal service) so we have tradable addresses.
    try:
        trending = await get_trending_with_sentiment()
        if trending:
            enriched: List[Dict[str, Any]] = []
            for t in trending[:limit]:
                address = t.get("address", "")
                price_usd = float(t.get("price_usd", 0) or t.get("price", 0) or 0)
                change_24h = float(t.get("change_24h", 0) or t.get("price_change_24h", 0) or 0)
                volume_24h = float(t.get("volume_24h", 0) or t.get("volume", 0) or 0)
                liquidity = float(t.get("liquidity", 0) or 0)
                market_cap = float(t.get("market_cap", 0) or 0)
                sentiment = t.get("sentiment", "neutral")
                sentiment_score = t.get("sentiment_score", 0.5)
                signal = t.get("signal", "NEUTRAL")

                if address and price_usd <= 0:
                    try:
                        extra = await get_ai_sentiment_for_token(address)
                        price_usd = float(extra.get("price", 0) or price_usd)
                        change_24h = float(extra.get("change_24h", change_24h) or change_24h)
                        volume_24h = float(extra.get("volume", volume_24h) or volume_24h)
                        liquidity = float(extra.get("liquidity", liquidity) or liquidity)
                        market_cap = float(extra.get("market_cap", market_cap) or market_cap)
                        sentiment = extra.get("sentiment", sentiment)
                        sentiment_score = extra.get("score", sentiment_score)
                        signal = extra.get("signal", signal)
                    except Exception:
                        pass

                enriched.append({
                    "symbol": t.get("symbol", "???"),
                    "name": t.get("name", t.get("symbol", "")),
                    "address": address,
                    "price_usd": price_usd,
                    "change_24h": change_24h,
                    "volume_24h": volume_24h,
                    "liquidity": liquidity,
                    "market_cap": market_cap,
                    "holders": int(t.get("holders", 0) or 0),
                    "sentiment": sentiment,
                    "sentiment_score": sentiment_score,
                    "signal": signal,
                })

            if enriched:
                return enriched
    except Exception as e:
        logger.warning(f"Could not load trending fallback tokens: {e}")

    # Fallback to mock data with realistic sentiment and real addresses for chart links
    # NOTE: These are placeholder tokens - DexScreener API should be working for real data
    logger.warning("⚠️ Using MOCK DATA for BAGS tokens - DexScreener API is not responding!")
    mock_tokens = [
        {"symbol": "SOL", "name": "Wrapped SOL", "address": "So11111111111111111111111111111111111111112", "price_usd": 142.50, "volume_24h": 850000000, "liquidity": 45000000, "market_cap": 125000000, "holders": 15420, "sentiment": "bullish", "sentiment_score": 0.78, "signal": "BUY"},
        {"symbol": "USDC", "name": "USD Coin", "address": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v", "price_usd": 1.0, "volume_24h": 620000000, "liquidity": 32000000, "market_cap": 850000000, "holders": 12350, "sentiment": "neutral", "sentiment_score": 0.50, "signal": "HOLD"},
        {"symbol": "JUP", "name": "Jupiter", "address": "JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN", "price_usd": 0.52, "volume_24h": 48000000, "liquidity": 2800000, "market_cap": 52000000, "holders": 9800, "sentiment": "bullish", "sentiment_score": 0.72, "signal": "BUY"},
        {"symbol": "BONK", "name": "Bonk", "address": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263", "price_usd": 0.0000125, "volume_24h": 42000000, "liquidity": 520000, "market_cap": 42500000, "holders": 18200, "sentiment": "neutral", "sentiment_score": 0.52, "signal": "HOLD"},
        {"symbol": "WIF", "name": "dogwifhat", "address": "EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm", "price_usd": 2.15, "volume_24h": 38000000, "liquidity": 1800000, "market_cap": 42500000, "holders": 7500, "sentiment": "bullish", "sentiment_score": 0.68, "signal": "BUY"},
        {"symbol": "RAY", "name": "Raydium", "address": "4k3Dyjzvzp8eMZWUXbBCjEvwSkkk59S5iCNLY3QrkX6R", "price_usd": 3.85, "volume_24h": 35000000, "liquidity": 1500000, "market_cap": 18500000, "holders": 6200, "sentiment": "very_bullish", "sentiment_score": 0.82, "signal": "STRONG_BUY"},
        {"symbol": "ORCA", "name": "Orca", "address": "orcaEKTdK7LKz57vaAYr9QeNsVEPfiu6QeMU1kektZE", "price_usd": 3.25, "volume_24h": 32000000, "liquidity": 3800000, "market_cap": 125000000, "holders": 14500, "sentiment": "neutral", "sentiment_score": 0.48, "signal": "HOLD"},
        {"symbol": "JTO", "name": "Jito", "address": "jtojtomepa8beP8AuQc6eXt5FriJwfFMwQx2v2f9mCL", "price_usd": 2.42, "volume_24h": 28000000, "liquidity": 1200000, "market_cap": 42000000, "holders": 5800, "sentiment": "bullish", "sentiment_score": 0.65, "signal": "BUY"},
        {"symbol": "PYTH", "name": "Pyth Network", "address": "HZ1JovNiVvGrGNiiYvEozEVgZ58xaU3RKwX8eACQBCt3", "price_usd": 0.38, "volume_24h": 25000000, "liquidity": 950000, "market_cap": 18000000, "holders": 4200, "sentiment": "bullish", "sentiment_score": 0.62, "signal": "BUY"},
        {"symbol": "TNSR", "name": "Tensor", "address": "TNSRxcUxoT9xBG3de7PiJyTDYu7kskLqcpddxnEJAS6", "price_usd": 0.45, "volume_24h": 22000000, "liquidity": 1100000, "market_cap": 65000000, "holders": 5500, "sentiment": "neutral", "sentiment_score": 0.55, "signal": "HOLD"},
        {"symbol": "POPCAT", "name": "Popcat", "address": "7GCihgDB8fe6KNjn2MYtkzZcRjQy3t9GHdC8uHYmW2hr", "price_usd": 0.95, "volume_24h": 19500000, "liquidity": 850000, "market_cap": 95000000, "holders": 8200, "sentiment": "bullish", "sentiment_score": 0.70, "signal": "BUY"},
        {"symbol": "MOBILE", "name": "Helium Mobile", "address": "mb1eu7TzEc71KxDpsmsKoucSSuuoGLv1drys1oP2jh6", "price_usd": 0.00082, "volume_24h": 18000000, "liquidity": 420000, "market_cap": 520000000, "holders": 22000, "sentiment": "neutral", "sentiment_score": 0.50, "signal": "HOLD"},
        {"symbol": "HNT", "name": "Helium", "address": "hntyVP6YFm1Hg25TN9WGLqM12b8TQmcknKrdu1oxWux", "price_usd": 6.25, "volume_24h": 16500000, "liquidity": 750000, "market_cap": 1250000, "holders": 3500, "sentiment": "bullish", "sentiment_score": 0.68, "signal": "BUY"},
        {"symbol": "MNGO", "name": "Mango", "address": "MangoCzJ36AjZyKwVj3VnYU4GTonjfVEnJmvvWaxLac", "price_usd": 0.035, "volume_24h": 15000000, "liquidity": 680000, "market_cap": 35000000, "holders": 4800, "sentiment": "neutral", "sentiment_score": 0.52, "signal": "HOLD"},
        {"symbol": "SAMO", "name": "Samoyedcoin", "address": "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU", "price_usd": 0.0028, "volume_24h": 13500000, "liquidity": 550000, "market_cap": 28000000, "holders": 3900, "sentiment": "neutral", "sentiment_score": 0.45, "signal": "HOLD"},
    ]

    # Add chart_url to all mock tokens
    for token in mock_tokens:
        token["chart_url"] = f"https://dexscreener.com/solana/{token['address']}"

    return mock_tokens


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

    # =========================================================================
    # BEAUTIFICATION V1.1 - Enhanced Visual Indicators
    # =========================================================================

    # Loading/Progress animations
    LOADING_FRAMES = ["⏳", "⌛"]
    PULSE_FRAMES = ["◉", "○"]
    SPIN_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

    # Market mood spectrum (more nuanced than bull/bear)
    MOOD_EUPHORIC = "🌟"      # Extreme greed - careful!
    MOOD_BULLISH = "🚀"       # Strong uptrend
    MOOD_OPTIMISTIC = "💚"    # Mild bullish
    MOOD_NEUTRAL = "⚖️"       # Sideways
    MOOD_CAUTIOUS = "🔶"      # Mild bearish
    MOOD_FEARFUL = "😰"       # Strong downtrend
    MOOD_PANIC = "🆘"         # Extreme fear - opportunities!

    # Health indicators for positions
    HEALTH_EXCELLENT = "💪"   # > +20% PnL, healthy time
    HEALTH_GOOD = "🟢"        # +5% to +20% PnL
    HEALTH_FAIR = "🟡"        # -5% to +5% PnL
    HEALTH_WEAK = "🟠"        # -5% to -15% PnL
    HEALTH_CRITICAL = "🔴"    # < -15% PnL

    # AI confidence levels
    CONFIDENCE_HIGH = "🎯"    # > 80% confidence
    CONFIDENCE_MED = "📊"     # 60-80% confidence
    CONFIDENCE_LOW = "⚠️"     # < 60% confidence

    # Time indicators
    TIME_FRESH = "🆕"         # < 1 hour
    TIME_NORMAL = "⏰"        # 1-24 hours
    TIME_AGING = "📅"         # 1-7 days
    TIME_OLD = "🗓️"          # > 7 days

    @classmethod
    def get_health_indicator(cls, pnl_pct: float, hours_held: float = 0) -> str:
        """Get position health indicator based on PnL and time."""
        if pnl_pct >= 20:
            return cls.HEALTH_EXCELLENT
        elif pnl_pct >= 5:
            return cls.HEALTH_GOOD
        elif pnl_pct >= -5:
            return cls.HEALTH_FAIR
        elif pnl_pct >= -15:
            return cls.HEALTH_WEAK
        else:
            return cls.HEALTH_CRITICAL

    @classmethod
    def get_health_bar(cls, pnl_pct: float, width: int = 5) -> str:
        """Generate a visual health bar for position PnL."""
        # Normalize PnL to 0-100 scale (capped at -50% to +100%)
        normalized = min(100, max(0, (pnl_pct + 50) / 1.5))
        filled = int(normalized / 100 * width)
        empty = width - filled

        if pnl_pct >= 20:
            bar = "🟩" * filled + "⬜" * empty
        elif pnl_pct >= 0:
            bar = "🟨" * filled + "⬜" * empty
        elif pnl_pct >= -15:
            bar = "🟧" * filled + "⬜" * empty
        else:
            bar = "🟥" * filled + "⬜" * empty
        return bar

    @classmethod
    def get_time_indicator(cls, hours_held: float) -> str:
        """Get time held indicator."""
        if hours_held < 1:
            return cls.TIME_FRESH
        elif hours_held < 24:
            return cls.TIME_NORMAL
        elif hours_held < 168:  # 7 days
            return cls.TIME_AGING
        else:
            return cls.TIME_OLD

    @classmethod
    def get_market_mood(cls, fear_greed_score: float) -> Tuple[str, str]:
        """Get market mood emoji and label based on fear/greed score (0-100)."""
        if fear_greed_score >= 85:
            return cls.MOOD_EUPHORIC, "EUPHORIC"
        elif fear_greed_score >= 65:
            return cls.MOOD_BULLISH, "BULLISH"
        elif fear_greed_score >= 55:
            return cls.MOOD_OPTIMISTIC, "OPTIMISTIC"
        elif fear_greed_score >= 45:
            return cls.MOOD_NEUTRAL, "NEUTRAL"
        elif fear_greed_score >= 35:
            return cls.MOOD_CAUTIOUS, "CAUTIOUS"
        elif fear_greed_score >= 15:
            return cls.MOOD_FEARFUL, "FEARFUL"
        else:
            return cls.MOOD_PANIC, "PANIC"

    @classmethod
    def get_confidence_bar(cls, confidence: float, width: int = 10) -> str:
        """Generate an AI confidence bar (0.0 to 1.0)."""
        filled = int(confidence * width)
        empty = width - filled
        bar_char = "▰" if confidence >= 0.6 else "▱"
        return "▰" * filled + "▱" * empty

    @classmethod
    def get_confidence_indicator(cls, confidence: float) -> str:
        """Get confidence level indicator."""
        if confidence >= 0.8:
            return cls.CONFIDENCE_HIGH
        elif confidence >= 0.6:
            return cls.CONFIDENCE_MED
        else:
            return cls.CONFIDENCE_LOW

    @classmethod
    def loading_text(cls, message: str = "Loading") -> str:
        """Generate loading text with animation hint."""
        return f"⏳ _{message}..._"

    @classmethod
    def format_pnl_styled(cls, pnl_pct: float, pnl_usd: float) -> str:
        """Format PnL with beautiful styling."""
        sign = "+" if pnl_pct >= 0 else ""
        emoji = cls.PROFIT if pnl_pct >= 0 else cls.LOSS
        health = cls.get_health_indicator(pnl_pct)
        bar = cls.get_health_bar(pnl_pct)

        return f"{emoji}{health} *{sign}{pnl_pct:.1f}%* ({sign}${abs(pnl_usd):.2f})\n{bar}"


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
        ai_auto_enabled: bool = False,
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

        # AI Auto-trade status
        ai_status = f"{theme.ROCKET} AUTO-TRADE ACTIVE" if ai_auto_enabled else ""

        # Build message with beautiful formatting + AI sentiment
        text = f"""
{theme.ROCKET} *JARVIS AI TRADING* {theme.ROCKET}
━━━━━━━━━━━━━━━━━━━━━
"""
        # Show AI auto-trade status if enabled
        if ai_auto_enabled:
            text += f"\n{ai_status}\n"

        text += f"""
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
            # Sentiment Hub - Premium Feature (NEW V1)
            [
                InlineKeyboardButton(f"📊 SENTIMENT HUB", callback_data="demo:hub"),
            ],
            # Insta Snipe - One-Click Trending Trade
            [
                InlineKeyboardButton(f"⚡ INSTA SNIPE", callback_data="demo:insta_snipe"),
                InlineKeyboardButton(f"{theme.CHART} AI Report", callback_data="demo:ai_report"),
            ],
            # AI-Powered Analysis Row
            [
                InlineKeyboardButton(f"{theme.AUTO} AI Picks", callback_data="demo:ai_picks"),
                InlineKeyboardButton(f"{theme.FIRE} Trending", callback_data="demo:trending"),
            ],
            # Bags.fm Top Tokens - Volume Leaders
            [
                InlineKeyboardButton("🎒 BAGS TOP 15", callback_data="demo:bags_fm"),
            ],
            # Universal Token Search - Buy/Sell ANY Token
            [
                InlineKeyboardButton(f"🔍 SEARCH TOKEN", callback_data="demo:token_search"),
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
            # 1-Tap Quick Actions
            [
                InlineKeyboardButton(f"🔴 Sell All", callback_data="demo:sell_all"),
                InlineKeyboardButton(f"📈 PnL Report", callback_data="demo:pnl_report"),
                InlineKeyboardButton(f"💰 Fee Stats", callback_data="demo:fee_stats"),
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
            # Watchlist & AI Picks
            [
                InlineKeyboardButton(f"⭐ Watchlist", callback_data="demo:watchlist"),
                InlineKeyboardButton(f"💎 AI Picks", callback_data="demo:ai_picks"),
            ],
            # DCA & Alerts
            [
                InlineKeyboardButton(f"📅 DCA", callback_data="demo:dca"),
                InlineKeyboardButton(f"🔔 Alerts", callback_data="demo:pnl_alerts"),
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
        token_holdings: List[Dict[str, Any]] = None,
        total_holdings_usd: float = 0.0,
    ) -> Tuple[str, InlineKeyboardMarkup]:
        """Build wallet management menu with enhanced features."""
        theme = JarvisTheme

        if not has_wallet:
            text = f"""
{theme.WALLET} *WALLET SETUP*
━━━━━━━━━━━━━━━━━━━━━

{theme.WARNING} No wallet configured

Create a new wallet or import an existing one.

{theme.LOCK} All keys are encrypted with AES-256
{theme.AUTO} Auto-backup to secure storage
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
            total_value = usd_value + total_holdings_usd

            text = f"""
{theme.WALLET} *WALLET MANAGEMENT*
━━━━━━━━━━━━━━━━━━━━━

{theme.KEY} *Address*
`{wallet_address}`

{theme.SOL} *SOL Balance:* {sol_balance:.4f} SOL
{theme.USD} *SOL Value:* ${usd_value:,.2f}
"""
            # Add token holdings summary
            if token_holdings:
                text += f"""
💎 *Token Holdings:* ${total_holdings_usd:,.2f}
"""
                for token in token_holdings[:3]:
                    symbol = token.get("symbol", "???")
                    value = token.get("value_usd", 0)
                    text += f"   └ {symbol}: ${value:,.2f}\n"
                if len(token_holdings) > 3:
                    text += f"   └ _+{len(token_holdings) - 3} more..._\n"

            text += f"""
━━━━━━━━━━━━━━━━━━━━━
💰 *Total Portfolio:* ${total_value:,.2f}
{theme.LOCK} Private key stored encrypted
"""
            keyboard = [
                # Row 1: Address & Balance
                [
                    InlineKeyboardButton(f"{theme.COPY} Copy Address", callback_data="demo:copy_address"),
                    InlineKeyboardButton(f"{theme.REFRESH} Refresh", callback_data="demo:refresh_balance"),
                ],
                # Row 2: Holdings & Activity
                [
                    InlineKeyboardButton(f"💎 Token Holdings", callback_data="demo:token_holdings"),
                    InlineKeyboardButton(f"📜 Activity", callback_data="demo:wallet_activity"),
                ],
                # Row 3: Transfer & Receive
                [
                    InlineKeyboardButton(f"📤 Send SOL", callback_data="demo:send_sol"),
                    InlineKeyboardButton(f"📥 Receive", callback_data="demo:receive_sol"),
                ],
                # Row 4: Security
                [
                    InlineKeyboardButton(f"{theme.LOCK} Export Key", callback_data="demo:export_key_confirm"),
                    InlineKeyboardButton(f"{theme.WARNING} Reset", callback_data="demo:wallet_reset_confirm"),
                ],
                # Row 5: Back
                [
                    InlineKeyboardButton(f"{theme.BACK} Back", callback_data="demo:main"),
                ],
            ]

        return text, InlineKeyboardMarkup(keyboard)

    @staticmethod
    def token_holdings_view(
        holdings: List[Dict[str, Any]],
        total_value: float = 0.0,
    ) -> Tuple[str, InlineKeyboardMarkup]:
        """
        Detailed token holdings view.

        Shows all SPL tokens in the wallet with values.
        """
        theme = JarvisTheme

        lines = [
            f"💎 *TOKEN HOLDINGS*",
            "━━━━━━━━━━━━━━━━━━━━━",
            "",
        ]

        if not holdings:
            lines.extend([
                "_No tokens found_",
                "",
                "Your SOL tokens will appear here",
                "once you make trades!",
            ])
        else:
            for token in holdings[:10]:
                symbol = token.get("symbol", "???")
                amount = token.get("amount", 0)
                value = token.get("value_usd", 0)
                change = token.get("change_24h", 0)

                change_emoji = "🟢" if change >= 0 else "🔴"
                change_sign = "+" if change >= 0 else ""

                lines.append(f"*{symbol}*")
                lines.append(f"   Amount: {amount:,.2f}")
                lines.append(f"   Value: ${value:,.2f}")
                lines.append(f"   {change_emoji} {change_sign}{change:.1f}%")
                lines.append("")

            if len(holdings) > 10:
                lines.append(f"_Showing 10 of {len(holdings)} tokens_")

        lines.extend([
            "━━━━━━━━━━━━━━━━━━━━━",
            f"💰 *Total:* ${total_value:,.2f}",
        ])

        text = "\n".join(lines)

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(f"{theme.REFRESH} Refresh", callback_data="demo:token_holdings"),
            ],
            [
                InlineKeyboardButton(f"{theme.BACK} Back", callback_data="demo:wallet_menu"),
            ],
        ])

        return text, keyboard

    @staticmethod
    def wallet_activity_view(
        transactions: List[Dict[str, Any]] = None,
    ) -> Tuple[str, InlineKeyboardMarkup]:
        """
        Wallet transaction history view.
        """
        theme = JarvisTheme

        lines = [
            f"📜 *WALLET ACTIVITY*",
            "━━━━━━━━━━━━━━━━━━━━━",
            "",
        ]

        if not transactions:
            lines.extend([
                "_No recent activity_",
                "",
                "Your transactions will appear here",
                "once you start trading!",
            ])
        else:
            for tx in transactions[:8]:
                tx_type = tx.get("type", "unknown")
                symbol = tx.get("symbol", "SOL")
                amount = tx.get("amount", 0)
                timestamp = tx.get("timestamp", "")
                status = tx.get("status", "confirmed")

                type_emoji = {
                    "buy": "🟢",
                    "sell": "🔴",
                    "transfer_in": "📥",
                    "transfer_out": "📤",
                    "swap": "🔄",
                }.get(tx_type, "⚪")

                status_emoji = "✅" if status == "confirmed" else "⏳"

                lines.append(f"{type_emoji} *{tx_type.upper()}* {symbol}")
                lines.append(f"   Amount: {amount:,.4f}")
                lines.append(f"   {status_emoji} {timestamp}")
                lines.append("")

        lines.extend([
            "━━━━━━━━━━━━━━━━━━━━━",
        ])

        text = "\n".join(lines)

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(f"{theme.REFRESH} Refresh", callback_data="demo:wallet_activity"),
            ],
            [
                InlineKeyboardButton(f"{theme.BACK} Back", callback_data="demo:wallet_menu"),
            ],
        ])

        return text, keyboard

    @staticmethod
    def send_sol_view(
        sol_balance: float = 0.0,
    ) -> Tuple[str, InlineKeyboardMarkup]:
        """
        Send SOL interface.
        """
        theme = JarvisTheme

        text = f"""
📤 *SEND SOL*
━━━━━━━━━━━━━━━━━━━━━

*Available:* {sol_balance:.4f} SOL

To send SOL:
1. Paste the recipient address
2. Enter the amount
3. Confirm the transaction

{theme.WARNING} _Always double-check addresses!_

━━━━━━━━━━━━━━━━━━━━━
_Feature coming in V2_

For now, use your wallet app
to send SOL directly.
"""

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(f"{theme.BACK} Back", callback_data="demo:wallet_menu"),
            ],
        ])

        return text, keyboard

    @staticmethod
    def export_key_confirm() -> Tuple[str, InlineKeyboardMarkup]:
        """
        Export private key confirmation with warnings.
        """
        theme = JarvisTheme

        text = f"""
{theme.WARNING} *EXPORT PRIVATE KEY*
━━━━━━━━━━━━━━━━━━━━━

⚠️ *SECURITY WARNING*

Your private key gives FULL access
to your wallet and ALL funds.

*NEVER share your key with anyone!*

{theme.WARNING} Scammers may pose as support
{theme.WARNING} No one should ever ask for it
{theme.WARNING} Store it securely offline

━━━━━━━━━━━━━━━━━━━━━

Are you sure you want to export?
"""

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(f"⚠️ Yes, Show Key", callback_data="demo:export_key"),
            ],
            [
                InlineKeyboardButton(f"{theme.CLOSE} Cancel", callback_data="demo:wallet_menu"),
            ],
        ])

        return text, keyboard

    @staticmethod
    def wallet_reset_confirm() -> Tuple[str, InlineKeyboardMarkup]:
        """
        Wallet reset confirmation with warnings.
        """
        theme = JarvisTheme

        text = f"""
{theme.WARNING} *RESET WALLET*
━━━━━━━━━━━━━━━━━━━━━

⚠️ *THIS IS IRREVERSIBLE*

Resetting will:
• Delete your current wallet
• Remove all encrypted keys
• Clear all trading history

{theme.WARNING} Make sure you have backed up
   your private key first!

━━━━━━━━━━━━━━━━━━━━━

Type "RESET" to confirm.
"""

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(f"🗑️ Confirm Reset", callback_data="demo:wallet_reset"),
            ],
            [
                InlineKeyboardButton(f"{theme.CLOSE} Cancel", callback_data="demo:wallet_menu"),
            ],
        ])

        return text, keyboard

    @staticmethod
    def wallet_import_prompt() -> Tuple[str, InlineKeyboardMarkup]:
        """
        Wallet import prompt - import private key or seed phrase.
        """
        theme = JarvisTheme

        text = f"""
{theme.LOCK} *IMPORT WALLET*
━━━━━━━━━━━━━━━━━━━━━

Import an existing wallet using:

📝 *Private Key (Base58)*
└ 64-88 character Solana key

🌱 *Seed Phrase (12/24 words)*
└ BIP39 mnemonic phrase

━━━━━━━━━━━━━━━━━━━━━

⚠️ *Security Warning*
• Only import on a secure device
• Never share your key/phrase
• Clear message history after

━━━━━━━━━━━━━━━━━━━━━

Send your private key or seed phrase
in the next message.
"""

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(f"🔑 Enter Private Key", callback_data="demo:import_mode_key"),
            ],
            [
                InlineKeyboardButton(f"🌱 Enter Seed Phrase", callback_data="demo:import_mode_seed"),
            ],
            [
                InlineKeyboardButton(f"{theme.CLOSE} Cancel", callback_data="demo:wallet_menu"),
            ],
        ])

        return text, keyboard

    @staticmethod
    def wallet_import_input(import_type: str = "key") -> Tuple[str, InlineKeyboardMarkup]:
        """
        Wallet import input mode - waiting for key/phrase.
        """
        theme = JarvisTheme

        if import_type == "seed":
            text = f"""
{theme.LOCK} *IMPORT SEED PHRASE*
━━━━━━━━━━━━━━━━━━━━━

🌱 Send your *12 or 24 word* seed phrase.

Example format:
_word1 word2 word3 ... word12_

━━━━━━━━━━━━━━━━━━━━━

⚠️ Your phrase is encrypted and
   stored securely.
"""
        else:
            text = f"""
{theme.LOCK} *IMPORT PRIVATE KEY*
━━━━━━━━━━━━━━━━━━━━━

🔑 Send your *Base58 private key*.

It should be 64-88 characters.

━━━━━━━━━━━━━━━━━━━━━

⚠️ Your key is encrypted and
   stored securely.
"""

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(f"{theme.CLOSE} Cancel", callback_data="demo:wallet_menu"),
            ],
        ])

        return text, keyboard

    @staticmethod
    def wallet_import_result(
        success: bool,
        wallet_address: str = None,
        error: str = None,
    ) -> Tuple[str, InlineKeyboardMarkup]:
        """
        Wallet import result view.
        """
        theme = JarvisTheme

        if success:
            short_addr = f"{wallet_address[:6]}...{wallet_address[-4:]}" if wallet_address else "?"
            text = f"""
✅ *WALLET IMPORTED*
━━━━━━━━━━━━━━━━━━━━━

🎉 Successfully imported wallet!

📍 *Address:*
`{wallet_address or 'Unknown'}`

━━━━━━━━━━━━━━━━━━━━━

⚠️ *Important*
• Delete the message with your key
• Your wallet is now active
• Start trading!
"""
        else:
            text = f"""
❌ *IMPORT FAILED*
━━━━━━━━━━━━━━━━━━━━━

Could not import wallet.

*Error:* {error or 'Invalid key or phrase'}

━━━━━━━━━━━━━━━━━━━━━

Please check your key/phrase and try again.
"""

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(f"💼 View Wallet", callback_data="demo:wallet_menu"),
            ] if success else [
                InlineKeyboardButton(f"🔄 Try Again", callback_data="demo:wallet_import"),
            ],
            [
                InlineKeyboardButton(f"{theme.BACK} Main Menu", callback_data="demo:main"),
            ],
        ])

        return text, keyboard

    @staticmethod
    def export_key_show(
        private_key: str,
        wallet_address: str,
    ) -> Tuple[str, InlineKeyboardMarkup]:
        """
        Export private key display - SENSITIVE.
        """
        theme = JarvisTheme

        # Mask middle portion for security
        key_display = f"`{private_key}`" if private_key else "_Key unavailable_"

        text = f"""
🔐 *YOUR PRIVATE KEY*
━━━━━━━━━━━━━━━━━━━━━

📍 *Address:*
`{wallet_address}`

🔑 *Private Key:*
{key_display}

━━━━━━━━━━━━━━━━━━━━━

⚠️ *CRITICAL SECURITY*
• Copy this key NOW
• Store in a password manager
• DELETE THIS MESSAGE after
• NEVER share with anyone
• Anyone with this key controls your funds

━━━━━━━━━━━━━━━━━━━━━
"""

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(f"📋 Copy Key", callback_data="demo:copy_key"),
            ],
            [
                InlineKeyboardButton(f"✅ Done, Back to Wallet", callback_data="demo:wallet_menu"),
            ],
        ])

        return text, keyboard

    @staticmethod
    def positions_menu(
        positions: list,
        total_pnl: float = 0.0,
    ) -> Tuple[str, InlineKeyboardMarkup]:
        """Build positions overview with health indicators, sell buttons, and quick SL/TP."""
        theme = JarvisTheme

        if not positions:
            text = f"""
{theme.CHART} *POSITIONS*
━━━━━━━━━━━━━━━━━━━━━

_No open positions_

{theme.ROCKET} *Ready to trade?*
Use AI-powered signals to find opportunities!
"""
            keyboard = [
                [
                    InlineKeyboardButton(f"{theme.FIRE} Find Tokens", callback_data="demo:trending"),
                    InlineKeyboardButton(f"📊 AI Picks", callback_data="demo:ai_picks"),
                ],
                [
                    InlineKeyboardButton(f"🎒 BAGS TOP 15", callback_data="demo:bags_fm"),
                ],
                [
                    InlineKeyboardButton(f"{theme.BACK} Back", callback_data="demo:main"),
                ],
            ]
        else:
            pnl_emoji = theme.PROFIT if total_pnl >= 0 else theme.LOSS
            pnl_sign = "+" if total_pnl >= 0 else ""

            # Portfolio health score (average of all positions)
            avg_pnl = sum(p.get("pnl_pct", 0) for p in positions) / len(positions)
            portfolio_health = theme.get_health_indicator(avg_pnl)
            portfolio_bar = theme.get_health_bar(avg_pnl, width=8)

            lines = [
                f"{theme.CHART} *POSITIONS*",
                "━━━━━━━━━━━━━━━━━━━━━",
                f"",
                f"{portfolio_health} *Portfolio Health*",
                f"{portfolio_bar}",
                f"Total P&L: {pnl_emoji} *{pnl_sign}${abs(total_pnl):.2f}*",
                f"",
                "━━━━━━━━━━━━━━━━━━━━━",
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

                # Calculate hours held (if available)
                entry_time = pos.get("entry_time")
                if entry_time:
                    try:
                        if isinstance(entry_time, str):
                            entry_dt = datetime.fromisoformat(entry_time.replace('Z', '+00:00'))
                        else:
                            entry_dt = entry_time
                        hours_held = (datetime.now(timezone.utc) - entry_dt).total_seconds() / 3600
                    except Exception:
                        hours_held = 0
                else:
                    hours_held = 0

                # Get health and time indicators
                health = theme.get_health_indicator(pnl_pct, hours_held)
                health_bar = theme.get_health_bar(pnl_pct, width=5)
                time_ind = theme.get_time_indicator(hours_held)
                pnl_sign = "+" if pnl_pct >= 0 else ""

                # Format time held
                if hours_held < 1:
                    time_str = f"{int(hours_held * 60)}m"
                elif hours_held < 24:
                    time_str = f"{int(hours_held)}h"
                else:
                    time_str = f"{int(hours_held / 24)}d"

                # Get current TP/SL if set
                tp = pos.get("take_profit", 50)
                sl = pos.get("stop_loss", 20)

                lines.extend([
                    f"{health} *{symbol}* {pnl_sign}{pnl_pct:.1f}%",
                    f"{health_bar}",
                    f"├ Entry: `${entry:.8f}`",
                    f"├ Now: `${current:.8f}`",
                    f"├ P&L: *{pnl_sign}${abs(pnl_usd):.2f}*",
                    f"├ {time_ind} Held: *{time_str}*",
                    f"└ TP: +{tp}% | SL: -{sl}%",
                    "",
                ])

                # Add action buttons for each position (sell + quick SL/TP adjust)
                keyboard.append([
                    InlineKeyboardButton(
                        f"🔴 Sell 25%",
                        callback_data=f"demo:sell:{pos_id}:25"
                    ),
                    InlineKeyboardButton(
                        f"🔴 Sell All",
                        callback_data=f"demo:sell:{pos_id}:100"
                    ),
                    InlineKeyboardButton(
                        f"⚙️ SL/TP",
                        callback_data=f"demo:pos_adjust:{pos_id}"
                    ),
                ])

            text = "\n".join(lines)

            # Add navigation with enhanced options
            keyboard.extend([
                [
                    InlineKeyboardButton("🔔 Alerts", callback_data="demo:pnl_alerts"),
                    InlineKeyboardButton("🛡️ Trailing SL", callback_data="demo:trailing_stops"),
                    InlineKeyboardButton("📊 P&L Report", callback_data="demo:pnl_report"),
                ],
                [
                    InlineKeyboardButton(f"{theme.REFRESH} Refresh", callback_data="demo:positions"),
                    InlineKeyboardButton(f"{theme.BACK} Back", callback_data="demo:main"),
                ],
            ])

        return text, InlineKeyboardMarkup(keyboard)

    @staticmethod
    def position_adjust_menu(
        pos_id: str,
        symbol: str,
        current_tp: float = 50.0,
        current_sl: float = 20.0,
        pnl_pct: float = 0.0,
    ) -> Tuple[str, InlineKeyboardMarkup]:
        """Quick SL/TP adjustment menu for a position."""
        theme = JarvisTheme
        health = theme.get_health_indicator(pnl_pct)
        health_bar = theme.get_health_bar(pnl_pct, width=8)
        pnl_sign = "+" if pnl_pct >= 0 else ""

        text = f"""
{theme.SETTINGS} *ADJUST POSITION*
━━━━━━━━━━━━━━━━━━━━━

{health} *{symbol}* {pnl_sign}{pnl_pct:.1f}%
{health_bar}

*Current Settings:*
├ 🎯 Take Profit: *+{current_tp}%*
└ 🛡️ Stop Loss: *-{current_sl}%*

━━━━━━━━━━━━━━━━━━━━━
_Adjust your exit strategy_
"""

        keyboard = [
            # TP adjustment row
            [
                InlineKeyboardButton("🎯 TP", callback_data="demo:noop"),
                InlineKeyboardButton("25%", callback_data=f"demo:set_tp:{pos_id}:25"),
                InlineKeyboardButton("50%", callback_data=f"demo:set_tp:{pos_id}:50"),
                InlineKeyboardButton("100%", callback_data=f"demo:set_tp:{pos_id}:100"),
                InlineKeyboardButton("200%", callback_data=f"demo:set_tp:{pos_id}:200"),
            ],
            # SL adjustment row
            [
                InlineKeyboardButton("🛡️ SL", callback_data="demo:noop"),
                InlineKeyboardButton("10%", callback_data=f"demo:set_sl:{pos_id}:10"),
                InlineKeyboardButton("20%", callback_data=f"demo:set_sl:{pos_id}:20"),
                InlineKeyboardButton("30%", callback_data=f"demo:set_sl:{pos_id}:30"),
                InlineKeyboardButton("50%", callback_data=f"demo:set_sl:{pos_id}:50"),
            ],
            # Quick actions
            [
                InlineKeyboardButton("🔴 Close Now", callback_data=f"demo:sell:{pos_id}:100"),
                InlineKeyboardButton("🛡️ Trailing SL", callback_data=f"demo:trailing_setup:{pos_id}"),
            ],
            [
                InlineKeyboardButton(f"{theme.BACK} Back to Positions", callback_data="demo:positions"),
            ],
        ]

        return text, InlineKeyboardMarkup(keyboard)

    @staticmethod
    def settings_menu(
        is_live: bool = False,
        slippage: float = 1.0,
        auto_sell: bool = True,
        take_profit: float = 50.0,
        stop_loss: float = 20.0,
        ai_auto_trade: bool = False,
    ) -> Tuple[str, InlineKeyboardMarkup]:
        """Build settings menu with AI auto-trade option."""
        theme = JarvisTheme

        mode = f"{theme.LIVE} LIVE" if is_live else f"{theme.PAPER} PAPER"
        auto_status = f"{theme.SUCCESS} ON" if auto_sell else f"{theme.ERROR} OFF"
        ai_status = f"{theme.ROCKET} ENABLED" if ai_auto_trade else f"{theme.ERROR} DISABLED"

        text = f"""
{theme.SETTINGS} *SETTINGS*
━━━━━━━━━━━━━━━━━━━━━

*Trading Mode*
└ {mode}

*Slippage*
└ {slippage}%

*Auto-Sell (TP/SL)*
└ Status: {auto_status}
├ Take Profit: +{take_profit}%
└ Stop Loss: -{stop_loss}%

*🤖 AI Auto-Trade*
└ Status: {ai_status}

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
            # AI Auto-Trade Settings
            [
                InlineKeyboardButton(f"🤖 AI Auto-Trade Settings", callback_data="demo:ai_auto_settings"),
            ],
            # TP/SL Advanced Settings (ladder exits, custom targets)
            [
                InlineKeyboardButton(f"🎯 TP/SL Advanced Settings", callback_data="demo:tpsl_settings"),
            ],
            # Fee Stats
            [
                InlineKeyboardButton(f"💰 Fee Stats (0.5% on wins)", callback_data="demo:fee_stats"),
            ],
            [
                InlineKeyboardButton(f"{theme.BACK} Back", callback_data="demo:main"),
            ],
        ]

        return text, InlineKeyboardMarkup(keyboard)

    @staticmethod
    def ai_auto_trade_settings(
        enabled: bool = False,
        risk_level: str = "MEDIUM",
        max_position_size: float = 0.5,
        min_confidence: float = 0.7,
        daily_limit: float = 2.0,
        cooldown_minutes: int = 30,
    ) -> Tuple[str, InlineKeyboardMarkup]:
        """
        AI Auto-Trade Settings - Configure autonomous trading.

        Features:
        - Enable/disable autonomous trading
        - Risk level (Conservative, Medium, Aggressive)
        - Position sizing limits
        - Confidence threshold for entries
        - Daily trade limits
        - Cooldown between trades
        """
        theme = JarvisTheme

        status_emoji = f"{theme.ROCKET}" if enabled else "⚪"
        status_text = "ENABLED" if enabled else "DISABLED"

        risk_emojis = {
            "CONSERVATIVE": "🐢",
            "MEDIUM": "⚖️",
            "AGGRESSIVE": "🔥",
        }
        risk_emoji = risk_emojis.get(risk_level, "⚖️")

        text = f"""
{theme.AUTO} *AI AUTO-TRADE SETTINGS*
━━━━━━━━━━━━━━━━━━━━━

{status_emoji} *Status:* {status_text}

{risk_emoji} *Risk Level:* {risk_level}
├ Conservative: Small positions, high confidence
├ Medium: Balanced approach
└ Aggressive: Larger positions, more trades

📊 *Parameters*
├ Max Position: {max_position_size} SOL
├ Min Confidence: {min_confidence * 100:.0f}%
├ Daily Limit: {daily_limit} SOL
└ Cooldown: {cooldown_minutes} min

━━━━━━━━━━━━━━━━━━━━━

{theme.WARNING} AI trades based on:
• Sentiment analysis (Grok AI)
• Market regime detection
• Technical indicators
• Trade intelligence learnings

"""

        keyboard = [
            # Toggle ON/OFF
            [
                InlineKeyboardButton(
                    f"{'🔴 Disable AI Trading' if enabled else '🟢 Enable AI Trading'}",
                    callback_data=f"demo:ai_auto_toggle:{not enabled}"
                ),
            ],
            # Risk Level Selection
            [
                InlineKeyboardButton(
                    "🐢 Conservative" + (" ✓" if risk_level == "CONSERVATIVE" else ""),
                    callback_data="demo:ai_risk:CONSERVATIVE"
                ),
            ],
            [
                InlineKeyboardButton(
                    "⚖️ Medium" + (" ✓" if risk_level == "MEDIUM" else ""),
                    callback_data="demo:ai_risk:MEDIUM"
                ),
            ],
            [
                InlineKeyboardButton(
                    "🔥 Aggressive" + (" ✓" if risk_level == "AGGRESSIVE" else ""),
                    callback_data="demo:ai_risk:AGGRESSIVE"
                ),
            ],
            # Max Position Size
            [
                InlineKeyboardButton("Max: 0.1 SOL", callback_data="demo:ai_max:0.1"),
                InlineKeyboardButton("Max: 0.5 SOL", callback_data="demo:ai_max:0.5"),
                InlineKeyboardButton("Max: 1 SOL", callback_data="demo:ai_max:1"),
            ],
            # Min Confidence
            [
                InlineKeyboardButton("Conf: 60%", callback_data="demo:ai_conf:0.6"),
                InlineKeyboardButton("Conf: 70%", callback_data="demo:ai_conf:0.7"),
                InlineKeyboardButton("Conf: 80%", callback_data="demo:ai_conf:0.8"),
            ],
            # Back
            [
                InlineKeyboardButton(f"{theme.BACK} Back to Settings", callback_data="demo:settings"),
            ],
        ]

        return text, InlineKeyboardMarkup(keyboard)

    @staticmethod
    def ai_auto_trade_status(
        enabled: bool,
        trades_today: int = 0,
        pnl_today: float = 0.0,
        last_trade: str = None,
        next_opportunity: str = None,
    ) -> Tuple[str, InlineKeyboardMarkup]:
        """
        AI Auto-Trade Status View - Show current AI trading activity.
        """
        theme = JarvisTheme

        status_emoji = f"{theme.ROCKET}" if enabled else "⚪"
        pnl_emoji = theme.PROFIT if pnl_today >= 0 else theme.LOSS
        pnl_sign = "+" if pnl_today >= 0 else ""

        text = f"""
{theme.AUTO} *AI TRADING STATUS*
━━━━━━━━━━━━━━━━━━━━━

{status_emoji} *Auto-Trade:* {'ACTIVE' if enabled else 'PAUSED'}

📈 *Today's Activity*
├ Trades: {trades_today}
├ {pnl_emoji} P&L: {pnl_sign}${abs(pnl_today):.2f}
"""
        if last_trade:
            text += f"└ Last Trade: {last_trade}\n"

        if next_opportunity:
            text += f"""
🎯 *Next Opportunity*
└ {next_opportunity}
"""

        text += f"""
━━━━━━━━━━━━━━━━━━━━━

{theme.AUTO} JARVIS is {'monitoring markets' if enabled else 'idle'}
"""

        keyboard = [
            [
                InlineKeyboardButton(
                    f"{'⏸️ Pause' if enabled else '▶️ Resume'}",
                    callback_data=f"demo:ai_auto_toggle:{not enabled}"
                ),
            ],
            [
                InlineKeyboardButton("📊 View AI Trades", callback_data="demo:ai_trades_history"),
            ],
            [
                InlineKeyboardButton(f"{theme.SETTINGS} AI Settings", callback_data="demo:ai_auto_settings"),
            ],
            [
                InlineKeyboardButton(f"{theme.BACK} Back", callback_data="demo:main"),
            ],
        ]

        return text, InlineKeyboardMarkup(keyboard)

    @staticmethod
    def fee_stats_view(
        fee_percent: float = 0.5,
        total_collected: float = 0.0,
        transaction_count: int = 0,
        recent_fees: List[Dict[str, Any]] = None,
    ) -> Tuple[str, InlineKeyboardMarkup]:
        """
        Fee statistics view - Show success fee collection stats.

        Displays:
        - Current fee rate (0.5% on wins)
        - Total fees collected
        - Recent fee transactions
        """
        theme = JarvisTheme
        recent_fees = recent_fees or []

        lines = [
            f"💰 *SUCCESS FEE STATS*",
            "━━━━━━━━━━━━━━━━━━━━━",
            "",
            f"📊 *Fee Structure*",
            f"├ Rate: {fee_percent}% on profits",
            f"├ Applied: Only on winning trades",
            f"└ Supports: JARVIS development",
            "",
            f"💵 *Total Collected*",
            f"└ ${total_collected:.4f}",
            "",
            f"📈 *Transactions*",
            f"└ {transaction_count} fee-bearing trades",
            "",
        ]

        if recent_fees:
            lines.extend([
                "📋 *Recent Fees*",
            ])
            for i, fee in enumerate(recent_fees[:5]):
                token = fee.get("token", "???")
                amount = fee.get("fee_amount", 0)
                pnl = fee.get("pnl_usd", 0)
                lines.append(f"├ {token}: ${amount:.4f} (${pnl:.2f} profit)")

            if len(recent_fees) > 5:
                lines.append(f"└ _...and {len(recent_fees) - 5} more_")
        else:
            lines.extend([
                "_No fees collected yet._",
                "_Trade profitably to see fees here._",
            ])

        lines.extend([
            "",
            "━━━━━━━━━━━━━━━━━━━━━",
            "_Fees support platform development._",
        ])

        text = "\n".join(lines)

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(f"📊 View Positions", callback_data="demo:positions"),
            ],
            [
                InlineKeyboardButton(f"{theme.SETTINGS} Settings", callback_data="demo:settings"),
            ],
            [
                InlineKeyboardButton(f"{theme.BACK} Main Menu", callback_data="demo:main"),
            ],
        ])

        return text, keyboard

    @staticmethod
    def pnl_report_view(
        positions: List[Dict[str, Any]] = None,
        total_pnl_usd: float = 0.0,
        total_pnl_percent: float = 0.0,
        winners: int = 0,
        losers: int = 0,
        best_trade: Dict[str, Any] = None,
        worst_trade: Dict[str, Any] = None,
    ) -> Tuple[str, InlineKeyboardMarkup]:
        """
        P&L Report View - Quick snapshot of portfolio performance.

        Shows:
        - Total P&L (USD and %)
        - Win/Loss breakdown
        - Best and worst performers
        """
        theme = JarvisTheme
        positions = positions or []

        pnl_emoji = "📈" if total_pnl_usd >= 0 else "📉"
        pnl_sign = "+" if total_pnl_usd >= 0 else ""

        total_trades = winners + losers
        win_rate = (winners / total_trades * 100) if total_trades > 0 else 0

        lines = [
            f"📊 *P&L REPORT*",
            "━━━━━━━━━━━━━━━━━━━━━",
            "",
            f"💰 *Total P&L*",
            f"└ {pnl_emoji} {pnl_sign}${abs(total_pnl_usd):.2f} ({pnl_sign}{total_pnl_percent:.1f}%)",
            "",
            f"📈 *Performance*",
            f"├ Winners: 🟢 {winners}",
            f"├ Losers: 🔴 {losers}",
            f"└ Win Rate: *{win_rate:.0f}%*",
            "",
        ]

        if best_trade:
            best_pnl = best_trade.get("pnl_pct", 0)
            lines.extend([
                f"🏆 *Best Trade*",
                f"└ {best_trade.get('symbol', '???')}: +{best_pnl:.1f}%",
                "",
            ])

        if worst_trade:
            worst_pnl = worst_trade.get("pnl_pct", 0)
            lines.extend([
                f"💀 *Worst Trade*",
                f"└ {worst_trade.get('symbol', '???')}: {worst_pnl:.1f}%",
                "",
            ])

        if positions:
            lines.append(f"📋 *Open Positions ({len(positions)})*")
            for pos in positions[:5]:
                symbol = pos.get("symbol", "???")
                pnl = pos.get("pnl_pct", 0)
                pnl_em = "🟢" if pnl >= 0 else "🔴"
                lines.append(f"├ {pnl_em} {symbol}: {pnl:+.1f}%")
            if len(positions) > 5:
                lines.append(f"└ _...and {len(positions) - 5} more_")
                lines.append(f"   _Tap 'View All Positions' below to expand_")
        else:
            lines.extend([
                "_No open positions_",
                "_Use Buy to enter trades_",
            ])

        lines.extend([
            "",
            "━━━━━━━━━━━━━━━━━━━━━",
        ])

        text = "\n".join(lines)

        # Add "View All" button when more than 5 positions
        keyboard_buttons = []
        if len(positions) > 5:
            keyboard_buttons.append([
                InlineKeyboardButton(f"📋 View All {len(positions)} Positions", callback_data="demo:positions_all"),
            ])

        keyboard_buttons.extend([
            [
                InlineKeyboardButton(f"📊 Positions", callback_data="demo:positions"),
                InlineKeyboardButton(f"📜 History", callback_data="demo:trade_history"),
            ],
            [
                InlineKeyboardButton(f"🔄 Refresh", callback_data="demo:pnl_report"),
                InlineKeyboardButton(f"{theme.BACK} Main Menu", callback_data="demo:main"),
            ],
        ])

        keyboard = InlineKeyboardMarkup(keyboard_buttons)

        return text, keyboard

    @staticmethod
    def pnl_alerts_overview(
        alerts: List[Dict[str, Any]] = None,
        positions: List[Dict[str, Any]] = None,
    ) -> Tuple[str, InlineKeyboardMarkup]:
        """
        P&L Alerts Overview - View and manage all active price alerts.

        Shows:
        - Active alerts with their trigger conditions
        - Triggered alerts history
        - Quick add buttons for positions without alerts
        """
        theme = JarvisTheme
        alerts = alerts or []
        positions = positions or []

        lines = [
            f"🔔 *P&L ALERTS*",
            "━━━━━━━━━━━━━━━━━━━━━",
            "",
        ]

        if not alerts:
            lines.extend([
                "_No active alerts_",
                "",
                "Set alerts to get notified when",
                "positions hit profit/loss targets!",
            ])
        else:
            active_count = len([a for a in alerts if not a.get("triggered")])
            triggered_count = len([a for a in alerts if a.get("triggered")])

            lines.extend([
                f"📊 *Active Alerts:* {active_count}",
                f"✅ *Triggered:* {triggered_count}",
                "",
            ])

            for alert in alerts[:5]:  # Show max 5
                symbol = alert.get("symbol", "???")
                alert_type = alert.get("type", "pnl")  # pnl, price, percent
                target = alert.get("target", 0)
                direction = alert.get("direction", "above")  # above, below
                triggered = alert.get("triggered", False)

                if triggered:
                    status = "✅"
                else:
                    status = "🔔"

                if alert_type == "pnl":
                    direction_emoji = "📈" if direction == "above" else "📉"
                    lines.append(f"{status} *{symbol}* - {direction_emoji} ${target:+.2f}")
                elif alert_type == "percent":
                    direction_emoji = "📈" if direction == "above" else "📉"
                    lines.append(f"{status} *{symbol}* - {direction_emoji} {target:+.1f}%")
                else:  # price
                    lines.append(f"{status} *{symbol}* - Price ${target:.8f}")

        text = "\n".join(lines)

        keyboard = []

        # Add alert buttons for positions
        if positions:
            for pos in positions[:4]:  # Max 4 position alert buttons
                symbol = pos.get("symbol", "???")
                pos_id = pos.get("id", "0")
                keyboard.append([
                    InlineKeyboardButton(
                        f"🔔 Add Alert: {symbol}",
                        callback_data=f"demo:alert_setup:{pos_id}"
                    ),
                ])

        keyboard.extend([
            [
                InlineKeyboardButton("🗑️ Clear Triggered", callback_data="demo:clear_triggered_alerts"),
            ],
            [
                InlineKeyboardButton(f"{theme.CHART} Positions", callback_data="demo:positions"),
                InlineKeyboardButton(f"{theme.BACK} Back", callback_data="demo:main"),
            ],
        ])

        return text, InlineKeyboardMarkup(keyboard)

    @staticmethod
    def position_alert_setup(
        position: Dict[str, Any],
        existing_alerts: List[Dict[str, Any]] = None,
    ) -> Tuple[str, InlineKeyboardMarkup]:
        """
        Set up P&L alerts for a specific position.

        Shows:
        - Current position info
        - Quick alert presets (+25%, +50%, +100%, -10%, -25%)
        - Existing alerts for this position
        """
        theme = JarvisTheme
        existing_alerts = existing_alerts or []

        symbol = position.get("symbol", "???")
        pos_id = position.get("id", "0")
        pnl_pct = position.get("pnl_pct", 0)
        pnl_usd = position.get("pnl_usd", 0)
        entry_price = position.get("entry_price", 0)
        current_price = position.get("current_price", 0)

        pnl_emoji = theme.PROFIT if pnl_pct >= 0 else theme.LOSS
        pnl_sign = "+" if pnl_pct >= 0 else ""

        lines = [
            f"🔔 *SET ALERT: {symbol}*",
            "━━━━━━━━━━━━━━━━━━━━━",
            "",
            f"*Current Position*",
            f"├ Entry: ${entry_price:.8f}",
            f"├ Now: ${current_price:.8f}",
            f"└ P&L: {pnl_emoji} {pnl_sign}{pnl_pct:.1f}% (${pnl_usd:+.2f})",
            "",
        ]

        # Show existing alerts
        pos_alerts = [a for a in existing_alerts if a.get("position_id") == pos_id]
        if pos_alerts:
            lines.append("*Active Alerts:*")
            for alert in pos_alerts:
                target = alert.get("target", 0)
                alert_type = alert.get("type", "percent")
                direction = alert.get("direction", "above")
                dir_emoji = "📈" if direction == "above" else "📉"
                if alert_type == "percent":
                    lines.append(f"  {dir_emoji} {target:+.1f}%")
                else:
                    lines.append(f"  {dir_emoji} ${target:+.2f}")
            lines.append("")

        lines.extend([
            "*Quick Presets*",
            "_Select a trigger level:_",
        ])

        text = "\n".join(lines)

        keyboard = [
            # Profit alerts
            [
                InlineKeyboardButton("📈 +25%", callback_data=f"demo:create_alert:{pos_id}:percent:25"),
                InlineKeyboardButton("📈 +50%", callback_data=f"demo:create_alert:{pos_id}:percent:50"),
                InlineKeyboardButton("📈 +100%", callback_data=f"demo:create_alert:{pos_id}:percent:100"),
            ],
            # Loss alerts
            [
                InlineKeyboardButton("📉 -10%", callback_data=f"demo:create_alert:{pos_id}:percent:-10"),
                InlineKeyboardButton("📉 -25%", callback_data=f"demo:create_alert:{pos_id}:percent:-25"),
                InlineKeyboardButton("📉 -50%", callback_data=f"demo:create_alert:{pos_id}:percent:-50"),
            ],
            # Custom alert
            [
                InlineKeyboardButton("✏️ Custom Alert", callback_data=f"demo:custom_alert:{pos_id}"),
            ],
            # Delete existing alerts for this position
            [
                InlineKeyboardButton("🗑️ Delete Alerts", callback_data=f"demo:delete_pos_alerts:{pos_id}"),
            ],
            [
                InlineKeyboardButton("🔔 All Alerts", callback_data="demo:pnl_alerts"),
                InlineKeyboardButton(f"{theme.BACK} Back", callback_data="demo:positions"),
            ],
        ]

        return text, InlineKeyboardMarkup(keyboard)

    @staticmethod
    def alert_created_success(
        symbol: str,
        alert_type: str,
        target: float,
        direction: str,
    ) -> Tuple[str, InlineKeyboardMarkup]:
        """Show success message after creating an alert."""
        theme = JarvisTheme

        dir_emoji = "📈" if direction == "above" else "📉"
        type_text = "%" if alert_type == "percent" else " USD"

        text = f"""
{theme.SUCCESS} *ALERT CREATED*
━━━━━━━━━━━━━━━━━━━━━

*{symbol}*
{dir_emoji} Trigger: {target:+.1f}{type_text}

You'll be notified when this
position hits your target!

━━━━━━━━━━━━━━━━━━━━━
"""

        keyboard = [
            [
                InlineKeyboardButton("🔔 View All Alerts", callback_data="demo:pnl_alerts"),
            ],
            [
                InlineKeyboardButton(f"{theme.CHART} Positions", callback_data="demo:positions"),
                InlineKeyboardButton(f"{theme.BACK} Main Menu", callback_data="demo:main"),
            ],
        ]

        return text, InlineKeyboardMarkup(keyboard)

    @staticmethod
    def dca_overview(
        dca_plans: List[Dict[str, Any]] = None,
        total_invested: float = 0.0,
        total_tokens_bought: int = 0,
    ) -> Tuple[str, InlineKeyboardMarkup]:
        """
        DCA Overview - View and manage Dollar Cost Averaging plans.

        Shows:
        - Active DCA plans with next execution time
        - Total invested via DCA
        - DCA execution history
        """
        theme = JarvisTheme
        dca_plans = dca_plans or []

        active_plans = [p for p in dca_plans if p.get("active", True)]
        paused_plans = [p for p in dca_plans if not p.get("active", True)]

        lines = [
            f"📅 *DCA (DOLLAR COST AVERAGE)*",
            "━━━━━━━━━━━━━━━━━━━━━",
            "",
        ]

        if not dca_plans:
            lines.extend([
                "_No DCA plans configured_",
                "",
                "DCA automatically buys tokens at",
                "regular intervals to average your",
                "entry price over time.",
                "",
                "*Benefits:*",
                "• Reduces timing risk",
                "• Removes emotional decisions",
                "• Builds positions gradually",
            ])
        else:
            lines.extend([
                f"💰 *Total Invested:* {total_invested:.2f} SOL",
                f"📊 *Active Plans:* {len(active_plans)}",
                f"⏸️ *Paused:* {len(paused_plans)}",
                "",
            ])

            for plan in active_plans[:5]:  # Show max 5
                symbol = plan.get("symbol", "???")
                amount = plan.get("amount", 0)
                frequency = plan.get("frequency", "daily")
                executions = plan.get("executions", 0)
                next_exec = plan.get("next_execution", "Soon")

                freq_emoji = {"hourly": "⏰", "daily": "📅", "weekly": "📆"}.get(frequency, "📅")

                lines.extend([
                    f"{freq_emoji} *{symbol}*",
                    f"├ Amount: {amount} SOL / {frequency}",
                    f"├ Executions: {executions}",
                    f"└ Next: {next_exec}",
                    "",
                ])

        text = "\n".join(lines)

        keyboard = [
            [
                InlineKeyboardButton("➕ New DCA Plan", callback_data="demo:dca_new"),
            ],
        ]

        # Add manage buttons for each plan
        for plan in active_plans[:3]:  # Max 3
            plan_id = plan.get("id", "0")
            symbol = plan.get("symbol", "???")
            keyboard.append([
                InlineKeyboardButton(f"⏸️ Pause {symbol}", callback_data=f"demo:dca_pause:{plan_id}"),
                InlineKeyboardButton(f"🗑️ Delete", callback_data=f"demo:dca_delete:{plan_id}"),
            ])

        keyboard.extend([
            [
                InlineKeyboardButton("📊 DCA History", callback_data="demo:dca_history"),
            ],
            [
                InlineKeyboardButton(f"{theme.BACK} Back", callback_data="demo:main"),
            ],
        ])

        return text, InlineKeyboardMarkup(keyboard)

    @staticmethod
    def dca_setup(
        token_symbol: str = None,
        token_address: str = None,
        token_ref: str = None,
        watchlist: List[Dict[str, Any]] = None,
    ) -> Tuple[str, InlineKeyboardMarkup]:
        """
        DCA Setup - Configure a new DCA plan.

        If no token specified, shows watchlist to choose from.
        If token specified, shows amount and frequency options.
        """
        theme = JarvisTheme
        watchlist = watchlist or []

        if not token_symbol:
            # Show token selection
            lines = [
                f"📅 *NEW DCA PLAN*",
                "━━━━━━━━━━━━━━━━━━━━━",
                "",
                "*Select a token to DCA:*",
                "",
            ]

            keyboard = []

            if watchlist:
                for token in watchlist[:6]:  # Max 6
                    sym = token.get("symbol", "???")
                    token_id = token.get("token_id") or token.get("address", "")
                    keyboard.append([
                        InlineKeyboardButton(f"📈 {sym}", callback_data=f"demo:dca_select:{token_id}"),
                    ])
            else:
                lines.append("_Add tokens to watchlist first!_")

            keyboard.append([
                InlineKeyboardButton("✏️ Enter Address", callback_data="demo:dca_input"),
            ])
            keyboard.append([
                InlineKeyboardButton(f"{theme.BACK} Back", callback_data="demo:dca"),
            ])

            text = "\n".join(lines)

        else:
            # Show DCA configuration
            short_addr = f"{token_address[:6]}...{token_address[-4:]}" if token_address else "N/A"
            token_ref = token_ref or token_address

            lines = [
                f"📅 *CONFIGURE DCA: {token_symbol}*",
                "━━━━━━━━━━━━━━━━━━━━━",
                "",
                f"*Token:* {token_symbol}",
                f"*Address:* `{short_addr}`",
                "",
                "*Select amount per buy:*",
            ]

            text = "\n".join(lines)

            keyboard = [
                # Amount options
                [
                    InlineKeyboardButton("0.1 SOL", callback_data=f"demo:dca_amount:{token_ref}:0.1"),
                    InlineKeyboardButton("0.25 SOL", callback_data=f"demo:dca_amount:{token_ref}:0.25"),
                    InlineKeyboardButton("0.5 SOL", callback_data=f"demo:dca_amount:{token_ref}:0.5"),
                ],
                [
                    InlineKeyboardButton("1 SOL", callback_data=f"demo:dca_amount:{token_ref}:1"),
                    InlineKeyboardButton("2 SOL", callback_data=f"demo:dca_amount:{token_ref}:2"),
                    InlineKeyboardButton("5 SOL", callback_data=f"demo:dca_amount:{token_ref}:5"),
                ],
                [
                    InlineKeyboardButton(f"{theme.BACK} Back", callback_data="demo:dca_new"),
                ],
            ]

        return text, InlineKeyboardMarkup(keyboard)

    @staticmethod
    def dca_frequency_select(
        token_symbol: str,
        token_address: str,
        amount: float,
        token_ref: Optional[str] = None,
    ) -> Tuple[str, InlineKeyboardMarkup]:
        """Select DCA frequency."""
        theme = JarvisTheme

        short_addr = f"{token_address[:6]}...{token_address[-4:]}"
        token_ref = token_ref or token_address

        lines = [
            f"📅 *DCA FREQUENCY*",
            "━━━━━━━━━━━━━━━━━━━━━",
            "",
            f"*Token:* {token_symbol}",
            f"*Amount:* {amount} SOL per buy",
            "",
            "*How often should we buy?*",
        ]

        text = "\n".join(lines)

        keyboard = [
            [
                InlineKeyboardButton("⏰ Every Hour", callback_data=f"demo:dca_create:{token_ref}:{amount}:hourly"),
            ],
            [
                InlineKeyboardButton("📅 Daily (Recommended)", callback_data=f"demo:dca_create:{token_ref}:{amount}:daily"),
            ],
            [
                InlineKeyboardButton("📆 Weekly", callback_data=f"demo:dca_create:{token_ref}:{amount}:weekly"),
            ],
            [
                InlineKeyboardButton(f"{theme.BACK} Back", callback_data=f"demo:dca_select:{token_ref}"),
            ],
        ]

        return text, InlineKeyboardMarkup(keyboard)

    @staticmethod
    def dca_plan_created(
        token_symbol: str,
        amount: float,
        frequency: str,
        first_execution: str = "Now",
    ) -> Tuple[str, InlineKeyboardMarkup]:
        """Show success after creating DCA plan."""
        theme = JarvisTheme

        freq_emoji = {"hourly": "⏰", "daily": "📅", "weekly": "📆"}.get(frequency, "📅")

        text = f"""
{theme.SUCCESS} *DCA PLAN CREATED*
━━━━━━━━━━━━━━━━━━━━━

*{token_symbol}*
{freq_emoji} Buy {amount} SOL {frequency}

*First Execution:* {first_execution}

Your DCA plan is now active!
We'll automatically buy {token_symbol}
at regular intervals.

━━━━━━━━━━━━━━━━━━━━━
_Cancel anytime from DCA menu_
"""

        keyboard = [
            [
                InlineKeyboardButton("📅 View DCA Plans", callback_data="demo:dca"),
            ],
            [
                InlineKeyboardButton(f"{theme.CHART} Positions", callback_data="demo:positions"),
                InlineKeyboardButton(f"{theme.BACK} Main Menu", callback_data="demo:main"),
            ],
        ]

        return text, InlineKeyboardMarkup(keyboard)

    # ========== TRAILING STOP-LOSS ==========

    @staticmethod
    def trailing_stop_overview(
        trailing_stops: List[Dict[str, Any]] = None,
        positions: List[Dict[str, Any]] = None,
    ) -> Tuple[str, InlineKeyboardMarkup]:
        """
        Trailing Stop-Loss Overview - View and manage trailing stops.

        Trailing stops automatically adjust upward as price rises,
        locking in profits while protecting against drawdowns.
        """
        theme = JarvisTheme
        trailing_stops = trailing_stops or []
        positions = positions or []

        active_stops = [s for s in trailing_stops if s.get("active", True)]

        lines = [
            f"🛡️ *TRAILING STOP-LOSS*",
            "━━━━━━━━━━━━━━━━━━━━━",
            "",
        ]

        if not trailing_stops:
            lines.extend([
                "_No trailing stops configured_",
                "",
                "*What is a Trailing Stop?*",
                "A trailing stop moves UP as price rises,",
                "locking in profits automatically.",
                "",
                "*Example:*",
                "• Buy at $0.001, set 10% trail",
                "• Price hits $0.002 → stop at $0.0018",
                "• Price hits $0.003 → stop at $0.0027",
                "• Price drops to $0.0025 → SOLD",
                "",
                "_Profit locked in automatically!_",
            ])
        else:
            lines.extend([
                f"🛡️ *Active Stops:* {len(active_stops)}",
                f"💰 *Protected Value:* ${sum(s.get('protected_value', 0) for s in active_stops):.2f}",
                "",
            ])

            for stop in active_stops[:5]:
                symbol = stop.get("symbol", "???")
                trail_pct = stop.get("trail_percent", 10)
                current_stop = stop.get("current_stop_price", 0)
                highest_price = stop.get("highest_price", 0)
                protected_pnl = stop.get("protected_pnl", 0)

                pnl_emoji = theme.PROFIT if protected_pnl >= 0 else "⚠️"

                lines.extend([
                    f"🛡️ *{symbol}*",
                    f"├ Trail: {trail_pct}%",
                    f"├ Stop Price: ${current_stop:.8f}",
                    f"├ Peak: ${highest_price:.8f}",
                    f"└ Protected P&L: {pnl_emoji} {'+' if protected_pnl >= 0 else ''}{protected_pnl:.1f}%",
                    "",
                ])

        text = "\n".join(lines)

        keyboard = []

        # Show buttons for each active stop
        for stop in active_stops[:4]:
            stop_id = stop.get("id", "")
            symbol = stop.get("symbol", "???")
            keyboard.append([
                InlineKeyboardButton(f"✏️ Edit {symbol}", callback_data=f"demo:tsl_edit:{stop_id}"),
                InlineKeyboardButton(f"❌ Remove", callback_data=f"demo:tsl_delete:{stop_id}"),
            ])

        # Add new trailing stop (if positions available)
        if positions:
            keyboard.append([
                InlineKeyboardButton("➕ Add Trailing Stop", callback_data="demo:tsl_new"),
            ])

        keyboard.extend([
            [
                InlineKeyboardButton(f"{theme.CHART} Positions", callback_data="demo:positions"),
                InlineKeyboardButton(f"{theme.BACK} Main Menu", callback_data="demo:main"),
            ],
        ])

        return text, InlineKeyboardMarkup(keyboard)

    @staticmethod
    def trailing_stop_setup(
        position: Dict[str, Any] = None,
        positions: List[Dict[str, Any]] = None,
    ) -> Tuple[str, InlineKeyboardMarkup]:
        """
        Trailing Stop Setup - Configure a trailing stop for a position.

        If no position provided, shows position selection.
        If position provided, shows trail percentage options.
        """
        theme = JarvisTheme

        if not position:
            # Show position selection
            positions = positions or []

            lines = [
                f"🛡️ *ADD TRAILING STOP*",
                "━━━━━━━━━━━━━━━━━━━━━",
                "",
                "*Select Position:*",
                "",
            ]

            if not positions:
                lines.append("_No open positions_")
            else:
                for pos in positions[:6]:
                    symbol = pos.get("symbol", "???")
                    pnl_pct = pos.get("pnl_pct", 0)
                    pnl_emoji = theme.PROFIT if pnl_pct >= 0 else theme.LOSS
                    lines.append(f"{pnl_emoji} {symbol} ({'+' if pnl_pct >= 0 else ''}{pnl_pct:.1f}%)")

            text = "\n".join(lines)

            keyboard = []
            for pos in positions[:6]:
                pos_id = pos.get("id", "")
                symbol = pos.get("symbol", "???")
                keyboard.append([
                    InlineKeyboardButton(f"🛡️ {symbol}", callback_data=f"demo:tsl_select:{pos_id}")
                ])

            keyboard.append([
                InlineKeyboardButton(f"{theme.BACK} Back", callback_data="demo:trailing_stops"),
            ])

        else:
            # Show trail percentage options
            symbol = position.get("symbol", "???")
            entry = position.get("entry_price", 0)
            current = position.get("current_price", 0)
            pnl_pct = position.get("pnl_pct", 0)

            lines = [
                f"🛡️ *TRAILING STOP: {symbol}*",
                "━━━━━━━━━━━━━━━━━━━━━",
                "",
                f"*Entry:* ${entry:.8f}",
                f"*Current:* ${current:.8f}",
                f"*P&L:* {'+' if pnl_pct >= 0 else ''}{pnl_pct:.1f}%",
                "",
                "*Select Trail Distance:*",
                "_How far below peak to trigger sell_",
                "",
                "• 5% - Tight (more frequent sells)",
                "• 10% - Standard (recommended)",
                "• 15% - Loose (ride bigger swings)",
                "• 20% - Wide (max profit potential)",
            ]

            text = "\n".join(lines)
            pos_id = position.get("id", "")

            keyboard = [
                [
                    InlineKeyboardButton("5%", callback_data=f"demo:tsl_create:{pos_id}:5"),
                    InlineKeyboardButton("10% ⭐", callback_data=f"demo:tsl_create:{pos_id}:10"),
                ],
                [
                    InlineKeyboardButton("15%", callback_data=f"demo:tsl_create:{pos_id}:15"),
                    InlineKeyboardButton("20%", callback_data=f"demo:tsl_create:{pos_id}:20"),
                ],
                [
                    InlineKeyboardButton("Custom %", callback_data=f"demo:tsl_custom:{pos_id}"),
                ],
                [
                    InlineKeyboardButton(f"{theme.BACK} Back", callback_data="demo:tsl_new"),
                ],
            ]

        return text, InlineKeyboardMarkup(keyboard)

    @staticmethod
    def trailing_stop_created(
        symbol: str,
        trail_percent: float,
        initial_stop: float,
        current_price: float,
    ) -> Tuple[str, InlineKeyboardMarkup]:
        """Show success after creating trailing stop."""
        theme = JarvisTheme

        text = f"""
{theme.SUCCESS} *TRAILING STOP CREATED*
━━━━━━━━━━━━━━━━━━━━━

🛡️ *{symbol}* - {trail_percent}% Trail

*Current Price:* ${current_price:.8f}
*Initial Stop:* ${initial_stop:.8f}

The stop will automatically move UP
as the price increases, locking in
profits along the way.

━━━━━━━━━━━━━━━━━━━━━
_Stop updates every 30 seconds_
"""

        keyboard = [
            [
                InlineKeyboardButton("🛡️ View All Stops", callback_data="demo:trailing_stops"),
            ],
            [
                InlineKeyboardButton(f"{theme.CHART} Positions", callback_data="demo:positions"),
                InlineKeyboardButton(f"{theme.BACK} Main Menu", callback_data="demo:main"),
            ],
        ]

        return text, InlineKeyboardMarkup(keyboard)

    # ========== END TRAILING STOP-LOSS ==========

    @staticmethod
    def buy_confirmation(
        token_symbol: str,
        token_address: str,
        amount_sol: float,
        estimated_tokens: float,
        price_usd: float,
        token_ref: Optional[str] = None,
    ) -> Tuple[str, InlineKeyboardMarkup]:
        """Build buy confirmation screen."""
        theme = JarvisTheme
        token_ref = token_ref or token_address

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
                InlineKeyboardButton(f"{theme.SUCCESS} Confirm Buy", callback_data=f"demo:execute_buy:{token_ref}:{amount_sol}"),
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
            safe_symbol = escape_md(symbol)
            change_24h = token.get("change_24h", 0)
            volume = token.get("volume", 0)
            liquidity = token.get("liquidity", 0)
            token_ref = token.get("token_id") or token.get("address", "")

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

            if token_ref:
                # Build button row with chart URL if available
                chart_url = token.get("chart_url", f"https://dexscreener.com/solana/{token_ref}")
                keyboard.append([
                    InlineKeyboardButton(
                        f"{theme.BUY} Buy",
                        callback_data=f"demo:quick_buy:{token_ref}"
                    ),
                    InlineKeyboardButton(
                        f"{theme.CHART} Chart",
                        url=chart_url
                    ),
                    InlineKeyboardButton(
                        f"🔍 Analyze",
                        callback_data=f"demo:analyze:{token_ref}"
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
        trending: List[Dict[str, Any]] = None,
        volume_leaders: List[Dict[str, Any]] = None,
        near_picks: List[Dict[str, Any]] = None,
        pick_stats: Dict[str, Any] = None,
    ) -> Tuple[str, InlineKeyboardMarkup]:
        """
        Show AI-powered conviction picks from Grok with comprehensive market data.

        Includes:
        - High conviction picks with entry criteria
        - Near-conviction tokens (close to triggering)
        - Volume leaders (high activity)
        - Trending tokens summary
        - Historical pick performance
        """
        theme = JarvisTheme

        # Market context
        regime = market_regime or {}
        regime_name = regime.get("regime", "NEUTRAL")
        risk_level = regime.get("risk_level", "NORMAL")
        btc_change = regime.get("btc_change_24h", 0)
        sol_change = regime.get("sol_change_24h", 0)
        fear_greed = regime.get("fear_greed", 50)

        regime_emoji = {"BULL": "🟢", "BEAR": "🔴"}.get(regime_name, "🟡")
        risk_emoji = {"LOW": "🟢", "NORMAL": "🟡", "HIGH": "🟠", "EXTREME": "🔴"}.get(risk_level, "⚪")

        # Fear/Greed emoji
        if fear_greed >= 75:
            fg_emoji = "🤑"
            fg_label = "Extreme Greed"
        elif fear_greed >= 55:
            fg_emoji = "😊"
            fg_label = "Greed"
        elif fear_greed >= 45:
            fg_emoji = "😐"
            fg_label = "Neutral"
        elif fear_greed >= 25:
            fg_emoji = "😰"
            fg_label = "Fear"
        else:
            fg_emoji = "😱"
            fg_label = "Extreme Fear"

        lines = [
            f"{theme.AUTO} *AI CONVICTION PICKS*",
            "━━━━━━━━━━━━━━━━━━━━━",
            "",
            f"📊 *Market Overview*",
            f"├ Regime: {regime_emoji} *{regime_name}* | Risk: {risk_emoji} *{risk_level}*",
            f"├ BTC: *{btc_change:+.1f}%* | SOL: *{sol_change:+.1f}%*",
            f"└ {fg_emoji} Fear/Greed: *{fear_greed}* ({fg_label})",
            "",
        ]

        # Pick statistics if available
        stats = pick_stats or {}
        if stats:
            win_rate = stats.get("win_rate", 0)
            avg_gain = stats.get("avg_gain", 0)
            total_picks = stats.get("total_picks", 0)
            lines.extend([
                f"📈 *Pick Performance (30d)*",
                f"├ Win Rate: *{win_rate:.0f}%* | Avg Gain: *+{avg_gain:.0f}%*",
                f"└ Total Picks: *{total_picks}*",
                "",
            ])

        lines.extend([
            "🎯 *Selection Criteria:*",
            "├ Entry timing < 50% pump (67% TP rate)",
            "├ Buy/sell ratio ≥ 2.0x",
            "└ Multi-sighting validation",
            "",
            "━━━━━━━━━━━━━━━━━━━━━",
        ])

        keyboard = []

        # High Conviction Picks
        if picks:
            lines.extend([
                "",
                f"🔥 *HIGH CONVICTION ({len(picks)})*",
            ])
            for pick in picks[:10]:  # Show all 10 picks instead of just 3
                symbol = pick.get("symbol", "???")
                conviction = pick.get("conviction", "MEDIUM")
                thesis = pick.get("thesis", "")[:40]
                token_ref = pick.get("token_id") or pick.get("address", "")
                tp = pick.get("tp_target", 0)
                sl = pick.get("sl_target", 0)
                ai_confidence = pick.get("ai_confidence", 0)
                change = pick.get("change_24h", 0)
                volume = pick.get("volume_24h", 0)

                conv_emoji = {"HIGH": "🔥", "MEDIUM": "📊", "LOW": "📉"}.get(conviction, "📊")
                change_emoji = "🟢" if change >= 0 else "🔴"

                lines.append(f"{conv_emoji} *{symbol}* | {change_emoji} {change:+.1f}%")
                if thesis:
                    lines.append(f"   _{thesis}_")

                details = []
                if tp:
                    details.append(f"TP +{tp}%")
                if sl:
                    details.append(f"SL -{sl}%")
                if ai_confidence > 0:
                    conf_pct = int(ai_confidence * 100)
                    details.append(f"AI {conf_pct}%")
                if volume > 0:
                    vol_k = volume / 1000
                    details.append(f"Vol ${vol_k:.0f}K")

                if details:
                    lines.append(f"   {' | '.join(details)}")
                lines.append("")

                if token_ref:
                    # DexScreener chart link
                    chart_url = pick.get("chart_url", f"https://dexscreener.com/solana/{token_ref}")

                    keyboard.append([
                        InlineKeyboardButton(
                            f"{theme.BUY} Buy {symbol}",
                            callback_data=f"demo:quick_buy:{token_ref}"
                        ),
                        InlineKeyboardButton(
                            f"{theme.CHART} Chart",
                            url=chart_url
                        ),
                    ])
        else:
            lines.extend([
                "",
                f"🔥 *HIGH CONVICTION*",
                "_No picks qualify right now._",
                "_AI is monitoring for setups..._",
                "",
            ])

        # Near-Conviction Picks (tokens close to triggering)
        near_picks = near_picks or []
        if near_picks:
            lines.extend([
                "━━━━━━━━━━━━━━━━━━━━━",
                "",
                f"⏳ *NEAR CONVICTION ({len(near_picks)})*",
                "_Almost meeting criteria:_",
            ])
            for np in near_picks[:3]:
                symbol = np.get("symbol", "???")
                missing = np.get("missing_criteria", "timing")
                score = np.get("score", 0)
                change = np.get("change_24h", 0)
                change_emoji = "🟢" if change >= 0 else "🔴"

                lines.append(f"📊 *{symbol}* {change_emoji} {change:+.1f}% (Score: {score}/100)")
                lines.append(f"   _Missing: {missing}_")
            lines.append("")

        # Volume Leaders
        volume_leaders = volume_leaders or []
        if volume_leaders:
            lines.extend([
                "━━━━━━━━━━━━━━━━━━━━━",
                "",
                f"💎 *VOLUME LEADERS*",
            ])
            for vl in volume_leaders[:4]:
                symbol = vl.get("symbol", "???")
                volume = vl.get("volume_24h", 0)
                change = vl.get("change_24h", 0)
                change_emoji = "🟢" if change >= 0 else "🔴"
                vol_m = volume / 1_000_000 if volume >= 1_000_000 else volume / 1000
                vol_unit = "M" if volume >= 1_000_000 else "K"

                lines.append(f"├ {symbol}: ${vol_m:.1f}{vol_unit} {change_emoji} {change:+.1f}%")
            lines.append("")

        # Trending Tokens
        trending = trending or []
        if trending:
            lines.extend([
                "━━━━━━━━━━━━━━━━━━━━━",
                "",
                f"🔥 *TRENDING NOW*",
            ])
            for t in trending[:4]:
                symbol = t.get("symbol", "???")
                change = t.get("change_24h", 0)
                sentiment = t.get("sentiment", "neutral")
                change_emoji = "🟢" if change >= 0 else "🔴"
                sent_emoji = {"bullish": "🟢", "bearish": "🔴", "very_bullish": "🚀"}.get(sentiment.lower(), "🟡")

                lines.append(f"├ {symbol}: {change_emoji} {change:+.1f}% {sent_emoji}")
            lines.append("")

        lines.extend([
            "━━━━━━━━━━━━━━━━━━━━━",
            f"_Updated: {datetime.now().strftime('%H:%M:%S')}_",
        ])

        text = "\n".join(lines)

        keyboard.extend([
            [
                InlineKeyboardButton(f"📊 Sentiment Hub", callback_data="demo:hub"),
                InlineKeyboardButton(f"🔥 Trending", callback_data="demo:trending"),
            ],
            [
                InlineKeyboardButton(f"{theme.REFRESH} Refresh", callback_data="demo:ai_picks"),
            ],
            [
                InlineKeyboardButton(f"{theme.BACK} Back", callback_data="demo:main"),
            ],
        ])

        return text, InlineKeyboardMarkup(keyboard)

    # ========== SENTIMENT HUB - COMPREHENSIVE TRADING DASHBOARD ==========

    @staticmethod
    def sentiment_hub_main(
        market_regime: Dict[str, Any] = None,
        last_report_time: datetime = None,
        report_interval_minutes: int = 15,
        wallet_connected: bool = False,
    ) -> Tuple[str, InlineKeyboardMarkup]:
        """
        Main Sentiment Hub - Beautiful comprehensive trading dashboard.

        Sections:
        - Market Overview (regime, countdown)
        - Asset Categories (Blue Chips, XStocks, PreStocks, Indexes, Trending)
        - Top 10 Picks with TP/SL
        - Market News & Analysis
        """
        theme = JarvisTheme

        regime = market_regime or {}
        regime_name = regime.get("regime", "NEUTRAL")
        risk_level = regime.get("risk_level", "NORMAL")
        btc_change = regime.get("btc_change_24h", 0)
        sol_change = regime.get("sol_change_24h", 0)

        # Calculate countdown to next report
        if last_report_time:
            next_report = last_report_time + timedelta(minutes=report_interval_minutes)
            time_left = next_report - datetime.now(timezone.utc)
            if time_left.total_seconds() > 0:
                mins_left = int(time_left.total_seconds() / 60)
                secs_left = int(time_left.total_seconds() % 60)
                countdown = f"{mins_left}:{secs_left:02d}"
                freshness = "🟢 FRESH" if mins_left >= 12 else "🟡 AGING" if mins_left >= 5 else "🟠 STALE"
            else:
                countdown = "UPDATING..."
                freshness = "⏳ REFRESH"
        else:
            countdown = "15:00"
            freshness = "🟢 FRESH"

        # Regime display
        regime_emoji = {"BULL": "🟢", "BEAR": "🔴"}.get(regime_name, "🟡")
        risk_emoji = {"LOW": "🟢", "NORMAL": "🟡", "HIGH": "🟠", "EXTREME": "🔴"}.get(risk_level, "⚪")

        # Entry advice based on freshness
        if "FRESH" in freshness:
            entry_advice = "✅ *Good time to enter* - Report is fresh"
        elif "AGING" in freshness:
            entry_advice = "⚡ Consider waiting for refresh"
        else:
            entry_advice = "⚠️ Wait for fresh report before risky entries"

        lines = [
            f"📊 *JARVIS SENTIMENT HUB*",
            f"{'━' * 25}",
            "",
            f"┌{'─' * 23}┐",
            f"│ {regime_emoji} Market: *{regime_name}*        │",
            f"│ {risk_emoji} Risk: *{risk_level}*          │",
            f"│ ⏱ Next Report: *{countdown}*   │",
            f"│ {freshness}                │",
            f"└{'─' * 23}┘",
            "",
            f"BTC: {'📈' if btc_change >= 0 else '📉'} {btc_change:+.1f}% | SOL: {'📈' if sol_change >= 0 else '📉'} {sol_change:+.1f}%",
            "",
            entry_advice,
            "",
            f"{'━' * 25}",
            "*SELECT CATEGORY:*",
        ]

        text = "\n".join(lines)

        # Beautiful category buttons
        keyboard = [
            # Row 1: Core categories
            [
                InlineKeyboardButton("💎 Blue Chips", callback_data="demo:hub_bluechips"),
                InlineKeyboardButton("🔥 TOP 10", callback_data="demo:hub_top10"),
            ],
            # Row 2: Stocks
            [
                InlineKeyboardButton("📈 XStocks", callback_data="demo:hub_xstocks"),
                InlineKeyboardButton("🌅 PreStocks", callback_data="demo:hub_prestocks"),
            ],
            # Row 3: Markets
            [
                InlineKeyboardButton("📊 Indexes", callback_data="demo:hub_indexes"),
                InlineKeyboardButton("🔥 Trending", callback_data="demo:hub_trending"),
            ],
            # Row 4: Reports
            [
                InlineKeyboardButton("📰 Market News", callback_data="demo:hub_news"),
                InlineKeyboardButton("🌍 Traditional", callback_data="demo:hub_traditional"),
            ],
            # Row 5: Wallet & Actions
            [
                InlineKeyboardButton("💳 Wallet", callback_data="demo:hub_wallet"),
                InlineKeyboardButton(f"{theme.REFRESH} Refresh", callback_data="demo:sentiment_hub"),
            ],
            [
                InlineKeyboardButton(f"{theme.BACK} Main Menu", callback_data="demo:main"),
            ],
        ]

        return text, InlineKeyboardMarkup(keyboard)

    @staticmethod
    def sentiment_hub_section(
        section: str,
        picks: List[Dict[str, Any]] = None,
        market_regime: Dict[str, Any] = None,
    ) -> Tuple[str, InlineKeyboardMarkup]:
        """
        Individual section view within the Sentiment Hub.

        Each section shows relevant tokens/assets with:
        - Current price and 24h change
        - Sentiment score and signal
        - TP/SL recommendations
        - Buy with auto-SL buttons
        """
        theme = JarvisTheme
        picks = picks or []

        # Section headers and emojis
        section_config = {
            "bluechips": {
                "title": "💎 BLUE CHIPS",
                "desc": "Established tokens with proven track records",
                "emoji": "💎",
            },
            "top10": {
                "title": "🔥 JARVIS TOP 10",
                "desc": "AI-selected high-conviction picks with TP/SL",
                "emoji": "🔥",
            },
            "xstocks": {
                "title": "📈 XSTOCKS",
                "desc": "Tokenized stocks on Solana (backed.fi)",
                "emoji": "📈",
            },
            "prestocks": {
                "title": "🌅 PRESTOCKS",
                "desc": "Pre-market tokenized equities",
                "emoji": "🌅",
            },
            "indexes": {
                "title": "📊 INDEXES",
                "desc": "SPX, NDX, DJI on Solana",
                "emoji": "📊",
            },
            "trending": {
                "title": "🔥 HOT TRENDING",
                "desc": "High-volume Solana tokens right now",
                "emoji": "🔥",
            },
        }

        config = section_config.get(section, {"title": section.upper(), "desc": "", "emoji": "📊"})

        lines = [
            f"{config['emoji']} *{config['title']}*",
            "━━━━━━━━━━━━━━━━━━━━━",
            f"_{config['desc']}_",
            "",
        ]

        keyboard = []

        if not picks:
            if section == "prestocks":
                lines.append("_PreStocks data is not live yet._")
                lines.append("_Check back soon for private market listings._")
            else:
                lines.append("_No picks available in this category_")
                lines.append("_Check back after next report refresh_")
        else:
            for i, pick in enumerate(picks[:8]):
                symbol = pick.get("symbol", "???")
                price = pick.get("price", 0)
                change_24h = pick.get("change_24h", 0)
                sentiment = pick.get("sentiment", "NEUTRAL")
                score = pick.get("score", 0)
                tp = pick.get("tp", 0)
                sl = pick.get("sl", 0)
                token_ref = pick.get("token_id") or pick.get("address", "")
                conviction = pick.get("conviction", "")

                # Sentiment emoji
                sent_emoji = {"BULLISH": "🟢", "BEARISH": "🔴", "VERY_BULLISH": "🚀"}.get(sentiment, "⚪")
                change_emoji = "📈" if change_24h >= 0 else "📉"

                # Format price nicely
                if price < 0.0001:
                    price_str = f"${price:.8f}"
                elif price < 1:
                    price_str = f"${price:.6f}"
                else:
                    price_str = f"${price:.2f}"

                lines.append(f"{sent_emoji} *{symbol}* {price_str}")
                lines.append(f"   {change_emoji} {change_24h:+.1f}% | Score: {score:.0f}/100")

                if tp or sl:
                    targets = []
                    if tp:
                        targets.append(f"TP: +{tp}%")
                    if sl:
                        targets.append(f"SL: -{sl}%")
                    lines.append(f"   🎯 {' | '.join(targets)}")

                if conviction:
                    lines.append(f"   _{conviction}_")

                lines.append("")

                # Buy button with auto stop-loss
                if token_ref:
                    sl_percent = sl if sl else 15  # Default 15% SL
                    keyboard.append([
                        InlineKeyboardButton(
                            f"🛒 Buy {symbol}",
                            callback_data=f"demo:hub_buy:{token_ref}:{sl_percent}"
                        ),
                        InlineKeyboardButton(
                            f"📊 Details",
                            callback_data=f"demo:hub_detail:{token_ref}"
                        ),
                    ])

        text = "\n".join(lines)

        keyboard.extend([
            [
                InlineKeyboardButton(f"{theme.REFRESH} Refresh", callback_data=f"demo:hub_{section}"),
            ],
            [
                InlineKeyboardButton("📊 Back to Hub", callback_data="demo:sentiment_hub"),
            ],
        ])

        return text, InlineKeyboardMarkup(keyboard)

    @staticmethod
    def sentiment_hub_wallet(
        wallet_address: str = None,
        sol_balance: float = 0.0,
        usd_value: float = 0.0,
        has_private_key: bool = False,
    ) -> Tuple[str, InlineKeyboardMarkup]:
        """
        Wallet management within Sentiment Hub.

        Supports:
        - Fresh wallet creation
        - Private key export
        - Private key import
        - Balance display
        """
        theme = JarvisTheme

        if wallet_address:
            short_addr = f"{wallet_address[:8]}...{wallet_address[-6:]}"

            lines = [
                f"💳 *HUB WALLET*",
                "━━━━━━━━━━━━━━━━━━━━━",
                "",
                f"*Address:* `{short_addr}`",
                f"*Balance:* {sol_balance:.4f} SOL",
                f"*Value:* ${usd_value:.2f}",
                "",
                "━━━━━━━━━━━━━━━━━━━━━",
                "_Secure your keys. Not your keys, not your coins._",
            ]

            keyboard = [
                [
                    InlineKeyboardButton("📤 Export Key", callback_data="demo:hub_export_key"),
                    InlineKeyboardButton("📋 Copy Address", callback_data="demo:hub_copy_addr"),
                ],
                [
                    InlineKeyboardButton("💰 Deposit", callback_data="demo:hub_deposit"),
                    InlineKeyboardButton("📤 Withdraw", callback_data="demo:hub_withdraw"),
                ],
                [
                    InlineKeyboardButton("🔄 Import Key", callback_data="demo:hub_import_key"),
                    InlineKeyboardButton("🆕 New Wallet", callback_data="demo:hub_new_wallet"),
                ],
                [
                    InlineKeyboardButton("📊 Back to Hub", callback_data="demo:sentiment_hub"),
                ],
            ]
        else:
            lines = [
                f"💳 *SETUP WALLET*",
                "━━━━━━━━━━━━━━━━━━━━━",
                "",
                "No wallet connected.",
                "",
                "*Options:*",
                "• Create a fresh Solana wallet",
                "• Import existing private key",
                "",
                "━━━━━━━━━━━━━━━━━━━━━",
                "_Your keys are encrypted locally._",
            ]

            keyboard = [
                [
                    InlineKeyboardButton("🆕 Create Wallet", callback_data="demo:hub_create_wallet"),
                ],
                [
                    InlineKeyboardButton("📥 Import Key", callback_data="demo:hub_import_key"),
                ],
                [
                    InlineKeyboardButton("📊 Back to Hub", callback_data="demo:sentiment_hub"),
                ],
            ]

        text = "\n".join(lines)
        return text, InlineKeyboardMarkup(keyboard)

    @staticmethod
    def sentiment_hub_news(
        news_items: List[Dict[str, Any]] = None,
        macro_analysis: Dict[str, Any] = None,
    ) -> Tuple[str, InlineKeyboardMarkup]:
        """
        Market news and macro analysis view.

        Shows:
        - Key market events
        - Macro outlook (short/medium/long term)
        - Impact on crypto
        """
        theme = JarvisTheme
        news_items = news_items or []
        macro = macro_analysis or {}

        lines = [
            f"📰 *MARKET NEWS & MACRO*",
            "━━━━━━━━━━━━━━━━━━━━━",
            "",
        ]

        # Macro outlook
        short_term = macro.get("short_term", "No data")
        medium_term = macro.get("medium_term", "No data")
        key_events = macro.get("key_events", [])

        lines.extend([
            "*MACRO OUTLOOK:*",
            f"📅 *24h:* {short_term[:60]}...",
            f"📆 *3-Day:* {medium_term[:60]}...",
            "",
        ])

        if key_events:
            lines.append("*KEY EVENTS:*")
            for event in key_events[:3]:
                lines.append(f"• {event[:50]}")
            lines.append("")

        # News items
        if news_items:
            lines.append("*RECENT NEWS:*")
            for item in news_items[:5]:
                # Support both 'title' and 'headline' keys
                headline = item.get("title") or item.get("headline", "")
                headline = headline[:45] if headline else ""
                source = item.get("source", "")
                time_str = item.get("time", "")
                impact = item.get("impact") or item.get("sentiment", "NEUTRAL")
                impact_upper = impact.upper() if impact else "NEUTRAL"
                impact_emoji = {"BULLISH": "🟢", "BEARISH": "🔴"}.get(impact_upper, "⚪")
                source_str = f" - {source}" if source else ""
                time_str = f" ({time_str})" if time_str else ""
                lines.append(f"{impact_emoji} {headline}{source_str}{time_str}")
            lines.append("")

        text = "\n".join(lines)

        keyboard = [
            [
                InlineKeyboardButton(f"{theme.REFRESH} Refresh", callback_data="demo:hub_news"),
            ],
            [
                InlineKeyboardButton("📊 Back to Hub", callback_data="demo:sentiment_hub"),
            ],
        ]

        return text, InlineKeyboardMarkup(keyboard)

    @staticmethod
    def sentiment_hub_traditional(
        stocks_outlook: Dict[str, Any] = None,
        dxy_data: Dict[str, Any] = None,
        commodities: List[Dict[str, Any]] = None,
    ) -> Tuple[str, InlineKeyboardMarkup]:
        """
        Traditional markets view - DXY, stocks, commodities.
        """
        theme = JarvisTheme

        stocks = stocks_outlook or {}
        dxy = dxy_data or {}
        comms = commodities or []

        # DXY - support multiple field names
        dxy_value = dxy.get("value", 0)
        dxy_change = dxy.get("change", 0)
        dxy_trend = dxy.get("trend") or dxy.get("direction", "NEUTRAL")
        dxy_trend_upper = dxy_trend.upper() if dxy_trend else "NEUTRAL"
        dxy_emoji = "📈" if dxy_change > 0 else "📉" if dxy_change < 0 else "➡️"

        # Stocks - support multiple field names
        stocks_direction = stocks.get("direction") or stocks.get("outlook", "NEUTRAL")
        stocks_direction_upper = stocks_direction.upper() if stocks_direction else "NEUTRAL"
        stocks_emoji = {"BULLISH": "📈", "BEARISH": "📉"}.get(stocks_direction_upper, "➡️")

        # Stocks changes
        spy_change = stocks.get("spy_change", 0)
        qqq_change = stocks.get("qqq_change", 0)
        dia_change = stocks.get("dia_change", 0)

        lines = [
            f"🌍 *TRADITIONAL MARKETS*",
            "━━━━━━━━━━━━━━━━━━━━━",
            "",
            f"*DXY (Dollar Index):* {dxy_emoji}",
            f"├ Value: *{dxy_value:.2f}*",
            f"├ Change: *{dxy_change:+.2f}%*",
            f"└ Trend: *{dxy_trend_upper}*",
            "",
            f"*US STOCKS:* {stocks_emoji} *{stocks_direction_upper}*",
        ]

        if spy_change or qqq_change or dia_change:
            lines.extend([
                f"├ SPY: *{spy_change:+.2f}%*",
                f"├ QQQ: *{qqq_change:+.2f}%*",
                f"└ DIA: *{dia_change:+.2f}%*",
            ])

        lines.append("")

        if stocks.get("correlation_note"):
            lines.extend([
                "*CRYPTO CORRELATION:*",
                f"_{stocks.get('correlation_note', '')[:80]}_",
                "",
            ])

        if comms:
            lines.append("*COMMODITIES:*")
            for c in comms[:3]:
                name = c.get("symbol") or c.get("name", "???")
                price = c.get("price", 0)
                change = c.get("change", 0)
                dir_emoji = "📈" if change > 0 else "📉" if change < 0 else "➡️"
                lines.append(f"{dir_emoji} {name}: ${price:,.2f} ({change:+.1f}%)")
            lines.append("")

        text = "\n".join(lines)

        keyboard = [
            [
                InlineKeyboardButton(f"{theme.REFRESH} Refresh", callback_data="demo:hub_traditional"),
            ],
            [
                InlineKeyboardButton("📊 Back to Hub", callback_data="demo:sentiment_hub"),
            ],
        ]

        return text, InlineKeyboardMarkup(keyboard)

    @staticmethod
    def sentiment_hub_buy_confirm(
        symbol: str,
        address: str,
        price: float,
        auto_sl_percent: float = 15,
        token_ref: Optional[str] = None,
        amount_options: List[float] = None,
    ) -> Tuple[str, InlineKeyboardMarkup]:
        """
        Buy confirmation with automatic stop-loss setup.
        """
        theme = JarvisTheme
        token_ref = token_ref or address
        amount_options = amount_options or [0.1, 0.25, 0.5, 1.0, 2.0]

        # Format price
        if price < 0.0001:
            price_str = f"${price:.8f}"
        elif price < 1:
            price_str = f"${price:.6f}"
        else:
            price_str = f"${price:.2f}"

        sl_price = price * (1 - auto_sl_percent / 100)
        sl_str = f"${sl_price:.8f}" if sl_price < 0.0001 else f"${sl_price:.6f}" if sl_price < 1 else f"${sl_price:.2f}"

        lines = [
            f"🛒 *BUY {symbol}*",
            "━━━━━━━━━━━━━━━━━━━━━",
            "",
            f"*Price:* {price_str}",
            f"*Auto Stop-Loss:* {auto_sl_percent}%",
            f"*SL Trigger:* {sl_str}",
            "",
            "_Select amount to buy:_",
            "",
            "━━━━━━━━━━━━━━━━━━━━━",
            f"⚠️ SL automatically set at -{auto_sl_percent}%",
        ]

        text = "\n".join(lines)

        keyboard = []
        row = []
        for amt in amount_options:
            row.append(InlineKeyboardButton(
                f"{amt} SOL",
                callback_data=f"demo:hub_exec_buy:{token_ref}:{amt}:{auto_sl_percent}"
            ))
            if len(row) == 2:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)

        keyboard.extend([
            [
                InlineKeyboardButton("✏️ Custom SL %", callback_data=f"demo:hub_custom_sl:{token_ref}"),
            ],
            [
                InlineKeyboardButton(f"{theme.BACK} Cancel", callback_data="demo:sentiment_hub"),
            ],
        ])

        return text, InlineKeyboardMarkup(keyboard)

    @staticmethod
    def bags_fm_top_tokens(
        tokens: List[Dict[str, Any]],
        market_regime: Dict[str, Any] = None,
        default_tp_percent: float = 15.0,
        default_sl_percent: float = 15.0,
    ) -> Tuple[str, InlineKeyboardMarkup]:
        """
        Bags.fm Top 15 Tokens by Volume with AI Sentiment.

        Features:
        - Top 15 tokens ranked by 24h volume
        - AI sentiment score per token
        - Signal strength indicator
        - Buy with auto TP/SL buttons
        - Sell buttons for open positions
        """
        theme = JarvisTheme

        regime = market_regime or {}
        regime_name = regime.get("regime", "NEUTRAL")
        risk_level = regime.get("risk_level", "NORMAL")
        regime_emoji = {"BULL": "🟢", "BEAR": "🔴"}.get(regime_name, "🟡")

        # Calculate total volume
        total_volume = sum(t.get("volume_24h", 0) for t in tokens)

        lines = [
            f"🎒 *BAGS.FM TOP 15*",
            "━━━━━━━━━━━━━━━━━━━━━",
            f"Market: {regime_emoji} {regime_name} | 24h Vol: ${total_volume/1_000_000:.1f}M",
            "",
            "*Volume Leaders with AI Sentiment:*",
            "",
        ]

        keyboard = []

        for i, token in enumerate(tokens[:15], 1):
            symbol = token.get("symbol", "???")
            safe_symbol = escape_md(symbol)
            address = token.get("address", "")
            token_ref = token.get("token_id") or address
            price = token.get("price_usd", 0)
            change_24h = token.get("change_24h", 0)
            volume = token.get("volume_24h", 0)
            liquidity = token.get("liquidity", 0)
            mcap = token.get("market_cap", 0)
            holders = token.get("holders", 0)

            # Sentiment data
            sentiment = token.get("sentiment", "neutral")
            sentiment_score = token.get("sentiment_score", 0.5)
            signal = token.get("signal", "NEUTRAL")

            # Format price
            if price < 0.0001:
                price_str = f"${price:.8f}"
            elif price < 1:
                price_str = f"${price:.6f}"
            else:
                price_str = f"${price:.2f}"

            # Price change formatting
            change_emoji = "🟢" if change_24h > 0 else "🔴" if change_24h < 0 else "⚪"
            change_str = f"{change_emoji} {change_24h:+.1f}%"

            # Volume formatting
            if volume >= 1_000_000:
                vol_str = f"${volume/1_000_000:.1f}M"
            else:
                vol_str = f"${volume/1_000:.0f}K"

            # Sentiment emoji and signal with CLEARER BULLISH/BEARISH labels
            sent_emoji = {
                "very_bullish": "🚀",
                "bullish": "🟢",
                "neutral": "🟡",
                "bearish": "🟠",
                "very_bearish": "🔴",
            }.get(sentiment.lower() if isinstance(sentiment, str) else "neutral", "⚪")

            # Clearer sentiment label
            sent_label = {
                "very_bullish": "VERY BULLISH",
                "bullish": "BULLISH",
                "neutral": "NEUTRAL",
                "bearish": "BEARISH",
                "very_bearish": "VERY BEARISH",
            }.get(sentiment.lower() if isinstance(sentiment, str) else "neutral", "NEUTRAL")

            signal_emoji = {
                "STRONG_BUY": "🟢🟢",
                "BUY": "🟢",
                "HOLD": "🟡",
                "SELL": "🟠",
                "STRONG_SELL": "🔴🔴",
            }.get(signal, "⚪")

            # Score bar visualization
            score_bars = int(sentiment_score * 5) if sentiment_score else 0
            score_bar = "▰" * score_bars + "▱" * (5 - score_bars)

            # Rank medal
            if i == 1:
                rank = "🥇"
            elif i == 2:
                rank = "🥈"
            elif i == 3:
                rank = "🥉"
            else:
                rank = f"#{i:02d}"

            # Contract address (shortened)
            contract_short = f"`{address[:8]}...{address[-6:]}`" if address else "N/A"

            lines.append(f"{rank} *{safe_symbol}* {price_str} {change_str}")
            lines.append(f"   Vol: {vol_str} | Liq: ${liquidity/1_000:.0f}K")
            lines.append(f"   {sent_emoji} {sent_label} | {signal_emoji} {signal}")
            lines.append(f"   📝 {contract_short}")
            lines.append("")

            # Add buy/sell buttons for each token with CLEAR LABELS
            if token_ref:
                # DexScreener chart link
                chart_url = token.get("chart_url", f"https://dexscreener.com/solana/{address}")

                keyboard.append([
                    InlineKeyboardButton(
                        f"💰 Buy 0.1 SOL of {symbol}",
                        callback_data=f"demo:bags_exec:{token_ref}:0.1:{default_tp_percent}:{default_sl_percent}"
                    ),
                    InlineKeyboardButton(
                        f"{theme.CHART} Chart",
                        url=chart_url
                    ),
                ])
                keyboard.append([
                    InlineKeyboardButton(
                        f"🔍 View {symbol} Details",
                        callback_data=f"demo:bags_info:{token_ref}"
                    ),
                ])

        # Add summary stats
        bullish_count = sum(1 for t in tokens if t.get("sentiment", "").lower() in ["bullish", "very_bullish"])
        bearish_count = sum(1 for t in tokens if t.get("sentiment", "").lower() in ["bearish", "very_bearish"])

        lines.extend([
            "━━━━━━━━━━━━━━━━━━━━━",
            f"📊 *Sentiment Summary*",
            f"   🟢 Bullish: {bullish_count} | 🔴 Bearish: {bearish_count}",
            "",
            f"_Default TP: +{default_tp_percent:.0f}% | SL: -{default_sl_percent:.0f}%_",
        ])

        text = "\n".join(lines)

        # Navigation buttons
        keyboard.extend([
            [
                InlineKeyboardButton(f"⚙️ Set TP/SL", callback_data="demo:bags_settings"),
                InlineKeyboardButton(f"{theme.REFRESH} Refresh", callback_data="demo:bags_fm"),
            ],
            [
                InlineKeyboardButton(f"{theme.BACK} Main Menu", callback_data="demo:main"),
            ],
        ])

        return text, InlineKeyboardMarkup(keyboard)

    @staticmethod
    def bags_token_detail(
        token: Dict[str, Any],
        market_regime: Dict[str, Any] = None,
        default_tp_percent: float = 15.0,
        default_sl_percent: float = 15.0,
    ) -> Tuple[str, InlineKeyboardMarkup]:
        """
        Detailed view of a single Bags.fm token with buy/sell options.
        """
        theme = JarvisTheme

        symbol = token.get("symbol", "???")
        name = token.get("name", symbol)
        safe_symbol = escape_md(symbol)
        safe_name = escape_md(name)
        address = token.get("address", "")
        price = token.get("price_usd", 0)
        volume = token.get("volume_24h", 0)
        liquidity = token.get("liquidity", 0)
        mcap = token.get("market_cap", 0)
        holders = token.get("holders", 0)

        sentiment = token.get("sentiment", "neutral")
        sentiment_score = token.get("sentiment_score", 0.5)
        signal = token.get("signal", "NEUTRAL")
        token_ref = token.get("token_id") or address

        # Format price
        if price < 0.0001:
            price_str = f"${price:.8f}"
        elif price < 1:
            price_str = f"${price:.6f}"
        else:
            price_str = f"${price:.2f}"

        # TP/SL targets
        tp_price = price * (1 + default_tp_percent / 100)
        sl_price = price * (1 - default_sl_percent / 100)

        tp_str = f"${tp_price:.8f}" if tp_price < 0.0001 else f"${tp_price:.6f}" if tp_price < 1 else f"${tp_price:.2f}"
        sl_str = f"${sl_price:.8f}" if sl_price < 0.0001 else f"${sl_price:.6f}" if sl_price < 1 else f"${sl_price:.2f}"

        # Sentiment display
        sent_emoji = {
            "very_bullish": "🚀",
            "bullish": "🟢",
            "neutral": "🟡",
            "bearish": "🟠",
            "very_bearish": "🔴",
        }.get(sentiment.lower() if isinstance(sentiment, str) else "neutral", "⚪")

        score_bars = int(sentiment_score * 5) if sentiment_score else 0
        score_bar = "▰" * score_bars + "▱" * (5 - score_bars)

        # Get 24h change if available
        change_24h = token.get("change_24h", 0)
        change_emoji = "🟢" if change_24h > 0 else "🔴" if change_24h < 0 else "⚪"
        change_str = f"{change_emoji} {change_24h:+.1f}%" if change_24h else ""

        lines = [
            f"🎒 *{safe_symbol}*",
            f"_{safe_name}_",
            "━━━━━━━━━━━━━━━━━━━━━",
            "",
            f"💰 *Price:* {price_str} {change_str}",
            f"📊 *24h Volume:* ${volume/1_000_000:.2f}M",
            f"💧 *Liquidity:* ${liquidity/1_000:.0f}K",
            f"📈 *Market Cap:* ${mcap/1_000_000:.2f}M",
            f"👥 *Holders:* {holders:,}",
            "",
            f"{sent_emoji} *AI Sentiment:* {sentiment.upper()}",
            f"   Score: {score_bar} ({sentiment_score:.0%})",
            f"   Signal: *{signal}*",
            "",
            "━━━━━━━━━━━━━━━━━━━━━",
            f"*Trading Setup:*",
            f"🎯 TP (+{default_tp_percent:.0f}%): {tp_str}",
            f"🛑 SL (-{default_sl_percent:.0f}%): {sl_str}",
            "",
            f"📋 *Contract:*",
            f"`{address}`",
            "",
            f"🔗 *Links:*",
            f"• [DexScreener](https://dexscreener.com/solana/{address})",
            f"• [Solscan](https://solscan.io/token/{address})",
            f"• [Birdeye](https://birdeye.so/token/{address})",
        ]

        text = "\n".join(lines)

        # Buy buttons with different amounts
        keyboard = [
            [
                InlineKeyboardButton(f"🟢 Buy 0.1 SOL", callback_data=f"demo:bags_exec:{token_ref}:0.1:{default_tp_percent}:{default_sl_percent}"),
                InlineKeyboardButton(f"🟢 Buy 0.25 SOL", callback_data=f"demo:bags_exec:{token_ref}:0.25:{default_tp_percent}:{default_sl_percent}"),
            ],
            [
                InlineKeyboardButton(f"🟢 Buy 0.5 SOL", callback_data=f"demo:bags_exec:{token_ref}:0.5:{default_tp_percent}:{default_sl_percent}"),
                InlineKeyboardButton(f"🟢 Buy 1 SOL", callback_data=f"demo:bags_exec:{token_ref}:1:{default_tp_percent}:{default_sl_percent}"),
            ],
            [
                InlineKeyboardButton(f"🟢 Buy 2 SOL", callback_data=f"demo:bags_exec:{token_ref}:2:{default_tp_percent}:{default_sl_percent}"),
                InlineKeyboardButton(f"🟢 Buy 5 SOL", callback_data=f"demo:bags_exec:{token_ref}:5:{default_tp_percent}:{default_sl_percent}"),
            ],
            [
                InlineKeyboardButton(f"✏️ Custom TP/SL", callback_data=f"demo:bags_custom_tpsl:{token_ref}"),
            ],
            [
                InlineKeyboardButton(f"{theme.BACK} Back to List", callback_data="demo:bags_fm"),
            ],
        ]

        return text, InlineKeyboardMarkup(keyboard)

    @staticmethod
    def bags_buy_result(
        success: bool,
        symbol: str,
        amount_sol: float,
        tokens_received: float = 0,
        price: float = 0,
        tp_percent: float = 15,
        sl_percent: float = 15,
        tx_hash: str = None,
        error: str = None,
    ) -> Tuple[str, InlineKeyboardMarkup]:
        """
        Result of a Bags.fm buy operation.
        """
        theme = JarvisTheme
        safe_symbol = escape_md(symbol)

        if success:
            tp_price = price * (1 + tp_percent / 100)
            sl_price = price * (1 - sl_percent / 100)

            lines = [
                f"✅ *BUY SUCCESSFUL*",
                "━━━━━━━━━━━━━━━━━━━━━",
                "",
                f"🪙 *Token:* {safe_symbol}",
                f"💰 *Spent:* {amount_sol} SOL",
                f"📦 *Received:* {tokens_received:,.2f} {safe_symbol}",
                f"💵 *Entry Price:* ${price:.8f}" if price < 0.0001 else f"💵 *Entry Price:* ${price:.6f}" if price < 1 else f"💵 *Entry Price:* ${price:.2f}",
                "",
                f"*Auto Orders Set:*",
                f"🎯 TP (+{tp_percent:.0f}%): ${tp_price:.8f}" if tp_price < 0.0001 else f"🎯 TP (+{tp_percent:.0f}%): ${tp_price:.6f}" if tp_price < 1 else f"🎯 TP (+{tp_percent:.0f}%): ${tp_price:.2f}",
                f"🛑 SL (-{sl_percent:.0f}%): ${sl_price:.8f}" if sl_price < 0.0001 else f"🛑 SL (-{sl_percent:.0f}%): ${sl_price:.6f}" if sl_price < 1 else f"🛑 SL (-{sl_percent:.0f}%): ${sl_price:.2f}",
                "",
            ]

            if tx_hash:
                lines.append(f"🔗 [View on Solscan](https://solscan.io/tx/{tx_hash})")

            lines.extend([
                "",
                "━━━━━━━━━━━━━━━━━━━━━",
                "_Position added to portfolio_",
            ])
        else:
            lines = [
                f"❌ *BUY FAILED*",
                "━━━━━━━━━━━━━━━━━━━━━",
                "",
                f"🪙 *Token:* {safe_symbol}",
                f"💰 *Amount:* {amount_sol} SOL",
                "",
                f"*Error:* {error or 'Unknown error'}",
                "",
                "_Please try again or contact support_",
            ]

        text = "\n".join(lines)

        keyboard = [
            [
                InlineKeyboardButton(f"{theme.CHART} Positions", callback_data="demo:positions"),
                InlineKeyboardButton(f"🎒 Back to Bags", callback_data="demo:bags_fm"),
            ],
            [
                InlineKeyboardButton(f"{theme.BACK} Main Menu", callback_data="demo:main"),
            ],
        ]

        return text, InlineKeyboardMarkup(keyboard)

    # Snipe amount constants - defined once, used everywhere
    SNIPE_AMOUNTS = [0.1, 0.25, 0.5, 1.0]

    @staticmethod
    def insta_snipe_menu(
        hottest_token: Dict[str, Any] = None,
        market_regime: Dict[str, Any] = None,
        auto_sl_percent: float = 15.0,
        auto_tp_percent: float = 15.0,
    ) -> Tuple[str, InlineKeyboardMarkup]:
        """
        Insta Snipe - One-click trade on the hottest trending token.

        Features:
        - Auto-detects hottest trending token
        - Pre-configured 15% SL / 15% TP
        - Conviction level display
        - One-click execution
        """
        theme = JarvisTheme

        regime = market_regime or {}
        regime_name = regime.get("regime", "NEUTRAL")

        if hottest_token:
            symbol = hottest_token.get("symbol", "UNKNOWN")
            safe_symbol = escape_md(symbol)
            address = hottest_token.get("address", "")
            token_ref = hottest_token.get("token_id") or address
            price = hottest_token.get("price", 0)
            change_24h = hottest_token.get("change_24h", 0)
            volume = hottest_token.get("volume_24h", 0)
            liquidity = hottest_token.get("liquidity", 0)
            mcap = hottest_token.get("market_cap", 0)
            conviction = hottest_token.get("conviction", "MEDIUM")
            sentiment_score = hottest_token.get("sentiment_score", 65)
            entry_timing = hottest_token.get("entry_timing", "GOOD")
            sightings = hottest_token.get("sightings", 1)

            # Price formatting
            if price < 0.0001:
                price_str = f"${price:.8f}"
            elif price < 1:
                price_str = f"${price:.6f}"
            else:
                price_str = f"${price:.2f}"

            # Volume/Liquidity formatting
            def fmt_num(n):
                if n >= 1_000_000:
                    return f"${n/1_000_000:.1f}M"
                elif n >= 1_000:
                    return f"${n/1_000:.1f}K"
                return f"${n:.0f}"

            # Conviction display
            conv_emoji = {
                "VERY HIGH": "🔥🔥🔥",
                "HIGH": "🔥🔥",
                "MEDIUM": "🔥",
                "LOW": "⚪",
            }.get(conviction, "🔥")

            # Entry timing
            timing_emoji = {
                "EXCELLENT": "🟢",
                "GOOD": "🟡",
                "LATE": "🟠",
                "RISKY": "🔴",
            }.get(entry_timing, "🟡")

            # Change emoji
            change_emoji = "📈" if change_24h >= 0 else "📉"

            # Calculate SL/TP prices
            sl_price = price * (1 - auto_sl_percent / 100)
            tp_price = price * (1 + auto_tp_percent / 100)
            sl_str = f"${sl_price:.8f}" if sl_price < 0.0001 else f"${sl_price:.6f}" if sl_price < 1 else f"${sl_price:.2f}"
            tp_str = f"${tp_price:.8f}" if tp_price < 0.0001 else f"${tp_price:.6f}" if tp_price < 1 else f"${tp_price:.2f}"

            lines = [
                f"⚡ *INSTA SNIPE*",
                "━━━━━━━━━━━━━━━━━━━━━",
                "",
                f"🎯 *HOTTEST TOKEN: {safe_symbol}*",
                "",
                f"*Conviction:* {conv_emoji} {conviction}",
                f"*Sentiment Score:* {sentiment_score}/100",
                f"*Entry Timing:* {timing_emoji} {entry_timing}",
                f"*Sightings:* {sightings}x (multi-source bonus)",
                "",
                "━━━━━━━━━━━━━━━━━━━━━",
                "",
                f"*Price:* {price_str}",
                f"*24h:* {change_emoji} {change_24h:+.1f}%",
                f"*Volume:* {fmt_num(volume)}",
                f"*Liquidity:* {fmt_num(liquidity)}",
                f"*MCap:* {fmt_num(mcap)}",
                "",
                "━━━━━━━━━━━━━━━━━━━━━",
                "",
                f"🛡️ *AUTO PROTECTION*",
                f"├ Stop Loss: *-{auto_sl_percent:.0f}%* ({sl_str})",
                f"└ Take Profit: *+{auto_tp_percent:.0f}%* ({tp_str})",
                "",
                "━━━━━━━━━━━━━━━━━━━━━",
                "_One-click trade with auto SL/TP_",
            ]

            text = "\n".join(lines)

            # Use SNIPE_AMOUNTS constant for consistency
            amounts = DemoMenuBuilder.SNIPE_AMOUNTS
            keyboard = [
                # Quick snipe amounts - row 1
                [
                    InlineKeyboardButton(f"⚡ {amounts[0]} SOL", callback_data=f"demo:snipe_exec:{token_ref}:{amounts[0]}"),
                    InlineKeyboardButton(f"⚡ {amounts[1]} SOL", callback_data=f"demo:snipe_exec:{token_ref}:{amounts[1]}"),
                ],
                # Quick snipe amounts - row 2
                [
                    InlineKeyboardButton(f"⚡ {amounts[2]} SOL", callback_data=f"demo:snipe_exec:{token_ref}:{amounts[2]}"),
                    InlineKeyboardButton(f"⚡ {amounts[3]} SOL", callback_data=f"demo:snipe_exec:{token_ref}:{amounts[3]}"),
                ],
                [
                    InlineKeyboardButton(f"🔄 Refresh Token", callback_data="demo:insta_snipe"),
                    InlineKeyboardButton(f"📊 Full Analysis", callback_data=f"demo:analyze:{token_ref}"),
                ],
                [
                    InlineKeyboardButton(f"{theme.BACK} Back", callback_data="demo:main"),
                ],
            ]
        else:
            # No token available
            lines = [
                f"⚡ *INSTA SNIPE*",
                "━━━━━━━━━━━━━━━━━━━━━",
                "",
                "🔍 *Scanning for hottest token...*",
                "",
                "_Analyzing trending tokens by:_",
                "├ Volume spike detection",
                "├ Social sentiment scoring",
                "├ Entry timing analysis",
                "└ Multi-source sightings",
                "",
                "━━━━━━━━━━━━━━━━━━━━━",
                "",
                "⏳ *No qualifying tokens found*",
                "_Try refreshing or check AI Picks_",
            ]

            text = "\n".join(lines)

            keyboard = [
                [
                    InlineKeyboardButton(f"🔄 Refresh", callback_data="demo:insta_snipe"),
                    InlineKeyboardButton(f"{theme.AUTO} AI Picks", callback_data="demo:ai_picks"),
                ],
                [
                    InlineKeyboardButton(f"📊 Sentiment Hub", callback_data="demo:hub"),
                ],
                [
                    InlineKeyboardButton(f"{theme.BACK} Back", callback_data="demo:main"),
                ],
            ]

        return text, InlineKeyboardMarkup(keyboard)

    @staticmethod
    def snipe_confirm(
        symbol: str,
        address: str,
        amount: float,
        price: float,
        sl_percent: float = 15.0,
        tp_percent: float = 15.0,
        token_ref: Optional[str] = None,
    ) -> Tuple[str, InlineKeyboardMarkup]:
        """
        Snipe confirmation screen before execution.
        """
        theme = JarvisTheme
        safe_symbol = escape_md(symbol)

        # Price formatting
        if price < 0.0001:
            price_str = f"${price:.8f}"
        elif price < 1:
            price_str = f"${price:.6f}"
        else:
            price_str = f"${price:.2f}"

        # Calculate SL/TP
        sl_price = price * (1 - sl_percent / 100)
        tp_price = price * (1 + tp_percent / 100)
        sl_str = f"${sl_price:.8f}" if sl_price < 0.0001 else f"${sl_price:.6f}" if sl_price < 1 else f"${sl_price:.2f}"
        tp_str = f"${tp_price:.8f}" if tp_price < 0.0001 else f"${tp_price:.6f}" if tp_price < 1 else f"${tp_price:.2f}"

        usd_value = amount * 225  # Approximate SOL price

        lines = [
            f"⚡ *CONFIRM SNIPE*",
            "━━━━━━━━━━━━━━━━━━━━━",
            "",
            f"*Token:* {safe_symbol}",
            f"*Amount:* {amount} SOL (~${usd_value:.2f})",
            f"*Price:* {price_str}",
            "",
            "🛡️ *Protection Orders*",
            f"├ Stop Loss: -{sl_percent:.0f}% @ {sl_str}",
            f"└ Take Profit: +{tp_percent:.0f}% @ {tp_str}",
            "",
            "━━━━━━━━━━━━━━━━━━━━━",
            "⚠️ _This will execute immediately_",
        ]

        text = "\n".join(lines)

        token_ref = token_ref or address
        keyboard = [
            [
                InlineKeyboardButton(f"✅ CONFIRM SNIPE", callback_data=f"demo:snipe_confirm:{token_ref}:{amount}"),
            ],
            [
                InlineKeyboardButton(f"❌ Cancel", callback_data="demo:insta_snipe"),
            ],
        ]

        return text, InlineKeyboardMarkup(keyboard)

    @staticmethod
    def snipe_result(
        success: bool,
        symbol: str,
        amount: float,
        tx_hash: str = None,
        error: str = None,
        sl_set: bool = False,
        tp_set: bool = False,
    ) -> Tuple[str, InlineKeyboardMarkup]:
        """
        Snipe execution result.
        """
        theme = JarvisTheme

        if success:
            # Escape symbol to prevent markdown parse errors
            safe_symbol = escape_md(symbol)

            lines = [
                f"✅ *SNIPE SUCCESSFUL*",
                "━━━━━━━━━━━━━━━━━━━━━",
                "",
                f"*Token:* {safe_symbol}",
                f"*Amount:* {amount} SOL",
                "",
                "🛡️ *Protection Status*",
                f"├ Stop Loss: {'✅ Set' if sl_set else '⏳ Pending'}",
                f"└ Take Profit: {'✅ Set' if tp_set else '⏳ Pending'}",
                "",
            ]
            if tx_hash:
                short_hash = f"{tx_hash[:8]}...{tx_hash[-8:]}" if len(tx_hash) > 16 else tx_hash
                lines.extend([
                    f"*TX:* `{short_hash}`",
                    "",
                ])
            lines.extend([
                "━━━━━━━━━━━━━━━━━━━━━",
                "_Position added to portfolio_",
            ])
        else:
            # Escape error message to prevent markdown parse errors
            safe_error = escape_md(error) if error else 'Unknown error'
            safe_symbol = escape_md(symbol)

            lines = [
                f"❌ *SNIPE FAILED*",
                "━━━━━━━━━━━━━━━━━━━━━",
                "",
                f"*Token:* {safe_symbol}",
                f"*Amount:* {amount} SOL",
                "",
                f"*Error:* {safe_error}",
                "",
                "━━━━━━━━━━━━━━━━━━━━━",
                "_Try again or check balance_",
            ]

        text = "\n".join(lines)

        keyboard = [
            [
                InlineKeyboardButton(f"⚡ Snipe Again", callback_data="demo:insta_snipe"),
                InlineKeyboardButton(f"📊 Positions", callback_data="demo:positions"),
            ],
            [
                InlineKeyboardButton(f"{theme.BACK} Main Menu", callback_data="demo:main"),
            ],
        ]

        return text, InlineKeyboardMarkup(keyboard)

    @staticmethod
    def close_position_result(
        success: bool,
        symbol: str,
        amount: float,
        entry_price: float,
        exit_price: float,
        pnl_usd: float,
        pnl_percent: float,
        success_fee: float = 0.0,
        net_profit: float = None,
        tx_hash: str = None,
        error: str = None,
    ) -> Tuple[str, InlineKeyboardMarkup]:
        """
        Position close result with success fee display.

        Shows:
        - PnL details
        - Success fee (0.5% on profit) if winning trade
        - Net profit after fee
        """
        theme = JarvisTheme

        is_profit = pnl_usd > 0
        pnl_emoji = "📈" if is_profit else "📉"
        pnl_sign = "+" if is_profit else ""

        if success:
            lines = [
                f"✅ *POSITION CLOSED*",
                "━━━━━━━━━━━━━━━━━━━━━",
                "",
                f"*Token:* {symbol}",
                f"*Amount:* {amount} SOL",
                "",
                f"*Entry:* ${entry_price:.8f}" if entry_price < 0.0001 else f"*Entry:* ${entry_price:.6f}" if entry_price < 1 else f"*Entry:* ${entry_price:.4f}",
                f"*Exit:* ${exit_price:.8f}" if exit_price < 0.0001 else f"*Exit:* ${exit_price:.6f}" if exit_price < 1 else f"*Exit:* ${exit_price:.4f}",
                "",
                f"{pnl_emoji} *P&L:* {pnl_sign}${abs(pnl_usd):.2f} ({pnl_sign}{pnl_percent:.1f}%)",
            ]

            # Show success fee if it was a winning trade
            if is_profit and success_fee > 0:
                lines.extend([
                    "",
                    "💰 *Success Fee (0.5% on profit)*",
                    f"├ Fee: -${success_fee:.4f}",
                    f"└ Net Profit: +${(net_profit or (pnl_usd - success_fee)):.2f}",
                    "",
                    "_Fee supports JARVIS development_",
                ])
            elif not is_profit:
                lines.extend([
                    "",
                    "💰 _No success fee (losing trade)_",
                ])

            if tx_hash:
                short_hash = f"{tx_hash[:8]}...{tx_hash[-8:]}" if len(tx_hash) > 16 else tx_hash
                lines.extend([
                    "",
                    f"*TX:* `{short_hash}`",
                ])

            lines.extend([
                "",
                "━━━━━━━━━━━━━━━━━━━━━",
            ])
        else:
            lines = [
                f"❌ *CLOSE FAILED*",
                "━━━━━━━━━━━━━━━━━━━━━",
                "",
                f"*Token:* {symbol}",
                f"*Error:* {error or 'Unknown error'}",
                "",
                "━━━━━━━━━━━━━━━━━━━━━",
                "_Try again or check position_",
            ]

        text = "\n".join(lines)

        keyboard = [
            [
                InlineKeyboardButton(f"📊 Positions", callback_data="demo:positions"),
                InlineKeyboardButton(f"📊 Hub", callback_data="demo:hub"),
            ],
            [
                InlineKeyboardButton(f"{theme.BACK} Main Menu", callback_data="demo:main"),
            ],
        ]

        return text, InlineKeyboardMarkup(keyboard)

    # ========== END SENTIMENT HUB ==========

    @staticmethod
    def ai_report_menu(
        market_regime: Dict[str, Any] = None,
    ) -> Tuple[str, InlineKeyboardMarkup]:
        """
        Show AI sentiment report summary with comprehensive market data.

        Displays detailed market analysis from our sentiment engine including:
        - Market regime and risk level
        - BTC/SOL trends and volume
        - Top gainers and losers
        - Market momentum indicators
        - Sector performance
        """
        theme = JarvisTheme

        regime = market_regime or {}
        regime_name = regime.get("regime", "NEUTRAL")
        risk_level = regime.get("risk_level", "NORMAL")
        btc_change = regime.get("btc_change_24h", 0)
        sol_change = regime.get("sol_change_24h", 0)
        btc_trend = regime.get("btc_trend", "NEUTRAL")
        sol_trend = regime.get("sol_trend", "NEUTRAL")

        # Volume data
        btc_volume = regime.get("btc_volume_24h", 0)
        sol_volume = regime.get("sol_volume_24h", 0)

        # Market breadth
        gainers = regime.get("gainers_count", 0)
        losers = regime.get("losers_count", 0)
        total_tokens = max(gainers + losers, 1)
        breadth_pct = (gainers / total_tokens) * 100 if total_tokens > 0 else 50

        # Status emojis
        regime_emoji = {"BULL": "🟢", "BEAR": "🔴"}.get(regime_name, "🟡")
        btc_emoji = "📈" if btc_change >= 0 else "📉"
        sol_emoji = "📈" if sol_change >= 0 else "📉"
        risk_emoji = {"LOW": "🟢", "NORMAL": "🟡", "HIGH": "🟠", "EXTREME": "🔴"}.get(risk_level, "⚪")

        # Momentum indicator
        if btc_change > 3 and sol_change > 3:
            momentum = "🚀 STRONG UP"
        elif btc_change < -3 and sol_change < -3:
            momentum = "📉 STRONG DOWN"
        elif btc_change > 0 and sol_change > 0:
            momentum = "↗️ BULLISH"
        elif btc_change < 0 and sol_change < 0:
            momentum = "↘️ BEARISH"
        else:
            momentum = "↔️ MIXED"

        # Determine recommendation with more detail
        if regime_name == "BULL" and risk_level in ("LOW", "NORMAL"):
            recommendation = "✅ CONDITIONS FAVORABLE\n   Quality entries, swing trades"
        elif regime_name == "BEAR":
            recommendation = "⚠️ CAUTION ADVISED\n   Reduce sizes, tight stops"
        elif risk_level in ("HIGH", "EXTREME"):
            recommendation = "🛑 HIGH RISK ENVIRONMENT\n   Defensive positioning, scalp only"
        else:
            recommendation = "📊 NEUTRAL MARKET\n   Selective opportunities, be patient"

        # Format volumes
        btc_vol_str = f"${btc_volume/1_000_000_000:.1f}B" if btc_volume > 0 else "N/A"
        sol_vol_str = f"${sol_volume/1_000_000_000:.1f}B" if sol_volume > 0 else "N/A"

        text = f"""
{theme.AUTO} *AI MARKET REPORT*
━━━━━━━━━━━━━━━━━━━━━

{theme.CHART} *Market Overview*
┌ Regime: {regime_emoji} *{regime_name}*
├ Risk: {risk_emoji} *{risk_level}*
├ Momentum: {momentum}
└ Breadth: *{breadth_pct:.0f}%* up ({gainers}/{total_tokens})

{btc_emoji} *Bitcoin (BTC)*
├ 24h: *{btc_change:+.1f}%*
├ Trend: *{btc_trend}*
└ Volume: {btc_vol_str}

{sol_emoji} *Solana (SOL)*
├ 24h: *{sol_change:+.1f}%*
├ Trend: *{sol_trend}*
└ Volume: {sol_vol_str}

{theme.FIRE} *Market Activity*"""

        # Market Activity - show real data or meaningful fallbacks
        top_gainer_pct = regime.get('top_gainer_pct')
        top_gainer_symbol = regime.get('top_gainer_symbol', 'N/A')
        top_loser_pct = regime.get('top_loser_pct')
        top_loser_symbol = regime.get('top_loser_symbol', 'N/A')
        hot_sectors = regime.get('hot_sectors', ['AI', 'DeFi', 'Memes'])  # Default sectors

        if top_gainer_pct is not None and top_gainer_pct > 0:
            gainer_line = f"├ Top Gainer: *{top_gainer_symbol}* +{top_gainer_pct:.0f}%"
        else:
            gainer_line = "├ Top Gainer: _Scanning..._"

        if top_loser_pct is not None and top_loser_pct < 0:
            loser_line = f"└ Top Loser: *{top_loser_symbol}* {top_loser_pct:.0f}%"
        else:
            loser_line = "└ Top Loser: _Scanning..._"

        sectors_str = ", ".join(hot_sectors[:3]) if isinstance(hot_sectors, list) else "AI, DeFi, Memes"

        text += f"""
├ Hot Sectors: {sectors_str}
{gainer_line}
{loser_line}"""

        text += f"""

━━━━━━━━━━━━━━━━━━━━━

{theme.AUTO} *AI Strategy*
{recommendation}

━━━━━━━━━━━━━━━━━━━━━

_Powered by Grok + Multi-Source Sentiment_
_Real-time data • Jan 2026 tune_
_Updated: {datetime.now(timezone.utc).strftime('%H:%M UTC')}_
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
                InlineKeyboardButton(f"📊 View BTC/SOL Chart", callback_data="demo:view_chart"),
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

        token_ref = token_data.get("token_id") or address
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

        # DexScreener chart link
        chart_url = token_data.get("chart_url", f"https://dexscreener.com/solana/{address}")

        keyboard = [
            [
                InlineKeyboardButton(f"{theme.BUY} Buy 0.1 SOL", callback_data=f"demo:quick_buy:{token_ref}:0.1"),
                InlineKeyboardButton(f"{theme.BUY} Buy 0.5 SOL", callback_data=f"demo:quick_buy:{token_ref}:0.5"),
            ],
            [
                InlineKeyboardButton(f"{theme.BUY} Buy 1 SOL", callback_data=f"demo:quick_buy:{token_ref}:1"),
                InlineKeyboardButton(f"{theme.BUY} Buy 5 SOL", callback_data=f"demo:quick_buy:{token_ref}:5"),
            ],
            [
                InlineKeyboardButton(f"{theme.CHART} Chart", url=chart_url),
                InlineKeyboardButton(f"{theme.REFRESH} Refresh Analysis", callback_data=f"demo:analyze:{token_ref}"),
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
        error_code: str = None,
        retry_action: str = "demo:main",
        context_hint: str = None,
    ) -> Tuple[str, InlineKeyboardMarkup]:
        """
        Show user-friendly error message with recovery options.

        Args:
            error: Error message to display
            error_code: Optional error code for categorization
            retry_action: Callback to retry (default: main menu)
            context_hint: Additional context for the error
        """
        theme = JarvisTheme

        # Categorize error and provide helpful suggestions
        error_lower = error.lower()

        if "network" in error_lower or "timeout" in error_lower or "connection" in error_lower:
            category = "🌐 Network Error"
            suggestion = "Check your internet connection and try again."
        elif "wallet" in error_lower or "balance" in error_lower:
            category = "💳 Wallet Error"
            suggestion = "Make sure your wallet is connected and funded."
        elif "api" in error_lower or "rate limit" in error_lower:
            category = "⚡ API Error"
            suggestion = "Service temporarily unavailable. Wait a moment."
        elif "permission" in error_lower or "unauthorized" in error_lower:
            category = "🔐 Access Error"
            suggestion = "Check your permissions and try again."
        elif "not found" in error_lower:
            category = "🔍 Not Found"
            suggestion = "The requested item doesn't exist."
        elif "invalid" in error_lower or "failed" in error_lower:
            category = "❌ Operation Failed"
            suggestion = "Something went wrong. Please try again."
        else:
            category = f"{theme.ERROR} Error"
            suggestion = "An unexpected error occurred."

        lines = [
            f"{category}",
            "━━━━━━━━━━━━━━━━━━━━━",
            "",
            f"_{error[:150]}{'...' if len(error) > 150 else ''}_",
            "",
        ]

        if context_hint:
            lines.append(f"*Context:* {context_hint}")
            lines.append("")

        lines.extend([
            f"💡 *Suggestion:* {suggestion}",
            "",
            "━━━━━━━━━━━━━━━━━━━━━",
        ])

        if error_code:
            lines.append(f"_Code: {error_code}_")

        text = "\n".join(lines)

        keyboard = [
            [
                InlineKeyboardButton(f"{theme.REFRESH} Try Again", callback_data=retry_action),
                InlineKeyboardButton(f"{theme.BACK} Main Menu", callback_data="demo:main"),
            ],
        ]

        return text, InlineKeyboardMarkup(keyboard)

    @staticmethod
    def operation_failed(
        operation: str,
        reason: str = None,
        retry_action: str = None,
    ) -> Tuple[str, InlineKeyboardMarkup]:
        """Show operation-specific failure message."""
        theme = JarvisTheme

        text = f"""
❌ *{operation.upper()} FAILED*
━━━━━━━━━━━━━━━━━━━━━

{reason or 'Operation could not be completed.'}

Please try again or return to main menu.

━━━━━━━━━━━━━━━━━━━━━
"""

        keyboard = []
        if retry_action:
            keyboard.append([
                InlineKeyboardButton(f"{theme.REFRESH} Retry {operation}", callback_data=retry_action),
            ])
        keyboard.append([
            InlineKeyboardButton(f"{theme.BACK} Main Menu", callback_data="demo:main"),
        ])

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
                try:
                    win_rate_val = float(str(win_rate).replace("%", ""))
                except (ValueError, TypeError):
                    win_rate_val = 0.0
                emoji = "🟢" if win_rate_val > 55 else "🟡" if win_rate_val > 45 else "🔴"
                safe_signal = escape_md(str(signal))
                safe_win_rate = escape_md(str(win_rate))
                lines.append(f"├ {emoji} {safe_signal}: {safe_win_rate} ({trades} trades)")
            lines.append("")

        # Regime correlations
        if regimes:
            lines.append(f"📈 *Regime Performance*")
            for regime, stats in regimes.items():
                win_rate = stats.get("win_rate", "N/A")
                avg_return = stats.get("avg_return", "0%")
                emoji = {"BULL": "🟢", "BEAR": "🔴"}.get(regime, "🟡")
                safe_regime = escape_md(str(regime))
                safe_win_rate = escape_md(str(win_rate))
                safe_avg_return = escape_md(str(avg_return))
                lines.append(f"├ {emoji} {safe_regime}: {safe_win_rate} | {safe_avg_return}")
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
                token_ref = token.get("token_id") or token.get("address", "")
                emoji = "🟢" if change >= 0 else "🔴"
                lines.append(f"  {emoji} {symbol} ({'+' if change >= 0 else ''}{change:.1f}%)")

                if token_ref:
                    keyboard.append([
                        InlineKeyboardButton(
                            f"{theme.BUY} Buy {symbol} (0.1 SOL)",
                            callback_data=f"demo:quick_buy:{token_ref}:0.1"
                        ),
                        InlineKeyboardButton(
                            f"{theme.BUY} (0.5 SOL)",
                            callback_data=f"demo:quick_buy:{token_ref}:0.5"
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

    @staticmethod
    def watchlist_menu(
        watchlist: List[Dict[str, Any]],
    ) -> Tuple[str, InlineKeyboardMarkup]:
        """
        Token Watchlist - Track your favorite tokens.

        Features:
        - Live price updates
        - Quick buy buttons
        - Price alerts (V2)
        """
        theme = JarvisTheme

        lines = [
            f"⭐ *WATCHLIST*",
            "━━━━━━━━━━━━━━━━━━━━━",
            "",
        ]

        keyboard = []

        if not watchlist:
            lines.extend([
                "_Your watchlist is empty_",
                "",
                "Add tokens to track their prices",
                "and get quick access to trade!",
                "",
                "_Paste a token address to add_",
            ])
        else:
            for i, token in enumerate(watchlist[:8]):
                symbol = token.get("symbol", "???")
                token_ref = token.get("token_id") or token.get("address", "")
                price = token.get("price", 0)
                change_24h = token.get("change_24h", 0)
                alert = token.get("alert", None)

                change_emoji = "🟢" if change_24h >= 0 else "🔴"
                change_sign = "+" if change_24h >= 0 else ""

                lines.append(f"{change_emoji} *{symbol}* ${price:.6f}")
                lines.append(f"   {change_sign}{change_24h:.1f}% (24h)")

                if alert:
                    lines.append(f"   🔔 Alert: ${alert}")

                lines.append("")

                if token_ref:
                    keyboard.append([
                        InlineKeyboardButton(
                            f"{theme.BUY} Buy {symbol}",
                            callback_data=f"demo:quick_buy:{token_ref}:0.1"
                        ),
                        InlineKeyboardButton(
                            f"🗑️ Remove",
                            callback_data=f"demo:watchlist_remove:{i}"
                        ),
                    ])

        lines.extend([
            "━━━━━━━━━━━━━━━━━━━━━",
        ])

        text = "\n".join(lines)

        keyboard.extend([
            [
                InlineKeyboardButton(f"➕ Add Token", callback_data="demo:watchlist_add"),
                InlineKeyboardButton(f"{theme.REFRESH} Refresh", callback_data="demo:watchlist"),
            ],
            [
                InlineKeyboardButton(f"{theme.BACK} Back", callback_data="demo:main"),
            ],
        ])

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
            engine = await _get_demo_engine()

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
        ai_auto_enabled = context.user_data.get("ai_auto_trade", False)
        text, keyboard = DemoMenuBuilder.main_menu(
            wallet_address=wallet_address,
            sol_balance=sol_balance,
            usd_value=usd_value,
            is_live=is_live,
            open_positions=open_positions,
            total_pnl=total_pnl,
            market_regime=market_regime,
            ai_auto_enabled=ai_auto_enabled,
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
    data = query.data if query else ""

    # Enforce admin-only demo access (callbacks can be clicked by anyone)
    try:
        config = get_config()
        user_id = query.from_user.id if query and query.from_user else 0
        username = query.from_user.username if query and query.from_user else None
        try:
            is_admin = config.is_admin(user_id, username)
        except TypeError:
            is_admin = config.is_admin(user_id)
        if not is_admin:
            try:
                await query.answer("Admin only.", show_alert=True)
            except BadRequest as exc:
                if (
                    "Query is too old" in str(exc)
                    or "response timeout expired" in str(exc)
                    or "query id is invalid" in str(exc)
                ):
                    logger.debug("Demo callback expired before admin check.")
                    return
                raise
            logger.warning(f"Unauthorized demo callback by user {user_id} (@{username})")
            return
    except Exception as exc:
        logger.warning(f"Demo admin check failed: {exc}")

    try:
        await query.answer()
    except BadRequest as exc:
        if (
            "Query is too old" in str(exc)
            or "response timeout expired" in str(exc)
            or "query id is invalid" in str(exc)
        ):
            logger.debug("Demo callback expired before answer.")
            return
        raise

    # Run TP/SL/trailing stop checks for demo positions (throttled)
    await _process_demo_exit_checks(update, context)

    callback_data = data  # Store for error logging

    if not data.startswith("demo:"):
        logger.warning(f"Non-demo callback received: {data}")
        return

    action = data.split(":")[1] if ":" in data else data
    logger.info(f"Demo callback: action={action}, full_data={data}")

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
            engine = await _get_demo_engine()

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
        ai_auto_enabled = context.user_data.get("ai_auto_trade", False)

        if action in ("main", "refresh"):
            text, keyboard = DemoMenuBuilder.main_menu(
                wallet_address=wallet_address,
                sol_balance=sol_balance,
                usd_value=usd_value,
                is_live=is_live,
                open_positions=open_positions_count,
                total_pnl=total_pnl,
                market_regime=market_regime,
                ai_auto_enabled=ai_auto_enabled,
            )

        elif action == "wallet_menu":
            # Fetch token holdings
            token_holdings = []
            total_holdings_usd = 0.0
            try:
                engine = await _get_demo_engine()
                if engine and hasattr(engine, 'get_token_holdings'):
                    holdings = await engine.get_token_holdings()
                    if holdings:
                        token_holdings = holdings
                        total_holdings_usd = sum(h.get("value_usd", 0) for h in holdings)
            except Exception:
                pass

            text, keyboard = DemoMenuBuilder.wallet_menu(
                wallet_address=wallet_address,
                sol_balance=sol_balance,
                usd_value=usd_value,
                has_wallet=wallet_address != "Not configured",
                token_holdings=token_holdings,
                total_holdings_usd=total_holdings_usd,
            )

        elif action == "token_holdings":
            # Detailed token holdings view
            token_holdings = []
            total_holdings_usd = 0.0
            try:
                engine = await _get_demo_engine()
                if engine and hasattr(engine, 'get_token_holdings'):
                    holdings = await engine.get_token_holdings()
                    if holdings:
                        token_holdings = holdings
                        total_holdings_usd = sum(h.get("value_usd", 0) for h in holdings)
            except Exception:
                pass

            text, keyboard = DemoMenuBuilder.token_holdings_view(
                holdings=token_holdings,
                total_value=total_holdings_usd,
            )

        elif action == "wallet_activity":
            # Wallet transaction history
            transactions = []
            try:
                engine = await _get_demo_engine()
                if engine and hasattr(engine, 'get_transaction_history'):
                    transactions = await engine.get_transaction_history()
            except Exception:
                pass

            text, keyboard = DemoMenuBuilder.wallet_activity_view(
                transactions=transactions,
            )

        elif action == "send_sol":
            text, keyboard = DemoMenuBuilder.send_sol_view(sol_balance=sol_balance)

        elif action == "receive_sol":
            # Show receive address with QR placeholder
            theme = JarvisTheme
            text = f"""
📥 *RECEIVE SOL*
━━━━━━━━━━━━━━━━━━━━━

Your wallet address:
`{wallet_address}`

_Tap the address to copy_

{theme.WARNING} Only send SOL and Solana
   tokens to this address!

━━━━━━━━━━━━━━━━━━━━━
_QR code coming in V2_
"""
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton(f"{theme.COPY} Copy Address", callback_data="demo:copy_address")],
                [InlineKeyboardButton(f"{theme.BACK} Back", callback_data="demo:wallet_menu")],
            ])

        elif action == "export_key_confirm":
            text, keyboard = DemoMenuBuilder.export_key_confirm()

        elif action == "wallet_reset_confirm":
            text, keyboard = DemoMenuBuilder.wallet_reset_confirm()

        elif action == "wallet_import":
            # Show wallet import options
            text, keyboard = DemoMenuBuilder.wallet_import_prompt()

        elif action == "import_mode_key":
            # Set import mode to private key
            context.user_data["import_mode"] = "key"
            context.user_data["awaiting_wallet_import"] = True
            text, keyboard = DemoMenuBuilder.wallet_import_input(import_type="key")

        elif action == "import_mode_seed":
            # Set import mode to seed phrase
            context.user_data["import_mode"] = "seed"
            context.user_data["awaiting_wallet_import"] = True
            text, keyboard = DemoMenuBuilder.wallet_import_input(import_type="seed")

        elif action == "export_key":
            # Show actual private key (SENSITIVE)
            theme = JarvisTheme
            try:
                from bots.treasury.wallet import SecureWallet
                wallet_password = _get_demo_wallet_password()
                if not wallet_password:
                    raise ValueError("Demo wallet password not configured")
                wallet = SecureWallet(
                    master_password=wallet_password,
                    wallet_dir=_get_demo_wallet_dir(),
                )
                private_key = wallet.get_private_key()  # Returns base58 key
                wallet_address = wallet.get_address()

                text, keyboard = DemoMenuBuilder.export_key_show(
                    private_key=private_key,
                    wallet_address=wallet_address,
                )
                logger.warning(f"Private key exported for wallet {wallet_address[:8]}...")
            except Exception as e:
                logger.error(f"Failed to export key: {e}")
                text, keyboard = DemoMenuBuilder.error_message(
                    f"Could not export key: {str(e)[:50]}"
                )

        elif action == "wallet_create":
            # Generate new wallet
            try:
                from bots.treasury.wallet import SecureWallet
                wallet_password = _get_demo_wallet_password()
                if not wallet_password:
                    raise ValueError("Demo wallet password not configured")
                wallet = SecureWallet(
                    master_password=wallet_password,
                    wallet_dir=_get_demo_wallet_dir(),
                )
                wallet_info = wallet.create_wallet(label="Demo Treasury", is_treasury=True)
                # Note: In production, this would require password setup
                # For demo, show what would happen
                text, keyboard = DemoMenuBuilder.success_message(
                    action="Wallet Generated",
                    details=f"New Solana wallet created and encrypted.\n\nAddress:\n`{wallet_info.address}`\n\nSend SOL to fund your trading!",
                )
            except Exception as e:
                text, keyboard = DemoMenuBuilder.error_message(f"Wallet creation failed: {e}")

        elif action == "positions":
            text, keyboard = DemoMenuBuilder.positions_menu(
                positions=positions,
                total_pnl=total_pnl,
            )

        elif action == "positions_all":
            # Show ALL positions with detailed info
            theme = JarvisTheme
            if not positions:
                text, keyboard = DemoMenuBuilder.error_message(
                    error="No open positions",
                    retry_action="demo:main",
                )
            else:
                lines = [
                    f"📋 *ALL OPEN POSITIONS ({len(positions)})*",
                    "━━━━━━━━━━━━━━━━━━━━━",
                    "",
                ]

                for i, pos in enumerate(positions, 1):
                    symbol = pos.get("symbol", "???")
                    pnl_pct = pos.get("pnl_pct", 0)
                    pnl_usd = pos.get("pnl_usd", 0)
                    entry_price = pos.get("entry_price", 0)
                    current_price = pos.get("current_price", 0)

                    pnl_emoji = "🟢" if pnl_pct >= 0 else "🔴"
                    pnl_sign = "+" if pnl_pct >= 0 else ""

                    lines.extend([
                        f"{i}. *{symbol}* {pnl_emoji}",
                        f"   P&L: {pnl_sign}{pnl_pct:.1f}% (${pnl_usd:+.2f})",
                        f"   Entry: ${entry_price:.8f}" if entry_price < 0.01 else f"   Entry: ${entry_price:.4f}",
                        f"   Current: ${current_price:.8f}" if current_price < 0.01 else f"   Current: ${current_price:.4f}",
                        "",
                    ])

                # Add summary
                winners = sum(1 for p in positions if p.get("pnl_pct", 0) >= 0)
                losers = len(positions) - winners
                total_pnl_sum = sum(p.get("pnl_usd", 0) for p in positions)
                total_pnl_sign = "+" if total_pnl_sum >= 0 else ""

                lines.extend([
                    "━━━━━━━━━━━━━━━━━━━━━",
                    f"📊 *Summary*",
                    f"├ Total P&L: ${total_pnl_sign}{abs(total_pnl_sum):.2f}",
                    f"├ Winners: 🟢 {winners}",
                    f"├ Losers: 🔴 {losers}",
                    f"└ Win Rate: {(winners/len(positions)*100):.0f}%",
                ])

                text = "\n".join(lines)
                keyboard = InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton(f"📊 P&L Report", callback_data="demo:pnl_report"),
                        InlineKeyboardButton(f"📈 Positions", callback_data="demo:positions"),
                    ],
                    [
                        InlineKeyboardButton(f"{theme.BACK} Main Menu", callback_data="demo:main"),
                    ],
                ])

        elif action == "settings":
            ai_auto = context.user_data.get("ai_auto_trade", False)
            text, keyboard = DemoMenuBuilder.settings_menu(
                is_live=is_live,
                ai_auto_trade=ai_auto,
            )

        elif action == "fee_stats":
            # Show fee collection statistics
            fee_manager = get_success_fee_manager()
            stats = fee_manager.get_fee_stats()
            text, keyboard = DemoMenuBuilder.fee_stats_view(
                fee_percent=stats.get("fee_percent", 0.5),
                total_collected=stats.get("total_collected", 0.0),
                transaction_count=stats.get("transaction_count", 0),
                recent_fees=stats.get("recent_fees", []),
            )

        elif action == "pnl_report":
            # Show P&L report
            # Calculate stats from positions
            winners = sum(1 for p in positions if p.get("pnl_pct", 0) >= 0)
            losers = sum(1 for p in positions if p.get("pnl_pct", 0) < 0)
            total_pnl_pct = sum(p.get("pnl_pct", 0) for p in positions) / max(len(positions), 1)

            # Find best and worst
            best_trade = max(positions, key=lambda p: p.get("pnl_pct", 0)) if positions else None
            worst_trade = min(positions, key=lambda p: p.get("pnl_pct", 0)) if positions else None

            text, keyboard = DemoMenuBuilder.pnl_report_view(
                positions=positions,
                total_pnl_usd=total_pnl,
                total_pnl_percent=total_pnl_pct,
                winners=winners,
                losers=losers,
                best_trade=best_trade,
                worst_trade=worst_trade,
            )

        elif action == "ai_auto_settings":
            # AI Auto-Trade Settings
            ai_settings = context.user_data.get("ai_settings", {})
            text, keyboard = DemoMenuBuilder.ai_auto_trade_settings(
                enabled=ai_settings.get("enabled", False),
                risk_level=ai_settings.get("risk_level", "MEDIUM"),
                max_position_size=ai_settings.get("max_position_size", 0.5),
                min_confidence=ai_settings.get("min_confidence", 0.7),
                daily_limit=ai_settings.get("daily_limit", 2.0),
                cooldown_minutes=ai_settings.get("cooldown_minutes", 30),
            )

        elif data.startswith("demo:ai_auto_toggle:"):
            # Toggle AI auto-trade
            parts = data.split(":")
            new_state = parts[2].lower() == "true" if len(parts) >= 3 else False

            # Update settings
            ai_settings = context.user_data.get("ai_settings", {})
            ai_settings["enabled"] = new_state
            context.user_data["ai_settings"] = ai_settings
            context.user_data["ai_auto_trade"] = new_state

            action_text = "ENABLED" if new_state else "DISABLED"
            text, keyboard = DemoMenuBuilder.success_message(
                action=f"AI Auto-Trade {action_text}",
                details=f"Autonomous trading is now {'active' if new_state else 'paused'}.\n\n{'JARVIS will monitor markets and execute trades based on your settings.' if new_state else 'JARVIS will not execute trades automatically.'}",
            )

        elif data.startswith("demo:ai_risk:"):
            # Set AI risk level
            parts = data.split(":")
            risk_level = parts[2] if len(parts) >= 3 else "MEDIUM"

            ai_settings = context.user_data.get("ai_settings", {})
            ai_settings["risk_level"] = risk_level
            context.user_data["ai_settings"] = ai_settings

            # Return to settings view
            text, keyboard = DemoMenuBuilder.ai_auto_trade_settings(
                enabled=ai_settings.get("enabled", False),
                risk_level=risk_level,
                max_position_size=ai_settings.get("max_position_size", 0.5),
                min_confidence=ai_settings.get("min_confidence", 0.7),
            )

        elif data.startswith("demo:ai_max:"):
            # Set max position size
            parts = data.split(":")
            max_size = float(parts[2]) if len(parts) >= 3 else 0.5

            ai_settings = context.user_data.get("ai_settings", {})
            ai_settings["max_position_size"] = max_size
            context.user_data["ai_settings"] = ai_settings

            text, keyboard = DemoMenuBuilder.ai_auto_trade_settings(
                enabled=ai_settings.get("enabled", False),
                risk_level=ai_settings.get("risk_level", "MEDIUM"),
                max_position_size=max_size,
                min_confidence=ai_settings.get("min_confidence", 0.7),
            )

        elif data.startswith("demo:ai_conf:"):
            # Set min confidence threshold
            parts = data.split(":")
            min_conf = float(parts[2]) if len(parts) >= 3 else 0.7

            ai_settings = context.user_data.get("ai_settings", {})
            ai_settings["min_confidence"] = min_conf
            context.user_data["ai_settings"] = ai_settings

            text, keyboard = DemoMenuBuilder.ai_auto_trade_settings(
                enabled=ai_settings.get("enabled", False),
                risk_level=ai_settings.get("risk_level", "MEDIUM"),
                max_position_size=ai_settings.get("max_position_size", 0.5),
                min_confidence=min_conf,
            )

        elif action == "ai_auto_status":
            # AI Auto-Trade Status View
            ai_settings = context.user_data.get("ai_settings", {})
            text, keyboard = DemoMenuBuilder.ai_auto_trade_status(
                enabled=ai_settings.get("enabled", False),
                trades_today=context.user_data.get("ai_trades_today", 0),
                pnl_today=context.user_data.get("ai_pnl_today", 0.0),
            )

        elif action == "ai_trades_history":
            # AI Trades History (placeholder)
            theme = JarvisTheme
            text = f"""
{theme.AUTO} *AI TRADE HISTORY*
━━━━━━━━━━━━━━━━━━━━━

_No AI trades executed yet_

When AI auto-trading is enabled,
JARVIS will:
• Analyze market conditions
• Find high-confidence opportunities
• Execute trades within your limits
• Record all trades here

━━━━━━━━━━━━━━━━━━━━━
_Feature tracking all AI trades coming in V2_
"""
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton(f"{theme.BACK} Back", callback_data="demo:ai_auto_settings")],
            ])

        elif action == "balance":
            text, keyboard = DemoMenuBuilder.wallet_menu(
                wallet_address=wallet_address,
                sol_balance=sol_balance,
                usd_value=usd_value,
                has_wallet=True,
            )

        # ========== P&L ALERTS HANDLERS ==========
        elif action == "pnl_alerts":
            # Show P&L Alerts Overview
            alerts = context.user_data.get("pnl_alerts", [])
            text, keyboard = DemoMenuBuilder.pnl_alerts_overview(
                alerts=alerts,
                positions=positions,
            )

        elif data.startswith("demo:alert_setup:"):
            # Set up alert for a specific position
            parts = data.split(":")
            pos_id = parts[2] if len(parts) >= 3 else "0"

            # Find the position
            target_pos = None
            for pos in positions:
                if str(pos.get("id", "")) == pos_id:
                    target_pos = pos
                    break

            if target_pos:
                alerts = context.user_data.get("pnl_alerts", [])
                text, keyboard = DemoMenuBuilder.position_alert_setup(
                    position=target_pos,
                    existing_alerts=alerts,
                )
            else:
                text, keyboard = DemoMenuBuilder.error_message("Position not found")

        elif data.startswith("demo:create_alert:"):
            # Create a new alert: demo:create_alert:{pos_id}:{type}:{target}
            parts = data.split(":")
            if len(parts) >= 5:
                pos_id = parts[2]
                alert_type = parts[3]  # percent, pnl, price
                target = float(parts[4])

                # Find the position
                target_pos = None
                for pos in positions:
                    if str(pos.get("id", "")) == pos_id:
                        target_pos = pos
                        break

                if target_pos:
                    symbol = target_pos.get("symbol", "???")
                    direction = "above" if target > 0 else "below"

                    # Create alert object
                    new_alert = {
                        "id": f"alert_{pos_id}_{target}",
                        "position_id": pos_id,
                        "symbol": symbol,
                        "type": alert_type,
                        "target": target,
                        "direction": direction,
                        "triggered": False,
                        "created_at": datetime.now().isoformat(),
                    }

                    # Store alert
                    alerts = context.user_data.get("pnl_alerts", [])
                    alerts.append(new_alert)
                    context.user_data["pnl_alerts"] = alerts

                    text, keyboard = DemoMenuBuilder.alert_created_success(
                        symbol=symbol,
                        alert_type=alert_type,
                        target=target,
                        direction=direction,
                    )
                else:
                    text, keyboard = DemoMenuBuilder.error_message("Position not found")
            else:
                text, keyboard = DemoMenuBuilder.error_message("Invalid alert data")

        elif data.startswith("demo:delete_pos_alerts:"):
            # Delete all alerts for a position
            parts = data.split(":")
            pos_id = parts[2] if len(parts) >= 3 else "0"

            alerts = context.user_data.get("pnl_alerts", [])
            # Filter out alerts for this position
            alerts = [a for a in alerts if a.get("position_id") != pos_id]
            context.user_data["pnl_alerts"] = alerts

            theme = JarvisTheme
            text = f"""
{theme.SUCCESS} *ALERTS DELETED*
━━━━━━━━━━━━━━━━━━━━━

All alerts for this position have been removed.

━━━━━━━━━━━━━━━━━━━━━
"""
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔔 All Alerts", callback_data="demo:pnl_alerts")],
                [InlineKeyboardButton(f"{theme.CHART} Positions", callback_data="demo:positions")],
            ])

        elif action == "clear_triggered_alerts":
            # Clear all triggered alerts
            alerts = context.user_data.get("pnl_alerts", [])
            # Keep only non-triggered alerts
            alerts = [a for a in alerts if not a.get("triggered", False)]
            context.user_data["pnl_alerts"] = alerts

            theme = JarvisTheme
            text = f"""
{theme.SUCCESS} *TRIGGERED ALERTS CLEARED*
━━━━━━━━━━━━━━━━━━━━━

All triggered alerts have been removed.

━━━━━━━━━━━━━━━━━━━━━
"""
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔔 All Alerts", callback_data="demo:pnl_alerts")],
                [InlineKeyboardButton(f"{theme.BACK} Main Menu", callback_data="demo:main")],
            ])

        elif data.startswith("demo:custom_alert:"):
            # Custom alert entry (placeholder for V2)
            parts = data.split(":")
            pos_id = parts[2] if len(parts) >= 3 else "0"

            theme = JarvisTheme
            text = f"""
{theme.AUTO} *CUSTOM ALERT*
━━━━━━━━━━━━━━━━━━━━━

Custom alert entry coming in V2!

For now, use the quick presets:
• +25%, +50%, +100% profit
• -10%, -25%, -50% loss

━━━━━━━━━━━━━━━━━━━━━
_Custom values & price alerts soon_
"""
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton(f"{theme.BACK} Back", callback_data=f"demo:alert_setup:{pos_id}")],
            ])

        # ========== END P&L ALERTS HANDLERS ==========

        # ========== DCA HANDLERS ==========
        elif action == "dca":
            # DCA Overview
            dca_plans = context.user_data.get("dca_plans", [])
            total_invested = sum(p.get("total_invested", 0) for p in dca_plans)
            text, keyboard = DemoMenuBuilder.dca_overview(
                dca_plans=dca_plans,
                total_invested=total_invested,
            )

        elif action == "dca_new":
            # New DCA Plan - select token
            watchlist = context.user_data.get("watchlist", [])
            for token in watchlist:
                token["token_id"] = _register_token_id(context, token.get("address"))
            text, keyboard = DemoMenuBuilder.dca_setup(
                watchlist=watchlist,
            )

        elif data.startswith("demo:dca_select:"):
            # Token selected for DCA
            parts = data.split(":")
            token_ref = parts[2] if len(parts) >= 3 else ""
            token_address = _resolve_token_ref(context, token_ref)

            # Find token info from watchlist or trending
            watchlist = context.user_data.get("watchlist", [])
            token_symbol = "TOKEN"
            for token in watchlist:
                if token.get("address") == token_address:
                    token_symbol = token.get("symbol", "TOKEN")
                    break

            text, keyboard = DemoMenuBuilder.dca_setup(
                token_symbol=token_symbol,
                token_address=token_address,
                token_ref=token_ref,
                watchlist=watchlist,
            )

        elif data.startswith("demo:dca_amount:"):
            # Amount selected for DCA: demo:dca_amount:{address}:{amount}
            try:
                parts = data.split(":")
                if len(parts) >= 4:
                    token_ref = parts[2]
                    token_address = _resolve_token_ref(context, token_ref)
                    amount = float(parts[3])

                    # Find token symbol
                    watchlist = context.user_data.get("watchlist", [])
                    token_symbol = "TOKEN"
                    for token in watchlist:
                        if token.get("address") == token_address:
                            token_symbol = token.get("symbol", "TOKEN")
                            break

                    text, keyboard = DemoMenuBuilder.dca_frequency_select(
                        token_symbol=token_symbol,
                        token_address=token_address,
                        token_ref=token_ref,
                        amount=amount,
                    )
                else:
                    text, keyboard = DemoMenuBuilder.error_message(
                        "Invalid DCA configuration",
                        retry_action="demo:dca_new",
                        context_hint="Amount selection failed"
                    )
            except (ValueError, IndexError) as e:
                logger.warning(f"DCA amount parse error: {e}")
                text, keyboard = DemoMenuBuilder.error_message(
                    f"Invalid amount: {str(e)[:50]}",
                    retry_action="demo:dca_new"
                )

        elif data.startswith("demo:dca_create:"):
            # Create DCA plan: demo:dca_create:{address}:{amount}:{frequency}
            try:
                parts = data.split(":")
                if len(parts) >= 5:
                    token_ref = parts[2]
                    token_address = _resolve_token_ref(context, token_ref)
                    amount = float(parts[3])
                    frequency = parts[4]

                    # Find token symbol
                    watchlist = context.user_data.get("watchlist", [])
                    token_symbol = "TOKEN"
                    for token in watchlist:
                        if token.get("address") == token_address:
                            token_symbol = token.get("symbol", "TOKEN")
                            break

                    # Create DCA plan
                    new_plan = {
                        "id": f"dca_{token_address[:8]}_{datetime.now().strftime('%H%M%S')}",
                        "symbol": token_symbol,
                        "address": token_address,
                        "amount": amount,
                        "frequency": frequency,
                        "active": True,
                        "executions": 0,
                        "total_invested": 0.0,
                        "next_execution": "In 1 " + ("hour" if frequency == "hourly" else "day" if frequency == "daily" else "week"),
                        "created_at": datetime.now().isoformat(),
                    }

                    # Store plan
                    dca_plans = context.user_data.get("dca_plans", [])
                    dca_plans.append(new_plan)
                    context.user_data["dca_plans"] = dca_plans

                    text, keyboard = DemoMenuBuilder.dca_plan_created(
                        token_symbol=token_symbol,
                        amount=amount,
                        frequency=frequency,
                        first_execution="Starting soon",
                    )
                else:
                    text, keyboard = DemoMenuBuilder.error_message(
                        "Invalid DCA configuration",
                        retry_action="demo:dca_new"
                    )
            except (ValueError, IndexError) as e:
                logger.warning(f"DCA create error: {e}")
                text, keyboard = DemoMenuBuilder.operation_failed(
                    "DCA Plan Creation",
                    f"Could not create plan: {str(e)[:50]}",
                    retry_action="demo:dca_new"
                )

        elif data.startswith("demo:dca_pause:"):
            # Pause/Resume DCA plan
            parts = data.split(":")
            plan_id = parts[2] if len(parts) >= 3 else ""

            dca_plans = context.user_data.get("dca_plans", [])
            for plan in dca_plans:
                if plan.get("id") == plan_id:
                    plan["active"] = not plan.get("active", True)
                    break
            context.user_data["dca_plans"] = dca_plans

            # Return to overview
            total_invested = sum(p.get("total_invested", 0) for p in dca_plans)
            text, keyboard = DemoMenuBuilder.dca_overview(
                dca_plans=dca_plans,
                total_invested=total_invested,
            )

        elif data.startswith("demo:dca_delete:"):
            # Delete DCA plan
            parts = data.split(":")
            plan_id = parts[2] if len(parts) >= 3 else ""

            dca_plans = context.user_data.get("dca_plans", [])
            dca_plans = [p for p in dca_plans if p.get("id") != plan_id]
            context.user_data["dca_plans"] = dca_plans

            theme = JarvisTheme
            text = f"""
{theme.SUCCESS} *DCA PLAN DELETED*
━━━━━━━━━━━━━━━━━━━━━

The DCA plan has been removed.
No further automatic purchases
will be made.

━━━━━━━━━━━━━━━━━━━━━
"""
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("📅 View DCA Plans", callback_data="demo:dca")],
                [InlineKeyboardButton(f"{theme.BACK} Main Menu", callback_data="demo:main")],
            ])

        elif action == "dca_history":
            # DCA execution history (placeholder)
            theme = JarvisTheme
            dca_plans = context.user_data.get("dca_plans", [])
            total_executions = sum(p.get("executions", 0) for p in dca_plans)

            text = f"""
{theme.AUTO} *DCA EXECUTION HISTORY*
━━━━━━━━━━━━━━━━━━━━━

📊 *Total Executions:* {total_executions}

_Detailed execution history coming in V2_

Each DCA execution will be logged with:
• Timestamp
• Token purchased
• Amount spent
• Price at execution
• Tokens received

━━━━━━━━━━━━━━━━━━━━━
"""
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("📅 DCA Plans", callback_data="demo:dca")],
                [InlineKeyboardButton(f"{theme.BACK} Main Menu", callback_data="demo:main")],
            ])

        elif action == "dca_input":
            # Manual token address input for DCA (placeholder)
            theme = JarvisTheme
            text = f"""
{theme.AUTO} *ENTER TOKEN ADDRESS*
━━━━━━━━━━━━━━━━━━━━━

Paste a Solana token address to
set up a DCA plan.

_Manual address input coming in V2_

For now, add tokens to your watchlist
first, then create DCA plans from there.

━━━━━━━━━━━━━━━━━━━━━
"""
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("⭐ Go to Watchlist", callback_data="demo:watchlist")],
                [InlineKeyboardButton(f"{theme.BACK} Back", callback_data="demo:dca_new")],
            ])

        # ========== END DCA HANDLERS ==========

        # ========== BAGS.FM HANDLERS ==========

        elif action == "bags_fm":
            # Show Bags.fm Top 15 tokens by volume with sentiment
            try:
                # Fetch tokens with sentiment
                bags_tokens = await get_bags_top_tokens_with_sentiment(limit=15)
                for token in bags_tokens:
                    token["token_id"] = _register_token_id(context, token.get("address"))

                # Get user's TP/SL settings
                default_tp = context.user_data.get("bags_tp_percent", 15.0)
                default_sl = context.user_data.get("bags_sl_percent", 15.0)

                text, keyboard = DemoMenuBuilder.bags_fm_top_tokens(
                    tokens=bags_tokens,
                    market_regime=market_regime,
                    default_tp_percent=default_tp,
                    default_sl_percent=default_sl,
                )
            except Exception as e:
                logger.error(f"Bags.fm error: {e}")
                text, keyboard = DemoMenuBuilder.error_message(
                    error=str(e),
                    retry_action="demo:bags_fm",
                    context_hint="bags_fm",
                )

        elif data.startswith("demo:bags_info:"):
            # Show detailed token info
            token_ref = action.split(":")[1]
            address = _resolve_token_ref(context, token_ref)

            # Find token from cached data or fetch
            bags_tokens = await get_bags_top_tokens_with_sentiment(limit=15)
            token = next((t for t in bags_tokens if t.get("address") == address), None)

            if token:
                token["token_id"] = token_ref
                default_tp = context.user_data.get("bags_tp_percent", 15.0)
                default_sl = context.user_data.get("bags_sl_percent", 15.0)

                text, keyboard = DemoMenuBuilder.bags_token_detail(
                    token=token,
                    market_regime=market_regime,
                    default_tp_percent=default_tp,
                    default_sl_percent=default_sl,
                )
            else:
                text, keyboard = DemoMenuBuilder.error_message(
                    error="Token not found",
                    retry_action="demo:bags_fm",
                )

        elif data.startswith("demo:bags_buy:"):
            # Show buy confirmation for a Bags token
            parts = action.split(":")
            token_ref = parts[1]
            address = _resolve_token_ref(context, token_ref)
            tp_percent = float(parts[2]) if len(parts) > 2 else 15.0
            sl_percent = float(parts[3]) if len(parts) > 3 else 15.0

            # Find token
            bags_tokens = await get_bags_top_tokens_with_sentiment(limit=15)
            token = next((t for t in bags_tokens if t.get("address") == address), None)

            if token:
                token["token_id"] = token_ref
                text, keyboard = DemoMenuBuilder.bags_token_detail(
                    token=token,
                    market_regime=market_regime,
                    default_tp_percent=tp_percent,
                    default_sl_percent=sl_percent,
                )
            else:
                text, keyboard = DemoMenuBuilder.error_message(
                    error="Token not found",
                    retry_action="demo:bags_fm",
                )

        elif data.startswith("demo:bags_exec:"):
            # Execute buy via Bags.fm API
            parts = action.split(":")
            token_ref = parts[1]
            address = _resolve_token_ref(context, token_ref)
            amount_sol = float(parts[2]) if len(parts) > 2 else 0.1
            tp_percent = float(parts[3]) if len(parts) > 3 else 15.0
            sl_percent = float(parts[4]) if len(parts) > 4 else 15.0

            # Find token
            bags_tokens = await get_bags_top_tokens_with_sentiment(limit=15)
            token = next((t for t in bags_tokens if t.get("address") == address), None)

            if token:
                symbol = token.get("symbol", "???")
                price = token.get("price_usd", 0)

                # Execute trade via Bags API with Jupiter fallback
                try:
                    wallet_address = context.user_data.get("wallet_address", "demo_wallet")
                    slippage_bps = _get_demo_slippage_bps()
                    swap = await _execute_swap_with_fallback(
                        from_token="So11111111111111111111111111111111111111112",  # SOL
                        to_token=address,
                        amount=amount_sol,
                        wallet_address=wallet_address,
                        slippage_bps=slippage_bps,
                    )

                    if swap.get("success"):
                        tokens_received = swap.get("amount_out") or (
                            (amount_sol * 225 / price) if price > 0 else 0
                        )

                        # Add position to portfolio
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

                        text, keyboard = DemoMenuBuilder.bags_buy_result(
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
                        text, keyboard = DemoMenuBuilder.bags_buy_result(
                            success=False,
                            symbol=symbol,
                            amount_sol=amount_sol,
                            error=swap.get("error") or "Trade execution failed",
                        )
                except Exception as e:
                    logger.error(f"Bags buy error: {e}")
                    text, keyboard = DemoMenuBuilder.bags_buy_result(
                        success=False,
                        symbol=symbol,
                        amount_sol=amount_sol,
                        error=str(e)[:50],
                    )
            else:
                text, keyboard = DemoMenuBuilder.error_message(
                    error="Token not found",
                    retry_action="demo:bags_fm",
                )

        elif action == "bags_settings":
            # Show TP/SL settings for Bags trading
            theme = JarvisTheme
            default_tp = context.user_data.get("bags_tp_percent", 15.0)
            default_sl = context.user_data.get("bags_sl_percent", 15.0)

            text = f"""
{theme.SETTINGS} *BAGS.FM TRADING SETTINGS*
━━━━━━━━━━━━━━━━━━━━━

*Current Settings:*
🎯 Take Profit: +{default_tp:.0f}%
🛑 Stop Loss: -{default_sl:.0f}%

*Select new TP/SL presets:*

━━━━━━━━━━━━━━━━━━━━━
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
                    InlineKeyboardButton("🎒 Back to Bags", callback_data="demo:bags_fm"),
                ],
            ])

        elif data.startswith("demo:bags_set_tp:"):
            tp_value = float(action.split(":")[1])
            context.user_data["bags_tp_percent"] = tp_value
            await query.answer(f"Take Profit set to +{tp_value:.0f}%")
            # Redirect back to settings
            theme = JarvisTheme
            default_tp = tp_value
            default_sl = context.user_data.get("bags_sl_percent", 15.0)
            text = f"""
{theme.SETTINGS} *BAGS.FM TRADING SETTINGS*
━━━━━━━━━━━━━━━━━━━━━

✅ *Settings Updated!*

*Current Settings:*
🎯 Take Profit: +{default_tp:.0f}%
🛑 Stop Loss: -{default_sl:.0f}%

━━━━━━━━━━━━━━━━━━━━━
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
                    InlineKeyboardButton("🎒 Back to Bags", callback_data="demo:bags_fm"),
                ],
            ])

        elif data.startswith("demo:bags_set_sl:"):
            sl_value = float(action.split(":")[1])
            context.user_data["bags_sl_percent"] = sl_value
            await query.answer(f"Stop Loss set to -{sl_value:.0f}%")
            # Redirect back to settings
            theme = JarvisTheme
            default_tp = context.user_data.get("bags_tp_percent", 15.0)
            default_sl = sl_value
            text = f"""
{theme.SETTINGS} *BAGS.FM TRADING SETTINGS*
━━━━━━━━━━━━━━━━━━━━━

✅ *Settings Updated!*

*Current Settings:*
🎯 Take Profit: +{default_tp:.0f}%
🛑 Stop Loss: -{default_sl:.0f}%

━━━━━━━━━━━━━━━━━━━━━
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
                    InlineKeyboardButton("🎒 Back to Bags", callback_data="demo:bags_fm"),
                ],
            ])

        # ========== END BAGS.FM HANDLERS ==========

        # ========== TRAILING STOP HANDLERS ==========

        elif action == "trailing_stops":
            # Show trailing stop overview
            trailing_stops = context.user_data.get("trailing_stops", [])
            positions = context.user_data.get("positions", [])
            text, keyboard = DemoMenuBuilder.trailing_stop_overview(
                trailing_stops=trailing_stops,
                positions=positions,
            )

        elif action == "tsl_new":
            # Show position selection for new trailing stop
            positions = context.user_data.get("positions", [])
            text, keyboard = DemoMenuBuilder.trailing_stop_setup(positions=positions)

        elif data.startswith("demo:tsl_select:"):
            # Position selected, show trail percentage options
            pos_id = action.split(":")[1]
            positions = context.user_data.get("positions", [])
            position = next((p for p in positions if p.get("id") == pos_id), None)

            if position:
                text, keyboard = DemoMenuBuilder.trailing_stop_setup(position=position)
            else:
                text = "❌ Position not found"
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton(f"{theme.BACK} Back", callback_data="demo:trailing_stops")]
                ])

        elif data.startswith("demo:tsl_create:"):
            # Create trailing stop with: pos_id:trail_percent
            try:
                parts = action.split(":")
                pos_id = parts[1]
                trail_percent = float(parts[2])

                positions = context.user_data.get("positions", [])
                position = next((p for p in positions if p.get("id") == pos_id), None)

                if position:
                    current_price = position.get("current_price", 0)
                    initial_stop = current_price * (1 - trail_percent / 100)

                    # Create trailing stop record
                    new_stop = {
                        "id": f"tsl_{pos_id}_{datetime.now().strftime('%H%M%S')}",
                        "position_id": pos_id,
                        "symbol": position.get("symbol", "???"),
                        "trail_percent": trail_percent,
                        "current_stop_price": initial_stop,
                        "highest_price": current_price,
                        "protected_value": position.get("value_usd", 0),
                        "protected_pnl": position.get("pnl_pct", 0),
                        "active": True,
                        "created_at": datetime.now().isoformat(),
                    }

                    # Store in user data
                    if "trailing_stops" not in context.user_data:
                        context.user_data["trailing_stops"] = []
                    context.user_data["trailing_stops"].append(new_stop)

                    text, keyboard = DemoMenuBuilder.trailing_stop_created(
                        symbol=position.get("symbol", "???"),
                        trail_percent=trail_percent,
                        initial_stop=initial_stop,
                        current_price=current_price,
                    )
                else:
                    text, keyboard = DemoMenuBuilder.error_message(
                        "Position not found",
                        retry_action="demo:trailing_stops",
                        context_hint="Position may have been closed"
                    )
            except (ValueError, IndexError) as e:
                logger.warning(f"Trailing stop create error: {e}")
                text, keyboard = DemoMenuBuilder.operation_failed(
                    "Trailing Stop",
                    f"Invalid configuration: {str(e)[:50]}",
                    retry_action="demo:trailing_stops"
                )

        elif data.startswith("demo:tsl_edit:"):
            # Edit a trailing stop
            stop_id = action.split(":")[1]
            trailing_stops = context.user_data.get("trailing_stops", [])
            stop = next((s for s in trailing_stops if s.get("id") == stop_id), None)

            if stop:
                # Find the associated position
                positions = context.user_data.get("positions", [])
                position = next((p for p in positions if p.get("id") == stop.get("position_id")), None)

                if position:
                    text, keyboard = DemoMenuBuilder.trailing_stop_setup(position=position)
                else:
                    text = f"🛡️ *Edit Trailing Stop*\n\n{stop.get('symbol', '???')} - {stop.get('trail_percent', 10)}%\n\n_Position no longer exists_"
                    keyboard = InlineKeyboardMarkup([
                        [InlineKeyboardButton("❌ Delete Stop", callback_data=f"demo:tsl_delete:{stop_id}")],
                        [InlineKeyboardButton(f"{theme.BACK} Back", callback_data="demo:trailing_stops")]
                    ])
            else:
                text = "❌ Trailing stop not found"
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton(f"{theme.BACK} Back", callback_data="demo:trailing_stops")]
                ])

        elif data.startswith("demo:tsl_delete:"):
            # Delete a trailing stop
            stop_id = action.split(":")[1]
            trailing_stops = context.user_data.get("trailing_stops", [])

            # Remove the stop
            context.user_data["trailing_stops"] = [
                s for s in trailing_stops if s.get("id") != stop_id
            ]

            # Show updated overview
            text, keyboard = DemoMenuBuilder.trailing_stop_overview(
                trailing_stops=context.user_data.get("trailing_stops", []),
                positions=context.user_data.get("positions", []),
            )

        elif data.startswith("demo:tsl_custom:"):
            # Custom trail percentage - placeholder
            pos_id = action.split(":")[1]
            text = f"""
🛡️ *CUSTOM TRAIL %*
━━━━━━━━━━━━━━━━━━━━━

Enter a custom trailing percentage
(e.g., 7 for 7% trail).

_This feature coming soon!_
"""
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("5%", callback_data=f"demo:tsl_create:{pos_id}:5")],
                [InlineKeyboardButton("10%", callback_data=f"demo:tsl_create:{pos_id}:10")],
                [InlineKeyboardButton(f"{theme.BACK} Back", callback_data=f"demo:tsl_select:{pos_id}")],
            ])

        # ========== END TRAILING STOP HANDLERS ==========

        # ========== POSITION ADJUSTMENT HANDLERS ==========

        elif action == "noop":
            # No-op for label buttons - just acknowledge
            await query.answer("This is a label")
            return

        elif data.startswith("demo:pos_adjust:"):
            # Show position adjustment menu (quick SL/TP)
            pos_id = action.split(":")[1]
            positions = context.user_data.get("positions", [])
            position = next((p for p in positions if p.get("id") == pos_id), None)

            if position:
                text, keyboard = DemoMenuBuilder.position_adjust_menu(
                    pos_id=pos_id,
                    symbol=position.get("symbol", "???"),
                    current_tp=position.get("take_profit", 50.0),
                    current_sl=position.get("stop_loss", 20.0),
                    pnl_pct=position.get("pnl_pct", 0.0),
                )
            else:
                text = "❌ Position not found"
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton(f"{theme.BACK} Back", callback_data="demo:positions")]
                ])

        elif data.startswith("demo:set_tp:"):
            # Set take profit for a position
            try:
                parts = action.split(":")
                pos_id = parts[1]
                tp_value = float(parts[2])

                positions = context.user_data.get("positions", [])
                for p in positions:
                    if p.get("id") == pos_id:
                        p["take_profit"] = tp_value
                        break

                context.user_data["positions"] = positions

                # Show success and return to adjust menu
                position = next((p for p in positions if p.get("id") == pos_id), None)
                if position:
                    await query.answer(f"✅ Take Profit set to +{tp_value}%")
                    text, keyboard = DemoMenuBuilder.position_adjust_menu(
                        pos_id=pos_id,
                        symbol=position.get("symbol", "???"),
                        current_tp=tp_value,
                        current_sl=position.get("stop_loss", 20.0),
                        pnl_pct=position.get("pnl_pct", 0.0),
                    )
                else:
                    text = "❌ Position not found"
                    keyboard = InlineKeyboardMarkup([
                        [InlineKeyboardButton(f"{theme.BACK} Back", callback_data="demo:positions")]
                    ])
            except (ValueError, IndexError) as e:
                logger.warning(f"Set TP error: {e}")
                await query.answer("❌ Error setting TP")
                return

        elif data.startswith("demo:set_sl:"):
            # Set stop loss for a position
            try:
                parts = action.split(":")
                pos_id = parts[1]
                sl_value = float(parts[2])

                positions = context.user_data.get("positions", [])
                for p in positions:
                    if p.get("id") == pos_id:
                        p["stop_loss"] = sl_value
                        break

                context.user_data["positions"] = positions

                # Show success and return to adjust menu
                position = next((p for p in positions if p.get("id") == pos_id), None)
                if position:
                    await query.answer(f"✅ Stop Loss set to -{sl_value}%")
                    text, keyboard = DemoMenuBuilder.position_adjust_menu(
                        pos_id=pos_id,
                        symbol=position.get("symbol", "???"),
                        current_tp=position.get("take_profit", 50.0),
                        current_sl=sl_value,
                        pnl_pct=position.get("pnl_pct", 0.0),
                    )
                else:
                    text = "❌ Position not found"
                    keyboard = InlineKeyboardMarkup([
                        [InlineKeyboardButton(f"{theme.BACK} Back", callback_data="demo:positions")]
                    ])
            except (ValueError, IndexError) as e:
                logger.warning(f"Set SL error: {e}")
                await query.answer("❌ Error setting SL")
                return

        elif data.startswith("demo:trailing_setup:"):
            # Quick trailing stop setup from position adjust menu
            pos_id = action.split(":")[1]
            positions = context.user_data.get("positions", [])
            position = next((p for p in positions if p.get("id") == pos_id), None)

            if position:
                text, keyboard = DemoMenuBuilder.trailing_stop_setup(position=position)
            else:
                text = "❌ Position not found"
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton(f"{theme.BACK} Back", callback_data="demo:positions")]
                ])

        # ========== END POSITION ADJUSTMENT HANDLERS ==========

        elif action == "token_input":
            text, keyboard = DemoMenuBuilder.token_input_prompt()
            # Store state for next message
            context.user_data["awaiting_token"] = True

        elif action == "token_search":
            # Universal Token Search - search and trade ANY token
            theme = JarvisTheme
            text = f"""
🔍 *UNIVERSAL TOKEN SEARCH*
━━━━━━━━━━━━━━━━━━━━━

Trade ANY token by contract address or symbol.

*How to use:*
1. Enter token contract address or symbol
2. View detailed token analysis
3. Buy or sell with custom amounts

*Examples:*
• `So11111111111111111111111111111111111111112` (SOL)
• `EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v` (USDC)
• Or just type: `BONK`, `WIF`, `JUP`

━━━━━━━━━━━━━━━━━━━━━
_Reply with token address or symbol:_
"""
            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(f"📚 Popular Tokens", callback_data="demo:trending"),
                    InlineKeyboardButton(f"🎒 Bags Top 15", callback_data="demo:bags_fm"),
                ],
                [
                    InlineKeyboardButton(f"{theme.BACK} Main Menu", callback_data="demo:main"),
                ],
            ])
            # Mark that we're awaiting token input
            context.user_data["awaiting_token_search"] = True

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
            for token in trending:
                token["token_id"] = _register_token_id(context, token.get("address"))
            text, keyboard = DemoMenuBuilder.trending_tokens(
                trending,
                market_regime=market_regime,
            )

        elif action == "ai_picks":
            # AI Conviction Picks - powered by Grok
            picks = await get_conviction_picks()
            trending = await get_trending_with_sentiment()
            volume_leaders = await get_bags_top_tokens_with_sentiment(limit=6)
            if not trending and volume_leaders:
                trending = volume_leaders[:6]

            for token in picks:
                token["token_id"] = _register_token_id(context, token.get("address"))
            for token in (trending or []):
                token["token_id"] = _register_token_id(context, token.get("address"))
            for token in volume_leaders:
                token["token_id"] = _register_token_id(context, token.get("address"))

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

            pick_stats = _get_pick_stats()
            text, keyboard = DemoMenuBuilder.ai_picks_menu(
                picks=picks,
                market_regime=market_regime,
                trending=trending,
                volume_leaders=volume_leaders,
                near_picks=near_picks,
                pick_stats=pick_stats,
            )

        elif action == "ai_report":
            # AI Market Report
            text, keyboard = DemoMenuBuilder.ai_report_menu(
                market_regime=market_regime,
            )

        elif action == "view_chart":
            # Generate and send BTC/SOL price chart
            try:
                if not MATPLOTLIB_AVAILABLE:
                    text, keyboard = DemoMenuBuilder.error_message(
                        error="Chart generation not available",
                        retry_action="demo:ai_report",
                        context_hint="Install matplotlib to enable charts: pip install matplotlib"
                    )
                else:
                    # Generate mock price data (in production, fetch from API)
                    import random
                    base_btc = 42000
                    base_sol = 100
                    hours = 24
                    timestamps = [datetime.now(timezone.utc) - timedelta(hours=hours-i) for i in range(hours)]
                    btc_prices = [base_btc + random.uniform(-2000, 2000) for _ in range(hours)]
                    sol_prices = [base_sol + random.uniform(-5, 5) for _ in range(hours)]

                    # Generate BTC chart
                    btc_chart = generate_price_chart(
                        prices=btc_prices,
                        timestamps=timestamps,
                        symbol="BTC",
                        timeframe="24H"
                    )

                    # Generate SOL chart
                    sol_chart = generate_price_chart(
                        prices=sol_prices,
                        timestamps=timestamps,
                        symbol="SOL",
                        timeframe="24H"
                    )

                    if btc_chart and sol_chart:
                        await query.message.reply_photo(
                            photo=btc_chart,
                            caption="📊 *Bitcoin (BTC) - 24H Price Chart*\n\n_Generated by JARVIS AI_",
                            parse_mode=ParseMode.MARKDOWN
                        )
                        await query.message.reply_photo(
                            photo=sol_chart,
                            caption="📊 *Solana (SOL) - 24H Price Chart*\n\n_Generated by JARVIS AI_",
                            parse_mode=ParseMode.MARKDOWN
                        )
                        # Return to AI report menu
                        text, keyboard = DemoMenuBuilder.ai_report_menu(market_regime=market_regime)
                    else:
                        text, keyboard = DemoMenuBuilder.error_message(
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
                text, keyboard = DemoMenuBuilder.error_message(
                    error=str(e)[:100],
                    retry_action="demo:view_chart",
                    context_hint=f"Error ID: {error_id}"
                )

        # ========== SENTIMENT HUB HANDLERS ==========
        elif action == "hub":
            # Main Sentiment Hub Dashboard
            try:
                last_report_time = context.user_data.get("hub_last_report", datetime.now(timezone.utc))
                wallet_connected = bool(context.user_data.get("wallet_address"))

                text, keyboard = DemoMenuBuilder.sentiment_hub_main(
                    market_regime=market_regime,
                    last_report_time=last_report_time,
                    report_interval_minutes=15,
                    wallet_connected=wallet_connected,
                )
            except Exception as e:
                logger.error(f"Hub error: {e}")
                text, keyboard = DemoMenuBuilder.error_message(
                    error=str(e),
                    retry_action="demo:hub",
                    context_hint="sentiment_hub",
                )

        elif data.startswith("demo:hub_"):
            # Hub section handlers
            try:
                section = action.replace("hub_", "")

                # Generate mock picks based on section
                section_picks = {
                    "bluechips": [
                        {"symbol": "SOL", "address": "So11111111111111111111111111111111111111112", "price": 225.50, "change_24h": 2.5, "conviction": "HIGH", "tp_percent": 20, "sl_percent": 10, "score": 85},
                        {"symbol": "JUP", "address": "JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN", "price": 1.25, "change_24h": 5.2, "conviction": "HIGH", "tp_percent": 25, "sl_percent": 12, "score": 82},
                        {"symbol": "RAY", "address": "4k3Dyjzvzp8eMZWUXbBCjEvwSkkk59S5iCNLY3QrkX6R", "price": 8.45, "change_24h": 1.8, "conviction": "MEDIUM", "tp_percent": 15, "sl_percent": 10, "score": 78},
                    ],
                    "top10": [
                        {"symbol": "BONK", "address": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263", "price": 0.0000325, "change_24h": 15.2, "conviction": "VERY HIGH", "tp_percent": 30, "sl_percent": 15, "score": 92},
                        {"symbol": "WIF", "address": "EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm", "price": 2.85, "change_24h": 8.5, "conviction": "HIGH", "tp_percent": 25, "sl_percent": 12, "score": 88},
                        {"symbol": "POPCAT", "address": "7GCihgDB8fe6KNjn2MYtkzZcRjQy3t9GHdC8uHYmW2hr", "price": 1.42, "change_24h": 22.1, "conviction": "HIGH", "tp_percent": 35, "sl_percent": 15, "score": 86},
                    ],
                    "xstocks": [],
                    "prestocks": [],
                    "indexes": [],
                    "trending": [
                        {"symbol": "FARTCOIN", "address": "FART1111111111111111111111111111111111111111", "price": 0.00125, "change_24h": 245.5, "conviction": "VERY HIGH", "tp_percent": 50, "sl_percent": 25, "score": 95},
                        {"symbol": "GIGA", "address": "GIGA1111111111111111111111111111111111111111", "price": 0.0425, "change_24h": 85.2, "conviction": "HIGH", "tp_percent": 40, "sl_percent": 20, "score": 88},
                        {"symbol": "AI16Z", "address": "AI16Z111111111111111111111111111111111111111", "price": 0.875, "change_24h": 32.1, "conviction": "HIGH", "tp_percent": 35, "sl_percent": 18, "score": 85},
                    ],
                }

                picks = section_picks.get(section, [])
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
                    pick["token_id"] = _register_token_id(context, pick.get("address"))

                text, keyboard = DemoMenuBuilder.sentiment_hub_section(
                    section=section,
                    picks=picks,
                    market_regime=market_regime,
                )
            except Exception as e:
                logger.error(f"Hub section error: {e}")
                text, keyboard = DemoMenuBuilder.error_message(
                    error=str(e),
                    retry_action="demo:hub",
                    context_hint="hub_section",
                )

        elif action == "hub_news":
            # Market news section
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

                text, keyboard = DemoMenuBuilder.sentiment_hub_news(
                    news_items=mock_news,
                    macro_analysis=mock_macro,
                )
            except Exception as e:
                logger.error(f"Hub news error: {e}")
                text, keyboard = DemoMenuBuilder.error_message(
                    error=str(e),
                    retry_action="demo:hub_news",
                    context_hint="hub_news",
                )

        elif action == "hub_traditional":
            # Traditional markets section
            try:
                mock_stocks = {"spy_change": 0.45, "qqq_change": 0.72, "dia_change": 0.22, "outlook": "bullish"}
                mock_dxy = {"value": 103.25, "change": -0.15, "trend": "weakening"}
                mock_commodities = [
                    {"symbol": "GOLD", "price": 2045.50, "change": 0.8},
                    {"symbol": "SILVER", "price": 24.15, "change": 1.2},
                    {"symbol": "OIL", "price": 78.50, "change": -0.5},
                ]

                text, keyboard = DemoMenuBuilder.sentiment_hub_traditional(
                    stocks_outlook=mock_stocks,
                    dxy_data=mock_dxy,
                    commodities=mock_commodities,
                )
            except Exception as e:
                logger.error(f"Hub traditional error: {e}")
                text, keyboard = DemoMenuBuilder.error_message(
                    error=str(e),
                    retry_action="demo:hub_traditional",
                    context_hint="hub_traditional",
                )

        elif action == "hub_wallet":
            # Hub wallet management
            try:
                wallet_address = context.user_data.get("wallet_address", "")
                sol_balance = context.user_data.get("sol_balance", 0.0)
                usd_value = sol_balance * 225  # Approximate

                text, keyboard = DemoMenuBuilder.sentiment_hub_wallet(
                    wallet_address=wallet_address,
                    sol_balance=sol_balance,
                    usd_value=usd_value,
                    has_private_key=bool(context.user_data.get("private_key")),
                )
            except Exception as e:
                logger.error(f"Hub wallet error: {e}")
                text, keyboard = DemoMenuBuilder.error_message(
                    error=str(e),
                    retry_action="demo:hub_wallet",
                    context_hint="hub_wallet",
                )

        elif data.startswith("demo:hub_buy:"):
            # Hub buy confirmation
            try:
                parts = callback_data.split(":")
                if len(parts) >= 3:
                    token_ref = parts[2]
                    address = _resolve_token_ref(context, token_ref)
                    auto_sl_percent = float(parts[3]) if len(parts) > 3 else 15.0
                    # Get token info (mock for now)
                    text, keyboard = DemoMenuBuilder.sentiment_hub_buy_confirm(
                        symbol="TOKEN",
                        address=address,
                        price=0.001,
                        auto_sl_percent=auto_sl_percent,
                        token_ref=token_ref,
                    )
                else:
                    text, keyboard = DemoMenuBuilder.error_message(
                        error="Invalid buy request",
                        retry_action="demo:hub",
                    )
            except Exception as e:
                logger.error(f"Hub buy error: {e}")
                text, keyboard = DemoMenuBuilder.error_message(
                    error=str(e),
                    retry_action="demo:hub",
                    context_hint="hub_buy",
                )

        elif data.startswith("demo:hub_detail:"):
            # Hub token detail view
            try:
                parts = callback_data.split(":")
                token_ref = parts[2] if len(parts) > 2 else ""
                address = _resolve_token_ref(context, token_ref)
                sentiment_data = await get_ai_sentiment_for_token(address)
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
                text, keyboard = DemoMenuBuilder.token_analysis_menu(token_data)
            except Exception as e:
                logger.error(f"Hub detail error: {e}")
                text, keyboard = DemoMenuBuilder.error_message(
                    error=str(e),
                    retry_action="demo:hub",
                    context_hint="hub_detail",
                )

        elif data.startswith("demo:hub_custom_sl:"):
            # Custom stop loss presets
            try:
                parts = callback_data.split(":")
                token_ref = parts[2] if len(parts) > 2 else ""
                theme = JarvisTheme
                text = f"""
{theme.WARNING} *CUSTOM STOP LOSS*
━━━━━━━━━━━━━━━━━━━━━━

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
            except Exception as e:
                logger.error(f"Hub custom SL error: {e}")
                text, keyboard = DemoMenuBuilder.error_message(
                    error=str(e),
                    retry_action="demo:hub",
                    context_hint="hub_custom_sl",
                )

        elif data.startswith("demo:hub_exec_buy:"):
            # Execute hub buy with TP/SL
            try:
                parts = callback_data.split(":")
                token_ref = parts[2] if len(parts) > 2 else ""
                address = _resolve_token_ref(context, token_ref)
                amount_sol = float(parts[3]) if len(parts) > 3 else 0.1
                sl_percent = float(parts[4]) if len(parts) > 4 else 15.0

                engine = await _get_demo_engine()
                portfolio = await engine.get_portfolio_value()
                if not portfolio:
                    raise RuntimeError("Portfolio unavailable")
                balance_sol, balance_usd = portfolio
                if balance_sol <= 0:
                    text, keyboard = DemoMenuBuilder.error_message("Treasury balance is zero.")
                    return

                sol_usd = balance_usd / balance_sol if balance_sol > 0 else 0
                amount_usd = amount_sol * sol_usd

                sentiment_data = await get_ai_sentiment_for_token(address)
                signal_name = sentiment_data.get("signal", "NEUTRAL")
                grade = _grade_for_signal_name(signal_name)
                sentiment_score = sentiment_data.get("score", 0) or 0
                token_symbol = sentiment_data.get("symbol", "TOKEN")

                tp_percent = context.user_data.get("hub_tp_percent", 25.0)
                custom_tp = tp_percent / 100.0
                custom_sl = sl_percent / 100.0

                from bots.treasury.trading import TradeDirection
                success, msg, position = await engine.open_position(
                    token_mint=address,
                    token_symbol=token_symbol,
                    direction=TradeDirection.LONG,
                    amount_usd=amount_usd,
                    sentiment_grade=grade,
                    sentiment_score=sentiment_score,
                    custom_tp=custom_tp,
                    custom_sl=custom_sl,
                    user_id=user_id,
                )

                if success and position:
                    text, keyboard = DemoMenuBuilder.success_message(
                        action="Hub Trade Executed",
                        details=(
                            f"Bought {token_symbol} with {amount_sol:.2f} SOL\n"
                            f"TP: +{tp_percent:.0f}% | SL: -{sl_percent:.0f}%\n"
                            f"Position ID: {position.id}"
                        ),
                    )
                else:
                    text, keyboard = DemoMenuBuilder.error_message(
                        error=msg or "Trade failed",
                        retry_action="demo:hub",
                    )
            except Exception as e:
                logger.error(f"Hub exec buy error: {e}")
                text, keyboard = DemoMenuBuilder.error_message(
                    error=str(e),
                    retry_action="demo:hub",
                    context_hint="hub_exec_buy",
                )

        # ========== INSTA SNIPE HANDLERS ==========
        elif action == "insta_snipe":
            # Insta Snipe - Find hottest token from DexScreener
            try:
                # Use DexScreener boosted tokens (most trending)
                hottest_token = None
                try:
                    from core.dexscreener import get_boosted_tokens_with_data
                    boosted = await asyncio.get_event_loop().run_in_executor(
                        None,
                        lambda: get_boosted_tokens_with_data(chain="solana", limit=1, cache_ttl_seconds=60)
                    )
                    if boosted:
                        top = boosted[0]
                        # Calculate conviction from volume/liquidity ratio
                        volume_ratio = top.volume_24h / top.liquidity_usd if top.liquidity_usd > 0 else 0
                        conviction = "VERY HIGH" if volume_ratio > 5 else "HIGH" if volume_ratio > 2 else "MEDIUM"
                        hottest_token = {
                            "symbol": top.base_token_symbol,
                            "address": top.base_token_address,
                            "price": top.price_usd,
                            "change_24h": top.price_change_24h,
                            "volume_24h": top.volume_24h,
                            "liquidity": top.liquidity_usd,
                            "market_cap": 0,  # DexScreener doesn't provide this
                            "conviction": conviction,
                            "sentiment_score": 75,  # Neutral default
                            "entry_timing": "GOOD" if abs(top.price_change_1h) < 10 else "LATE",
                            "sightings": 1,
                        }
                except Exception as api_err:
                    logger.warning(f"DexScreener boosted tokens error: {api_err}")

                # Validate the token payload - avoid UNKNOWN/zeroed data
                if hottest_token:
                    symbol_ok = bool(hottest_token.get("symbol")) and hottest_token.get("symbol") != "UNKNOWN"
                    price_ok = float(hottest_token.get("price", 0) or 0) > 0
                    if not (symbol_ok and price_ok):
                        hottest_token = None

                # Fallback to Bags.fm volume leaders (real tradable tokens)
                if not hottest_token:
                    bags_tokens = await get_bags_top_tokens_with_sentiment(limit=1)
                    if bags_tokens:
                        t = bags_tokens[0]
                        score = float(t.get("sentiment_score", 0.5) or 0.5)
                        conviction_score = int(round(score * 100)) if score <= 1 else int(score)
                        conviction = _conviction_label(conviction_score)
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

                # Fallback to mock data if API fails
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

                hottest_token["token_id"] = _register_token_id(context, hottest_token.get("address"))

                text, keyboard = DemoMenuBuilder.insta_snipe_menu(
                    hottest_token=hottest_token,
                    market_regime=market_regime,
                    auto_sl_percent=15.0,
                    auto_tp_percent=15.0,
                )
            except Exception as e:
                logger.error(f"Insta snipe error: {e}")
                text, keyboard = DemoMenuBuilder.error_message(
                    error=str(e),
                    retry_action="demo:insta_snipe",
                    context_hint="insta_snipe",
                )

        elif data.startswith("demo:snipe_exec:"):
            # Snipe execution - show confirmation
            try:
                parts = callback_data.split(":")
                if len(parts) >= 4:
                    token_ref = parts[2]
                    address = _resolve_token_ref(context, token_ref)
                    amount = float(parts[3])

                    # Store snipe details
                    context.user_data["snipe_address"] = address
                    context.user_data["snipe_token_ref"] = token_ref
                    context.user_data["snipe_amount"] = amount

                    sentiment_data = await get_ai_sentiment_for_token(address)
                    symbol = sentiment_data.get("symbol", "TOKEN")
                    price = float(sentiment_data.get("price", 0) or 0)
                    if price <= 0:
                        price = 0.001
                    context.user_data["snipe_symbol"] = symbol
                    context.user_data["snipe_price"] = price

                    text, keyboard = DemoMenuBuilder.snipe_confirm(
                        symbol=symbol,
                        address=address,
                        amount=amount,
                        price=price,
                        sl_percent=15.0,
                        tp_percent=15.0,
                        token_ref=token_ref,
                    )
                else:
                    text, keyboard = DemoMenuBuilder.error_message(
                        error="Invalid snipe request",
                        retry_action="demo:insta_snipe",
                    )
            except Exception as e:
                logger.error(f"Snipe exec error: {e}")
                text, keyboard = DemoMenuBuilder.error_message(
                    error=str(e),
                    retry_action="demo:insta_snipe",
                    context_hint="snipe_exec",
                )

        elif data.startswith("demo:snipe_confirm:"):
            # Execute the snipe
            try:
                parts = callback_data.split(":")
                if len(parts) >= 4:
                    token_ref = parts[2]
                    address = _resolve_token_ref(context, token_ref)
                    amount = float(parts[3])

                    # Flow controller validation (same as quick buy)
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
                            text, keyboard = DemoMenuBuilder.error_message(
                                f"Trade blocked: {flow_result.hold_reason}"
                            )
                            await query.message.edit_text(
                                text,
                                parse_mode=ParseMode.MARKDOWN,
                                reply_markup=keyboard,
                            )
                            return
                    except ImportError:
                        logger.debug("Flow controller not available, proceeding")
                    except Exception as e:
                        logger.warning(f"Flow validation error (continuing): {e}")

                    # Execute via treasury engine
                    try:
                        engine = await _get_demo_engine()
                        portfolio = await engine.get_portfolio_value()
                        if not portfolio:
                            raise RuntimeError("Portfolio unavailable")
                        balance_sol, balance_usd = portfolio
                        if balance_sol <= 0:
                            text, keyboard = DemoMenuBuilder.error_message("Treasury balance is zero.")
                            return

                        sol_usd = balance_usd / balance_sol if balance_sol > 0 else 0
                        amount_usd = amount * sol_usd

                        sentiment_data = await get_ai_sentiment_for_token(address)
                        token_symbol = sentiment_data.get("symbol", "TOKEN")
                        signal_name = sentiment_data.get("signal", "NEUTRAL")
                        grade = _grade_for_signal_name(signal_name)
                        sentiment_score = sentiment_data.get("score", 0) or 0

                        from bots.treasury.trading import TradeDirection
                        success, msg, position = await engine.open_position(
                            token_mint=address,
                            token_symbol=token_symbol,
                            direction=TradeDirection.LONG,
                            amount_usd=amount_usd,
                            sentiment_grade=grade,
                            sentiment_score=sentiment_score,
                            custom_tp=15.0,
                            custom_sl=15.0,
                            user_id=user_id,
                        )

                        if success and position:
                            text, keyboard = DemoMenuBuilder.snipe_result(
                                success=True,
                                symbol=token_symbol,
                                amount=amount,
                                tx_hash=f"pending_{position.id[:8]}",
                                error=None,
                                sl_set=True,
                                tp_set=True,
                            )
                        else:
                            text, keyboard = DemoMenuBuilder.snipe_result(
                                success=False,
                                symbol=token_symbol,
                                amount=amount,
                                error=msg or "Trade failed",
                            )
                    except Exception as e:
                        logger.error(f"Snipe confirm error: {e}")
                        text, keyboard = DemoMenuBuilder.snipe_result(
                            success=False,
                            symbol="TOKEN",
                            amount=amount,
                            error=str(e),
                        )
                else:
                    text, keyboard = DemoMenuBuilder.error_message(
                        error="Invalid confirmation",
                        retry_action="demo:insta_snipe",
                    )
            except Exception as e:
                logger.error(f"Snipe confirm error: {e}")
                text, keyboard = DemoMenuBuilder.snipe_result(
                    success=False,
                    symbol="TOKEN",
                    amount=0,
                    error=str(e),
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

        elif data.startswith("demo:history_page:"):
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
            # Execute sell all positions with success fee tracking
            theme = JarvisTheme

            # Show loading state (US-032)
            try:
                position_count = len(positions)
                await query.message.edit_text(
                    JarvisTheme.loading_text(f"Processing Sell All ({position_count} positions)"),
                    parse_mode=ParseMode.MARKDOWN,
                )
            except Exception:
                pass  # Continue even if loading message fails

            # =====================================================================
            # FLOW CONTROLLER - Validate sell all action
            # =====================================================================
            try:
                from tg_bot.services.flow_controller import get_flow_controller, FlowDecision

                flow = get_flow_controller()
                flow_result = await flow.process_command(
                    command="sell",
                    args=["all"],
                    user_id=user_id,
                    chat_id=query.message.chat_id,
                    is_admin=True,
                    force_execute=True,  # User clicked confirm
                )

                if flow_result.decision == FlowDecision.HOLD:
                    text, keyboard = DemoMenuBuilder.error_message(
                        f"Sell blocked: {flow_result.hold_reason}"
                    )
                    await query.message.edit_text(
                        text,
                        parse_mode=ParseMode.MARKDOWN,
                        reply_markup=keyboard,
                    )
                    return

                logger.info(f"Flow approved sell all (checks: {flow_result.checks_performed})")
            except ImportError:
                pass
            except Exception as e:
                logger.warning(f"Flow validation error (continuing): {e}")

            try:
                wallet_address = context.user_data.get("wallet_address", "demo_wallet")
                slippage_bps = _get_demo_slippage_bps()

                closed_count = 0
                failed_count = 0
                total_pnl = 0.0
                total_fees = 0.0
                fee_manager = get_success_fee_manager()

                for pos in positions:
                    try:
                        token_address = pos.get("address")
                        token_amount = pos.get("amount", 0)
                        symbol = pos.get("symbol", "???")

                        # Sell via Bags API with Jupiter fallback (Token -> SOL)
                        swap = await _execute_swap_with_fallback(
                            from_token=token_address,
                            to_token="So11111111111111111111111111111111111111112",  # SOL
                            amount=token_amount,
                            wallet_address=wallet_address,
                            slippage_bps=slippage_bps,
                        )

                        if swap.get("success"):
                            closed_count += 1
                            logger.info(
                                f"Sold {symbol} via {swap.get('source', 'bags_fm')}: {swap.get('tx_hash')}"
                            )

                            # Calculate success fee for winning positions
                            pnl_usd = pos.get("pnl_usd", 0)
                            total_pnl += pnl_usd

                            if pnl_usd > 0:
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
                pnl_emoji = "📈" if total_pnl > 0 else "📉" if total_pnl < 0 else "➖"
                pnl_sign = "+" if total_pnl > 0 else ""

                details = f"Sold {closed_count}/{len(positions)} positions via Bags.fm"
                if failed_count > 0:
                    details += f"\n⚠️ {failed_count} failed"
                details += f"\n\n{pnl_emoji} Total P&L: {pnl_sign}${total_pnl:.2f}"

                if total_fees > 0:
                    net_profit = total_pnl - total_fees
                    details += f"\n💰 Success Fee (0.5%): -${total_fees:.4f}"
                    details += f"\n💵 Net Profit: +${net_profit:.2f}"

                text, keyboard = DemoMenuBuilder.success_message(
                    action="Sell All Executed",
                    details=details,
                )

                logger.info(f"Sell all: {closed_count} sold, {failed_count} failed | PnL: ${total_pnl:.2f} | Fees: ${total_fees:.4f}")
            except Exception as e:
                logger.error(f"Sell all error: {e}")
                text, keyboard = DemoMenuBuilder.error_message(f"Sell all failed: {str(e)[:50]}")

        elif action == "snipe_mode":
            # Snipe mode view
            text, keyboard = DemoMenuBuilder.snipe_mode_view()
            context.user_data["snipe_mode"] = True
            context.user_data["snipe_amount"] = 0.1

        elif data.startswith("demo:snipe_amount:"):
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

        elif action == "watchlist":
            # Show watchlist menu
            watchlist = context.user_data.get("watchlist", [])

            # Fetch live prices for watchlist tokens
            if watchlist:
                for token in watchlist:
                    try:
                        address = token.get("address", "")
                        if address:
                            sentiment = await get_ai_sentiment_for_token(address)
                            token["price"] = sentiment.get("price", token.get("price", 0))
                            token["change_24h"] = sentiment.get("change_24h", token.get("change_24h", 0))
                            token["token_id"] = _register_token_id(context, address)
                    except Exception:
                        pass  # Keep existing data

            text, keyboard = DemoMenuBuilder.watchlist_menu(watchlist)

        elif action == "watchlist_add":
            # Prompt to add token
            theme = JarvisTheme
            text = f"""
{theme.GEM} *ADD TO WATCHLIST*
━━━━━━━━━━━━━━━━━━━━━

Paste a Solana token address
to add it to your watchlist.

Example:
`DezXAZ8z7PnrnRJjz3...`

The token will be tracked with
live price updates!
"""
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton(f"{theme.BACK} Cancel", callback_data="demo:watchlist")],
            ])
            context.user_data["awaiting_watchlist_token"] = True

        elif data.startswith("demo:watchlist_remove:"):
            # Remove from watchlist
            parts = data.split(":")
            if len(parts) >= 3:
                try:
                    index = int(parts[2])
                    watchlist = context.user_data.get("watchlist", [])
                    if 0 <= index < len(watchlist):
                        removed = watchlist.pop(index)
                        context.user_data["watchlist"] = watchlist
                        text, keyboard = DemoMenuBuilder.success_message(
                            action="Token Removed",
                            details=f"Removed {removed.get('symbol', 'token')} from watchlist",
                        )
                    else:
                        text, keyboard = DemoMenuBuilder.error_message("Invalid watchlist index")
                except Exception as e:
                    text, keyboard = DemoMenuBuilder.error_message(f"Failed to remove: {e}")
            else:
                text, keyboard = DemoMenuBuilder.error_message("Invalid remove command")

        elif data.startswith("demo:analyze:"):
            # AI Token Analysis
            parts = data.split(":")
            if len(parts) >= 3:
                token_ref = parts[2]
                token_address = _resolve_token_ref(context, token_ref)
                sentiment_data = await get_ai_sentiment_for_token(token_address)
                token_data = {
                    "symbol": sentiment_data.get("symbol", "TOKEN"),
                    "address": token_address,
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
                engine = await _get_demo_engine()
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

        elif data.startswith("demo:buy:"):
            # Handle buy amount selection
            parts = data.split(":")
            if len(parts) >= 3:
                amount = float(parts[2])
                text, keyboard = DemoMenuBuilder.token_input_prompt()
                context.user_data["buy_amount"] = amount
                context.user_data["awaiting_token"] = True

        elif data.startswith("demo:sell:"):
            # Handle sell action via Bags API with success fee calculation
            parts = data.split(":")
            if len(parts) >= 4:
                pos_id = parts[2]
                pct = int(parts[3])

                # Find position
                pos_data = next((p for p in positions if p["id"] == pos_id), None)
                if pos_data:
                    # Show loading state (US-032)
                    try:
                        symbol_preview = safe_symbol(pos_data.get("symbol", "TOKEN"))
                        await query.message.edit_text(
                            JarvisTheme.loading_text(f"Processing Sell Order for {pct}% of {symbol_preview}"),
                            parse_mode=ParseMode.MARKDOWN,
                        )
                    except Exception:
                        pass  # Continue even if loading message fails

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
                        slippage_bps = _get_demo_slippage_bps()

                        swap = await _execute_swap_with_fallback(
                            from_token=token_address,
                            to_token="So11111111111111111111111111111111111111112",  # SOL
                            amount=token_amount,
                            wallet_address=wallet_address,
                            slippage_bps=slippage_bps,
                        )

                        if swap.get("success"):
                            # Calculate success fee if winning trade
                            fee_manager = get_success_fee_manager()
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
                                # Use .get() with fallback to avoid KeyError (Bug Fix US-033)
                                current_amount = pos_data.get("amount", pos_data.get("amount_sol", 0))
                                current_amount_sol = pos_data.get("amount_sol", pos_data.get("amount", 0))
                                pos_data["amount"] = current_amount * (1 - pct / 100)
                                pos_data["amount_sol"] = current_amount_sol * (1 - pct / 100)
                            context.user_data["positions"] = positions

                            text, keyboard = DemoMenuBuilder.close_position_result(
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

                            logger.info(
                                f"Sold {pct}% of {symbol} via {swap.get('source', 'bags_fm')} | "
                                f"PnL: ${pnl_usd:.2f} ({pnl_pct:+.1f}%) | "
                                f"Fee: ${success_fee:.4f} | TX: {swap.get('tx_hash')}"
                            )
                        else:
                            text, keyboard = DemoMenuBuilder.error_message(
                                f"Sell failed: {swap.get('error') or 'Unknown error'}"
                            )
                    except Exception as e:
                        logger.error(f"Sell position error: {e}")
                        text, keyboard = DemoMenuBuilder.error_message(f"Sell failed: {str(e)[:50]}")
                else:
                    text, keyboard = DemoMenuBuilder.error_message("Position not found")

        elif data.startswith("demo:quick_buy:"):
            # Quick buy from trending - with AI sentiment check
            parts = data.split(":")
            if len(parts) >= 3:
                token_ref = parts[2]
                token_addr = _resolve_token_ref(context, token_ref)
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
                        InlineKeyboardButton(f"{theme.SUCCESS} Confirm Buy", callback_data=f"demo:execute_buy:{token_ref}:{amount}"),
                    ],
                    [
                        InlineKeyboardButton(f"{theme.CHART} More Analysis", callback_data=f"demo:analyze:{token_ref}"),
                    ],
                    [
                        InlineKeyboardButton(f"{theme.CLOSE} Cancel", callback_data="demo:main"),
                    ],
                ])

        elif data.startswith("demo:execute_buy:"):
            # Actually execute the buy order
            parts = data.split(":")
            if len(parts) >= 4:
                token_ref = parts[2]
                token_addr = _resolve_token_ref(context, token_ref)
                amount = float(parts[3])

                # Show loading state (US-032)
                try:
                    await query.message.edit_text(
                        JarvisTheme.loading_text(f"Processing Buy Order for {amount:.2f} SOL"),
                        parse_mode=ParseMode.MARKDOWN,
                    )
                except Exception:
                    pass  # Continue even if loading message fails

                # =====================================================================
                # FLOW CONTROLLER - Validate action before execution
                # =====================================================================
                try:
                    from tg_bot.services.flow_controller import get_flow_controller, FlowDecision

                    flow = get_flow_controller()
                    flow_result = await flow.process_command(
                        command="buy",
                        args=[token_addr, str(amount)],
                        user_id=user_id,
                        chat_id=query.message.chat_id,
                        is_admin=True,  # Demo is admin-only
                        force_execute=True,  # User already clicked confirm button
                    )

                    if flow_result.decision == FlowDecision.HOLD:
                        text, keyboard = DemoMenuBuilder.error_message(
                            f"Trade blocked: {flow_result.hold_reason}"
                        )
                        await query.message.edit_text(
                            text,
                            parse_mode=ParseMode.MARKDOWN,
                            reply_markup=keyboard,
                        )
                        return

                    logger.info(
                        f"Flow approved buy: {token_addr[:8]}... for {amount} SOL "
                        f"(checks: {flow_result.checks_performed})"
                    )
                except ImportError:
                    logger.debug("Flow controller not available, proceeding")
                except Exception as e:
                    logger.warning(f"Flow validation error (continuing): {e}")

                # Execute via Bags.fm API with Jupiter fallback
                try:
                    sentiment_data = await get_ai_sentiment_for_token(token_addr)
                    token_symbol = sentiment_data.get("symbol", "TOKEN")
                    token_price = sentiment_data.get("price", 0) or 0

                    wallet_address = context.user_data.get("wallet_address", "demo_wallet")
                    slippage_bps = _get_demo_slippage_bps()

                    swap = await _execute_swap_with_fallback(
                        from_token="So11111111111111111111111111111111111111112",  # SOL
                        to_token=token_addr,
                        amount=amount,
                        wallet_address=wallet_address,
                        slippage_bps=slippage_bps,
                    )

                    if swap.get("success"):
                        tokens_received = swap.get("amount_out") if swap.get("amount_out") else (
                            (amount * 225 / token_price) if token_price > 0 else 0
                        )

                        # Add position to portfolio
                        positions = context.user_data.get("positions", [])
                        # Default TP/SL values (US-005 requirement: 50% TP, 20% SL)
                        default_tp_pct = 50.0
                        default_sl_pct = 20.0
                        new_position = {
                            "id": f"buy_{len(positions) + 1}",
                            "symbol": token_symbol,
                            "address": token_addr,
                            "amount": tokens_received,
                            "amount_sol": amount,
                            "entry_price": token_price,
                            "current_price": token_price,
                            "tp_percent": default_tp_pct,
                            "sl_percent": default_sl_pct,
                            "tp_price": token_price * (1 + default_tp_pct / 100),
                            "sl_price": token_price * (1 - default_sl_pct / 100),
                            "source": swap.get("source", "bags_api"),
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "tx_hash": swap.get("tx_hash"),
                        }
                        positions.append(new_position)
                        context.user_data["positions"] = positions

                        tx_hash = swap.get("tx_hash")
                        tx_display = f"{tx_hash[:8]}...{tx_hash[-8:]}" if tx_hash else "N/A"

                        text, keyboard = DemoMenuBuilder.success_message(
                            action=(
                                "Buy Order Executed via Bags.fm"
                                if swap.get("source") == "bags_fm"
                                else "Buy Order Executed via Jupiter"
                            ),
                            details=(
                                f"Bought {token_symbol} with {amount:.2f} SOL\n"
                                f"Received: {tokens_received:,.0f} {token_symbol}\n"
                                f"Entry: ${token_price:.8f}\n"
                                f"TX: {tx_display}\n\n"
                                "Check /positions to monitor."
                            ),
                        )
                    else:
                        text, keyboard = DemoMenuBuilder.error_message(
                            f"Swap failed: {swap.get('error') or 'Unknown error'}"
                        )
                except Exception as e:
                    logger.error(f"Bags API buy execution failed: {e}")
                    text, keyboard = DemoMenuBuilder.error_message(f"Buy failed: {str(e)[:50]}")

        # =====================================================================
        # TP/SL Adjustment Handlers (Bug Fix US-033)
        # =====================================================================

        elif data.startswith("demo:adj_tp:"):
            # Adjust take-profit percentage: demo:adj_tp:pos_id:delta
            parts = data.split(":")
            if len(parts) >= 4:
                pos_id = parts[2]
                delta = float(parts[3])

                positions = context.user_data.get("positions", [])
                pos = next((p for p in positions if p.get("id") == pos_id), None)

                if pos:
                    current_tp = pos.get("tp_percent", 50.0)
                    new_tp = max(5.0, min(200.0, current_tp + delta))  # Clamp 5-200%
                    pos["tp_percent"] = new_tp

                    entry_price = pos.get("entry_price", 0)
                    if entry_price > 0:
                        pos["tp_price"] = entry_price * (1 + new_tp / 100)

                    context.user_data["positions"] = positions

                    symbol = safe_symbol(pos.get("symbol", "TOKEN"))
                    sl_pct = pos.get("sl_percent", 20.0)

                    text = f"""
{JarvisTheme.SETTINGS} *ADJUST TP/SL*
{JarvisTheme.COIN} *{symbol}*
-
:
{JarvisTheme.SNIPE} Take Profit: *+{new_tp:.0f}%*
{JarvisTheme.ERROR} Stop Loss: *-{sl_pct:.0f}%*

_Use buttons to adjust_
"""
                    keyboard = InlineKeyboardMarkup([
                        [
                            InlineKeyboardButton("-10%", callback_data=f"demo:adj_tp:{pos_id}:-10"),
                            InlineKeyboardButton("-5%", callback_data=f"demo:adj_tp:{pos_id}:-5"),
                            InlineKeyboardButton(f"TP +{new_tp:.0f}%", callback_data=f"demo:adj_tp:{pos_id}:0"),
                            InlineKeyboardButton("+5%", callback_data=f"demo:adj_tp:{pos_id}:5"),
                            InlineKeyboardButton("+10%", callback_data=f"demo:adj_tp:{pos_id}:10"),
                        ],
                        [
                            InlineKeyboardButton("-10%", callback_data=f"demo:adj_sl:{pos_id}:-10"),
                            InlineKeyboardButton("-5%", callback_data=f"demo:adj_sl:{pos_id}:-5"),
                            InlineKeyboardButton(f"SL -{sl_pct:.0f}%", callback_data=f"demo:adj_sl:{pos_id}:0"),
                            InlineKeyboardButton("+5%", callback_data=f"demo:adj_sl:{pos_id}:5"),
                            InlineKeyboardButton("+10%", callback_data=f"demo:adj_sl:{pos_id}:10"),
                        ],
                        [
                            InlineKeyboardButton(f"{JarvisTheme.SUCCESS} Save", callback_data=f"demo:adj_save:{pos_id}"),
                            InlineKeyboardButton(f"{JarvisTheme.CLOSE} Cancel", callback_data="demo:adj_cancel"),
                        ],
                    ])
                else:
                    text, keyboard = DemoMenuBuilder.error_message("Position not found")

        elif data.startswith("demo:adj_sl:"):
            # Adjust stop-loss percentage: demo:adj_sl:pos_id:delta
            parts = data.split(":")
            if len(parts) >= 4:
                pos_id = parts[2]
                delta = float(parts[3])

                positions = context.user_data.get("positions", [])
                pos = next((p for p in positions if p.get("id") == pos_id), None)

                if pos:
                    current_sl = pos.get("sl_percent", 20.0)
                    new_sl = max(5.0, min(100.0, current_sl + delta))  # Clamp 5-100%
                    pos["sl_percent"] = new_sl

                    entry_price = pos.get("entry_price", 0)
                    if entry_price > 0:
                        pos["sl_price"] = entry_price * (1 - new_sl / 100)

                    context.user_data["positions"] = positions

                    symbol = safe_symbol(pos.get("symbol", "TOKEN"))
                    tp_pct = pos.get("tp_percent", 50.0)

                    text = f"""
{JarvisTheme.SETTINGS} *ADJUST TP/SL*
{JarvisTheme.COIN} *{symbol}*
-
:
{JarvisTheme.SNIPE} Take Profit: *+{tp_pct:.0f}%*
{JarvisTheme.ERROR} Stop Loss: *-{new_sl:.0f}%*

_Use buttons to adjust_
"""
                    keyboard = InlineKeyboardMarkup([
                        [
                            InlineKeyboardButton("-10%", callback_data=f"demo:adj_tp:{pos_id}:-10"),
                            InlineKeyboardButton("-5%", callback_data=f"demo:adj_tp:{pos_id}:-5"),
                            InlineKeyboardButton(f"TP +{tp_pct:.0f}%", callback_data=f"demo:adj_tp:{pos_id}:0"),
                            InlineKeyboardButton("+5%", callback_data=f"demo:adj_tp:{pos_id}:5"),
                            InlineKeyboardButton("+10%", callback_data=f"demo:adj_tp:{pos_id}:10"),
                        ],
                        [
                            InlineKeyboardButton("-10%", callback_data=f"demo:adj_sl:{pos_id}:-10"),
                            InlineKeyboardButton("-5%", callback_data=f"demo:adj_sl:{pos_id}:-5"),
                            InlineKeyboardButton(f"SL -{new_sl:.0f}%", callback_data=f"demo:adj_sl:{pos_id}:0"),
                            InlineKeyboardButton("+5%", callback_data=f"demo:adj_sl:{pos_id}:5"),
                            InlineKeyboardButton("+10%", callback_data=f"demo:adj_sl:{pos_id}:10"),
                        ],
                        [
                            InlineKeyboardButton(f"{JarvisTheme.SUCCESS} Save", callback_data=f"demo:adj_save:{pos_id}"),
                            InlineKeyboardButton(f"{JarvisTheme.CLOSE} Cancel", callback_data="demo:adj_cancel"),
                        ],
                    ])
                else:
                    text, keyboard = DemoMenuBuilder.error_message("Position not found")

        elif data.startswith("demo:adj_save:"):
            # Save TP/SL adjustments: demo:adj_save:pos_id
            parts = data.split(":")
            pos_id = parts[2] if len(parts) > 2 else ""

            positions = context.user_data.get("positions", [])
            pos = next((p for p in positions if p.get("id") == pos_id), None)

            if pos:
                symbol = safe_symbol(pos.get("symbol", "TOKEN"))
                tp_pct = pos.get("tp_percent", 50.0)
                sl_pct = pos.get("sl_percent", 20.0)

                text, keyboard = DemoMenuBuilder.success_message(
                    action="TP/SL Updated",
                    details=f"*{symbol}*\nTake Profit: +{tp_pct:.0f}%\nStop Loss: -{sl_pct:.0f}%",
                )
            else:
                text, keyboard = DemoMenuBuilder.error_message("Position not found")

        elif action == "adj_cancel":
            # Cancel TP/SL adjustment - return to positions
            text, keyboard = DemoMenuBuilder.positions_menu(
                positions=context.user_data.get("positions", []),
            )

        # =====================================================================
        # Chart Handler (US-007)
        # =====================================================================

        elif data.startswith("demo:chart:"):
            # Generate and send chart: demo:chart:token_ref:interval
            parts = data.split(":")
            token_ref = parts[2] if len(parts) > 2 else ""
            interval = parts[3] if len(parts) > 3 else "1h"

            token_addr = _resolve_token_ref(context, token_ref)
            sentiment_data = await get_ai_sentiment_for_token(token_addr)
            token_symbol = sentiment_data.get("symbol", "TOKEN")

            # Show loading state
            try:
                await query.message.edit_text(
                    JarvisTheme.loading_text(f"Generating {token_symbol} chart"),
                    parse_mode=ParseMode.MARKDOWN,
                )
            except Exception:
                pass

            # Generate chart
            try:
                from tg_bot.handlers.demo_charts import handle_chart_callback

                success, result = await handle_chart_callback(
                    token_mint=token_addr,
                    token_symbol=token_symbol,
                    interval=interval,
                )

                if success:
                    # Send chart as photo
                    await context.bot.send_photo(
                        chat_id=query.message.chat_id,
                        photo=result,
                        caption=f"{JarvisTheme.CHART} *{safe_symbol(token_symbol)}* Price Chart ({interval})",
                        parse_mode=ParseMode.MARKDOWN,
                    )
                    text = f"{JarvisTheme.SUCCESS} Chart generated for *{safe_symbol(token_symbol)}*"
                    keyboard = InlineKeyboardMarkup([
                        [
                            InlineKeyboardButton("1h", callback_data=f"demo:chart:{token_ref}:1h"),
                            InlineKeyboardButton("4h", callback_data=f"demo:chart:{token_ref}:4h"),
                            InlineKeyboardButton("1d", callback_data=f"demo:chart:{token_ref}:1d"),
                        ],
                        [
                            InlineKeyboardButton(f"{JarvisTheme.BACK} Back", callback_data="demo:main"),
                        ],
                    ])
                else:
                    text, keyboard = DemoMenuBuilder.error_message(result)
            except ImportError:
                text, keyboard = DemoMenuBuilder.error_message(
                    "Chart feature requires mplfinance. Install with: pip install mplfinance pandas"
                )
            except Exception as e:
                logger.error(f"Chart generation error: {e}")
                text, keyboard = DemoMenuBuilder.error_message(f"Chart failed: {str(e)[:50]}")

        # =====================================================================
        # Custom Buy Amount Handler (US-031)
        # =====================================================================

        elif data.startswith("demo:buy_custom:"):
            # Show custom amount input prompt: demo:buy_custom:token_ref
            parts = data.split(":")
            token_ref = parts[2] if len(parts) > 2 else ""

            # Store state for message handler
            context.user_data["awaiting_custom_buy_amount"] = True
            context.user_data["custom_buy_token_ref"] = token_ref

            text = f"""
{JarvisTheme.BUY} *CUSTOM BUY AMOUNT*

Enter the amount of SOL you want to spend:

*Limits:*
- Minimum: 0.01 SOL
- Maximum: 50 SOL

_Send a number like "0.5" or "2.5"_
"""
            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(f"{JarvisTheme.CLOSE} Cancel", callback_data="demo:main"),
                ],
            ])

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
                ai_auto_enabled=ai_auto_enabled,
            )

        # Edit the message with new content
        try:
            await query.message.edit_text(
                text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=keyboard,
            )
        except BadRequest as e:
            if "Message is not modified" not in str(e):
                raise

    except Exception as e:
        # Track error for automatic fixing
        from core.logging.error_tracker import error_tracker
        error_id = error_tracker.track_error(
            e,
            context=f"demo_callback action={action}",
            component="telegram_demo",
            metadata={"action": action, "callback_data": data}
        )
        logger.error(f"Demo callback error [{error_id}]: action={action}, error={e}", exc_info=True)

        text, keyboard = DemoMenuBuilder.error_message(
            error=str(e)[:100],
            retry_action=f"demo:{action}",
            context_hint=f"Error ID: {error_id}"
        )
        try:
            await query.message.edit_text(
                text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=keyboard,
            )
        except Exception as edit_err:
            logger.error(f"Failed to edit message after error: {edit_err}")


# =============================================================================
# Message Handler for Token Input
# =============================================================================

def validate_buy_amount(amount: float) -> tuple:
    """
    Validate custom buy amount for US-031.

    Args:
        amount: SOL amount to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    if amount < 0.01:
        return False, "Minimum buy amount is 0.01 SOL"
    if amount > 50:
        return False, "Maximum buy amount is 50 SOL"
    return True, ""


@error_handler
async def demo_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle text messages when awaiting token input or watchlist add."""
    # PTB can invoke handlers for updates where `update.message` is None (e.g., edited messages,
    # service updates, etc.). Guard so we don't crash on `.text`.
    msg = update.effective_message or update.message
    if not msg or not getattr(msg, "text", None):
        return

    text = msg.text.strip()

    # Enforce admin-only demo access
    try:
        config = get_config()
        user_id = msg.from_user.id if msg and msg.from_user else 0
        username = msg.from_user.username if msg and msg.from_user else None
        try:
            is_admin = config.is_admin(user_id, username)
        except TypeError:
            is_admin = config.is_admin(user_id)
        if not is_admin:
            await msg.reply_text("Unauthorized: Demo is admin-only.")
            logger.warning(f"Unauthorized demo message by user {user_id} (@{username})")
            return
    except Exception as exc:
        logger.warning(f"Demo message admin check failed: {exc}")

    # Run TP/SL/trailing stop checks for demo positions (throttled)
    await _process_demo_exit_checks(update, context)

    # Early return if not awaiting any demo input - let message pass to other handlers
    if not any([
        context.user_data.get("awaiting_custom_buy_amount"),
        context.user_data.get("awaiting_watchlist_token"),
        context.user_data.get("awaiting_wallet_import"),
        context.user_data.get("awaiting_token"),
        context.user_data.get("awaiting_token_search"),
    ]):
        return

    # =========================================================================
    # Handle Custom Buy Amount Input (US-031)
    # =========================================================================
    if context.user_data.get("awaiting_custom_buy_amount"):
        context.user_data["awaiting_custom_buy_amount"] = False
        token_ref = context.user_data.pop("custom_buy_token_ref", "")

        try:
            amount = float(text)
            is_valid, error_msg = validate_buy_amount(amount)

            if not is_valid:
                error_text, keyboard = DemoMenuBuilder.error_message(error_msg)
                await update.message.reply_text(
                    error_text,
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=keyboard,
                )
                return

            # Build buy confirmation
            token_addr = _resolve_token_ref(context, token_ref)
            sentiment_data = await get_ai_sentiment_for_token(token_addr)
            token_symbol = sentiment_data.get("symbol", "TOKEN")
            token_price = sentiment_data.get("price", 0) or 0
            sentiment = sentiment_data.get("sentiment", "neutral")
            score = sentiment_data.get("score", 0)
            signal = sentiment_data.get("signal", "NEUTRAL")

            theme = JarvisTheme
            sent_emoji = {"bullish": "g", "bearish": "r", "very_bullish": "rkt"}.get(
                sentiment.lower(), "y"
            )
            sig_emoji = {"STRONG_BUY": "fire", "BUY": "g", "SELL": "r"}.get(signal, "y")

            confirm_text = f"""
{theme.BUY} *CONFIRM CUSTOM BUY*

*Token:* {safe_symbol(token_symbol)}
*Amount:* {amount} SOL
*Est. Price:* ${token_price:.8f}

{theme.AUTO} *AI Analysis*
- Sentiment: *{sentiment.upper()}*
- Score: *{score:.2f}*
- Signal: *{signal}*

_Tap Confirm to execute_
"""
            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        f"{theme.SUCCESS} Confirm Buy",
                        callback_data=f"demo:execute_buy:{token_ref}:{amount}"
                    ),
                ],
                [
                    InlineKeyboardButton(
                        f"{theme.CLOSE} Cancel",
                        callback_data="demo:main"
                    ),
                ],
            ])

            await update.message.reply_text(
                confirm_text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=keyboard,
            )
        except ValueError:
            error_text, keyboard = DemoMenuBuilder.error_message(
                "Invalid amount. Please enter a number like 0.5 or 2.5"
            )
            await update.message.reply_text(
                error_text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=keyboard,
            )
        except Exception as e:
            logger.error(f"Custom buy amount error: {e}")
            error_text, keyboard = DemoMenuBuilder.error_message(
                f"Error: {str(e)[:50]}"
            )
            await update.message.reply_text(
                error_text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=keyboard,
            )
        return

    # Handle watchlist token addition
    if context.user_data.get("awaiting_watchlist_token"):
        context.user_data["awaiting_watchlist_token"] = False

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

        # Get token info
        try:
            sentiment = await get_ai_sentiment_for_token(text)
            token_data = {
                "symbol": sentiment.get("symbol", "TOKEN"),
                "address": text,
                "price": sentiment.get("price", 0),
                "change_24h": sentiment.get("change_24h", 0),
            }
            token_data["token_id"] = _register_token_id(context, text)

            # Add to watchlist
            watchlist = context.user_data.get("watchlist", [])

            # Check for duplicates
            if any(t.get("address") == text for t in watchlist):
                error_text, keyboard = DemoMenuBuilder.error_message(
                    "Token already in watchlist"
                )
                await update.message.reply_text(
                    error_text,
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=keyboard,
                )
                return

            watchlist.append(token_data)
            context.user_data["watchlist"] = watchlist

            success_text, keyboard = DemoMenuBuilder.success_message(
                action="Token Added",
                details=f"Added {token_data['symbol']} to your watchlist!\n\nCurrent price: ${token_data['price']:.6f}",
            )
            await update.message.reply_text(
                success_text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=keyboard,
            )
        except Exception as e:
            error_text, keyboard = DemoMenuBuilder.error_message(
                f"Failed to add token: {str(e)[:50]}"
            )
            await update.message.reply_text(
                error_text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=keyboard,
            )
        return

    # Handle wallet import input
    if context.user_data.get("awaiting_wallet_import"):
        context.user_data["awaiting_wallet_import"] = False
        import_mode = context.user_data.get("import_mode", "key")

        try:
            from bots.treasury.wallet import SecureWallet
            from core.wallet_service import WalletService

            wallet_password = _get_demo_wallet_password()
            if not wallet_password:
                raise ValueError("Demo wallet password not configured")

            wallet_service = WalletService()
            private_key = None

            if import_mode == "seed":
                # Import from seed phrase
                words = text.strip().split()
                if len(words) not in [12, 24]:
                    raise ValueError(f"Seed phrase must be 12 or 24 words, got {len(words)}")
                wallet_data, _ = await wallet_service.import_wallet(
                    seed_phrase=text.strip(),
                    user_password=wallet_password,
                )
                private_key = wallet_data.private_key
            else:
                # Import from private key
                if len(text.strip()) < 64:
                    raise ValueError("Private key too short (min 64 chars)")
                wallet_data, _ = await wallet_service.import_from_private_key(
                    private_key=text.strip(),
                    user_password=wallet_password,
                )
                private_key = wallet_data.private_key

            secure_wallet = SecureWallet(
                master_password=wallet_password,
                wallet_dir=_get_demo_wallet_dir(),
            )
            wallet_info = secure_wallet.import_wallet(private_key, label="Demo Imported")
            wallet_address = wallet_info.address

            result_text, keyboard = DemoMenuBuilder.wallet_import_result(
                success=True,
                wallet_address=wallet_address,
            )
            logger.info(f"Wallet imported: {wallet_address[:8]}...")

        except Exception as e:
            logger.error(f"Wallet import failed: {e}")
            result_text, keyboard = DemoMenuBuilder.wallet_import_result(
                success=False,
                error=str(e)[:100],
            )

        await update.message.reply_text(
            result_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard,
        )
        return

    # Handle buy token input
    if not context.user_data.get("awaiting_token"):
        return

    # Clear the flag
    context.user_data["awaiting_token"] = False

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
    token_ref = _register_token_id(context, text)

    # Show buy confirmation
    confirm_text, keyboard = DemoMenuBuilder.buy_confirmation(
        token_symbol="TOKEN",
        token_address=text,
        amount_sol=amount,
        estimated_tokens=1000000,  # Would be calculated from price
        price_usd=0.00001,  # Would be fetched from DEX
        token_ref=token_ref,
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
