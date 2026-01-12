"""
Sentiment Aggregator - Aggregate sentiment from multiple sources.
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from pathlib import Path
from enum import Enum
import json
import sqlite3
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class SentimentSource(Enum):
    """Sources of sentiment data."""
    TWITTER = "twitter"
    TELEGRAM = "telegram"
    DISCORD = "discord"
    REDDIT = "reddit"
    NEWS = "news"
    GROK = "grok"
    TECHNICAL = "technical"
    ONCHAIN = "onchain"
    WHALE = "whale"


class SentimentLabel(Enum):
    """Sentiment classification."""
    VERY_BULLISH = "very_bullish"
    BULLISH = "bullish"
    NEUTRAL = "neutral"
    BEARISH = "bearish"
    VERY_BEARISH = "very_bearish"


@dataclass
class SentimentReading:
    """A single sentiment reading from a source."""
    source: SentimentSource
    symbol: str
    score: float  # -100 to 100
    label: SentimentLabel
    confidence: float  # 0 to 1
    timestamp: str
    data_points: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AggregatedSentiment:
    """Aggregated sentiment from multiple sources."""
    symbol: str
    overall_score: float
    overall_label: SentimentLabel
    overall_confidence: float
    source_scores: Dict[str, float]
    source_weights: Dict[str, float]
    trend: str  # IMPROVING, STABLE, DECLINING
    trend_change: float
    timestamp: str
    warning: str = ""


@dataclass
class SentimentConfig:
    """Configuration for sentiment aggregation."""
    # Source weights (higher = more influence)
    source_weights: Dict[str, float] = field(default_factory=lambda: {
        SentimentSource.GROK.value: 1.0,
        SentimentSource.TWITTER.value: 0.8,
        SentimentSource.WHALE.value: 0.9,
        SentimentSource.ONCHAIN.value: 0.85,
        SentimentSource.TECHNICAL.value: 0.7,
        SentimentSource.TELEGRAM.value: 0.6,
        SentimentSource.REDDIT.value: 0.5,
        SentimentSource.NEWS.value: 0.7,
        SentimentSource.DISCORD.value: 0.4
    })

    # Thresholds for labels
    very_bullish_threshold: float = 60
    bullish_threshold: float = 20
    neutral_low: float = -20
    bearish_threshold: float = -60


class SentimentDB:
    """SQLite storage for sentiment data."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Initialize database schema."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sentiment_readings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    score REAL NOT NULL,
                    label TEXT,
                    confidence REAL,
                    timestamp TEXT,
                    data_points INTEGER,
                    metadata_json TEXT
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS aggregated_sentiment (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    overall_score REAL,
                    overall_label TEXT,
                    overall_confidence REAL,
                    source_scores_json TEXT,
                    trend TEXT,
                    trend_change REAL,
                    timestamp TEXT,
                    warning TEXT
                )
            """)

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_readings_symbol ON sentiment_readings(symbol)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_readings_time ON sentiment_readings(timestamp)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_agg_symbol ON aggregated_sentiment(symbol)")

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


class SentimentAggregator:
    """
    Aggregate sentiment from multiple sources.

    Usage:
        aggregator = SentimentAggregator()

        # Add sentiment readings
        aggregator.add_reading(SentimentReading(
            source=SentimentSource.TWITTER,
            symbol="BTC",
            score=65,
            label=SentimentLabel.BULLISH,
            confidence=0.8,
            timestamp=datetime.now(timezone.utc).isoformat()
        ))

        # Get aggregated sentiment
        sentiment = aggregator.get_aggregated("BTC")
    """

    def __init__(
        self,
        db_path: Optional[Path] = None,
        config: SentimentConfig = None
    ):
        db_path = db_path or Path(__file__).parent.parent / "data" / "sentiment.db"
        self.db = SentimentDB(db_path)
        self.config = config or SentimentConfig()

    def add_reading(self, reading: SentimentReading):
        """Add a sentiment reading."""
        reading.timestamp = reading.timestamp or datetime.now(timezone.utc).isoformat()

        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO sentiment_readings
                (source, symbol, score, label, confidence, timestamp, data_points, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                reading.source.value, reading.symbol.upper(), reading.score,
                reading.label.value, reading.confidence, reading.timestamp,
                reading.data_points, json.dumps(reading.metadata)
            ))
            conn.commit()

    def get_readings(
        self,
        symbol: str,
        source: SentimentSource = None,
        hours: int = 24
    ) -> List[SentimentReading]:
        """Get sentiment readings."""
        with self.db._get_connection() as conn:
            cursor = conn.cursor()

            query = """
                SELECT * FROM sentiment_readings
                WHERE symbol = ?
                AND datetime(timestamp) > datetime('now', ?)
            """
            params = [symbol.upper(), f'-{hours} hours']

            if source:
                query += " AND source = ?"
                params.append(source.value)

            query += " ORDER BY timestamp DESC"

            cursor.execute(query, params)

            return [
                SentimentReading(
                    source=SentimentSource(row['source']),
                    symbol=row['symbol'],
                    score=row['score'],
                    label=SentimentLabel(row['label']),
                    confidence=row['confidence'],
                    timestamp=row['timestamp'],
                    data_points=row['data_points'],
                    metadata=json.loads(row['metadata_json']) if row['metadata_json'] else {}
                )
                for row in cursor.fetchall()
            ]

    def aggregate(self, symbol: str, hours: int = 24) -> AggregatedSentiment:
        """Aggregate sentiment from all sources."""
        readings = self.get_readings(symbol, hours=hours)

        if not readings:
            return AggregatedSentiment(
                symbol=symbol,
                overall_score=0,
                overall_label=SentimentLabel.NEUTRAL,
                overall_confidence=0,
                source_scores={},
                source_weights={},
                trend="STABLE",
                trend_change=0,
                timestamp=datetime.now(timezone.utc).isoformat(),
                warning="No sentiment data available"
            )

        # Group by source and take most recent
        by_source: Dict[str, SentimentReading] = {}
        for reading in readings:
            source_key = reading.source.value
            if source_key not in by_source or reading.timestamp > by_source[source_key].timestamp:
                by_source[source_key] = reading

        # Calculate weighted average
        total_weight = 0
        weighted_score = 0
        source_scores = {}
        source_weights = {}

        for source_key, reading in by_source.items():
            weight = self.config.source_weights.get(source_key, 0.5)
            weight *= reading.confidence  # Adjust by confidence

            weighted_score += reading.score * weight
            total_weight += weight

            source_scores[source_key] = reading.score
            source_weights[source_key] = weight

        overall_score = weighted_score / total_weight if total_weight > 0 else 0

        # Determine label
        overall_label = self._score_to_label(overall_score)

        # Calculate trend
        trend, trend_change = self._calculate_trend(symbol, overall_score)

        # Calculate overall confidence
        overall_confidence = sum(r.confidence for r in by_source.values()) / len(by_source)

        # Check for divergence warnings
        warning = self._check_divergence(source_scores)

        result = AggregatedSentiment(
            symbol=symbol,
            overall_score=overall_score,
            overall_label=overall_label,
            overall_confidence=overall_confidence,
            source_scores=source_scores,
            source_weights=source_weights,
            trend=trend,
            trend_change=trend_change,
            timestamp=datetime.now(timezone.utc).isoformat(),
            warning=warning
        )

        # Save aggregated result
        self._save_aggregated(result)

        return result

    def _score_to_label(self, score: float) -> SentimentLabel:
        """Convert score to sentiment label."""
        if score >= self.config.very_bullish_threshold:
            return SentimentLabel.VERY_BULLISH
        elif score >= self.config.bullish_threshold:
            return SentimentLabel.BULLISH
        elif score >= self.config.neutral_low:
            return SentimentLabel.NEUTRAL
        elif score >= self.config.bearish_threshold:
            return SentimentLabel.BEARISH
        else:
            return SentimentLabel.VERY_BEARISH

    def _calculate_trend(self, symbol: str, current_score: float) -> tuple:
        """Calculate sentiment trend."""
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT overall_score FROM aggregated_sentiment
                WHERE symbol = ?
                ORDER BY timestamp DESC
                LIMIT 5
            """, (symbol,))

            past_scores = [row['overall_score'] for row in cursor.fetchall()]

        if len(past_scores) < 2:
            return "STABLE", 0

        avg_past = sum(past_scores) / len(past_scores)
        change = current_score - avg_past

        if change > 10:
            return "IMPROVING", change
        elif change < -10:
            return "DECLINING", change
        else:
            return "STABLE", change

    def _check_divergence(self, source_scores: Dict[str, float]) -> str:
        """Check for significant divergence between sources."""
        if len(source_scores) < 2:
            return ""

        scores = list(source_scores.values())
        min_score = min(scores)
        max_score = max(scores)

        if max_score - min_score > 60:
            bullish_sources = [s for s, v in source_scores.items() if v > 20]
            bearish_sources = [s for s, v in source_scores.items() if v < -20]

            if bullish_sources and bearish_sources:
                return f"Significant divergence: {', '.join(bullish_sources)} bullish vs {', '.join(bearish_sources)} bearish"

        return ""

    def _save_aggregated(self, result: AggregatedSentiment):
        """Save aggregated sentiment to database."""
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO aggregated_sentiment
                (symbol, overall_score, overall_label, overall_confidence,
                 source_scores_json, trend, trend_change, timestamp, warning)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                result.symbol, result.overall_score, result.overall_label.value,
                result.overall_confidence, json.dumps(result.source_scores),
                result.trend, result.trend_change, result.timestamp, result.warning
            ))
            conn.commit()

    def get_historical(
        self,
        symbol: str,
        days: int = 7
    ) -> List[AggregatedSentiment]:
        """Get historical aggregated sentiment."""
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM aggregated_sentiment
                WHERE symbol = ?
                AND datetime(timestamp) > datetime('now', ?)
                ORDER BY timestamp ASC
            """, (symbol.upper(), f'-{days} days'))

            return [
                AggregatedSentiment(
                    symbol=row['symbol'],
                    overall_score=row['overall_score'],
                    overall_label=SentimentLabel(row['overall_label']),
                    overall_confidence=row['overall_confidence'],
                    source_scores=json.loads(row['source_scores_json']) if row['source_scores_json'] else {},
                    source_weights={},
                    trend=row['trend'],
                    trend_change=row['trend_change'],
                    timestamp=row['timestamp'],
                    warning=row['warning'] or ""
                )
                for row in cursor.fetchall()
            ]

    def get_market_sentiment(self, symbols: List[str] = None) -> Dict[str, AggregatedSentiment]:
        """Get sentiment for multiple symbols."""
        if symbols is None:
            symbols = ["BTC", "ETH", "SOL"]

        return {symbol: self.aggregate(symbol) for symbol in symbols}

    def get_sentiment_leaders(self, hours: int = 24, limit: int = 10) -> List[Dict]:
        """Get symbols with strongest sentiment."""
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT symbol, AVG(overall_score) as avg_score,
                       MAX(timestamp) as latest
                FROM aggregated_sentiment
                WHERE datetime(timestamp) > datetime('now', ?)
                GROUP BY symbol
                ORDER BY avg_score DESC
                LIMIT ?
            """, (f'-{hours} hours', limit))

            return [
                {
                    'symbol': row['symbol'],
                    'avg_score': row['avg_score'],
                    'latest': row['latest'],
                    'label': self._score_to_label(row['avg_score']).value
                }
                for row in cursor.fetchall()
            ]

    def generate_report(self, symbols: List[str] = None) -> str:
        """Generate a sentiment report."""
        if symbols is None:
            symbols = ["BTC", "ETH", "SOL"]

        lines = [
            "Sentiment Report",
            "=" * 40,
            f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
            ""
        ]

        for symbol in symbols:
            sentiment = self.aggregate(symbol)

            emoji = {
                SentimentLabel.VERY_BULLISH: "🟢🟢",
                SentimentLabel.BULLISH: "🟢",
                SentimentLabel.NEUTRAL: "⚪",
                SentimentLabel.BEARISH: "🔴",
                SentimentLabel.VERY_BEARISH: "🔴🔴"
            }.get(sentiment.overall_label, "")

            lines.append(f"{symbol}: {sentiment.overall_label.value.upper()} {emoji}")
            lines.append(f"  Score: {sentiment.overall_score:.1f} | Confidence: {sentiment.overall_confidence:.0%}")
            lines.append(f"  Trend: {sentiment.trend} ({sentiment.trend_change:+.1f})")

            if sentiment.source_scores:
                sources = ", ".join(f"{k}:{v:.0f}" for k, v in sentiment.source_scores.items())
                lines.append(f"  Sources: {sources}")

            if sentiment.warning:
                lines.append(f"  ⚠️ {sentiment.warning}")

            lines.append("")

        return "\n".join(lines)


# Singleton
_aggregator: Optional[SentimentAggregator] = None

def get_sentiment_aggregator() -> SentimentAggregator:
    """Get singleton sentiment aggregator."""
    global _aggregator
    if _aggregator is None:
        _aggregator = SentimentAggregator()
    return _aggregator
