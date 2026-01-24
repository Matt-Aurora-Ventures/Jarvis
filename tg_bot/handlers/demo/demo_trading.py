"""
Demo Bot - Trading Execution Module

Contains:
- Swap execution with Bags.fm/Jupiter fallback
- Buy with TP/SL execution
- Wallet and Jupiter client management
- Token decimals/price utilities
"""

import os
import logging
from pathlib import Path
from typing import Any, Dict, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Profile configuration
DEMO_PROFILE = (os.environ.get("DEMO_TRADING_PROFILE", "demo") or "demo").strip().lower()
DEMO_DEFAULT_SLIPPAGE_BPS = 100  # 1% default


# =============================================================================
# Lazy-loaded Clients
# =============================================================================

_JUPITER_CLIENT = None


def _get_jupiter_client():
    """Lazy Jupiter client init for fallback swaps."""
    global _JUPITER_CLIENT
    if _JUPITER_CLIENT is None:
        from bots.treasury.jupiter import JupiterClient
        _JUPITER_CLIENT = JupiterClient()
    return _JUPITER_CLIENT


def get_bags_client():
    """Get Bags.fm API client for trading."""
    try:
        from core.trading.bags_client import get_bags_client as _get_bags
        return _get_bags(profile=DEMO_PROFILE)
    except ImportError:
        logger.warning("Bags client not available")
        return None


def get_trade_intelligence():
    """Get trade intelligence engine for self-improvement."""
    try:
        from core.trade_intelligence import get_intelligence_engine
        return get_intelligence_engine()
    except ImportError:
        logger.warning("Trade intelligence not available")
        return None


def get_success_fee_manager():
    """Get Success Fee Manager for 0.5% fee on winning trades."""
    try:
        from core.trading.bags_client import get_success_fee_manager as _get_fee_manager
        return _get_fee_manager(profile=DEMO_PROFILE)
    except ImportError:
        logger.warning("Success fee manager not available")
        return None


# =============================================================================
# Wallet Configuration
# =============================================================================

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
    root = Path(__file__).resolve().parents[3]
    return root / "bots" / "treasury" / f".wallets-{DEMO_PROFILE}"


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


# =============================================================================
# Slippage Configuration
# =============================================================================

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


# =============================================================================
# Token Utilities
# =============================================================================

async def _get_token_decimals(mint: str, jupiter) -> int:
    """Get token decimals for a mint address."""
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
    """Convert human-readable amount to base units."""
    decimals = await _get_token_decimals(mint, jupiter)
    return int(float(amount) * (10 ** decimals))


async def _from_base_units(mint: str, amount: int, jupiter) -> float:
    """Convert base units to human-readable amount."""
    decimals = await _get_token_decimals(mint, jupiter)
    return float(amount) / (10 ** decimals)


# =============================================================================
# Demo Engine
# =============================================================================

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
# Swap Execution
# =============================================================================

async def _execute_swap_with_fallback(
    *,
    from_token: str,
    to_token: str,
    amount: float,
    wallet_address: str,
    slippage_bps: int,
) -> Dict[str, Any]:
    """
    Execute swap via Bags.fm with Jupiter fallback.

    Args:
        from_token: Input token mint address
        to_token: Output token mint address
        amount: Amount of input token (human-readable)
        wallet_address: User's wallet address
        slippage_bps: Slippage tolerance in basis points

    Returns:
        Dict with success/error status and transaction details
    """
    last_error = None

    # Try Bags.fm first
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


# =============================================================================
# Buy with TP/SL
# =============================================================================

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
    """
    import uuid
    from tg_bot.handlers.demo.demo_sentiment import get_ai_sentiment_for_token

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


# =============================================================================
# Buy Amount Validation
# =============================================================================

def validate_buy_amount(amount: float) -> tuple:
    """
    Validate custom buy amount.

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
