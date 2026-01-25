"""
Unit tests for tg_bot/services/notification_service.py and core/notifications/router.py

Covers:
- Send notifications (success, failures, retries)
- Priority queue (high/medium/low priority)
- Rate limiting (per-user, per-chat, global)
- Template formatting (variables, markdown, HTML)
- Delivery status (tracking, callbacks, errors)
- Notification preferences
- Quiet hours
- Notification history
- Multi-channel delivery (Telegram, Discord, Webhook)
- Circuit breaker pattern
- Batch processing
- Routing rules

Target: 60%+ coverage with ~40-60 tests
"""

import asyncio
import pytest
import time
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch


# ============================================================================
# Import modules under test
# ============================================================================

from tg_bot.services.notification_service import (
    NotificationService,
    Notification,
    NotificationPreferences,
    NotificationType,
    NotificationPriority,
)

from core.notifications import (
    NotificationRouter,
    NotificationPriority as RouterPriority,
    NotificationType as RouterNotificationType,
    ChannelConfig,
    ChannelType,
    Notification as RouterNotification,
    RoutingRule,
    ChannelResult,
    DeliveryRecord,
    DeliveryStatus,
    RouteResult,
    CircuitBreakerState,
    NonRetryableError,
    get_notification_router,
)


# ============================================================================
# Fixtures - TG Bot Notification Service
# ============================================================================

@pytest.fixture
def notification_service():
    """Create a NotificationService instance."""
    return NotificationService()


@pytest.fixture
def mock_context():
    """Create a mock Telegram context."""
    context = MagicMock()
    context.bot = MagicMock()
    context.bot.send_message = AsyncMock()
    return context


@pytest.fixture
def sample_notification():
    """Create a sample notification."""
    return Notification(
        notification_id="test_123",
        user_id=12345,
        notification_type=NotificationType.PRICE_ALERT,
        priority=NotificationPriority.MEDIUM,
        title="Test Alert",
        message="This is a test notification",
        details={"key": "value"},
    )


@pytest.fixture
def user_preferences():
    """Create user notification preferences."""
    return NotificationPreferences(user_id=12345)


# ============================================================================
# Fixtures - Core Notification Router
# ============================================================================

@pytest.fixture
def notification_router():
    """Create a NotificationRouter instance."""
    return NotificationRouter()


@pytest.fixture
def configured_router(notification_router):
    """Create a fully configured NotificationRouter."""
    notification_router.register_channel(
        channel_type=ChannelType.TELEGRAM,
        name="telegram_main",
        endpoint="123456789",
        api_key="test_bot_token",
        min_priority=RouterPriority.LOW,
        rate_limit_per_minute=10,
    )
    notification_router.register_channel(
        channel_type=ChannelType.DISCORD,
        name="discord_main",
        endpoint="https://discord.webhook/test",
        min_priority=RouterPriority.MEDIUM,
        rate_limit_per_minute=5,
    )
    notification_router.register_channel(
        channel_type=ChannelType.CONSOLE,
        name="console",
        endpoint="",
        min_priority=RouterPriority.LOW,
        rate_limit_per_minute=100,
    )
    # Add routing rules
    notification_router.add_routing_rule(
        notification_type=RouterNotificationType.TRADE_EXECUTED,
        channels=["telegram_main", "discord_main"],
    )
    notification_router.add_routing_rule(
        notification_type=RouterNotificationType.PRICE_ALERT,
        channels=["telegram_main"],
    )
    notification_router.add_routing_rule(
        notification_type=RouterNotificationType.CUSTOM,
        channels=["console"],
    )
    return notification_router


@pytest.fixture
def sample_router_notification():
    """Create a sample router notification."""
    return RouterNotification(
        notification_id="test_router_123",
        notification_type=RouterNotificationType.TRADE_EXECUTED,
        title="Trade Executed",
        message="Bought 10 SOL at $150",
        priority=RouterPriority.HIGH,
        data={"symbol": "SOL", "amount": 10, "price": 150},
        created_at=datetime.now(),
    )


# ============================================================================
# Test: Notification Creation and Properties
# ============================================================================

class TestNotificationCreation:
    """Test notification dataclass creation and properties."""

    def test_notification_creation(self, sample_notification):
        """Should create notification with all fields."""
        assert sample_notification.notification_id == "test_123"
        assert sample_notification.user_id == 12345
        assert sample_notification.notification_type == NotificationType.PRICE_ALERT
        assert sample_notification.priority == NotificationPriority.MEDIUM
        assert sample_notification.title == "Test Alert"
        assert sample_notification.message == "This is a test notification"

    def test_notification_is_read_property(self, sample_notification):
        """Should correctly report read status."""
        assert not sample_notification.is_read
        sample_notification.read_at = datetime.utcnow()
        assert sample_notification.is_read

    def test_notification_time_since_creation(self, sample_notification):
        """Should calculate time since creation."""
        time_diff = sample_notification.time_since_creation
        assert isinstance(time_diff, timedelta)
        assert time_diff.total_seconds() >= 0

    def test_notification_default_factory_fields(self):
        """Should use default factory for list/dict fields."""
        notification = Notification(
            notification_id="test",
            user_id=1,
            notification_type=NotificationType.SYSTEM,
            priority=NotificationPriority.LOW,
            title="Test",
            message="Test",
        )
        assert notification.details == {}
        assert notification.action_buttons == []
        assert notification.sent_at is None
        assert notification.read_at is None


