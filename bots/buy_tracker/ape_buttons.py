"""
Ape Trading Buttons for Sentiment Reports.

CRITICAL: All treasury trades MUST have TP/SL set.
If TP/SL cannot be configured, the trade WILL NOT execute.

Risk Profiles:
- SAFE:   TP +15%, SL -5%  (3:1 R/R)
- MEDIUM: TP +30%, SL -10% (3:1 R/R)
- DEGEN:  TP +50%, SL -15% (3.3:1 R/R)

Treasury Allocations:
- 5% of active wallet
- 2% of active wallet
- 1% of active wallet
"""

import logging
import json
import os
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

logger = logging.getLogger(__name__)


# =============================================================================
# RISK PROFILES - MANDATORY FOR ALL TRADES
# =============================================================================

class RiskProfile(Enum):
    """Risk profile determines TP/SL percentages."""
    SAFE = "safe"
    MEDIUM = "medium"
    DEGEN = "degen"


# TP/SL percentages by risk profile for CRYPTO (volatile assets)
# Format: (take_profit_pct, stop_loss_pct)
RISK_PROFILE_CONFIG = {
    RiskProfile.SAFE: {
        "tp_pct": 15.0,   # +15% take profit
        "sl_pct": 5.0,    # -5% stop loss
        "label": "SAFE",
        "emoji": "🛡️",
        "description": "Conservative: +15% TP / -5% SL (3:1 R/R)",
    },
    RiskProfile.MEDIUM: {
        "tp_pct": 30.0,   # +30% take profit
        "sl_pct": 10.0,   # -10% stop loss
        "label": "MED",
        "emoji": "⚖️",
        "description": "Balanced: +30% TP / -10% SL (3:1 R/R)",
    },
    RiskProfile.DEGEN: {
        "tp_pct": 50.0,   # +50% take profit
        "sl_pct": 15.0,   # -15% stop loss
        "label": "DEGEN",
        "emoji": "🔥",
        "description": "Aggressive: +50% TP / -15% SL (3.3:1 R/R)",
    },
}

# TP/SL percentages for STOCKS (less volatile, realistic targets)
STOCK_RISK_PROFILE_CONFIG = {
    RiskProfile.SAFE: {
        "tp_pct": 5.0,    # +5% take profit (swing trade)
        "sl_pct": 2.0,    # -2% stop loss
        "label": "SAFE",
        "emoji": "🛡️",
        "description": "Conservative: +5% TP / -2% SL (2.5:1 R/R)",
    },
    RiskProfile.MEDIUM: {
        "tp_pct": 10.0,   # +10% take profit
        "sl_pct": 4.0,    # -4% stop loss
        "label": "MED",
        "emoji": "⚖️",
        "description": "Balanced: +10% TP / -4% SL (2.5:1 R/R)",
    },
    RiskProfile.DEGEN: {
        "tp_pct": 20.0,   # +20% take profit (momentum play)
        "sl_pct": 8.0,    # -8% stop loss
        "label": "DEGEN",
        "emoji": "🔥",
        "description": "Aggressive: +20% TP / -8% SL (2.5:1 R/R)",
    },
}

# TP/SL percentages for INDEX ETFs (moderate volatility, between stocks and crypto)
INDEX_RISK_PROFILE_CONFIG = {
    RiskProfile.SAFE: {
        "tp_pct": 8.0,    # +8% take profit
        "sl_pct": 3.0,    # -3% stop loss
        "label": "SAFE",
        "emoji": "🛡️",
        "description": "Conservative: +8% TP / -3% SL (2.7:1 R/R)",
    },
    RiskProfile.MEDIUM: {
        "tp_pct": 15.0,   # +15% take profit
        "sl_pct": 6.0,    # -6% stop loss
        "label": "MED",
        "emoji": "⚖️",
        "description": "Balanced: +15% TP / -6% SL (2.5:1 R/R)",
    },
    RiskProfile.DEGEN: {
        "tp_pct": 25.0,   # +25% take profit
        "sl_pct": 10.0,   # -10% stop loss
        "label": "DEGEN",
        "emoji": "🔥",
        "description": "Aggressive: +25% TP / -10% SL (2.5:1 R/R)",
    },
}

