"""
Trading Decision Matrix - Unified Strategy Registry and Decision Framework
===========================================================================

Central hub connecting all trading strategies with unified metadata.
Enables:
- Model-agnostic strategy understanding
- Consistent behavior across different LLMs/IDEs
- Automatic training data generation
- Unified decision flow

AI CONTEXT: Any AI reading this repo should understand the complete trading system
by reading this file + the exported training data.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Type

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[1]
TRAINING_DATA_DIR = ROOT / "data" / "training_data"


# =============================================================================
# Strategy Categories - Unified Classification
# =============================================================================

class StrategyCategory(str, Enum):
    """Primary strategy categories for classification."""
    ARBITRAGE = "arbitrage"
    MOMENTUM = "momentum"
    MEAN_REVERSION = "mean_reversion"
    MARKET_NEUTRAL = "market_neutral"
    AI_ADAPTIVE = "ai_adaptive"


class MarketRegime(str, Enum):
    """Market regime types for strategy matching."""
    TRENDING = "trending"
    CHOPPING = "chopping"
    VOLATILE = "volatile"
    CALM = "calm"


class HoldingPeriod(str, Enum):
    """Expected position holding duration."""
    SUB_SECOND = "sub_second"
    MINUTES = "minutes"
    HOURS = "hours"
    DAYS = "days"
    WEEKS = "weeks"


class LatencyClass(str, Enum):
    """Execution latency requirements."""
    LOW_MS = "low_ms"       # Sub-100ms required
    MEDIUM_S = "medium_s"   # 1-10 seconds acceptable
    HIGH_MIN = "high_min"   # Minutes acceptable


# =============================================================================
# Strategy Definition - Complete Metadata
# =============================================================================

@dataclass
class StrategyDefinition:
    """
    Complete strategy definition with all metadata needed for:
    - AI understanding
    - Decision matrix matching
    - Training data generation
    - Risk assessment
    
    AI NOTE: Each strategy has explicit regime_fit, failure_modes, and risk_controls
    to enable intelligent selection.
    """
    id: str                         # "STRAT-001"
    name: str                       # "TrendFollower"
    category: StrategyCategory
    implementation: str             # "core.trading_strategies.TrendFollower"
    
    # What market conditions this strategy works in
    regime_fit: List[MarketRegime] = field(default_factory=list)
    
    # What data this strategy needs
    data_requirements: List[str] = field(default_factory=list)
    
    # How fast execution needs to be
    latency_class: LatencyClass = LatencyClass.MEDIUM_S
    
    # Expected holding duration
    holding_period: HoldingPeriod = HoldingPeriod.HOURS
    
    # What can go wrong - critical for AI risk assessment
    failure_modes: List[str] = field(default_factory=list)
    
    # What controls mitigate risks
    risk_controls: List[str] = field(default_factory=list)
    
    # Human-readable description for AI understanding
    description: str = ""
    
    # Entry/exit conditions for AI to understand strategy logic
    entry_conditions: List[str] = field(default_factory=list)
    exit_conditions: List[str] = field(default_factory=list)
    
    # Priority for selection (P0 = highest)
    priority: int = 1
    
    # Whether this is safe for paper trading
    paper_safe: bool = True
    
    # Example trade for AI training
    example_trade: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to serializable dict for training data."""
        data = asdict(self)
        data["category"] = self.category.value
        data["regime_fit"] = [r.value for r in self.regime_fit]
        data["latency_class"] = self.latency_class.value
        data["holding_period"] = self.holding_period.value
        return data
    
    def matches_regime(self, regime: str) -> bool:
        """Check if strategy fits the given market regime."""
        regime_lower = regime.lower()
        for fit in self.regime_fit:
            if fit.value == regime_lower:
                return True
        return False


# =============================================================================
# Trading Decision Matrix - Central Registry
# =============================================================================

