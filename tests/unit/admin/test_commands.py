"""
Tests for core/admin/commands.py - Admin command handlers.
"""

import os
from unittest.mock import patch, MagicMock, AsyncMock

import pytest


class TestAdminCommands:
    """Tests for AdminCommands class."""

    def test_admin_commands_init(self):
        """AdminCommands should initialize without error."""
        from core.admin.commands import AdminCommands

        with patch.dict(os.environ, {"ADMIN_USER_IDS": "123456789"}):
            cmds = AdminCommands()
            assert cmds is not None

    def test_admin_commands_has_required_handlers(self):
        """AdminCommands should have all required command handlers."""
        from core.admin.commands import AdminCommands

        with patch.dict(os.environ, {"ADMIN_USER_IDS": "123456789"}):
            cmds = AdminCommands()

            # Check for required methods
            assert hasattr(cmds, "handle_status")
            assert hasattr(cmds, "handle_restart")
            assert hasattr(cmds, "handle_logs")
            assert hasattr(cmds, "handle_cost")
            assert hasattr(cmds, "handle_health")


class TestStatusCommand:
    """Tests for /admin status command."""

    @pytest.mark.asyncio
    async def test_status_command_returns_status(self):
        """Status command should return system status."""
        from core.admin.commands import AdminCommands

        with patch.dict(os.environ, {"ADMIN_USER_IDS": "123456789"}):
            # Clear the admin cache so it reloads
            from core.admin import auth
            auth._admin_user_ids = None

            cmds = AdminCommands()

            with patch("core.admin.commands.get_status") as mock_status:
                mock_status.return_value = {
                    "system": {"cpu": 50, "memory": 60},
                    "bots": {"telegram_bot": "running"},
                    "timestamp": "2025-01-01T00:00:00",
                    "resources": {"cpu_percent": 50, "memory_percent": 60, "disk_percent": 70}
                }

                result = await cmds.handle_status(user_id=123456789)

                assert isinstance(result, (str, dict))

    @pytest.mark.asyncio
    async def test_status_command_requires_admin(self):
        """Status command should reject non-admin users."""
        from core.admin.commands import AdminCommands
        from core.admin.auth import UnauthorizedError

        with patch.dict(os.environ, {"ADMIN_USER_IDS": "123456789"}):
            from core.admin import auth
            auth._admin_user_ids = None

            cmds = AdminCommands()

            with pytest.raises(UnauthorizedError):
                await cmds.handle_status(user_id=999999999)


class TestRestartCommand:
    """Tests for /admin restart command."""

    @pytest.mark.asyncio
    async def test_restart_command_restarts_bot(self):
        """Restart command should trigger bot restart."""
        from core.admin.commands import AdminCommands

        with patch.dict(os.environ, {"ADMIN_USER_IDS": "123456789"}):
            from core.admin import auth
            auth._admin_user_ids = None

            cmds = AdminCommands()

            with patch("core.admin.commands.restart_bot") as mock_restart:
                mock_restart.return_value = {"success": True, "bot": "telegram_bot"}

                result = await cmds.handle_restart(
                    user_id=123456789,
                    bot_name="telegram_bot"
                )

                mock_restart.assert_called_once_with("telegram_bot")
                assert "success" in str(result).lower() or "restart" in str(result).lower()

    @pytest.mark.asyncio
    async def test_restart_command_requires_bot_name(self):
        """Restart command should require a bot name."""
        from core.admin.commands import AdminCommands

        with patch.dict(os.environ, {"ADMIN_USER_IDS": "123456789"}):
            from core.admin import auth
            auth._admin_user_ids = None

            cmds = AdminCommands()

            result = await cmds.handle_restart(user_id=123456789, bot_name="")

            assert "error" in str(result).lower() or "required" in str(result).lower()


class TestLogsCommand:
    """Tests for /admin logs command."""

    @pytest.mark.asyncio
    async def test_logs_command_returns_logs(self):
        """Logs command should return recent logs."""
        from core.admin.commands import AdminCommands

        with patch.dict(os.environ, {"ADMIN_USER_IDS": "123456789"}):
            from core.admin import auth
            auth._admin_user_ids = None

            cmds = AdminCommands()

            with patch("core.admin.commands.get_logs") as mock_logs:
                mock_logs.return_value = "2025-01-01 INFO Starting bot...\n2025-01-01 INFO Bot started."

                result = await cmds.handle_logs(
                    user_id=123456789,
                    bot_name="telegram_bot"
                )

                mock_logs.assert_called()
                assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_logs_command_respects_line_limit(self):
        """Logs command should respect line limit parameter."""
        from core.admin.commands import AdminCommands

        with patch.dict(os.environ, {"ADMIN_USER_IDS": "123456789"}):
            from core.admin import auth
            auth._admin_user_ids = None

            cmds = AdminCommands()

            with patch("core.admin.commands.get_logs") as mock_logs:
                mock_logs.return_value = "Line 1\nLine 2"

                await cmds.handle_logs(
                    user_id=123456789,
                    bot_name="telegram_bot",
                    lines=100
                )

                mock_logs.assert_called_with("telegram_bot", lines=100)


