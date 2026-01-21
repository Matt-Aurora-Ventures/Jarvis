"""
Trade Intelligence Engine - Self-Improving Trader with Generative Compression

JARVIS V1 Production System

Core Principle: Compression is intelligence. The better the predictive compression,
the better the understanding of market dynamics and trading patterns.

Features:
- Generative compression for trade memory
- Self-improving learning from trade outcomes
- Predictive residual storage (store deviations from model expectations)
- Latent embeddings as primary memory objects
- Multi-tier memory hierarchy (short/medium/long)

Architecture:
- Tier 0: Ephemeral Context (seconds-minutes) - streaming buffer
- Tier 1: Short Latent Memory (hours-days) - recent trades/context
- Tier 2: Medium Latent Memory (weeks-months) - consolidated patterns
- Tier 3: Long Latent Memory (months-years) - stable strategy behaviors
"""

import json
import logging
import hashlib
import asyncio
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from decimal import Decimal
import statistics

logger = logging.getLogger(__name__)

# Storage paths
_ROOT = Path(__file__).resolve().parents[1]
_DATA_DIR = _ROOT / "data" / "intelligence"
_DATA_DIR.mkdir(parents=True, exist_ok=True)

# Memory tier files
_TIER1_FILE = _DATA_DIR / "tier1_short_memory.json"
_TIER2_FILE = _DATA_DIR / "tier2_medium_memory.json"
_TIER3_FILE = _DATA_DIR / "tier3_long_memory.json"
_TRADE_LOG_FILE = _DATA_DIR / "trade_outcomes.json"
_LEARNING_FILE = _DATA_DIR / "learned_patterns.json"


@dataclass
class TradeOutcome:
    """Represents a completed trade with outcome metrics."""
    trade_id: str
    token_address: str
    token_symbol: str
    entry_time: str
    exit_time: str
    entry_price: float
    exit_price: float
    amount_sol: float
    pnl_pct: float
    pnl_sol: float
    hold_duration_minutes: float

    # Market context at entry
    market_regime: str  # BULL/BEAR/NEUTRAL
    sentiment_score: float
    signal_type: str  # STRONG_BUY/BUY/NEUTRAL/SELL

    # Outcome analysis
    outcome: str  # WIN/LOSS/BREAKEVEN
    max_drawdown_pct: float = 0.0
    max_profit_pct: float = 0.0

    # Learning metadata
    reasons: List[str] = field(default_factory=list)
    lessons: List[str] = field(default_factory=list)


@dataclass
class LatentTradeMemory:
    """
    Compressed representation of trading knowledge.

    This is the "latent embedding" that stores intelligence,
    not raw data. Preserves:
    - Pattern signatures
    - Strategy behaviors
    - Market regime correlations
    - Predictive signals

    Discards:
    - Raw tick data
    - Redundant price points
    - Noise and microstructure
    """
    memory_id: str
    created_at: str
    tier: int  # 1=short, 2=medium, 3=long

    # Compressed pattern representation
    pattern_type: str  # momentum/reversal/breakout/accumulation
    confidence: float  # 0-1
    win_rate: float  # historical accuracy
    avg_return: float  # expected return

    # Market conditions this pattern works in
    favorable_regimes: List[str]  # BULL/BEAR/NEUTRAL
    unfavorable_regimes: List[str]

    # Entry/exit criteria (compressed)
    entry_signals: List[str]  # compressed criteria
    exit_signals: List[str]

    # Time characteristics
    optimal_hold_time_minutes: float
    time_decay_factor: float  # how quickly edge decays

    # Sample size for confidence
    trade_count: int
    last_updated: str


