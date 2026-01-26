"""
Comprehensive Unit Tests for Twitter A/B Testing Framework.

Tests cover:
- ABTestResult dataclass creation and serialization
- ABTestingFramework initialization and database setup
- Variant assignment (hash-based determinism)
- Engagement tracking
- Test results aggregation
- Weekly report generation
- Optimal settings retrieval
- Export functionality
- Edge cases and error handling

Target: 85%+ code coverage for bots/twitter/ab_testing.py
"""

import pytest
import json
import sqlite3
import tempfile
import hashlib
from pathlib import Path
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock, mock_open
from dataclasses import asdict

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from bots.twitter.ab_testing import (
    ABTestResult,
    ABTestingFramework,
    DEFAULT_DATA_DIR,
)


# =============================================================================
# ABTestResult Dataclass Tests
# =============================================================================

class TestABTestResult:
    """Tests for the ABTestResult dataclass."""

    def test_create_result_with_all_fields(self):
        """Test creating ABTestResult with all fields."""
        result = ABTestResult(
            test_name="emoji_test",
            variant="treatment",
            tweet_id="12345",
            impressions=1000,
            engagements=50,
            retweets=10,
            replies=5,
            clicks=20,
            engagement_rate=5.0,
            recorded_at="2026-01-26T00:00:00Z"
        )

        assert result.test_name == "emoji_test"
        assert result.variant == "treatment"
        assert result.tweet_id == "12345"
        assert result.impressions == 1000
        assert result.engagements == 50
        assert result.retweets == 10
        assert result.replies == 5
        assert result.clicks == 20
        assert result.engagement_rate == 5.0
        assert result.recorded_at == "2026-01-26T00:00:00Z"

    def test_create_result_with_defaults(self):
        """Test ABTestResult uses default values."""
        result = ABTestResult(
            test_name="tone_test",
            variant="control",
            tweet_id="67890"
        )

        assert result.impressions == 0
        assert result.engagements == 0
        assert result.retweets == 0
        assert result.replies == 0
        assert result.clicks == 0
        assert result.engagement_rate == 0.0
        assert result.recorded_at == ""

    def test_result_to_dict(self):
        """Test converting ABTestResult to dictionary."""
        result = ABTestResult(
            test_name="cta_test",
            variant="link",
            tweet_id="999",
            impressions=500
        )

        result_dict = asdict(result)
        assert result_dict["test_name"] == "cta_test"
        assert result_dict["variant"] == "link"
        assert result_dict["impressions"] == 500

    def test_result_equality(self):
        """Test ABTestResult equality comparison."""
        result1 = ABTestResult("test", "variant", "id1", impressions=100)
        result2 = ABTestResult("test", "variant", "id1", impressions=100)

        assert result1 == result2

    def test_result_inequality(self):
        """Test ABTestResult inequality."""
        result1 = ABTestResult("test", "variant", "id1", impressions=100)
        result2 = ABTestResult("test", "variant", "id1", impressions=200)

        assert result1 != result2


# =============================================================================
# ABTestingFramework Initialization Tests
# =============================================================================

