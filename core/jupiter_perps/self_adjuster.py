"""Self-adjusting trade outcome tracker for Jupiter Perps.

Learns from trade outcomes to:
    1. Tune signal source weights (EMA of win rate per source)
    2. Apply half-Kelly position sizing per source
    3. Calibrate confidence scores against actual results
    4. Adjust regime-specific exposure

All state is persisted in SQLite (same DB as event journal).
Tuning runs every 24h or after N closed trades, whichever comes first.
"""

from __future__ import annotations

import json
import logging
import math
import os
import time
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass
class TunerConfig:
    min_trades: int = 10            # minimum trades before tuning kicks in
    learning_rate: float = 0.10     # EMA learning rate for weight updates
    min_weight: float = 0.10        # floor weight for any source
    tune_interval_hours: float = 24.0
    tune_after_trades: int = 10     # also tune after this many new trades
    sqlite_path: str = ""

    @classmethod
    def from_env(cls) -> TunerConfig:
        return cls(
            min_trades=int(os.environ.get("PERPS_TUNER_MIN_TRADES", "10")),
            learning_rate=float(os.environ.get("PERPS_TUNER_LEARNING_RATE", "0.10")),
            min_weight=float(os.environ.get("PERPS_TUNER_MIN_WEIGHT", "0.10")),
            sqlite_path=os.environ.get("PERPS_SQLITE_PATH", ""),
        )


# ---------------------------------------------------------------------------
# Trade outcome
# ---------------------------------------------------------------------------


@dataclass
class TradeOutcome:
    """Record of a completed trade."""

    source: str              # signal source that triggered this trade
    asset: str
    direction: str           # "long" | "short"
    confidence_at_entry: float
    entry_price: float
    exit_price: float
    pnl_usd: float
    pnl_pct: float
    hold_hours: float
    fees_usd: float
    exit_trigger: str        # "take_profit", "stop_loss", "trailing_stop", etc.
    regime: str = "ranging"  # market regime at entry
    timestamp: float = field(default_factory=time.time)

    @property
    def is_win(self) -> bool:
        return self.pnl_usd > 0


# ---------------------------------------------------------------------------
# Tune result
# ---------------------------------------------------------------------------


@dataclass
class TuneResult:
    """Summary of a tuning cycle."""

    total_trades: int
    source_stats: dict[str, dict[str, float]]  # source -> {win_rate, avg_pnl, weight, size_mult}
    regime_stats: dict[str, dict[str, float]]   # regime -> {win_rate, avg_pnl}
    weights_updated: bool
    timestamp: float = field(default_factory=time.time)


# ---------------------------------------------------------------------------
# Auto-tuner
# ---------------------------------------------------------------------------

# Default source weights (match ai_signal_bridge.py)
_DEFAULT_WEIGHTS: dict[str, float] = {
    "grok_perps": 0.50,
    "momentum": 0.30,
    "aggregate": 0.20,
}


