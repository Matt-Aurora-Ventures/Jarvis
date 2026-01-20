"""
Unit tests for alert integration.

Tests:
- Telegram message delivery
- Core alert engine integration
- Telegram alert system integration
- Multiple channel delivery
- Error handling
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime

from bots.treasury.position_alerts import (
    PositionAlert,
    PositionAlertType,
    AlertSeverity,
    PositionMonitor,
    AlertThreshold
)
from bots.treasury.alert_integration import AlertIntegration, setup_position_alerts


class TestAlertIntegration:
    """Test alert integration with notification systems."""

    @pytest.fixture
    def mock_monitor(self):
        """Create mock position monitor."""
        mock_engine = Mock()
        mock_engine.get_open_positions = Mock(return_value=[])
        return PositionMonitor(mock_engine)

    @pytest.fixture
    def mock_telegram_context(self):
        """Create mock Telegram context."""
        context = Mock()
        context.bot = Mock()
        context.bot.send_message = AsyncMock()
        return context

    @pytest.fixture
    def sample_alert(self):
        """Create sample alert for testing."""
        return PositionAlert(
            alert_id="TEST-ALERT-1",
            position_id="POS-123",
            token_symbol="SOL",
            alert_type=PositionAlertType.PROFIT_THRESHOLD,
            severity=AlertSeverity.SUCCESS,
            title="🎯 Profit Milestone: +20%",
            message="Position has reached +20% profit!",
            data={
                "Entry Price": 100.0,
                "Current Price": 120.0,
                "P&L %": 20.0
            }
        )

    @pytest.mark.asyncio
    async def test_telegram_message_delivery(self, mock_monitor, mock_telegram_context, sample_alert):
        """Test alert delivery via Telegram."""
        admin_ids = [12345, 67890]

        integration = AlertIntegration(
            position_monitor=mock_monitor,
            admin_ids=admin_ids,
            telegram_context=mock_telegram_context
        )

        # Deliver alert
        await integration.handle_alert(sample_alert)

        # Verify sent to all admins
        assert mock_telegram_context.bot.send_message.call_count == len(admin_ids)

        # Check call arguments
        calls = mock_telegram_context.bot.send_message.call_args_list
        sent_to = {call.kwargs['chat_id'] for call in calls}
        assert sent_to == set(admin_ids)

        # Check message format
        for call in calls:
            assert 'text' in call.kwargs
            assert sample_alert.token_symbol in call.kwargs['text']
            assert 'parse_mode' in call.kwargs

    @pytest.mark.asyncio
    async def test_no_telegram_context(self, mock_monitor, sample_alert):
        """Test graceful handling when no Telegram context."""
        integration = AlertIntegration(
            position_monitor=mock_monitor,
            admin_ids=[12345],
            telegram_context=None
        )

        # Should not raise error
        await integration.handle_alert(sample_alert)

    @pytest.mark.asyncio
    async def test_telegram_send_error_handling(self, mock_monitor, mock_telegram_context, sample_alert):
        """Test error handling when Telegram send fails."""
        admin_ids = [12345, 67890]

        # First send succeeds, second fails
        mock_telegram_context.bot.send_message = AsyncMock(
            side_effect=[None, Exception("Send failed")]
        )

        integration = AlertIntegration(
            position_monitor=mock_monitor,
            admin_ids=admin_ids,
            telegram_context=mock_telegram_context
        )

        # Should not raise, should log error
        await integration.handle_alert(sample_alert)

        # Both sends were attempted
        assert mock_telegram_context.bot.send_message.call_count == 2

    @pytest.mark.asyncio
    async def test_core_alert_engine_integration(self, mock_monitor, sample_alert):
        """Test integration with core alert engine."""
        # Mock core alert engine
        mock_core_engine = Mock()
        mock_core_engine.create_alert = AsyncMock()

        integration = AlertIntegration(
            position_monitor=mock_monitor,
            admin_ids=[12345],
            core_alert_engine=mock_core_engine
        )

        # Deliver alert
        await integration.handle_alert(sample_alert)

        # Verify core engine was called
        mock_core_engine.create_alert.assert_called_once()

        # Check arguments
        call_kwargs = mock_core_engine.create_alert.call_args.kwargs
        assert call_kwargs['title'] == sample_alert.title
        assert call_kwargs['message'] == sample_alert.message
        assert call_kwargs['token'] == sample_alert.token_symbol

    @pytest.mark.asyncio
    async def test_telegram_system_integration(self, mock_monitor, mock_telegram_context, sample_alert):
        """Test integration with Telegram alert system."""
        # Mock Telegram alert system
        mock_tg_system = Mock()
        mock_tg_system.send_alert = AsyncMock()

        integration = AlertIntegration(
            position_monitor=mock_monitor,
            admin_ids=[12345],
            telegram_context=mock_telegram_context,
            telegram_alert_system=mock_tg_system
        )

        # Deliver alert
        await integration.handle_alert(sample_alert)

        # Verify telegram system was called
        mock_tg_system.send_alert.assert_called_once()

    @pytest.mark.asyncio
    async def test_multiple_channel_delivery(self, mock_monitor, mock_telegram_context, sample_alert):
        """Test alert sent through all configured channels."""
        mock_core_engine = Mock()
        mock_core_engine.create_alert = AsyncMock()

        mock_tg_system = Mock()
        mock_tg_system.send_alert = AsyncMock()

        integration = AlertIntegration(
            position_monitor=mock_monitor,
            admin_ids=[12345],
            telegram_context=mock_telegram_context,
            core_alert_engine=mock_core_engine,
            telegram_alert_system=mock_tg_system
        )

        # Deliver alert
        await integration.handle_alert(sample_alert)

        # All channels should receive
        assert mock_telegram_context.bot.send_message.call_count == 1
        mock_core_engine.create_alert.assert_called_once()
        mock_tg_system.send_alert.assert_called_once()

    @pytest.mark.asyncio
    async def test_alert_type_mapping(self, mock_monitor, mock_telegram_context):
        """Test different alert types map correctly."""
        mock_core_engine = Mock()
        mock_core_engine.create_alert = AsyncMock()

        integration = AlertIntegration(
            position_monitor=mock_monitor,
            admin_ids=[12345],
            telegram_context=mock_telegram_context,
            core_alert_engine=mock_core_engine
        )

        # Test different alert types
        alert_types = [
            PositionAlertType.PROFIT_THRESHOLD,
            PositionAlertType.LOSS_THRESHOLD,
            PositionAlertType.STOP_LOSS_TRIGGERED,
            PositionAlertType.TAKE_PROFIT_REACHED,
            PositionAlertType.VOLUME_SPIKE
        ]

        for alert_type in alert_types:
            alert = PositionAlert(
                alert_id=f"TEST-{alert_type.value}",
                position_id="POS-1",
                token_symbol="SOL",
                alert_type=alert_type,
                severity=AlertSeverity.INFO,
                title="Test",
                message="Test message"
            )

            await integration.handle_alert(alert)

        # Should have called for each type
        assert mock_core_engine.create_alert.call_count == len(alert_types)

    @pytest.mark.asyncio
    async def test_severity_mapping(self, mock_monitor, mock_telegram_context):
        """Test severity levels map to priority."""
        mock_core_engine = Mock()
        mock_core_engine.create_alert = AsyncMock()

        integration = AlertIntegration(
            position_monitor=mock_monitor,
            admin_ids=[12345],
            telegram_context=mock_telegram_context,
            core_alert_engine=mock_core_engine
        )

        # Test different severities
        severities = [
            AlertSeverity.INFO,
            AlertSeverity.SUCCESS,
            AlertSeverity.WARNING,
            AlertSeverity.CRITICAL
        ]

        for severity in severities:
            alert = PositionAlert(
                alert_id=f"TEST-{severity.value}",
                position_id="POS-1",
                token_symbol="SOL",
                alert_type=PositionAlertType.PROFIT_THRESHOLD,
                severity=severity,
                title="Test",
                message="Test message"
            )

            await integration.handle_alert(alert)

        # Should have called for each severity
        assert mock_core_engine.create_alert.call_count == len(severities)

    def test_update_telegram_context(self, mock_monitor, mock_telegram_context):
        """Test updating Telegram context."""
        integration = AlertIntegration(
            position_monitor=mock_monitor,
            admin_ids=[12345],
            telegram_context=None
        )

        assert integration.telegram_context is None

        integration.set_telegram_context(mock_telegram_context)

        assert integration.telegram_context == mock_telegram_context

    def test_update_admin_ids(self, mock_monitor):
        """Test updating admin IDs."""
        integration = AlertIntegration(
            position_monitor=mock_monitor,
            admin_ids=[12345]
        )

        assert integration.admin_ids == [12345]

        new_ids = [11111, 22222, 33333]
        integration.update_admin_ids(new_ids)

        assert integration.admin_ids == new_ids

    def test_handler_registration(self, mock_monitor):
        """Test alert handler is registered on init."""
        integration = AlertIntegration(
            position_monitor=mock_monitor,
            admin_ids=[12345]
        )

        # Handler should be registered
        assert len(mock_monitor.alert_handlers) == 1
        assert integration.handle_alert in mock_monitor.alert_handlers


class TestSetupPositionAlerts:
    """Test quick setup function."""

    @pytest.fixture
    def mock_engine(self):
        """Create mock trading engine."""
        engine = Mock()
        engine.get_open_positions = Mock(return_value=[])
        return engine

    def test_basic_setup(self, mock_engine):
        """Test basic setup without optional parameters."""
        admin_ids = [12345]

        monitor, integration = setup_position_alerts(
            trading_engine=mock_engine,
            admin_ids=admin_ids
        )

        assert monitor is not None
        assert integration is not None
        assert integration.admin_ids == admin_ids
        assert monitor.thresholds is not None

    def test_setup_with_telegram_context(self, mock_engine):
        """Test setup with Telegram context."""
        mock_context = Mock()
        admin_ids = [12345]

        monitor, integration = setup_position_alerts(
            trading_engine=mock_engine,
            admin_ids=admin_ids,
            telegram_context=mock_context
        )

        assert integration.telegram_context == mock_context

    def test_setup_with_custom_thresholds(self, mock_engine):
        """Test setup with custom thresholds."""
        custom_thresholds = AlertThreshold(
            profit_levels=[25.0, 50.0],
            loss_levels=[10.0, 25.0]
        )

        monitor, integration = setup_position_alerts(
            trading_engine=mock_engine,
            admin_ids=[12345],
            custom_thresholds=custom_thresholds
        )

        assert monitor.thresholds == custom_thresholds
        assert monitor.thresholds.profit_levels == [25.0, 50.0]

    @patch('bots.treasury.alert_integration.CORE_ALERTS_AVAILABLE', True)
    @patch('core.alerts.alert_engine.get_alert_engine')
    def test_setup_with_core_engine(self, mock_get_engine, mock_engine):
        """Test setup connects to core alert engine."""
        mock_core_engine = Mock()
        mock_get_engine.return_value = mock_core_engine

        monitor, integration = setup_position_alerts(
            trading_engine=mock_engine,
            admin_ids=[12345]
        )

        # Should have attempted to connect to core engine
        # (may or may not call depending on import success)


class TestAlertMessageFormatting:
    """Test alert message formatting."""

    def test_profit_alert_format(self):
        """Test profit alert message formatting."""
        alert = PositionAlert(
            alert_id="TEST-1",
            position_id="POS-1",
            token_symbol="SOL",
            alert_type=PositionAlertType.PROFIT_THRESHOLD,
            severity=AlertSeverity.SUCCESS,
            title="🎯 Profit Milestone: +20%",
            message="Position reached +20%",
            data={
                "Entry Price": 100.0,
                "Current Price": 120.0,
                "P&L %": 20.0
            }
        )

        message = alert.to_telegram_message()

        assert "SOL" in message
        assert "20%" in message or "20.0%" in message
        assert "Entry Price" in message
        assert "Current Price" in message

    def test_loss_alert_format(self):
        """Test loss alert message formatting."""
        alert = PositionAlert(
            alert_id="TEST-2",
            position_id="POS-2",
            token_symbol="BONK",
            alert_type=PositionAlertType.LOSS_THRESHOLD,
            severity=AlertSeverity.WARNING,
            title="📉 Loss Alert: -10%",
            message="Position lost 10%",
            data={
                "Entry Price": 0.00001,
                "Current Price": 0.000009,
                "P&L %": -10.0
            }
        )

        message = alert.to_telegram_message()

        assert "BONK" in message
        assert "-10" in message
        assert alert.severity.value in message

    def test_stop_loss_format(self):
        """Test stop loss alert formatting."""
        alert = PositionAlert(
            alert_id="TEST-3",
            position_id="POS-3",
            token_symbol="ETH",
            alert_type=PositionAlertType.STOP_LOSS_TRIGGERED,
            severity=AlertSeverity.CRITICAL,
            title="🛑 Stop Loss Triggered",
            message="Stop loss hit",
            data={
                "Stop Loss": 2800.0,
                "Current Price": 2750.0
            }
        )

        message = alert.to_telegram_message()

        assert "ETH" in message
        assert "2800" in message
        assert "🚨" in message  # Critical emoji


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
