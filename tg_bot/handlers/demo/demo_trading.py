"""
Demo Bot - Trading Execution Module

Contains:
- Swap execution with Bags.fm/Jupiter fallback
- Buy with TP/SL execution
- Wallet and Jupiter client management
- Token decimals/price utilities

Integrates with:
- Circuit breakers for endpoint protection
- Error handlers for user-friendly error messages
"""

import os
import asyncio
import hashlib
import logging
import random
from pathlib import Path
from typing import Any, Dict, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Profile configuration
DEMO_PROFILE = (os.environ.get("DEMO_TRADING_PROFILE", "demo") or "demo").strip().lower()
DEMO_DEFAULT_SLIPPAGE_BPS = 100  # 1% default

# Import circuit breaker and error handler for enhanced error handling
try:
    from core.solana.circuit_breaker import (
        RPCCircuitBreaker,
        CircuitOpenError,
        get_rpc_circuit_breaker,
    )
    CIRCUIT_BREAKER_AVAILABLE = True
except ImportError:
    CIRCUIT_BREAKER_AVAILABLE = False
    RPCCircuitBreaker = None
    CircuitOpenError = Exception
    get_rpc_circuit_breaker = None

try:
    from core.solana.error_handler import (
        RPCErrorHandler,
        ErrorCategory,
        get_rpc_error_handler,
    )
    ERROR_HANDLER_AVAILABLE = True
except ImportError:
    ERROR_HANDLER_AVAILABLE = False
    RPCErrorHandler = None
    ErrorCategory = None
    get_rpc_error_handler = None

# Import config for Jupiter settings
try:
    from core.config import load_config
    CONFIG_AVAILABLE = True
except ImportError:
    CONFIG_AVAILABLE = False
    load_config = None

# Initialize demo trading circuit breaker
_DEMO_CIRCUIT_BREAKER = None
_DEMO_ERROR_HANDLER = None


def _get_demo_circuit_breaker():
    """Get or create circuit breaker for demo trading."""
    global _DEMO_CIRCUIT_BREAKER
    if CIRCUIT_BREAKER_AVAILABLE and _DEMO_CIRCUIT_BREAKER is None:
        _DEMO_CIRCUIT_BREAKER = get_rpc_circuit_breaker(
            "demo_trading",
            failure_threshold=5,
            recovery_timeout=60.0,
        )
    return _DEMO_CIRCUIT_BREAKER


def _get_demo_error_handler():
    """Get or create error handler for demo trading."""
    global _DEMO_ERROR_HANDLER
    if ERROR_HANDLER_AVAILABLE and _DEMO_ERROR_HANDLER is None:
        _DEMO_ERROR_HANDLER = get_rpc_error_handler()
    return _DEMO_ERROR_HANDLER


# =============================================================================
# Error Classes (User-Friendly)
# =============================================================================

class TradingError(Exception):
    """Base exception for user-friendly trading errors."""

    def __init__(self, message: str, hint: Optional[str] = None):
        self.message = message
        self.hint = hint
        super().__init__(message)

    def format_telegram(self) -> str:
        """Format error for Telegram display."""
        msg = f"❌ {self.message}"
        if self.hint:
            msg += f"\n\n💡 Hint: {self.hint}"
        return msg


class BagsAPIError(TradingError):
    """bags.fm API error with user-friendly messaging."""
    pass


class TPSLValidationError(TradingError):
    """TP/SL validation error with helpful hints."""
    pass