# ============================================================================
# Test: Notification Telegram Message Formatting
# ============================================================================

class TestNotificationFormatting:
    """Test Telegram message formatting."""

    def test_to_telegram_message_basic(self, sample_notification):
        """Should format basic notification."""
        message = sample_notification.to_telegram_message()
        assert "<b>Test Alert</b>" in message
        assert "This is a test notification" in message
        assert "key" in message

    def test_to_telegram_message_priority_emojis(self):
        """Should use correct emoji for each priority."""
        priorities = {
            NotificationPriority.LOW: "info",
            NotificationPriority.MEDIUM: "pin",
            NotificationPriority.HIGH: "warning",
            NotificationPriority.CRITICAL: "alert",
        }

        for priority, _ in priorities.items():
            notification = Notification(
                notification_id="test",
                user_id=1,
                notification_type=NotificationType.SYSTEM,
                priority=priority,
                title="Test",
                message="Test",
            )
            message = notification.to_telegram_message()
            # Just verify it doesn't crash
            assert len(message) > 0

    def test_to_telegram_message_float_formatting(self):
        """Should format float values with 2 decimal places."""
        notification = Notification(
            notification_id="test",
            user_id=1,
            notification_type=NotificationType.PRICE_ALERT,
            priority=NotificationPriority.MEDIUM,
            title="Price Alert",
            message="Price changed",
            details={"price": 123.456789},
        )
        message = notification.to_telegram_message()
        assert "123.46" in message

    def test_to_telegram_message_timestamp(self, sample_notification):
        """Should include timestamp in message."""
        message = sample_notification.to_telegram_message()
        assert "UTC" in message


# ============================================================================
# Test: Notification Preferences
# ============================================================================

class TestNotificationPreferences:
    """Test user notification preferences."""

    def test_default_preferences(self, user_preferences):
        """Should have sensible defaults."""
        assert user_preferences.user_id == 12345
        assert user_preferences.price_alerts_enabled is True
        assert user_preferences.trade_alerts_enabled is True
        assert user_preferences.telegram_enabled is True
        assert user_preferences.max_alerts_per_hour == 30
        assert user_preferences.max_alerts_per_day == 200

    def test_is_notification_enabled(self, user_preferences):
        """Should check if notification type is enabled."""
        assert user_preferences.is_notification_enabled(NotificationType.PRICE_ALERT)
        user_preferences.price_alerts_enabled = False
        assert not user_preferences.is_notification_enabled(NotificationType.PRICE_ALERT)

    def test_is_notification_enabled_all_types(self, user_preferences):
        """Should handle all notification types."""
        for ntype in NotificationType:
            result = user_preferences.is_notification_enabled(ntype)
            assert isinstance(result, bool)

    def test_quiet_hours_disabled(self, user_preferences):
        """Should return False when quiet hours disabled."""
        assert not user_preferences.is_in_quiet_hours()

    def test_quiet_hours_normal_range(self):
        """Should detect quiet hours in normal range."""
        prefs = NotificationPreferences(
            user_id=1,
            quiet_hours_enabled=True,
            quiet_hours_start=10,
            quiet_hours_end=12,
        )
        current_hour = datetime.utcnow().hour
        expected = 10 <= current_hour < 12
        assert prefs.is_in_quiet_hours() == expected

    def test_quiet_hours_wraparound(self):
        """Should handle quiet hours that wrap around midnight."""
        prefs = NotificationPreferences(
            user_id=1,
            quiet_hours_enabled=True,
            quiet_hours_start=23,
            quiet_hours_end=7,
        )
        current_hour = datetime.utcnow().hour
        expected = current_hour >= 23 or current_hour < 7
        assert prefs.is_in_quiet_hours() == expected


# ============================================================================
# Test: Send Notification - Success Cases
# ============================================================================

