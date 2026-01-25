"""
Tests for Usage Tracking & Cost Management Module.

Tests UsageTracker, quota management, cost estimation, and auto-reset.
Follows TDD approach - these tests are written before implementation.
"""

import pytest
import sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock
from decimal import Decimal


class TestUsageQuota:
    """Tests for UsageQuota dataclass."""

    def test_quota_creation(self):
        """Test UsageQuota creation with all fields."""
        from core.usage.tracker import UsageQuota

        reset_at = datetime.now(timezone.utc) + timedelta(hours=1)
        quota = UsageQuota(
            name="hourly",
            limit=50_000,
            period="hour",
            used=10_000,
            reset_at=reset_at,
        )

        assert quota.name == "hourly"
        assert quota.limit == 50_000
        assert quota.period == "hour"
        assert quota.used == 10_000
        assert quota.reset_at == reset_at

    def test_quota_remaining(self):
        """Test remaining tokens calculation."""
        from core.usage.tracker import UsageQuota

        quota = UsageQuota(
            name="hourly",
            limit=50_000,
            period="hour",
            used=10_000,
            reset_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )

        assert quota.remaining == 40_000

    def test_quota_remaining_never_negative(self):
        """Test remaining never goes negative when overused."""
        from core.usage.tracker import UsageQuota

        quota = UsageQuota(
            name="hourly",
            limit=50_000,
            period="hour",
            used=60_000,  # Overused
            reset_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )

        assert quota.remaining == 0

    def test_quota_percentage_left(self):
        """Test percentage left calculation."""
        from core.usage.tracker import UsageQuota

        quota = UsageQuota(
            name="hourly",
            limit=100_000,
            period="hour",
            used=13_000,
            reset_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )

        assert quota.percentage_left == 87.0

    def test_quota_time_until_reset(self):
        """Test time until reset calculation."""
        from core.usage.tracker import UsageQuota

        future_time = datetime.now(timezone.utc) + timedelta(hours=2, minutes=30)
        quota = UsageQuota(
            name="hourly",
            limit=50_000,
            period="hour",
            used=10_000,
            reset_at=future_time,
        )

        time_until = quota.time_until_reset
        # Should be approximately 2.5 hours
        assert time_until.total_seconds() > 8900  # > 2h 28min
        assert time_until.total_seconds() < 9100  # < 2h 32min

    def test_quota_unlimited(self):
        """Test unlimited quota (limit=-1)."""
        from core.usage.tracker import UsageQuota

        quota = UsageQuota(
            name="admin",
            limit=-1,  # Unlimited
            period="hour",
            used=1_000_000,
            reset_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )

        assert quota.is_unlimited is True
        assert quota.remaining == float('inf')
        assert quota.percentage_left == 100.0


class TestUsageRecord:
    """Tests for UsageRecord dataclass."""

    def test_usage_record_creation(self):
        """Test UsageRecord creation."""
        from core.usage.tracker import UsageRecord

        record = UsageRecord(
            user_id=123,
            session_id="session_abc",
            model_id="grok-3-mini",
            tokens_in=500,
            tokens_out=1000,
            estimated_cost=0.0015,
        )

        assert record.user_id == 123
        assert record.model_id == "grok-3-mini"
        assert record.tokens_in == 500
        assert record.tokens_out == 1000
        assert record.estimated_cost == 0.0015

    def test_usage_record_total_tokens(self):
        """Test total tokens calculation."""
        from core.usage.tracker import UsageRecord

        record = UsageRecord(
            user_id=123,
            session_id="session_abc",
            model_id="grok-3-mini",
            tokens_in=500,
            tokens_out=1000,
            estimated_cost=0.0015,
        )

        assert record.total_tokens == 1500