class PerpsAutoTuner:
    """Learns from trade outcomes and tunes signal weights + position sizing.

    State is kept in-memory and persisted to SQLite.
    All methods are synchronous (called from async context via the runner).
    """

    def __init__(self, config: TunerConfig | None = None) -> None:
        self._config = config or TunerConfig.from_env()
        self._outcomes: list[TradeOutcome] = []
        self._source_weights: dict[str, float] = dict(_DEFAULT_WEIGHTS)
        self._size_multipliers: dict[str, float] = {}
        self._confidence_calibration: dict[str, float] = {}
        self._last_tune_time: float = time.time()
        self._trades_since_tune: int = 0
        self._loaded = False

    # --- Public API ---

    def record_outcome(self, outcome: TradeOutcome) -> None:
        """Record a completed trade outcome."""
        self._outcomes.append(outcome)
        self._trades_since_tune += 1

        log.info(
            "Trade outcome recorded: %s %s %s pnl=%+.2f%% exit=%s source=%s",
            outcome.asset, outcome.direction,
            "WIN" if outcome.is_win else "LOSS",
            outcome.pnl_pct, outcome.exit_trigger, outcome.source,
        )

        # Auto-tune if threshold reached
        if self._should_tune():
            self.tune()

    def get_weights(self) -> dict[str, float]:
        """Get current signal source weights."""
        return dict(self._source_weights)

    def get_position_size_multiplier(self, source: str) -> float:
        """Get half-Kelly position size multiplier for a source.

        Returns a value between 0.25 and 1.5.
        Before enough data, returns 1.0 (neutral).
        """
        # Extract base source name from consensus strings
        base_source = self._extract_base_source(source)
        return self._size_multipliers.get(base_source, 1.0)

    def get_calibrated_confidence(self, source: str, raw_confidence: float) -> float:
        """Apply confidence calibration based on historical accuracy."""
        base_source = self._extract_base_source(source)
        cal_factor = self._confidence_calibration.get(base_source, 1.0)
        return max(0.0, min(1.0, raw_confidence * cal_factor))

    def tune(self) -> TuneResult:
        """Run the tuning cycle. Updates weights, size multipliers, and calibration."""
        cfg = self._config

        source_stats: dict[str, dict[str, float]] = {}
        regime_stats: dict[str, dict[str, float]] = {}

        if len(self._outcomes) < cfg.min_trades:
            log.info(
                "Tuner: %d trades < %d minimum — skipping tune",
                len(self._outcomes), cfg.min_trades,
            )
            return TuneResult(
                total_trades=len(self._outcomes),
                source_stats={},
                regime_stats={},
                weights_updated=False,
            )

        # --- Per-source statistics ---
        by_source: dict[str, list[TradeOutcome]] = {}
        for o in self._outcomes:
            base = self._extract_base_source(o.source)
            by_source.setdefault(base, []).append(o)

        for source, trades in by_source.items():
            wins = sum(1 for t in trades if t.is_win)
            total = len(trades)
            win_rate = wins / total if total > 0 else 0.5

            avg_pnl = sum(t.pnl_pct for t in trades) / total if total > 0 else 0.0
            avg_win = sum(t.pnl_pct for t in trades if t.is_win) / max(wins, 1)
            avg_loss = abs(sum(t.pnl_pct for t in trades if not t.is_win) / max(total - wins, 1))

            # EMA weight update
            if source in self._source_weights:
                old_w = self._source_weights[source]
                # Higher win rate -> higher weight
                target_w = win_rate  # normalize later
                new_w = old_w + cfg.learning_rate * (target_w - old_w)
                self._source_weights[source] = max(cfg.min_weight, new_w)

            # Half-Kelly position sizing
            if avg_win > 0 and total >= 5:
                kelly = (win_rate * avg_win - (1 - win_rate) * avg_loss) / avg_win
                half_kelly = kelly / 2.0
                self._size_multipliers[source] = max(0.25, min(half_kelly, 1.5))
            else:
                self._size_multipliers[source] = 1.0

            # Confidence calibration
            avg_claimed_conf = sum(t.confidence_at_entry for t in trades) / total if total > 0 else 0.5
            if avg_claimed_conf > 0.1:
                cal = win_rate / avg_claimed_conf
                self._confidence_calibration[source] = max(0.5, min(cal, 1.5))

            source_stats[source] = {
                "win_rate": round(win_rate, 3),
                "avg_pnl_pct": round(avg_pnl, 3),
                "avg_win_pct": round(avg_win, 3),
                "avg_loss_pct": round(avg_loss, 3),
                "trades": total,
                "weight": round(self._source_weights.get(source, 0.0), 4),
                "size_mult": round(self._size_multipliers.get(source, 1.0), 3),
                "cal_factor": round(self._confidence_calibration.get(source, 1.0), 3),
            }

        # --- Normalize weights to sum to 1.0 ---
        total_w = sum(self._source_weights.values())
        if total_w > 0:
            self._source_weights = {
                k: v / total_w for k, v in self._source_weights.items()
            }

        # --- Per-regime statistics ---
        by_regime: dict[str, list[TradeOutcome]] = {}
        for o in self._outcomes:
            by_regime.setdefault(o.regime, []).append(o)

        for regime, trades in by_regime.items():
            wins = sum(1 for t in trades if t.is_win)
            total = len(trades)
            regime_stats[regime] = {
                "win_rate": round(wins / total if total > 0 else 0.5, 3),
                "avg_pnl_pct": round(sum(t.pnl_pct for t in trades) / total if total > 0 else 0.0, 3),
                "trades": total,
            }

        self._last_tune_time = time.time()
        self._trades_since_tune = 0

        result = TuneResult(
            total_trades=len(self._outcomes),
            source_stats=source_stats,
            regime_stats=regime_stats,
            weights_updated=True,
        )

        log.info(
            "Tuner updated: %d trades, weights=%s, multipliers=%s",
            len(self._outcomes),
            {k: f"{v:.3f}" for k, v in self._source_weights.items()},
            {k: f"{v:.2f}" for k, v in self._size_multipliers.items()},
        )

        return result

    def get_summary(self) -> dict[str, Any]:
        """Get a human-readable summary of tuner state."""
        return {
            "total_outcomes": len(self._outcomes),
            "source_weights": {k: round(v, 4) for k, v in self._source_weights.items()},
            "size_multipliers": {k: round(v, 3) for k, v in self._size_multipliers.items()},
            "confidence_calibration": {k: round(v, 3) for k, v in self._confidence_calibration.items()},
            "trades_since_tune": self._trades_since_tune,
            "last_tune_age_hours": round((time.time() - self._last_tune_time) / 3600, 1),
        }

    # --- Persistence (SQLite) ---

    async def load_from_sqlite(self, sqlite_conn: Any) -> None:
        """Load historical outcomes from SQLite on startup."""
        if sqlite_conn is None:
            return

        try:
            await sqlite_conn.execute(
                """
                CREATE TABLE IF NOT EXISTS trade_outcomes (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    source          TEXT NOT NULL,
                    asset           TEXT NOT NULL,
                    direction       TEXT NOT NULL,
                    confidence      REAL NOT NULL,
                    entry_price     REAL NOT NULL,
                    exit_price      REAL NOT NULL,
                    pnl_usd         REAL NOT NULL,
                    pnl_pct         REAL NOT NULL,
                    hold_hours      REAL NOT NULL,
                    fees_usd        REAL NOT NULL,
                    exit_trigger    TEXT NOT NULL,
                    regime          TEXT NOT NULL DEFAULT 'ranging',
                    created_at      REAL NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_outcomes_source ON trade_outcomes (source);
                CREATE INDEX IF NOT EXISTS idx_outcomes_created ON trade_outcomes (created_at);
                """
            )
            await sqlite_conn.commit()

            cursor = await sqlite_conn.execute(
                "SELECT * FROM trade_outcomes ORDER BY created_at ASC"
            )
            rows = await cursor.fetchall()

            for row in rows:
                self._outcomes.append(TradeOutcome(
                    source=row["source"],
                    asset=row["asset"],
                    direction=row["direction"],
                    confidence_at_entry=row["confidence"],
                    entry_price=row["entry_price"],
                    exit_price=row["exit_price"],
                    pnl_usd=row["pnl_usd"],
                    pnl_pct=row["pnl_pct"],
                    hold_hours=row["hold_hours"],
                    fees_usd=row["fees_usd"],
                    exit_trigger=row["exit_trigger"],
                    regime=row["regime"],
                    timestamp=row["created_at"],
                ))

            self._loaded = True
            log.info("Tuner loaded %d historical outcomes from SQLite", len(self._outcomes))

            # Run initial tune if we have enough data
            if len(self._outcomes) >= self._config.min_trades:
                self.tune()

        except Exception:
            log.debug("Failed to load tuner state from SQLite", exc_info=True)

    async def save_outcome_to_sqlite(self, outcome: TradeOutcome, sqlite_conn: Any) -> None:
        """Persist a single outcome to SQLite."""
        if sqlite_conn is None:
            return

        try:
            await sqlite_conn.execute(
                """
                INSERT INTO trade_outcomes
                    (source, asset, direction, confidence, entry_price, exit_price,
                     pnl_usd, pnl_pct, hold_hours, fees_usd, exit_trigger, regime, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    outcome.source, outcome.asset, outcome.direction,
                    outcome.confidence_at_entry, outcome.entry_price, outcome.exit_price,
                    outcome.pnl_usd, outcome.pnl_pct, outcome.hold_hours,
                    outcome.fees_usd, outcome.exit_trigger, outcome.regime,
                    outcome.timestamp,
                ),
            )
            await sqlite_conn.commit()
        except Exception:
            log.debug("Failed to save outcome to SQLite", exc_info=True)

    # --- Internal ---

    def _should_tune(self) -> bool:
        """Check if it's time to run a tuning cycle."""
        if len(self._outcomes) < self._config.min_trades:
            return False

        hours_since = (time.time() - self._last_tune_time) / 3600.0
        if hours_since >= self._config.tune_interval_hours:
            return True

        if self._trades_since_tune >= self._config.tune_after_trades:
            return True

        return False

    @staticmethod
    def _extract_base_source(source: str) -> str:
        """Extract the base source name from consensus strings.

        'consensus(grok_perps,momentum)' -> 'grok_perps' (highest weight)
        'grok_perps' -> 'grok_perps'
        """
        if source.startswith("consensus("):
            inner = source[len("consensus("):-1]
            parts = inner.split(",")
            # Return the first source (typically highest weight)
            return parts[0].strip() if parts else source
        return source