class TestCostCommand:
    """Tests for /admin cost command."""

    @pytest.mark.asyncio
    async def test_cost_command_returns_costs(self):
        """Cost command should return API costs."""
        from core.admin.commands import AdminCommands
        from dataclasses import dataclass

        @dataclass
        class MockSummary:
            total_usd: float = 5.50
            by_provider: dict = None
            by_category: dict = None
            api_calls: int = 100
            total_tokens: int = 50000

            def __post_init__(self):
                if self.by_provider is None:
                    self.by_provider = {"claude": 3.00, "grok": 2.50}
                if self.by_category is None:
                    self.by_category = {"api_call": 5.50}

        with patch.dict(os.environ, {"ADMIN_USER_IDS": "123456789"}):
            from core.admin import auth
            auth._admin_user_ids = None

            cmds = AdminCommands()

            with patch("core.admin.commands.get_cost_tracker") as mock_tracker:
                mock_cost_tracker = MagicMock()
                mock_cost_tracker.get_summary.return_value = MockSummary()
                mock_tracker.return_value = mock_cost_tracker

                result = await cmds.handle_cost(user_id=123456789)

                assert isinstance(result, (str, dict))

    @pytest.mark.asyncio
    async def test_cost_command_formats_currency(self):
        """Cost command should format costs as currency."""
        from core.admin.commands import AdminCommands
        from dataclasses import dataclass

        @dataclass
        class MockSummary:
            total_usd: float = 5.50
            by_provider: dict = None
            by_category: dict = None
            api_calls: int = 50
            total_tokens: int = 25000

            def __post_init__(self):
                if self.by_provider is None:
                    self.by_provider = {"claude": 3.00}
                if self.by_category is None:
                    self.by_category = {}

        with patch.dict(os.environ, {"ADMIN_USER_IDS": "123456789"}):
            from core.admin import auth
            auth._admin_user_ids = None

            cmds = AdminCommands()

            with patch("core.admin.commands.get_cost_tracker") as mock_tracker:
                mock_cost_tracker = MagicMock()
                mock_cost_tracker.get_summary.return_value = MockSummary()
                mock_tracker.return_value = mock_cost_tracker

                result = await cmds.handle_cost(user_id=123456789)

                # Should contain dollar sign or USD
                assert "$" in str(result) or "USD" in str(result) or "5.50" in str(result)


class TestHealthCommand:
    """Tests for /admin health command."""

    @pytest.mark.asyncio
    async def test_health_command_returns_health(self):
        """Health command should return health check results."""
        from core.admin.commands import AdminCommands

        with patch.dict(os.environ, {"ADMIN_USER_IDS": "123456789"}):
            from core.admin import auth
            auth._admin_user_ids = None

            cmds = AdminCommands()

            with patch("core.admin.commands.health_check") as mock_health:
                mock_health.return_value = {
                    "healthy": True,
                    "components": {
                        "database": "ok",
                        "telegram": "ok",
                        "trading": "ok"
                    }
                }

                result = await cmds.handle_health(user_id=123456789)

                mock_health.assert_called_once()
                assert isinstance(result, (str, dict))

    @pytest.mark.asyncio
    async def test_health_command_shows_unhealthy(self):
        """Health command should indicate unhealthy components."""
        from core.admin.commands import AdminCommands

        with patch.dict(os.environ, {"ADMIN_USER_IDS": "123456789"}):
            from core.admin import auth
            auth._admin_user_ids = None

            cmds = AdminCommands()

            with patch("core.admin.commands.health_check") as mock_health:
                mock_health.return_value = {
                    "healthy": False,
                    "components": {
                        "database": "error",
                        "telegram": "ok"
                    }
                }

                result = await cmds.handle_health(user_id=123456789)

                # Should indicate unhealthy state
                result_str = str(result).lower()
                assert "error" in result_str or "unhealthy" in result_str or "fail" in result_str


class TestCommandDispatch:
    """Tests for command dispatching."""

    @pytest.mark.asyncio
    async def test_dispatch_routes_to_correct_handler(self):
        """Dispatch should route commands to correct handlers."""
        from core.admin.commands import AdminCommands

        with patch.dict(os.environ, {"ADMIN_USER_IDS": "123456789"}):
            from core.admin import auth
            auth._admin_user_ids = None

            cmds = AdminCommands()

            # Use AsyncMock for the async handler
            mock_status = AsyncMock(return_value="Status OK")

            # Replace the handler in the command map
            cmds._command_map["status"] = mock_status

            result = await cmds.dispatch(
                user_id=123456789,
                command="status"
            )

            mock_status.assert_called_once()

    @pytest.mark.asyncio
    async def test_dispatch_handles_unknown_command(self):
        """Dispatch should handle unknown commands gracefully."""
        from core.admin.commands import AdminCommands

        with patch.dict(os.environ, {"ADMIN_USER_IDS": "123456789"}):
            from core.admin import auth
            auth._admin_user_ids = None

            cmds = AdminCommands()

            result = await cmds.dispatch(
                user_id=123456789,
                command="nonexistent_command"
            )

            assert "unknown" in str(result).lower() or "invalid" in str(result).lower()
