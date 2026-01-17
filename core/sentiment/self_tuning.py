"""
Self-Tuning Sentiment Engine - Machine learning-based sentiment weight optimization.

Continuously learns from prediction outcomes and automatically adjusts sentiment
component weights (price momentum, volume, social, whale activity, technical).

Features:
- Record sentiment predictions and outcomes
- Calculate correlation between components and actual returns
- Auto-tune weights using reinforcement learning
- Track performance metrics and generate tuning reports
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import sqlite3
import json
import statistics
import uuid
from enum import Enum


class SentimentGrade(Enum):
    """Sentiment grade classification."""
    VERY_BEARISH = "F"
    BEARISH = "D"
    NEUTRAL = "C"
    BULLISH = "B"
    VERY_BULLISH = "A"


@dataclass
class SentimentComponents:
    """Individual sentiment component scores."""
    price_momentum: float = 0.0  # Range: -1.0 to 1.0
    volume: float = 0.0  # Range: -1.0 to 1.0
    social_sentiment: float = 0.0  # Range: -1.0 to 1.0
    whale_activity: float = 0.0  # Range: -1.0 to 1.0
    technical_analysis: float = 0.0  # Range: -1.0 to 1.0

    @property
    def components_dict(self) -> Dict[str, float]:
        """Get components as dictionary."""
        return {
            "price_momentum": self.price_momentum,
            "volume": self.volume,
            "social_sentiment": self.social_sentiment,
            "whale_activity": self.whale_activity,
            "technical_analysis": self.technical_analysis,
        }


@dataclass
class SentimentWeights:
    """Sentiment component weights for blending."""
    price_momentum: float = 0.20
    volume: float = 0.15
    social_sentiment: float = 0.25
    whale_activity: float = 0.20
    technical_analysis: float = 0.20
    
    def __post_init__(self):
        """Normalize weights to sum to 1.0."""
        total = (
            self.price_momentum + self.volume + self.social_sentiment +
            self.whale_activity + self.technical_analysis
        )
        if total > 0:
            self.price_momentum /= total
            self.volume /= total
            self.social_sentiment /= total
            self.whale_activity /= total
            self.technical_analysis /= total

    @property
    def weights_dict(self) -> Dict[str, float]:
        """Get weights as dictionary."""
        return {
            "price_momentum": self.price_momentum,
            "volume": self.volume,
            "social_sentiment": self.social_sentiment,
            "whale_activity": self.whale_activity,
            "technical_analysis": self.technical_analysis,
        }

    def to_json(self) -> str:
        """Serialize to JSON."""
        return json.dumps(self.weights_dict)


@dataclass
class SentimentPrediction:
    """Stored sentiment prediction with outcome tracking."""
    id: str
    symbol: str
    timestamp: datetime
    components: SentimentComponents
    sentiment_score: float  # -1.0 to 1.0
    sentiment_grade: str  # A-F
    weights_used: SentimentWeights
    predicted_direction: str  # "UP", "DOWN", "NEUTRAL"
    
    # Outcome tracking
    outcome_recorded_at: Optional[datetime] = None
    actual_price_change: Optional[float] = None  # Actual % change
    outcome_correct: Optional[bool] = None  # Whether prediction was correct
    
    @property
    def is_pending_outcome(self) -> bool:
        """Check if outcome needs to be recorded."""
        return (
            self.outcome_recorded_at is None and
            datetime.utcnow() >= self.timestamp + timedelta(hours=24)
        )
    
    @property
    def age_hours(self) -> float:
        """Hours since prediction was made."""
        delta = datetime.utcnow() - self.timestamp
        return delta.total_seconds() / 3600


class SelfTuningSentimentEngine:
    """Self-tuning sentiment engine with reinforcement learning."""

    def __init__(self, db_path: str = None):
        """Initialize sentiment engine."""
        self.db_path = db_path or "./data/sentiment.db"
        self.weights = SentimentWeights()
        self._init_database()
        self._load_weights()

    def _init_database(self):
        """Initialize SQLite database for predictions and weights."""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()

        # Predictions table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS predictions (
                id TEXT PRIMARY KEY,
                symbol TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                components TEXT NOT NULL,
                sentiment_score REAL NOT NULL,
                sentiment_grade TEXT NOT NULL,
                weights_used TEXT NOT NULL,
                predicted_direction TEXT NOT NULL,
                outcome_recorded_at TEXT,
                actual_price_change REAL,
                outcome_correct INTEGER
            )
        """)

        # Weight history table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS weight_history (
                id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                weights TEXT NOT NULL,
                trigger_type TEXT,
                performance_metric REAL
            )
        """)

        # Component correlation table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS component_correlations (
                timestamp TEXT NOT NULL,
                component TEXT NOT NULL,
                correlation REAL NOT NULL,
                sample_size INTEGER NOT NULL
            )
        """)

        conn.commit()
        conn.close()

    def _load_weights(self):
        """Load latest weights from database."""
        try:
            conn = sqlite3.connect(self.db_path)
            cur = conn.cursor()
            cur.execute("""
                SELECT weights FROM weight_history
                ORDER BY timestamp DESC
                LIMIT 1
            """)
            result = cur.fetchone()
            conn.close()

            if result:
                weights_dict = json.loads(result[0])
                self.weights = SentimentWeights(**weights_dict)
        except Exception as e:
            print(f"Error loading weights: {e}")

    def compute_sentiment(
        self,
        symbol: str,
        components: SentimentComponents
    ) -> Tuple[float, str, SentimentPrediction]:
        """
        Compute weighted sentiment score from components.

        Returns:
            (sentiment_score, sentiment_grade, prediction_object)
        """
        # Calculate weighted score
        score = (
            components.price_momentum * self.weights.price_momentum +
            components.volume * self.weights.volume +
            components.social_sentiment * self.weights.social_sentiment +
            components.whale_activity * self.weights.whale_activity +
            components.technical_analysis * self.weights.technical_analysis
        )

        # Clamp to [-1, 1]
        score = max(-1.0, min(1.0, score))

        # Determine grade
        if score >= 0.8:
            grade = SentimentGrade.VERY_BULLISH.value
            direction = "UP"
        elif score >= 0.4:
            grade = SentimentGrade.BULLISH.value
            direction = "UP"
        elif score >= -0.4:
            grade = SentimentGrade.NEUTRAL.value
            direction = "NEUTRAL"
        elif score >= -0.8:
            grade = SentimentGrade.BEARISH.value
            direction = "DOWN"
        else:
            grade = SentimentGrade.VERY_BEARISH.value
            direction = "DOWN"

        # Create prediction record
        prediction = SentimentPrediction(
            id=str(uuid.uuid4()),
            symbol=symbol,
            timestamp=datetime.utcnow(),
            components=components,
            sentiment_score=score,
            sentiment_grade=grade,
            weights_used=SentimentWeights(
                self.weights.price_momentum,
                self.weights.volume,
                self.weights.social_sentiment,
                self.weights.whale_activity,
                self.weights.technical_analysis,
            ),
            predicted_direction=direction,
        )

        # Store prediction
        self._store_prediction(prediction)

        return score, grade, prediction

    def _store_prediction(self, prediction: SentimentPrediction):
        """Store prediction in database."""
        try:
            conn = sqlite3.connect(self.db_path)
            cur = conn.cursor()

            cur.execute("""
                INSERT INTO predictions
                (id, symbol, timestamp, components, sentiment_score, sentiment_grade,
                 weights_used, predicted_direction, outcome_recorded_at, actual_price_change,
                 outcome_correct)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                prediction.id,
                prediction.symbol,
                prediction.timestamp.isoformat(),
                json.dumps(prediction.components.components_dict),
                prediction.sentiment_score,
                prediction.sentiment_grade,
                prediction.weights_used.to_json(),
                prediction.predicted_direction,
                None,
                None,
                None,
            ))

            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Error storing prediction: {e}")

    def record_outcome(self, prediction_id: str, actual_price_change: float):
        """
        Record actual price change outcome for a prediction.

        Args:
            prediction_id: UUID of the prediction
            actual_price_change: Actual % price change
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cur = conn.cursor()

            # Get prediction
            cur.execute("SELECT predicted_direction FROM predictions WHERE id = ?", (prediction_id,))
            result = cur.fetchone()

            if not result:
                return

            predicted_direction = result[0]

            # Determine if prediction was correct
            if predicted_direction == "UP":
                outcome_correct = actual_price_change > 0
            elif predicted_direction == "DOWN":
                outcome_correct = actual_price_change < 0
            else:  # NEUTRAL
                outcome_correct = -1 < actual_price_change < 1

            # Update prediction with outcome
            cur.execute("""
                UPDATE predictions
                SET outcome_recorded_at = ?, actual_price_change = ?, outcome_correct = ?
                WHERE id = ?
            """, (
                datetime.utcnow().isoformat(),
                actual_price_change,
                int(outcome_correct),
                prediction_id,
            ))

            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Error recording outcome: {e}")

    def tune_weights(self, min_samples: int = 50, learning_rate: float = 0.05):
        """
        Automatically tune weights based on prediction outcomes.

        Args:
            min_samples: Minimum number of outcomes needed before tuning
            learning_rate: How much to adjust weights (0.01-0.20)
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()

            # Get predictions with outcomes
            cur.execute("""
                SELECT * FROM predictions
                WHERE outcome_recorded_at IS NOT NULL
                AND outcome_correct IS NOT NULL
                ORDER BY outcome_recorded_at DESC
                LIMIT 500
            """)
            predictions = cur.fetchall()

            if len(predictions) < min_samples:
                print(f"Not enough samples ({len(predictions)}/{min_samples}) for tuning")
                conn.close()
                return

            # Calculate correlations for each component
            correlations = {}
            component_names = [
                "price_momentum",
                "volume",
                "social_sentiment",
                "whale_activity",
                "technical_analysis",
            ]

            for component in component_names:
                # Collect scores and outcomes
                scores = []
                outcomes = []

                for pred in predictions:
                    components = json.loads(pred["components"])
                    outcome = bool(pred["outcome_correct"])

                    scores.append(components.get(component, 0))
                    outcomes.append(1.0 if outcome else -1.0)

                # Calculate correlation
                if len(scores) > 1 and statistics.stdev(scores) > 0 and statistics.stdev(outcomes) > 0:
                    correlation = self._calculate_correlation(scores, outcomes)
                    correlations[component] = max(0, correlation)  # Floor at 0

            # Normalize correlations
            total_corr = sum(correlations.values())
            if total_corr > 0:
                for key in correlations:
                    correlations[key] /= total_corr

            # Update weights with learning rate
            old_weights = self.weights.weights_dict.copy()
            new_weights = {}

            for component in component_names:
                old_weight = old_weights[component]
                corr_weight = correlations.get(component, 0)

                # Blend old and new weights with learning rate
                new_weights[component] = (
                    old_weight * (1 - learning_rate) +
                    corr_weight * learning_rate
                )

            # Normalize new weights
            self.weights = SentimentWeights(**new_weights)

            # Store weight history
            cur.execute("""
                INSERT INTO weight_history (id, timestamp, weights, trigger_type, performance_metric)
                VALUES (?, ?, ?, ?, ?)
            """, (
                str(uuid.uuid4()),
                datetime.utcnow().isoformat(),
                self.weights.to_json(),
                "AUTO_TUNE",
                self._calculate_win_rate(predictions),
            ))

            conn.commit()
            conn.close()

            print(f"✅ Weights tuned. New correlations: {json.dumps(correlations, indent=2)}")

        except Exception as e:
            print(f"Error tuning weights: {e}")

    @staticmethod
    def _calculate_correlation(x: List[float], y: List[float]) -> float:
        """Calculate Pearson correlation coefficient."""
        if len(x) < 2 or len(y) < 2:
            return 0.0

        mean_x = statistics.mean(x)
        mean_y = statistics.mean(y)

        numerator = sum((x[i] - mean_x) * (y[i] - mean_y) for i in range(len(x)))
        denominator = (
            (sum((xi - mean_x) ** 2 for xi in x) ** 0.5) *
            (sum((yi - mean_y) ** 2 for yi in y) ** 0.5)
        )

        if denominator == 0:
            return 0.0

        return numerator / denominator

    @staticmethod
    def _calculate_win_rate(predictions: List) -> float:
        """Calculate win rate from predictions."""
        if not predictions:
            return 0.0

        wins = sum(1 for p in predictions if p["outcome_correct"])
        return (wins / len(predictions)) * 100

    def get_tuning_report(self) -> Dict:
        """Generate comprehensive tuning report."""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()

            # Get recent outcomes
            cur.execute("""
                SELECT * FROM predictions
                WHERE outcome_recorded_at IS NOT NULL
                ORDER BY outcome_recorded_at DESC
                LIMIT 100
            """)
            outcomes = cur.fetchall()

            # Get weight history
            cur.execute("""
                SELECT timestamp, weights FROM weight_history
                ORDER BY timestamp DESC
                LIMIT 5
            """)
            weight_history = cur.fetchall()

            conn.close()

            # Calculate statistics
            if outcomes:
                wins = sum(1 for o in outcomes if o["outcome_correct"])
                win_rate = (wins / len(outcomes)) * 100

                # Calculate per-component performance
                component_perf = {}
                for component in ["price_momentum", "volume", "social_sentiment", "whale_activity", "technical_analysis"]:
                    correct_outcomes = []
                    for pred in outcomes:
                        components = json.loads(pred["components"])
                        score = components.get(component, 0)
                        if pred["outcome_correct"]:
                            correct_outcomes.append(score)

                    if correct_outcomes:
                        component_perf[component] = statistics.mean(correct_outcomes)
            else:
                win_rate = 0.0
                component_perf = {}

            return {
                "total_predictions": len(outcomes),
                "win_rate": win_rate,
                "current_weights": self.weights.weights_dict,
                "component_performance": component_perf,
                "weight_history": [
                    {
                        "timestamp": w["timestamp"],
                        "weights": json.loads(w["weights"]),
                    }
                    for w in weight_history
                ],
            }

        except Exception as e:
            print(f"Error generating report: {e}")
            return {}

    def get_pending_outcomes(self) -> List[SentimentPrediction]:
        """Get predictions that need outcome recording."""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()

            cur.execute("""
                SELECT * FROM predictions
                WHERE outcome_recorded_at IS NULL
                AND datetime(timestamp) <= datetime('now', '-24 hours')
            """)
            results = cur.fetchall()
            conn.close()

            predictions = []
            for row in results:
                pred = SentimentPrediction(
                    id=row["id"],
                    symbol=row["symbol"],
                    timestamp=datetime.fromisoformat(row["timestamp"]),
                    components=SentimentComponents(**json.loads(row["components"])),
                    sentiment_score=row["sentiment_score"],
                    sentiment_grade=row["sentiment_grade"],
                    weights_used=SentimentWeights(**json.loads(row["weights_used"])),
                    predicted_direction=row["predicted_direction"],
                    outcome_recorded_at=(
                        datetime.fromisoformat(row["outcome_recorded_at"])
                        if row["outcome_recorded_at"] else None
                    ),
                    actual_price_change=row["actual_price_change"],
                    outcome_correct=bool(row["outcome_correct"]) if row["outcome_correct"] is not None else None,
                )
                predictions.append(pred)

            return predictions
        except Exception as e:
            print(f"Error getting pending outcomes: {e}")
            return []


# Example component calculation functions (to be integrated with actual data sources)

def calculate_price_momentum(symbol: str, lookback_hours: int = 24) -> float:
    """Calculate price momentum component (-1.0 to 1.0)."""
    # TODO: Integrate with actual price data
    # For now, return placeholder
    return 0.0


def calculate_volume_signal(symbol: str, lookback_hours: int = 24) -> float:
    """Calculate volume spike component (-1.0 to 1.0)."""
    # TODO: Integrate with volume data from Jupiter/DEX
    return 0.0


def calculate_social_sentiment(symbol: str) -> float:
    """Calculate social sentiment component (-1.0 to 1.0)."""
    # TODO: Integrate with Grok AI sentiment analysis
    return 0.0


def calculate_whale_activity(symbol: str, lookback_hours: int = 24) -> float:
    """Calculate whale activity component (-1.0 to 1.0)."""
    # TODO: Integrate with blockchain data (Solana RPC)
    return 0.0


def calculate_technical_analysis(symbol: str) -> float:
    """Calculate technical analysis component (-1.0 to 1.0)."""
    # TODO: Integrate with technical indicator calculations
    return 0.0


__all__ = [
    'SelfTuningSentimentEngine',
    'SentimentPrediction',
    'SentimentComponents',
    'SentimentWeights',
    'SentimentGrade',
]


if __name__ == "__main__":
    # Example usage
    engine = SelfTuningSentimentEngine("./data/sentiment.db")

    # Example: Make a prediction
    components = SentimentComponents(
        price_momentum=0.5,
        volume=0.3,
        social_sentiment=0.7,
        whale_activity=0.4,
        technical_analysis=0.6,
    )

    score, grade, prediction = engine.compute_sentiment("SOL", components)
    print(f"Sentiment: {grade} ({score:.2f})")
    print(f"Prediction ID: {prediction.id}")

    # Get report
    report = engine.get_tuning_report()
    print(f"\nTuning Report:")
    print(json.dumps(report, indent=2, default=str))
