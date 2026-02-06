"""
Notification Templates - Pre-defined templates for common notification types.

Templates provide consistent formatting for:
- AlertTemplate: Price alerts, whale alerts, risk warnings
- ReportTemplate: Daily summaries, portfolio reports, performance reports
- ErrorTemplate: System errors, API failures, exceptions
- SuccessTemplate: Trade confirmations, deployment success, backups
"""
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional


class BaseTemplate(ABC):
    """Abstract base class for notification templates."""

    @abstractmethod
    def render(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Render the template with the provided data.

        Args:
            data: Template-specific data to render

        Returns:
            Dict containing at minimum: title, message, priority
        """
        pass

    def _get_timestamp(self) -> str:
        """Get current timestamp in ISO format."""
        return datetime.now().isoformat()

    def _generate_id(self, prefix: str = "notif") -> str:
        """Generate a unique notification ID."""
        import uuid
        return f"{prefix}-{uuid.uuid4().hex[:8]}"


class AlertTemplate(BaseTemplate):
    """Template for alert notifications (price alerts, whale alerts, risk warnings)."""

    # Priority mapping based on severity
    SEVERITY_PRIORITY = {
        "critical": "critical",
        "high": "high",
        "medium": "medium",
        "low": "low",
        "info": "low",
    }

    def render(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Render an alert notification.

        Expected data fields:
            - alert_type: str (price, whale, risk, info)
            - message: str (alert message)
            - severity: str (optional, defaults based on alert_type)
            - symbol: str (optional, for price/whale alerts)
            - threshold: float (optional, for price alerts)
            - current_value/current_price: float (optional)
            - direction: str (optional, above/below)
            - wallet: str (optional, for whale alerts)
            - amount: float (optional, for whale alerts)
            - action: str (optional, buy/sell for whale alerts)
        """
        alert_type = data.get("alert_type", "generic")
        severity = data.get("severity", self._infer_severity(alert_type))
        priority = self.SEVERITY_PRIORITY.get(severity, "medium")

        title = self._generate_title(data)
        message = self._generate_message(data)

        return {
            "id": data.get("id", self._generate_id("alert")),
            "title": title,
            "message": message,
            "priority": priority,
            "type": f"alert_{alert_type}",
            "data": data,
            "created_at": self._get_timestamp(),
        }

    def _infer_severity(self, alert_type: str) -> str:
        """Infer severity based on alert type."""
        severity_map = {
            "risk": "critical",
            "whale": "high",
            "price": "medium",
            "info": "low",
        }
        return severity_map.get(alert_type, "medium")

    def _generate_title(self, data: Dict[str, Any]) -> str:
        """Generate alert title based on type."""
        alert_type = data.get("alert_type", "generic")
        symbol = data.get("symbol", "")

        if alert_type == "price":
            direction = data.get("direction", "reached")
            return f"Price Alert: {symbol} {direction} threshold"
        elif alert_type == "whale":
            action = data.get("action", "movement")
            return f"Whale Alert: Large {action} detected"
        elif alert_type == "risk":
            return "RISK WARNING: Immediate attention required"
        elif alert_type == "info":
            return "Information Alert"
        else:
            return f"Alert: {alert_type.title()}"

    def _generate_message(self, data: Dict[str, Any]) -> str:
        """Generate alert message."""
        alert_type = data.get("alert_type", "generic")
        message = data.get("message", "")

        if message:
            return message

        if alert_type == "price":
            symbol = data.get("symbol", "Unknown")
            threshold = data.get("threshold", 0)
            current = data.get("current_price", data.get("current_value", 0))
            direction = data.get("direction", "reached")

            return f"{symbol} has {direction} ${threshold:,.2f}. Current price: ${current:,.2f}"

        elif alert_type == "whale":
            symbol = data.get("symbol", "Unknown")
            amount = data.get("amount", 0)
            action = data.get("action", "moved")
            wallet = data.get("wallet", "Unknown")

            return f"Whale {action}: {amount:,.0f} {symbol} by wallet {wallet}"

        return "Alert triggered"


class ReportTemplate(BaseTemplate):
    """Template for report notifications (summaries, portfolio, performance)."""

    def render(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Render a report notification.

        Expected data fields:
            - report_type: str (daily_summary, portfolio, performance, comprehensive)
            - period: str (date/range)
            - metrics: dict (key metrics)
            - sections: list (for comprehensive reports)
            - positions: list (for portfolio reports)
            - returns: float (for performance reports)
        """
        report_type = data.get("report_type", "summary")
        title = self._generate_title(data)
        message = self._generate_message(data)

        return {
            "id": data.get("id", self._generate_id("report")),
            "title": title,
            "message": message,
            "priority": "low",
            "type": f"report_{report_type}",
            "data": data,
            "created_at": self._get_timestamp(),
        }

    def _generate_title(self, data: Dict[str, Any]) -> str:
        """Generate report title."""
        report_type = data.get("report_type", "summary")
        period = data.get("period", "")

        title_map = {
            "daily_summary": f"Daily Summary - {period}",
            "portfolio": "Portfolio Report",
            "performance": f"Performance Report ({period})" if period else "Performance Report",
            "comprehensive": "Comprehensive Report",
        }

        return title_map.get(report_type, f"Report: {report_type.replace('_', ' ').title()}")

    def _generate_message(self, data: Dict[str, Any]) -> str:
        """Generate report message."""
        report_type = data.get("report_type", "summary")
        lines = []

        if report_type == "daily_summary":
            metrics = data.get("metrics", {})
            if metrics:
                lines.append("Key Metrics:")
                for key, value in metrics.items():
                    formatted_key = key.replace("_", " ").title()
                    if isinstance(value, float):
                        lines.append(f"  - {formatted_key}: {value:,.2f}")
                    else:
                        lines.append(f"  - {formatted_key}: {value}")

        elif report_type == "portfolio":
            total_value = data.get("total_value", 0)
            positions = data.get("positions", [])
            lines.append(f"Total Portfolio Value: ${total_value:,.2f}")
            if positions:
                lines.append("\nPositions:")
                for pos in positions[:5]:  # Limit to top 5
                    symbol = pos.get("symbol", "Unknown")
                    value = pos.get("value", 0)
                    pnl = pos.get("pnl_percent", 0)
                    sign = "+" if pnl >= 0 else ""
                    lines.append(f"  - {symbol}: ${value:,.2f} ({sign}{pnl:.1f}%)")

        elif report_type == "performance":
            returns = data.get("returns", 0)
            sharpe = data.get("sharpe_ratio", 0)
            drawdown = data.get("max_drawdown", 0)
            period = data.get("period", "Period")

            lines.append(f"{period.title()} Performance Summary:")
            lines.append(f"  - Returns: {'+' if returns >= 0 else ''}{returns:.2f}%")
            if sharpe:
                lines.append(f"  - Sharpe Ratio: {sharpe:.2f}")
            if drawdown:
                lines.append(f"  - Max Drawdown: {drawdown:.2f}%")

        elif report_type == "comprehensive":
            sections = data.get("sections", [])
            for section in sections:
                name = section.get("name", "Section")
                content = section.get("content", "")
                lines.append(f"\n{name}:")
                lines.append(f"  {content}")

        return "\n".join(lines) if lines else "Report generated successfully."


class ErrorTemplate(BaseTemplate):
    """Template for error notifications (system errors, API failures, exceptions)."""

    def render(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Render an error notification.

        Expected data fields:
            - error_type: str (connection, exception, api, system, auth)
            - message: str (error message)
            - severity: str (critical, high, medium)
            - component: str (optional, which component failed)
            - stack_trace: str (optional)
            - impact: str (optional)
            - recovery: str (optional, recovery instructions)
        """
        error_type = data.get("error_type", "generic")
        severity = data.get("severity", "high")

        # Errors are at least high priority
        priority = "critical" if severity == "critical" else "high"

        title = self._generate_title(data)
        message = self._generate_message(data)

        result = {
            "id": data.get("id", self._generate_id("error")),
            "title": title,
            "message": message,
            "priority": priority,
            "type": f"error_{error_type}",
            "created_at": self._get_timestamp(),
        }

        # Include additional data for debugging
        error_data = {}
        if "component" in data:
            error_data["component"] = data["component"]
        if "stack_trace" in data:
            error_data["stack_trace"] = data["stack_trace"]
        if "impact" in data:
            error_data["impact"] = data["impact"]
        if "recovery" in data:
            error_data["recovery"] = data["recovery"]

        if error_data:
            result["data"] = error_data

        return result

    def _generate_title(self, data: Dict[str, Any]) -> str:
        """Generate error title."""
        error_type = data.get("error_type", "generic")
        severity = data.get("severity", "high")
        component = data.get("component", "")

        severity_prefix = "CRITICAL: " if severity == "critical" else "ERROR: "

        type_titles = {
            "connection": "Connection Failed",
            "exception": "Unexpected Exception",
            "api": "API Error",
            "system": "System Error",
            "auth": "Authentication Failed",
        }

        title = type_titles.get(error_type, f"{error_type.title()} Error")

        if component:
            title = f"{title} in {component}"

        return f"{severity_prefix}{title}"

    def _generate_message(self, data: Dict[str, Any]) -> str:
        """Generate error message."""
        lines = []

        message = data.get("message", "An error occurred")
        lines.append(message)

        impact = data.get("impact")
        if impact:
            lines.append(f"\nImpact: {impact}")

        recovery = data.get("recovery")
        if recovery:
            lines.append(f"\nRecovery: {recovery}")

        stack_trace = data.get("stack_trace")
        if stack_trace:
            # Truncate long stack traces
            truncated = stack_trace[:500] + "..." if len(stack_trace) > 500 else stack_trace
            lines.append(f"\nStack Trace:\n{truncated}")

        return "\n".join(lines)


class SuccessTemplate(BaseTemplate):
    """Template for success notifications (trade confirmations, deployments, backups)."""

    def render(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Render a success notification.

        Expected data fields:
            - action: str (trade, deployment, backup, etc.)
            - message: str (success message)
            - details: dict (optional, action-specific details)
            - trade_type: str (optional, buy/sell)
            - symbol: str (optional)
            - amount: float (optional)
            - price: float (optional)
            - service: str (optional, for deployments)
            - version: str (optional)
            - environment: str (optional)
        """
        action = data.get("action", "operation")
        title = self._generate_title(data)
        message = self._generate_message(data)

        return {
            "id": data.get("id", self._generate_id("success")),
            "title": title,
            "message": message,
            "priority": "low",
            "type": f"success_{action}",
            "data": data.get("details", {}),
            "created_at": self._get_timestamp(),
        }

    def _generate_title(self, data: Dict[str, Any]) -> str:
        """Generate success title."""
        action = data.get("action", "operation")

        if action == "trade" or action == "trade_executed":
            trade_type = data.get("trade_type", "trade")
            symbol = data.get("symbol", "")
            return f"Trade Success: {trade_type.upper()} {symbol}"

        elif action == "deployment":
            service = data.get("service", "Service")
            return f"Deployment Success: {service}"

        elif action == "backup":
            return "Backup Completed Successfully"

        return f"Success: {action.replace('_', ' ').title()}"

    def _generate_message(self, data: Dict[str, Any]) -> str:
        """Generate success message."""
        action = data.get("action", "operation")
        message = data.get("message", "")

        if message:
            return message

        if action == "trade" or action == "trade_executed":
            trade_type = data.get("trade_type", "Executed")
            symbol = data.get("symbol", "Unknown")
            amount = data.get("amount", 0)
            price = data.get("price", 0)
            total = data.get("total_value", amount * price)

            return (
                f"Successfully {trade_type.lower()} {amount:,.2f} {symbol} "
                f"at ${price:,.2f} (Total: ${total:,.2f})"
            )

        elif action == "deployment":
            service = data.get("service", "Service")
            version = data.get("version", "")
            env = data.get("environment", "")

            msg = f"{service} deployed successfully"
            if version:
                msg += f" (v{version})"
            if env:
                msg += f" to {env}"
            return msg

        elif action == "backup":
            return "System backup completed successfully. All data has been preserved."

        return f"Operation '{action}' completed successfully."