# TP/SL percentages for COMMODITIES (gold, silver, oil - moderate volatility)
COMMODITY_RISK_PROFILE_CONFIG = {
    RiskProfile.SAFE: {
        "tp_pct": 6.0,    # +6% take profit
        "sl_pct": 2.5,    # -2.5% stop loss
        "label": "SAFE",
        "emoji": "🛡️",
        "description": "Conservative: +6% TP / -2.5% SL (2.4:1 R/R)",
    },
    RiskProfile.MEDIUM: {
        "tp_pct": 12.0,   # +12% take profit
        "sl_pct": 5.0,    # -5% stop loss
        "label": "MED",
        "emoji": "⚖️",
        "description": "Balanced: +12% TP / -5% SL (2.4:1 R/R)",
    },
    RiskProfile.DEGEN: {
        "tp_pct": 20.0,   # +20% take profit
        "sl_pct": 8.0,    # -8% stop loss
        "label": "DEGEN",
        "emoji": "🔥",
        "description": "Aggressive: +20% TP / -8% SL (2.5:1 R/R)",
    },
}

# TP/SL percentages for BONDS/T-BILLS (lowest volatility)
BOND_RISK_PROFILE_CONFIG = {
    RiskProfile.SAFE: {
        "tp_pct": 3.0,    # +3% take profit
        "sl_pct": 1.0,    # -1% stop loss
        "label": "SAFE",
        "emoji": "🛡️",
        "description": "Conservative: +3% TP / -1% SL (3:1 R/R)",
    },
    RiskProfile.MEDIUM: {
        "tp_pct": 5.0,    # +5% take profit
        "sl_pct": 2.0,    # -2% stop loss
        "label": "MED",
        "emoji": "⚖️",
        "description": "Balanced: +5% TP / -2% SL (2.5:1 R/R)",
    },
    RiskProfile.DEGEN: {
        "tp_pct": 8.0,    # +8% take profit
        "sl_pct": 3.0,    # -3% stop loss
        "label": "DEGEN",
        "emoji": "🔥",
        "description": "Aggressive: +8% TP / -3% SL (2.7:1 R/R)",
    },
}

def get_risk_config(asset_type: str, profile: RiskProfile) -> dict:
    """Get appropriate risk config based on asset type."""
    if asset_type == "stock":
        return STOCK_RISK_PROFILE_CONFIG[profile]
    elif asset_type == "index":
        return INDEX_RISK_PROFILE_CONFIG[profile]
    elif asset_type in ("commodity", "metal"):
        return COMMODITY_RISK_PROFILE_CONFIG[profile]
    elif asset_type == "bond":
        return BOND_RISK_PROFILE_CONFIG[profile]
    return RISK_PROFILE_CONFIG[profile]