class TestUsageTracker:
    """Tests for UsageTracker class."""

    @pytest.fixture
    def tracker(self, tmp_path):
        """Create a UsageTracker with temp database."""
        from core.usage.tracker import UsageTracker

        db_path = tmp_path / "test_usage.db"
        return UsageTracker(db_path=db_path)

    @pytest.fixture
    def tracker_with_user(self, tracker):
        """Create tracker with an initialized user."""
        # Initialize a user with default quotas
        tracker._ensure_user_quotas(user_id=1)
        return tracker

    def test_tracker_initialization(self, tracker):
        """Test tracker creates database tables."""
        # Verify tables exist
        conn = sqlite3.connect(tracker.db_path)
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
        tables = {row[0] for row in cursor.fetchall()}
        conn.close()

        assert "usage_quotas" in tables
        assert "usage_history" in tables

    def test_track_usage_records_correctly(self, tracker_with_user):
        """Test track_usage records tokens and cost."""
        tracker = tracker_with_user

        tracker.track_usage(
            user_id=1,
            tokens_in=500,
            tokens_out=1000,
            model_id="grok-3-mini",
            session_id="session_123",
        )

        # Verify record was created
        conn = sqlite3.connect(tracker.db_path)
        cursor = conn.execute(
            "SELECT tokens_in, tokens_out, model_id FROM usage_history WHERE user_id = 1"
        )
        row = cursor.fetchone()
        conn.close()

        assert row is not None
        assert row[0] == 500
        assert row[1] == 1000
        assert row[2] == "grok-3-mini"

    def test_track_usage_updates_quota(self, tracker_with_user):
        """Test track_usage updates hourly quota."""
        tracker = tracker_with_user

        initial_quota = tracker.get_quota(user_id=1, period="hour")
        initial_used = initial_quota.used

        tracker.track_usage(
            user_id=1,
            tokens_in=500,
            tokens_out=1000,
            model_id="grok-3-mini",
        )

        updated_quota = tracker.get_quota(user_id=1, period="hour")
        assert updated_quota.used == initial_used + 1500

    def test_get_quota_hourly(self, tracker_with_user):
        """Test getting hourly quota."""
        tracker = tracker_with_user

        quota = tracker.get_quota(user_id=1, period="hour")

        assert quota is not None
        assert quota.period == "hour"
        assert quota.limit > 0

    def test_get_quota_daily(self, tracker_with_user):
        """Test getting daily quota."""
        tracker = tracker_with_user

        quota = tracker.get_quota(user_id=1, period="day")

        assert quota is not None
        assert quota.period == "day"
        assert quota.limit > 0

    def test_get_quota_monthly(self, tracker_with_user):
        """Test getting monthly quota."""
        tracker = tracker_with_user

        quota = tracker.get_quota(user_id=1, period="month")

        assert quota is not None
        assert quota.period == "month"
        assert quota.limit > 0

    def test_check_quota_sufficient(self, tracker_with_user):
        """Test check_quota returns True when sufficient tokens."""
        tracker = tracker_with_user

        can_proceed, reason = tracker.check_quota(user_id=1, tokens_needed=1000)

        assert can_proceed is True
        assert reason == "OK"

    def test_check_quota_insufficient(self, tracker_with_user):
        """Test check_quota returns False when quota exceeded."""
        tracker = tracker_with_user

        # Use up the quota
        quota = tracker.get_quota(user_id=1, period="hour")
        tracker.track_usage(
            user_id=1,
            tokens_in=quota.limit // 2,
            tokens_out=quota.limit // 2 + 1000,  # Exceed limit
            model_id="grok-3-mini",
        )

        can_proceed, reason = tracker.check_quota(user_id=1, tokens_needed=1000)

        assert can_proceed is False
        assert "exceeded" in reason.lower() or "limit" in reason.lower()

    def test_estimate_cost_grok_mini(self, tracker):
        """Test cost estimation for Grok-3-mini."""
        cost = tracker.estimate_cost(
            tokens_in=1000,
            tokens_out=1000,
            model_id="grok-3-mini",
        )

        # grok-3-mini: $0.30/M input, $0.50/M output
        expected = (1000 * 0.30 + 1000 * 0.50) / 1_000_000
        assert abs(cost - expected) < 0.0001

    def test_estimate_cost_claude_sonnet(self, tracker):
        """Test cost estimation for Claude Sonnet."""
        cost = tracker.estimate_cost(
            tokens_in=1000,
            tokens_out=1000,
            model_id="claude-sonnet-4-20250514",
        )

        # Claude Sonnet: $3/M input, $15/M output
        expected = (1000 * 3 + 1000 * 15) / 1_000_000
        assert abs(cost - expected) < 0.0001

    def test_estimate_cost_unknown_model(self, tracker):
        """Test cost estimation for unknown model uses default."""
        cost = tracker.estimate_cost(
            tokens_in=1000,
            tokens_out=1000,
            model_id="unknown-model-xyz",
        )

        # Should use default pricing (not raise error)
        assert cost >= 0

    def test_get_usage_summary(self, tracker_with_user):
        """Test getting usage summary."""
        tracker = tracker_with_user

        # Add some usage
        tracker.track_usage(
            user_id=1,
            tokens_in=500,
            tokens_out=1000,
            model_id="grok-3-mini",
        )
        tracker.track_usage(
            user_id=1,
            tokens_in=200,
            tokens_out=300,
            model_id="claude-sonnet-4-20250514",
        )

        summary = tracker.get_usage_summary(user_id=1)

        assert "hourly" in summary
        assert "daily" in summary
        assert "monthly" in summary
        assert "cost_today" in summary
        assert summary["total_tokens_today"] >= 2000

    def test_reset_quota(self, tracker_with_user):
        """Test manually resetting a quota."""
        tracker = tracker_with_user

        # Use some tokens
        tracker.track_usage(
            user_id=1,
            tokens_in=10000,
            tokens_out=10000,
            model_id="grok-3-mini",
        )

        # Reset hourly quota
        tracker.reset_quota(user_id=1, period="hour")

        quota = tracker.get_quota(user_id=1, period="hour")
        assert quota.used == 0


