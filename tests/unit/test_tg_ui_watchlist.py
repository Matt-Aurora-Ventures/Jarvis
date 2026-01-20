"""
Tests for Telegram UI Watchlist Manager.

Tests cover:
- Add/remove tokens to watchlists
- View watchlist with current prices
- Persistent storage (JSON/SQLite)
- Price alert functionality
"""

import pytest
import tempfile
import json
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime


# =============================================================================
# Test Watchlist Manager Core
# =============================================================================

class TestWatchlistManager:
    """Test core watchlist management functionality."""

    @pytest.fixture
    def temp_storage(self):
        """Create a temporary storage file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({}, f)
            return Path(f.name)

    def test_create_manager(self, temp_storage):
        """Manager should create without errors."""
        from tg_bot.ui.watchlist_manager import WatchlistManager

        manager = WatchlistManager(storage_path=temp_storage)
        assert manager is not None

    def test_add_token_to_watchlist(self, temp_storage):
        """Should add token to user's watchlist."""
        from tg_bot.ui.watchlist_manager import WatchlistManager

        manager = WatchlistManager(storage_path=temp_storage)
        user_id = 12345

        result = manager.add_token(
            user_id=user_id,
            token_address="So11111111111111111111111111111111",
            token_symbol="SOL",
            note="Main position"
        )

        assert result is True
        watchlist = manager.get_watchlist(user_id)
        assert len(watchlist) == 1
        assert watchlist[0]["symbol"] == "SOL"

    def test_add_duplicate_token(self, temp_storage):
        """Adding duplicate token should update, not duplicate."""
        from tg_bot.ui.watchlist_manager import WatchlistManager

        manager = WatchlistManager(storage_path=temp_storage)
        user_id = 12345
        address = "So11111111111111111111111111111111"

        manager.add_token(user_id, address, "SOL")
        manager.add_token(user_id, address, "SOL", note="Updated note")

        watchlist = manager.get_watchlist(user_id)
        assert len(watchlist) == 1
        assert watchlist[0]["note"] == "Updated note"

    def test_remove_token_from_watchlist(self, temp_storage):
        """Should remove token from user's watchlist."""
        from tg_bot.ui.watchlist_manager import WatchlistManager

        manager = WatchlistManager(storage_path=temp_storage)
        user_id = 12345
        address = "So11111111111111111111111111111111"

        manager.add_token(user_id, address, "SOL")
        result = manager.remove_token(user_id, address)

        assert result is True
        watchlist = manager.get_watchlist(user_id)
        assert len(watchlist) == 0

    def test_remove_nonexistent_token(self, temp_storage):
        """Removing nonexistent token should return False."""
        from tg_bot.ui.watchlist_manager import WatchlistManager

        manager = WatchlistManager(storage_path=temp_storage)
        result = manager.remove_token(12345, "nonexistent")

        assert result is False

    def test_clear_watchlist(self, temp_storage):
        """Should clear all tokens from user's watchlist."""
        from tg_bot.ui.watchlist_manager import WatchlistManager

        manager = WatchlistManager(storage_path=temp_storage)
        user_id = 12345

        manager.add_token(user_id, "addr1", "TOK1")
        manager.add_token(user_id, "addr2", "TOK2")
        manager.add_token(user_id, "addr3", "TOK3")

        result = manager.clear_watchlist(user_id)

        assert result is True
        watchlist = manager.get_watchlist(user_id)
        assert len(watchlist) == 0

    def test_get_empty_watchlist(self, temp_storage):
        """Empty watchlist should return empty list."""
        from tg_bot.ui.watchlist_manager import WatchlistManager

        manager = WatchlistManager(storage_path=temp_storage)
        watchlist = manager.get_watchlist(99999)

        assert watchlist == []

    def test_watchlist_limit(self, temp_storage):
        """Watchlist should enforce maximum size."""
        from tg_bot.ui.watchlist_manager import WatchlistManager

        manager = WatchlistManager(storage_path=temp_storage, max_items=5)
        user_id = 12345

        # Add more than max
        for i in range(10):
            manager.add_token(user_id, f"addr{i}", f"TOK{i}")

        watchlist = manager.get_watchlist(user_id)
        assert len(watchlist) <= 5


# =============================================================================
# Test Watchlist Persistence
# =============================================================================

