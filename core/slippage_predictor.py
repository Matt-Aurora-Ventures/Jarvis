"""
Slippage Predictor - ML-based slippage estimation.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum
import json
import sqlite3
from pathlib import Path
from contextlib import contextmanager
import math
from collections import deque

logger = logging.getLogger(__name__)


class LiquidityTier(Enum):
    """Liquidity tier classification."""
    VERY_HIGH = "very_high"  # > $10M
    HIGH = "high"  # $1M - $10M
    MEDIUM = "medium"  # $100K - $1M
    LOW = "low"  # $10K - $100K
    VERY_LOW = "very_low"  # < $10K


class MarketCondition(Enum):
    """Market volatility condition."""
    CALM = "calm"
    NORMAL = "normal"
    VOLATILE = "volatile"
    EXTREME = "extreme"


@dataclass
class SlippageFeatures:
    """Features used for slippage prediction."""
    trade_size_usd: float
    liquidity_usd: float
    liquidity_tier: LiquidityTier
    spread_bps: float
    volatility_1h: float
    volatility_24h: float
    volume_24h: float
    price_impact_estimate: float
    market_condition: MarketCondition
    order_book_depth: float
    bid_ask_imbalance: float
    recent_large_trades: int
    timestamp: str


@dataclass
class SlippagePrediction:
    """Slippage prediction result."""
    symbol: str
    trade_size_usd: float
    predicted_slippage_bps: float
    predicted_slippage_pct: float
    confidence: float
    price_impact_bps: float
    market_impact_bps: float
    execution_cost_usd: float
    optimal_chunks: int
    chunk_delay_ms: int
    risk_level: str  # low, medium, high
    recommendation: str
    features: SlippageFeatures
    timestamp: str


@dataclass
class SlippageRecord:
    """Historical slippage record."""
    symbol: str
    trade_size_usd: float
    expected_price: float
    executed_price: float
    actual_slippage_bps: float
    predicted_slippage_bps: float
    prediction_error: float
    liquidity_at_time: float
    volatility_at_time: float
    timestamp: str


class SlippageDB:
    """SQLite storage for slippage data."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Initialize database schema."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS slippage_predictions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    trade_size_usd REAL,
                    predicted_slippage_bps REAL,
                    confidence REAL,
                    price_impact_bps REAL,
                    market_impact_bps REAL,
                    optimal_chunks INTEGER,
                    features_json TEXT,
                    timestamp TEXT
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS slippage_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    trade_size_usd REAL,
                    expected_price REAL,
                    executed_price REAL,
                    actual_slippage_bps REAL,
                    predicted_slippage_bps REAL,
                    prediction_error REAL,
                    liquidity_at_time REAL,
                    volatility_at_time REAL,
                    timestamp TEXT
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS liquidity_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    liquidity_usd REAL,
                    spread_bps REAL,
                    depth_1pct REAL,
                    depth_5pct REAL,
                    timestamp TEXT
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS model_parameters (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    base_slippage REAL,
                    size_coefficient REAL,
                    liquidity_coefficient REAL,
                    volatility_coefficient REAL,
                    updated_at TEXT
                )
            """)

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_slip_symbol ON slippage_predictions(symbol)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_records_symbol ON slippage_records(symbol)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_liq_symbol ON liquidity_snapshots(symbol)")

            conn.commit()

    @contextmanager
    def _get_connection(self):
        """Get database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()