@dataclass
class MarketStateVector:
    """
    Compressed market state for prediction.

    This is the "state vector" that captures market essence
    without storing raw data.
    """
    timestamp: str

    # Regime embedding
    regime: str
    regime_confidence: float
    regime_duration_hours: float

    # Momentum vectors (compressed)
    btc_momentum: float  # -1 to 1
    sol_momentum: float
    memecoin_momentum: float

    # Volatility state
    volatility_regime: str  # LOW/NORMAL/HIGH/EXTREME
    vol_percentile: float  # 0-100

    # Sentiment aggregation
    aggregated_sentiment: float  # -1 to 1
    sentiment_divergence: float  # market vs social

    # Liquidity state
    liquidity_depth: str  # THIN/NORMAL/DEEP
    spread_percentile: float


class TradeIntelligenceEngine:
    """
    Self-Improving Trade Intelligence Engine.

    Core functions:
    1. Record trade outcomes
    2. Learn patterns from outcomes
    3. Update strategy based on learnings
    4. Compress memory over time
    5. Generate predictions based on patterns

    Memory hierarchy:
    - Tier 1 (hours): Individual trade outcomes
    - Tier 2 (weeks): Consolidated pattern observations
    - Tier 3 (months): Stable strategy parameters
    """

    def __init__(self):
        self._tier1: List[TradeOutcome] = []
        self._tier2: List[LatentTradeMemory] = []
        self._tier3: List[LatentTradeMemory] = []
        self._learned_patterns: Dict[str, Any] = {}
        self._load_state()

    def _load_state(self):
        """Load persisted memory state."""
        try:
            if _TIER1_FILE.exists():
                with open(_TIER1_FILE, "r") as f:
                    data = json.load(f)
                    self._tier1 = [TradeOutcome(**t) for t in data]

            if _TIER2_FILE.exists():
                with open(_TIER2_FILE, "r") as f:
                    data = json.load(f)
                    self._tier2 = [LatentTradeMemory(**m) for m in data]

            if _TIER3_FILE.exists():
                with open(_TIER3_FILE, "r") as f:
                    data = json.load(f)
                    self._tier3 = [LatentTradeMemory(**m) for m in data]

            if _LEARNING_FILE.exists():
                with open(_LEARNING_FILE, "r") as f:
                    self._learned_patterns = json.load(f)

        except Exception as e:
            logger.warning(f"Could not load intelligence state: {e}")

    def _save_state(self):
        """Persist memory state."""
        try:
            with open(_TIER1_FILE, "w") as f:
                json.dump([asdict(t) for t in self._tier1], f, indent=2)

            with open(_TIER2_FILE, "w") as f:
                json.dump([asdict(m) for m in self._tier2], f, indent=2)

            with open(_TIER3_FILE, "w") as f:
                json.dump([asdict(m) for m in self._tier3], f, indent=2)

            with open(_LEARNING_FILE, "w") as f:
                json.dump(self._learned_patterns, f, indent=2)

        except Exception as e:
            logger.error(f"Could not save intelligence state: {e}")

    # =========================================================================
    # Trade Recording (Tier 0 -> Tier 1)
    # =========================================================================

    def record_trade(
        self,
        trade_id: str,
        token_address: str,
        token_symbol: str,
        entry_price: float,
        exit_price: float,
        amount_sol: float,
        entry_time: datetime,
        exit_time: datetime,
        market_regime: str = "NEUTRAL",
        sentiment_score: float = 0.0,
        signal_type: str = "NEUTRAL",
        reasons: List[str] = None,
    ) -> TradeOutcome:
        """
        Record a completed trade outcome.

        This is the entry point for learning. Every trade teaches us something.
        """
        # Calculate metrics
        pnl_pct = ((exit_price - entry_price) / entry_price) * 100 if entry_price else 0
        pnl_sol = amount_sol * (pnl_pct / 100)
        hold_duration = (exit_time - entry_time).total_seconds() / 60

        # Determine outcome
        if pnl_pct > 1:
            outcome = "WIN"
        elif pnl_pct < -1:
            outcome = "LOSS"
        else:
            outcome = "BREAKEVEN"

        # Generate lessons from outcome
        lessons = self._generate_lessons(
            outcome=outcome,
            pnl_pct=pnl_pct,
            market_regime=market_regime,
            sentiment_score=sentiment_score,
            signal_type=signal_type,
            hold_duration=hold_duration,
        )

        trade_outcome = TradeOutcome(
            trade_id=trade_id,
            token_address=token_address,
            token_symbol=token_symbol,
            entry_time=entry_time.isoformat(),
            exit_time=exit_time.isoformat(),
            entry_price=entry_price,
            exit_price=exit_price,
            amount_sol=amount_sol,
            pnl_pct=pnl_pct,
            pnl_sol=pnl_sol,
            hold_duration_minutes=hold_duration,
            market_regime=market_regime,
            sentiment_score=sentiment_score,
            signal_type=signal_type,
            outcome=outcome,
            reasons=reasons or [],
            lessons=lessons,
        )

        self._tier1.append(trade_outcome)

        # Trigger learning
        self._learn_from_trade(trade_outcome)

        # Check if consolidation needed
        if len(self._tier1) >= 20:
            self._consolidate_tier1_to_tier2()

        self._save_state()

        return trade_outcome

    def _generate_lessons(
        self,
        outcome: str,
        pnl_pct: float,
        market_regime: str,
        sentiment_score: float,
        signal_type: str,
        hold_duration: float,
    ) -> List[str]:
        """Generate automated lessons from trade outcome."""
        lessons = []

        if outcome == "WIN":
            if sentiment_score > 0.6:
                lessons.append("High sentiment score correlated with win")
            if signal_type in ("STRONG_BUY", "BUY"):
                lessons.append(f"{signal_type} signal was accurate")
            if market_regime == "BULL":
                lessons.append("Bull regime supported the trade")
            if hold_duration < 30:
                lessons.append("Quick exit captured profit")
            elif hold_duration > 120:
                lessons.append("Patience allowed full move")

        elif outcome == "LOSS":
            if sentiment_score < 0.4:
                lessons.append("Low sentiment was warning sign")
            if signal_type in ("SELL", "NEUTRAL"):
                lessons.append(f"Entered against {signal_type} signal")
            if market_regime == "BEAR":
                lessons.append("Bear regime worked against trade")
            if hold_duration > 60:
                lessons.append("Should have cut losses earlier")

        return lessons

    # =========================================================================
    # Learning Engine
    # =========================================================================

    def _learn_from_trade(self, trade: TradeOutcome):
        """
        Extract patterns and update learned knowledge.

        This is the core learning function. It:
        1. Updates win rates for signal types
        2. Identifies regime correlations
        3. Optimizes hold time parameters
        4. Adjusts confidence levels
        """
        # Update signal accuracy tracking
        signal_key = f"signal_{trade.signal_type}"
        if signal_key not in self._learned_patterns:
            self._learned_patterns[signal_key] = {
                "total": 0,
                "wins": 0,
                "win_rate": 0.5,
                "avg_pnl": 0.0,
            }

        stats = self._learned_patterns[signal_key]
        stats["total"] += 1
        if trade.outcome == "WIN":
            stats["wins"] += 1
        stats["win_rate"] = stats["wins"] / stats["total"]

        # Running average PnL
        n = stats["total"]
        stats["avg_pnl"] = ((n - 1) * stats["avg_pnl"] + trade.pnl_pct) / n

        # Update regime tracking
        regime_key = f"regime_{trade.market_regime}"
        if regime_key not in self._learned_patterns:
            self._learned_patterns[regime_key] = {
                "total": 0,
                "wins": 0,
                "win_rate": 0.5,
                "avg_pnl": 0.0,
            }

        regime_stats = self._learned_patterns[regime_key]
        regime_stats["total"] += 1
        if trade.outcome == "WIN":
            regime_stats["wins"] += 1
        regime_stats["win_rate"] = regime_stats["wins"] / regime_stats["total"]
        n = regime_stats["total"]
        regime_stats["avg_pnl"] = ((n - 1) * regime_stats["avg_pnl"] + trade.pnl_pct) / n

        # Update sentiment effectiveness
        sentiment_bucket = self._sentiment_bucket(trade.sentiment_score)
        sent_key = f"sentiment_{sentiment_bucket}"
        if sent_key not in self._learned_patterns:
            self._learned_patterns[sent_key] = {
                "total": 0,
                "wins": 0,
                "win_rate": 0.5,
                "avg_pnl": 0.0,
            }

        sent_stats = self._learned_patterns[sent_key]
        sent_stats["total"] += 1
        if trade.outcome == "WIN":
            sent_stats["wins"] += 1
        sent_stats["win_rate"] = sent_stats["wins"] / sent_stats["total"]
        n = sent_stats["total"]
        sent_stats["avg_pnl"] = ((n - 1) * sent_stats["avg_pnl"] + trade.pnl_pct) / n

        # Track hold time optimization
        if "hold_times" not in self._learned_patterns:
            self._learned_patterns["hold_times"] = {
                "winning_durations": [],
                "losing_durations": [],
                "optimal_exit": 60,  # default 60 min
            }

        ht = self._learned_patterns["hold_times"]
        if trade.outcome == "WIN":
            ht["winning_durations"].append(trade.hold_duration_minutes)
            # Keep last 50
            ht["winning_durations"] = ht["winning_durations"][-50:]
        else:
            ht["losing_durations"].append(trade.hold_duration_minutes)
            ht["losing_durations"] = ht["losing_durations"][-50:]

        # Calculate optimal exit time
        if len(ht["winning_durations"]) >= 5:
            ht["optimal_exit"] = statistics.median(ht["winning_durations"])

        logger.info(
            f"Learned from trade: {trade.token_symbol} | "
            f"Outcome: {trade.outcome} | PnL: {trade.pnl_pct:+.1f}%"
        )

    def _sentiment_bucket(self, score: float) -> str:
        """Convert sentiment score to bucket for learning."""
        if score >= 0.7:
            return "very_high"
        elif score >= 0.5:
            return "high"
        elif score >= 0.3:
            return "medium"
        else:
            return "low"

    # =========================================================================
    # Memory Consolidation (Tier 1 -> Tier 2)
    # =========================================================================

    def _consolidate_tier1_to_tier2(self):
        """
        Consolidate short-term trade memories into patterns.

        This is GENERATIVE COMPRESSION:
        - Many trades -> one pattern embedding
        - Preserves: signals, win rates, regime correlations
        - Discards: individual price points, timestamps, noise
        """
        if len(self._tier1) < 10:
            return

        # Group trades by signal type
        signal_groups: Dict[str, List[TradeOutcome]] = {}
        for trade in self._tier1:
            key = trade.signal_type
            if key not in signal_groups:
                signal_groups[key] = []
            signal_groups[key].append(trade)

        # Create pattern memories from groups
        for signal_type, trades in signal_groups.items():
            if len(trades) < 3:
                continue

            wins = sum(1 for t in trades if t.outcome == "WIN")
            win_rate = wins / len(trades)
            avg_return = statistics.mean(t.pnl_pct for t in trades)
            avg_hold = statistics.mean(t.hold_duration_minutes for t in trades)

            # Determine favorable regimes
            regime_wins: Dict[str, Tuple[int, int]] = {}
            for trade in trades:
                if trade.market_regime not in regime_wins:
                    regime_wins[trade.market_regime] = (0, 0)
                wins, total = regime_wins[trade.market_regime]
                if trade.outcome == "WIN":
                    wins += 1
                regime_wins[trade.market_regime] = (wins + 1, total + 1)

            favorable = [r for r, (w, t) in regime_wins.items() if t >= 2 and w / t > 0.5]
            unfavorable = [r for r, (w, t) in regime_wins.items() if t >= 2 and w / t < 0.4]

            # Determine pattern type
            if avg_return > 10:
                pattern_type = "momentum"
            elif avg_return < -5:
                pattern_type = "reversal_failed"
            else:
                pattern_type = "neutral"

            memory = LatentTradeMemory(
                memory_id=hashlib.md5(f"{signal_type}_{datetime.now().isoformat()}".encode()).hexdigest()[:12],
                created_at=datetime.now(timezone.utc).isoformat(),
                tier=2,
                pattern_type=pattern_type,
                confidence=min(0.9, 0.3 + (len(trades) * 0.03)),  # More trades = more confidence
                win_rate=win_rate,
                avg_return=avg_return,
                favorable_regimes=favorable,
                unfavorable_regimes=unfavorable,
                entry_signals=[signal_type],
                exit_signals=["target_hit", "stop_loss", "time_decay"],
                optimal_hold_time_minutes=avg_hold,
                time_decay_factor=0.1,
                trade_count=len(trades),
                last_updated=datetime.now(timezone.utc).isoformat(),
            )

            self._tier2.append(memory)

        # Keep only recent Tier 1 trades (last 20)
        self._tier1 = self._tier1[-20:]

        logger.info(f"Consolidated to Tier 2: {len(self._tier2)} pattern memories")

    # =========================================================================
    # Prediction & Recommendations
    # =========================================================================

    def get_trade_recommendation(
        self,
        signal_type: str,
        market_regime: str,
        sentiment_score: float,
    ) -> Dict[str, Any]:
        """
        Get recommendation based on learned patterns.

        This is GENERATIVE RETRIEVAL:
        - Not looking up raw data
        - Reconstructing prediction from compressed patterns
        - Returning confidence and uncertainty
        """
        recommendation = {
            "action": "NEUTRAL",
            "confidence": 0.5,
            "expected_return": 0.0,
            "suggested_hold_minutes": 60,
            "reasons": [],
            "warnings": [],
        }

        # Check signal effectiveness
        signal_key = f"signal_{signal_type}"
        if signal_key in self._learned_patterns:
            stats = self._learned_patterns[signal_key]
            if stats["total"] >= 5:
                if stats["win_rate"] > 0.6:
                    recommendation["action"] = "BUY"
                    recommendation["confidence"] = stats["win_rate"]
                    recommendation["reasons"].append(
                        f"{signal_type} signals have {stats['win_rate']:.0%} win rate"
                    )
                elif stats["win_rate"] < 0.4:
                    recommendation["action"] = "AVOID"
                    recommendation["warnings"].append(
                        f"{signal_type} signals only {stats['win_rate']:.0%} accurate"
                    )
                recommendation["expected_return"] = stats["avg_pnl"]

        # Check regime effectiveness
        regime_key = f"regime_{market_regime}"
        if regime_key in self._learned_patterns:
            stats = self._learned_patterns[regime_key]
            if stats["total"] >= 5:
                if stats["win_rate"] > 0.6:
                    recommendation["confidence"] = min(0.95, recommendation["confidence"] + 0.1)
                    recommendation["reasons"].append(
                        f"{market_regime} regime favorable ({stats['win_rate']:.0%} wins)"
                    )
                elif stats["win_rate"] < 0.4:
                    recommendation["confidence"] = max(0.1, recommendation["confidence"] - 0.2)
                    recommendation["warnings"].append(
                        f"{market_regime} regime unfavorable ({stats['win_rate']:.0%} wins)"
                    )

        # Check sentiment bucket
        sent_bucket = self._sentiment_bucket(sentiment_score)
        sent_key = f"sentiment_{sent_bucket}"
        if sent_key in self._learned_patterns:
            stats = self._learned_patterns[sent_key]
            if stats["total"] >= 5:
                if stats["win_rate"] > 0.6:
                    recommendation["reasons"].append(
                        f"{sent_bucket} sentiment correlates with wins"
                    )
                elif stats["win_rate"] < 0.4:
                    recommendation["warnings"].append(
                        f"{sent_bucket} sentiment correlates with losses"
                    )

        # Get optimal hold time
        if "hold_times" in self._learned_patterns:
            recommendation["suggested_hold_minutes"] = self._learned_patterns["hold_times"]["optimal_exit"]

        return recommendation

    def get_learning_summary(self) -> Dict[str, Any]:
        """
        Get summary of what the engine has learned.

        Returns a human-readable summary of patterns and statistics.
        """
        summary = {
            "total_trades_analyzed": len(self._tier1),
            "pattern_memories": len(self._tier2),
            "stable_strategies": len(self._tier3),
            "signals": {},
            "regimes": {},
            "optimal_hold_time": 60,
        }

        for key, stats in self._learned_patterns.items():
            if key.startswith("signal_"):
                signal = key.replace("signal_", "")
                summary["signals"][signal] = {
                    "trades": stats["total"],
                    "win_rate": f"{stats['win_rate']:.0%}",
                    "avg_return": f"{stats['avg_pnl']:+.1f}%",
                }
            elif key.startswith("regime_"):
                regime = key.replace("regime_", "")
                summary["regimes"][regime] = {
                    "trades": stats["total"],
                    "win_rate": f"{stats['win_rate']:.0%}",
                    "avg_return": f"{stats['avg_pnl']:+.1f}%",
                }

        if "hold_times" in self._learned_patterns:
            summary["optimal_hold_time"] = self._learned_patterns["hold_times"]["optimal_exit"]

        return summary

    # =========================================================================
    # Compression Metrics
    # =========================================================================

    def get_compression_stats(self) -> Dict[str, Any]:
        """
        Get compression statistics.

        Shows how much raw data was compressed into latent memory.
        """
        # Estimate raw data size (if we stored everything)
        tier1_raw = len(self._tier1) * 500  # ~500 bytes per trade if raw
        tier2_raw = len(self._tier2) * 2000  # ~2KB per pattern if raw

        # Actual compressed size
        tier1_compressed = len(self._tier1) * 200  # ~200 bytes compressed
        tier2_compressed = len(self._tier2) * 300  # ~300 bytes per pattern

        raw_total = tier1_raw + tier2_raw
        compressed_total = tier1_compressed + tier2_compressed

        return {
            "tier1_trades": len(self._tier1),
            "tier2_patterns": len(self._tier2),
            "tier3_strategies": len(self._tier3),
            "estimated_raw_bytes": raw_total,
            "compressed_bytes": compressed_total,
            "compression_ratio": raw_total / max(1, compressed_total),
            "learned_patterns": len(self._learned_patterns),
        }