class TestWatchlistPersistence:
    """Test watchlist data persistence."""

    @pytest.fixture
    def temp_storage(self):
        """Create a temporary storage file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({}, f)
            return Path(f.name)

    def test_persist_to_json(self, temp_storage):
        """Data should persist to JSON file."""
        from tg_bot.ui.watchlist_manager import WatchlistManager

        manager = WatchlistManager(storage_path=temp_storage)
        manager.add_token(12345, "addr1", "SOL")

        # Force save
        manager.save()

        # Read file directly
        with open(temp_storage) as f:
            data = json.load(f)

        assert "12345" in data or 12345 in data

    def test_load_from_json(self, temp_storage):
        """Data should load from existing JSON file."""
        from tg_bot.ui.watchlist_manager import WatchlistManager

        # Write directly to file
        initial_data = {
            "12345": {
                "tokens": [
                    {"address": "addr1", "symbol": "SOL", "added_at": "2024-01-01T00:00:00"}
                ]
            }
        }
        with open(temp_storage, 'w') as f:
            json.dump(initial_data, f)

        # Load manager
        manager = WatchlistManager(storage_path=temp_storage)
        watchlist = manager.get_watchlist(12345)

        assert len(watchlist) == 1
        assert watchlist[0]["symbol"] == "SOL"

    def test_corrupt_file_handling(self, temp_storage):
        """Should handle corrupt JSON gracefully."""
        from tg_bot.ui.watchlist_manager import WatchlistManager

        # Write invalid JSON
        with open(temp_storage, 'w') as f:
            f.write("not valid json{{{")

        # Should not raise
        manager = WatchlistManager(storage_path=temp_storage)
        watchlist = manager.get_watchlist(12345)

        assert watchlist == []


# =============================================================================
# Test Price Alerts
# =============================================================================

class TestPriceAlerts:
    """Test price alert functionality."""

    @pytest.fixture
    def temp_storage(self):
        """Create a temporary storage file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({}, f)
            return Path(f.name)

    def test_set_price_alert(self, temp_storage):
        """Should set price alert for a token."""
        from tg_bot.ui.watchlist_manager import WatchlistManager

        manager = WatchlistManager(storage_path=temp_storage)
        user_id = 12345
        address = "So11111111111111111111111111111111"

        manager.add_token(user_id, address, "SOL")
        result = manager.set_price_alert(
            user_id=user_id,
            token_address=address,
            target_price=100.0,
            direction="above"
        )

        assert result is True

        alerts = manager.get_alerts(user_id)
        assert len(alerts) == 1
        assert alerts[0]["target_price"] == 100.0
        assert alerts[0]["direction"] == "above"

    def test_remove_price_alert(self, temp_storage):
        """Should remove price alert."""
        from tg_bot.ui.watchlist_manager import WatchlistManager

        manager = WatchlistManager(storage_path=temp_storage)
        user_id = 12345
        address = "addr1"

        manager.add_token(user_id, address, "SOL")
        manager.set_price_alert(user_id, address, 100.0, "above")

        result = manager.remove_alert(user_id, address)

        assert result is True
        alerts = manager.get_alerts(user_id)
        assert len(alerts) == 0

    def test_check_triggered_alerts(self, temp_storage):
        """Should detect triggered alerts."""
        from tg_bot.ui.watchlist_manager import WatchlistManager

        manager = WatchlistManager(storage_path=temp_storage)
        user_id = 12345

        manager.add_token(user_id, "addr1", "SOL")
        manager.set_price_alert(user_id, "addr1", 100.0, "above")

        manager.add_token(user_id, "addr2", "BONK")
        manager.set_price_alert(user_id, "addr2", 0.00001, "below")

        # Mock current prices
        current_prices = {
            "addr1": 110.0,  # Above 100 - triggered
            "addr2": 0.00002,  # Not below 0.00001 - not triggered
        }

        triggered = manager.check_alerts(user_id, current_prices)

        assert len(triggered) == 1
        assert triggered[0]["token_address"] == "addr1"


# =============================================================================
# Test Watchlist View Formatting
# =============================================================================

class TestWatchlistView:
    """Test watchlist view generation."""

    @pytest.fixture
    def temp_storage(self):
        """Create a temporary storage file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({}, f)
            return Path(f.name)

    def test_format_watchlist_empty(self, temp_storage):
        """Empty watchlist should show appropriate message."""
        from tg_bot.ui.watchlist_manager import WatchlistManager

        manager = WatchlistManager(storage_path=temp_storage)
        formatted = manager.format_watchlist(12345)

        assert "empty" in formatted.lower() or "no tokens" in formatted.lower()

    def test_format_watchlist_with_items(self, temp_storage):
        """Watchlist with items should show token info."""
        from tg_bot.ui.watchlist_manager import WatchlistManager

        manager = WatchlistManager(storage_path=temp_storage)
        user_id = 12345

        manager.add_token(user_id, "addr1", "SOL")
        manager.add_token(user_id, "addr2", "BONK")

        formatted = manager.format_watchlist(user_id)

        assert "SOL" in formatted
        assert "BONK" in formatted

    @pytest.mark.asyncio
    async def test_format_with_prices(self, temp_storage):
        """Watchlist should show current prices when available."""
        from tg_bot.ui.watchlist_manager import WatchlistManager

        manager = WatchlistManager(storage_path=temp_storage)
        user_id = 12345

        manager.add_token(user_id, "addr1", "SOL")

        # Mock price fetcher
        async def mock_fetch_price(address):
            return {"price_usd": 100.0, "change_24h": 5.5}

        formatted = await manager.format_watchlist_with_prices(user_id, mock_fetch_price)

        assert "SOL" in formatted
        assert "100" in formatted or "$100" in formatted
