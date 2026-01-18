"""
Tests for /watchlist command and watchlist management.

Tests cover:
- Watchlist command parsing (add/remove/list)
- Token addition and removal
- Watchlist display with current prices
- Max tokens limit (50 per user)
- Persistence to ~/.lifeos/trading/user_watchlists.json
"""

import pytest
import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def mock_update():
    """Create mock Telegram update."""
    update = MagicMock()
    update.effective_user.id = 12345
    update.effective_chat.id = 67890
    update.message.reply_text = AsyncMock()
    return update


@pytest.fixture
def mock_context():
    """Create mock Telegram context."""
    context = MagicMock()
    context.args = []
    context.bot = MagicMock()
    return context


@pytest.fixture
def temp_watchlist_dir():
    """Create temporary directory for watchlist storage."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def watchlist_manager(temp_watchlist_dir):
    """Create WatchlistManager with temp directory."""
    from tg_bot.handlers.commands.watchlist_command import WatchlistManager
    return WatchlistManager(data_dir=str(temp_watchlist_dir), max_tokens=50)


# =============================================================================
# Test Command Parsing
# =============================================================================

class TestWatchlistCommandParsing:
    """Test /watchlist command parsing."""

    @pytest.mark.asyncio
    async def test_watchlist_no_args_shows_list(self, mock_update, mock_context):
        """Should show watchlist when no args provided."""
        from tg_bot.handlers.commands.watchlist_command import watchlist_command

        mock_context.args = []

        with patch("tg_bot.handlers.commands.watchlist_command.WatchlistManager") as MockManager:
            mock_manager = MockManager.return_value
            mock_manager.get_watchlist.return_value = []

            await watchlist_command(mock_update, mock_context)

            mock_update.message.reply_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_watchlist_add_parses_correctly(self, mock_update, mock_context):
        """Should parse 'add TOKEN' correctly."""
        from tg_bot.handlers.commands.watchlist_command import watchlist_command

        mock_context.args = ["add", "SOL"]

        with patch("tg_bot.handlers.commands.watchlist_command.WatchlistManager") as MockManager:
            mock_manager = MockManager.return_value
            mock_manager.add_token.return_value = True

            await watchlist_command(mock_update, mock_context)

            mock_manager.add_token.assert_called_once()
            call_args = mock_manager.add_token.call_args
            assert "SOL" in str(call_args) or "So11111" in str(call_args)

    @pytest.mark.asyncio
    async def test_watchlist_remove_parses_correctly(self, mock_update, mock_context):
        """Should parse 'remove TOKEN' correctly."""
        from tg_bot.handlers.commands.watchlist_command import watchlist_command

        mock_context.args = ["remove", "SOL"]

        with patch("tg_bot.handlers.commands.watchlist_command.WatchlistManager") as MockManager:
            mock_manager = MockManager.return_value
            mock_manager.remove_token.return_value = True

            await watchlist_command(mock_update, mock_context)

            mock_manager.remove_token.assert_called_once()


# =============================================================================
# Test Watchlist Manager
# =============================================================================

class TestWatchlistManager:
    """Test WatchlistManager operations."""

    def test_add_token(self, watchlist_manager):
        """Should add token to watchlist."""
        result = watchlist_manager.add_token(
            user_id=12345,
            token_address="So11111111111111111111111111111111111111112",
            token_symbol="SOL"
        )

        assert result is True

        watchlist = watchlist_manager.get_watchlist(12345)
        assert len(watchlist) == 1
        assert watchlist[0]["symbol"] == "SOL"

    def test_add_duplicate_token_returns_false(self, watchlist_manager):
        """Should return False when adding duplicate."""
        watchlist_manager.add_token(12345, "address1", "SOL")
        result = watchlist_manager.add_token(12345, "address1", "SOL")

        assert result is False

        watchlist = watchlist_manager.get_watchlist(12345)
        assert len(watchlist) == 1

    def test_remove_token(self, watchlist_manager):
        """Should remove token from watchlist."""
        watchlist_manager.add_token(12345, "address1", "SOL")
        watchlist_manager.add_token(12345, "address2", "BONK")

        result = watchlist_manager.remove_token(12345, "address1")

        assert result is True

        watchlist = watchlist_manager.get_watchlist(12345)
        assert len(watchlist) == 1
        assert watchlist[0]["symbol"] == "BONK"

    def test_remove_nonexistent_returns_false(self, watchlist_manager):
        """Should return False when removing nonexistent token."""
        result = watchlist_manager.remove_token(12345, "nonexistent")
        assert result is False

    def test_max_tokens_limit(self, temp_watchlist_dir):
        """Should enforce max tokens limit."""
        from tg_bot.handlers.commands.watchlist_command import WatchlistManager

        manager = WatchlistManager(data_dir=str(temp_watchlist_dir), max_tokens=5)

        # Add 6 tokens
        for i in range(6):
            manager.add_token(12345, f"address{i}", f"TOKEN{i}")

        watchlist = manager.get_watchlist(12345)
        # Should only have 5 (max), oldest removed
        assert len(watchlist) == 5

    def test_get_watchlist_empty_user(self, watchlist_manager):
        """Should return empty list for new user."""
        watchlist = watchlist_manager.get_watchlist(99999)
        assert watchlist == []

    def test_clear_watchlist(self, watchlist_manager):
        """Should clear all tokens."""
        watchlist_manager.add_token(12345, "address1", "SOL")
        watchlist_manager.add_token(12345, "address2", "BONK")

        watchlist_manager.clear_watchlist(12345)

        watchlist = watchlist_manager.get_watchlist(12345)
        assert len(watchlist) == 0


# =============================================================================
# Test Watchlist Display
# =============================================================================

class TestWatchlistDisplay:
    """Test watchlist display formatting."""

    def test_empty_watchlist_message(self):
        """Should show helpful message for empty watchlist."""
        from tg_bot.handlers.commands.watchlist_command import format_watchlist_display

        message = format_watchlist_display([], {})

        assert "empty" in message.lower() or "no tokens" in message.lower() or "add" in message.lower()

    def test_watchlist_shows_symbols(self, watchlist_manager):
        """Should show token symbols."""
        from tg_bot.handlers.commands.watchlist_command import format_watchlist_display

        watchlist = [
            {"address": "addr1", "symbol": "SOL"},
            {"address": "addr2", "symbol": "BONK"},
        ]

        message = format_watchlist_display(watchlist, {})

        assert "SOL" in message
        assert "BONK" in message

    def test_watchlist_shows_prices_when_available(self, watchlist_manager):
        """Should show current prices when available."""
        from tg_bot.handlers.commands.watchlist_command import format_watchlist_display

        watchlist = [
            {"address": "addr1", "symbol": "SOL"},
        ]

        prices = {
            "addr1": {"price_usd": 150.0, "price_change_24h": 5.0}
        }

        message = format_watchlist_display(watchlist, prices)

        assert "$150" in message or "150" in message

    def test_watchlist_shows_change_indicators(self, watchlist_manager):
        """Should show price change indicators."""
        from tg_bot.handlers.commands.watchlist_command import format_watchlist_display

        watchlist = [
            {"address": "addr1", "symbol": "SOL"},
        ]

        prices = {
            "addr1": {"price_usd": 150.0, "price_change_24h": 5.0}
        }

        message = format_watchlist_display(watchlist, prices)

        # Should have some indicator of price change
        assert "5" in message or "+" in message or "%" in message


# =============================================================================
# Test Persistence
# =============================================================================

class TestWatchlistPersistence:
    """Test watchlist file persistence."""

    def test_watchlist_persisted_to_file(self, temp_watchlist_dir):
        """Watchlist should be saved to file."""
        from tg_bot.handlers.commands.watchlist_command import WatchlistManager

        manager = WatchlistManager(data_dir=str(temp_watchlist_dir))
        manager.add_token(12345, "address1", "SOL")

        # Check file exists
        watchlist_file = temp_watchlist_dir / "12345_watchlist.json"
        assert watchlist_file.exists()

        # Check content
        with open(watchlist_file) as f:
            data = json.load(f)

        assert "tokens" in data
        assert len(data["tokens"]) == 1
        assert data["tokens"][0]["symbol"] == "SOL"

    def test_watchlist_loaded_from_file(self, temp_watchlist_dir):
        """Watchlist should be loaded from existing file."""
        from tg_bot.handlers.commands.watchlist_command import WatchlistManager

        # Create file directly
        watchlist_file = temp_watchlist_dir / "12345_watchlist.json"
        with open(watchlist_file, "w") as f:
            json.dump({
                "tokens": [
                    {"address": "addr1", "symbol": "SOL", "added_at": "2025-01-01T00:00:00Z"}
                ]
            }, f)

        # Load via manager
        manager = WatchlistManager(data_dir=str(temp_watchlist_dir))
        watchlist = manager.get_watchlist(12345)

        assert len(watchlist) == 1
        assert watchlist[0]["symbol"] == "SOL"

    def test_corrupted_file_returns_empty(self, temp_watchlist_dir):
        """Should handle corrupted file gracefully."""
        from tg_bot.handlers.commands.watchlist_command import WatchlistManager

        # Create corrupted file
        watchlist_file = temp_watchlist_dir / "12345_watchlist.json"
        with open(watchlist_file, "w") as f:
            f.write("not valid json{{{")

        manager = WatchlistManager(data_dir=str(temp_watchlist_dir))
        watchlist = manager.get_watchlist(12345)

        assert watchlist == []


# =============================================================================
# Test Watchlist Callbacks
# =============================================================================

class TestWatchlistCallbacks:
    """Test watchlist inline button callbacks."""

    @pytest.mark.asyncio
    async def test_watch_view_callback(self):
        """View callback should show token analysis."""
        from tg_bot.handlers.commands.watchlist_command import handle_watchlist_callback

        query = MagicMock()
        query.data = "watch_view:So11111111111111111111111111111111111111112"
        query.from_user.id = 12345
        query.answer = AsyncMock()
        query.message.edit_text = AsyncMock()

        with patch("tg_bot.services.signal_service.get_signal_service") as mock_service:
            mock_service.return_value.get_comprehensive_signal = AsyncMock()
            await handle_watchlist_callback(query, MagicMock())

            # Should have answered callback
            query.answer.assert_called()

    @pytest.mark.asyncio
    async def test_watch_remove_callback(self):
        """Remove callback should remove token."""
        from tg_bot.handlers.commands.watchlist_command import handle_watchlist_callback

        query = MagicMock()
        query.data = "watch_remove:address1"
        query.from_user.id = 12345
        query.answer = AsyncMock()
        query.message.edit_text = AsyncMock()

        with patch("tg_bot.handlers.commands.watchlist_command.WatchlistManager") as MockManager:
            mock_manager = MockManager.return_value
            mock_manager.remove_token.return_value = True
            mock_manager.get_watchlist.return_value = []

            await handle_watchlist_callback(query, MagicMock())

            mock_manager.remove_token.assert_called_once()

    @pytest.mark.asyncio
    async def test_watch_refresh_callback(self):
        """Refresh callback should update prices."""
        from tg_bot.handlers.commands.watchlist_command import handle_watchlist_callback

        query = MagicMock()
        query.data = "watch_refresh"
        query.from_user.id = 12345
        query.answer = AsyncMock()
        query.message.edit_text = AsyncMock()

        with patch("tg_bot.handlers.commands.watchlist_command.WatchlistManager") as MockManager:
            with patch("tg_bot.handlers.commands.watchlist_command.fetch_current_prices") as mock_fetch:
                mock_manager = MockManager.return_value
                mock_manager.get_watchlist.return_value = [
                    {"address": "addr1", "symbol": "SOL"}
                ]
                mock_fetch.return_value = {"addr1": {"price_usd": 150.0}}

                await handle_watchlist_callback(query, MagicMock())

                # Should have fetched prices
                mock_fetch.assert_called_once()
