"""
Tests for core.costs.tracker module.

Tests the CostTracker class for tracking API calls.
"""

import pytest
from datetime import datetime, date
from unittest.mock import Mock, patch, MagicMock


class TestCostTracker:
    """Test suite for CostTracker class."""

    @pytest.fixture
    def mock_storage(self):
        """Create a mock storage instance."""
        storage = Mock()
        storage.save_entry = Mock()
        storage.get_daily_total = Mock(return_value=0.0)
        storage.get_monthly_total = Mock(return_value=0.0)
        return storage

    @pytest.fixture
    def mock_calculator(self):
        """Create a mock calculator instance."""
        calc = Mock()
        calc.calculate_cost = Mock(return_value=0.045)
        return calc

    @pytest.fixture
    def tracker(self, mock_storage, mock_calculator):
        """Create a CostTracker with mocked dependencies."""
        from core.costs.tracker import CostTracker

        return CostTracker(
            storage=mock_storage,
            calculator=mock_calculator,
            daily_limit=10.0
        )

    def test_tracker_initialization(self):
        """Test CostTracker can be instantiated with defaults."""
        from core.costs.tracker import CostTracker

        tracker = CostTracker()
        assert tracker is not None

    def test_tracker_with_custom_daily_limit(self):
        """Test CostTracker accepts custom daily limit."""
        from core.costs.tracker import CostTracker

        tracker = CostTracker(daily_limit=5.0)
        assert tracker.daily_limit == 5.0

    def test_track_call_saves_entry(self, tracker, mock_storage):
        """Test track_call saves an entry to storage."""
        tracker.track_call(
            provider="openai",
            model="gpt-4o",
            input_tokens=1000,
            output_tokens=500,
            cost=0.045
        )

        mock_storage.save_entry.assert_called_once()
        call_args = mock_storage.save_entry.call_args[0][0]
        assert call_args["provider"] == "openai"
        assert call_args["model"] == "gpt-4o"
        assert call_args["cost_usd"] == 0.045

    def test_track_call_calculates_cost_if_not_provided(self, tracker, mock_calculator):
        """Test track_call calculates cost when not provided."""
        tracker.track_call(
            provider="openai",
            model="gpt-4o",
            input_tokens=1000,
            output_tokens=500
            # cost not provided
        )

        mock_calculator.calculate_cost.assert_called_once_with(
            provider="openai",
            model="gpt-4o",
            input_tokens=1000,
            output_tokens=500
        )

    def test_track_call_returns_cost(self, tracker):
        """Test track_call returns the cost."""
        cost = tracker.track_call(
            provider="openai",
            model="gpt-4o",
            input_tokens=1000,
            output_tokens=500,
            cost=0.045
        )

        assert cost == 0.045

    def test_get_daily_cost(self, tracker, mock_storage):
        """Test get_daily_cost returns today's total."""
        mock_storage.get_daily_total.return_value = 5.50

        cost = tracker.get_daily_cost()

        assert cost == 5.50
        mock_storage.get_daily_total.assert_called_once()

    def test_get_daily_cost_by_provider(self, tracker, mock_storage):
        """Test get_daily_cost with provider filter."""
        mock_storage.get_daily_total.return_value = 2.50

        cost = tracker.get_daily_cost(provider="openai")

        mock_storage.get_daily_total.assert_called()
        # The call should include provider parameter

    def test_get_monthly_cost(self, tracker, mock_storage):
        """Test get_monthly_cost returns current month's total."""
        mock_storage.get_monthly_total.return_value = 150.00

        cost = tracker.get_monthly_cost()

        assert cost == 150.00
        mock_storage.get_monthly_total.assert_called_once()

    def test_get_monthly_cost_by_provider(self, tracker, mock_storage):
        """Test get_monthly_cost with provider filter."""
        mock_storage.get_monthly_total.return_value = 50.00

        cost = tracker.get_monthly_cost(provider="anthropic")

        # Should filter by provider
        assert cost == 50.00

    def test_check_budget_under_limit(self, tracker, mock_storage):
        """Test check_budget returns True when under daily limit."""
        mock_storage.get_daily_total.return_value = 5.00  # Under $10 limit

        is_ok = tracker.check_budget()

        assert is_ok is True

    def test_check_budget_over_limit(self, tracker, mock_storage):
        """Test check_budget returns False when over daily limit."""
        mock_storage.get_daily_total.return_value = 15.00  # Over $10 limit

        is_ok = tracker.check_budget()

        assert is_ok is False

    def test_check_budget_at_limit(self, tracker, mock_storage):
        """Test check_budget returns False when at exactly daily limit."""
        mock_storage.get_daily_total.return_value = 10.00  # At $10 limit

        is_ok = tracker.check_budget()

        # At limit should be considered over
        assert is_ok is False

    def test_check_budget_for_specific_provider(self, tracker, mock_storage):
        """Test check_budget with provider-specific limit."""
        mock_storage.get_daily_total.return_value = 8.00

        # Provider check (if provider limits are set)
        is_ok = tracker.check_budget(provider="grok")

        assert isinstance(is_ok, bool)

    def test_alert_if_over_budget_triggers_when_over(self, tracker, mock_storage):
        """Test alert_if_over_budget sends alert when over limit."""
        mock_storage.get_daily_total.return_value = 12.00  # Over $10 limit

        with patch.object(tracker, '_send_alert') as mock_alert:
            tracker.alert_if_over_budget()
            mock_alert.assert_called_once()

    def test_alert_if_over_budget_no_alert_when_under(self, tracker, mock_storage):
        """Test alert_if_over_budget doesn't alert when under limit."""
        mock_storage.get_daily_total.return_value = 5.00  # Under limit

        with patch.object(tracker, '_send_alert') as mock_alert:
            tracker.alert_if_over_budget()
            mock_alert.assert_not_called()

    def test_alert_if_over_budget_returns_status(self, tracker, mock_storage):
        """Test alert_if_over_budget returns budget status."""
        mock_storage.get_daily_total.return_value = 12.00

        with patch.object(tracker, '_send_alert'):
            result = tracker.alert_if_over_budget()

        assert result["over_budget"] is True
        assert result["current_spend"] == 12.00
        assert result["daily_limit"] == 10.00


