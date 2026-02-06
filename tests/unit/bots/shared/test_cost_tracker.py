"""
Tests for ClawdBots API Cost Tracker.

Tests the cost tracking module for ClawdBot API usage monitoring.
"""

import json
import os
import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest import mock

import pytest


class TestModelPricing:
    """Test model pricing constants."""

    def test_openai_gpt4_pricing_exists(self):
        """OpenAI GPT-4 pricing should be defined."""
        from bots.shared.cost_tracker import API_PRICING

        assert "openai" in API_PRICING
        assert "gpt-4" in API_PRICING["openai"]
        pricing = API_PRICING["openai"]["gpt-4"]
        assert "input_per_1k" in pricing
        assert "output_per_1k" in pricing
        # GPT-4: $0.03/1K input, $0.06/1K output
        assert pricing["input_per_1k"] == 0.03
        assert pricing["output_per_1k"] == 0.06

    def test_anthropic_claude_pricing_exists(self):
        """Anthropic Claude pricing should be defined."""
        from bots.shared.cost_tracker import API_PRICING

        assert "anthropic" in API_PRICING
        assert "claude" in API_PRICING["anthropic"]
        pricing = API_PRICING["anthropic"]["claude"]
        assert "input_per_1k" in pricing
        assert "output_per_1k" in pricing
        # Claude: $0.015/1K input, $0.075/1K output
        assert pricing["input_per_1k"] == 0.015
        assert pricing["output_per_1k"] == 0.075

    def test_xai_grok_pricing_exists(self):
        """X.AI/Grok pricing should be defined."""
        from bots.shared.cost_tracker import API_PRICING

        assert "xai" in API_PRICING
        assert "grok" in API_PRICING["xai"]
        pricing = API_PRICING["xai"]["grok"]
        assert "input_per_1k" in pricing
        assert "output_per_1k" in pricing
        # Grok: similar to GPT-4 ($0.03/1K input, $0.06/1K output)
        assert pricing["input_per_1k"] == 0.03
        assert pricing["output_per_1k"] == 0.06


class TestCostCalculation:
    """Test cost calculation functionality."""

    def test_calculate_openai_cost(self):
        """Calculate cost for OpenAI API call."""
        from bots.shared.cost_tracker import ClawdBotCostTracker

        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = ClawdBotCostTracker(storage_path=Path(tmpdir) / "costs.json")

            # 1000 input tokens, 500 output tokens
            # Input: 1000/1000 * $0.03 = $0.03
            # Output: 500/1000 * $0.06 = $0.03
            # Total: $0.06
            cost = tracker._calculate_cost("openai", 1000, 500)
            assert cost == pytest.approx(0.06, rel=1e-4)

    def test_calculate_anthropic_cost(self):
        """Calculate cost for Anthropic API call."""
        from bots.shared.cost_tracker import ClawdBotCostTracker

        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = ClawdBotCostTracker(storage_path=Path(tmpdir) / "costs.json")

            # 1000 input tokens, 500 output tokens
            # Input: 1000/1000 * $0.015 = $0.015
            # Output: 500/1000 * $0.075 = $0.0375
            # Total: $0.0525
            cost = tracker._calculate_cost("anthropic", 1000, 500)
            assert cost == pytest.approx(0.0525, rel=1e-4)

    def test_calculate_xai_cost(self):
        """Calculate cost for X.AI/Grok API call."""
        from bots.shared.cost_tracker import ClawdBotCostTracker

        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = ClawdBotCostTracker(storage_path=Path(tmpdir) / "costs.json")

            # 1000 input tokens, 500 output tokens (same as GPT-4)
            cost = tracker._calculate_cost("xai", 1000, 500)
            assert cost == pytest.approx(0.06, rel=1e-4)

    def test_calculate_unknown_api_returns_zero(self):
        """Unknown API should return zero cost (not raise)."""
        from bots.shared.cost_tracker import ClawdBotCostTracker

        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = ClawdBotCostTracker(storage_path=Path(tmpdir) / "costs.json")
            cost = tracker._calculate_cost("unknown_api", 1000, 500)
            assert cost == 0.0