class TestQuotaAutoReset:
    """Tests for automatic quota reset on period expiration."""

    @pytest.fixture
    def tracker(self, tmp_path):
        """Create a UsageTracker with temp database."""
        from core.usage.tracker import UsageTracker

        db_path = tmp_path / "test_usage.db"
        return UsageTracker(db_path=db_path)

    def test_expired_hourly_quota_auto_resets(self, tracker):
        """Test that expired hourly quota automatically resets."""
        # Create quota that expired 1 hour ago
        tracker._ensure_user_quotas(user_id=1)

        conn = sqlite3.connect(tracker.db_path)
        expired_time = datetime.now(timezone.utc) - timedelta(hours=1)
        conn.execute(
            """
            UPDATE usage_quotas
            SET tokens_used = 40000, reset_at = ?
            WHERE user_id = 1 AND period = 'hour'
            """,
            (expired_time.isoformat(),)
        )
        conn.commit()
        conn.close()

        # Getting quota should trigger auto-reset
        quota = tracker.get_quota(user_id=1, period="hour")

        assert quota.used == 0
        assert quota.reset_at > datetime.now(timezone.utc)

    def test_unexpired_quota_not_reset(self, tracker):
        """Test that unexpired quota is not reset."""
        tracker._ensure_user_quotas(user_id=1)

        # Add some usage
        tracker.track_usage(
            user_id=1,
            tokens_in=5000,
            tokens_out=5000,
            model_id="grok-3-mini",
        )

        quota = tracker.get_quota(user_id=1, period="hour")

        assert quota.used == 10000  # Should retain usage