class TestCostTrackerIntegration:
    """Integration-style tests for CostTracker."""

    @pytest.fixture
    def tracker_with_real_storage(self, tmp_path):
        """Create tracker with real storage in temp directory."""
        from core.costs.tracker import CostTracker
        from core.costs.storage import CostStorage
        from core.costs.calculator import CostCalculator

        storage_dir = tmp_path / "costs"
        storage_dir.mkdir()

        storage = CostStorage(storage_dir=storage_dir)
        calculator = CostCalculator()

        return CostTracker(
            storage=storage,
            calculator=calculator,
            daily_limit=10.0
        )

    def test_full_tracking_workflow(self, tracker_with_real_storage):
        """Test complete tracking workflow: track, query, check budget."""
        tracker = tracker_with_real_storage

        # Track a few API calls
        tracker.track_call(
            provider="openai",
            model="gpt-4o",
            input_tokens=1000,
            output_tokens=500
        )

        tracker.track_call(
            provider="anthropic",
            model="claude-opus-4",
            input_tokens=2000,
            output_tokens=1000
        )

        # Query totals
        daily = tracker.get_daily_cost()
        assert daily > 0

        # Check budget
        is_ok = tracker.check_budget()
        assert is_ok is True  # Should be under $10

    def test_budget_warning_at_threshold(self, tracker_with_real_storage):
        """Test warning when approaching budget limit."""
        tracker = tracker_with_real_storage

        # Simulate approaching limit (80%)
        result = tracker.check_budget_warning(threshold=0.8)

        # Should return warning status
        assert "warning" in result or "status" in result


class TestGetGlobalTracker:
    """Test global tracker singleton."""

    def test_get_global_tracker_returns_instance(self):
        """Test get_cost_tracker returns a CostTracker instance."""
        from core.costs.tracker import get_cost_tracker

        tracker = get_cost_tracker()

        assert tracker is not None

    def test_get_global_tracker_returns_same_instance(self):
        """Test get_cost_tracker returns singleton."""
        from core.costs.tracker import get_cost_tracker

        tracker1 = get_cost_tracker()
        tracker2 = get_cost_tracker()

        assert tracker1 is tracker2