class TestABTestingFrameworkInit:
    """Tests for ABTestingFramework initialization."""

    @pytest.fixture
    def temp_data_dir(self, tmp_path):
        """Create temporary data directory."""
        return tmp_path / "test_data"

    def test_framework_init_creates_directory(self, temp_data_dir):
        """Test framework creates data directory if not exists."""
        assert not temp_data_dir.exists()

        framework = ABTestingFramework(data_dir=temp_data_dir)

        assert temp_data_dir.exists()
        assert framework.data_dir == temp_data_dir

    def test_framework_init_creates_database(self, temp_data_dir):
        """Test framework creates SQLite database."""
        framework = ABTestingFramework(data_dir=temp_data_dir)

        db_path = temp_data_dir / "ab_testing.db"
        assert db_path.exists()
        assert framework.db_path == db_path

    def test_framework_init_creates_table(self, temp_data_dir):
        """Test framework creates ab_results table."""
        framework = ABTestingFramework(data_dir=temp_data_dir)

        with framework._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='ab_results'"
            )
            result = cursor.fetchone()
            assert result is not None
            assert result[0] == "ab_results"

    def test_framework_init_creates_indexes(self, temp_data_dir):
        """Test framework creates indexes."""
        framework = ABTestingFramework(data_dir=temp_data_dir)

        with framework._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='index'"
            )
            indexes = [row[0] for row in cursor.fetchall()]

            assert "idx_ab_test" in indexes
            assert "idx_ab_variant" in indexes
            assert "idx_ab_recorded" in indexes

    def test_framework_init_uses_default_dir(self):
        """Test framework uses DEFAULT_DATA_DIR when not specified."""
        with patch.object(Path, 'mkdir'):
            with patch('bots.twitter.ab_testing.sqlite3.connect') as mock_connect:
                mock_conn = MagicMock()
                mock_connect.return_value = mock_conn
                mock_conn.__enter__ = MagicMock(return_value=mock_conn)
                mock_conn.__exit__ = MagicMock(return_value=False)
                mock_cursor = MagicMock()
                mock_conn.cursor.return_value = mock_cursor

                framework = ABTestingFramework()

                assert framework.data_dir == DEFAULT_DATA_DIR

    def test_framework_tests_constant(self, temp_data_dir):
        """Test TESTS constant is correctly defined."""
        framework = ABTestingFramework(data_dir=temp_data_dir)

        assert "emoji_usage" in framework.TESTS
        assert "tone" in framework.TESTS
        assert "cta_style" in framework.TESTS
        assert "tweet_length" in framework.TESTS
        assert "posting_time" in framework.TESTS

    def test_framework_emoji_usage_variants(self, temp_data_dir):
        """Test emoji_usage test has correct variants."""
        framework = ABTestingFramework(data_dir=temp_data_dir)

        assert framework.TESTS["emoji_usage"]["variants"] == ["many", "minimal", "none"]
        assert "description" in framework.TESTS["emoji_usage"]

    def test_framework_tone_variants(self, temp_data_dir):
        """Test tone test has correct variants."""
        framework = ABTestingFramework(data_dir=temp_data_dir)

        assert framework.TESTS["tone"]["variants"] == ["casual", "professional", "sarcastic"]

    def test_framework_posting_time_variants(self, temp_data_dir):
        """Test posting_time test has correct variants."""
        framework = ABTestingFramework(data_dir=temp_data_dir)

        assert framework.TESTS["posting_time"]["variants"] == ["morning", "afternoon", "evening", "night"]


# =============================================================================
# Database Connection Tests
# =============================================================================

class TestDatabaseConnection:
    """Tests for database connection context manager."""

    @pytest.fixture
    def framework(self, tmp_path):
        """Create framework with temp directory."""
        return ABTestingFramework(data_dir=tmp_path / "test_data")

    def test_get_connection_returns_connection(self, framework):
        """Test _get_connection yields a connection."""
        with framework._get_connection() as conn:
            assert conn is not None
            assert isinstance(conn, sqlite3.Connection)

    def test_get_connection_sets_row_factory(self, framework):
        """Test connection has Row factory set."""
        with framework._get_connection() as conn:
            assert conn.row_factory == sqlite3.Row

    def test_connection_is_closed_after_context(self, framework):
        """Test connection is properly closed after context."""
        with framework._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1")

        # Connection should be closed - attempting to use it should fail
        with pytest.raises(sqlite3.ProgrammingError):
            conn.execute("SELECT 1")


# =============================================================================
# Variant Assignment Tests
# =============================================================================