class TestTrackAPICall:
    """Test track_api_call function."""

    def test_track_api_call_stores_entry(self):
        """track_api_call should store the entry."""
        from bots.shared.cost_tracker import track_api_call, get_tracker

        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = get_tracker(storage_path=Path(tmpdir) / "costs.json", force_new=True)

            track_api_call("clawdmatt", "openai", 1000, 500)

            # Verify entry was stored
            assert tracker._data is not None
            assert "daily" in tracker._data
            today = date.today().isoformat()
            assert today in tracker._data["daily"]
            assert len(tracker._data["daily"][today]) > 0

    def test_track_api_call_calculates_cost(self):
        """track_api_call should calculate and store cost."""
        from bots.shared.cost_tracker import track_api_call, get_tracker

        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = get_tracker(storage_path=Path(tmpdir) / "costs.json", force_new=True)

            track_api_call("clawdmatt", "openai", 1000, 500)

            today = date.today().isoformat()
            entries = tracker._data["daily"][today]
            assert entries[-1]["cost_usd"] == pytest.approx(0.06, rel=1e-4)

    def test_track_api_call_stores_bot_name(self):
        """track_api_call should store the bot name."""
        from bots.shared.cost_tracker import track_api_call, get_tracker

        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = get_tracker(storage_path=Path(tmpdir) / "costs.json", force_new=True)

            track_api_call("clawdjarvis", "anthropic", 500, 1000)

            today = date.today().isoformat()
            entries = tracker._data["daily"][today]
            assert entries[-1]["bot_name"] == "clawdjarvis"

    def test_track_api_call_stores_api_name(self):
        """track_api_call should store the API provider name."""
        from bots.shared.cost_tracker import track_api_call, get_tracker

        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = get_tracker(storage_path=Path(tmpdir) / "costs.json", force_new=True)

            track_api_call("clawdfriday", "xai", 2000, 1000)

            today = date.today().isoformat()
            entries = tracker._data["daily"][today]
            assert entries[-1]["api"] == "xai"

    def test_track_api_call_stores_tokens(self):
        """track_api_call should store token counts."""
        from bots.shared.cost_tracker import track_api_call, get_tracker

        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = get_tracker(storage_path=Path(tmpdir) / "costs.json", force_new=True)

            track_api_call("clawdmatt", "openai", 1500, 750)

            today = date.today().isoformat()
            entries = tracker._data["daily"][today]
            assert entries[-1]["input_tokens"] == 1500
            assert entries[-1]["output_tokens"] == 750


class TestGetDailyCost:
    """Test get_daily_cost function."""

    def test_get_daily_cost_no_data(self):
        """get_daily_cost should return 0 when no data."""
        from bots.shared.cost_tracker import get_daily_cost, get_tracker

        with tempfile.TemporaryDirectory() as tmpdir:
            get_tracker(storage_path=Path(tmpdir) / "costs.json", force_new=True)

            cost = get_daily_cost()
            assert cost == 0.0

    def test_get_daily_cost_all_bots(self):
        """get_daily_cost should return total for all bots."""
        from bots.shared.cost_tracker import track_api_call, get_daily_cost, get_tracker

        with tempfile.TemporaryDirectory() as tmpdir:
            get_tracker(storage_path=Path(tmpdir) / "costs.json", force_new=True)

            track_api_call("clawdmatt", "openai", 1000, 500)  # $0.06
            track_api_call("clawdjarvis", "openai", 1000, 500)  # $0.06

            cost = get_daily_cost()
            assert cost == pytest.approx(0.12, rel=1e-4)

    def test_get_daily_cost_specific_bot(self):
        """get_daily_cost should filter by bot_name when provided."""
        from bots.shared.cost_tracker import track_api_call, get_daily_cost, get_tracker

        with tempfile.TemporaryDirectory() as tmpdir:
            get_tracker(storage_path=Path(tmpdir) / "costs.json", force_new=True)

            track_api_call("clawdmatt", "openai", 1000, 500)  # $0.06
            track_api_call("clawdjarvis", "openai", 2000, 1000)  # $0.12

            matt_cost = get_daily_cost(bot_name="clawdmatt")
            assert matt_cost == pytest.approx(0.06, rel=1e-4)

            jarvis_cost = get_daily_cost(bot_name="clawdjarvis")
            assert jarvis_cost == pytest.approx(0.12, rel=1e-4)