class TradingDecisionMatrix:
    """
    Unified decision framework connecting all trading strategies.
    
    AI CONTEXT:
    This class is the central hub for all trading decisions. Any AI working
    with this codebase should:
    1. Call get_decision_matrix() to get the singleton instance
    2. Use select_strategy_for_regime() to pick the right strategy
    3. Use export_training_data() to understand all available strategies
    4. Use get_system_prompt() to get unified context for AI models
    
    SAFETY:
    - All strategies have paper_safe=True by default
    - Real execution requires explicit human approval
    - The matrix never executes trades, only recommends strategies
    """
    
    def __init__(self):
        self._strategies: Dict[str, StrategyDefinition] = {}
        self._regime_index: Dict[str, List[str]] = {}  # regime -> [strategy_ids]
        self._initialized = False
        
    def register_strategy(self, definition: StrategyDefinition) -> None:
        """
        Register a strategy with the decision matrix.
        
        Args:
            definition: Complete strategy metadata
        """
        self._strategies[definition.id] = definition
        
        # Index by regime for fast lookup
        for regime in definition.regime_fit:
            regime_key = regime.value
            if regime_key not in self._regime_index:
                self._regime_index[regime_key] = []
            if definition.id not in self._regime_index[regime_key]:
                self._regime_index[regime_key].append(definition.id)
        
        logger.debug(f"Registered strategy: {definition.id} ({definition.name})")
    
    def get_strategy(self, strategy_id: str) -> Optional[StrategyDefinition]:
        """Get strategy by ID."""
        return self._strategies.get(strategy_id)
    
    def get_strategy_by_name(self, name: str) -> Optional[StrategyDefinition]:
        """Get strategy by name."""
        for strat in self._strategies.values():
            if strat.name.lower() == name.lower():
                return strat
        return None
    
    def get_all_strategies(self) -> List[StrategyDefinition]:
        """Get all registered strategies."""
        return list(self._strategies.values())
    
    def select_strategy_for_regime(
        self,
        regime: str,
        snapshot: Optional[Any] = None,
    ) -> Optional[StrategyDefinition]:
        """
        Select the best strategy for current market regime.
        
        Args:
            regime: Market regime ("trending", "chopping", etc.)
            snapshot: Optional MarketSnapshot for additional context
            
        Returns:
            Best matching StrategyDefinition or None
        """
        regime_lower = regime.lower()
        
        # Get all strategies that fit this regime
        matching_ids = self._regime_index.get(regime_lower, [])
        if not matching_ids:
            # Fallback: return highest priority strategy
            all_strats = sorted(
                self._strategies.values(),
                key=lambda s: s.priority
            )
            return all_strats[0] if all_strats else None
        
        # Sort by priority and return best
        matching = [self._strategies[sid] for sid in matching_ids if sid in self._strategies]
        if not matching:
            return None
        
        matching.sort(key=lambda s: s.priority)
        return matching[0]
    
    def get_strategies_for_category(
        self,
        category: StrategyCategory
    ) -> List[StrategyDefinition]:
        """Get all strategies in a category."""
        return [s for s in self._strategies.values() if s.category == category]
    
    def export_training_data(self) -> Dict[str, Any]:
        """
        Export complete training data for AI model understanding.
        
        Returns:
            Dict with strategies, categories, regime mapping, and system prompt
        """
        return {
            "export_timestamp": datetime.utcnow().isoformat(),
            "system_name": "LifeOS Trading Decision Matrix",
            "version": "2.0.0",
            "strategies": [s.to_dict() for s in self._strategies.values()],
            "categories": [c.value for c in StrategyCategory],
            "regimes": [r.value for r in MarketRegime],
            "regime_strategy_mapping": self._regime_index,
            "system_prompt": self.get_system_prompt(),
            "decision_flow": self.get_decision_flow(),
        }
    
    def get_system_prompt(self) -> str:
        """
        Generate model-agnostic system prompt for AI context.
        
        This prompt should be included in any AI model (local or cloud)
        to ensure consistent understanding of the trading system.
        """
        strategy_list = []
        for cat in StrategyCategory:
            strats = self.get_strategies_for_category(cat)
            if strats:
                names = ", ".join(s.name for s in strats)
                strategy_list.append(f"- **{cat.value.title()}**: {names}")
        
        return f"""# LifeOS Trading System Context

## Overview
You are an AI assistant working with the LifeOS trading system. This system includes
{len(self._strategies)} trading strategies across {len(StrategyCategory)} categories.

## Available Strategies
{chr(10).join(strategy_list)}

## Decision Flow
1. **Regime Detection**: Classify market as trending, chopping, volatile, or calm
2. **Strategy Selection**: Pick strategy matching current regime
3. **Signal Generation**: Get buy/sell/hold signal from strategy
4. **Gate Check**: Verify risk limits, confidence, velocity thresholds
5. **Execution Plan**: Build entry/stop/take-profit levels

## Solana-Specific Context
- Primary execution: Jupiter aggregator for best swap rates
- MEV protection: Jito bundles for front-running protection
- RPC failover: Helius → QuickNode → public endpoints
- Always simulate transactions before execution

## Safety Rules (CRITICAL)
1. NEVER execute live trades without explicit human approval
2. Always use paper/simulation mode for testing
3. Circuit breaker triggers at 10% drawdown
4. All trades require minimum 0.55 confidence score
5. Position size capped at 8% of capital

## Key Files
- `core/trading_decision_matrix.py` - This file, central registry
- `core/logic_core.py` - 5-phase decision engine
- `core/trading_strategies.py` - Basic strategies
- `core/trading_strategies_advanced.py` - Advanced strategies
- `core/solana_execution.py` - Solana swap execution
- `core/exit_intents.py` - Take profit/stop loss management
"""
    
    def get_decision_flow(self) -> List[Dict[str, str]]:
        """Get structured decision flow for AI understanding."""
        return [
            {
                "phase": "1. Sentiment Classification",
                "description": "Analyze volume, volatility, fear/greed index",
                "output": "Bullish / Neutral / Bearish",
            },
            {
                "phase": "2. Regime Detection",
                "description": "Linear regression on price series, R² threshold",
                "output": "trending / chopping",
            },
            {
                "phase": "3. Strategy Selection",
                "description": "Match regime to strategy from decision matrix",
                "output": "Strategy name (e.g., TrendFollower)",
            },
            {
                "phase": "4. Signal Generation",
                "description": "Run strategy on price data, get trade signal",
                "output": "BUY / SELL / HOLD + confidence",
            },
            {
                "phase": "5. Gate Check",
                "description": "Validate risk limits, ROI velocity, confidence",
                "output": "PASS / FAIL with reasons",
            },
            {
                "phase": "6. Execution Planning",
                "description": "Calculate entry, stop, take-profit levels",
                "output": "ExecutionPlan with prices",
            },
        ]
    
    def save_training_data(self, path: Optional[Path] = None) -> Path:
        """Save training data to JSON file."""
        if path is None:
            TRAINING_DATA_DIR.mkdir(parents=True, exist_ok=True)
            path = TRAINING_DATA_DIR / "strategy_catalog.json"
        
        data = self.export_training_data()
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
        
        logger.info(f"Saved training data to {path}")
        return path


