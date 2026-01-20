"""
Trending Tracker Tests

Tests for core/social/trending_tracker.py:
- Monitor trending tokens on exchanges
- Detect pump/dump patterns
- Track social mentions spike
"""

import pytest
import tempfile
import json
from pathlib import Path
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, AsyncMock, patch


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


class TestTrendingTrackerImport:
    """Test that trending tracker module imports correctly."""

    def test_trending_tracker_import(self):
        """Test that TrendingTokenTracker can be imported."""
        from core.social.trending_tracker import TrendingTokenTracker
        assert TrendingTokenTracker is not None

    def test_pump_dump_detector_import(self):
        """Test that PumpDumpDetector can be imported."""
        from core.social.trending_tracker import PumpDumpDetector
        assert PumpDumpDetector is not None

    def test_mention_tracker_import(self):
        """Test that MentionTracker can be imported."""
        from core.social.trending_tracker import MentionTracker
        assert MentionTracker is not None


class TestTrendingTokenTrackerInit:
    """Test TrendingTokenTracker initialization."""

    def test_default_init(self, temp_dir):
        """Test default initialization."""
        from core.social.trending_tracker import TrendingTokenTracker

        tracker = TrendingTokenTracker(data_dir=temp_dir)
        assert tracker is not None
        assert tracker.data_dir == temp_dir

    def test_custom_exchanges(self, temp_dir):
        """Test initialization with custom exchanges."""
        from core.social.trending_tracker import TrendingTokenTracker

        exchanges = ["jupiter", "raydium"]
        tracker = TrendingTokenTracker(data_dir=temp_dir, exchanges=exchanges)
        assert tracker.exchanges == exchanges


class TestTrendingTokenMonitoring:
    """Tests for trending token monitoring."""

    def test_get_trending_tokens(self, temp_dir):
        """Test fetching trending tokens."""
        from core.social.trending_tracker import TrendingTokenTracker

        tracker = TrendingTokenTracker(data_dir=temp_dir)

        # Mock the exchange API
        with patch.object(tracker, '_fetch_exchange_data') as mock_fetch:
            mock_fetch.return_value = [
                {"symbol": "SOL", "volume_24h": 1000000, "price_change_24h": 15.5},
                {"symbol": "WIF", "volume_24h": 500000, "price_change_24h": 25.0},
                {"symbol": "BONK", "volume_24h": 300000, "price_change_24h": -5.0},
            ]

            trending = tracker.get_trending_tokens(limit=10)

            assert isinstance(trending, list)
            assert len(trending) <= 10

    def test_trending_tokens_sorted_by_volume(self, temp_dir):
        """Test that trending tokens are sorted by volume."""
        from core.social.trending_tracker import TrendingTokenTracker

        tracker = TrendingTokenTracker(data_dir=temp_dir)

        with patch.object(tracker, '_fetch_exchange_data') as mock_fetch:
            mock_fetch.return_value = [
                {"symbol": "LOW", "volume_24h": 100000},
                {"symbol": "HIGH", "volume_24h": 900000},
                {"symbol": "MID", "volume_24h": 500000},
            ]

            trending = tracker.get_trending_tokens(sort_by="volume")

            assert trending[0]["symbol"] == "HIGH"
            assert trending[1]["symbol"] == "MID"
            assert trending[2]["symbol"] == "LOW"

    def test_trending_tokens_filter_by_change(self, temp_dir):
        """Test filtering trending tokens by price change."""
        from core.social.trending_tracker import TrendingTokenTracker

        tracker = TrendingTokenTracker(data_dir=temp_dir)

        with patch.object(tracker, '_fetch_exchange_data') as mock_fetch:
            mock_fetch.return_value = [
                {"symbol": "PUMP", "volume_24h": 500000, "price_change_24h": 50.0},
                {"symbol": "STABLE", "volume_24h": 500000, "price_change_24h": 2.0},
                {"symbol": "DUMP", "volume_24h": 500000, "price_change_24h": -30.0},
            ]

            # Filter for gainers only (>10%)
            trending = tracker.get_trending_tokens(min_change=10)

            assert len(trending) == 1
            assert trending[0]["symbol"] == "PUMP"

    def test_cache_trending_data(self, temp_dir):
        """Test that trending data is cached."""
        from core.social.trending_tracker import TrendingTokenTracker

        tracker = TrendingTokenTracker(data_dir=temp_dir)

        tracker._cache_trending_data([
            {"symbol": "SOL", "volume_24h": 1000000}
        ])

        cache_file = temp_dir / "trending_tokens.json"
        assert cache_file.exists()

    def test_load_cached_data(self, temp_dir):
        """Test loading cached trending data."""
        from core.social.trending_tracker import TrendingTokenTracker

        # Pre-create cache file
        cache_data = {
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "tokens": [{"symbol": "SOL", "volume_24h": 1000000}]
        }
        cache_file = temp_dir / "trending_tokens.json"
        cache_file.write_text(json.dumps(cache_data))

        tracker = TrendingTokenTracker(data_dir=temp_dir)
        cached = tracker.get_cached_trending()

        assert len(cached) == 1
        assert cached[0]["symbol"] == "SOL"