class TestGetMonthlyCost:
    """Test get_monthly_cost function."""

    def test_get_monthly_cost_no_data(self):
        """get_monthly_cost should return 0 when no data."""
        from bots.shared.cost_tracker import get_monthly_cost, get_tracker

        with tempfile.TemporaryDirectory() as tmpdir:
            get_tracker(storage_path=Path(tmpdir) / "costs.json", force_new=True)

            cost = get_monthly_cost()
            assert cost == 0.0

    def test_get_monthly_cost_all_bots(self):
        """get_monthly_cost should aggregate all daily costs."""
        from bots.shared.cost_tracker import track_api_call, get_monthly_cost, get_tracker

        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = get_tracker(storage_path=Path(tmpdir) / "costs.json", force_new=True)

            track_api_call("clawdmatt", "openai", 1000, 500)  # $0.06
            track_api_call("clawdjarvis", "anthropic", 1000, 500)  # $0.0525

            cost = get_monthly_cost()
            assert cost == pytest.approx(0.1125, rel=1e-4)

    def test_get_monthly_cost_specific_bot(self):
        """get_monthly_cost should filter by bot_name when provided."""
        from bots.shared.cost_tracker import track_api_call, get_monthly_cost, get_tracker

        with tempfile.TemporaryDirectory() as tmpdir:
            get_tracker(storage_path=Path(tmpdir) / "costs.json", force_new=True)

            track_api_call("clawdmatt", "openai", 1000, 500)  # $0.06
            track_api_call("clawdjarvis", "anthropic", 1000, 500)  # $0.0525

            matt_cost = get_monthly_cost(bot_name="clawdmatt")
            assert matt_cost == pytest.approx(0.06, rel=1e-4)


class TestCheckBudget:
    """Test check_budget function."""

    def test_check_budget_under_limit(self):
        """check_budget should return True when under daily limit."""
        from bots.shared.cost_tracker import track_api_call, check_budget, get_tracker

        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = get_tracker(storage_path=Path(tmpdir) / "costs.json", force_new=True)
            tracker.set_daily_limit("clawdmatt", 10.0)

            track_api_call("clawdmatt", "openai", 1000, 500)  # $0.06

            assert check_budget("clawdmatt") is True

    def test_check_budget_over_limit(self):
        """check_budget should return False when over daily limit."""
        from bots.shared.cost_tracker import track_api_call, check_budget, get_tracker

        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = get_tracker(storage_path=Path(tmpdir) / "costs.json", force_new=True)
            tracker.set_daily_limit("clawdmatt", 0.05)  # $0.05 limit

            track_api_call("clawdmatt", "openai", 1000, 500)  # $0.06 - over limit

            assert check_budget("clawdmatt") is False

    def test_check_budget_default_limit(self):
        """check_budget should use default $10 daily limit."""
        from bots.shared.cost_tracker import track_api_call, check_budget, get_tracker

        with tempfile.TemporaryDirectory() as tmpdir:
            get_tracker(storage_path=Path(tmpdir) / "costs.json", force_new=True)

            track_api_call("clawdmatt", "openai", 1000, 500)  # $0.06

            # Should be under default $10 limit
            assert check_budget("clawdmatt") is True


class TestSetDailyLimit:
    """Test set_daily_limit function."""

    def test_set_daily_limit_stores_limit(self):
        """set_daily_limit should store the limit for a bot."""
        from bots.shared.cost_tracker import get_tracker, set_daily_limit

        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = get_tracker(storage_path=Path(tmpdir) / "costs.json", force_new=True)

            set_daily_limit("clawdmatt", 5.0)

            assert tracker._limits["clawdmatt"] == 5.0

    def test_set_daily_limit_persists(self):
        """set_daily_limit should persist to storage."""
        from bots.shared.cost_tracker import get_tracker, set_daily_limit

        with tempfile.TemporaryDirectory() as tmpdir:
            storage_path = Path(tmpdir) / "costs.json"
            tracker = get_tracker(storage_path=storage_path, force_new=True)

            set_daily_limit("clawdmatt", 7.5)

            # Force reload from disk
            tracker2 = get_tracker(storage_path=storage_path, force_new=True)
            assert tracker2._limits["clawdmatt"] == 7.5


