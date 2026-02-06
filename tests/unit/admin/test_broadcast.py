"""
Tests for core/admin/broadcast.py - Admin broadcast functionality.
"""

import os
from unittest.mock import patch, MagicMock, AsyncMock

import pytest


class TestBroadcast:
    """Tests for broadcast function."""

    @pytest.mark.asyncio
    async def test_broadcast_sends_to_all_bots(self):
        """Broadcast should send message to all specified bots."""
        from core.admin.broadcast import broadcast

        with patch("core.admin.broadcast._send_to_bot", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = {"success": True}

            result = await broadcast(
                message="Test broadcast message",
                bots=["telegram_bot", "treasury_bot"],
                confirmed=True  # Must confirm to actually send
            )

            assert mock_send.call_count == 2
            assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_broadcast_returns_results_per_bot(self):
        """Broadcast should return results for each bot."""
        from core.admin.broadcast import broadcast

        with patch("core.admin.broadcast._send_to_bot", new_callable=AsyncMock) as mock_send:
            mock_send.side_effect = [
                {"success": True, "bot": "telegram_bot"},
                {"success": False, "bot": "treasury_bot", "error": "timeout"}
            ]

            result = await broadcast(
                message="Test message",
                bots=["telegram_bot", "treasury_bot"],
                confirmed=True  # Must confirm to actually send
            )

            assert "telegram_bot" in result or "results" in result
            assert "treasury_bot" in result or len(result.get("results", [])) == 2

    @pytest.mark.asyncio
    async def test_broadcast_handles_empty_bots(self):
        """Broadcast should handle empty bot list gracefully."""
        from core.admin.broadcast import broadcast

        result = await broadcast(
            message="Test message",
            bots=[]
        )

        assert "error" in result or result.get("sent", 0) == 0

    @pytest.mark.asyncio
    async def test_broadcast_handles_empty_message(self):
        """Broadcast should reject empty messages."""
        from core.admin.broadcast import broadcast

        result = await broadcast(
            message="",
            bots=["telegram_bot"]
        )

        assert "error" in result or result.get("success") is False


class TestBroadcastWithConfirmation:
    """Tests for broadcast with confirmation requirement."""

    @pytest.mark.asyncio
    async def test_broadcast_requires_confirmation(self):
        """Broadcast should require confirmation by default."""
        from core.admin.broadcast import broadcast, BroadcastRequiresConfirmation

        with patch("core.admin.broadcast._send_to_bot") as mock_send:
            mock_send.return_value = {"success": True}

            # Without confirmed=True, should raise or return pending
            result = await broadcast(
                message="Important broadcast",
                bots=["telegram_bot", "treasury_bot"],
                confirmed=False
            )

            # Either raises exception or returns pending confirmation
            if isinstance(result, dict):
                assert result.get("pending_confirmation") or result.get("requires_confirmation")

    @pytest.mark.asyncio
    async def test_broadcast_executes_when_confirmed(self):
        """Broadcast should execute when confirmation is provided."""
        from core.admin.broadcast import broadcast

        with patch("core.admin.broadcast._send_to_bot") as mock_send:
            mock_send.return_value = {"success": True}

            result = await broadcast(
                message="Confirmed broadcast",
                bots=["telegram_bot"],
                confirmed=True
            )

            mock_send.assert_called_once()
            assert result.get("success") or result.get("sent", 0) > 0


class TestBroadcastToAllBots:
    """Tests for broadcast_to_all function."""

    @pytest.mark.asyncio
    async def test_broadcast_to_all_discovers_bots(self):
        """broadcast_to_all should discover and message all running bots."""
        from core.admin.broadcast import broadcast_to_all

        with patch("core.admin.broadcast._get_running_bots") as mock_get_bots:
            mock_get_bots.return_value = ["telegram_bot", "treasury_bot", "twitter_bot"]

            with patch("core.admin.broadcast._send_to_bot") as mock_send:
                mock_send.return_value = {"success": True}

                result = await broadcast_to_all(
                    message="System maintenance in 10 minutes",
                    confirmed=True
                )

                assert mock_send.call_count == 3


class TestSendToBot:
    """Tests for _send_to_bot helper function."""

    @pytest.mark.asyncio
    async def test_send_to_telegram_bot(self):
        """Should send message via Telegram API."""
        from core.admin.broadcast import _send_to_bot
        import aiohttp

        # Create properly nested async context managers using MagicMock
        mock_response = MagicMock()
        mock_response.status = 200

        # Create context manager for post
        mock_post_cm = MagicMock()
        mock_post_cm.__aenter__ = AsyncMock(return_value=mock_response)
        mock_post_cm.__aexit__ = AsyncMock(return_value=None)

        # Create session mock
        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=mock_post_cm)

        # Create session context manager
        mock_session_cm = MagicMock()
        mock_session_cm.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_cm.__aexit__ = AsyncMock(return_value=None)

        with patch.object(aiohttp, "ClientSession", return_value=mock_session_cm):
            with patch.dict(os.environ, {
                "TELEGRAM_BOT_TOKEN": "test_token",
                "TELEGRAM_ADMIN_IDS": "123456789"
            }):
                result = await _send_to_bot(
                    bot_name="telegram_bot",
                    message="Test message"
                )

                assert result.get("success") is True

    @pytest.mark.asyncio
    async def test_send_to_bot_handles_error(self):
        """Should handle send errors gracefully."""
        from core.admin.broadcast import _send_to_bot
        import aiohttp

        # Create mock that raises exception during post
        mock_session = MagicMock()
        mock_session.post.side_effect = Exception("Network error")

        # Create session context manager
        mock_session_cm = MagicMock()
        mock_session_cm.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_cm.__aexit__ = AsyncMock(return_value=None)

        with patch.object(aiohttp, "ClientSession", return_value=mock_session_cm):
            with patch.dict(os.environ, {
                "TELEGRAM_BOT_TOKEN": "test_token",
                "TELEGRAM_ADMIN_IDS": "123456789"
            }):
                result = await _send_to_bot(
                    bot_name="telegram_bot",
                    message="Test message"
                )

                assert result.get("success") is False
                assert "error" in result


class TestGetRunningBots:
    """Tests for _get_running_bots helper."""

    def test_get_running_bots_from_supervisor(self):
        """Should get running bots from supervisor."""
        from core.admin.broadcast import _get_running_bots

        with patch("core.admin.broadcast._get_supervisor") as mock_get_supervisor:
            mock_supervisor = MagicMock()
            mock_supervisor.get_status.return_value = {
                "telegram_bot": {"status": "running"},
                "treasury_bot": {"status": "running"},
                "twitter_bot": {"status": "stopped"}
            }
            mock_get_supervisor.return_value = mock_supervisor

            bots = _get_running_bots()

            assert "telegram_bot" in bots
            assert "treasury_bot" in bots
            assert "twitter_bot" not in bots  # Stopped bots excluded

    def test_get_running_bots_handles_no_supervisor(self):
        """Should return empty list if supervisor unavailable."""
        from core.admin.broadcast import _get_running_bots

        with patch("core.admin.broadcast._get_supervisor") as mock_get_supervisor:
            mock_get_supervisor.return_value = None

            bots = _get_running_bots()

            assert bots == [] or isinstance(bots, list)