class InsufficientBalanceError(TradingError):
    """Insufficient balance for trade."""
    pass


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
# Token ID Helpers (callback-safe token references)
# =============================================================================

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
    """Resolve short token id back to full address.
    
    Raises ValueError if resolution fails (prevents sending garbage to APIs).
    """
    if not token_ref:
        raise ValueError("Empty token reference")
    
    # Already a full Solana address (32-44 base58 chars)
    if len(token_ref) >= 32:
        return token_ref
    
    # Try to resolve from session map
    resolved = context.user_data.get("token_id_map", {}).get(token_ref)
    if resolved and len(resolved) >= 32:
        return resolved
    
    # Resolution failed - don't pass garbage to APIs
    logger.warning(f"Token ref '{token_ref}' not found in session map (may have expired). User should re-select token.")
    raise ValueError(
        f"Token session expired. Please go back to Trending or AI Picks and select the token again."
    )


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

    Integrates with:
    - Circuit breaker to prevent cascading failures
    - Error handler for user-friendly error messages

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

    # Check circuit breaker before execution
    circuit_breaker = _get_demo_circuit_breaker()
    if circuit_breaker and not circuit_breaker.allow_request():
        remaining = circuit_breaker.get_remaining_timeout()
        return {
            "success": False,
            "error": f"Trading temporarily paused due to recent failures. Please retry in {remaining:.0f} seconds.",
        }

    async def _retry_async(fn, attempts: int = 3, base_delay: float = 0.5):
        """Retry helper with exponential backoff and jitter."""
        for attempt in range(1, attempts + 1):
            try:
                return await fn()
            except Exception as exc:
                if attempt >= attempts:
                    raise
                delay = base_delay * (2 ** (attempt - 1))
                delay += random.uniform(0, base_delay / 4)
                logger.warning(
                    "Swap attempt %s/%s failed: %s (retrying in %.2fs)",
                    attempt,
                    attempts,
                    exc,
                    delay,
                )
                await asyncio.sleep(delay)

    # Try Bags.fm first
    bags_client = get_bags_client()
    if bags_client and getattr(bags_client, "api_key", None) and getattr(bags_client, "partner_key", None):
        async def _bags_swap():
            return await bags_client.swap(
                from_token=from_token,
                to_token=to_token,
                amount=amount,
                wallet_address=wallet_address,
                slippage_bps=slippage_bps,
            )

        try:
            bags_result = await _retry_async(_bags_swap)
            if bags_result and bags_result.success:
                # Record success with circuit breaker
                if circuit_breaker:
                    circuit_breaker.record_success()
                return {
                    "success": True,
                    "source": "bags_fm",
                    "tx_hash": bags_result.tx_hash,
                    "amount_out": bags_result.to_amount,
                }
            last_error = getattr(bags_result, "error", None) or "Bags.fm swap failed"
        except Exception as exc:
            last_error = str(exc)

            # Check for specific HTTP errors from bags.fm
            try:
                import httpx
                if isinstance(exc, httpx.HTTPStatusError):
                    status = exc.response.status_code
                    if status == 401 or status == 403:
                        raise BagsAPIError(
                            "bags.fm API authentication failed",
                            hint="API key may be invalid or expired. Check BAGS_API_KEY and BAGS_PARTNER_KEY in settings"
                        )
                    elif status >= 500:
                        logger.warning(f"bags.fm server error {status}, falling back to Jupiter: {exc}")
                        # Continue to Jupiter fallback
                    elif status == 429:
                        logger.warning(f"bags.fm rate limit exceeded, falling back to Jupiter")
                        # Continue to Jupiter fallback
            except ImportError:
                # httpx not available, continue with fallback
                pass

            # Log technical details for debugging
            logger.info(f"⚠️ bags.fm unavailable, falling back to Jupiter: {exc}")

    # Jupiter fallback
    logger.info("⚙️ Attempting Jupiter fallback for trade execution")
    try:
        jupiter = _get_jupiter_client()
        wallet = _load_demo_wallet(wallet_address)
        if not wallet:
            raise BagsAPIError(
                "Trade execution failed - wallet not configured",
                hint="Both bags.fm and Jupiter fallback require wallet setup. Contact admin."
            )

        amount_base = await _to_base_units(from_token, amount, jupiter)

        async def _get_quote():
            return await jupiter.get_quote(
                input_mint=from_token,
                output_mint=to_token,
                amount=amount_base,
                slippage_bps=slippage_bps,
            )

        quote = await _retry_async(_get_quote)
        if not quote:
            raise BagsAPIError(
                "Trade execution failed - unable to get price quote",
                hint=f"Both bags.fm and Jupiter could not provide a quote. Original error: {last_error or 'Unknown'}"
            )

        async def _execute_swap():
            return await jupiter.execute_swap(quote, wallet)

        jup_result = await _retry_async(_execute_swap)
        if jup_result and getattr(jup_result, "success", False):
            # Record success with circuit breaker
            if circuit_breaker:
                circuit_breaker.record_success()

            amount_out_ui = await _from_base_units(
                to_token,
                getattr(jup_result, "output_amount", 0),
                jupiter,
            )
            logger.info("Trade executed successfully via Jupiter fallback")
            return {
                "success": True,
                "source": "jupiter",
                "tx_hash": getattr(jup_result, "signature", None),
                "amount_out": amount_out_ui,
            }

        # Both bags.fm and Jupiter failed - record failure
        if circuit_breaker:
            circuit_breaker.record_failure("swap_failed")

        jup_error = getattr(jup_result, "error", None)
        raise BagsAPIError(
            "Trade execution failed on all platforms",
            hint=f"bags.fm error: {last_error or 'Unknown'}. Jupiter error: {jup_error or 'Unknown'}. Try again later or contact support."
        )
    except BagsAPIError:
        # Record failure with circuit breaker
        if circuit_breaker:
            circuit_breaker.record_failure("bags_api_error")
        # Re-raise our custom errors
        raise
    except Exception as exc:
        # Record failure with circuit breaker
        if circuit_breaker:
            circuit_breaker.record_failure(str(exc))

        # Use error handler for user-friendly message if available
        error_handler = _get_demo_error_handler()
        if error_handler:
            user_msg = error_handler.sanitize_for_user(exc)
            # Log detailed error for developers
            dev_msg = error_handler.format_for_developer(exc, {
                "from_token": from_token[:8] if from_token else "unknown",
                "to_token": to_token[:8] if to_token else "unknown",
                "amount": amount,
            })
            logger.error(f"Swap error (dev): {dev_msg}")
        else:
            user_msg = "An unexpected error occurred"
            logger.error(f"Unexpected error during swap execution: {exc}")

        raise BagsAPIError(
            "Trade execution failed due to unexpected error",
            hint=f"{user_msg}. Please try again or contact support if the issue persists."
        )