class TestVariantAssignment:
    """Tests for variant assignment logic."""

    @pytest.fixture
    def framework(self, tmp_path):
        """Create framework with temp directory."""
        return ABTestingFramework(data_dir=tmp_path / "test_data")

    def test_assign_variant_unknown_test_returns_control(self, framework):
        """Test unknown test name returns 'control'."""
        result = framework.assign_variant("tweet_123", "unknown_test")
        assert result == "control"

    def test_assign_variant_deterministic(self, framework):
        """Test same tweet_id and test_name always return same variant."""
        variant1 = framework.assign_variant("tweet_123", "emoji_usage")
        variant2 = framework.assign_variant("tweet_123", "emoji_usage")

        assert variant1 == variant2

    def test_assign_variant_different_tweets_may_differ(self, framework):
        """Test different tweet IDs may get different variants."""
        # With enough tweets, we should get different variants
        variants = set()
        for i in range(100):
            variant = framework.assign_variant(f"tweet_{i}", "emoji_usage")
            variants.add(variant)

        # Should have multiple variants (emoji_usage has 3: many, minimal, none)
        assert len(variants) > 1

    def test_assign_variant_for_two_variant_test(self, framework):
        """Test two-variant test returns treatment/control."""
        # Create a test with exactly 2 variants
        framework.TESTS["binary_test"] = {
            "variants": ["A", "B"],
            "description": "Binary test"
        }

        results = set()
        for i in range(100):
            variant = framework.assign_variant(f"tweet_{i}", "binary_test")
            results.add(variant)

        # For 2-variant tests, should return treatment or control
        assert results == {"treatment", "control"}

    def test_assign_variant_for_multi_variant_test(self, framework):
        """Test multi-variant test returns actual variant names."""
        results = set()
        for i in range(100):
            variant = framework.assign_variant(f"tweet_{i}", "emoji_usage")
            results.add(variant)

        # Should get the actual variant names for 3+ variants
        expected_variants = set(framework.TESTS["emoji_usage"]["variants"])
        assert results.issubset(expected_variants)

    def test_assign_variant_hash_consistency(self, framework):
        """Test the hash-based assignment is consistent."""
        tweet_id = "consistent_tweet_id"
        test_name = "tone"

        # Manually compute expected behavior
        hash_input = f"{tweet_id}:{test_name}"
        hash_value = int(hashlib.md5(hash_input.encode()).hexdigest(), 16)
        variants = framework.TESTS[test_name]["variants"]
        expected_index = hash_value % len(variants)
        expected_variant = variants[expected_index]

        actual_variant = framework.assign_variant(tweet_id, test_name)
        assert actual_variant == expected_variant

    def test_assign_variant_distribution_roughly_even(self, framework):
        """Test variants are distributed roughly evenly."""
        variant_counts = {}
        total = 1000

        for i in range(total):
            variant = framework.assign_variant(f"tweet_{i}", "tone")
            variant_counts[variant] = variant_counts.get(variant, 0) + 1

        # Each of 3 variants should get roughly 33% (allow 20-45% range)
        for variant, count in variant_counts.items():
            ratio = count / total
            assert 0.2 <= ratio <= 0.45, f"Variant {variant} got {ratio*100:.1f}%"


# =============================================================================
# Engagement Tracking Tests
# =============================================================================

class TestEngagementTracking:
    """Tests for engagement tracking."""

    @pytest.fixture
    def framework(self, tmp_path):
        """Create framework with temp directory."""
        return ABTestingFramework(data_dir=tmp_path / "test_data")

    def test_track_engagement_creates_record(self, framework):
        """Test track_engagement inserts a record."""
        framework.track_engagement(
            tweet_id="test_tweet_1",
            test_name="emoji_usage",
            variant="many",
            impressions=1000,
            engagements=50,
            retweets=10,
            replies=5,
            clicks=15
        )

        with framework._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM ab_results WHERE tweet_id = ?", ("test_tweet_1",))
            row = cursor.fetchone()

            assert row is not None
            assert row["test_name"] == "emoji_usage"
            assert row["variant"] == "many"
            assert row["impressions"] == 1000
            assert row["engagements"] == 50

    def test_track_engagement_calculates_rate(self, framework):
        """Test engagement rate is calculated correctly."""
        framework.track_engagement(
            tweet_id="rate_tweet",
            test_name="tone",
            variant="casual",
            impressions=1000,
            engagements=50
        )

        with framework._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT engagement_rate FROM ab_results WHERE tweet_id = ?", ("rate_tweet",))
            row = cursor.fetchone()

            # 50/1000 * 100 = 5.0
            assert row["engagement_rate"] == 5.0

    def test_track_engagement_zero_impressions(self, framework):
        """Test engagement rate is 0 when impressions is 0."""
        framework.track_engagement(
            tweet_id="zero_tweet",
            test_name="cta_style",
            variant="link",
            impressions=0,
            engagements=10
        )

        with framework._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT engagement_rate FROM ab_results WHERE tweet_id = ?", ("zero_tweet",))
            row = cursor.fetchone()

            assert row["engagement_rate"] == 0.0

    def test_track_engagement_updates_existing(self, framework):
        """Test track_engagement replaces existing record for same test/tweet."""
        # Insert initial record
        framework.track_engagement(
            tweet_id="update_tweet",
            test_name="tone",
            variant="casual",
            impressions=500,
            engagements=20
        )

        # Update with new metrics
        framework.track_engagement(
            tweet_id="update_tweet",
            test_name="tone",
            variant="casual",
            impressions=1000,
            engagements=50
        )

        with framework._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COUNT(*), impressions FROM ab_results WHERE tweet_id = ? AND test_name = ?",
                ("update_tweet", "tone")
            )
            row = cursor.fetchone()

            # Should have only 1 record with updated values
            assert row[0] == 1
            assert row["impressions"] == 1000

    def test_track_engagement_records_timestamp(self, framework):
        """Test engagement tracking records timestamp."""
        framework.track_engagement(
            tweet_id="time_tweet",
            test_name="emoji_usage",
            variant="minimal",
            impressions=100
        )

        with framework._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT recorded_at FROM ab_results WHERE tweet_id = ?", ("time_tweet",))
            row = cursor.fetchone()

            assert row["recorded_at"] is not None
            # Should be ISO format
            datetime.fromisoformat(row["recorded_at"].replace('Z', '+00:00'))

    def test_track_engagement_with_all_metrics(self, framework):
        """Test all metrics are stored correctly."""
        framework.track_engagement(
            tweet_id="full_tweet",
            test_name="tweet_length",
            variant="medium",
            impressions=5000,
            engagements=250,
            retweets=30,
            replies=20,
            clicks=100
        )

        with framework._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM ab_results WHERE tweet_id = ?", ("full_tweet",))
            row = cursor.fetchone()

            assert row["impressions"] == 5000
            assert row["engagements"] == 250
            assert row["retweets"] == 30
            assert row["replies"] == 20
            assert row["clicks"] == 100
            assert row["engagement_rate"] == 5.0  # 250/5000 * 100


