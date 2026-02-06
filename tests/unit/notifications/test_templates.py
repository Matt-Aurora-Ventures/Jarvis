"""
Tests for notification templates - AlertTemplate, ReportTemplate, ErrorTemplate, SuccessTemplate.

TDD Phase 1: Write failing tests first.
"""
import pytest
from datetime import datetime


class TestAlertTemplate:
    """Test suite for AlertTemplate."""

    @pytest.fixture
    def alert_template(self):
        """Create an AlertTemplate instance."""
        from core.notifications.templates import AlertTemplate
        return AlertTemplate()

    def test_alert_template_instantiation(self, alert_template):
        """Test AlertTemplate can be instantiated."""
        assert alert_template is not None

    def test_alert_template_render_basic(self, alert_template):
        """Test basic alert rendering."""
        data = {
            "alert_type": "price",
            "symbol": "SOL",
            "message": "SOL price crossed $150",
            "threshold": 150.0,
            "current_value": 152.5,
        }

        result = alert_template.render(data)

        assert isinstance(result, dict)
        assert "title" in result
        assert "message" in result
        assert "priority" in result

    def test_alert_template_priority_levels(self, alert_template):
        """Test alert priority based on severity."""
        high_alert = {
            "alert_type": "risk",
            "severity": "critical",
            "message": "Portfolio at extreme risk",
        }
        low_alert = {
            "alert_type": "info",
            "severity": "low",
            "message": "Minor price change",
        }

        high_result = alert_template.render(high_alert)
        low_result = alert_template.render(low_alert)

        assert high_result["priority"] == "critical"
        assert low_result["priority"] == "low"

    def test_alert_template_price_alert(self, alert_template):
        """Test price alert specific formatting."""
        data = {
            "alert_type": "price",
            "symbol": "BTC",
            "direction": "above",
            "threshold": 50000,
            "current_price": 51000,
        }

        result = alert_template.render(data)

        assert "BTC" in result["title"] or "BTC" in result["message"]
        assert "50000" in str(result["message"]) or "threshold" in str(result)

    def test_alert_template_whale_alert(self, alert_template):
        """Test whale alert specific formatting."""
        data = {
            "alert_type": "whale",
            "symbol": "SOL",
            "amount": 1000000,
            "wallet": "ABC123...",
            "action": "buy",
        }

        result = alert_template.render(data)

        assert "whale" in result["title"].lower() or "whale" in result.get("type", "").lower()

    def test_alert_template_includes_timestamp(self, alert_template):
        """Test that alerts include timestamp."""
        data = {
            "alert_type": "price",
            "message": "Test alert",
        }

        result = alert_template.render(data)

        assert "created_at" in result or "timestamp" in result


class TestReportTemplate:
    """Test suite for ReportTemplate."""

    @pytest.fixture
    def report_template(self):
        """Create a ReportTemplate instance."""
        from core.notifications.templates import ReportTemplate
        return ReportTemplate()

    def test_report_template_instantiation(self, report_template):
        """Test ReportTemplate can be instantiated."""
        assert report_template is not None

    def test_report_template_render_basic(self, report_template):
        """Test basic report rendering."""
        data = {
            "report_type": "daily_summary",
            "period": "2026-02-01",
            "metrics": {
                "total_trades": 15,
                "profit_loss": 1250.50,
                "win_rate": 0.67,
            },
        }

        result = report_template.render(data)

        assert isinstance(result, dict)
        assert "title" in result
        assert "message" in result

    def test_report_template_portfolio_report(self, report_template):
        """Test portfolio report formatting."""
        data = {
            "report_type": "portfolio",
            "total_value": 50000,
            "positions": [
                {"symbol": "SOL", "value": 20000, "pnl_percent": 5.2},
                {"symbol": "BTC", "value": 30000, "pnl_percent": -2.1},
            ],
        }

        result = report_template.render(data)

        # Should include position information
        message = result["message"]
        assert "SOL" in message or "portfolio" in result["title"].lower()

    def test_report_template_performance_report(self, report_template):
        """Test performance report formatting."""
        data = {
            "report_type": "performance",
            "period": "weekly",
            "returns": 12.5,
            "sharpe_ratio": 1.8,
            "max_drawdown": -8.3,
        }

        result = report_template.render(data)

        assert "performance" in result["title"].lower() or "weekly" in result["title"].lower()

    def test_report_template_sections(self, report_template):
        """Test report with multiple sections."""
        data = {
            "report_type": "comprehensive",
            "sections": [
                {"name": "Overview", "content": "Summary text"},
                {"name": "Details", "content": "Detailed analysis"},
                {"name": "Recommendations", "content": "Action items"},
            ],
        }

        result = report_template.render(data)

        # Message should include section content
        message = result["message"]
        assert "Overview" in message or "Summary" in message


