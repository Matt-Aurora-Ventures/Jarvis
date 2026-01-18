"""
A/B Testing Framework for Twitter Bot

Test variants:
- Emoji usage: many vs minimal vs none
- Tone: casual vs professional vs sarcastic
- Call-to-action: link vs button vs direct

Track metrics:
- Impressions, engagements, retweets, replies
- Clicks, conversions (link tracking)

Variant assignment: hash(tweet_id) % 2 for 50/50 split
"""

import json
import hashlib
import sqlite3
import logging
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from contextlib import contextmanager

logger = logging.getLogger(__name__)

# Default data directory
DEFAULT_DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "twitter"


@dataclass
class ABTestResult:
    """Result of an A/B test variant."""
    test_name: str
    variant: str
    tweet_id: str
    impressions: int = 0
    engagements: int = 0
    retweets: int = 0
    replies: int = 0
    clicks: int = 0
    engagement_rate: float = 0.0
    recorded_at: str = ""


class ABTestingFramework:
    """
    A/B testing framework for Twitter content optimization.

    Usage:
        framework = ABTestingFramework()

        # Assign variant before posting
        variant = framework.assign_variant(tweet_id, "emoji_test")

        # Track engagement after tweet
        framework.track_engagement(tweet_id, "emoji_test", variant, impressions=1000, ...)

        # Get results
        report = framework.generate_weekly_report()
    """

    # Available A/B tests
    TESTS = {
        "emoji_usage": {
            "variants": ["many", "minimal", "none"],
            "description": "Test emoji density in tweets"
        },
        "tone": {
            "variants": ["casual", "professional", "sarcastic"],
            "description": "Test tweet tone/voice"
        },
        "cta_style": {
            "variants": ["link", "direct", "subtle"],
            "description": "Test call-to-action style"
        },
        "tweet_length": {
            "variants": ["short", "medium", "long"],
            "description": "Test optimal tweet length"
        },
        "posting_time": {
            "variants": ["morning", "afternoon", "evening", "night"],
            "description": "Test optimal posting times"
        }
    }

    def __init__(self, data_dir: Optional[Path] = None):
        """
        Initialize A/B testing framework.

        Args:
            data_dir: Directory for storing test data
        """
        self.data_dir = data_dir or DEFAULT_DATA_DIR
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.data_dir / "ab_testing.db"
        self._init_db()

    def _init_db(self):
        """Initialize SQLite database for A/B test tracking."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Test results table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS ab_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    test_name TEXT NOT NULL,
                    variant TEXT NOT NULL,
                    tweet_id TEXT NOT NULL,
                    impressions INTEGER DEFAULT 0,
                    engagements INTEGER DEFAULT 0,
                    retweets INTEGER DEFAULT 0,
                    replies INTEGER DEFAULT 0,
                    clicks INTEGER DEFAULT 0,
                    engagement_rate REAL DEFAULT 0.0,
                    recorded_at TEXT NOT NULL,
                    UNIQUE(test_name, tweet_id)
                )
            """)

            # Indexes
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_ab_test ON ab_results(test_name)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_ab_variant ON ab_results(variant)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_ab_recorded ON ab_results(recorded_at)")

            conn.commit()
            logger.debug("A/B testing database initialized")

    @contextmanager
    def _get_connection(self):
        """Get database connection."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def assign_variant(self, tweet_id: str, test_name: str) -> str:
        """
        Assign a variant for a tweet based on deterministic hashing.

        Uses hash(tweet_id) to ensure same tweet always gets same variant.
        This allows for reproducible results.

        Args:
            tweet_id: The tweet identifier
            test_name: Name of the A/B test

        Returns:
            Assigned variant name
        """
        if test_name not in self.TESTS:
            logger.warning(f"Unknown test: {test_name}, defaulting to control")
            return "control"

        variants = self.TESTS[test_name]["variants"]

        # Deterministic hash-based assignment
        hash_input = f"{tweet_id}:{test_name}"
        hash_value = int(hashlib.md5(hash_input.encode()).hexdigest(), 16)

        # For 2 variants, use simple 50/50 split
        if len(variants) == 2:
            return "treatment" if hash_value % 2 == 0 else "control"

        # For multiple variants, distribute evenly
        variant_index = hash_value % len(variants)
        return variants[variant_index]

    def track_engagement(
        self,
        tweet_id: str,
        test_name: str,
        variant: str,
        impressions: int = 0,
        engagements: int = 0,
        retweets: int = 0,
        replies: int = 0,
        clicks: int = 0
    ):
        """
        Track engagement metrics for an A/B test variant.

        Args:
            tweet_id: The tweet identifier
            test_name: Name of the A/B test
            variant: The variant that was used
            impressions: Number of impressions
            engagements: Total engagements (likes, etc)
            retweets: Number of retweets
            replies: Number of replies
            clicks: Number of link clicks
        """
        engagement_rate = (engagements / impressions * 100) if impressions > 0 else 0.0

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO ab_results
                (test_name, variant, tweet_id, impressions, engagements,
                 retweets, replies, clicks, engagement_rate, recorded_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                test_name, variant, tweet_id, impressions, engagements,
                retweets, replies, clicks, round(engagement_rate, 4),
                datetime.now(timezone.utc).isoformat()
            ))
            conn.commit()

        logger.debug(f"Tracked A/B result: {test_name}/{variant} for {tweet_id}")

    def get_test_results(self, test_name: str, days: int = 7) -> Optional[Dict[str, Any]]:
        """
        Get aggregated results for a specific test.

        Args:
            test_name: Name of the A/B test
            days: Number of days to look back

        Returns:
            Dict with variant performance data
        """
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT
                    variant,
                    COUNT(*) as sample_size,
                    AVG(impressions) as avg_impressions,
                    AVG(engagements) as avg_engagements,
                    AVG(retweets) as avg_retweets,
                    AVG(replies) as avg_replies,
                    AVG(clicks) as avg_clicks,
                    AVG(engagement_rate) as avg_engagement_rate
                FROM ab_results
                WHERE test_name = ? AND recorded_at > ?
                GROUP BY variant
            """, (test_name, cutoff))

            results = {}
            for row in cursor.fetchall():
                results[row['variant']] = {
                    'sample_size': row['sample_size'],
                    'avg_impressions': round(row['avg_impressions'] or 0, 2),
                    'avg_engagements': round(row['avg_engagements'] or 0, 2),
                    'avg_retweets': round(row['avg_retweets'] or 0, 2),
                    'avg_replies': round(row['avg_replies'] or 0, 2),
                    'avg_clicks': round(row['avg_clicks'] or 0, 2),
                    'avg_engagement_rate': round(row['avg_engagement_rate'] or 0, 4)
                }

            return results if results else None

    def get_available_tests(self) -> Dict[str, Dict[str, Any]]:
        """
        Get all available A/B tests and their variants.

        Returns:
            Dict of test definitions
        """
        return self.TESTS.copy()

    def generate_weekly_report(self) -> Dict[str, Any]:
        """
        Generate a weekly A/B testing report.

        Returns:
            Dict containing results for all active tests
        """
        report = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "period_days": 7,
            "tests": {}
        }

        for test_name in self.TESTS:
            results = self.get_test_results(test_name, days=7)
            if results:
                # Determine winning variant
                winner = None
                max_engagement = -1

                for variant, data in results.items():
                    if data['avg_engagement_rate'] > max_engagement:
                        max_engagement = data['avg_engagement_rate']
                        winner = variant

                report["tests"][test_name] = {
                    "variants": results,
                    "winner": winner,
                    "recommendation": self._get_recommendation(test_name, results, winner)
                }

        return report

    def _get_recommendation(
        self,
        test_name: str,
        results: Dict[str, Any],
        winner: Optional[str]
    ) -> str:
        """Generate a recommendation based on test results."""
        if not winner or not results:
            return "Insufficient data for recommendation"

        winner_data = results.get(winner, {})
        sample_size = winner_data.get('sample_size', 0)

        if sample_size < 10:
            return f"Need more data (only {sample_size} samples)"

        engagement_rate = winner_data.get('avg_engagement_rate', 0)

        return f"Use '{winner}' variant (avg engagement: {engagement_rate:.2f}%, n={sample_size})"

    def get_optimal_settings(self) -> Dict[str, str]:
        """
        Get optimal settings based on A/B test results.

        Returns:
            Dict mapping test names to recommended variants
        """
        optimal = {}

        for test_name in self.TESTS:
            results = self.get_test_results(test_name, days=30)
            if results:
                # Find best performing variant
                best_variant = max(
                    results.items(),
                    key=lambda x: x[1].get('avg_engagement_rate', 0)
                )
                if best_variant[1].get('sample_size', 0) >= 5:
                    optimal[test_name] = best_variant[0]

        return optimal

    def export_results(self, filepath: Optional[Path] = None) -> Path:
        """
        Export all A/B test results to JSON.

        Args:
            filepath: Optional output path

        Returns:
            Path to exported file
        """
        if not filepath:
            filepath = self.data_dir / f"ab_results_{datetime.now().strftime('%Y%m%d')}.json"

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM ab_results ORDER BY recorded_at DESC")

            results = [dict(row) for row in cursor.fetchall()]

        filepath.write_text(json.dumps({
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "total_records": len(results),
            "results": results
        }, indent=2))

        logger.info(f"A/B results exported to {filepath}")
        return filepath
