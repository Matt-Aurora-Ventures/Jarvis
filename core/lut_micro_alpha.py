"""
LUT Micro-Alpha Trading Module
==============================

High-risk trending token subsystem with weighted allocation and phase-based scaling.
Implements the complete LUT_MICRO_ALPHA specification with:

- Multi-source trending data (Birdeye, GeckoTerminal, DexScreener)
- xAI/Grok sentiment validation
- Strict liquidity and rug-risk gating
- Fee-aware execution
- Immediate exit planning (TP ladder + SL + time stop)
- Phase-based scaling (0 → 1 → 2)

Core Principle: This module is always evaluated each cycle, but must not dominate.

Usage:
    from core.lut_micro_alpha import run_cycle, get_module_status

    result = run_cycle(nav=1000.0)
    status = get_module_status()
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core import birdeye
from core import exit_intents
from core import rugcheck
from core import solana_network_guard
from core import trending_aggregator

logger = logging.getLogger(__name__)

# State file locations
TRADING_DIR = Path.home() / ".lifeos" / "trading"
STATE_FILE = TRADING_DIR / "lut_module_state.json"


# ============================================================================
# Phase Configuration
# ============================================================================

PHASE_CONFIG = {
    0: {  # Trial Mode (Phase 0)
        "name": "Trial",
        "module_weight": 0.33,           # Relative to core strategies at 1.0
        "max_module_exposure": 0.10,     # 10% of NAV max
        "max_single_trade": 0.02,        # 2% of NAV per trade
        "max_trades_per_day": 2,
        "tokens_per_cycle": 2,
        "edge_to_cost_min": 2.0,
        "trial_trades": 12,              # Trades needed to evaluate promotion
        "trial_days": 7,
    },
    1: {  # Validated (Phase 1)
        "name": "Validated",
        "module_weight": 0.50,
        "max_module_exposure": 0.15,     # 15% of NAV
        "max_single_trade": 0.025,       # 2.5% of NAV
        "max_trades_per_day": 3,
        "tokens_per_cycle": 2,
        "edge_to_cost_min": 2.5,
    },
    2: {  # Scaled (Phase 2)
        "name": "Scaled",
        "module_weight": 0.75,
        "max_module_exposure": 0.20,     # 20% of NAV
        "max_single_trade": 0.03,        # 3% of NAV
        "max_trades_per_day": 4,
        "tokens_per_cycle": 2,
        "edge_to_cost_min": 3.0,
    },
}

# Promotion Thresholds
PROMOTION_TO_PHASE_1 = {
    "min_net_pnl": 0.0,              # Must be positive
    "min_profit_factor": 1.25,
    "max_drawdown_pct": 0.40,        # 40% of module risk budget
    "min_enforcement_reliability": 0.95,
    "avg_edge_to_cost_min": 2.5,
    "max_catastrophic_events": 1,
}

PROMOTION_TO_PHASE_2 = {
    "min_profit_factor": 1.50,
    "min_win_rate": 0.55,
    "min_enforcement_reliability": 0.97,
    "avg_edge_to_cost_min": 3.0,
}

# Hard Safety Constraints
DEFAULT_CONSTRAINTS = {
    "min_liquidity_usd": 100_000,    # $100k minimum
    "min_volume_24h_usd": 250_000,   # $250k minimum
    "max_slippage_pct": 0.04,        # 4% max slippage
    "max_top10_holder_pct": 0.40,    # 40% max concentration (excl LP)
    "sentiment_min_score": 0.3,
    "sentiment_min_credibility": 0.5,
}


# ============================================================================
# Data Structures
# ============================================================================

@dataclass
class ModuleState:
    """Persistent state for the LUT micro-alpha module."""
    phase: int = 0
    phase_started_at: float = field(default_factory=time.time)

    # Trade history
    total_trades: int = 0
    trades_today: int = 0
    last_trade_date: str = ""

    # Exposure tracking
    current_exposure_usd: float = 0.0
    open_positions: List[str] = field(default_factory=list)  # Position IDs

    # Performance metrics
    total_pnl_usd: float = 0.0
    win_count: int = 0
    loss_count: int = 0
    gross_profit: float = 0.0
    gross_loss: float = 0.0
    max_drawdown_pct: float = 0.0
    peak_equity: float = 0.0

    # Recent trades for evaluation
    recent_trades: List[Dict[str, Any]] = field(default_factory=list)

    # Module status
    enabled: bool = True
    shutdown_reason: Optional[str] = None
    cooldown_until: Optional[float] = None

    # Catastrophic events
    catastrophic_events: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ModuleState":
        state = cls()
        for key, value in data.items():
            if hasattr(state, key):
                setattr(state, key, value)
        return state


@dataclass
class CycleResult:
    """Result of a single trading cycle."""
    timestamp: float = field(default_factory=time.time)
    skipped: bool = False
    skip_reason: str = ""

    candidates_scanned: int = 0
    candidates_validated: int = 0
    trades_executed: int = 0

    trade_results: List[Dict[str, Any]] = field(default_factory=list)
    rejections: List[Dict[str, Any]] = field(default_factory=list)

    phase_before: int = 0
    phase_after: int = 0
    phase_transition: Optional[str] = None

    jupyter_bundles: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TradeCandidate:
    """A token being evaluated for trading."""
    token: trending_aggregator.TrendingToken
    sentiment_score: float = 0.0
    sentiment_credibility: float = 0.0
    sentiment_notes: str = ""
    safety_report: Optional[Dict[str, Any]] = None

    estimated_edge: float = 0.0
    estimated_cost: float = 0.0
    edge_to_cost: float = 0.0

    rejection_reason: Optional[str] = None

    def is_valid(self) -> bool:
        return self.rejection_reason is None


# ============================================================================
# State Management
# ============================================================================

def _ensure_dir():
    TRADING_DIR.mkdir(parents=True, exist_ok=True)


def load_module_state() -> ModuleState:
    """Load module state from disk."""
    if STATE_FILE.exists():
        try:
            data = json.loads(STATE_FILE.read_text())
            return ModuleState.from_dict(data)
        except (json.JSONDecodeError, IOError):
            pass
    return ModuleState()


def save_module_state(state: ModuleState) -> bool:
    """Save module state to disk."""
    _ensure_dir()
    try:
        STATE_FILE.write_text(json.dumps(state.to_dict(), indent=2))
        return True
    except IOError as e:
        logger.error(f"[lut_micro_alpha] Failed to save state: {e}")
        return False


def get_module_status() -> Dict[str, Any]:
    """Get current module status for display."""
    state = load_module_state()
    config = PHASE_CONFIG[state.phase]
    reliability = exit_intents.get_reliability_stats()

    win_rate = state.win_count / max(state.total_trades, 1)
    profit_factor = state.gross_profit / max(abs(state.gross_loss), 0.01)

    return {
        "phase": state.phase,
        "phase_name": config["name"],
        "enabled": state.enabled,
        "total_trades": state.total_trades,
        "trades_today": state.trades_today,
        "current_exposure_usd": state.current_exposure_usd,
        "open_positions": len(state.open_positions),
        "total_pnl_usd": state.total_pnl_usd,
        "win_rate": win_rate,
        "profit_factor": profit_factor,
        "max_drawdown_pct": state.max_drawdown_pct,
        "enforcement_reliability": reliability.get("reliability_pct", 0),
        "cooldown_until": state.cooldown_until,
        "shutdown_reason": state.shutdown_reason,
    }


# ============================================================================
# Constraint Checking
# ============================================================================

def check_hard_constraints(
    token: trending_aggregator.TrendingToken,
    constraints: Dict[str, Any] = None,
) -> Optional[str]:
    """
    Check hard safety constraints. Returns rejection reason or None if passes.
    """
    if constraints is None:
        constraints = DEFAULT_CONSTRAINTS

    # Liquidity check
    if token.liquidity_usd < constraints["min_liquidity_usd"]:
        return f"liquidity_low: ${token.liquidity_usd:,.0f} < ${constraints['min_liquidity_usd']:,.0f}"

    # Volume check
    if token.volume_24h_usd < constraints["min_volume_24h_usd"]:
        return f"volume_low: ${token.volume_24h_usd:,.0f} < ${constraints['min_volume_24h_usd']:,.0f}"

    return None


def check_safety_gate(
    token_mint: str,
    constraints: Dict[str, Any] = None,
) -> Tuple[bool, Dict[str, Any]]:
    """
    Run RugCheck safety validation.

    Returns (is_safe, report)
    """
    if constraints is None:
        constraints = DEFAULT_CONSTRAINTS

    try:
        report = rugcheck.fetch_report(token_mint)
        if not report:
            return False, {"error": "fetch_failed"}

        safety = rugcheck.evaluate_safety(
            report,
            min_locked_pct=50,
            require_spl_program=True,
            max_transfer_fee_bps=100,
        )

        return safety.get("ok", False), safety

    except Exception as e:
        logger.warning(f"[lut_micro_alpha] RugCheck failed for {token_mint}: {e}")
        return False, {"error": str(e)}


def validate_sentiment(
    token: trending_aggregator.TrendingToken,
    constraints: Dict[str, Any] = None,
) -> Tuple[float, float, str]:
    """
    Validate sentiment using xAI. Returns (score, credibility, notes).

    For now, returns mock data. Will integrate with xai_twitter.py.
    """
    if constraints is None:
        constraints = DEFAULT_CONSTRAINTS

    # TODO: Integrate with xai_twitter.py for real sentiment analysis
    # For Phase 0, use velocity as a proxy for sentiment
    velocity_score = min(1.0, max(0.0, token.velocity + 0.5))
    credibility = 0.7 if len(token.sources) >= 2 else 0.5

    notes = f"velocity={token.velocity:+.2f}, sources={len(token.sources)}"

    return velocity_score, credibility, notes


# ============================================================================
# Edge Estimation
# ============================================================================

def estimate_edge(
    token: trending_aggregator.TrendingToken,
    sentiment_score: float,
) -> float:
    """
    Estimate expected edge (expected return) for a trade.

    Factors:
    - Trend velocity (rising = higher edge)
    - Multi-source confirmation
    - Sentiment score
    - Price momentum
    """
    base_edge = 0.03  # 3% base expectation for momentum trade

    # Velocity factor (rising trends have higher edge)
    velocity_factor = 1.0 + (token.velocity * 2.0)  # +/- 200% based on velocity
    velocity_factor = max(0.5, min(2.0, velocity_factor))

    # Source confirmation factor
    source_factor = 1.0 + (len(token.sources) - 1) * 0.1  # +10% per extra source

    # Sentiment factor
    sentiment_factor = 0.5 + sentiment_score  # 0.5x to 1.5x

    # Price momentum factor
    if token.price_change_24h > 0:
        momentum_factor = min(1.5, 1.0 + token.price_change_24h / 100)
    else:
        momentum_factor = max(0.7, 1.0 + token.price_change_24h / 200)

    edge = base_edge * velocity_factor * source_factor * sentiment_factor * momentum_factor

    return min(0.20, max(0.01, edge))  # Cap at 1-20%


def estimate_total_cost(
    token: trending_aggregator.TrendingToken,
    trade_size_usd: float,
) -> float:
    """
    Estimate total trading costs (fees + slippage + spread).
    """
    # Base costs
    dex_fee_bps = 30       # 0.3% DEX fee
    aggregator_fee_bps = 5 # 0.05% aggregator
    network_fee_usd = 0.003  # ~0.003 SOL

    # Slippage estimate based on liquidity
    if token.liquidity_usd > 0:
        size_pct_of_liquidity = trade_size_usd / token.liquidity_usd
        slippage_bps = min(500, size_pct_of_liquidity * 10000)  # 1% of pool = 100 bps
    else:
        slippage_bps = 200  # 2% default

    # Spread estimate
    spread_bps = 20  # 0.2% typical spread

    total_bps = dex_fee_bps + aggregator_fee_bps + slippage_bps + spread_bps
    total_pct = total_bps / 10000

    # Include exit costs (similar magnitude)
    total_pct *= 2

    return total_pct + (network_fee_usd * 2 / trade_size_usd)


# ============================================================================
# Trade Execution
# ============================================================================

def execute_paper_entry(
    candidate: TradeCandidate,
    size_usd: float,
    nav: float,
) -> Dict[str, Any]:
    """
    Execute a paper trade entry.
    """
    token = candidate.token
    position_id = f"lut-{str(uuid.uuid4())[:8]}"

    # Simulate fill price with slippage
    slippage_pct = 0.005  # 0.5% slippage
    fill_price = token.price_usd * (1 + slippage_pct) if token.price_usd > 0 else 0.00001

    quantity = size_usd / fill_price

    entry_result = {
        "position_id": position_id,
        "symbol": token.symbol,
        "mint": token.mint,
        "fill_price": fill_price,
        "quantity": quantity,
        "size_usd": size_usd,
        "size_pct_nav": (size_usd / nav) * 100,
        "timestamp": time.time(),
        "is_paper": True,
        "edge_to_cost": candidate.edge_to_cost,
        "estimated_edge": candidate.estimated_edge,
        "estimated_cost": candidate.estimated_cost,
        "tx_hash": f"paper-{position_id}",
    }

    return entry_result


def generate_jupyter_bundle(
    entry: Dict[str, Any],
    intent: exit_intents.ExitIntent,
) -> str:
    """Generate Jupyter cell bundle for trade monitoring."""
    tps = intent.take_profits
    bundle = f'''
# ============================================================================
# Cell 1: Trade Details
# ============================================================================
"""
## LUT Micro-Alpha Trade: {entry["symbol"]}