class TestGetCostReport:
    """Test get_cost_report function."""

    def test_get_cost_report_empty(self):
        """get_cost_report should return report even with no data."""
        from bots.shared.cost_tracker import get_cost_report, get_tracker

        with tempfile.TemporaryDirectory() as tmpdir:
            get_tracker(storage_path=Path(tmpdir) / "costs.json", force_new=True)

            report = get_cost_report()

            assert isinstance(report, str)
            assert "Cost Report" in report or "cost" in report.lower()

    def test_get_cost_report_includes_daily_cost(self):
        """get_cost_report should include daily cost."""
        from bots.shared.cost_tracker import track_api_call, get_cost_report, get_tracker

        with tempfile.TemporaryDirectory() as tmpdir:
            get_tracker(storage_path=Path(tmpdir) / "costs.json", force_new=True)

            track_api_call("clawdmatt", "openai", 1000, 500)  # $0.06

            report = get_cost_report()

            assert "0.06" in report or "$0.06" in report

    def test_get_cost_report_includes_bot_breakdown(self):
        """get_cost_report should include per-bot breakdown."""
        from bots.shared.cost_tracker import track_api_call, get_cost_report, get_tracker

        with tempfile.TemporaryDirectory() as tmpdir:
            get_tracker(storage_path=Path(tmpdir) / "costs.json", force_new=True)

            track_api_call("clawdmatt", "openai", 1000, 500)
            track_api_call("clawdjarvis", "anthropic", 1000, 500)

            report = get_cost_report()

            assert "clawdmatt" in report
            assert "clawdjarvis" in report


class TestBudgetAlerts:
    """Test budget alert functionality."""

    def test_alert_when_approaching_limit(self):
        """Should alert when approaching 80% of daily limit."""
        from bots.shared.cost_tracker import ClawdBotCostTracker

        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = ClawdBotCostTracker(storage_path=Path(tmpdir) / "costs.json")
            tracker.set_daily_limit("clawdmatt", 0.10)  # $0.10 limit

            alerts = []
            def alert_callback(bot, current, limit, percent):
                alerts.append({"bot": bot, "current": current, "limit": limit, "percent": percent})

            tracker.set_alert_callback(alert_callback)

            # Track an API call that exceeds 80% of $0.10 limit
            # Input: 2000/1000 * $0.03 = $0.06
            # Output: 1000/1000 * $0.06 = $0.06
            # Total: $0.12, which is 120% of $0.10 limit (> 80% threshold)
            tracker.track_api_call("clawdmatt", "openai", 2000, 1000)

            # Should have triggered alert
            assert len(alerts) >= 1
            assert alerts[-1]["bot"] == "clawdmatt"

    def test_no_alert_under_threshold(self):
        """Should not alert when under 80% of daily limit."""
        from bots.shared.cost_tracker import ClawdBotCostTracker

        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = ClawdBotCostTracker(storage_path=Path(tmpdir) / "costs.json")
            tracker.set_daily_limit("clawdmatt", 10.0)  # $10 limit

            alerts = []
            def alert_callback(bot, current, limit, percent):
                alerts.append({"bot": bot})

            tracker.set_alert_callback(alert_callback)

            # Track $0.06 (0.6% of limit)
            tracker.track_api_call("clawdmatt", "openai", 1000, 500)

            # Should not have triggered alert
            assert len(alerts) == 0