class TestPumpDumpDetection:
    """Tests for pump/dump pattern detection."""

    def test_detect_pump_pattern(self, temp_dir):
        """Test detection of pump pattern."""
        from core.social.trending_tracker import PumpDumpDetector

        detector = PumpDumpDetector(data_dir=temp_dir)

        # Price rapidly increasing with high volume
        price_data = {
            "symbol": "PUMP",
            "prices": [1.0, 1.5, 2.0, 3.0, 4.5],  # 350% increase
            "volumes": [100000, 200000, 500000, 800000, 1000000],
            "timestamps": list(range(5))
        }

        result = detector.detect_pump(price_data)

        assert result["is_pump"] is True
        assert result["confidence"] >= 0.7

    def test_detect_dump_pattern(self, temp_dir):
        """Test detection of dump pattern."""
        from core.social.trending_tracker import PumpDumpDetector

        detector = PumpDumpDetector(data_dir=temp_dir)

        # Price rapidly decreasing
        price_data = {
            "symbol": "DUMP",
            "prices": [10.0, 8.0, 5.0, 3.0, 1.5],  # 85% decrease
            "volumes": [500000, 800000, 1000000, 600000, 400000],
            "timestamps": list(range(5))
        }

        result = detector.detect_dump(price_data)

        assert result["is_dump"] is True
        assert result["confidence"] >= 0.7

    def test_detect_pump_and_dump(self, temp_dir):
        """Test detection of pump followed by dump."""
        from core.social.trending_tracker import PumpDumpDetector

        detector = PumpDumpDetector(data_dir=temp_dir)

        # Classic pump and dump pattern
        price_data = {
            "symbol": "SCAM",
            "prices": [1.0, 2.0, 4.0, 5.0, 2.0, 0.5],
            "volumes": [100000, 300000, 800000, 1200000, 900000, 500000],
            "timestamps": list(range(6))
        }

        result = detector.detect_pump_and_dump(price_data)

        assert result["pattern_detected"] is True
        assert result["risk_level"] in ["high", "extreme"]

    def test_no_pattern_stable_price(self, temp_dir):
        """Test no pattern for stable prices."""
        from core.social.trending_tracker import PumpDumpDetector

        detector = PumpDumpDetector(data_dir=temp_dir)

        # Stable price movement
        price_data = {
            "symbol": "STABLE",
            "prices": [10.0, 10.2, 9.8, 10.1, 10.0],
            "volumes": [100000, 110000, 95000, 105000, 100000],
            "timestamps": list(range(5))
        }

        result = detector.detect_pump(price_data)
        assert result["is_pump"] is False

        result = detector.detect_dump(price_data)
        assert result["is_dump"] is False

    def test_pump_detection_thresholds(self, temp_dir):
        """Test configurable pump detection thresholds."""
        from core.social.trending_tracker import PumpDumpDetector

        detector = PumpDumpDetector(
            data_dir=temp_dir,
            pump_threshold=0.5,  # 50% increase
            volume_multiplier=3.0  # 3x volume spike
        )

        assert detector.pump_threshold == 0.5
        assert detector.volume_multiplier == 3.0

    def test_get_risk_tokens(self, temp_dir):
        """Test getting list of risky tokens."""
        from core.social.trending_tracker import PumpDumpDetector

        detector = PumpDumpDetector(data_dir=temp_dir)

        # Add some detected patterns
        detector._flagged_tokens = {
            "SCAM1": {"risk": "high", "pattern": "pump_and_dump"},
            "SCAM2": {"risk": "medium", "pattern": "pump"},
        }

        risky = detector.get_risk_tokens()

        assert len(risky) == 2
        assert "SCAM1" in [t["symbol"] for t in risky]