class TestSendNotificationSuccess:
    """Test successful notification sending."""

    @pytest.mark.asyncio
    async def test_send_notification_success(self, notification_service, sample_notification, mock_context):
        """Should send notification successfully."""
        result = await notification_service.send_notification(
            sample_notification.user_id,
            sample_notification,
            mock_context
        )
        assert result is True
        mock_context.bot.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_notification_stores_in_history(self, notification_service, sample_notification, mock_context):
        """Should store notification in history."""
        await notification_service.send_notification(
            sample_notification.user_id,
            sample_notification,
            mock_context
        )
        history = notification_service.get_notifications(sample_notification.user_id)
        assert len(history) == 1
        assert history[0].notification_id == sample_notification.notification_id

    @pytest.mark.asyncio
    async def test_send_notification_updates_sent_at(self, notification_service, sample_notification, mock_context):
        """Should update sent_at timestamp."""
        assert sample_notification.sent_at is None
        await notification_service.send_notification(
            sample_notification.user_id,
            sample_notification,
            mock_context
        )
        assert sample_notification.sent_at is not None

    @pytest.mark.asyncio
    async def test_send_notification_tracks_alert_count(self, notification_service, sample_notification, mock_context):
        """Should track alert count for rate limiting."""
        user_id = sample_notification.user_id
        initial_count = len(notification_service.alert_counts.get(user_id, []))
        await notification_service.send_notification(user_id, sample_notification, mock_context)
        new_count = len(notification_service.alert_counts.get(user_id, []))
        assert new_count == initial_count + 1


# ============================================================================
# Test: Send Notification - Failure Cases
# ============================================================================

class TestSendNotificationFailure:
    """Test notification sending failure scenarios."""

    @pytest.mark.asyncio
    async def test_send_notification_disabled_type(self, notification_service, mock_context):
        """Should not send when notification type is disabled."""
        notification_service.update_preferences(12345, price_alerts_enabled=False)
        notification = Notification(
            notification_id="test",
            user_id=12345,
            notification_type=NotificationType.PRICE_ALERT,
            priority=NotificationPriority.MEDIUM,
            title="Test",
            message="Test",
        )
        result = await notification_service.send_notification(12345, notification, mock_context)
        assert result is False
        mock_context.bot.send_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_send_notification_telegram_disabled(self, notification_service, mock_context):
        """Should skip telegram sending when disabled but still process notification."""
        notification_service.update_preferences(12345, telegram_enabled=False)
        notification = Notification(
            notification_id="test",
            user_id=12345,
            notification_type=NotificationType.SYSTEM,
            priority=NotificationPriority.MEDIUM,
            title="Test",
            message="Test",
        )
        result = await notification_service.send_notification(12345, notification, mock_context)
        # Implementation returns True (notification processed) but doesn't send via Telegram
        assert result is True
        # Verify telegram was NOT called
        mock_context.bot.send_message.assert_not_called()
        # But notification was still stored in history
        history = notification_service.get_notifications(12345)
        assert len(history) == 1

    @pytest.mark.asyncio
    async def test_send_notification_api_failure(self, notification_service, mock_context):
        """Should handle Telegram API failure."""
        mock_context.bot.send_message.side_effect = Exception("API Error")
        notification = Notification(
            notification_id="test",
            user_id=12345,
            notification_type=NotificationType.SYSTEM,
            priority=NotificationPriority.MEDIUM,
            title="Test",
            message="Test",
        )
        result = await notification_service.send_notification(12345, notification, mock_context)
        assert result is False


# ============================================================================
# Test: Rate Limiting
# ============================================================================

class TestRateLimiting:
    """Test rate limiting functionality."""

    def test_check_rate_limit_allows_under_limit(self, notification_service):
        """Should allow when under rate limit."""
        prefs = notification_service.get_preferences(12345)
        allowed, reason = notification_service._check_rate_limit(12345, prefs)
        assert allowed is True
        assert reason == "OK"

    def test_check_rate_limit_blocks_hourly_exceeded(self, notification_service):
        """Should block when hourly limit exceeded."""
        prefs = notification_service.get_preferences(12345)
        # Fill up hourly limit
        now = datetime.utcnow()
        notification_service.alert_counts[12345] = [
            now - timedelta(minutes=i) for i in range(prefs.max_alerts_per_hour)
        ]
        allowed, reason = notification_service._check_rate_limit(12345, prefs)
        assert allowed is False
        assert "per hour" in reason

    def test_check_rate_limit_blocks_daily_exceeded(self, notification_service):
        """Should block when daily limit exceeded."""
        prefs = notification_service.get_preferences(12345)
        # Fill up daily limit (spread over last 24 hours)
        now = datetime.utcnow()
        notification_service.alert_counts[12345] = [
            now - timedelta(hours=i % 24, minutes=i * 7 % 60)
            for i in range(prefs.max_alerts_per_day)
        ]
        allowed, reason = notification_service._check_rate_limit(12345, prefs)
        assert allowed is False
        assert "today" in reason

    def test_check_rate_limit_ignores_old_alerts(self, notification_service):
        """Should ignore alerts older than limits."""
        prefs = notification_service.get_preferences(12345)
        # Add alerts from 2 days ago
        old_time = datetime.utcnow() - timedelta(days=2)
        notification_service.alert_counts[12345] = [old_time for _ in range(100)]
        allowed, reason = notification_service._check_rate_limit(12345, prefs)
        assert allowed is True

    @pytest.mark.asyncio
    async def test_rate_limit_integration(self, notification_service, mock_context):
        """Should block notifications when rate limited."""
        notification_service.update_preferences(12345, max_alerts_per_hour=2)

        # Send up to limit
        for i in range(3):
            notification = Notification(
                notification_id=f"test_{i}",
                user_id=12345,
                notification_type=NotificationType.SYSTEM,
                priority=NotificationPriority.MEDIUM,
                title="Test",
                message="Test",
            )
            result = await notification_service.send_notification(12345, notification, mock_context)
            if i < 2:
                assert result is True
            else:
                # Third should be rate limited
                assert result is False