class SlippagePredictor:
    """
    Predict and analyze trade slippage.

    Usage:
        predictor = SlippagePredictor()

        # Update market data
        predictor.update_liquidity("SOL", 1000000, 10)  # $1M liquidity, 10bps spread

        # Predict slippage
        prediction = predictor.predict("SOL", 10000)  # $10K trade
        print(f"Expected slippage: {prediction.predicted_slippage_bps}bps")

        # Record actual slippage for model improvement
        predictor.record_trade("SOL", 10000, 100.0, 99.85)
    """

    # Default model parameters (calibrated from historical data)
    DEFAULT_PARAMS = {
        'base_slippage': 5,  # Base slippage in bps
        'size_coefficient': 0.5,  # Slippage increase per $10K
        'liquidity_coefficient': -0.3,  # Slippage decrease per $100K liquidity
        'volatility_coefficient': 2.0,  # Slippage multiplier per 1% volatility
        'spread_coefficient': 0.5,  # Direct spread impact
        'imbalance_coefficient': 10,  # Order book imbalance impact
    }

    def __init__(self, db_path: Optional[Path] = None):
        db_path = db_path or Path(__file__).parent.parent / "data" / "slippage.db"
        self.db = SlippageDB(db_path)

        # In-memory caches
        self._liquidity_cache: Dict[str, Tuple[float, float, str]] = {}  # symbol -> (liquidity, spread, timestamp)
        self._volatility_cache: Dict[str, float] = {}
        self._recent_trades: Dict[str, deque] = {}  # symbol -> recent trade sizes
        self._model_params: Dict[str, Dict] = {}  # symbol -> parameters

        self._load_model_params()

    def _load_model_params(self):
        """Load model parameters from database."""
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM model_parameters ORDER BY updated_at DESC")

            for row in cursor.fetchall():
                self._model_params[row['symbol']] = {
                    'base_slippage': row['base_slippage'],
                    'size_coefficient': row['size_coefficient'],
                    'liquidity_coefficient': row['liquidity_coefficient'],
                    'volatility_coefficient': row['volatility_coefficient']
                }

    def update_liquidity(
        self,
        symbol: str,
        liquidity_usd: float,
        spread_bps: float,
        depth_1pct: float = 0,
        depth_5pct: float = 0
    ):
        """Update liquidity data for a symbol."""
        symbol = symbol.upper()
        timestamp = datetime.now(timezone.utc).isoformat()

        self._liquidity_cache[symbol] = (liquidity_usd, spread_bps, timestamp)

        # Save snapshot
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO liquidity_snapshots
                (symbol, liquidity_usd, spread_bps, depth_1pct, depth_5pct, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (symbol, liquidity_usd, spread_bps, depth_1pct, depth_5pct, timestamp))
            conn.commit()

    def update_volatility(self, symbol: str, volatility_pct: float):
        """Update volatility data for a symbol."""
        self._volatility_cache[symbol.upper()] = volatility_pct

    def get_liquidity_tier(self, liquidity_usd: float) -> LiquidityTier:
        """Classify liquidity tier."""
        if liquidity_usd >= 10_000_000:
            return LiquidityTier.VERY_HIGH
        elif liquidity_usd >= 1_000_000:
            return LiquidityTier.HIGH
        elif liquidity_usd >= 100_000:
            return LiquidityTier.MEDIUM
        elif liquidity_usd >= 10_000:
            return LiquidityTier.LOW
        else:
            return LiquidityTier.VERY_LOW

    def get_market_condition(self, volatility_pct: float) -> MarketCondition:
        """Classify market condition."""
        if volatility_pct < 1:
            return MarketCondition.CALM
        elif volatility_pct < 3:
            return MarketCondition.NORMAL
        elif volatility_pct < 7:
            return MarketCondition.VOLATILE
        else:
            return MarketCondition.EXTREME

    def predict(
        self,
        symbol: str,
        trade_size_usd: float,
        is_buy: bool = True,
        order_book_depth: float = 0,
        bid_ask_imbalance: float = 0
    ) -> SlippagePrediction:
        """Predict slippage for a trade."""
        symbol = symbol.upper()
        timestamp = datetime.now(timezone.utc).isoformat()

        # Get cached data
        liquidity_data = self._liquidity_cache.get(symbol, (100000, 20, timestamp))
        liquidity_usd, spread_bps, _ = liquidity_data
        volatility = self._volatility_cache.get(symbol, 2.0)

        # Get model parameters
        params = self._model_params.get(symbol, self.DEFAULT_PARAMS)

        # Build features
        features = SlippageFeatures(
            trade_size_usd=trade_size_usd,
            liquidity_usd=liquidity_usd,
            liquidity_tier=self.get_liquidity_tier(liquidity_usd),
            spread_bps=spread_bps,
            volatility_1h=volatility,
            volatility_24h=volatility * 1.5,  # Estimate
            volume_24h=liquidity_usd * 5,  # Estimate
            price_impact_estimate=self._estimate_price_impact(trade_size_usd, liquidity_usd),
            market_condition=self.get_market_condition(volatility),
            order_book_depth=order_book_depth,
            bid_ask_imbalance=bid_ask_imbalance,
            recent_large_trades=self._count_recent_large_trades(symbol),
            timestamp=timestamp
        )

        # Calculate slippage components
        base_slippage = params.get('base_slippage', 5)

        # Size impact: larger trades = more slippage
        size_impact = (trade_size_usd / 10000) * params.get('size_coefficient', 0.5)

        # Liquidity impact: more liquidity = less slippage
        liquidity_factor = math.log10(max(liquidity_usd / 100000, 0.1))
        liquidity_impact = liquidity_factor * params.get('liquidity_coefficient', -0.3) * base_slippage

        # Volatility impact
        volatility_impact = (volatility / 2) * params.get('volatility_coefficient', 2.0)

        # Spread impact
        spread_impact = spread_bps * params.get('spread_coefficient', 0.5)

        # Order book imbalance impact
        imbalance_impact = 0
        if bid_ask_imbalance != 0:
            # Positive imbalance (more bids) is bad for buys, good for sells
            direction_factor = 1 if is_buy else -1
            imbalance_impact = bid_ask_imbalance * direction_factor * params.get('imbalance_coefficient', 10)

        # Total predicted slippage
        predicted_bps = max(0, (
            base_slippage +
            size_impact +
            liquidity_impact +
            volatility_impact +
            spread_impact +
            imbalance_impact
        ))

        # Calculate price and market impact separately
        price_impact_bps = features.price_impact_estimate * 10000
        market_impact_bps = predicted_bps - price_impact_bps

        # Execution cost
        execution_cost = (predicted_bps / 10000) * trade_size_usd

        # Calculate optimal execution strategy
        optimal_chunks, chunk_delay = self._calculate_optimal_execution(
            trade_size_usd, liquidity_usd, volatility
        )

        # Confidence based on data freshness and model fit
        confidence = self._calculate_confidence(symbol, liquidity_usd)

        # Risk level
        if predicted_bps < 20:
            risk_level = "low"
        elif predicted_bps < 50:
            risk_level = "medium"
        else:
            risk_level = "high"

        # Generate recommendation
        recommendation = self._generate_recommendation(
            predicted_bps, trade_size_usd, liquidity_usd, optimal_chunks
        )

        prediction = SlippagePrediction(
            symbol=symbol,
            trade_size_usd=trade_size_usd,
            predicted_slippage_bps=predicted_bps,
            predicted_slippage_pct=predicted_bps / 100,
            confidence=confidence,
            price_impact_bps=price_impact_bps,
            market_impact_bps=market_impact_bps,
            execution_cost_usd=execution_cost,
            optimal_chunks=optimal_chunks,
            chunk_delay_ms=chunk_delay,
            risk_level=risk_level,
            recommendation=recommendation,
            features=features,
            timestamp=timestamp
        )

        # Save prediction
        self._save_prediction(prediction)

        return prediction

    def _estimate_price_impact(self, trade_size: float, liquidity: float) -> float:
        """Estimate pure price impact as fraction."""
        if liquidity == 0:
            return 0.01  # 1% default

        # Square root market impact model
        impact = math.sqrt(trade_size / liquidity) * 0.1
        return min(impact, 0.05)  # Cap at 5%

    def _count_recent_large_trades(self, symbol: str) -> int:
        """Count recent large trades."""
        trades = self._recent_trades.get(symbol, deque(maxlen=100))
        # Count trades > $10K in last 100 trades
        return sum(1 for t in trades if t > 10000)

    def _calculate_optimal_execution(
        self,
        trade_size: float,
        liquidity: float,
        volatility: float
    ) -> Tuple[int, int]:
        """Calculate optimal number of chunks and delay."""
        # Participation rate target: 5-10% of liquidity
        target_participation = 0.07
        chunk_size = liquidity * target_participation

        if trade_size <= chunk_size:
            return 1, 0

        chunks = max(2, int(trade_size / chunk_size))
        chunks = min(chunks, 20)  # Cap at 20 chunks

        # Delay based on volatility (higher vol = longer delay)
        base_delay = 1000  # 1 second
        delay = int(base_delay * (1 + volatility / 5))
        delay = min(delay, 5000)  # Cap at 5 seconds

        return chunks, delay

    def _calculate_confidence(self, symbol: str, liquidity: float) -> float:
        """Calculate prediction confidence."""
        confidence = 0.7  # Base confidence

        # Higher liquidity = more predictable
        if liquidity > 1_000_000:
            confidence += 0.1
        elif liquidity < 100_000:
            confidence -= 0.1

        # Check if we have calibrated parameters
        if symbol in self._model_params:
            confidence += 0.1

        # Check data freshness
        if symbol in self._liquidity_cache:
            _, _, timestamp = self._liquidity_cache[symbol]
            try:
                data_age = datetime.now(timezone.utc) - datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                if data_age.total_seconds() < 60:
                    confidence += 0.1
                elif data_age.total_seconds() > 300:
                    confidence -= 0.1
            except Exception:
                pass

        return min(max(confidence, 0.3), 0.95)

    def _generate_recommendation(
        self,
        slippage_bps: float,
        trade_size: float,
        liquidity: float,
        chunks: int
    ) -> str:
        """Generate execution recommendation."""
        if slippage_bps < 10:
            return "Execute immediately - minimal slippage expected"
        elif slippage_bps < 30:
            return "Execute - acceptable slippage"
        elif slippage_bps < 50:
            if chunks > 1:
                return f"Consider splitting into {chunks} chunks to reduce slippage"
            return "Execute with caution - moderate slippage expected"
        elif slippage_bps < 100:
            return f"High slippage warning - strongly recommend {chunks} chunks with delays"
        else:
            return "Very high slippage - consider reducing size or waiting for better liquidity"

    def _save_prediction(self, prediction: SlippagePrediction):
        """Save prediction to database."""
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO slippage_predictions
                (symbol, trade_size_usd, predicted_slippage_bps, confidence,
                 price_impact_bps, market_impact_bps, optimal_chunks, features_json, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                prediction.symbol, prediction.trade_size_usd,
                prediction.predicted_slippage_bps, prediction.confidence,
                prediction.price_impact_bps, prediction.market_impact_bps,
                prediction.optimal_chunks,
                json.dumps({
                    'trade_size_usd': prediction.features.trade_size_usd,
                    'liquidity_usd': prediction.features.liquidity_usd,
                    'spread_bps': prediction.features.spread_bps,
                    'volatility_1h': prediction.features.volatility_1h
                }),
                prediction.timestamp
            ))
            conn.commit()

    def record_trade(
        self,
        symbol: str,
        trade_size_usd: float,
        expected_price: float,
        executed_price: float,
        predicted_slippage_bps: Optional[float] = None
    ):
        """Record actual trade slippage for model improvement."""
        symbol = symbol.upper()

        # Calculate actual slippage
        actual_slippage_bps = abs(executed_price - expected_price) / expected_price * 10000

        # Get prediction error if we have a prediction
        prediction_error = 0
        if predicted_slippage_bps is not None:
            prediction_error = actual_slippage_bps - predicted_slippage_bps

        # Get current market data
        liquidity = 0
        volatility = self._volatility_cache.get(symbol, 0)
        if symbol in self._liquidity_cache:
            liquidity, _, _ = self._liquidity_cache[symbol]

        record = SlippageRecord(
            symbol=symbol,
            trade_size_usd=trade_size_usd,
            expected_price=expected_price,
            executed_price=executed_price,
            actual_slippage_bps=actual_slippage_bps,
            predicted_slippage_bps=predicted_slippage_bps or 0,
            prediction_error=prediction_error,
            liquidity_at_time=liquidity,
            volatility_at_time=volatility,
            timestamp=datetime.now(timezone.utc).isoformat()
        )

        # Save record
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO slippage_records
                (symbol, trade_size_usd, expected_price, executed_price,
                 actual_slippage_bps, predicted_slippage_bps, prediction_error,
                 liquidity_at_time, volatility_at_time, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                record.symbol, record.trade_size_usd, record.expected_price,
                record.executed_price, record.actual_slippage_bps,
                record.predicted_slippage_bps, record.prediction_error,
                record.liquidity_at_time, record.volatility_at_time,
                record.timestamp
            ))
            conn.commit()

        # Update recent trades
        if symbol not in self._recent_trades:
            self._recent_trades[symbol] = deque(maxlen=100)
        self._recent_trades[symbol].append(trade_size_usd)

        logger.info(f"Recorded slippage for {symbol}: actual={actual_slippage_bps:.1f}bps, "
                   f"predicted={predicted_slippage_bps:.1f}bps, error={prediction_error:.1f}bps")

        # Trigger model recalibration if we have enough data
        self._maybe_recalibrate(symbol)

    def _maybe_recalibrate(self, symbol: str):
        """Recalibrate model if we have enough new data."""
        with self.db._get_connection() as conn:
            cursor = conn.cursor()

            # Check how many records we have since last calibration
            cursor.execute("""
                SELECT COUNT(*) FROM slippage_records
                WHERE symbol = ?
                AND datetime(timestamp) > datetime('now', '-24 hours')
            """, (symbol,))

            recent_count = cursor.fetchone()[0]

            if recent_count >= 20:
                self.calibrate_model(symbol)

    def calibrate_model(self, symbol: str):
        """Calibrate model parameters based on historical data."""
        symbol = symbol.upper()

        with self.db._get_connection() as conn:
            cursor = conn.cursor()

            # Get recent slippage records
            cursor.execute("""
                SELECT * FROM slippage_records
                WHERE symbol = ?
                ORDER BY timestamp DESC
                LIMIT 100
            """, (symbol,))

            records = cursor.fetchall()

            if len(records) < 10:
                logger.warning(f"Not enough data to calibrate model for {symbol}")
                return

            # Simple regression to fit parameters
            # In practice, you'd use proper ML here
            total_error = sum(r['prediction_error'] for r in records)
            avg_error = total_error / len(records)

            # Adjust base slippage based on average error
            current_params = self._model_params.get(symbol, self.DEFAULT_PARAMS.copy())
            current_params['base_slippage'] = max(1, current_params.get('base_slippage', 5) + avg_error * 0.1)

            # Save updated parameters
            cursor.execute("""
                INSERT INTO model_parameters
                (symbol, base_slippage, size_coefficient, liquidity_coefficient,
                 volatility_coefficient, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                symbol,
                current_params['base_slippage'],
                current_params.get('size_coefficient', 0.5),
                current_params.get('liquidity_coefficient', -0.3),
                current_params.get('volatility_coefficient', 2.0),
                datetime.now(timezone.utc).isoformat()
            ))
            conn.commit()

            self._model_params[symbol] = current_params

            logger.info(f"Calibrated slippage model for {symbol}: base_slippage={current_params['base_slippage']:.2f}")

    def get_model_accuracy(self, symbol: str, days: int = 7) -> Dict[str, float]:
        """Get model accuracy metrics."""
        with self.db._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT
                    AVG(ABS(prediction_error)) as mae,
                    AVG(prediction_error * prediction_error) as mse,
                    AVG(prediction_error) as bias,
                    COUNT(*) as n_records
                FROM slippage_records
                WHERE symbol = ?
                AND datetime(timestamp) > datetime('now', ?)
            """, (symbol.upper(), f'-{days} days'))

            row = cursor.fetchone()

            if not row or row['n_records'] == 0:
                return {'mae': 0, 'rmse': 0, 'bias': 0, 'n_records': 0}

            return {
                'mae': row['mae'] or 0,
                'rmse': math.sqrt(row['mse']) if row['mse'] else 0,
                'bias': row['bias'] or 0,
                'n_records': row['n_records']
            }

    def get_slippage_stats(self, symbol: str, days: int = 7) -> Dict[str, Any]:
        """Get slippage statistics for a symbol."""
        with self.db._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT
                    AVG(actual_slippage_bps) as avg_slippage,
                    MIN(actual_slippage_bps) as min_slippage,
                    MAX(actual_slippage_bps) as max_slippage,
                    SUM(trade_size_usd) as total_volume,
                    COUNT(*) as n_trades
                FROM slippage_records
                WHERE symbol = ?
                AND datetime(timestamp) > datetime('now', ?)
            """, (symbol.upper(), f'-{days} days'))

            row = cursor.fetchone()

            # Get by trade size bucket
            cursor.execute("""
                SELECT
                    CASE
                        WHEN trade_size_usd < 1000 THEN 'small'
                        WHEN trade_size_usd < 10000 THEN 'medium'
                        ELSE 'large'
                    END as bucket,
                    AVG(actual_slippage_bps) as avg_slippage,
                    COUNT(*) as count
                FROM slippage_records
                WHERE symbol = ?
                AND datetime(timestamp) > datetime('now', ?)
                GROUP BY bucket
            """, (symbol.upper(), f'-{days} days'))

            by_size = {r['bucket']: {'avg': r['avg_slippage'], 'count': r['count']}
                      for r in cursor.fetchall()}

            return {
                'symbol': symbol,
                'period_days': days,
                'avg_slippage_bps': row['avg_slippage'] or 0,
                'min_slippage_bps': row['min_slippage'] or 0,
                'max_slippage_bps': row['max_slippage'] or 0,
                'total_volume': row['total_volume'] or 0,
                'n_trades': row['n_trades'] or 0,
                'by_size': by_size,
                'model_accuracy': self.get_model_accuracy(symbol, days)
            }


# Singleton
_predictor: Optional[SlippagePredictor] = None


def get_slippage_predictor() -> SlippagePredictor:
    """Get singleton slippage predictor."""
    global _predictor
    if _predictor is None:
        _predictor = SlippagePredictor()
    return _predictor