class TestErrorTemplate:
    """Test suite for ErrorTemplate."""

    @pytest.fixture
    def error_template(self):
        """Create an ErrorTemplate instance."""
        from core.notifications.templates import ErrorTemplate
        return ErrorTemplate()

    def test_error_template_instantiation(self, error_template):
        """Test ErrorTemplate can be instantiated."""
        assert error_template is not None

    def test_error_template_render_basic(self, error_template):
        """Test basic error rendering."""
        data = {
            "error_type": "connection",
            "message": "Failed to connect to exchange",
            "component": "trading_engine",
        }

        result = error_template.render(data)

        assert isinstance(result, dict)
        assert "title" in result
        assert "message" in result
        assert result["priority"] in ["high", "critical"]

    def test_error_template_includes_stack_trace(self, error_template):
        """Test error includes stack trace when provided."""
        data = {
            "error_type": "exception",
            "message": "Unexpected error",
            "stack_trace": "Traceback (most recent call last):\n  File ...",
        }

        result = error_template.render(data)

        # Stack trace should be in data or truncated message
        assert "stack_trace" in result.get("data", {}) or "Traceback" in result.get("message", "")

    def test_error_template_severity_critical(self, error_template):
        """Test critical error formatting."""
        data = {
            "error_type": "system",
            "severity": "critical",
            "message": "Database connection lost",
            "impact": "All trading halted",
        }

        result = error_template.render(data)

        assert result["priority"] == "critical"

    def test_error_template_includes_timestamp(self, error_template):
        """Test error includes timestamp."""
        data = {
            "error_type": "api",
            "message": "API rate limit exceeded",
        }

        result = error_template.render(data)

        assert "created_at" in result or "timestamp" in result

    def test_error_template_recovery_instructions(self, error_template):
        """Test error includes recovery instructions when provided."""
        data = {
            "error_type": "auth",
            "message": "Authentication failed",
            "recovery": "Regenerate API keys and restart service",
        }

        result = error_template.render(data)

        message = result["message"]
        assert "recovery" in message.lower() or "regenerate" in message.lower() or "recovery" in result.get("data", {})


class TestSuccessTemplate:
    """Test suite for SuccessTemplate."""

    @pytest.fixture
    def success_template(self):
        """Create a SuccessTemplate instance."""
        from core.notifications.templates import SuccessTemplate
        return SuccessTemplate()

    def test_success_template_instantiation(self, success_template):
        """Test SuccessTemplate can be instantiated."""
        assert success_template is not None

    def test_success_template_render_basic(self, success_template):
        """Test basic success rendering."""
        data = {
            "action": "trade_executed",
            "message": "Successfully bought 10 SOL",
            "details": {
                "symbol": "SOL",
                "amount": 10,
                "price": 150.0,
            },
        }

        result = success_template.render(data)

        assert isinstance(result, dict)
        assert "title" in result
        assert "message" in result
        assert result["priority"] in ["low", "medium"]

    def test_success_template_trade_success(self, success_template):
        """Test trade success formatting."""
        data = {
            "action": "trade",
            "trade_type": "buy",
            "symbol": "SOL",
            "amount": 100,
            "price": 150.0,
            "total_value": 15000,
        }

        result = success_template.render(data)

        message = result["message"]
        assert "SOL" in message or "trade" in result["title"].lower()

    def test_success_template_deployment_success(self, success_template):
        """Test deployment success formatting."""
        data = {
            "action": "deployment",
            "service": "trading_bot",
            "version": "1.2.3",
            "environment": "production",
        }

        result = success_template.render(data)

        assert "deploy" in result["title"].lower() or "success" in result["title"].lower()

    def test_success_template_includes_timestamp(self, success_template):
        """Test success includes timestamp."""
        data = {
            "action": "backup",
            "message": "Backup completed successfully",
        }

        result = success_template.render(data)

        assert "created_at" in result or "timestamp" in result


class TestTemplateBase:
    """Test suite for template base functionality."""

    def test_all_templates_have_render_method(self):
        """Test that all templates implement render method."""
        from core.notifications.templates import (
            AlertTemplate,
            ReportTemplate,
            ErrorTemplate,
            SuccessTemplate,
        )

        templates = [AlertTemplate(), ReportTemplate(), ErrorTemplate(), SuccessTemplate()]

        for template in templates:
            assert hasattr(template, "render")
            assert callable(template.render)

    def test_all_templates_return_notification_dict(self):
        """Test that all templates return properly structured notifications."""
        from core.notifications.templates import (
            AlertTemplate,
            ReportTemplate,
            ErrorTemplate,
            SuccessTemplate,
        )

        templates_and_data = [
            (AlertTemplate(), {"alert_type": "test", "message": "Test alert"}),
            (ReportTemplate(), {"report_type": "test", "metrics": {}}),
            (ErrorTemplate(), {"error_type": "test", "message": "Test error"}),
            (SuccessTemplate(), {"action": "test", "message": "Test success"}),
        ]

        required_fields = ["title", "message", "priority"]

        for template, data in templates_and_data:
            result = template.render(data)

            for field in required_fields:
                assert field in result, f"{template.__class__.__name__} missing '{field}'"