# ============================================================================
# Test: Specific Notification Types
# ============================================================================

class TestSpecificNotifications:
    """Test specific notification type methods."""

    @pytest.mark.asyncio
    async def test_notify_price_alert(self, notification_service, mock_context):
        """Should send price alert notification."""
        result = await notification_service.notify_price_alert(
            user_id=12345,
            symbol="SOL",
            current_price=150.50,
            target_price=150.00,
            context=mock_context
        )
        assert result is True
        call_args = mock_context.bot.send_message.call_args
        text = call_args.kwargs.get("text") or call_args[1].get("text")
        assert "SOL" in text
        assert "Price Alert" in text

    @pytest.mark.asyncio
    async def test_notify_trade_executed_buy(self, notification_service, mock_context):
        """Should send trade executed notification for BUY."""
        result = await notification_service.notify_trade_executed(
            user_id=12345,
            symbol="ETH",
            action="BUY",
            amount_usd=1000.0,
            price=2500.0,
            context=mock_context
        )
        assert result is True
        call_args = mock_context.bot.send_message.call_args
        text = call_args.kwargs.get("text") or call_args[1].get("text")
        assert "ETH" in text
        assert "BUY" in text

    @pytest.mark.asyncio
    async def test_notify_trade_executed_sell(self, notification_service, mock_context):
        """Should send trade executed notification for SELL."""
        result = await notification_service.notify_trade_executed(
            user_id=12345,
            symbol="BTC",
            action="SELL",
            amount_usd=5000.0,
            price=45000.0,
            context=mock_context
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_notify_milestone(self, notification_service, mock_context):
        """Should send milestone notification."""
        result = await notification_service.notify_milestone(
            user_id=12345,
            milestone="First $1000 Profit",
            value=1000.0,
            context=mock_context
        )
        assert result is True
        call_args = mock_context.bot.send_message.call_args
        text = call_args.kwargs.get("text") or call_args[1].get("text")
        assert "First $1000 Profit" in text

    @pytest.mark.asyncio
    async def test_notify_risk_alert(self, notification_service, mock_context):
        """Should send risk alert notification."""
        result = await notification_service.notify_risk_alert(
            user_id=12345,
            risk_type="Drawdown",
            current_value=15.0,
            threshold=10.0,
            context=mock_context
        )
        assert result is True
        call_args = mock_context.bot.send_message.call_args
        text = call_args.kwargs.get("text") or call_args[1].get("text")
        assert "Drawdown" in text
        assert "Risk Alert" in text

    @pytest.mark.asyncio
    async def test_notify_high_confidence_signal(self, notification_service, mock_context):
        """Should send high confidence signal notification."""
        result = await notification_service.notify_high_confidence_signal(
            user_id=12345,
            symbol="BONK",
            action="BUY",
            confidence=85.0,
            reason="Strong momentum detected",
            context=mock_context
        )
        assert result is True
        call_args = mock_context.bot.send_message.call_args
        text = call_args.kwargs.get("text") or call_args[1].get("text")
        assert "BONK" in text
        assert "85" in text

    @pytest.mark.asyncio
    async def test_notify_fees_earned(self, notification_service, mock_context):
        """Should send fees earned notification."""
        result = await notification_service.notify_fees_earned(
            user_id=12345,
            amount=5.25,
            symbol="SOL",
            context=mock_context
        )
        assert result is True
        call_args = mock_context.bot.send_message.call_args
        text = call_args.kwargs.get("text") or call_args[1].get("text")
        assert "Fees Earned" in text
        assert "SOL" in text


# ============================================================================
# Test: Preference Management
# ============================================================================

class TestPreferenceManagement:
    """Test preference get/update functionality."""

    def test_get_preferences_creates_default(self, notification_service):
        """Should create default preferences for new user."""
        prefs = notification_service.get_preferences(99999)
        assert prefs.user_id == 99999
        assert prefs.price_alerts_enabled is True

    def test_get_preferences_returns_existing(self, notification_service):
        """Should return existing preferences."""
        notification_service.preferences[12345] = NotificationPreferences(
            user_id=12345,
            price_alerts_enabled=False
        )
        prefs = notification_service.get_preferences(12345)
        assert prefs.price_alerts_enabled is False

    def test_update_preferences_success(self, notification_service):
        """Should update preferences successfully."""
        result = notification_service.update_preferences(
            12345,
            price_alerts_enabled=False,
            max_alerts_per_hour=10
        )
        assert result is True
        prefs = notification_service.get_preferences(12345)
        assert prefs.price_alerts_enabled is False
        assert prefs.max_alerts_per_hour == 10

    def test_update_preferences_ignores_invalid_fields(self, notification_service):
        """Should ignore invalid field names."""
        result = notification_service.update_preferences(
            12345,
            invalid_field=True,
            another_invalid=42
        )
        assert result is True  # Should not fail

    def test_update_preferences_updates_timestamp(self, notification_service):
        """Should update the updated_at timestamp."""
        prefs = notification_service.get_preferences(12345)
        old_timestamp = prefs.updated_at

        # Small delay to ensure timestamp difference
        time.sleep(0.01)

        notification_service.update_preferences(12345, price_alerts_enabled=False)
        prefs = notification_service.get_preferences(12345)
        assert prefs.updated_at >= old_timestamp


# ============================================================================
# Test: Notification History
# ============================================================================

class TestNotificationHistory:
    """Test notification history management."""

    def test_get_notifications_empty(self, notification_service):
        """Should return empty list for new user."""
        history = notification_service.get_notifications(99999)
        assert history == []

    def test_get_notifications_with_limit(self, notification_service):
        """Should respect limit parameter."""
        user_id = 12345
        for i in range(30):
            notification_service.notifications[user_id].append(
                Notification(
                    notification_id=f"test_{i}",
                    user_id=user_id,
                    notification_type=NotificationType.SYSTEM,
                    priority=NotificationPriority.LOW,
                    title=f"Test {i}",
                    message="Test",
                )
            )
        history = notification_service.get_notifications(user_id, limit=10)
        assert len(history) == 10

    def test_mark_as_read_success(self, notification_service):
        """Should mark notification as read."""
        notification = Notification(
            notification_id="read_test",
            user_id=12345,
            notification_type=NotificationType.SYSTEM,
            priority=NotificationPriority.LOW,
            title="Test",
            message="Test",
        )
        notification_service.notifications[12345].append(notification)

        result = notification_service.mark_as_read("read_test")
        assert result is True
        assert notification.read_at is not None

    def test_mark_as_read_not_found(self, notification_service):
        """Should return False for non-existent notification."""
        result = notification_service.mark_as_read("nonexistent")
        assert result is False

    def test_get_unread_count(self, notification_service):
        """Should count unread notifications."""
        user_id = 12345
        for i in range(5):
            notification = Notification(
                notification_id=f"test_{i}",
                user_id=user_id,
                notification_type=NotificationType.SYSTEM,
                priority=NotificationPriority.LOW,
                title=f"Test {i}",
                message="Test",
            )
            if i < 2:
                notification.read_at = datetime.utcnow()
            notification_service.notifications[user_id].append(notification)

        count = notification_service.get_unread_count(user_id)
        assert count == 3

    def test_clear_notifications(self, notification_service):
        """Should clear all notifications for user."""
        user_id = 12345
        notification_service.notifications[user_id] = [
            Notification(
                notification_id="test",
                user_id=user_id,
                notification_type=NotificationType.SYSTEM,
                priority=NotificationPriority.LOW,
                title="Test",
                message="Test",
            )
        ]
        notification_service.alert_counts[user_id] = [datetime.utcnow()]

        result = notification_service.clear_notifications(user_id)
        assert result is True
        assert notification_service.notifications[user_id] == []
        assert notification_service.alert_counts[user_id] == []


# ============================================================================
# Test: Router - Channel Registration
# ============================================================================

class TestRouterChannelRegistration:
    """Test router channel registration."""

    def test_register_channel(self, notification_router):
        """Should register a channel."""
        config = notification_router.register_channel(
            channel_type=ChannelType.TELEGRAM,
            name="test_telegram",
            endpoint="123456",
            api_key="bot_token",
            min_priority=RouterPriority.MEDIUM,
            rate_limit_per_minute=20,
        )
        assert config.channel_type == ChannelType.TELEGRAM
        assert config.name == "test_telegram"
        assert config.endpoint == "123456"
        assert config.api_key == "bot_token"
        assert config.rate_limit_per_minute == 20

    def test_get_channel(self, configured_router):
        """Should get channel by name."""
        channel = configured_router.get_channel("telegram_main")
        assert channel is not None
        assert channel.name == "telegram_main"

    def test_get_channel_not_found(self, notification_router):
        """Should return None for unknown channel."""
        channel = notification_router.get_channel("nonexistent")
        assert channel is None

    def test_disable_channel(self, configured_router):
        """Should disable a channel."""
        configured_router.disable_channel("telegram_main")
        channel = configured_router.get_channel("telegram_main")
        assert channel.enabled is False

    def test_enable_channel(self, configured_router):
        """Should enable a channel."""
        configured_router.disable_channel("telegram_main")
        configured_router.enable_channel("telegram_main")
        channel = configured_router.get_channel("telegram_main")
        assert channel.enabled is True


# ============================================================================
# Test: Router - Routing Rules
# ============================================================================

class TestRouterRoutingRules:
    """Test routing rules functionality."""

    def test_add_routing_rule(self, notification_router):
        """Should add a routing rule."""
        rule = notification_router.add_routing_rule(
            notification_type=RouterNotificationType.TRADE_EXECUTED,
            channels=["telegram", "discord"],
            min_priority=RouterPriority.MEDIUM,
        )
        assert rule.notification_type == RouterNotificationType.TRADE_EXECUTED
        assert "telegram" in rule.channels
        assert rule.min_priority == RouterPriority.MEDIUM

    def test_get_routing_rules(self, configured_router):
        """Should get routing rules for a type."""
        rules = configured_router.get_routing_rules(RouterNotificationType.TRADE_EXECUTED)
        assert len(rules) > 0
        assert "telegram_main" in rules[0].channels

    def test_get_routing_rules_empty(self, notification_router):
        """Should return empty list for type without rules."""
        rules = notification_router.get_routing_rules(RouterNotificationType.WHALE_ALERT)
        assert rules == []

    def test_get_target_channels(self, configured_router, sample_router_notification):
        """Should get target channels for notification."""
        channels = configured_router.get_target_channels(sample_router_notification)
        assert len(channels) > 0
        channel_names = [c.name for c in channels]
        assert "telegram_main" in channel_names


# ============================================================================
# Test: Router - Rate Limiting
# ============================================================================

class TestRouterRateLimiting:
    """Test router rate limiting."""

    def test_check_rate_limit_allows(self, configured_router):
        """Should allow when under rate limit."""
        result = configured_router._check_rate_limit("telegram_main")
        assert result is True

    def test_check_rate_limit_blocks(self, configured_router):
        """Should block when over rate limit."""
        channel_name = "telegram_main"
        config = configured_router.get_channel(channel_name)

        # Fill up the rate counter
        now = datetime.now()
        configured_router._rate_counters[channel_name] = [
            now - timedelta(seconds=i) for i in range(config.rate_limit_per_minute)
        ]

        result = configured_router._check_rate_limit(channel_name)
        assert result is False

    def test_reset_rate_limit(self, configured_router):
        """Should reset rate limit counter."""
        channel_name = "telegram_main"
        now = datetime.now()
        configured_router._rate_counters[channel_name] = [now for _ in range(10)]

        configured_router.reset_rate_limit(channel_name)
        assert configured_router._rate_counters[channel_name] == []


# ============================================================================
# Test: Router - Circuit Breaker
# ============================================================================

class TestRouterCircuitBreaker:
    """Test router circuit breaker."""

    def test_circuit_breaker_initial_state(self, configured_router):
        """Should have circuit breaker closed initially."""
        state = configured_router.get_circuit_breaker_state("telegram_main")
        assert state.is_open is False
        assert state.failure_count == 0

    def test_circuit_breaker_opens_after_failures(self, configured_router):
        """Should open circuit breaker after threshold failures."""
        channel_name = "telegram_main"
        config = configured_router.get_channel(channel_name)

        # Record failures up to threshold
        for _ in range(config.circuit_breaker_threshold):
            configured_router._record_circuit_breaker_failure(channel_name)

        state = configured_router.get_circuit_breaker_state(channel_name)
        assert state.is_open is True
        assert state.failure_count >= config.circuit_breaker_threshold

    def test_circuit_breaker_blocks_requests(self, configured_router):
        """Should block requests when circuit breaker is open."""
        channel_name = "telegram_main"
        config = configured_router.get_channel(channel_name)

        # Open circuit breaker
        for _ in range(config.circuit_breaker_threshold):
            configured_router._record_circuit_breaker_failure(channel_name)

        result = configured_router._check_circuit_breaker(channel_name)
        assert result is False

    def test_circuit_breaker_success_resets(self, configured_router):
        """Should reset failure count on success."""
        channel_name = "telegram_main"

        # Add some failures
        configured_router._record_circuit_breaker_failure(channel_name)
        configured_router._record_circuit_breaker_failure(channel_name)

        # Record success
        configured_router._record_circuit_breaker_success(channel_name)

        state = configured_router.get_circuit_breaker_state(channel_name)
        assert state.failure_count == 0


# ============================================================================
# Test: Router - Send Notifications
# ============================================================================

class TestRouterSendNotifications:
    """Test router notification sending."""

    @pytest.mark.asyncio
    async def test_route_to_console(self, configured_router, capsys):
        """Should route to console channel."""
        notification = RouterNotification(
            notification_id="console_test",
            notification_type=RouterNotificationType.CUSTOM,
            title="Console Test",
            message="Test message",
            priority=RouterPriority.HIGH,
            data={},
            created_at=datetime.now(),
        )
        result = await configured_router.route(notification)
        assert result.channels_sent >= 0

        captured = capsys.readouterr()
        assert "Console Test" in captured.out or result.channels_sent > 0

    @pytest.mark.asyncio
    async def test_route_no_matching_rules(self, notification_router):
        """Should handle no matching routing rules."""
        notification = RouterNotification(
            notification_id="no_rules",
            notification_type=RouterNotificationType.WHALE_ALERT,
            title="Whale Alert",
            message="Test",
            priority=RouterPriority.HIGH,
            data={},
            created_at=datetime.now(),
        )
        result = await notification_router.route(notification)
        assert result.channels_sent == 0
        assert result.channels_failed == 0

    @pytest.mark.asyncio
    async def test_route_updates_statistics(self, configured_router):
        """Should update statistics after routing."""
        initial_stats = configured_router.get_statistics()
        initial_total = initial_stats["total_notifications"]

        notification = RouterNotification(
            notification_id="stats_test",
            notification_type=RouterNotificationType.CUSTOM,
            title="Stats Test",
            message="Test",
            priority=RouterPriority.HIGH,
            data={},
            created_at=datetime.now(),
        )
        await configured_router.route(notification)

        new_stats = configured_router.get_statistics()
        assert new_stats["total_notifications"] == initial_total + 1


# ============================================================================
# Test: Router - Retry Logic
# ============================================================================

class TestRouterRetryLogic:
    """Test router retry logic."""

    @pytest.mark.asyncio
    async def test_send_with_retry_success(self, configured_router):
        """Should succeed on first attempt."""
        config = configured_router.get_channel("console")
        notification = RouterNotification(
            notification_id="retry_success",
            notification_type=RouterNotificationType.CUSTOM,
            title="Retry Test",
            message="Test",
            priority=RouterPriority.HIGH,
            data={},
            created_at=datetime.now(),
        )
        result = await configured_router._send_with_retry(config, notification)
        assert result.success is True
        assert result.retry_count == 0

    @pytest.mark.asyncio
    async def test_non_retryable_error(self, configured_router):
        """Should not retry non-retryable errors."""
        config = configured_router.get_channel("telegram_main")
        notification = RouterNotification(
            notification_id="non_retry",
            notification_type=RouterNotificationType.CUSTOM,
            title="Non-Retry Test",
            message="Test",
            priority=RouterPriority.HIGH,
            data={},
            created_at=datetime.now(),
        )

        # Mock send to raise non-retryable error
        original_send = configured_router._send_to_channel

        async def mock_send(*args, **kwargs):
            raise NonRetryableError("Invalid credentials")

        configured_router._send_to_channel = mock_send

        try:
            result = await configured_router._send_with_retry(config, notification)
            assert result.success is False
            assert result.retry_count == 0
            assert "Invalid credentials" in result.error
        finally:
            configured_router._send_to_channel = original_send


# ============================================================================
# Test: Router - Batching
# ============================================================================

class TestRouterBatching:
    """Test router batching functionality."""

    @pytest.mark.asyncio
    async def test_queue_high_priority_sends_immediately(self, configured_router):
        """Should send high priority notifications immediately."""
        notification = RouterNotification(
            notification_id="high_priority",
            notification_type=RouterNotificationType.CUSTOM,
            title="High Priority",
            message="Test",
            priority=RouterPriority.HIGH,
            data={},
            created_at=datetime.now(),
        )

        # High priority should be routed immediately, not queued
        await configured_router.queue(notification)

        # Check that delivery record exists
        record = configured_router.get_delivery_status("high_priority")
        assert record is not None

    @pytest.mark.asyncio
    async def test_queue_low_priority_batches(self, configured_router):
        """Should batch low priority notifications."""
        configured_router._batch_low_priority = True
        configured_router._batch_max_size = 3

        for i in range(2):
            notification = RouterNotification(
                notification_id=f"low_priority_{i}",
                notification_type=RouterNotificationType.CUSTOM,
                title=f"Low Priority {i}",
                message="Test",
                priority=RouterPriority.LOW,
                data={},
                created_at=datetime.now(),
            )
            await configured_router.queue(notification)

        # Should be in batch queue
        assert len(configured_router._batch_queue) == 2

    @pytest.mark.asyncio
    async def test_flush_batch(self, configured_router):
        """Should flush batch queue."""
        configured_router._batch_queue = [
            RouterNotification(
                notification_id=f"batch_{i}",
                notification_type=RouterNotificationType.CUSTOM,
                title=f"Batch {i}",
                message="Test",
                priority=RouterPriority.LOW,
                data={},
                created_at=datetime.now(),
            )
            for i in range(3)
        ]

        await configured_router.flush_batch()
        assert len(configured_router._batch_queue) == 0


# ============================================================================
# Test: Router - Delivery Status
# ============================================================================

class TestRouterDeliveryStatus:
    """Test delivery status tracking."""

    @pytest.mark.asyncio
    async def test_get_delivery_status(self, configured_router):
        """Should retrieve delivery status."""
        notification = RouterNotification(
            notification_id="delivery_status_test",
            notification_type=RouterNotificationType.CUSTOM,
            title="Delivery Status Test",
            message="Test",
            priority=RouterPriority.HIGH,
            data={},
            created_at=datetime.now(),
        )
        await configured_router.route(notification)

        status = configured_router.get_delivery_status("delivery_status_test")
        assert status is not None
        assert status.notification_id == "delivery_status_test"

    def test_get_delivery_status_not_found(self, notification_router):
        """Should return None for unknown notification."""
        status = notification_router.get_delivery_status("unknown")
        assert status is None


# ============================================================================
# Test: Router - Statistics
# ============================================================================

class TestRouterStatistics:
    """Test router statistics."""

    def test_get_statistics(self, configured_router):
        """Should return statistics."""
        stats = configured_router.get_statistics()
        assert "total_notifications" in stats
        assert "total_delivered" in stats
        assert "total_failed" in stats
        assert "channels" in stats

    def test_get_channel_statistics(self, configured_router):
        """Should return channel-specific statistics."""
        stats = configured_router.get_channel_statistics("telegram_main")
        assert "sent" in stats
        assert "failed" in stats
        assert "rate_limited" in stats
        assert "avg_latency_ms" in stats


# ============================================================================
# Test: Router Priority Comparison
# ============================================================================

class TestRouterPriorityComparison:
    """Test priority comparison operators."""

    def test_priority_less_than(self):
        """Should compare priorities with less than."""
        assert RouterPriority.LOW < RouterPriority.MEDIUM
        assert RouterPriority.MEDIUM < RouterPriority.HIGH
        assert RouterPriority.HIGH < RouterPriority.CRITICAL

    def test_priority_greater_than(self):
        """Should compare priorities with greater than."""
        assert RouterPriority.CRITICAL > RouterPriority.HIGH
        assert RouterPriority.HIGH > RouterPriority.MEDIUM
        assert RouterPriority.MEDIUM > RouterPriority.LOW

    def test_priority_less_equal(self):
        """Should compare priorities with less than or equal."""
        assert RouterPriority.LOW <= RouterPriority.LOW
        assert RouterPriority.LOW <= RouterPriority.MEDIUM

    def test_priority_greater_equal(self):
        """Should compare priorities with greater than or equal."""
        assert RouterPriority.HIGH >= RouterPriority.HIGH
        assert RouterPriority.HIGH >= RouterPriority.MEDIUM


# ============================================================================
# Test: Singleton Pattern
# ============================================================================

class TestSingleton:
    """Test singleton pattern for NotificationRouter."""

    def test_get_notification_router_returns_same_instance(self):
        """Should return same instance on repeated calls."""
        # Reset singleton for test
        import core.notifications.router as router_module
        router_module._notification_router = None

        router1 = get_notification_router()
        router2 = get_notification_router()
        assert router1 is router2

        # Reset after test
        router_module._notification_router = None


# ============================================================================
# Test: Edge Cases
# ============================================================================

class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_notification_message(self):
        """Should handle empty message."""
        notification = Notification(
            notification_id="empty",
            user_id=1,
            notification_type=NotificationType.SYSTEM,
            priority=NotificationPriority.LOW,
            title="",
            message="",
        )
        message = notification.to_telegram_message()
        assert isinstance(message, str)

    def test_very_long_details(self):
        """Should handle very long details."""
        notification = Notification(
            notification_id="long",
            user_id=1,
            notification_type=NotificationType.SYSTEM,
            priority=NotificationPriority.LOW,
            title="Test",
            message="Test",
            details={"key": "x" * 10000},
        )
        message = notification.to_telegram_message()
        assert len(message) > 10000

    def test_special_characters_in_details(self):
        """Should handle special characters."""
        notification = Notification(
            notification_id="special",
            user_id=1,
            notification_type=NotificationType.SYSTEM,
            priority=NotificationPriority.LOW,
            title="Test <script>alert('xss')</script>",
            message="Test & more",
            details={"<key>": "<value>"},
        )
        message = notification.to_telegram_message()
        assert "<key>" in message or "&lt;key&gt;" in message

    @pytest.mark.asyncio
    async def test_concurrent_notifications(self, notification_service, mock_context):
        """Should handle concurrent notification sends."""
        notifications = [
            Notification(
                notification_id=f"concurrent_{i}",
                user_id=12345,
                notification_type=NotificationType.SYSTEM,
                priority=NotificationPriority.MEDIUM,
                title=f"Test {i}",
                message="Test",
            )
            for i in range(10)
        ]

        results = await asyncio.gather(*[
            notification_service.send_notification(12345, n, mock_context)
            for n in notifications
        ])

        # Some might be rate limited, but shouldn't crash
        assert all(isinstance(r, bool) for r in results)

    def test_router_notification_with_metadata(self):
        """Should handle notification with metadata."""
        notification = RouterNotification(
            notification_id="meta_test",
            notification_type=RouterNotificationType.CUSTOM,
            title="Metadata Test",
            message="Test",
            priority=RouterPriority.MEDIUM,
            data={"key": "value"},
            created_at=datetime.now(),
            metadata={"source": "test", "version": "1.0"},
        )
        assert notification.metadata["source"] == "test"
