"""
Jupiter Perps Acceleration Layer - SAVAGE MODE v2.3.1
======================================================

High-conviction leveraged perpetuals via Jupiter Perps for accelerated capital growth.
Part of the $20 → $1M challenge system.

Core Principles:
- Phase-based leverage scaling (5x → 15x → 30x SAVAGE MODE)
- Immediate exit planning (SL + TP ladder)
- Ultra-tight stop loss for high leverage (1-1.5% for 30x)
- Only trade high-liquidity assets (SOL, BTC, ETH)

Phase Config:
- Phase 0 (Trial): 5x max leverage, 2 trades/day
- Phase 1 (Validated): 15x max leverage, 5 trades/day  
- Phase 2 (SAVAGE): 30x max leverage, 10 trades/day, conviction > 0.9 required

Usage:
    from core.jupiter_perps import evaluate_perps_opportunity, execute_perps_entry

    opp = evaluate_perps_opportunity("SOL", "long", sentiment_score=0.95)
    if opp.is_valid:
        result = execute_perps_entry(opp, wallet_usd=100)
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests

from core import exit_intents
from core import jupiter
from core import solana_network_guard
from core.transaction_guard import require_poly_gnosis_safe

logger = logging.getLogger(__name__)

# State file locations
TRADING_DIR = Path.home() / ".lifeos" / "trading"
PERPS_STATE_FILE = TRADING_DIR / "perps_state.json"

# Jupiter Perps API (paper trading simulation for now)
JUPITER_PERPS_API = "https://perps-api.jup.ag"


# ============================================================================
# Phase Configuration
# ============================================================================

PERPS_PHASE_CONFIG = {
    0: {  # Trial Mode
        "name": "Trial",
        "max_trades_per_day": 2,
        "max_concurrent_positions": 1,
        "max_margin_pct": 0.35,        # 35% of wallet
        "max_leverage": 5.0,           # 5x leverage (Savage Mode upgrade)
        "risk_per_trade_pct": 0.05,    # 5% max loss per trade
        "min_sol_reserve": 0.05,       # Keep for fees
        "trial_trades": 10,
        "edge_to_cost_min": 2.0,
    },
    1: {  # Validated
        "name": "Validated",
        "max_trades_per_day": 5,
        "max_concurrent_positions": 3,
        "max_margin_pct": 0.55,
        "max_leverage": 15.0,          # 15x leverage (Savage Mode upgrade)
        "risk_per_trade_pct": 0.06,
        "min_sol_reserve": 0.05,
        "edge_to_cost_min": 2.5,
    },
    2: {  # SAVAGE MODE 🔥
        "name": "Savage",
        "max_trades_per_day": 10,
        "max_concurrent_positions": 5,
        "max_margin_pct": 0.75,        # 75% of wallet (high risk)
        "max_leverage": 30.0,          # 30x SAVAGE leverage
        "risk_per_trade_pct": 0.03,    # Tighter risk with extreme leverage
        "min_sol_reserve": 0.10,       # Keep more for fees at high frequency
        "min_conviction": 0.9,          # Only trade on high conviction
        "edge_to_cost_min": 3.0,
    },
}

# Promotion thresholds
PERPS_PROMOTION_THRESHOLDS = {
    "min_profit_factor": 1.25,
    "max_drawdown_pct": 0.15,
    "min_enforcement_reliability": 0.97,
    "max_liquidation_events": 0,
}

# Eligible assets (high liquidity only)
ELIGIBLE_ASSETS = {
    "SOL": {
        "symbol": "SOL",
        "min_liquidity_usd": 10_000_000,
        "typical_funding_rate": 0.0001,  # 0.01% per 8h
        "typical_spread_bps": 5,
    },
    "BTC": {
        "symbol": "BTC",
        "min_liquidity_usd": 50_000_000,
        "typical_funding_rate": 0.0001,
        "typical_spread_bps": 3,
    },
    "ETH": {
        "symbol": "ETH",
        "min_liquidity_usd": 30_000_000,
        "typical_funding_rate": 0.0001,
        "typical_spread_bps": 4,
    },
}


# ============================================================================
# Data Structures
# ============================================================================

@dataclass
class PerpsState:
    """Persistent state for perps module."""
    phase: int = 0
    enabled: bool = True

    total_trades: int = 0
    trades_today: int = 0
    last_trade_date: str = ""

    open_positions: List[str] = field(default_factory=list)
    current_margin_usd: float = 0.0

    # Performance
    total_pnl_usd: float = 0.0
    win_count: int = 0
    loss_count: int = 0
    gross_profit: float = 0.0
    gross_loss: float = 0.0
    max_drawdown_pct: float = 0.0

    # Risk events
    liquidation_events: int = 0
    stop_failures: int = 0

    # Recent trades
    recent_trades: List[Dict[str, Any]] = field(default_factory=list)

    # Cooldown
    cooldown_until: Optional[float] = None
    shutdown_reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PerpsState":
        state = cls()
        for key, value in data.items():
            if hasattr(state, key):
                setattr(state, key, value)
        return state


@dataclass
class PerpsOpportunity:
    """Evaluated perps trading opportunity."""
    asset: str
    direction: str                 # "long" or "short"

    # Market data
    current_price: float = 0.0
    funding_rate: float = 0.0

    # Analysis
    sentiment_score: float = 0.0
    momentum_score: float = 0.0
    edge_estimate: float = 0.0
    cost_estimate: float = 0.0
    edge_to_cost: float = 0.0

    # Risk
    recommended_leverage: float = 1.5
    recommended_margin_pct: float = 0.10
    stop_loss_pct: float = 0.03
    liquidation_distance_pct: float = 0.0

    # Validation
    is_valid: bool = True
    rejection_reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PerpsPosition:
    """Active perps position."""
    id: str
    asset: str
    direction: str
    leverage: float
    margin_usd: float
    entry_price: float
    quantity: float
    liquidation_price: float

    # Exit levels
    stop_loss: float
    take_profits: List[Dict[str, Any]]
    trailing_stop_active: bool = False

    # Status
    status: str = "open"
    pnl_usd: float = 0.0
    pnl_pct: float = 0.0
    funding_paid: float = 0.0

    # Timestamps
    entry_timestamp: float = field(default_factory=time.time)
    last_update: float = field(default_factory=time.time)

    # Intent
    intent_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PerpsPosition":
        return cls(**data)


# ============================================================================
# State Management
# ============================================================================

def _ensure_dir():
    TRADING_DIR.mkdir(parents=True, exist_ok=True)


def load_perps_state() -> PerpsState:
    """Load perps module state."""
    if PERPS_STATE_FILE.exists():
        try:
            data = json.loads(PERPS_STATE_FILE.read_text())
            return PerpsState.from_dict(data)
        except (json.JSONDecodeError, IOError):
            pass
    return PerpsState()


def save_perps_state(state: PerpsState) -> bool:
    """Save perps module state."""
    _ensure_dir()
    try:
        PERPS_STATE_FILE.write_text(json.dumps(state.to_dict(), indent=2))
        return True
    except IOError as e:
        logger.error(f"[jupiter_perps] Failed to save state: {e}")
        return False


def get_perps_status() -> Dict[str, Any]:
    """Get current perps module status."""
    state = load_perps_state()
    config = PERPS_PHASE_CONFIG.get(state.phase, PERPS_PHASE_CONFIG[0])

    win_rate = state.win_count / max(state.total_trades, 1)
    profit_factor = state.gross_profit / max(abs(state.gross_loss), 0.01)

    return {
        "phase": state.phase,
        "phase_name": config["name"],
        "enabled": state.enabled,
        "max_leverage": config["max_leverage"],
        "total_trades": state.total_trades,
        "trades_today": state.trades_today,
        "open_positions": len(state.open_positions),
        "current_margin_usd": state.current_margin_usd,
        "total_pnl_usd": state.total_pnl_usd,
        "win_rate": win_rate,
        "profit_factor": profit_factor,
        "liquidation_events": state.liquidation_events,
        "cooldown_until": state.cooldown_until,
    }


# ============================================================================
# Market Data
# ============================================================================

def get_asset_price(asset: str) -> Optional[float]:
    """Get current price for an asset."""
    try:
        # Use Jupiter price API
        price_data = jupiter.get_price([asset])
        if price_data and "data" in price_data:
            asset_data = price_data["data"].get(asset, {})
            return float(asset_data.get("price", 0))
    except Exception as e:
        logger.warning(f"[jupiter_perps] Failed to get price for {asset}: {e}")

    # Fallback: hardcoded for demo
    fallback_prices = {"SOL": 180.0, "BTC": 95000.0, "ETH": 3500.0}
    return fallback_prices.get(asset)


def get_funding_rate(asset: str) -> float:
    """Get current funding rate for an asset."""
    # In production, fetch from Jupiter Perps API
    # For now, return typical rate
    asset_config = ELIGIBLE_ASSETS.get(asset, {})
    return asset_config.get("typical_funding_rate", 0.0001)


# ============================================================================
# Opportunity Evaluation
# ============================================================================

def evaluate_perps_opportunity(
    asset: str,
    direction: str,
    *,
    sentiment_score: float = 0.5,
    momentum_score: float = 0.5,
    volatility_regime: str = "normal",
) -> PerpsOpportunity:
    """
    Evaluate a perps trading opportunity.

    Args:
        asset: Asset to trade (SOL, BTC, ETH)
        direction: "long" or "short"
        sentiment_score: 0-1 sentiment score
        momentum_score: 0-1 momentum confirmation
        volatility_regime: "low", "normal", or "high"

    Returns:
        PerpsOpportunity with validity and sizing
    """
    opp = PerpsOpportunity(
        asset=asset,
        direction=direction,
        sentiment_score=sentiment_score,
        momentum_score=momentum_score,
    )

    # Check if asset is eligible
    if asset not in ELIGIBLE_ASSETS:
        opp.is_valid = False
        opp.rejection_reason = f"asset_not_eligible: {asset}"
        return opp

    # Get current price
    price = get_asset_price(asset)
    if not price:
        opp.is_valid = False
        opp.rejection_reason = "price_fetch_failed"
        return opp
    opp.current_price = price

    # Get funding rate
    opp.funding_rate = get_funding_rate(asset)

    # Check if funding is adverse to position
    # Positive funding = longs pay shorts
    if direction == "long" and opp.funding_rate > 0.0005:  # 0.05% per 8h
        opp.is_valid = False
        opp.rejection_reason = f"funding_adverse: {opp.funding_rate:.4%}"
        return opp
    elif direction == "short" and opp.funding_rate < -0.0005:
        opp.is_valid = False
        opp.rejection_reason = f"funding_adverse: {opp.funding_rate:.4%}"
        return opp

    # Load state and config
    state = load_perps_state()
    config = PERPS_PHASE_CONFIG.get(state.phase, PERPS_PHASE_CONFIG[0])

    # Calculate conviction score
    conviction = (sentiment_score + momentum_score) / 2
    
    # Check conviction requirements for Phase 2 (Savage Mode)
    min_conviction = config.get("min_conviction", 0.0)
    if conviction < min_conviction:
        opp.is_valid = False
        opp.rejection_reason = f"conviction_too_low: {conviction:.2f} < {min_conviction}"
        return opp

    # Determine leverage based on conditions - SAVAGE MODE SCALING
    max_leverage = config["max_leverage"]
    
    if conviction > 0.9 and max_leverage >= 30.0:
        # SAVAGE MODE: 30x for ultra-high conviction
        base_leverage = 30.0
        logger.info(f"[jupiter_perps] 🔥 SAVAGE MODE ACTIVATED: 30x leverage (conviction={conviction:.2f})")
    elif conviction > 0.8 and max_leverage >= 15.0:
        # High conviction: up to 15x
        base_leverage = min(15.0, max_leverage)
    elif conviction > 0.7:
        # Good conviction: up to 10x
        base_leverage = min(10.0, max_leverage)
    elif conviction > 0.5:
        # Moderate conviction: up to 5x
        base_leverage = min(5.0, max_leverage)
    else:
        # Low conviction: conservative 2x
        base_leverage = min(2.0, max_leverage)

    # Adjust for volatility
    if volatility_regime == "high":
        base_leverage *= 0.6  # More conservative in high vol
    elif volatility_regime == "low":
        base_leverage *= 1.1

    # Cap at phase limit
    opp.recommended_leverage = min(base_leverage, max_leverage)

    # Calculate stop loss - ULTRA-TIGHT FOR HIGH LEVERAGE
    # At 30x: liquidation at ~3.3%, so stop must be 1-1.5%
    if opp.recommended_leverage >= 25.0:
        # SAVAGE MODE: Ultra-tight stop loss (1-1.5%)
        opp.stop_loss_pct = 0.012  # 1.2% stop loss for 30x
    elif opp.recommended_leverage >= 15.0:
        # High leverage: tight stop (2%)
        opp.stop_loss_pct = 0.02
    elif opp.recommended_leverage >= 10.0:
        # Medium-high: 2.5% stop
        opp.stop_loss_pct = 0.025
    elif opp.recommended_leverage >= 5.0:
        # Medium: 3% stop
        opp.stop_loss_pct = 0.03
    else:
        # Conservative: 4% stop
        opp.stop_loss_pct = 0.04

    # Calculate margin allocation
    opp.recommended_margin_pct = min(
        config["max_margin_pct"],
        config["risk_per_trade_pct"] / opp.stop_loss_pct,
    )

    # Calculate liquidation distance
    # Liquidation happens when loss = margin
    # With leverage L, price move of 1/L causes 100% loss
    opp.liquidation_distance_pct = 1.0 / opp.recommended_leverage - 0.005  # Tighter safety buffer for high leverage

    # Ensure stop loss is WELL before liquidation (critical for 30x)
    liquidation_safety_margin = 0.7 if opp.recommended_leverage >= 20.0 else 0.8
    if opp.stop_loss_pct >= opp.liquidation_distance_pct * liquidation_safety_margin:
        opp.is_valid = False
        opp.rejection_reason = f"stop_too_close_to_liquidation: SL={opp.stop_loss_pct:.2%}, Liq={opp.liquidation_distance_pct:.2%}"
        return opp

    # Estimate edge
    opp.edge_estimate = _estimate_perps_edge(sentiment_score, momentum_score, direction)

    # Estimate costs
    opp.cost_estimate = _estimate_perps_costs(asset, opp.recommended_leverage, hold_time_hours=4)

    # Edge to cost ratio
    if opp.cost_estimate > 0:
        opp.edge_to_cost = opp.edge_estimate / opp.cost_estimate
    else:
        opp.edge_to_cost = 0

    if opp.edge_to_cost < config["edge_to_cost_min"]:
        opp.is_valid = False
        opp.rejection_reason = f"edge_to_cost_low: {opp.edge_to_cost:.2f}"
        return opp

    return opp


def _estimate_perps_edge(
    sentiment_score: float,
    momentum_score: float,
    direction: str,
) -> float:
    """Estimate expected edge for perps trade."""
    base_edge = 0.02  # 2% base

    # Conviction multiplier
    conviction = (sentiment_score + momentum_score) / 2
    conviction_mult = 0.5 + conviction  # 0.5x to 1.5x

    edge = base_edge * conviction_mult

    return min(0.10, max(0.005, edge))  # 0.5% to 10%


def _estimate_perps_costs(
    asset: str,
    leverage: float,
    hold_time_hours: float,
) -> float:
    """Estimate total costs for perps trade."""
    asset_config = ELIGIBLE_ASSETS.get(asset, {})

    # Taker fee (0.06% on Jupiter Perps)
    taker_fee_pct = 0.0006

    # Spread
    spread_bps = asset_config.get("typical_spread_bps", 5)
    spread_pct = spread_bps / 10000

    # Funding (per 8h period)
    funding_rate = asset_config.get("typical_funding_rate", 0.0001)
    funding_periods = hold_time_hours / 8
    funding_cost = abs(funding_rate) * funding_periods * leverage

    # Total (entry + exit)
    total = (taker_fee_pct * 2) + (spread_pct * 2) + funding_cost

    return total


# ============================================================================
# Trade Execution
# ============================================================================

def can_trade_perps(wallet_usd: float) -> Tuple[bool, str]:
    """Check if perps trading is allowed."""
    state = load_perps_state()
    config = PERPS_PHASE_CONFIG.get(state.phase, PERPS_PHASE_CONFIG[0])

    if not state.enabled:
        return False, f"module_disabled: {state.shutdown_reason}"

    if state.cooldown_until and time.time() < state.cooldown_until:
        remaining = int(state.cooldown_until - time.time())
        return False, f"cooldown: {remaining}s remaining"

    network_status = solana_network_guard.assess_network_health()
    if not network_status.get("ok", True):
        return False, f"network_guard:{network_status.get('reason', 'unknown')}"

    today = time.strftime("%Y-%m-%d")
    if state.last_trade_date != today:
        state.trades_today = 0
        state.last_trade_date = today
        save_perps_state(state)

    if state.trades_today >= config["max_trades_per_day"]:
        return False, "daily_limit_reached"

    if len(state.open_positions) >= config["max_concurrent_positions"]:
        return False, "max_positions_reached"

    max_margin = wallet_usd * config["max_margin_pct"]
    if state.current_margin_usd >= max_margin:
        return False, "margin_limit_reached"

    # Check SOL reserve
    sol_price = get_asset_price("SOL") or 180.0
    min_reserve_usd = config["min_sol_reserve"] * sol_price
    if wallet_usd - state.current_margin_usd < min_reserve_usd:
        return False, "insufficient_reserve"

    return True, ""


def execute_perps_entry(
    opportunity: PerpsOpportunity,
    wallet_usd: float,
    *,
    paper_mode: bool = True,
) -> Optional[PerpsPosition]:
    """
    Execute a perps trade entry.

    Returns PerpsPosition if successful, None otherwise.
    """
    if not opportunity.is_valid:
        logger.warning(f"[jupiter_perps] Invalid opportunity: {opportunity.rejection_reason}")
        return None

    can_trade, reason = can_trade_perps(wallet_usd)
    if not can_trade:
        logger.warning(f"[jupiter_perps] Cannot trade: {reason}")
        return None

    if not paper_mode:
        ok, error = require_poly_gnosis_safe("jupiter_perps_entry")
        if not ok:
            logger.error(f"[jupiter_perps] Safe enforcement failed: {error}")
            return None

    state = load_perps_state()
    config = PERPS_PHASE_CONFIG.get(state.phase, PERPS_PHASE_CONFIG[0])

    # Calculate position size
    margin_usd = min(
        wallet_usd * opportunity.recommended_margin_pct,
        wallet_usd * config["max_margin_pct"] - state.current_margin_usd,
        50 if paper_mode else wallet_usd * 0.10,  # Cap paper at $50
    )

    if margin_usd < 1:
        logger.warning("[jupiter_perps] Margin too small")
        return None

    position_value = margin_usd * opportunity.recommended_leverage
    quantity = position_value / opportunity.current_price

    # Calculate stop loss and liquidation prices
    if opportunity.direction == "long":
        stop_loss = opportunity.current_price * (1 - opportunity.stop_loss_pct)
        liquidation_price = opportunity.current_price * (1 - opportunity.liquidation_distance_pct)
    else:
        stop_loss = opportunity.current_price * (1 + opportunity.stop_loss_pct)
        liquidation_price = opportunity.current_price * (1 + opportunity.liquidation_distance_pct)

    # Create position
    position_id = f"perps-{str(uuid.uuid4())[:8]}"

    position = PerpsPosition(
        id=position_id,
        asset=opportunity.asset,
        direction=opportunity.direction,
        leverage=opportunity.recommended_leverage,
        margin_usd=margin_usd,
        entry_price=opportunity.current_price,
        quantity=quantity,
        liquidation_price=liquidation_price,
        stop_loss=stop_loss,
        take_profits=[
            {"level": 1, "price": opportunity.current_price * (1 + 0.04 if opportunity.direction == "long" else 1 - 0.04), "size_pct": 50},
            {"level": 2, "price": opportunity.current_price * (1 + 0.08 if opportunity.direction == "long" else 1 - 0.08), "size_pct": 30},
            {"level": 3, "price": opportunity.current_price * (1 + 0.15 if opportunity.direction == "long" else 1 - 0.15), "size_pct": 20},
        ],
    )

    # Create exit intent IMMEDIATELY
    intent = exit_intents.create_perps_intent(
        position_id=position.id,
        asset=position.asset,
        direction=position.direction,
        entry_price=position.entry_price,
        quantity=position.quantity,
        leverage=position.leverage,
        liquidation_price=position.liquidation_price,
        is_paper=paper_mode,
        strategy_id="jupiter_perps",
    )

    # CRITICAL: Persist intent
    if not exit_intents.persist_intent(intent):
        logger.error(f"[jupiter_perps] CRITICAL: Failed to persist intent for {position.id}")
        return None

    position.intent_id = intent.id

    # Update state
    state.trades_today += 1
    state.total_trades += 1
    state.current_margin_usd += margin_usd
    state.open_positions.append(position.id)

    trade_record = {
        "position_id": position.id,
        "asset": position.asset,
        "direction": position.direction,
        "leverage": position.leverage,
        "margin_usd": margin_usd,
        "entry_price": position.entry_price,
        "quantity": position.quantity,
        "stop_loss": position.stop_loss,
        "liquidation_price": position.liquidation_price,
        "intent_id": intent.id,
        "timestamp": time.time(),
        "is_paper": paper_mode,
        "status": "open",
    }
    state.recent_trades.append(trade_record)

    save_perps_state(state)

    logger.info(
        f"[jupiter_perps] Opened {position.direction} {position.asset}: "
        f"${margin_usd:.2f} @ ${position.entry_price:.2f}, "
        f"{position.leverage:.1f}x leverage, liq=${position.liquidation_price:.2f}"
    )

    return position


def generate_perps_jupyter_bundle(position: PerpsPosition) -> str:
    """Generate Jupyter cell bundle for perps position monitoring."""
    direction_sign = "+" if position.direction == "long" else "-"

    bundle = f'''
# ============================================================================
# Cell 1: Perps Position Details
# ============================================================================
"""
## Jupiter Perps Position: {position.asset} {position.direction.upper()}

