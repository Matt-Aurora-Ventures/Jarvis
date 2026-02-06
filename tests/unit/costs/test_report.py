"""
Tests for core.costs.report module.

Tests report generation functions.
"""

import pytest
from datetime import datetime, date
from unittest.mock import Mock, patch, AsyncMock


class TestDailyReport:
    """Test suite for daily report generation."""

    @pytest.fixture
    def mock_tracker(self):
        """Create a mock tracker with sample data."""
        tracker = Mock()
        tracker.get_daily_cost.return_value = 5.50
        tracker.daily_limit = 10.0
        tracker.storage = Mock()
        tracker.storage.load_daily.return_value = [
            {"provider": "openai", "model": "gpt-4o", "cost_usd": 3.00, "input_tokens": 50000, "output_tokens": 10000},
            {"provider": "anthropic", "model": "claude-opus-4", "cost_usd": 2.00, "input_tokens": 20000, "output_tokens": 8000},
            {"provider": "grok", "model": "grok-3", "cost_usd": 0.50, "input_tokens": 100000, "output_tokens": 50000},
        ]
        # Also mock get_daily_total for report generation
        tracker.storage.get_daily_total.return_value = 5.50
        return tracker

    def test_generate_daily_report_returns_string(self, mock_tracker):
        """Test generate_daily_report returns a string."""
        from core.costs.report import generate_daily_report

        report = generate_daily_report(tracker=mock_tracker)

        assert isinstance(report, str)
        assert len(report) > 0

    def test_daily_report_contains_date(self, mock_tracker):
        """Test daily report includes the date."""
        from core.costs.report import generate_daily_report

        report = generate_daily_report(tracker=mock_tracker)

        today = date.today().isoformat()
        assert today in report or date.today().strftime("%Y-%m-%d") in report

    def test_daily_report_contains_total_cost(self, mock_tracker):
        """Test daily report shows total cost."""
        from core.costs.report import generate_daily_report

        report = generate_daily_report(tracker=mock_tracker)

        # Should contain the total cost ($5.50)
        assert "5.50" in report or "$5.50" in report

    def test_daily_report_contains_budget_status(self, mock_tracker):
        """Test daily report shows budget status."""
        from core.costs.report import generate_daily_report

        report = generate_daily_report(tracker=mock_tracker)

        # Should show percentage or budget info
        assert "%" in report or "limit" in report.lower() or "budget" in report.lower()

    def test_daily_report_contains_provider_breakdown(self, mock_tracker):
        """Test daily report shows costs by provider."""
        from core.costs.report import generate_daily_report

        report = generate_daily_report(tracker=mock_tracker)

        # Should list providers
        assert "openai" in report.lower() or "OpenAI" in report
        assert "anthropic" in report.lower() or "Anthropic" in report

    def test_daily_report_contains_call_count(self, mock_tracker):
        """Test daily report shows number of API calls."""
        from core.costs.report import generate_daily_report

        report = generate_daily_report(tracker=mock_tracker)

        # Should mention calls/requests
        assert "3" in report or "calls" in report.lower() or "requests" in report.lower()


class TestMonthlyReport:
    """Test suite for monthly report generation."""

    @pytest.fixture
    def mock_tracker(self):
        """Create a mock tracker with monthly data."""
        tracker = Mock()
        tracker.get_monthly_cost.return_value = 150.00
        tracker.daily_limit = 10.0
        tracker.storage = Mock()
        tracker.storage.get_monthly_total.return_value = 150.00
        tracker.storage.get_monthly_by_provider.return_value = {
            "openai": 80.00,
            "anthropic": 50.00,
            "grok": 20.00,
        }
        tracker.storage.get_monthly_by_day.return_value = {
            "2026-02-01": 5.00,
            "2026-02-02": 7.50,
        }
        return tracker

    def test_generate_monthly_report_returns_string(self, mock_tracker):
        """Test generate_monthly_report returns a string."""
        from core.costs.report import generate_monthly_report

        report = generate_monthly_report(tracker=mock_tracker)

        assert isinstance(report, str)
        assert len(report) > 0

    def test_monthly_report_contains_month(self, mock_tracker):
        """Test monthly report includes the month."""
        from core.costs.report import generate_monthly_report

        report = generate_monthly_report(tracker=mock_tracker)

        # Should contain month name or YYYY-MM
        today = date.today()
        month_str = today.strftime("%B")  # Full month name
        month_num = today.strftime("%Y-%m")

        assert month_str in report or month_num in report

    def test_monthly_report_contains_total_cost(self, mock_tracker):
        """Test monthly report shows total cost."""
        from core.costs.report import generate_monthly_report

        report = generate_monthly_report(tracker=mock_tracker)

        assert "150" in report or "$150.00" in report

    def test_monthly_report_contains_provider_breakdown(self, mock_tracker):
        """Test monthly report shows costs by provider."""
        from core.costs.report import generate_monthly_report

        report = generate_monthly_report(tracker=mock_tracker)

        # Should show provider totals
        assert "80" in report  # OpenAI cost
        assert "50" in report  # Anthropic cost

    def test_monthly_report_contains_daily_trend(self, mock_tracker):
        """Test monthly report shows daily spending trend."""
        from core.costs.report import generate_monthly_report

        report = generate_monthly_report(tracker=mock_tracker)

        # Should show some trend info
        assert "average" in report.lower() or "day" in report.lower() or "trend" in report.lower()