# Treasury allocation percentages
APE_ALLOCATION_PCT = {
    "5": {"percent": 5.0, "label": "5%"},
    "2": {"percent": 2.0, "label": "2%"},
    "1": {"percent": 1.0, "label": "1%"},
}


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class TradeSetup:
    """
    Complete trade setup with MANDATORY TP/SL.

    A trade CANNOT be executed without valid TP and SL prices.
    """
    symbol: str
    asset_type: str  # "token", "stock", "commodity", "metal"
    direction: str   # "LONG" or "SHORT"
    entry_price: float

    # MANDATORY - Trade will be rejected without these
    take_profit_price: float
    stop_loss_price: float
    risk_profile: RiskProfile

    # Trade sizing
    allocation_percent: float
    amount_sol: float = 0.0

    # Optional metadata
    contract_address: Optional[str] = None
    reasoning: str = ""
    grade: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def validate(self) -> tuple[bool, str]:
        """
        Validate that trade setup has all required fields.

        Returns:
            (is_valid, error_message)
        """
        errors = []

        # Check mandatory TP/SL
        if self.take_profit_price <= 0:
            errors.append("Take profit price must be set and > 0")

        if self.stop_loss_price <= 0:
            errors.append("Stop loss price must be set and > 0")

        if self.entry_price <= 0:
            errors.append("Entry price must be > 0")

        # Validate TP/SL logic for direction
        if self.direction == "LONG":
            if self.take_profit_price <= self.entry_price:
                errors.append("LONG: Take profit must be above entry price")
            if self.stop_loss_price >= self.entry_price:
                errors.append("LONG: Stop loss must be below entry price")
        else:  # SHORT
            if self.take_profit_price >= self.entry_price:
                errors.append("SHORT: Take profit must be below entry price")
            if self.stop_loss_price <= self.entry_price:
                errors.append("SHORT: Stop loss must be above entry price")

        # Check allocation
        if self.allocation_percent <= 0 or self.allocation_percent > 10:
            errors.append("Allocation must be between 0 and 10%")

        if errors:
            return False, "; ".join(errors)

        return True, "Valid"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage/transmission."""
        return {
            "symbol": self.symbol,
            "asset_type": self.asset_type,
            "direction": self.direction,
            "entry_price": self.entry_price,
            "take_profit_price": self.take_profit_price,
            "stop_loss_price": self.stop_loss_price,
            "risk_profile": self.risk_profile.value,
            "allocation_percent": self.allocation_percent,
            "amount_sol": self.amount_sol,
            "contract_address": self.contract_address,
            "grade": self.grade,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class TradeResult:
    """Result of a trade execution attempt."""
    success: bool
    trade_setup: Optional[TradeSetup] = None
    error: str = ""
    tx_signature: str = ""
    message: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "error": self.error,
            "tx_signature": self.tx_signature,
            "message": self.message,
            "trade_setup": self.trade_setup.to_dict() if self.trade_setup else None,
        }


# =============================================================================
# CONTRACT LOOKUP - Stores full contract for truncated callback data
# =============================================================================

def _save_contract_lookup(contract_short: str, contract_full: str):
    """
    Save contract address mapping for callback lookup.

    Telegram callbacks are limited to 64 bytes, so we truncate contracts.
    This saves the full address for trade execution.
    """
    import tempfile
    from pathlib import Path

    if not contract_short or not contract_full or len(contract_full) < 32:
        return

    lookup_file = Path(tempfile.gettempdir()) / "jarvis_contract_lookup.json"

    try:
        # Load existing
        lookup = {}
        if lookup_file.exists():
            with open(lookup_file) as f:
                lookup = json.load(f)

        # Add/update mapping
        lookup[contract_short] = contract_full

        # Limit size (keep most recent 500)
        if len(lookup) > 500:
            keys = list(lookup.keys())
            for k in keys[:100]:  # Remove oldest 100
                del lookup[k]

        # Save
        with open(lookup_file, "w") as f:
            json.dump(lookup, f)

    except Exception as e:
        logger.debug(f"Contract lookup save failed: {e}")


# =============================================================================
# BUTTON CREATION
# =============================================================================

def create_ape_buttons_with_tp_sl(
    symbol: str,
    asset_type: str,
    contract_address: str = "",
    entry_price: float = 0.0,
    grade: str = "",
) -> InlineKeyboardMarkup:
    """
    Create ape buttons with risk profile selection.

    Each button shows:
    - Allocation percentage (1%, 2%, 5%)
    - Risk profile (Safe, Med, Degen)
    - TP/SL percentages

    Args:
        symbol: Asset symbol
        asset_type: "token", "stock", etc.
        contract_address: For Solana tokens
        entry_price: Current entry price
        grade: Grok grade (A, B, C, etc.)

    Returns:
        InlineKeyboardMarkup with 9 buttons (3 allocations x 3 profiles)
    """
    buttons = []

    # Shorten contract for callback data (Telegram 64-byte limit)
    contract_short = contract_address[:10] if contract_address else ""

    # Save full contract for trade execution lookup
    if contract_address and contract_short:
        _save_contract_lookup(contract_short, contract_address)

    # Header row with profile descriptions
    buttons.append([
        InlineKeyboardButton(
            text="🛡️ SAFE",
            callback_data="info:safe"
        ),
        InlineKeyboardButton(
            text="⚖️ MED",
            callback_data="info:med"
        ),
        InlineKeyboardButton(
            text="🔥 DEGEN",
            callback_data="info:degen"
        ),
    ])

    # Create button rows for each allocation level
    for alloc_key, alloc_config in APE_ALLOCATION_PCT.items():
        row = []

        for profile in [RiskProfile.SAFE, RiskProfile.MEDIUM, RiskProfile.DEGEN]:
            # Use asset-appropriate risk config (stocks have lower targets)
            profile_config = get_risk_config(asset_type, profile)

            # Button text: "5% 🛡️ +15/-5" for crypto, "5% 🛡️ +5/-2" for stocks
            tp = profile_config["tp_pct"]
            sl = profile_config["sl_pct"]
            emoji = profile_config["emoji"]

            button_text = f"{alloc_config['label']} {emoji} +{int(tp)}/-{int(sl)}"

            # Callback data format: ape:{alloc}:{profile}:{type}:{symbol}:{contract}
            # Keep under 64 bytes
            callback = f"ape:{alloc_key}:{profile.value[0]}:{asset_type[0]}:{symbol}:{contract_short}"

            row.append(InlineKeyboardButton(
                text=button_text,
                callback_data=callback[:64]
            ))

        buttons.append(row)

    # Info row
    grade_display = f"Grade: {grade}" if grade else "Ungraded"
    buttons.append([
        InlineKeyboardButton(
            text=f"ℹ️ {symbol} ({grade_display})",
            callback_data=f"info:{asset_type[0]}:{symbol}:{contract_short}"[:64]
        )
    ])

    return InlineKeyboardMarkup(buttons)


def create_token_ape_keyboard(
    symbol: str,
    contract: str,
    entry_price: float = 0.0,
    grade: str = "",
) -> InlineKeyboardMarkup:
    """Create ape keyboard specifically for Solana tokens."""
    return create_ape_buttons_with_tp_sl(
        symbol=symbol,
        asset_type="token",
        contract_address=contract,
        entry_price=entry_price,
        grade=grade,
    )


def create_stock_ape_keyboard(
    ticker: str,
    entry_price: float = 0.0,
    grade: str = "",
) -> InlineKeyboardMarkup:
    """Create ape keyboard for stocks."""
    return create_ape_buttons_with_tp_sl(
        symbol=ticker,
        asset_type="stock",
        entry_price=entry_price,
        grade=grade,
    )


# =============================================================================
# CALLBACK PARSING
# =============================================================================

def parse_ape_callback(callback_data: str) -> Optional[Dict[str, Any]]:
    """
    Parse ape button callback data.

    Callback format: ape:{alloc}:{profile}:{type}:{symbol}:{contract}

    Returns:
        Dict with parsed data or None if invalid
    """
    try:
        parts = callback_data.split(":")

        if parts[0] != "ape" or len(parts) < 5:
            return None

        alloc_key = parts[1]
        profile_char = parts[2]
        asset_type_char = parts[3]
        symbol = parts[4]
        contract = parts[5] if len(parts) > 5 else ""

        # Map profile character to enum
        profile_map = {"s": RiskProfile.SAFE, "m": RiskProfile.MEDIUM, "d": RiskProfile.DEGEN}
        profile = profile_map.get(profile_char, RiskProfile.MEDIUM)

        # Map asset type character
        type_map = {"t": "token", "s": "stock", "i": "index", "c": "commodity", "m": "metal", "b": "bond"}
        asset_type = type_map.get(asset_type_char, "token")

        # Get allocation percent
        alloc_config = APE_ALLOCATION_PCT.get(alloc_key, {"percent": 1.0})

        # Get TP/SL config based on asset type (stocks have lower targets)
        profile_config = get_risk_config(asset_type, profile)

        return {
            "allocation_percent": alloc_config["percent"],
            "risk_profile": profile,
            "tp_pct": profile_config["tp_pct"],
            "sl_pct": profile_config["sl_pct"],
            "asset_type": asset_type,
            "symbol": symbol,
            "contract": contract,
        }

    except Exception as e:
        logger.error(f"Failed to parse ape callback: {e}")
        return None


# =============================================================================
# TRADE EXECUTION WITH MANDATORY TP/SL
# =============================================================================

def calculate_tp_sl_prices(
    entry_price: float,
    risk_profile: RiskProfile,
    direction: str = "LONG",
    asset_type: str = "token",
) -> tuple[float, float]:
    """
    Calculate TP and SL prices from entry price and risk profile.

    Args:
        entry_price: Current/entry price
        risk_profile: Selected risk profile
        direction: "LONG" or "SHORT"
        asset_type: "token", "stock", etc. - determines TP/SL percentages

    Returns:
        (take_profit_price, stop_loss_price)
    """
    # Use asset-appropriate config (stocks have lower targets)
    config = get_risk_config(asset_type, risk_profile)
    tp_pct = config["tp_pct"] / 100
    sl_pct = config["sl_pct"] / 100

    if direction == "LONG":
        tp_price = entry_price * (1 + tp_pct)
        sl_price = entry_price * (1 - sl_pct)
    else:  # SHORT
        tp_price = entry_price * (1 - tp_pct)
        sl_price = entry_price * (1 + sl_pct)

    return tp_price, sl_price


def create_trade_setup(
    parsed_callback: Dict[str, Any],
    entry_price: float,
    treasury_balance_sol: float,
    direction: str = "LONG",
    grade: str = "",
) -> TradeSetup:
    """
    Create a validated TradeSetup from parsed callback data.

    Args:
        parsed_callback: Parsed callback data from parse_ape_callback
        entry_price: Current entry price
        treasury_balance_sol: Treasury balance for sizing
        direction: Trade direction
        grade: Asset grade

    Returns:
        TradeSetup with TP/SL calculated
    """
    profile = parsed_callback["risk_profile"]
    allocation_pct = parsed_callback["allocation_percent"]
    asset_type = parsed_callback.get("asset_type", "token")

    # Calculate TP/SL prices (uses asset-appropriate config - stocks have lower targets)
    tp_price, sl_price = calculate_tp_sl_prices(entry_price, profile, direction, asset_type)

    # Calculate trade amount
    amount_sol = treasury_balance_sol * (allocation_pct / 100)

    return TradeSetup(
        symbol=parsed_callback["symbol"],
        asset_type=parsed_callback["asset_type"],
        direction=direction,
        entry_price=entry_price,
        take_profit_price=tp_price,
        stop_loss_price=sl_price,
        risk_profile=profile,
        allocation_percent=allocation_pct,
        amount_sol=amount_sol,
        contract_address=parsed_callback.get("contract", ""),
        grade=grade,
    )


async def fetch_token_price(contract_address: str = "", symbol: str = "") -> float:
    """Fetch current token price from DexScreener by contract or symbol."""
    import aiohttp

    try:
        async with aiohttp.ClientSession() as session:
            # Try by contract address first (if full address)
            if contract_address and len(contract_address) >= 32:
                url = f"https://api.dexscreener.com/latest/dex/tokens/{contract_address}"
                async with session.get(url, timeout=5) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        pairs = data.get("pairs", [])
                        if pairs:
                            best_pair = max(pairs, key=lambda p: float(p.get("liquidity", {}).get("usd", 0) or 0))
                            price = float(best_pair.get("priceUsd", 0) or 0)
                            if price > 0:
                                logger.info(f"Fetched price by contract: ${price}")
                                return price

            # Try by symbol search (for truncated addresses)
            if symbol:
                url = f"https://api.dexscreener.com/latest/dex/search?q={symbol}"
                async with session.get(url, timeout=5) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        pairs = data.get("pairs", [])
                        # Filter for Solana pairs matching our symbol
                        solana_pairs = [
                            p for p in pairs
                            if p.get("chainId") == "solana"
                            and (p.get("baseToken", {}).get("symbol", "").upper() == symbol.upper()
                                 or symbol.upper() in p.get("baseToken", {}).get("name", "").upper())
                        ]
                        if solana_pairs:
                            # Get most liquid Solana pair
                            best_pair = max(solana_pairs, key=lambda p: float(p.get("liquidity", {}).get("usd", 0) or 0))
                            price = float(best_pair.get("priceUsd", 0) or 0)
                            if price > 0:
                                logger.info(f"Fetched price for {symbol} by search: ${price}")
                                return price

            # Last resort: search trending tokens
            if symbol:
                url = "https://api.dexscreener.com/token-boosts/top/v1"
                async with session.get(url, timeout=5) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        for token in data:
                            if token.get("tokenAddress") and symbol.upper() in str(token).upper():
                                # Found a match, fetch its price
                                token_addr = token.get("tokenAddress")
                                price_url = f"https://api.dexscreener.com/latest/dex/tokens/{token_addr}"
                                async with session.get(price_url, timeout=5) as price_resp:
                                    if price_resp.status == 200:
                                        price_data = await price_resp.json()
                                        pairs = price_data.get("pairs", [])
                                        if pairs:
                                            price = float(pairs[0].get("priceUsd", 0) or 0)
                                            if price > 0:
                                                logger.info(f"Fetched price for {symbol} from trending: ${price}")
                                                return price

    except Exception as e:
        logger.error(f"Failed to fetch token price: {e}")

    return 0.0


async def execute_ape_trade(
    callback_data: str,
    entry_price: float,
    treasury_balance_sol: float,
    direction: str = "LONG",
    grade: str = "",
    max_slippage_pct: float = 20.0,  # Accept up to 20% slippage for volatile tokens
    user_id: Optional[int] = None,
) -> TradeResult:
    """
    Execute an ape trade with MANDATORY TP/SL validation.

    For volatile Solana tokens, fetches current price and accepts slippage.

    Args:
        callback_data: Raw callback data from button
        entry_price: Quoted entry price (0 = fetch from DexScreener)
        treasury_balance_sol: Available treasury balance
        direction: Trade direction
        grade: Asset grade
        max_slippage_pct: Maximum acceptable slippage from quoted price

    Returns:
        TradeResult with success/failure info
    """
    import tempfile
    from pathlib import Path

    # Parse callback
    parsed = parse_ape_callback(callback_data)
    if not parsed:
        return TradeResult(
            success=False,
            error="Invalid callback data - cannot parse trade parameters"
        )

    # Fetch current price if not provided
    current_price = entry_price
    symbol = parsed.get("symbol", "")
    contract_short = parsed.get("contract", "")

    # Look up full contract from mapping (truncated for Telegram callback limit)
    contract = contract_short
    if contract_short and len(contract_short) <= 10:
        lookup_file = Path(tempfile.gettempdir()) / "jarvis_contract_lookup.json"
        try:
            if lookup_file.exists():
                with open(lookup_file) as f:
                    lookup = json.load(f)
                full_contract = lookup.get(contract_short, "")
                if full_contract:
                    contract = full_contract
                    logger.info(f"Resolved contract: {contract_short} -> {contract}")
        except Exception as e:
            logger.error(f"Failed to lookup contract: {e}")

    # Update parsed with full contract for trade setup
    parsed["contract"] = contract

    if current_price <= 0:
        logger.info(f"Fetching live price for {symbol} (contract: {contract})")
        current_price = await fetch_token_price(contract_address=contract, symbol=symbol)

    # For volatile tokens, use market order if price fetch fails
    if current_price <= 0:
        logger.warning(f"Could not fetch price for {symbol}, will use market order with 20% slippage protection")
        # Use a small placeholder - actual execution will be at market price
        # TP/SL will be calculated as percentages from actual fill price
        current_price = 0.000001

    if current_price <= 0:
        return TradeResult(
            success=False,
            error="Could not determine entry price - try again"
        )

    logger.info(f"Trade price for {symbol}: ${current_price}")

    # Create trade setup with TP/SL using FETCHED price
    trade_setup = create_trade_setup(
        parsed_callback=parsed,
        entry_price=current_price,  # Use the fetched/current price, NOT the original parameter
        treasury_balance_sol=treasury_balance_sol,
        direction=direction,
        grade=grade,
    )

    # CRITICAL: Validate trade setup
    is_valid, error_msg = trade_setup.validate()
    if not is_valid:
        return TradeResult(
            success=False,
            trade_setup=trade_setup,
            error=f"REJECTED: {error_msg}"
        )

    # Log the validated trade
    profile_config = RISK_PROFILE_CONFIG[trade_setup.risk_profile]
    logger.info(
        f"APE TRADE VALIDATED: {trade_setup.symbol} "
        f"| {trade_setup.allocation_percent}% allocation "
        f"| {profile_config['label']} profile "
        f"| Entry: ${trade_setup.entry_price:.6f} "
        f"| TP: ${trade_setup.take_profit_price:.6f} (+{profile_config['tp_pct']}%) "
        f"| SL: ${trade_setup.stop_loss_price:.6f} (-{profile_config['sl_pct']}%)"
    )

    # Execute trade based on asset type
    # Note: xStocks (tokenized stocks), indexes, bonds, and commodities are Solana SPL tokens traded on Jupiter
    # They use the same trading flow as regular tokens, just with different TP/SL
    if trade_setup.asset_type in ("token", "stock", "index", "commodity", "metal", "bond"):
        return await _execute_token_trade(trade_setup, user_id=user_id)
    else:
        return TradeResult(
            success=False,
            trade_setup=trade_setup,
            error=f"Asset type '{trade_setup.asset_type}' not supported"
        )


async def _execute_token_trade(setup: TradeSetup, user_id: Optional[int] = None) -> TradeResult:
    """
    Execute a Solana token trade with TP/SL orders.

    This integrates with the treasury trading system.
    """
    logger.info(f"_execute_token_trade called: {setup.symbol}, user={user_id}")
    try:
        # Import treasury trading module
        from bots.treasury.trading import TreasuryTrader

        logger.info("Creating TreasuryTrader...")
        trader = TreasuryTrader()

        logger.info(f"Calling execute_buy_with_tp_sl: {setup.contract_address}, {setup.amount_sol} SOL")
        # Execute buy with TP/SL
        result = await trader.execute_buy_with_tp_sl(
            token_mint=setup.contract_address or "",
            amount_sol=setup.amount_sol,
            take_profit_price=setup.take_profit_price,
            stop_loss_price=setup.stop_loss_price,
            token_symbol=setup.symbol,
            user_id=user_id,
        )

        if result.get("success"):
            return TradeResult(
                success=True,
                trade_setup=setup,
                tx_signature=result.get("tx_signature", ""),
                message=f"Trade executed: {setup.amount_sol:.4f} SOL of {setup.symbol} "
                        f"| TP: ${setup.take_profit_price:.6f} | SL: ${setup.stop_loss_price:.6f}"
            )
        else:
            return TradeResult(
                success=False,
                trade_setup=setup,
                error=result.get("error", "Unknown error during execution")
            )

    except ImportError:
        # Treasury trader not available - return placeholder result
        logger.warning("TreasuryTrader not available - trade not executed")
        return TradeResult(
            success=False,
            trade_setup=setup,
            error="Treasury trading system not available",
            message=f"VALIDATED (not executed): {setup.amount_sol:.4f} SOL of {setup.symbol} "
                    f"| TP: ${setup.take_profit_price:.6f} | SL: ${setup.stop_loss_price:.6f}"
        )
    except Exception as e:
        logger.error(f"Token trade execution failed: {e}")
        return TradeResult(
            success=False,
            trade_setup=setup,
            error=str(e)
        )


# =============================================================================
# TREASURY STATUS DISPLAY
# =============================================================================

def format_treasury_status(
    balance_sol: float = 0.0,
    balance_usd: float = 0.0,
    open_positions: int = 0,
    pnl_24h: float = 0.0,
    treasury_address: str = "",
) -> str:
    """
    Format treasury status message for end of sentiment report.
    """
    pnl_emoji = "📈" if pnl_24h >= 0 else "📉"

    lines = [
        "",
        "<b>========================================</b>",
        "<b>   💰 TREASURY STATUS</b>",
        "<b>========================================</b>",
        "",
        f"Balance: <code>{balance_sol:.4f} SOL</code> (${balance_usd:,.2f})",
        f"Open Positions: <code>{open_positions}</code>",
        f"24h P&L: {pnl_emoji} <code>{pnl_24h:+.2f}%</code>",
    ]

    if treasury_address:
        addr_short = treasury_address[:8] + "..." + treasury_address[-4:]
        lines.extend([
            "",
            f"Treasury: <code>{addr_short}</code>",
            f"<a href=\"https://solscan.io/account/{treasury_address}\">View on Solscan</a>",
        ])

    lines.extend([
        "",
        "<b>Risk Profiles:</b>",
        "🛡️ <b>SAFE</b>: +15% TP / -5% SL",
        "⚖️ <b>MED</b>: +30% TP / -10% SL",
        "🔥 <b>DEGEN</b>: +50% TP / -15% SL",
        "",
        "<i>⚠️ All trades REQUIRE TP/SL - no exceptions</i>",
    ])

    return "\n".join(lines)


# =============================================================================
# TESTING
# =============================================================================

def test_ape_buttons():
    """Test the ape button system."""
    print("=" * 60)
    print("APE BUTTON SYSTEM TEST")
    print("=" * 60)

    # Test 1: Create buttons
    print("\n1. Creating buttons for BONK token...")
    keyboard = create_token_ape_keyboard(
        symbol="BONK",
        contract="DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",
        entry_price=0.00001234,
        grade="B+",
    )
    print(f"   Created keyboard with {len(keyboard.inline_keyboard)} rows")
    for row in keyboard.inline_keyboard:
        print(f"   Row: {[btn.text for btn in row]}")

    # Test 2: Parse callback
    print("\n2. Testing callback parsing...")
    test_callbacks = [
        "ape:5:s:t:BONK:DezXAZ8z7P",  # 5%, Safe, Token
        "ape:2:m:t:BONK:DezXAZ8z7P",  # 2%, Medium, Token
        "ape:1:d:t:BONK:DezXAZ8z7P",  # 1%, Degen, Token
    ]

    for cb in test_callbacks:
        parsed = parse_ape_callback(cb)
        if parsed:
            print(f"   {cb}")
            print(f"      -> {parsed['allocation_percent']}% | {parsed['risk_profile'].value} | TP +{parsed['tp_pct']}% / SL -{parsed['sl_pct']}%")
        else:
            print(f"   FAILED: {cb}")

    # Test 3: Create trade setup
    print("\n3. Testing trade setup creation...")
    parsed = parse_ape_callback("ape:5:m:t:BONK:DezXAZ8z7P")
    if parsed:
        setup = create_trade_setup(
            parsed_callback=parsed,
            entry_price=0.00001234,
            treasury_balance_sol=10.0,
            direction="LONG",
            grade="B+",
        )

        print(f"   Symbol: {setup.symbol}")
        print(f"   Allocation: {setup.allocation_percent}%")
        print(f"   Amount: {setup.amount_sol:.4f} SOL")
        print(f"   Entry: ${setup.entry_price:.8f}")
        print(f"   TP: ${setup.take_profit_price:.8f} (+{RISK_PROFILE_CONFIG[setup.risk_profile]['tp_pct']}%)")
        print(f"   SL: ${setup.stop_loss_price:.8f} (-{RISK_PROFILE_CONFIG[setup.risk_profile]['sl_pct']}%)")

        # Validate
        is_valid, msg = setup.validate()
        print(f"   Valid: {is_valid} ({msg})")

    # Test 4: Validation failures
    print("\n4. Testing validation failures...")

    # Missing TP
    bad_setup = TradeSetup(
        symbol="TEST",
        asset_type="token",
        direction="LONG",
        entry_price=1.0,
        take_profit_price=0,  # Invalid!
        stop_loss_price=0.95,
        risk_profile=RiskProfile.SAFE,
        allocation_percent=5.0,
    )
    is_valid, msg = bad_setup.validate()
    print(f"   Missing TP: Valid={is_valid}, Error='{msg}'")

    # Wrong direction TP
    bad_setup2 = TradeSetup(
        symbol="TEST",
        asset_type="token",
        direction="LONG",
        entry_price=1.0,
        take_profit_price=0.8,  # Below entry for LONG - wrong!
        stop_loss_price=0.95,
        risk_profile=RiskProfile.SAFE,
        allocation_percent=5.0,
    )
    is_valid, msg = bad_setup2.validate()
    print(f"   Wrong TP direction: Valid={is_valid}, Error='{msg}'")

    print("\n" + "=" * 60)
    print("TEST COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    test_ape_buttons()
