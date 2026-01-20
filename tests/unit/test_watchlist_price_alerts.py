"""
Tests for Watchlist Price Alert Integration.

Tests cover:
- Creating price alerts via /watchlist alert command
- Listing active alerts via /watchlist alerts
- Quick /watch and /unwatch commands
- Integration with core price_alerts system
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch, call
from telegram import Update, Message, User, Chat
from telegram.ext import ContextTypes


# =============================================================================
# Test /watch and /unwatch Commands
# =============================================================================

class TestWatchCommands:
    """Test quick watch/unwatch commands."""

    @pytest.fixture
    def mock_update(self):
        """Create a mock Telegram Update object."""
        update = MagicMock(spec=Update)
        update.message = MagicMock(spec=Message)
        update.message.reply_text = AsyncMock()
        update.effective_user = MagicMock(spec=User)
        update.effective_user.id = 12345
        return update

    @pytest.fixture
    def mock_context(self):
        """Create a mock Context object."""
        context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
        context.args = []
        return context

    @pytest.mark.asyncio
    async def test_watch_command_adds_token(self, mock_update, mock_context):
        """Should add token to watchlist via /watch."""
        from tg_bot.handlers.commands.watchlist_command import watch_command

        mock_context.args = ["SOL"]

        with patch("tg_bot.handlers.commands.watchlist_command.WatchlistManager") as MockManager:
            manager = MockManager.return_value
            manager.add_token.return_value = True

            await watch_command(mock_update, mock_context)

            manager.add_token.assert_called_once_with(
                12345,
                "So11111111111111111111111111111111111111112",
                "SOL"
            )

            mock_update.message.reply_text.assert_called_once()
            call_args = mock_update.message.reply_text.call_args
            assert "Added" in call_args[0][0]
            assert "SOL" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_watch_command_no_args(self, mock_update, mock_context):
        """Should show usage when no args provided."""
        from tg_bot.handlers.commands.watchlist_command import watch_command

        mock_context.args = []

        await watch_command(mock_update, mock_context)

        mock_update.message.reply_text.assert_called_once()
        call_args = mock_update.message.reply_text.call_args
        assert "Usage" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_unwatch_command_removes_token(self, mock_update, mock_context):
        """Should remove token from watchlist via /unwatch."""
        from tg_bot.handlers.commands.watchlist_command import unwatch_command

        mock_context.args = ["SOL"]

        with patch("tg_bot.handlers.commands.watchlist_command.WatchlistManager") as MockManager:
            manager = MockManager.return_value
            manager.remove_token.return_value = True

            await unwatch_command(mock_update, mock_context)

            manager.remove_token.assert_called_once_with(
                12345,
                "So11111111111111111111111111111111111111112"
            )

            mock_update.message.reply_text.assert_called_once()
            call_args = mock_update.message.reply_text.call_args
            assert "Removed" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_unwatch_token_not_found(self, mock_update, mock_context):
        """Should notify when token not in watchlist."""
        from tg_bot.handlers.commands.watchlist_command import unwatch_command

        mock_context.args = ["NOTFOUND"]

        with patch("tg_bot.handlers.commands.watchlist_command.WatchlistManager") as MockManager:
            manager = MockManager.return_value
            manager.remove_token.return_value = False

            await unwatch_command(mock_update, mock_context)

            mock_update.message.reply_text.assert_called_once()
            call_args = mock_update.message.reply_text.call_args
            assert "not on your watchlist" in call_args[0][0]


# =============================================================================
# Test Price Alert Commands
# =============================================================================

class TestPriceAlerts:
    """Test price alert integration."""

    @pytest.fixture
    def mock_update(self):
        """Create a mock Telegram Update object."""
        update = MagicMock(spec=Update)
        update.message = MagicMock(spec=Message)
        update.message.reply_text = AsyncMock()
        update.effective_user = MagicMock(spec=User)
        update.effective_user.id = 12345
        return update

    @pytest.fixture
    def mock_context(self):
        """Create a mock Context object."""
        context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
        context.args = []
        return context

    @pytest.mark.asyncio
    async def test_set_price_alert_above(self, mock_update, mock_context):
        """Should create price alert via /watchlist alert."""
        from tg_bot.handlers.commands.watchlist_command import watchlist_command

        mock_context.args = ["alert", "SOL", "100", "above"]

        with patch("tg_bot.handlers.commands.watchlist_command.create_price_alert") as mock_create:
            mock_alert = MagicMock()
            mock_alert.id = "abc123"
            mock_create.return_value = mock_alert

            await watchlist_command(mock_update, mock_context)

            mock_create.assert_called_once()
            call_args = mock_create.call_args

            assert call_args.kwargs["token_symbol"] == "SOL"
            assert call_args.kwargs["threshold"] == 100.0
            assert "ABOVE" in str(call_args.kwargs["alert_type"])

            mock_update.message.reply_text.assert_called_once()
            reply_text = mock_update.message.reply_text.call_args[0][0]
            assert "Alert set" in reply_text
            assert "100" in reply_text

    @pytest.mark.asyncio
    async def test_set_price_alert_below(self, mock_update, mock_context):
        """Should create below-price alert."""
        from tg_bot.handlers.commands.watchlist_command import watchlist_command

        mock_context.args = ["alert", "BONK", "0.00001", "below"]

        with patch("tg_bot.handlers.commands.watchlist_command.create_price_alert") as mock_create:
            mock_alert = MagicMock()
            mock_alert.id = "xyz789"
            mock_create.return_value = mock_alert

            await watchlist_command(mock_update, mock_context)

            call_args = mock_create.call_args
            assert call_args.kwargs["threshold"] == 0.00001
            assert "BELOW" in str(call_args.kwargs["alert_type"])

    @pytest.mark.asyncio
    async def test_alert_invalid_price(self, mock_update, mock_context):
        """Should handle invalid price gracefully."""
        from tg_bot.handlers.commands.watchlist_command import watchlist_command

        mock_context.args = ["alert", "SOL", "notanumber", "above"]

        await watchlist_command(mock_update, mock_context)

        mock_update.message.reply_text.assert_called_once()
        reply_text = mock_update.message.reply_text.call_args[0][0]
        assert "Invalid price" in reply_text

    @pytest.mark.asyncio
    async def test_alert_missing_args(self, mock_update, mock_context):
        """Should show usage when args missing."""
        from tg_bot.handlers.commands.watchlist_command import watchlist_command

        mock_context.args = ["alert", "SOL"]  # Missing price and direction

        await watchlist_command(mock_update, mock_context)

        mock_update.message.reply_text.assert_called_once()
        reply_text = mock_update.message.reply_text.call_args[0][0]
        assert "Usage" in reply_text

    @pytest.mark.asyncio
    async def test_list_active_alerts(self, mock_update, mock_context):
        """Should list active price alerts."""
        from tg_bot.handlers.commands.watchlist_command import watchlist_command

        mock_context.args = ["alerts"]

        with patch("tg_bot.handlers.commands.watchlist_command.get_alert_manager") as mock_get_mgr:
            mock_mgr = MagicMock()

            # Mock alerts
            mock_alert1 = MagicMock()
            mock_alert1.token_symbol = "SOL"
            mock_alert1.alert_type.value = "price_above"
            mock_alert1.threshold = 100.0
            mock_alert1.id = "abc123"

            mock_alert2 = MagicMock()
            mock_alert2.token_symbol = "BONK"
            mock_alert2.alert_type.value = "price_below"
            mock_alert2.threshold = 0.00001
            mock_alert2.id = "xyz789"

            mock_mgr.list_alerts.return_value = [mock_alert1, mock_alert2]
            mock_get_mgr.return_value = mock_mgr

            await watchlist_command(mock_update, mock_context)

            mock_update.message.reply_text.assert_called_once()
            reply_text = mock_update.message.reply_text.call_args[0][0]

            assert "SOL" in reply_text
            assert "BONK" in reply_text
            assert "100" in reply_text
            assert "above" in reply_text
            assert "below" in reply_text

    @pytest.mark.asyncio
    async def test_list_alerts_empty(self, mock_update, mock_context):
        """Should show message when no alerts active."""
        from tg_bot.handlers.commands.watchlist_command import watchlist_command

        mock_context.args = ["alerts"]

        with patch("tg_bot.handlers.commands.watchlist_command.get_alert_manager") as mock_get_mgr:
            mock_mgr = MagicMock()
            mock_mgr.list_alerts.return_value = []
            mock_get_mgr.return_value = mock_mgr

            await watchlist_command(mock_update, mock_context)

            mock_update.message.reply_text.assert_called_once()
            reply_text = mock_update.message.reply_text.call_args[0][0]
            assert "No active alerts" in reply_text


# =============================================================================
# Test Integration with Core Alert System
# =============================================================================

class TestAlertSystemIntegration:
    """Test integration between watchlist and core price_alerts."""

    @pytest.mark.asyncio
    async def test_alert_creates_with_correct_type(self):
        """Alert should use correct AlertType based on direction."""
        from core.price_alerts import AlertType, create_price_alert

        # Above alert
        alert_above = create_price_alert(
            token_symbol="SOL",
            token_mint="So11111111111111111111111111111111111111112",
            alert_type=AlertType.PRICE_ABOVE,
            threshold=100.0,
            note="Test alert",
        )

        assert alert_above.alert_type == AlertType.PRICE_ABOVE
        assert alert_above.threshold == 100.0

        # Below alert
        alert_below = create_price_alert(
            token_symbol="BONK",
            token_mint="DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",
            alert_type=AlertType.PRICE_BELOW,
            threshold=0.00001,
            note="Test alert",
        )

        assert alert_below.alert_type == AlertType.PRICE_BELOW

    def test_alert_manager_singleton(self):
        """Alert manager should be a singleton."""
        from core.price_alerts import get_alert_manager

        mgr1 = get_alert_manager()
        mgr2 = get_alert_manager()

        assert mgr1 is mgr2