class TestDefaultQuotas:
    """Tests for default quota configuration."""

    def test_free_tier_defaults(self):
        """Test free tier default quotas."""
        from core.usage.config import DEFAULT_QUOTAS

        free = DEFAULT_QUOTAS["free_tier"]

        assert free["hour"] == 50_000
        assert free["day"] == 1_000_000
        assert free["month"] == 10_000_000

    def test_premium_tier_defaults(self):
        """Test premium tier default quotas."""
        from core.usage.config import DEFAULT_QUOTAS

        premium = DEFAULT_QUOTAS["premium"]

        assert premium["hour"] == 200_000
        assert premium["day"] == 5_000_000
        assert premium["month"] == 50_000_000

    def test_admin_unlimited(self):
        """Test admin tier has unlimited quotas."""
        from core.usage.config import DEFAULT_QUOTAS

        admin = DEFAULT_QUOTAS["admin"]

        assert admin["hour"] == -1
        assert admin["day"] == -1
        assert admin["month"] == -1


class TestModelPricing:
    """Tests for model pricing configuration."""

    def test_grok_models_have_pricing(self):
        """Test Grok models have pricing defined."""
        from core.usage.config import MODEL_PRICING

        assert "grok-3-mini" in MODEL_PRICING
        assert "grok-3" in MODEL_PRICING

        grok_mini = MODEL_PRICING["grok-3-mini"]
        assert "input" in grok_mini
        assert "output" in grok_mini

    def test_claude_models_have_pricing(self):
        """Test Claude models have pricing defined."""
        from core.usage.config import MODEL_PRICING

        assert "claude-sonnet-4-20250514" in MODEL_PRICING

        sonnet = MODEL_PRICING["claude-sonnet-4-20250514"]
        assert "input" in sonnet
        assert "output" in sonnet

    def test_default_pricing_exists(self):
        """Test default pricing for unknown models."""
        from core.usage.config import MODEL_PRICING

        assert "default" in MODEL_PRICING


class TestUsageAlerts:
    """Tests for usage alert thresholds."""

    @pytest.fixture
    def tracker(self, tmp_path):
        """Create a UsageTracker with temp database."""
        from core.usage.tracker import UsageTracker

        db_path = tmp_path / "test_usage.db"
        return UsageTracker(db_path=db_path)

    def test_alert_at_80_percent(self, tracker):
        """Test warning alert at 80% usage."""
        tracker._ensure_user_quotas(user_id=1)

        quota = tracker.get_quota(user_id=1, period="hour")
        # Use 80% of quota
        tokens_to_use = int(quota.limit * 0.80)
        tracker.track_usage(
            user_id=1,
            tokens_in=tokens_to_use // 2,
            tokens_out=tokens_to_use // 2,
            model_id="grok-3-mini",
        )

        alerts = tracker.get_alerts(user_id=1)

        assert any(a["level"] == "warning" and a["period"] == "hour" for a in alerts)

    def test_alert_at_90_percent(self, tracker):
        """Test critical alert at 90% usage."""
        tracker._ensure_user_quotas(user_id=1)

        quota = tracker.get_quota(user_id=1, period="hour")
        # Use 90% of quota
        tokens_to_use = int(quota.limit * 0.90)
        tracker.track_usage(
            user_id=1,
            tokens_in=tokens_to_use // 2,
            tokens_out=tokens_to_use // 2,
            model_id="grok-3-mini",
        )

        alerts = tracker.get_alerts(user_id=1)

        assert any(a["level"] == "critical" and a["period"] == "hour" for a in alerts)

    def test_no_alert_below_80_percent(self, tracker):
        """Test no alert below 80% usage."""
        tracker._ensure_user_quotas(user_id=1)

        quota = tracker.get_quota(user_id=1, period="hour")
        # Use only 50% of quota
        tokens_to_use = int(quota.limit * 0.50)
        tracker.track_usage(
            user_id=1,
            tokens_in=tokens_to_use // 2,
            tokens_out=tokens_to_use // 2,
            model_id="grok-3-mini",
        )

        alerts = tracker.get_alerts(user_id=1)

        # Should have no hourly alerts
        assert not any(a["period"] == "hour" for a in alerts)