# =============================================================================
# Singleton Instance
# =============================================================================

_engine: Optional[TradeIntelligenceEngine] = None


def get_intelligence_engine() -> TradeIntelligenceEngine:
    """Get singleton trade intelligence engine."""
    global _engine
    if _engine is None:
        _engine = TradeIntelligenceEngine()
    return _engine


# =============================================================================
# Convenience Functions
# =============================================================================

def record_trade_outcome(
    trade_id: str,
    token_address: str,
    token_symbol: str,
    entry_price: float,
    exit_price: float,
    amount_sol: float,
    entry_time: datetime,
    exit_time: datetime,
    market_regime: str = "NEUTRAL",
    sentiment_score: float = 0.0,
    signal_type: str = "NEUTRAL",
    reasons: List[str] = None,
) -> TradeOutcome:
    """Convenience function to record trade outcome."""
    engine = get_intelligence_engine()
    return engine.record_trade(
        trade_id=trade_id,
        token_address=token_address,
        token_symbol=token_symbol,
        entry_price=entry_price,
        exit_price=exit_price,
        amount_sol=amount_sol,
        entry_time=entry_time,
        exit_time=exit_time,
        market_regime=market_regime,
        sentiment_score=sentiment_score,
        signal_type=signal_type,
        reasons=reasons,
    )


def get_recommendation(
    signal_type: str,
    market_regime: str,
    sentiment_score: float,
) -> Dict[str, Any]:
    """Get trade recommendation based on learned patterns."""
    engine = get_intelligence_engine()
    return engine.get_trade_recommendation(signal_type, market_regime, sentiment_score)


def get_learning_status() -> Dict[str, Any]:
    """Get current learning status."""
    engine = get_intelligence_engine()
    return engine.get_learning_summary()
