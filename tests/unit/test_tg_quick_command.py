"""
Tests for quick command handler (/quick or /q).
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from telegram import Update, User, Chat, Message, CallbackQuery, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from tg_bot.handlers.commands.quick_command import (
    quick_command,
    handle_quick_callback,
    _quick_market_summary,
    _quick_alerts,
)


@pytest.fixture
def mock_config():
    """Mock config."""
    with patch('tg_bot.handlers.commands.quick_command.get_config') as mock:
        config = Mock()
        config.is_admin = Mock(return_value=True)
        mock.return_value = config
        yield config


@pytest.fixture
def mock_update():
    """Mock update object."""
    update = Mock(spec=Update)
    update.effective_user = Mock(spec=User)
    update.effective_user.id = 123456
    update.effective_chat = Mock(spec=Chat)
    update.effective_chat.id = 123456
    update.message = Mock(spec=Message)
    update.message.reply_text = AsyncMock()
    update.message.chat_id = 123456
    update.message.message_id = 1
    return update


@pytest.fixture
def mock_context():
    """Mock context object."""
    return Mock(spec=ContextTypes.DEFAULT_TYPE)


class TestQuickCommand:
    """Test suite for quick command."""

    @pytest.mark.asyncio
    async def test_quick_command_admin(self, mock_update, mock_context, mock_config):
        """Test /quick command for admin user."""
        mock_config.is_admin.return_value = True

        await quick_command(mock_update, mock_context)

        # Verify reply was sent
        mock_update.message.reply_text.assert_called_once()
        call_args = mock_update.message.reply_text.call_args

        # Check message content
        message = call_args[0][0]
        assert "QUICK ACCESS" in message
        assert "tap what you need" in message

        # Check keyboard markup was included
        assert 'reply_markup' in call_args[1]
        keyboard = call_args[1]['reply_markup']
        assert isinstance(keyboard, InlineKeyboardMarkup)

        # Admin should have more buttons
        buttons = keyboard.inline_keyboard
        assert len(buttons) >= 5  # At least 5 rows for admin

    @pytest.mark.asyncio
    async def test_quick_command_non_admin(self, mock_update, mock_context, mock_config):
        """Test /quick command for non-admin user."""
        mock_config.is_admin.return_value = False

        await quick_command(mock_update, mock_context)

        # Verify reply was sent
        mock_update.message.reply_text.assert_called_once()
        call_args = mock_update.message.reply_text.call_args

        # Check message content
        message = call_args[0][0]
        assert "QUICK ACCESS" in message
        assert "admin commands locked" in message

        # Non-admin should have fewer buttons
        keyboard = call_args[1]['reply_markup']
        buttons = keyboard.inline_keyboard
        assert len(buttons) < 5  # Fewer rows for non-admin

    @pytest.mark.asyncio
    async def test_quick_command_keyboard_structure(self, mock_update, mock_context, mock_config):
        """Test that keyboard has correct structure."""
        await quick_command(mock_update, mock_context)

        call_args = mock_update.message.reply_text.call_args
        keyboard = call_args[1]['reply_markup']
        buttons = keyboard.inline_keyboard

        # Check that positions and balance are in first row
        first_row = buttons[0]
        assert len(first_row) == 2
        assert "Positions" in first_row[0].text
        assert "Balance" in first_row[1].text

        # Check last row has full menu button
        last_row = buttons[-1]
        assert len(last_row) == 1
        assert "Full Menu" in last_row[0].text


class TestQuickCallbacks:
    """Test suite for quick command callbacks."""

    @pytest.fixture
    def mock_callback_update(self):
        """Mock callback query update."""
        update = Mock(spec=Update)
        update.update_id = 1
        update.effective_user = Mock(spec=User)
        update.effective_user.id = 123456
        update.effective_chat = Mock(spec=Chat)
        update.effective_chat.id = 123456

        query = Mock(spec=CallbackQuery)
        query.answer = AsyncMock()
        query.message = Mock(spec=Message)
        query.message.reply_text = AsyncMock()
        query.message.chat_id = 123456
        query.message.message_id = 1
        query.data = "quick_positions"

        update.callback_query = query
        return update

    @pytest.mark.asyncio
    async def test_handle_quick_positions_callback(self, mock_callback_update, mock_context):
        """Test positions callback."""
        mock_callback_update.callback_query.data = "quick_positions"

        with patch('tg_bot.handlers.treasury.handle_portfolio') as mock_handler:
            mock_handler.return_value = AsyncMock()

            await handle_quick_callback(mock_callback_update, mock_context)

            # Verify callback was answered
            mock_callback_update.callback_query.answer.assert_called_once()

            # Verify portfolio handler was called
            mock_handler.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_quick_balance_callback(self, mock_callback_update, mock_context):
        """Test balance callback."""
        mock_callback_update.callback_query.data = "quick_balance"

        with patch('tg_bot.handlers.treasury.handle_balance') as mock_handler:
            mock_handler.return_value = AsyncMock()

            await handle_quick_callback(mock_callback_update, mock_context)

            mock_callback_update.callback_query.answer.assert_called_once()
            mock_handler.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_quick_wallet_callback(self, mock_callback_update, mock_context):
        """Test wallet callback."""
        mock_callback_update.callback_query.data = "quick_wallet"

        with patch('tg_bot.handlers.trading.wallet') as mock_wallet:
            mock_wallet.return_value = AsyncMock()

            await handle_quick_callback(mock_callback_update, mock_context)

            mock_callback_update.callback_query.answer.assert_called_once()
            mock_wallet.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_quick_health_callback(self, mock_callback_update, mock_context):
        """Test health callback."""
        mock_callback_update.callback_query.data = "quick_health"

        with patch('tg_bot.handlers.system.health') as mock_health:
            mock_health.return_value = AsyncMock()

            await handle_quick_callback(mock_callback_update, mock_context)

            mock_callback_update.callback_query.answer.assert_called_once()
            mock_health.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_quick_full_menu_callback(self, mock_callback_update, mock_context):
        """Test full menu callback."""
        mock_callback_update.callback_query.data = "quick_full_menu"

        with patch('tg_bot.handlers.commands_base.start') as mock_start:
            mock_start.return_value = AsyncMock()

            await handle_quick_callback(mock_callback_update, mock_context)

            mock_callback_update.callback_query.answer.assert_called_once()
            mock_start.assert_called_once()


class TestQuickMarketSummary:
    """Test suite for quick market summary helper."""

    @pytest.fixture
    def mock_query(self):
        """Mock callback query."""
        query = Mock(spec=CallbackQuery)
        query.message = Mock(spec=Message)
        query.message.reply_text = AsyncMock()
        return query

    @pytest.mark.asyncio
    async def test_quick_market_summary_with_data(self, mock_query, mock_context):
        """Test market summary with trending data."""
        mock_service = Mock()
        mock_service.get_trending_tokens = Mock(return_value=[
            {
                'symbol': 'SOL',
                'price': 100.50,
                'price_change_24h': 5.25,
            },
            {
                'symbol': 'BONK',
                'price': 0.000012,
                'price_change_24h': -2.50,
            },
        ])

        with patch('tg_bot.services.signal_service.get_signal_service', return_value=mock_service):
            await _quick_market_summary(mock_query, mock_context)

            mock_query.message.reply_text.assert_called_once()
            call_args = mock_query.message.reply_text.call_args
            message = call_args[0][0]

            assert "Quick Market Check" in message
            assert "SOL" in message
            assert "BONK" in message
            assert "$100.5" in message or "$100.50" in message

    @pytest.mark.asyncio
    async def test_quick_market_summary_no_data(self, mock_query, mock_context):
        """Test market summary with no trending data."""
        mock_service = Mock()
        mock_service.get_trending_tokens = Mock(return_value=[])

        with patch('tg_bot.services.signal_service.get_signal_service', return_value=mock_service):
            await _quick_market_summary(mock_query, mock_context)

            mock_query.message.reply_text.assert_called_once()
            call_args = mock_query.message.reply_text.call_args
            message = call_args[0][0]

            assert "no trending data available" in message

    @pytest.mark.asyncio
    async def test_quick_market_summary_error(self, mock_query, mock_context):
        """Test market summary error handling."""
        mock_service = Mock()
        mock_service.get_trending_tokens = Mock(side_effect=Exception("API Error"))

        with patch('tg_bot.services.signal_service.get_signal_service', return_value=mock_service):
            await _quick_market_summary(mock_query, mock_context)

            mock_query.message.reply_text.assert_called_once()
            call_args = mock_query.message.reply_text.call_args
            message = call_args[0][0]

            assert "Market data unavailable" in message


class TestQuickAlerts:
    """Test suite for quick alerts helper."""

    @pytest.fixture
    def mock_query(self):
        """Mock callback query."""
        query = Mock(spec=CallbackQuery)
        query.message = Mock(spec=Message)
        query.message.reply_text = AsyncMock()
        return query

    @pytest.mark.asyncio
    async def test_quick_alerts_with_data(self, mock_query, mock_context, tmp_path):
        """Test alerts with exit intents data."""
        # Create mock exit intents file
        exit_intents_data = {
            "SOL": {
                "reason": "Take profit target reached",
                "timestamp": "2026-01-19T10:00:00",
            },
            "BONK": {
                "reason": "Stop loss triggered",
                "timestamp": "2026-01-19T11:00:00",
            },
        }

        import json
        exit_intents_path = tmp_path / ".lifeos" / "trading" / "exit_intents.json"
        exit_intents_path.parent.mkdir(parents=True, exist_ok=True)
        with open(exit_intents_path, 'w') as f:
            json.dump(exit_intents_data, f)

        with patch('pathlib.Path.home', return_value=tmp_path):
            await _quick_alerts(mock_query, mock_context)

            mock_query.message.reply_text.assert_called_once()
            call_args = mock_query.message.reply_text.call_args
            message = call_args[0][0]

            assert "Active Alerts" in message
            assert "SOL" in message
            assert "BONK" in message

    @pytest.mark.asyncio
    async def test_quick_alerts_no_data(self, mock_query, mock_context, tmp_path):
        """Test alerts with no data."""
        with patch('pathlib.Path.home', return_value=tmp_path):
            await _quick_alerts(mock_query, mock_context)

            mock_query.message.reply_text.assert_called_once()
            call_args = mock_query.message.reply_text.call_args
            message = call_args[0][0]

            assert "no active alerts" in message

    @pytest.mark.asyncio
    async def test_quick_alerts_error(self, mock_query, mock_context):
        """Test alerts error handling."""
        with patch('pathlib.Path.home', side_effect=Exception("Path error")):
            await _quick_alerts(mock_query, mock_context)

            mock_query.message.reply_text.assert_called_once()
            call_args = mock_query.message.reply_text.call_args
            message = call_args[0][0]

            assert "Alerts unavailable" in message