# =============================================================================
# Test Results Aggregation Tests
# =============================================================================

class TestResultsAggregation:
    """Tests for test results aggregation."""

    @pytest.fixture
    def framework_with_data(self, tmp_path):
        """Create framework with sample data."""
        framework = ABTestingFramework(data_dir=tmp_path / "test_data")

        # Insert sample data for emoji_usage test
        for i in range(20):
            variant = "many" if i % 2 == 0 else "minimal"
            impressions = 1000 + (i * 10)
            engagements = 50 + i

            framework.track_engagement(
                tweet_id=f"tweet_{i}",
                test_name="emoji_usage",
                variant=variant,
                impressions=impressions,
                engagements=engagements,
                retweets=i,
                replies=i // 2,
                clicks=i * 2
            )

        return framework

    def test_get_test_results_returns_data(self, framework_with_data):
        """Test get_test_results returns aggregated data."""
        results = framework_with_data.get_test_results("emoji_usage")

        assert results is not None
        assert "many" in results
        assert "minimal" in results

    def test_get_test_results_has_sample_size(self, framework_with_data):
        """Test results include sample size."""
        results = framework_with_data.get_test_results("emoji_usage")

        assert results["many"]["sample_size"] == 10
        assert results["minimal"]["sample_size"] == 10

    def test_get_test_results_has_averages(self, framework_with_data):
        """Test results include average metrics."""
        results = framework_with_data.get_test_results("emoji_usage")

        for variant in ["many", "minimal"]:
            data = results[variant]
            assert "avg_impressions" in data
            assert "avg_engagements" in data
            assert "avg_retweets" in data
            assert "avg_replies" in data
            assert "avg_clicks" in data
            assert "avg_engagement_rate" in data

    def test_get_test_results_respects_days_parameter(self, framework_with_data):
        """Test days parameter filters results."""
        # All data is recent, so should be included
        results_7_days = framework_with_data.get_test_results("emoji_usage", days=7)
        assert results_7_days is not None

        # With 0 days, nothing should match
        results_0_days = framework_with_data.get_test_results("emoji_usage", days=0)
        assert results_0_days is None or len(results_0_days) == 0

    def test_get_test_results_empty_for_unknown_test(self, framework_with_data):
        """Test get_test_results returns None for unknown test."""
        results = framework_with_data.get_test_results("nonexistent_test")
        assert results is None

    def test_get_test_results_rounds_values(self, framework_with_data):
        """Test results are properly rounded."""
        results = framework_with_data.get_test_results("emoji_usage")

        for variant_data in results.values():
            # Check avg_engagement_rate has max 4 decimal places
            rate_str = str(variant_data["avg_engagement_rate"])
            if "." in rate_str:
                decimals = len(rate_str.split(".")[1])
                assert decimals <= 4