class TestUsageSummaryFormatting:
    """Tests for formatted usage summary (Clawdbot-style)."""

    @pytest.fixture
    def tracker(self, tmp_path):
        """Create a UsageTracker with temp database."""
        from core.usage.tracker import UsageTracker

        db_path = tmp_path / "test_usage.db"
        return UsageTracker(db_path=db_path)

    def test_format_usage_status(self, tracker):
        """Test Clawdbot-style usage status formatting."""
        tracker._ensure_user_quotas(user_id=1)

        # Add some usage
        tracker.track_usage(
            user_id=1,
            tokens_in=5000,
            tokens_out=5000,
            model_id="grok-3-mini",
        )

        status = tracker.format_usage_status(user_id=1)

        # Should include percentage remaining and time until reset
        assert "%" in status
        assert "left" in status.lower()

    def test_format_includes_cost(self, tracker):
        """Test status includes cost information."""
        tracker._ensure_user_quotas(user_id=1)

        tracker.track_usage(
            user_id=1,
            tokens_in=5000,
            tokens_out=5000,
            model_id="grok-3-mini",
        )

        status = tracker.format_usage_status(user_id=1)

        assert "$" in status


class TestAdminQuotaManagement:
    """Tests for admin quota management features."""

    @pytest.fixture
    def tracker(self, tmp_path):
        """Create a UsageTracker with temp database."""
        from core.usage.tracker import UsageTracker

        db_path = tmp_path / "test_usage.db"
        return UsageTracker(db_path=db_path)

    def test_set_custom_quota(self, tracker):
        """Test setting custom quota for a user."""
        tracker._ensure_user_quotas(user_id=1)

        tracker.set_custom_quota(
            user_id=1,
            period="hour",
            new_limit=100_000,
        )

        quota = tracker.get_quota(user_id=1, period="hour")
        assert quota.limit == 100_000

    def test_get_all_users_usage(self, tracker):
        """Test getting usage summary for all users."""
        # Create multiple users
        tracker._ensure_user_quotas(user_id=1)
        tracker._ensure_user_quotas(user_id=2)

        tracker.track_usage(user_id=1, tokens_in=1000, tokens_out=1000, model_id="grok-3-mini")
        tracker.track_usage(user_id=2, tokens_in=2000, tokens_out=2000, model_id="grok-3-mini")

        all_usage = tracker.get_all_users_usage()

        assert len(all_usage) >= 2
        assert any(u["user_id"] == 1 for u in all_usage)
        assert any(u["user_id"] == 2 for u in all_usage)

    def test_get_cost_report(self, tracker):
        """Test generating cost report."""
        tracker._ensure_user_quotas(user_id=1)

        tracker.track_usage(user_id=1, tokens_in=10000, tokens_out=10000, model_id="grok-3-mini")

        report = tracker.get_cost_report(days=7)

        assert "total_cost" in report
        assert "by_model" in report
        assert "by_day" in report


class TestDatabaseSchema:
    """Tests for database schema creation."""

    def test_usage_quotas_schema(self, tmp_path):
        """Test usage_quotas table schema."""
        from core.usage.tracker import UsageTracker

        db_path = tmp_path / "test_usage.db"
        tracker = UsageTracker(db_path=db_path)
        tracker._ensure_user_quotas(user_id=1)

        conn = sqlite3.connect(tracker.db_path)
        cursor = conn.execute("PRAGMA table_info(usage_quotas)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}
        conn.close()

        assert "user_id" in columns
        assert "period" in columns
        assert "token_limit" in columns
        assert "tokens_used" in columns
        assert "reset_at" in columns

    def test_usage_history_schema(self, tmp_path):
        """Test usage_history table schema."""
        from core.usage.tracker import UsageTracker

        db_path = tmp_path / "test_usage.db"
        tracker = UsageTracker(db_path=db_path)

        conn = sqlite3.connect(tracker.db_path)
        cursor = conn.execute("PRAGMA table_info(usage_history)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}
        conn.close()

        assert "user_id" in columns
        assert "model_id" in columns
        assert "tokens_in" in columns
        assert "tokens_out" in columns
        assert "estimated_cost" in columns
        assert "timestamp" in columns


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