class TestPersistence:
    """Test data persistence."""

    def test_data_persists_to_file(self):
        """Data should persist to JSON file."""
        from bots.shared.cost_tracker import ClawdBotCostTracker

        with tempfile.TemporaryDirectory() as tmpdir:
            storage_path = Path(tmpdir) / "costs.json"
            tracker = ClawdBotCostTracker(storage_path=storage_path)

            tracker.track_api_call("clawdmatt", "openai", 1000, 500)

            # Verify file exists and has data
            assert storage_path.exists()

            with open(storage_path, "r") as f:
                data = json.load(f)

            assert "daily" in data
            today = date.today().isoformat()
            assert today in data["daily"]

    def test_data_loads_on_init(self):
        """Data should load from existing file on init."""
        from bots.shared.cost_tracker import ClawdBotCostTracker

        with tempfile.TemporaryDirectory() as tmpdir:
            storage_path = Path(tmpdir) / "costs.json"

            # First tracker - add data
            tracker1 = ClawdBotCostTracker(storage_path=storage_path)
            tracker1.track_api_call("clawdmatt", "openai", 1000, 500)

            # Second tracker - should load existing data
            tracker2 = ClawdBotCostTracker(storage_path=storage_path)

            cost = tracker2.get_daily_cost()
            assert cost == pytest.approx(0.06, rel=1e-4)


class TestMonthlyRollup:
    """Test monthly data aggregation."""

    def test_monthly_includes_all_days(self):
        """Monthly cost should include all days in the month."""
        from bots.shared.cost_tracker import ClawdBotCostTracker

        with tempfile.TemporaryDirectory() as tmpdir:
            storage_path = Path(tmpdir) / "costs.json"
            tracker = ClawdBotCostTracker(storage_path=storage_path)

            # Add data for today
            tracker.track_api_call("clawdmatt", "openai", 1000, 500)  # $0.06

            # Manually add data for yesterday (same month)
            yesterday = (date.today() - timedelta(days=1)).isoformat()
            tracker._data["daily"][yesterday] = [
                {
                    "bot_name": "clawdmatt",
                    "api": "openai",
                    "input_tokens": 1000,
                    "output_tokens": 500,
                    "cost_usd": 0.06,
                    "timestamp": datetime.now().isoformat(),
                }
            ]
            tracker._save_data()

            # Monthly should include both days
            monthly_cost = tracker.get_monthly_cost()
            assert monthly_cost == pytest.approx(0.12, rel=1e-4)


class TestDefaultStoragePath:
    """Test default storage path configuration."""

    def test_default_path_on_vps(self):
        """Default storage path should be /root/clawdbots/api_costs.json on VPS."""
        from bots.shared.cost_tracker import DEFAULT_STORAGE_PATH

        # The default should be set for VPS deployment
        assert DEFAULT_STORAGE_PATH == Path("/root/clawdbots/api_costs.json")

    def test_can_override_storage_path(self):
        """Should be able to override the storage path."""
        from bots.shared.cost_tracker import ClawdBotCostTracker

        with tempfile.TemporaryDirectory() as tmpdir:
            custom_path = Path(tmpdir) / "custom_costs.json"
            tracker = ClawdBotCostTracker(storage_path=custom_path)

            assert tracker._storage_path == custom_path


class TestMultipleBots:
    """Test handling multiple bots."""

    def test_track_multiple_bots(self):
        """Should correctly track costs for multiple bots."""
        from bots.shared.cost_tracker import ClawdBotCostTracker

        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = ClawdBotCostTracker(storage_path=Path(tmpdir) / "costs.json")

            tracker.track_api_call("clawdmatt", "openai", 1000, 500)    # $0.06
            tracker.track_api_call("clawdjarvis", "anthropic", 1000, 500)  # $0.0525
            tracker.track_api_call("clawdfriday", "xai", 1000, 500)     # $0.06

            assert tracker.get_daily_cost(bot_name="clawdmatt") == pytest.approx(0.06, rel=1e-4)
            assert tracker.get_daily_cost(bot_name="clawdjarvis") == pytest.approx(0.0525, rel=1e-4)
            assert tracker.get_daily_cost(bot_name="clawdfriday") == pytest.approx(0.06, rel=1e-4)

            total = tracker.get_daily_cost()
            assert total == pytest.approx(0.1725, rel=1e-4)

    def test_separate_limits_per_bot(self):
        """Each bot should have its own daily limit."""
        from bots.shared.cost_tracker import ClawdBotCostTracker

        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = ClawdBotCostTracker(storage_path=Path(tmpdir) / "costs.json")

            tracker.set_daily_limit("clawdmatt", 5.0)
            tracker.set_daily_limit("clawdjarvis", 15.0)

            assert tracker._limits["clawdmatt"] == 5.0
            assert tracker._limits["clawdjarvis"] == 15.0
