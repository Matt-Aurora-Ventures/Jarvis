"""
Tests for response templates.

Tests pre-defined response templates for common scenarios.
"""

import pytest


class TestErrorResponse:
    """Test error_response template."""

    def test_error_response_basic(self):
        """error_response() should format error message."""
        from core.response.templates import error_response

        result = error_response("Something went wrong")

        assert "Something went wrong" in result
        # Should have error indicator
        assert "Error" in result or "error" in result.lower()

    def test_error_response_with_code(self):
        """error_response() should include error code if provided."""
        from core.response.templates import error_response

        result = error_response("Not found", code="404")

        assert "Not found" in result
        assert "404" in result

    def test_error_response_returns_string(self):
        """error_response() should return a string."""
        from core.response.templates import error_response

        result = error_response("Test error")

        assert isinstance(result, str)


class TestSuccessResponse:
    """Test success_response template."""

    def test_success_response_basic(self):
        """success_response() should format success message."""
        from core.response.templates import success_response

        result = success_response("Operation completed")

        assert "Operation completed" in result
        # Should have success indicator
        assert "Success" in result or "success" in result.lower() or "completed" in result.lower()

    def test_success_response_with_details(self):
        """success_response() should include details if provided."""
        from core.response.templates import success_response

        result = success_response("Trade executed", details="Bought 100 tokens")

        assert "Trade executed" in result
        assert "Bought 100 tokens" in result

    def test_success_response_returns_string(self):
        """success_response() should return a string."""
        from core.response.templates import success_response

        result = success_response("Test success")

        assert isinstance(result, str)


class TestLoadingResponse:
    """Test loading_response template."""

    def test_loading_response_basic(self):
        """loading_response() should return loading message."""
        from core.response.templates import loading_response

        result = loading_response()

        # Should contain loading indicator text
        assert any(word in result.lower() for word in ["loading", "processing", "wait", "please"])

    def test_loading_response_with_message(self):
        """loading_response() should accept custom message."""
        from core.response.templates import loading_response

        result = loading_response("Fetching price data...")

        assert "Fetching price data" in result

    def test_loading_response_returns_string(self):
        """loading_response() should return a string."""
        from core.response.templates import loading_response

        result = loading_response()

        assert isinstance(result, str)


class TestConfirmationResponse:
    """Test confirmation_response template."""

    def test_confirmation_response_basic(self):
        """confirmation_response() should format confirmation prompt."""
        from core.response.templates import confirmation_response

        result = confirmation_response("delete all positions")

        assert "delete all positions" in result
        # Should ask for confirmation
        assert any(word in result.lower() for word in ["confirm", "sure", "proceed", "?"])

    def test_confirmation_response_with_warning(self):
        """confirmation_response() should include warning if dangerous."""
        from core.response.templates import confirmation_response

        result = confirmation_response("delete all data", dangerous=True)

        assert "delete all data" in result
        # Should have warning indicator for dangerous actions
        assert any(word in result.lower() for word in ["warning", "irreversible", "cannot be undone"])

    def test_confirmation_response_returns_string(self):
        """confirmation_response() should return a string."""
        from core.response.templates import confirmation_response

        result = confirmation_response("test action")

        assert isinstance(result, str)


class TestInfoResponse:
    """Test info_response template."""

    def test_info_response_basic(self):
        """info_response() should format informational message."""
        from core.response.templates import info_response

        result = info_response("Feature is currently in beta")

        assert "Feature is currently in beta" in result

    def test_info_response_returns_string(self):
        """info_response() should return a string."""
        from core.response.templates import info_response

        result = info_response("Test info")

        assert isinstance(result, str)


class TestWarningResponse:
    """Test warning_response template."""

    def test_warning_response_basic(self):
        """warning_response() should format warning message."""
        from core.response.templates import warning_response

        result = warning_response("Rate limit approaching")

        assert "Rate limit approaching" in result
        # Should have warning indicator
        assert any(word in result.lower() for word in ["warning", "caution", "attention"])

    def test_warning_response_returns_string(self):
        """warning_response() should return a string."""
        from core.response.templates import warning_response

        result = warning_response("Test warning")

        assert isinstance(result, str)


class TestTradeResponse:
    """Test trade-related templates."""

    def test_trade_success_response(self):
        """trade_success() should format successful trade."""
        from core.response.templates import trade_success

        result = trade_success(
            action="BUY",
            token="BONK",
            amount=100.0,
            price=0.000025
        )

        assert "BUY" in result
        assert "BONK" in result
        assert "100" in result

    def test_trade_failed_response(self):
        """trade_failed() should format failed trade."""
        from core.response.templates import trade_failed

        result = trade_failed(
            action="SELL",
            token="BONK",
            reason="Insufficient balance"
        )

        assert "SELL" in result
        assert "BONK" in result
        assert "Insufficient balance" in result


class TestPortfolioResponse:
    """Test portfolio-related templates."""

    def test_portfolio_summary(self):
        """portfolio_summary() should format portfolio overview."""
        from core.response.templates import portfolio_summary

        result = portfolio_summary(
            balance_sol=10.5,
            balance_usd=1050.0,
            positions=3,
            total_pnl=125.50
        )

        assert "10.5" in result
        assert "1050" in result or "1,050" in result
        assert "3" in result
        assert "125" in result

    def test_position_summary(self):
        """position_summary() should format single position."""
        from core.response.templates import position_summary

        result = position_summary(
            token="SOL",
            entry_price=100.0,
            current_price=115.0,
            pnl_pct=15.0,
            value_usd=115.0
        )

        assert "SOL" in result
        assert "100" in result
        assert "115" in result
        assert "15" in result


class TestAlertResponse:
    """Test alert-related templates."""

    def test_price_alert(self):
        """price_alert() should format price alert notification."""
        from core.response.templates import price_alert

        result = price_alert(
            token="BONK",
            target_price=0.00003,
            current_price=0.000031,
            direction="above"
        )

        assert "BONK" in result
        assert "above" in result.lower() or "reached" in result.lower()

    def test_position_alert(self):
        """position_alert() should format position alert."""
        from core.response.templates import position_alert

        result = position_alert(
            token="SOL",
            alert_type="take_profit",
            trigger_price=120.0,
            current_pnl_pct=20.0
        )

        assert "SOL" in result
        assert "take" in result.lower() or "profit" in result.lower()
        assert "20" in result


class TestTemplateHelpers:
    """Test template helper functions."""

    def test_format_price(self):
        """format_price() should format price appropriately."""
        from core.response.templates import format_price

        # Large price
        assert "$100.00" in format_price(100.0) or "100" in format_price(100.0)

        # Small price (crypto)
        small = format_price(0.00001234)
        assert "1234" in small or "1.234" in small

    def test_format_percentage(self):
        """format_percentage() should format percentages."""
        from core.response.templates import format_percentage

        # Positive
        pos = format_percentage(15.5)
        assert "15.5" in pos or "+15.5" in pos

        # Negative
        neg = format_percentage(-8.2)
        assert "8.2" in neg

    def test_format_amount(self):
        """format_amount() should format amounts with commas."""
        from core.response.templates import format_amount

        result = format_amount(1234567.89)
        assert "1,234,567" in result or "1234567" in result