class TestMentionTracking:
    """Tests for social mention spike tracking."""

    def test_mention_tracker_init(self, temp_dir):
        """Test MentionTracker initialization."""
        from core.social.trending_tracker import MentionTracker

        tracker = MentionTracker(data_dir=temp_dir)
        assert tracker is not None

    def test_track_mention_count(self, temp_dir):
        """Test tracking mention counts."""
        from core.social.trending_tracker import MentionTracker

        tracker = MentionTracker(data_dir=temp_dir)

        # Record mentions
        tracker.record_mention("SOL", count=50)
        tracker.record_mention("SOL", count=75)
        tracker.record_mention("BTC", count=100)

        stats = tracker.get_mention_stats("SOL")

        assert stats is not None
        assert stats["total_mentions"] == 125

    def test_detect_mention_spike(self, temp_dir):
        """Test detection of mention spike."""
        from core.social.trending_tracker import MentionTracker

        tracker = MentionTracker(data_dir=temp_dir)

        # Historical baseline (low mentions)
        for i in range(10):
            tracker.record_mention("WIF", count=10, timestamp=datetime.now(timezone.utc) - timedelta(hours=i+2))

        # Sudden spike
        tracker.record_mention("WIF", count=200, timestamp=datetime.now(timezone.utc))

        spike = tracker.detect_spike("WIF")

        assert spike["is_spike"] is True
        assert spike["multiplier"] >= 10  # 10x increase

    def test_no_spike_normal_activity(self, temp_dir):
        """Test no spike for normal activity."""
        from core.social.trending_tracker import MentionTracker

        tracker = MentionTracker(data_dir=temp_dir)

        # Consistent mentions
        for i in range(10):
            tracker.record_mention("SOL", count=50)

        spike = tracker.detect_spike("SOL")

        assert spike["is_spike"] is False

    def test_get_trending_by_mentions(self, temp_dir):
        """Test getting tokens trending by mentions."""
        from core.social.trending_tracker import MentionTracker

        tracker = MentionTracker(data_dir=temp_dir)

        tracker.record_mention("SOL", count=100)
        tracker.record_mention("WIF", count=500)
        tracker.record_mention("BTC", count=200)

        trending = tracker.get_trending_by_mentions(limit=3)

        assert trending[0]["symbol"] == "WIF"
        assert trending[1]["symbol"] == "BTC"
        assert trending[2]["symbol"] == "SOL"

    @pytest.mark.asyncio
    async def test_fetch_twitter_mentions(self, temp_dir):
        """Test fetching mentions from Twitter."""
        from core.social.trending_tracker import MentionTracker

        tracker = MentionTracker(data_dir=temp_dir)

        with patch.object(tracker, '_twitter_client') as mock_client:
            mock_client.search_recent = AsyncMock(return_value=[
                {"text": "$SOL looking good"},
                {"text": "$SOL to the moon"},
                {"text": "Buy $SOL now"},
            ])

            count = await tracker.fetch_twitter_mentions("SOL")

            assert count == 3

    def test_mention_history_persistence(self, temp_dir):
        """Test that mention history is persisted."""
        from core.social.trending_tracker import MentionTracker

        tracker = MentionTracker(data_dir=temp_dir)

        tracker.record_mention("SOL", count=100)
        tracker.save_history()

        history_file = temp_dir / "mention_history.json"
        assert history_file.exists()

        # Create new tracker and verify data loads
        tracker2 = MentionTracker(data_dir=temp_dir)
        stats = tracker2.get_mention_stats("SOL")

        assert stats["total_mentions"] == 100


class TestTrendingIntegration:
    """Integration tests combining all tracking features."""

    def test_comprehensive_trending_report(self, temp_dir):
        """Test generating comprehensive trending report."""
        from core.social.trending_tracker import TrendingTokenTracker, PumpDumpDetector, MentionTracker

        token_tracker = TrendingTokenTracker(data_dir=temp_dir)
        pump_detector = PumpDumpDetector(data_dir=temp_dir)
        mention_tracker = MentionTracker(data_dir=temp_dir)

        # Mock data
        with patch.object(token_tracker, '_fetch_exchange_data') as mock_fetch:
            mock_fetch.return_value = [
                {"symbol": "SOL", "volume_24h": 1000000, "price_change_24h": 15.5},
            ]

            mention_tracker.record_mention("SOL", count=500)

            trending = token_tracker.get_trending_tokens()
            mentions = mention_tracker.get_trending_by_mentions()

            assert len(trending) >= 1
            assert len(mentions) >= 1

    def test_alert_generation(self, temp_dir):
        """Test alert generation for significant events."""
        from core.social.trending_tracker import TrendingTokenTracker

        tracker = TrendingTokenTracker(data_dir=temp_dir)

        # Configure alerts
        tracker.configure_alerts(
            pump_threshold=0.5,
            mention_spike_multiplier=5.0
        )

        alerts = tracker.get_active_alerts()

        assert isinstance(alerts, list)