# =============================================================================
# Singleton Instance and Initialization
# =============================================================================

_decision_matrix: Optional[TradingDecisionMatrix] = None


def get_decision_matrix() -> TradingDecisionMatrix:
    """
    Get the global decision matrix instance.
    
    Initializes with all registered strategies on first call.
    """
    global _decision_matrix
    if _decision_matrix is None:
        _decision_matrix = TradingDecisionMatrix()
        _register_all_strategies(_decision_matrix)
    return _decision_matrix


def _register_all_strategies(matrix: TradingDecisionMatrix) -> None:
    """Register all trading strategies with the decision matrix."""
    
    # ==========================================================================
    # Basic Strategies (from trading_strategies.py)
    # ==========================================================================
    
    matrix.register_strategy(StrategyDefinition(
        id="STRAT-001",
        name="TrendFollower",
        category=StrategyCategory.MOMENTUM,
        implementation="core.trading_strategies.TrendFollower",
        description="Moving average crossover strategy. Buys when short MA crosses above long MA (golden cross), sells on death cross.",
        regime_fit=[MarketRegime.TRENDING],
        data_requirements=["ohlcv"],
        latency_class=LatencyClass.MEDIUM_S,
        holding_period=HoldingPeriod.HOURS,
        failure_modes=[
            "whipsaw_in_ranging_market",
            "late_entry_near_reversal",
            "false_breakout_signals",
        ],
        risk_controls=[
            "adx_filter_above_25",
            "stop_loss_1_5_atr",
            "max_position_8_pct",
        ],
        entry_conditions=[
            "short_ma > long_ma",
            "adx > 25 (recommended)",
        ],
        exit_conditions=[
            "short_ma < long_ma",
            "stop_loss_hit",
            "take_profit_hit",
        ],
        priority=1,
        example_trade={
            "symbol": "SOL/USDC",
            "signal": "BUY",
            "confidence": 0.72,
            "expected_roi_pct": 0.035,
            "expected_time_minutes": 120,
        },
    ))
    
    matrix.register_strategy(StrategyDefinition(
        id="STRAT-002",
        name="MeanReversion",
        category=StrategyCategory.MEAN_REVERSION,
        implementation="core.trading_strategies.MeanReversion",
        description="Bollinger Bands + RSI strategy. Buys when price below lower band AND RSI < 30 (oversold). Sells when above upper band AND RSI > 70.",
        regime_fit=[MarketRegime.CHOPPING, MarketRegime.CALM],
        data_requirements=["ohlcv"],
        latency_class=LatencyClass.MEDIUM_S,
        holding_period=HoldingPeriod.HOURS,
        failure_modes=[
            "trend_continuation_losses",
            "extended_oversold_conditions",
            "volatility_expansion_stops",
        ],
        risk_controls=[
            "trend_filter_exclusion",
            "max_hold_time_4_hours",
            "tight_stop_loss",
        ],
        entry_conditions=[
            "price < lower_bollinger_band",
            "rsi < 30",
        ],
        exit_conditions=[
            "price > upper_bollinger_band",
            "rsi > 70",
            "stop_loss_hit",
        ],
        priority=1,
        example_trade={
            "symbol": "BONK/USDC",
            "signal": "BUY",
            "confidence": 0.68,
            "expected_roi_pct": 0.025,
            "expected_time_minutes": 90,
        },
    ))
    
    matrix.register_strategy(StrategyDefinition(
        id="STRAT-003",
        name="DCABot",
        category=StrategyCategory.MARKET_NEUTRAL,
        implementation="core.trading_strategies.DCABot",
        description="Dollar-cost averaging with optional smart DCA (buy more on dips). Generates BUY signals at regular intervals regardless of price.",
        regime_fit=[MarketRegime.TRENDING, MarketRegime.CHOPPING, MarketRegime.VOLATILE, MarketRegime.CALM],
        data_requirements=["ohlcv"],
        latency_class=LatencyClass.HIGH_MIN,
        holding_period=HoldingPeriod.WEEKS,
        failure_modes=[
            "prolonged_bear_market",
            "opportunity_cost_in_bull",
        ],
        risk_controls=[
            "fixed_schedule",
            "portfolio_rebalancing",
        ],
        entry_conditions=[
            "time_interval_elapsed",
            "smart_dca: price_below_average (optional)",
        ],
        exit_conditions=[
            "manual_exit",
            "target_reached",
        ],
        priority=2,
        example_trade={
            "symbol": "SOL/USDC",
            "signal": "BUY",
            "confidence": 0.95,
            "expected_roi_pct": 0.01,
            "expected_time_minutes": 1440,
        },
    ))
    
    matrix.register_strategy(StrategyDefinition(
        id="STRAT-004",
        name="ArbitrageScanner",
        category=StrategyCategory.ARBITRAGE,
        implementation="core.trading_strategies.ArbitrageScanner",
        description="Cross-DEX arbitrage scanner. Compares prices across multiple DEXs to find profitable spreads.",
        regime_fit=[MarketRegime.VOLATILE],
        data_requirements=["multi_dex_prices"],
        latency_class=LatencyClass.LOW_MS,
        holding_period=HoldingPeriod.SUB_SECOND,
        failure_modes=[
            "stale_price_execution",
            "slippage_exceeds_spread",
            "gas_cost_exceeds_profit",
        ],
        risk_controls=[
            "min_spread_0_5_pct",
            "max_slippage_0_3_pct",
            "simulation_before_execution",
        ],
        entry_conditions=[
            "price_spread > min_spread + fees",
            "sufficient_liquidity",
        ],
        exit_conditions=[
            "immediate_exit_after_arb",
        ],
        priority=1,
        example_trade={
            "symbol": "BONK",
            "signal": "ARBITRAGE",
            "confidence": 0.85,
            "expected_roi_pct": 0.008,
            "expected_time_minutes": 1,
        },
    ))
    
    # ==========================================================================
    # Advanced Strategies (from trading_strategies_advanced.py)
    # ==========================================================================
    
    matrix.register_strategy(StrategyDefinition(
        id="STRAT-005",
        name="TriangularArbitrage",
        category=StrategyCategory.ARBITRAGE,
        implementation="core.trading_strategies_advanced.TriangularArbitrage",
        description="Cross-rate exploitation (e.g., BTC→ETH→USDT→BTC). Exploits price discrepancies between three trading pairs.",
        regime_fit=[MarketRegime.TRENDING, MarketRegime.CHOPPING, MarketRegime.VOLATILE, MarketRegime.CALM],
        data_requirements=["multi_pair_prices"],
        latency_class=LatencyClass.LOW_MS,
        holding_period=HoldingPeriod.SUB_SECOND,
        failure_modes=[
            "execution_latency",
            "rate_stale_mid_execution",
            "insufficient_liquidity",
        ],
        risk_controls=[
            "min_profit_0_1_pct",
            "atomic_execution",
            "pre_simulation",
        ],
        entry_conditions=[
            "triangle_profit > fees + slippage",
        ],
        exit_conditions=[
            "immediate_completion",
        ],
        priority=0,  # P0 - highest priority
        example_trade={
            "path": ["USDT", "BTC", "ETH", "USDT"],
            "expected_profit_pct": 0.15,
        },
    ))
    
    matrix.register_strategy(StrategyDefinition(
        id="STRAT-006",
        name="GridTrader",
        category=StrategyCategory.MARKET_NEUTRAL,
        implementation="core.trading_strategies_advanced.GridTrader",
        description="Grid trading for sideways markets. Places buy orders below current price and sell orders above, profiting from oscillations.",
        regime_fit=[MarketRegime.CHOPPING, MarketRegime.CALM],
        data_requirements=["ohlcv"],
        latency_class=LatencyClass.MEDIUM_S,
        holding_period=HoldingPeriod.DAYS,
        failure_modes=[
            "trend_breakout_losses",
            "range_expansion",
            "capital_stuck_at_extremes",
        ],
        risk_controls=[
            "upper_lower_bounds",
            "volatility_filter",
            "max_grid_levels",
        ],
        entry_conditions=[
            "price_touches_grid_level",
        ],
        exit_conditions=[
            "opposite_grid_level_hit",
            "range_breakout",
        ],
        priority=1,
        example_trade={
            "symbol": "SOL/USDC",
            "grid_levels": 10,
            "upper_bound": 110,
            "lower_bound": 90,
        },
    ))
    
    matrix.register_strategy(StrategyDefinition(
        id="STRAT-007",
        name="BreakoutTrader",
        category=StrategyCategory.MOMENTUM,
        implementation="core.trading_strategies_advanced.BreakoutTrader",
        description="Detects when price breaks through support/resistance with volume confirmation. Enters on confirmed breakout.",
        regime_fit=[MarketRegime.TRENDING, MarketRegime.VOLATILE],
        data_requirements=["ohlcv", "volume"],
        latency_class=LatencyClass.MEDIUM_S,
        holding_period=HoldingPeriod.HOURS,
        failure_modes=[
            "false_breakout",
            "failed_continuation",
            "gap_reversals",
        ],
        risk_controls=[
            "volume_confirmation_1_5x",
            "confirmation_candles",
            "stop_below_breakout_level",
        ],
        entry_conditions=[
            "price > resistance",
            "volume > 1.5x average",
            "confirmation_candles >= 2",
        ],
        exit_conditions=[
            "trailing_stop",
            "target_reached",
            "reversal_signal",
        ],
        priority=1,
        example_trade={
            "symbol": "SOL/USDC",
            "breakout_level": 100,
            "signal": "BUY",
            "confidence": 0.70,
        },
    ))
    
    matrix.register_strategy(StrategyDefinition(
        id="STRAT-008",
        name="MarketMaker",
        category=StrategyCategory.MARKET_NEUTRAL,
        implementation="core.trading_strategies_advanced.MarketMaker",
        description="Bid-ask spread capture. Provides liquidity by placing orders on both sides, profiting from the spread.",
        regime_fit=[MarketRegime.CHOPPING, MarketRegime.CALM],
        data_requirements=["orderbook_l2", "ohlcv"],
        latency_class=LatencyClass.LOW_MS,
        holding_period=HoldingPeriod.MINUTES,
        failure_modes=[
            "adverse_selection",
            "inventory_risk",
            "trend_directional_losses",
        ],
        risk_controls=[
            "inventory_skew",
            "crash_mode_exit",
            "max_position_size",
        ],
        entry_conditions=[
            "spread > min_spread",
            "inventory_within_limits",
        ],
        exit_conditions=[
            "inventory_limit_hit",
            "volatility_spike",
        ],
        priority=2,
    ))
    
    # ==========================================================================
    # AI/Adaptive Strategies
    # ==========================================================================
    
    matrix.register_strategy(StrategyDefinition(
        id="STRAT-009",
        name="RegimeDetector",
        category=StrategyCategory.AI_ADAPTIVE,
        implementation="core.ml_regime_detector.RegimeDetector",
        description="ML-based market regime classification. Uses historical patterns to identify trending vs ranging conditions.",
        regime_fit=[MarketRegime.TRENDING, MarketRegime.CHOPPING, MarketRegime.VOLATILE, MarketRegime.CALM],
        data_requirements=["ohlcv", "volume"],
        latency_class=LatencyClass.MEDIUM_S,
        holding_period=HoldingPeriod.HOURS,
        failure_modes=[
            "regime_transition_lag",
            "overfitting_to_history",
        ],
        risk_controls=[
            "ensemble_voting",
            "confidence_threshold",
        ],
        priority=0,  # P0 - used for all other strategy selection
    ))
    
    matrix.register_strategy(StrategyDefinition(
        id="STRAT-010",
        name="SentimentAnalyzer",
        category=StrategyCategory.AI_ADAPTIVE,
        implementation="core.trading_strategies.SentimentAnalyzer",
        description="NLP-based sentiment analysis from social/news. Adjusts position sizing based on sentiment signals.",
        regime_fit=[MarketRegime.VOLATILE],
        data_requirements=["social_sentiment", "news"],
        latency_class=LatencyClass.HIGH_MIN,
        holding_period=HoldingPeriod.HOURS,
        failure_modes=[
            "fake_news",
            "sentiment_lag",
            "bot_manipulation",
        ],
        risk_controls=[
            "multi_source_validation",
            "position_scaling",
        ],
        priority=2,
    ))
    
    logger.info(f"Registered {len(matrix.get_all_strategies())} strategies in decision matrix")