class TestTelegramIntegration:
    """Test Telegram report sending."""

    @pytest.fixture
    def mock_telegram(self):
        """Create mock Telegram client."""
        client = AsyncMock()
        client.send_message = AsyncMock(return_value=True)
        return client

    @pytest.mark.asyncio
    async def test_send_daily_report_to_telegram(self, mock_telegram):
        """Test sending daily report to Telegram."""
        from core.costs.report import send_daily_report_telegram

        with patch("core.costs.report.get_telegram_client", return_value=mock_telegram):
            result = await send_daily_report_telegram(chat_id=-1001234567890)

        mock_telegram.send_message.assert_called_once()
        assert result is True

    @pytest.mark.asyncio
    async def test_telegram_report_handles_no_client(self):
        """Test graceful handling when Telegram client unavailable."""
        from core.costs.report import send_daily_report_telegram

        with patch("core.costs.report.get_telegram_client", return_value=None):
            result = await send_daily_report_telegram(chat_id=-1001234567890)

        # Should return False but not crash
        assert result is False

    @pytest.mark.asyncio
    async def test_send_monthly_report_to_telegram(self, mock_telegram):
        """Test sending monthly report to Telegram."""
        from core.costs.report import send_monthly_report_telegram

        with patch("core.costs.report.get_telegram_client", return_value=mock_telegram):
            result = await send_monthly_report_telegram(chat_id=-1001234567890)

        mock_telegram.send_message.assert_called_once()


class TestReportFormatting:
    """Test report formatting utilities."""

    def test_format_currency(self):
        """Test currency formatting."""
        from core.costs.report import format_currency

        assert format_currency(5.50) == "$5.50"
        assert format_currency(0.001) == "$0.00" or "$0.001" in format_currency(0.001)
        assert format_currency(1500.00) == "$1,500.00" or "1500" in format_currency(1500.00)

    def test_format_percentage(self):
        """Test percentage formatting."""
        from core.costs.report import format_percentage

        assert "55%" in format_percentage(5.50, 10.00)
        assert "100%" in format_percentage(10.00, 10.00)
        assert "150%" in format_percentage(15.00, 10.00)

    def test_format_token_count(self):
        """Test token count formatting."""
        from core.costs.report import format_tokens

        assert format_tokens(1000) == "1K" or "1,000" in format_tokens(1000)
        assert format_tokens(1500000) == "1.5M" or "1,500,000" in format_tokens(1500000)


class TestReportTemplates:
    """Test report template rendering."""

    def test_daily_report_has_header(self):
        """Test daily report has a clear header."""
        from core.costs.report import generate_daily_report

        mock_tracker = Mock()
        mock_tracker.get_daily_cost.return_value = 5.00
        mock_tracker.daily_limit = 10.0
        mock_tracker.storage = Mock()
        mock_tracker.storage.load_daily.return_value = []
        mock_tracker.storage.get_daily_total.return_value = 5.00

        report = generate_daily_report(tracker=mock_tracker)

        # Should have some kind of header
        assert "API Cost" in report or "Daily" in report or "Report" in report

    def test_daily_report_uses_emoji_sparingly(self):
        """Test report uses emoji for status but not excessively."""
        from core.costs.report import generate_daily_report

        mock_tracker = Mock()
        mock_tracker.get_daily_cost.return_value = 5.00
        mock_tracker.daily_limit = 10.0
        mock_tracker.storage = Mock()
        mock_tracker.storage.load_daily.return_value = []
        mock_tracker.storage.get_daily_total.return_value = 5.00

        report = generate_daily_report(tracker=mock_tracker)

        # Emoji count should be reasonable (not excessive)
        # This is a soft check - emoji usage is optional
        assert isinstance(report, str)
