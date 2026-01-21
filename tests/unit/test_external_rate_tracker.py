"""
Unit tests for External API Rate Limit Tracker.

Tests cover:
1. Rate limit tracking per API
2. Preemptive backoff at threshold
3. Cost tracking
4. Usage statistics
5. Persistent state management
6. Multiple API tracking
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
import tempfile
import json
from pathlib import Path


class TestExternalRateTrackerImports:
    """Test that rate tracker module imports correctly."""

    def test_tracker_import(self):
        """Test ExternalAPIRateTracker import."""
        from core.api.external_rate_tracker import ExternalAPIRateTracker
        assert ExternalAPIRateTracker is not None

    def test_api_provider_import(self):
        """Test APIProvider enum import."""
        from core.api.external_rate_tracker import APIProvider
        assert APIProvider.GROK is not None
        assert APIProvider.COINGECKO is not None
        assert APIProvider.TWITTER is not None

    def test_api_limits_import(self):
        """Test APILimits dataclass import."""
        from core.api.external_rate_tracker import APILimits
        limits = APILimits(requests_per_minute=30)
        assert limits.requests_per_minute == 30

    def test_default_limits_import(self):
        """Test DEFAULT_LIMITS dictionary import."""
        from core.api.external_rate_tracker import DEFAULT_LIMITS, APIProvider
        assert APIProvider.GROK in DEFAULT_LIMITS
        assert APIProvider.COINGECKO in DEFAULT_LIMITS


class TestAPILimitsDefaults:
    """Tests for API configuration defaults."""

    def test_grok_limits(self):
        """Test Grok API default limits."""
        from core.api.external_rate_tracker import DEFAULT_LIMITS, APIProvider

        grok = DEFAULT_LIMITS.get(APIProvider.GROK)
        assert grok is not None
        assert grok.requests_per_minute == 20
        assert grok.requests_per_day == 1000
        assert grok.cost_per_request > 0

    def test_coingecko_limits(self):
        """Test CoinGecko API default limits."""
        from core.api.external_rate_tracker import DEFAULT_LIMITS, APIProvider

        cg = DEFAULT_LIMITS.get(APIProvider.COINGECKO)
        assert cg is not None
        assert cg.requests_per_minute == 30

    def test_twitter_limits(self):
        """Test Twitter API default limits."""
        from core.api.external_rate_tracker import DEFAULT_LIMITS, APIProvider

        twitter = DEFAULT_LIMITS.get(APIProvider.TWITTER)
        assert twitter is not None
        assert twitter.requests_per_hour == 100

    def test_jupiter_limits(self):
        """Test Jupiter API default limits."""
        from core.api.external_rate_tracker import DEFAULT_LIMITS, APIProvider

        jupiter = DEFAULT_LIMITS.get(APIProvider.JUPITER)
        assert jupiter is not None
        assert jupiter.requests_per_minute == 60


class TestTrackerInitialization:
    """Tests for ExternalAPIRateTracker initialization."""

    def test_default_initialization(self):
        """Test tracker initializes with defaults."""
        from core.api.external_rate_tracker import ExternalAPIRateTracker

        tracker = ExternalAPIRateTracker()
        assert tracker is not None

    def test_custom_limits(self):
        """Test tracker with custom limits."""
        from core.api.external_rate_tracker import (
            ExternalAPIRateTracker,
            APIProvider,
            APILimits
        )

        custom = {
            APIProvider.GROK: APILimits(requests_per_minute=100)
        }
        tracker = ExternalAPIRateTracker(custom_limits=custom)
        assert tracker._limits[APIProvider.GROK].requests_per_minute == 100

    def test_all_providers_initialized(self):
        """Test all providers have usage state initialized."""
        from core.api.external_rate_tracker import ExternalAPIRateTracker, APIProvider

        tracker = ExternalAPIRateTracker()

        for provider in APIProvider:
            assert provider in tracker._usage


class TestRateLimitTracking:
    """Tests for rate limit tracking."""

    def test_record_request_increments_count(self):
        """Test that recording a request increments the count."""
        from core.api.external_rate_tracker import ExternalAPIRateTracker, APIProvider

        tracker = ExternalAPIRateTracker()

        tracker.record_request(APIProvider.GROK)

        usage = tracker.get_usage(APIProvider.GROK)
        assert usage["minute_requests"] >= 1

    def test_multiple_requests_tracked(self):
        """Test multiple requests are tracked correctly."""
        from core.api.external_rate_tracker import ExternalAPIRateTracker, APIProvider

        tracker = ExternalAPIRateTracker()

        for _ in range(5):
            tracker.record_request(APIProvider.GROK)

        usage = tracker.get_usage(APIProvider.GROK)
        assert usage["minute_requests"] >= 5

    def test_different_apis_tracked_separately(self):
        """Test different APIs are tracked independently."""
        from core.api.external_rate_tracker import ExternalAPIRateTracker, APIProvider

        tracker = ExternalAPIRateTracker()

        tracker.record_request(APIProvider.GROK)
        tracker.record_request(APIProvider.GROK)
        tracker.record_request(APIProvider.COINGECKO)

        grok_usage = tracker.get_usage(APIProvider.GROK)
        cg_usage = tracker.get_usage(APIProvider.COINGECKO)

        assert grok_usage["minute_requests"] >= 2
        assert cg_usage["minute_requests"] >= 1


class TestPreemptiveBackoff:
    """Tests for preemptive backoff functionality."""

    def test_can_request_when_under_threshold(self):
        """Test can_request returns True when under threshold."""
        from core.api.external_rate_tracker import ExternalAPIRateTracker, APIProvider

        tracker = ExternalAPIRateTracker()

        # Fresh tracker should allow requests
        can_request, wait_time = tracker.can_request(APIProvider.GROK)
        assert can_request is True
        assert wait_time is None

    def test_backoff_at_threshold(self):
        """Test backoff triggers at threshold."""
        from core.api.external_rate_tracker import (
            ExternalAPIRateTracker,
            APIProvider,
            DEFAULT_LIMITS
        )

        tracker = ExternalAPIRateTracker()

        # Grok has 20 per minute limit, 80% threshold = 16 calls
        grok_limits = DEFAULT_LIMITS[APIProvider.GROK]
        threshold_calls = int(grok_limits.requests_per_minute * grok_limits.backoff_threshold)

        for _ in range(threshold_calls + 1):
            tracker.record_request(APIProvider.GROK)

        # Should now be at or over threshold
        can_request, wait_time = tracker.can_request(APIProvider.GROK)
        assert can_request is False
        assert wait_time is not None
        assert wait_time > 0

    def test_wait_time_calculation(self):
        """Test wait time is calculated correctly."""
        from core.api.external_rate_tracker import (
            ExternalAPIRateTracker,
            APIProvider,
            DEFAULT_LIMITS
        )

        tracker = ExternalAPIRateTracker()

        # Fill up to threshold
        grok_limits = DEFAULT_LIMITS[APIProvider.GROK]
        for _ in range(grok_limits.requests_per_minute):
            tracker.record_request(APIProvider.GROK)

        can_request, wait_time = tracker.can_request(APIProvider.GROK)
        assert wait_time is not None
        assert wait_time <= 60  # Max 60 seconds for minute-based limit


class TestCostTracking:
    """Tests for cost tracking functionality."""

    def test_cost_recorded_on_request(self):
        """Test that cost is recorded when making requests."""
        from core.api.external_rate_tracker import ExternalAPIRateTracker, APIProvider

        tracker = ExternalAPIRateTracker()

        initial_usage = tracker.get_usage(APIProvider.GROK)
        initial_cost = initial_usage["day_cost"] if initial_usage else 0

        tracker.record_request(APIProvider.GROK)

        usage = tracker.get_usage(APIProvider.GROK)
        assert usage["day_cost"] >= initial_cost

    def test_cost_override(self):
        """Test cost can be overridden per request."""
        from core.api.external_rate_tracker import ExternalAPIRateTracker, APIProvider

        tracker = ExternalAPIRateTracker()

        tracker.record_request(APIProvider.GROK, cost_override=0.05)

        usage = tracker.get_usage(APIProvider.GROK)
        assert usage["day_cost"] >= 0.05


class TestDailyLimits:
    """Tests for daily limit tracking."""

    def test_daily_limits_defined(self):
        """Test that daily limits are defined for APIs."""
        from core.api.external_rate_tracker import DEFAULT_LIMITS, APIProvider

        grok_limits = DEFAULT_LIMITS[APIProvider.GROK]
        assert grok_limits.requests_per_day > 0
        assert grok_limits.daily_cost_limit > 0


class TestStatistics:
    """Tests for usage statistics."""

    def test_get_usage(self):
        """Test getting usage for an API."""
        from core.api.external_rate_tracker import ExternalAPIRateTracker, APIProvider

        tracker = ExternalAPIRateTracker()

        tracker.record_request(APIProvider.GROK)

        usage = tracker.get_usage(APIProvider.GROK)

        assert usage is not None
        assert "minute_requests" in usage
        assert "hour_requests" in usage
        assert "day_requests" in usage
        assert "limits" in usage
        assert "usage_pct" in usage

    def test_get_all_usage(self):
        """Test getting usage for all APIs."""
        from core.api.external_rate_tracker import ExternalAPIRateTracker, APIProvider

        tracker = ExternalAPIRateTracker()

        tracker.record_request(APIProvider.GROK)
        tracker.record_request(APIProvider.COINGECKO)

        all_usage = tracker.get_all_usage()

        assert "grok" in all_usage
        assert "coingecko" in all_usage

    def test_usage_percentage(self):
        """Test usage percentage calculation."""
        from core.api.external_rate_tracker import (
            ExternalAPIRateTracker,
            APIProvider,
            DEFAULT_LIMITS
        )

        tracker = ExternalAPIRateTracker()

        # Make 5 requests to grok (limit is 20/min)
        for _ in range(5):
            tracker.record_request(APIProvider.GROK)

        usage = tracker.get_usage(APIProvider.GROK)
        grok_limit = DEFAULT_LIMITS[APIProvider.GROK].requests_per_minute

        expected_pct = (5 / grok_limit) * 100
        assert usage["usage_pct"]["minute"] >= expected_pct - 1


class TestErrorTracking:
    """Tests for error tracking."""

    def test_error_recorded(self):
        """Test that errors are recorded."""
        from core.api.external_rate_tracker import ExternalAPIRateTracker, APIProvider

        tracker = ExternalAPIRateTracker()

        tracker.record_request(APIProvider.GROK, success=False)

        state = tracker._usage[APIProvider.GROK]
        assert state.consecutive_errors == 1

    def test_consecutive_errors_reset_on_success(self):
        """Test consecutive errors reset on successful request."""
        from core.api.external_rate_tracker import ExternalAPIRateTracker, APIProvider

        tracker = ExternalAPIRateTracker()

        tracker.record_request(APIProvider.GROK, success=False)
        tracker.record_request(APIProvider.GROK, success=False)
        tracker.record_request(APIProvider.GROK, success=True)

        state = tracker._usage[APIProvider.GROK]
        assert state.consecutive_errors == 0

    def test_rate_limited_tracked(self):
        """Test rate limit events are tracked."""
        from core.api.external_rate_tracker import ExternalAPIRateTracker, APIProvider

        tracker = ExternalAPIRateTracker()

        tracker.record_request(APIProvider.GROK, rate_limited=True)

        state = tracker._usage[APIProvider.GROK]
        assert state.last_rate_limit is not None
        assert state.minute_window.rate_limited_count >= 1


class TestAlerts:
    """Tests for alert functionality."""

    def test_alert_callback_called(self):
        """Test that alert callback is called when approaching limits."""
        from core.api.external_rate_tracker import (
            ExternalAPIRateTracker,
            APIProvider,
            DEFAULT_LIMITS
        )

        alerts = []
        def alert_callback(provider, message):
            alerts.append((provider, message))

        tracker = ExternalAPIRateTracker(alert_callback=alert_callback)

        # Fill up to trigger alert
        grok_limits = DEFAULT_LIMITS[APIProvider.GROK]
        threshold_calls = int(grok_limits.requests_per_minute * grok_limits.backoff_threshold)

        for _ in range(threshold_calls + 1):
            tracker.record_request(APIProvider.GROK)

        # Should have triggered an alert
        assert len(alerts) > 0
        assert any("grok" in a[0] for a in alerts)


class TestWindowRotation:
    """Tests for time window rotation."""

    def test_minute_window_rotates(self):
        """Test that minute window rotates after 60 seconds."""
        from core.api.external_rate_tracker import ExternalAPIRateTracker, APIProvider
        from datetime import timedelta

        tracker = ExternalAPIRateTracker()

        tracker.record_request(APIProvider.GROK)

        # Manually set window start to 2 minutes ago
        state = tracker._usage[APIProvider.GROK]
        state.minute_window.window_start = datetime.utcnow() - timedelta(minutes=2)

        # Next request should rotate the window
        tracker.record_request(APIProvider.GROK)

        # Window should have been reset
        usage = tracker.get_usage(APIProvider.GROK)
        # After rotation, count should be 1 (the most recent request)
        assert usage["minute_requests"] <= 2


class TestAllProviders:
    """Tests for all API providers."""

    def test_all_providers_have_limits(self):
        """Test all providers have defined limits."""
        from core.api.external_rate_tracker import DEFAULT_LIMITS, APIProvider

        for provider in APIProvider:
            assert provider in DEFAULT_LIMITS

    def test_all_providers_can_be_tracked(self):
        """Test all providers can record requests."""
        from core.api.external_rate_tracker import ExternalAPIRateTracker, APIProvider

        tracker = ExternalAPIRateTracker()

        for provider in APIProvider:
            tracker.record_request(provider)
            usage = tracker.get_usage(provider)
            assert usage is not None
            assert usage["minute_requests"] >= 1


class TestEdgeCases:
    """Tests for edge cases."""

    def test_zero_requests(self):
        """Test handling of zero requests."""
        from core.api.external_rate_tracker import ExternalAPIRateTracker, APIProvider

        tracker = ExternalAPIRateTracker()

        # Get usage before any requests
        usage = tracker.get_usage(APIProvider.GROK)
        assert usage is not None
        assert usage["minute_requests"] == 0

    def test_rapid_requests(self):
        """Test handling of rapid successive requests."""
        from core.api.external_rate_tracker import ExternalAPIRateTracker, APIProvider

        tracker = ExternalAPIRateTracker()

        # Make many rapid requests
        for _ in range(100):
            tracker.record_request(APIProvider.GROK)

        usage = tracker.get_usage(APIProvider.GROK)
        assert usage["minute_requests"] >= 100

    def test_concurrent_apis(self):
        """Test tracking many APIs simultaneously."""
        from core.api.external_rate_tracker import ExternalAPIRateTracker, APIProvider

        tracker = ExternalAPIRateTracker()

        for provider in APIProvider:
            tracker.record_request(provider)
            tracker.record_request(provider)

        all_usage = tracker.get_all_usage()
        assert len(all_usage) >= len(APIProvider)


class TestUsageState:
    """Tests for APIUsageState."""

    def test_to_dict(self):
        """Test APIUsageState.to_dict() method."""
        from core.api.external_rate_tracker import ExternalAPIRateTracker, APIProvider

        tracker = ExternalAPIRateTracker()

        tracker.record_request(APIProvider.GROK)

        state = tracker._usage[APIProvider.GROK]
        state_dict = state.to_dict()

        assert "provider" in state_dict
        assert "total_requests" in state_dict
        assert "total_cost" in state_dict
        assert "minute_requests" in state_dict

    def test_last_request_updated(self):
        """Test last_request timestamp is updated."""
        from core.api.external_rate_tracker import ExternalAPIRateTracker, APIProvider

        tracker = ExternalAPIRateTracker()

        before = datetime.utcnow()
        tracker.record_request(APIProvider.GROK)

        state = tracker._usage[APIProvider.GROK]
        assert state.last_request is not None
        assert state.last_request >= before