# =============================================================================
# Available Tests Retrieval
# =============================================================================

class TestAvailableTests:
    """Tests for get_available_tests method."""

    @pytest.fixture
    def framework(self, tmp_path):
        """Create framework with temp directory."""
        return ABTestingFramework(data_dir=tmp_path / "test_data")

    def test_get_available_tests_returns_all(self, framework):
        """Test get_available_tests returns all defined tests."""
        tests = framework.get_available_tests()

        assert "emoji_usage" in tests
        assert "tone" in tests
        assert "cta_style" in tests
        assert "tweet_length" in tests
        assert "posting_time" in tests

    def test_get_available_tests_returns_copy(self, framework):
        """Test get_available_tests returns a copy (not reference)."""
        tests1 = framework.get_available_tests()
        tests2 = framework.get_available_tests()

        # Modifying one should not affect the other
        tests1["new_test"] = {"variants": ["a", "b"]}
        assert "new_test" not in tests2

    def test_get_available_tests_includes_variants(self, framework):
        """Test returned tests include variants."""
        tests = framework.get_available_tests()

        for test_name, test_config in tests.items():
            assert "variants" in test_config
            assert isinstance(test_config["variants"], list)
            assert len(test_config["variants"]) >= 2

    def test_get_available_tests_includes_descriptions(self, framework):
        """Test returned tests include descriptions."""
        tests = framework.get_available_tests()

        for test_name, test_config in tests.items():
            assert "description" in test_config
            assert isinstance(test_config["description"], str)


# =============================================================================
# Weekly Report Generation Tests
# =============================================================================

class TestWeeklyReport:
    """Tests for weekly report generation."""

    @pytest.fixture
    def framework_with_data(self, tmp_path):
        """Create framework with sample data."""
        framework = ABTestingFramework(data_dir=tmp_path / "test_data")

        # Insert data for multiple tests
        for test_name in ["emoji_usage", "tone"]:
            for i in range(15):
                if test_name == "emoji_usage":
                    variant = ["many", "minimal", "none"][i % 3]
                else:
                    variant = ["casual", "professional", "sarcastic"][i % 3]

                engagement_rate = 5.0 + (i * 0.5) if variant in ["many", "casual"] else 3.0 + (i * 0.3)

                framework.track_engagement(
                    tweet_id=f"{test_name}_{i}",
                    test_name=test_name,
                    variant=variant,
                    impressions=1000,
                    engagements=int(engagement_rate * 10)
                )

        return framework

    def test_generate_weekly_report_structure(self, framework_with_data):
        """Test weekly report has correct structure."""
        report = framework_with_data.generate_weekly_report()

        assert "generated_at" in report
        assert "period_days" in report
        assert report["period_days"] == 7
        assert "tests" in report

    def test_generate_weekly_report_includes_active_tests(self, framework_with_data):
        """Test report includes tests with data."""
        report = framework_with_data.generate_weekly_report()

        assert "emoji_usage" in report["tests"]
        assert "tone" in report["tests"]

    def test_generate_weekly_report_has_winner(self, framework_with_data):
        """Test report identifies winning variant."""
        report = framework_with_data.generate_weekly_report()

        for test_name, test_data in report["tests"].items():
            assert "winner" in test_data
            assert test_data["winner"] is not None

    def test_generate_weekly_report_has_recommendation(self, framework_with_data):
        """Test report includes recommendation."""
        report = framework_with_data.generate_weekly_report()

        for test_name, test_data in report["tests"].items():
            assert "recommendation" in test_data
            assert isinstance(test_data["recommendation"], str)

    def test_generate_weekly_report_has_variants(self, framework_with_data):
        """Test report includes variant data."""
        report = framework_with_data.generate_weekly_report()

        for test_name, test_data in report["tests"].items():
            assert "variants" in test_data
            assert len(test_data["variants"]) > 0

    def test_generate_weekly_report_empty_database(self, tmp_path):
        """Test report handles empty database."""
        framework = ABTestingFramework(data_dir=tmp_path / "empty_data")
        report = framework.generate_weekly_report()

        assert report["tests"] == {}

    def test_generate_weekly_report_timestamp_format(self, framework_with_data):
        """Test generated_at is valid ISO format."""
        report = framework_with_data.generate_weekly_report()

        # Should be able to parse as datetime
        datetime.fromisoformat(report["generated_at"].replace('Z', '+00:00'))