# =============================================================================
# Buy with TP/SL
# =============================================================================

def _validate_tpsl_required(tp_percent: Optional[float], sl_percent: Optional[float]) -> None:
    """
    Validate that TP/SL are provided and within reasonable ranges.

    Args:
        tp_percent: Take-profit percentage
        sl_percent: Stop-loss percentage

    Raises:
        TPSLValidationError: If TP/SL are missing or invalid
    """
    if tp_percent is None or sl_percent is None:
        raise TPSLValidationError(
            "Take-profit and stop-loss are required for all trades",
            hint="Example: tp_percent=50.0 (50% profit target), sl_percent=20.0 (20% max loss)"
        )

    if tp_percent <= 0:
        raise TPSLValidationError(
            f"Take-profit must be positive, got {tp_percent}%",
            hint="Try tp_percent=50.0 for a 50% profit target"
        )

    if sl_percent <= 0:
        raise TPSLValidationError(
            f"Stop-loss must be positive, got {sl_percent}%",
            hint="Try sl_percent=20.0 to risk 20% max loss"
        )

    if sl_percent >= 100:
        raise TPSLValidationError(
            f"Stop-loss cannot be >= 100% (would exceed your investment), got {sl_percent}%",
            hint="Maximum stop-loss is 99%. Typical range: 10-50%"
        )

    if tp_percent >= 500:
        raise TPSLValidationError(
            f"Take-profit seems unrealistic: {tp_percent}%",
            hint="Maximum recommended TP is 200%. For aggressive targets, try 100-200%"
        )

    if tp_percent < 5:
        raise TPSLValidationError(
            f"Take-profit too low: {tp_percent}%",
            hint="Minimum recommended: 5% to cover trading fees. Try 10-20% for conservative trades"
        )

    if sl_percent < 5:
        raise TPSLValidationError(
            f"Stop-loss too low: {sl_percent}%",
            hint="Minimum recommended: 5% to allow natural price movement. Try 10-20% for conservative trades"
        )


async def execute_buy_with_tpsl(
    token_address: str,
    amount_sol: float,
    wallet_address: str,
    tp_percent: float,  # REQUIRED (no default)
    sl_percent: float,  # REQUIRED (no default)
    slippage_bps: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Execute a buy order with mandatory TP/SL via Bags.fm with Jupiter fallback.

    This function:
    1. Validates TP/SL are provided and reasonable
    2. Tries Bags.fm first for partner fee collection
    3. Falls back to Jupiter on Bags.fm failure
    4. Creates a position with validated TP/SL

    Args:
        token_address: Token mint address to buy
        amount_sol: Amount of SOL to spend
        wallet_address: User's wallet address
        tp_percent: Take-profit percentage (REQUIRED, 5-200%)
        sl_percent: Stop-loss percentage (REQUIRED, 5-99%)
        slippage_bps: Slippage in basis points (default from env)

    Returns:
        Dict with:
            - success: bool
            - position: Position dict with TP/SL (on success)
            - error: Error message (on failure)

    Raises:
        ValueError: If TP/SL are missing or invalid
    """
    import uuid
    from tg_bot.handlers.demo.demo_sentiment import get_ai_sentiment_for_token

    # CRITICAL: Validate TP/SL before executing trade
    _validate_tpsl_required(tp_percent, sl_percent)

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

    # Log trade metrics
    from core.trading.bags_metrics import log_trade
    source = swap.get("source", "bags_api")
    partner_fee = swap.get("partner_fee", 0)
    log_trade(via=source, success=True, volume_sol=amount_sol, partner_fee=partner_fee)

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