**Entry:**
- Asset: {position.asset}
- Direction: {position.direction.upper()}
- Entry Price: ${position.entry_price:.2f}
- Leverage: {position.leverage:.1f}x
- Margin: ${position.margin_usd:.2f}
- Quantity: {position.quantity:.6f}

**Risk Levels:**
- Stop Loss: ${position.stop_loss:.2f} ({direction_sign}{abs((position.stop_loss/position.entry_price - 1)*100):.1f}%)
- Liquidation: ${position.liquidation_price:.2f}

**Take Profits:**
- TP1: ${position.take_profits[0]["price"]:.2f} (50%)
- TP2: ${position.take_profits[1]["price"]:.2f} (30%)
- TP3: ${position.take_profits[2]["price"]:.2f} (20% runner)
"""

# ============================================================================
# Cell 2: Monitor Position
# ============================================================================
from core.jupiter_perps import get_asset_price

current_price = get_asset_price("{position.asset}")
entry_price = {position.entry_price}

if current_price:
    pnl_pct = ((current_price / entry_price) - 1) * 100
    if "{position.direction}" == "short":
        pnl_pct = -pnl_pct
    pnl_leveraged = pnl_pct * {position.leverage}

    print(f"Current Price: ${{current_price:.2f}}")
    print(f"P&L: {{pnl_pct:+.2f}}% ({{pnl_leveraged:+.2f}}% with leverage)")

    # Distance to liquidation
    liq_distance = abs((current_price - {position.liquidation_price}) / current_price) * 100
    print(f"Distance to Liquidation: {{liq_distance:.1f}}%")

# ============================================================================
# Cell 3: Emergency Close
# ============================================================================
# from core.jupiter_perps import close_perps_position
# close_perps_position("{position.id}", reason="manual_emergency")
'''
    return bundle


def close_perps_position(
    position_id: str,
    reason: str = "manual",
    *,
    paper_mode: bool = True,
) -> Optional[Dict[str, Any]]:
    """Close a perps position."""
    state = load_perps_state()

    # Find position
    trade = None
    for t in state.recent_trades:
        if t.get("position_id") == position_id:
            trade = t
            break

    if not trade:
        return None

    # Get current price
    current_price = get_asset_price(trade["asset"])
    if not current_price:
        current_price = trade["entry_price"]

    # Calculate P&L
    entry_price = trade["entry_price"]
    quantity = trade["quantity"]
    leverage = trade["leverage"]
    direction = trade["direction"]

    if direction == "long":
        pnl_pct = ((current_price / entry_price) - 1) * 100
    else:
        pnl_pct = ((entry_price / current_price) - 1) * 100

    pnl_leveraged = pnl_pct * leverage
    pnl_usd = trade["margin_usd"] * (pnl_leveraged / 100)

    # Cancel intent
    if trade.get("intent_id"):
        exit_intents.cancel_intent(trade["intent_id"], reason=reason)

    # Update state
    if position_id in state.open_positions:
        state.open_positions.remove(position_id)
    state.current_margin_usd -= trade["margin_usd"]
    state.total_pnl_usd += pnl_usd

    if pnl_usd >= 0:
        state.win_count += 1
        state.gross_profit += pnl_usd
    else:
        state.loss_count += 1
        state.gross_loss += abs(pnl_usd)

    trade["status"] = "closed"
    trade["close_price"] = current_price
    trade["close_reason"] = reason
    trade["pnl_usd"] = pnl_usd
    trade["pnl_pct"] = pnl_leveraged
    trade["close_timestamp"] = time.time()

    save_perps_state(state)

    logger.info(
        f"[jupiter_perps] Closed {trade['direction']} {trade['asset']}: "
        f"PnL ${pnl_usd:+.2f} ({pnl_leveraged:+.2f}%)"
    )

    return {
        "position_id": position_id,
        "closed": True,
        "reason": reason,
        "pnl_usd": pnl_usd,
        "pnl_pct": pnl_leveraged,
    }


# ============================================================================
# CLI Demo
# ============================================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("=== Jupiter Perps Module Demo ===\n")

    # Show status
    status = get_perps_status()
    print("Module Status:")
    for key, value in status.items():
        print(f"  {key}: {value}")

    print("\n" + "=" * 50)
    print("Evaluating SOL long opportunity...")
    print("=" * 50 + "\n")

    opp = evaluate_perps_opportunity(
        "SOL",
        "long",
        sentiment_score=0.75,
        momentum_score=0.65,
        volatility_regime="normal",
    )

    print("Opportunity Analysis:")
    print(f"  Asset: {opp.asset}")
    print(f"  Direction: {opp.direction}")
    print(f"  Current Price: ${opp.current_price:.2f}")
    print(f"  Recommended Leverage: {opp.recommended_leverage:.1f}x")
    print(f"  Stop Loss: {opp.stop_loss_pct:.1%}")
    print(f"  Liquidation Distance: {opp.liquidation_distance_pct:.1%}")
    print(f"  Edge Estimate: {opp.edge_estimate:.2%}")
    print(f"  Cost Estimate: {opp.cost_estimate:.2%}")
    print(f"  Edge/Cost: {opp.edge_to_cost:.2f}x")
    print(f"  Valid: {opp.is_valid}")

    if opp.is_valid:
        print("\nExecuting paper trade...")
        position = execute_perps_entry(opp, wallet_usd=100, paper_mode=True)

        if position:
            print(f"\nPosition opened: {position.id}")
            print(f"  Margin: ${position.margin_usd:.2f}")
            print(f"  Entry: ${position.entry_price:.2f}")
            print(f"  Stop: ${position.stop_loss:.2f}")
            print(f"  Liquidation: ${position.liquidation_price:.2f}")

            # Generate bundle
            bundle = generate_perps_jupyter_bundle(position)
            print("\n[Jupyter bundle generated]")

    else:
        print(f"\nRejected: {opp.rejection_reason}")

    print("\n✓ Jupiter Perps module ready")