# =============================================================================
# Convenience Functions
# =============================================================================

def select_strategy(regime: str, snapshot: Optional[Any] = None) -> Optional[str]:
    """
    Select best strategy for regime - convenience wrapper.
    
    Args:
        regime: Market regime ("trending", "chopping", etc.)
        snapshot: Optional market snapshot
        
    Returns:
        Strategy name or None
    """
    matrix = get_decision_matrix()
    definition = matrix.select_strategy_for_regime(regime, snapshot)
    return definition.name if definition else None


def get_all_strategy_names() -> List[str]:
    """Get list of all registered strategy names."""
    matrix = get_decision_matrix()
    return [s.name for s in matrix.get_all_strategies()]


def export_training_data_to_file() -> Path:
    """Export training data to default location."""
    matrix = get_decision_matrix()
    return matrix.save_training_data()


# =============================================================================
# Self-Test
# =============================================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    print("Testing Trading Decision Matrix...")
    matrix = get_decision_matrix()
    
    print(f"\nRegistered strategies: {len(matrix.get_all_strategies())}")
    for strat in matrix.get_all_strategies():
        print(f"  - {strat.id}: {strat.name} ({strat.category.value})")
    
    print("\n--- Strategy Selection Tests ---")
    for regime in ["trending", "chopping", "volatile"]:
        selected = matrix.select_strategy_for_regime(regime)
        print(f"Regime '{regime}' -> {selected.name if selected else 'None'}")
    
    print("\n--- Exporting Training Data ---")
    path = matrix.save_training_data()
    print(f"Saved to: {path}")
    
    print("\n--- System Prompt Preview ---")
    prompt = matrix.get_system_prompt()
    print(prompt[:500] + "...")