# =============================================================================
# Recommendation Generation Tests
# =============================================================================

class TestRecommendations:
    """Tests for recommendation generation."""

    @pytest.fixture
    def framework(self, tmp_path):
        """Create framework with temp directory."""
        return ABTestingFramework(data_dir=tmp_path / "test_data")

    def test_recommendation_insufficient_data_no_winner(self, framework):
        """Test recommendation when no winner."""
        result = framework._get_recommendation("test", {}, None)
        assert "Insufficient data" in result

    def test_recommendation_insufficient_data_empty_results(self, framework):
        """Test recommendation with empty results."""
        result = framework._get_recommendation("test", {}, "variant")
        assert "Insufficient data" in result

    def test_recommendation_needs_more_data(self, framework):
        """Test recommendation when sample size < 10."""
        results = {
            "treatment": {
                "sample_size": 5,
                "avg_engagement_rate": 5.0
            }
        }
        result = framework._get_recommendation("test", results, "treatment")
        assert "Need more data" in result
        assert "5 samples" in result

    def test_recommendation_success(self, framework):
        """Test successful recommendation."""
        results = {
            "treatment": {
                "sample_size": 15,
                "avg_engagement_rate": 7.5
            }
        }
        result = framework._get_recommendation("test", results, "treatment")

        assert "Use 'treatment' variant" in result
        assert "7.50%" in result
        assert "n=15" in result


# =============================================================================
# Optimal Settings Tests
# =============================================================================