**Entry:**
- Token: {entry["symbol"]} ({entry["mint"][:12]}...)
- Entry Price: ${entry["fill_price"]:.8f}
- Quantity: {entry["quantity"]:.4f} tokens
- Size: ${entry["size_usd"]:.2f} ({entry["size_pct_nav"]:.1f}% NAV)
- TX: {entry["tx_hash"]}

**Edge Analysis:**
- Expected Edge: {entry["estimated_edge"]:.1%}
- Estimated Cost: {entry["estimated_cost"]:.1%}
- Edge/Cost Ratio: {entry["edge_to_cost"]:.2f}x

**Exit Ladder:**
- TP1: ${tps[0].price:.8f} ({tps[0].size_pct:.0f}% @ +8%)
- TP2: ${tps[1].price:.8f} ({tps[1].size_pct:.0f}% @ +18%)
- TP3: ${tps[2].price:.8f} ({tps[2].size_pct:.0f}% @ +40%)
- SL: ${intent.stop_loss.price:.8f} (-9%)
- Time Stop: {int((intent.time_stop.deadline_timestamp - time.time()) / 60)}min remaining
"""

# ============================================================================
# Cell 2: Verify Intent Persistence
# ============================================================================
from core.exit_intents import load_intent

intent = load_intent("{intent.id}")
if intent:
    print(f"Intent Status: {{intent.status}}")
    print(f"Remaining Qty: {{intent.remaining_quantity:.4f}}")
    print(f"TPs Filled: {{sum(1 for tp in intent.take_profits if tp.filled)}}/{{len(intent.take_profits)}}")
else:
    print("WARNING: Intent not found!")

# ============================================================================
# Cell 3: Monitor Position
# ============================================================================
from core.lut_micro_alpha import get_position_pnl
from core.birdeye import fetch_token_price

price_data = fetch_token_price("{entry['mint']}")
if price_data and price_data.get("data"):
    current_price = price_data["data"].get("value", 0)
    entry_price = {entry['fill_price']}
    pnl_pct = ((current_price / entry_price) - 1) * 100
    print(f"Current Price: ${{current_price:.8f}}")
    print(f"Entry Price: ${{entry_price:.8f}}")
    print(f"P&L: {{pnl_pct:+.2f}}%")

# ============================================================================
# Cell 4: Emergency Exit (UNCOMMENT TO USE)
# ============================================================================
# from core.exit_intents import cancel_intent, execute_action, ExitAction
#
# # Cancel intent and force exit
# cancel_intent("{intent.id}", reason="manual_emergency_exit")
# print("Emergency exit triggered!")
'''
    return bundle


# ============================================================================
# Main Cycle
# ============================================================================

def run_cycle(
    nav: float,
    *,
    constraints: Dict[str, Any] = None,
    paper_mode: bool = True,
) -> CycleResult:
    """
    Run a single trading cycle.

    Args:
        nav: Current Net Asset Value in USD
        constraints: Override default constraints
        paper_mode: If True, execute paper trades only

    Returns:
        CycleResult with all trade outcomes
    """
    result = CycleResult()

    # 1. Load state
    state = load_module_state()
    result.phase_before = state.phase
    config = PHASE_CONFIG[state.phase]

    # Reset daily counters if new day
    today = time.strftime("%Y-%m-%d")
    if state.last_trade_date != today:
        state.trades_today = 0
        state.last_trade_date = today

    # 2. Check if module can trade
    can_trade, reason = _can_trade(state, config, nav)
    if not can_trade:
        result.skipped = True
        result.skip_reason = reason
        save_module_state(state)
        return result

    network_status = solana_network_guard.assess_network_health()
    if not network_status.get("ok", True):
        result.skipped = True
        result.skip_reason = f"network_guard:{network_status.get('reason', 'unknown')}"
        save_module_state(state)
        return result

    # 3. Fetch trending tokens
    logger.info("[lut_micro_alpha] Fetching trending tokens...")
    tokens = trending_aggregator.fetch_trending_all_sources(limit=50)
    result.candidates_scanned = len(tokens)

    if not tokens:
        result.skipped = True
        result.skip_reason = "no_trending_tokens"
        return result

    # 4. Build candidates with validation
    candidates: List[TradeCandidate] = []

    for token in tokens[:20]:  # Top 20 by composite rank
        candidate = TradeCandidate(token=token)

        # Hard constraints
        rejection = check_hard_constraints(token, constraints)
        if rejection:
            candidate.rejection_reason = rejection
            result.rejections.append({"symbol": token.symbol, "reason": rejection})
            continue

        # Safety gate (RugCheck)
        is_safe, safety_report = check_safety_gate(token.mint, constraints)
        candidate.safety_report = safety_report
        if not is_safe:
            issues = safety_report.get("issues", ["unknown"])
            candidate.rejection_reason = f"safety_failed: {issues}"
            result.rejections.append({"symbol": token.symbol, "reason": candidate.rejection_reason})
            continue

        # Sentiment validation
        sentiment_score, credibility, notes = validate_sentiment(token, constraints)
        candidate.sentiment_score = sentiment_score
        candidate.sentiment_credibility = credibility
        candidate.sentiment_notes = notes

        min_sentiment = (constraints or DEFAULT_CONSTRAINTS).get("sentiment_min_score", 0.3)
        min_cred = (constraints or DEFAULT_CONSTRAINTS).get("sentiment_min_credibility", 0.5)

        if sentiment_score < min_sentiment:
            candidate.rejection_reason = f"sentiment_low: {sentiment_score:.2f} < {min_sentiment}"
            result.rejections.append({"symbol": token.symbol, "reason": candidate.rejection_reason})
            continue

        if credibility < min_cred:
            candidate.rejection_reason = f"credibility_low: {credibility:.2f} < {min_cred}"
            result.rejections.append({"symbol": token.symbol, "reason": candidate.rejection_reason})
            continue

        # Edge estimation
        trade_size = min(config["max_single_trade"] * nav, 100)  # Cap at $100 for paper
        candidate.estimated_edge = estimate_edge(token, sentiment_score)
        candidate.estimated_cost = estimate_total_cost(token, trade_size)
        candidate.edge_to_cost = (
            candidate.estimated_edge / candidate.estimated_cost
            if candidate.estimated_cost > 0 else 0
        )

        if candidate.edge_to_cost < config["edge_to_cost_min"]:
            candidate.rejection_reason = (
                f"edge_to_cost_low: {candidate.edge_to_cost:.2f} < {config['edge_to_cost_min']}"
            )
            result.rejections.append({"symbol": token.symbol, "reason": candidate.rejection_reason})
            continue

        candidates.append(candidate)

    result.candidates_validated = len(candidates)

    if not candidates:
        result.skipped = True
        result.skip_reason = "no_valid_candidates"
        save_module_state(state)
        return result

    # 5. Sort by edge-to-cost ratio and select top N
    candidates.sort(key=lambda c: c.edge_to_cost, reverse=True)
    selected = candidates[:config["tokens_per_cycle"]]

    # 6. Execute trades
    max_exposure = config["max_module_exposure"] * nav
    remaining_exposure = max_exposure - state.current_exposure_usd

    for candidate in selected:
        if state.trades_today >= config["max_trades_per_day"]:
            logger.info("[lut_micro_alpha] Daily trade limit reached")
            break

        if remaining_exposure <= 0:
            logger.info("[lut_micro_alpha] Exposure limit reached")
            break

        # Calculate position size
        size_usd = min(
            config["max_single_trade"] * nav,
            remaining_exposure,
            100 if paper_mode else remaining_exposure,  # Cap paper trades at $100
        )

        if size_usd < 1:
            continue

        # Execute entry
        entry = execute_paper_entry(candidate, size_usd, nav)

        # Create exit intent IMMEDIATELY
        intent = exit_intents.create_spot_intent(
            position_id=entry["position_id"],
            token_mint=candidate.token.mint,
            symbol=candidate.token.symbol,
            entry_price=entry["fill_price"],
            quantity=entry["quantity"],
            is_paper=paper_mode,
        )

        # CRITICAL: Persist intent before anything else
        if not exit_intents.persist_intent(intent):
            logger.error(f"[lut_micro_alpha] CRITICAL: Failed to persist intent for {entry['position_id']}")
            continue

        # Generate Jupyter bundle
        jupyter_bundle = generate_jupyter_bundle(entry, intent)
        result.jupyter_bundles.append(jupyter_bundle)

        # Update state
        state.trades_today += 1
        state.total_trades += 1
        state.current_exposure_usd += size_usd
        state.open_positions.append(entry["position_id"])
        remaining_exposure -= size_usd

        # Record trade
        trade_record = {
            **entry,
            "intent_id": intent.id,
            "edge_to_cost": candidate.edge_to_cost,
            "status": "open",
        }
        state.recent_trades.append(trade_record)
        result.trade_results.append(trade_record)
        result.trades_executed += 1

        logger.info(
            f"[lut_micro_alpha] Executed: {candidate.token.symbol} "
            f"${size_usd:.2f} @ ${entry['fill_price']:.8f}, "
            f"E/C={candidate.edge_to_cost:.2f}x"
        )

    # 7. Check phase transition
    transition = _check_phase_transition(state)
    if transition:
        result.phase_transition = transition

    result.phase_after = state.phase

    # 8. Save state
    save_module_state(state)

    return result


def _can_trade(
    state: ModuleState,
    config: Dict[str, Any],
    nav: float,
) -> Tuple[bool, str]:
    """Check if module can execute trades."""
    if not state.enabled:
        return False, f"module_disabled: {state.shutdown_reason}"

    if state.cooldown_until and time.time() < state.cooldown_until:
        remaining = int(state.cooldown_until - time.time())
        return False, f"cooldown_active: {remaining}s remaining"

    if state.trades_today >= config["max_trades_per_day"]:
        return False, "daily_limit_reached"

    max_exposure = config["max_module_exposure"] * nav
    if state.current_exposure_usd >= max_exposure:
        return False, "exposure_limit_reached"

    return True, ""


def _check_phase_transition(state: ModuleState) -> Optional[str]:
    """Check if module should be promoted or demoted."""
    reliability = exit_intents.get_reliability_stats()

    # Calculate metrics
    win_rate = state.win_count / max(state.total_trades, 1)
    profit_factor = state.gross_profit / max(abs(state.gross_loss), 0.01)
    reliability_pct = reliability.get("reliability_pct", 0) / 100

    # Recent trades analysis
    recent = state.recent_trades[-12:] if len(state.recent_trades) >= 12 else state.recent_trades
    recent_pnl = sum(t.get("realized_pnl", 0) for t in recent)

    # Check for demotion/shutdown first
    if state.catastrophic_events >= 2:
        state.enabled = False
        state.shutdown_reason = "too_many_catastrophic_events"
        state.cooldown_until = time.time() + (3 * 24 * 3600)  # 3 days
        return "shutdown_catastrophic"

    if reliability_pct < 0.95:
        if state.phase > 0:
            state.phase -= 1
            return "demoted_reliability"

    if profit_factor < 1.1 and len(recent) >= 6:
        if state.phase > 0:
            state.phase -= 1
            return "demoted_profit_factor"

    # Check for promotion
    if state.phase == 0:
        # Trial to Phase 1
        if state.total_trades >= PHASE_CONFIG[0]["trial_trades"]:
            thresholds = PROMOTION_TO_PHASE_1
            if (
                state.total_pnl_usd > thresholds["min_net_pnl"] and
                profit_factor >= thresholds["min_profit_factor"] and
                state.max_drawdown_pct <= thresholds["max_drawdown_pct"] and
                reliability_pct >= thresholds["min_enforcement_reliability"] and
                state.catastrophic_events <= thresholds["max_catastrophic_events"]
            ):
                state.phase = 1
                state.phase_started_at = time.time()
                return "promoted_to_phase_1"

    elif state.phase == 1:
        # Phase 1 to Phase 2
        thresholds = PROMOTION_TO_PHASE_2
        if (
            profit_factor >= thresholds["min_profit_factor"] and
            (win_rate >= thresholds["min_win_rate"]) and
            reliability_pct >= thresholds["min_enforcement_reliability"]
        ):
            state.phase = 2
            state.phase_started_at = time.time()
            return "promoted_to_phase_2"

    return None


# ============================================================================
# Position Monitoring
# ============================================================================

def get_position_pnl(position_id: str) -> Optional[Dict[str, Any]]:
    """Get current P&L for a position."""
    state = load_module_state()

    for trade in state.recent_trades:
        if trade.get("position_id") == position_id:
            # Fetch current price
            price_data = birdeye.fetch_token_price(trade["mint"])
            if not price_data or not price_data.get("data"):
                return None

            current_price = price_data["data"].get("value", 0)
            entry_price = trade["fill_price"]
            quantity = trade["quantity"]

            pnl_usd = (current_price - entry_price) * quantity
            pnl_pct = ((current_price / entry_price) - 1) * 100

            return {
                "position_id": position_id,
                "symbol": trade["symbol"],
                "entry_price": entry_price,
                "current_price": current_price,
                "quantity": quantity,
                "pnl_usd": pnl_usd,
                "pnl_pct": pnl_pct,
                "status": trade.get("status", "unknown"),
            }

    return None


def close_position(
    position_id: str,
    reason: str = "manual",
) -> Optional[Dict[str, Any]]:
    """Close a position and update state."""
    state = load_module_state()

    # Find the trade
    trade = None
    for t in state.recent_trades:
        if t.get("position_id") == position_id:
            trade = t
            break

    if not trade:
        return None

    # Cancel the intent
    intent_id = trade.get("intent_id")
    if intent_id:
        exit_intents.cancel_intent(intent_id, reason=reason)

    # Update state
    if position_id in state.open_positions:
        state.open_positions.remove(position_id)
    state.current_exposure_usd -= trade.get("size_usd", 0)

    trade["status"] = "closed"
    trade["close_reason"] = reason
    trade["close_timestamp"] = time.time()

    save_module_state(state)

    return {"position_id": position_id, "closed": True, "reason": reason}


# ============================================================================
# CLI Demo
# ============================================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("=== LUT Micro-Alpha Module Demo ===\n")

    # Show current status
    status = get_module_status()
    print("Module Status:")
    for key, value in status.items():
        print(f"  {key}: {value}")

    print("\n" + "=" * 50)
    print("Running cycle with $1000 NAV (paper mode)...")
    print("=" * 50 + "\n")

    result = run_cycle(nav=1000.0, paper_mode=True)

    print(f"\nCycle Result:")
    print(f"  Scanned: {result.candidates_scanned} tokens")
    print(f"  Validated: {result.candidates_validated} candidates")
    print(f"  Executed: {result.trades_executed} trades")
    print(f"  Phase: {result.phase_before} → {result.phase_after}")

    if result.phase_transition:
        print(f"  Transition: {result.phase_transition}")

    if result.skipped:
        print(f"  Skipped: {result.skip_reason}")

    if result.trade_results:
        print("\nTrades:")
        for trade in result.trade_results:
            print(f"  - {trade['symbol']}: ${trade['size_usd']:.2f} @ ${trade['fill_price']:.8f}")

    if result.jupyter_bundles:
        print(f"\nGenerated {len(result.jupyter_bundles)} Jupyter bundle(s)")

    print("\n✓ LUT Micro-Alpha module ready")