class TestOptimalSettings:
    """Tests for optimal settings retrieval."""

    @pytest.fixture
    def framework_with_data(self, tmp_path):
        """Create framework with varied engagement data."""
        framework = ABTestingFramework(data_dir=tmp_path / "test_data")

        # emoji_usage - "many" has highest engagement
        for i in range(10):
            framework.track_engagement(
                tweet_id=f"emoji_many_{i}",
                test_name="emoji_usage",
                variant="many",
                impressions=1000,
                engagements=80  # 8% rate
            )
            framework.track_engagement(
                tweet_id=f"emoji_minimal_{i}",
                test_name="emoji_usage",
                variant="minimal",
                impressions=1000,
                engagements=50  # 5% rate
            )

        # tone - "casual" has highest engagement
        for i in range(10):
            framework.track_engagement(
                tweet_id=f"tone_casual_{i}",
                test_name="tone",
                variant="casual",
                impressions=1000,
                engagements=90  # 9% rate
            )
            framework.track_engagement(
                tweet_id=f"tone_professional_{i}",
                test_name="tone",
                variant="professional",
                impressions=1000,
                engagements=60  # 6% rate
            )

        return framework

    def test_get_optimal_settings_returns_best_variants(self, framework_with_data):
        """Test optimal settings returns best performing variants."""
        optimal = framework_with_data.get_optimal_settings()

        assert optimal.get("emoji_usage") == "many"
        assert optimal.get("tone") == "casual"

    def test_get_optimal_settings_respects_minimum_samples(self, tmp_path):
        """Test optimal settings requires minimum sample size."""
        framework = ABTestingFramework(data_dir=tmp_path / "test_data")

        # Only 3 samples - below minimum of 5
        for i in range(3):
            framework.track_engagement(
                tweet_id=f"small_{i}",
                test_name="emoji_usage",
                variant="many",
                impressions=1000,
                engagements=80
            )

        optimal = framework.get_optimal_settings()
        assert "emoji_usage" not in optimal

    def test_get_optimal_settings_empty_database(self, tmp_path):
        """Test optimal settings with empty database."""
        framework = ABTestingFramework(data_dir=tmp_path / "empty_data")
        optimal = framework.get_optimal_settings()

        assert optimal == {}

    def test_get_optimal_settings_uses_30_days(self, tmp_path):
        """Test optimal settings uses 30-day window."""
        framework = ABTestingFramework(data_dir=tmp_path / "test_data")

        # Insert old data (manually modify timestamp)
        with framework._get_connection() as conn:
            cursor = conn.cursor()
            old_date = (datetime.now(timezone.utc) - timedelta(days=45)).isoformat()
            cursor.execute("""
                INSERT INTO ab_results (test_name, variant, tweet_id, impressions, engagements, engagement_rate, recorded_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, ("emoji_usage", "many", "old_tweet", 1000, 80, 8.0, old_date))
            conn.commit()

        optimal = framework.get_optimal_settings()
        # Old data should not be included
        assert "emoji_usage" not in optimal


# =============================================================================
# Export Functionality Tests
# =============================================================================

class TestExportResults:
    """Tests for export functionality."""

    @pytest.fixture
    def framework_with_data(self, tmp_path):
        """Create framework with sample data."""
        framework = ABTestingFramework(data_dir=tmp_path / "test_data")

        for i in range(5):
            framework.track_engagement(
                tweet_id=f"export_tweet_{i}",
                test_name="emoji_usage",
                variant="many",
                impressions=1000,
                engagements=50
            )

        return framework

    def test_export_results_creates_file(self, framework_with_data):
        """Test export creates JSON file."""
        filepath = framework_with_data.export_results()

        assert filepath.exists()
        assert filepath.suffix == ".json"

    def test_export_results_valid_json(self, framework_with_data):
        """Test exported file is valid JSON."""
        filepath = framework_with_data.export_results()

        with open(filepath) as f:
            data = json.load(f)

        assert "exported_at" in data
        assert "total_records" in data
        assert "results" in data

    def test_export_results_includes_all_records(self, framework_with_data):
        """Test export includes all records."""
        filepath = framework_with_data.export_results()

        with open(filepath) as f:
            data = json.load(f)

        assert data["total_records"] == 5
        assert len(data["results"]) == 5

    def test_export_results_custom_path(self, framework_with_data, tmp_path):
        """Test export to custom path."""
        custom_path = tmp_path / "custom_export.json"
        filepath = framework_with_data.export_results(filepath=custom_path)

        assert filepath == custom_path
        assert filepath.exists()

    def test_export_results_default_filename(self, framework_with_data):
        """Test default filename includes date."""
        filepath = framework_with_data.export_results()

        today = datetime.now().strftime('%Y%m%d')
        assert f"ab_results_{today}" in filepath.name

    def test_export_results_empty_database(self, tmp_path):
        """Test export with empty database."""
        framework = ABTestingFramework(data_dir=tmp_path / "empty_data")
        filepath = framework.export_results()

        with open(filepath) as f:
            data = json.load(f)

        assert data["total_records"] == 0
        assert data["results"] == []


# =============================================================================
# Edge Cases and Error Handling Tests
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases and error handling."""

    @pytest.fixture
    def framework(self, tmp_path):
        """Create framework with temp directory."""
        return ABTestingFramework(data_dir=tmp_path / "test_data")

    def test_special_characters_in_tweet_id(self, framework):
        """Test handling of special characters in tweet_id."""
        tweet_id = "tweet-with_special.chars:123"
        framework.track_engagement(
            tweet_id=tweet_id,
            test_name="emoji_usage",
            variant="many",
            impressions=100
        )

        with framework._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM ab_results WHERE tweet_id = ?", (tweet_id,))
            row = cursor.fetchone()
            assert row is not None

    def test_unicode_in_variant(self, framework):
        """Test handling of unicode characters."""
        # Add a test with unicode variant
        framework.TESTS["unicode_test"] = {
            "variants": ["variant_emoji", "variant_standard"],
            "description": "Unicode test"
        }

        framework.track_engagement(
            tweet_id="unicode_tweet",
            test_name="unicode_test",
            variant="variant_emoji",
            impressions=100
        )

        results = framework.get_test_results("unicode_test")
        assert results is not None

    def test_very_large_impression_count(self, framework):
        """Test handling of very large numbers."""
        framework.track_engagement(
            tweet_id="viral_tweet",
            test_name="emoji_usage",
            variant="many",
            impressions=10000000,  # 10 million
            engagements=500000  # 500k
        )

        with framework._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT engagement_rate FROM ab_results WHERE tweet_id = ?", ("viral_tweet",))
            row = cursor.fetchone()
            assert row["engagement_rate"] == 5.0  # 500k/10M * 100

    def test_zero_engagements(self, framework):
        """Test handling of zero engagements."""
        framework.track_engagement(
            tweet_id="zero_engagement",
            test_name="tone",
            variant="professional",
            impressions=1000,
            engagements=0
        )

        with framework._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT engagement_rate FROM ab_results WHERE tweet_id = ?", ("zero_engagement",))
            row = cursor.fetchone()
            assert row["engagement_rate"] == 0.0

    def test_negative_metrics_handled(self, framework):
        """Test handling of negative values (edge case)."""
        # While not expected in real usage, should not crash
        framework.track_engagement(
            tweet_id="negative_tweet",
            test_name="emoji_usage",
            variant="none",
            impressions=-100,  # Invalid but should be stored
            engagements=10
        )

        with framework._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT impressions FROM ab_results WHERE tweet_id = ?", ("negative_tweet",))
            row = cursor.fetchone()
            assert row["impressions"] == -100

    def test_concurrent_writes(self, framework):
        """Test handling of concurrent writes to same tweet."""
        # Simulate concurrent updates
        for i in range(10):
            framework.track_engagement(
                tweet_id="concurrent_tweet",
                test_name="emoji_usage",
                variant="many",
                impressions=100 * (i + 1),
                engagements=5 * (i + 1)
            )

        # Should have only 1 record (last one wins)
        with framework._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM ab_results WHERE tweet_id = ?", ("concurrent_tweet",))
            count = cursor.fetchone()[0]
            assert count == 1


# =============================================================================
# Integration Tests
# =============================================================================

class TestIntegration:
    """Integration tests for full A/B testing workflow."""

    def test_full_ab_testing_workflow(self, tmp_path):
        """Test complete A/B testing workflow."""
        framework = ABTestingFramework(data_dir=tmp_path / "test_data")

        # 1. Get available tests
        tests = framework.get_available_tests()
        assert "emoji_usage" in tests

        # 2. Assign variants for multiple tweets
        tweet_variants = {}
        for i in range(20):
            tweet_id = f"workflow_tweet_{i}"
            variant = framework.assign_variant(tweet_id, "emoji_usage")
            tweet_variants[tweet_id] = variant

        # 3. Track engagement for all tweets
        for tweet_id, variant in tweet_variants.items():
            framework.track_engagement(
                tweet_id=tweet_id,
                test_name="emoji_usage",
                variant=variant,
                impressions=1000 + hash(tweet_id) % 500,
                engagements=50 + hash(tweet_id) % 30,
                retweets=5 + hash(tweet_id) % 10,
                replies=2 + hash(tweet_id) % 5,
                clicks=10 + hash(tweet_id) % 20
            )

        # 4. Get test results
        results = framework.get_test_results("emoji_usage")
        assert results is not None
        assert len(results) >= 1

        # 5. Generate weekly report
        report = framework.generate_weekly_report()
        assert "emoji_usage" in report["tests"]
        assert report["tests"]["emoji_usage"]["winner"] is not None

        # 6. Get optimal settings
        optimal = framework.get_optimal_settings()
        # May or may not have enough data, but should not crash

        # 7. Export results
        export_path = framework.export_results()
        assert export_path.exists()

        with open(export_path) as f:
            exported_data = json.load(f)
        assert exported_data["total_records"] == 20

    def test_multiple_tests_simultaneously(self, tmp_path):
        """Test tracking multiple A/B tests at once."""
        framework = ABTestingFramework(data_dir=tmp_path / "test_data")

        # Track same tweets in multiple tests
        for i in range(15):
            tweet_id = f"multi_test_tweet_{i}"

            for test_name in ["emoji_usage", "tone", "cta_style"]:
                variant = framework.assign_variant(tweet_id, test_name)
                framework.track_engagement(
                    tweet_id=f"{tweet_id}_{test_name}",  # Unique per test
                    test_name=test_name,
                    variant=variant,
                    impressions=1000,
                    engagements=50
                )

        # Check all tests have data
        for test_name in ["emoji_usage", "tone", "cta_style"]:
            results = framework.get_test_results(test_name)
            assert results is not None
            assert len(results) >= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
