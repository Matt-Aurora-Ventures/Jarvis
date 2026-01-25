"""
Unit tests for MCP Telegram handler.

Tests following TDD approach:
1. /mcp servers command
2. /mcp tools command
3. /mcp execute command
4. /mcp health command
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch


class TestMCPTelegramServersCommand:
    """Tests for /mcp servers command."""

    @pytest.mark.asyncio
    async def test_list_servers_command(self):
        """Should list all available MCP servers."""
        from tg_bot.handlers.mcp import handle_mcp_servers

        update = MagicMock()
        update.message = MagicMock()
        update.message.reply_text = AsyncMock()
        update.effective_user.id = 12345

        context = MagicMock()

        with patch('tg_bot.handlers.mcp.get_mcp_coordinator') as mock_coord:
            mock_coordinator = MagicMock()
            mock_coordinator.list_servers.return_value = {
                "filesystem": {"name": "filesystem", "enabled": True, "status": "healthy"},
                "git": {"name": "git", "enabled": True, "status": "healthy"},
            }
            mock_coord.return_value = mock_coordinator

            await handle_mcp_servers(update, context)

            update.message.reply_text.assert_called_once()
            call_args = update.message.reply_text.call_args[0][0]
            assert "filesystem" in call_args
            assert "git" in call_args

    @pytest.mark.asyncio
    async def test_list_servers_empty(self):
        """Should handle case with no servers."""
        from tg_bot.handlers.mcp import handle_mcp_servers

        update = MagicMock()
        update.message = MagicMock()
        update.message.reply_text = AsyncMock()
        update.effective_user.id = 12345

        context = MagicMock()

        with patch('tg_bot.handlers.mcp.get_mcp_coordinator') as mock_coord:
            mock_coordinator = MagicMock()
            mock_coordinator.list_servers.return_value = {}
            mock_coord.return_value = mock_coordinator

            await handle_mcp_servers(update, context)

            update.message.reply_text.assert_called_once()
            call_args = update.message.reply_text.call_args[0][0]
            assert "no servers" in call_args.lower() or "none" in call_args.lower()


class TestMCPTelegramToolsCommand:
    """Tests for /mcp tools command."""

    @pytest.mark.asyncio
    async def test_list_tools_for_server(self):
        """Should list tools for a specific server."""
        from tg_bot.handlers.mcp import handle_mcp_tools

        update = MagicMock()
        update.message = MagicMock()
        update.message.text = "/mcp tools filesystem"
        update.message.reply_text = AsyncMock()
        update.effective_user.id = 12345

        context = MagicMock()
        context.args = ["filesystem"]

        with patch('tg_bot.handlers.mcp.get_mcp_coordinator') as mock_coord:
            mock_coordinator = MagicMock()
            mock_coordinator.list_tools.return_value = [
                "read_file",
                "write_file",
                "list_directory",
            ]
            mock_coord.return_value = mock_coordinator

            await handle_mcp_tools(update, context)

            update.message.reply_text.assert_called_once()
            call_args = update.message.reply_text.call_args[0][0]
            assert "read_file" in call_args
            assert "write_file" in call_args

    @pytest.mark.asyncio
    async def test_list_tools_missing_server_arg(self):
        """Should prompt for server name if missing."""
        from tg_bot.handlers.mcp import handle_mcp_tools

        update = MagicMock()
        update.message = MagicMock()
        update.message.text = "/mcp tools"
        update.message.reply_text = AsyncMock()
        update.effective_user.id = 12345

        context = MagicMock()
        context.args = []

        await handle_mcp_tools(update, context)

        update.message.reply_text.assert_called_once()
        call_args = update.message.reply_text.call_args[0][0]
        assert "usage" in call_args.lower() or "server" in call_args.lower()

    @pytest.mark.asyncio
    async def test_list_tools_unknown_server(self):
        """Should handle unknown server gracefully."""
        from tg_bot.handlers.mcp import handle_mcp_tools
        from core.mcp.manager import MCPServerNotFoundError

        update = MagicMock()
        update.message = MagicMock()
        update.message.text = "/mcp tools nonexistent"
        update.message.reply_text = AsyncMock()
        update.effective_user.id = 12345

        context = MagicMock()
        context.args = ["nonexistent"]

        with patch('tg_bot.handlers.mcp.get_mcp_coordinator') as mock_coord:
            mock_coordinator = MagicMock()
            mock_coordinator.list_tools.side_effect = MCPServerNotFoundError("nonexistent")
            mock_coord.return_value = mock_coordinator

            await handle_mcp_tools(update, context)

            update.message.reply_text.assert_called_once()
            call_args = update.message.reply_text.call_args[0][0]
            assert "not found" in call_args.lower() or "unknown" in call_args.lower()


class TestMCPTelegramExecuteCommand:
    """Tests for /mcp execute command."""

    @pytest.mark.asyncio
    async def test_execute_tool(self):
        """Should execute a tool and return result."""
        from tg_bot.handlers.mcp import handle_mcp_execute

        update = MagicMock()
        update.message = MagicMock()
        update.message.text = '/mcp execute filesystem read_file {"path": "/test.txt"}'
        update.message.reply_text = AsyncMock()
        update.effective_user.id = 12345

        context = MagicMock()
        context.args = ["filesystem", "read_file", '{"path": "/test.txt"}']

        with patch('tg_bot.handlers.mcp.get_mcp_coordinator') as mock_coord:
            mock_coordinator = MagicMock()
            mock_coordinator.execute_tool = AsyncMock(return_value={"content": "file contents"})
            mock_coord.return_value = mock_coordinator

            await handle_mcp_execute(update, context)

            update.message.reply_text.assert_called()
            call_args = update.message.reply_text.call_args[0][0]
            assert "file contents" in call_args or "success" in call_args.lower()

    @pytest.mark.asyncio
    async def test_execute_tool_missing_args(self):
        """Should prompt for missing arguments."""
        from tg_bot.handlers.mcp import handle_mcp_execute

        update = MagicMock()
        update.message = MagicMock()
        update.message.text = "/mcp execute"
        update.message.reply_text = AsyncMock()
        update.effective_user.id = 12345

        context = MagicMock()
        context.args = []

        await handle_mcp_execute(update, context)

        update.message.reply_text.assert_called_once()
        call_args = update.message.reply_text.call_args[0][0]
        assert "usage" in call_args.lower()

    @pytest.mark.asyncio
    async def test_execute_tool_invalid_json(self):
        """Should handle invalid JSON params."""
        from tg_bot.handlers.mcp import handle_mcp_execute

        update = MagicMock()
        update.message = MagicMock()
        update.message.text = "/mcp execute filesystem read_file {invalid json}"
        update.message.reply_text = AsyncMock()
        update.effective_user.id = 12345

        context = MagicMock()
        context.args = ["filesystem", "read_file", "{invalid json}"]

        await handle_mcp_execute(update, context)

        update.message.reply_text.assert_called_once()
        call_args = update.message.reply_text.call_args[0][0]
        assert "json" in call_args.lower() or "invalid" in call_args.lower()

    @pytest.mark.asyncio
    async def test_execute_tool_error(self):
        """Should handle execution errors gracefully."""
        from tg_bot.handlers.mcp import handle_mcp_execute

        update = MagicMock()
        update.message = MagicMock()
        update.message.text = '/mcp execute filesystem read_file {"path": "/nonexistent"}'
        update.message.reply_text = AsyncMock()
        update.effective_user.id = 12345

        context = MagicMock()
        context.args = ["filesystem", "read_file", '{"path": "/nonexistent"}']

        with patch('tg_bot.handlers.mcp.get_mcp_coordinator') as mock_coord:
            mock_coordinator = MagicMock()
            mock_coordinator.execute_tool = AsyncMock(side_effect=Exception("File not found"))
            mock_coord.return_value = mock_coordinator

            await handle_mcp_execute(update, context)

            update.message.reply_text.assert_called()
            call_args = update.message.reply_text.call_args[0][0]
            assert "error" in call_args.lower()


class TestMCPTelegramHealthCommand:
    """Tests for /mcp health command."""

    @pytest.mark.asyncio
    async def test_health_check_all(self):
        """Should show health of all servers."""
        from tg_bot.handlers.mcp import handle_mcp_health

        update = MagicMock()
        update.message = MagicMock()
        update.message.text = "/mcp health"
        update.message.reply_text = AsyncMock()
        update.effective_user.id = 12345

        context = MagicMock()
        context.args = []

        with patch('tg_bot.handlers.mcp.get_mcp_coordinator') as mock_coord:
            mock_coordinator = MagicMock()
            mock_coordinator.check_health_all.return_value = {
                "filesystem": {"healthy": True, "last_check": "2025-01-25T12:00:00"},
                "git": {"healthy": True, "last_check": "2025-01-25T12:00:00"},
                "sqlite": {"healthy": False, "error": "Connection failed"},
            }
            mock_coord.return_value = mock_coordinator

            await handle_mcp_health(update, context)

            update.message.reply_text.assert_called_once()
            call_args = update.message.reply_text.call_args[0][0]
            assert "filesystem" in call_args
            assert "healthy" in call_args.lower() or "ok" in call_args.lower()

    @pytest.mark.asyncio
    async def test_health_check_single_server(self):
        """Should show health of specific server."""
        from tg_bot.handlers.mcp import handle_mcp_health

        update = MagicMock()
        update.message = MagicMock()
        update.message.text = "/mcp health filesystem"
        update.message.reply_text = AsyncMock()
        update.effective_user.id = 12345

        context = MagicMock()
        context.args = ["filesystem"]

        with patch('tg_bot.handlers.mcp.get_mcp_coordinator') as mock_coord:
            mock_coordinator = MagicMock()
            mock_coordinator.check_health.return_value = {
                "healthy": True,
                "last_check": "2025-01-25T12:00:00",
                "response_time_ms": 50
            }
            mock_coord.return_value = mock_coordinator

            await handle_mcp_health(update, context)

            update.message.reply_text.assert_called_once()
            call_args = update.message.reply_text.call_args[0][0]
            assert "filesystem" in call_args.lower()


class TestMCPTelegramAdminOnly:
    """Tests for admin-only access to MCP commands."""

    @pytest.mark.asyncio
    async def test_execute_requires_admin(self):
        """Execute command should require admin access."""
        from tg_bot.handlers.mcp import handle_mcp_execute

        update = MagicMock()
        update.message = MagicMock()
        update.message.text = '/mcp execute filesystem read_file {"path": "/test.txt"}'
        update.message.reply_text = AsyncMock()
        update.effective_user.id = 99999  # Non-admin user

        context = MagicMock()
        context.args = ["filesystem", "read_file", '{"path": "/test.txt"}']

        with patch('tg_bot.handlers.mcp.is_admin', return_value=False):
            await handle_mcp_execute(update, context)

            update.message.reply_text.assert_called_once()
            call_args = update.message.reply_text.call_args[0][0]
            assert "admin" in call_args.lower() or "unauthorized" in call_args.lower()


class TestMCPTelegramMainHandler:
    """Tests for main /mcp command router."""

    @pytest.mark.asyncio
    async def test_mcp_help(self):
        """Should show help when no subcommand given."""
        from tg_bot.handlers.mcp import handle_mcp

        update = MagicMock()
        update.message = MagicMock()
        update.message.text = "/mcp"
        update.message.reply_text = AsyncMock()
        update.effective_user.id = 12345

        context = MagicMock()
        context.args = []

        await handle_mcp(update, context)

        update.message.reply_text.assert_called_once()
        call_args = update.message.reply_text.call_args[0][0]
        assert "servers" in call_args.lower()
        assert "tools" in call_args.lower()
        assert "execute" in call_args.lower()
        assert "health" in call_args.lower()

    @pytest.mark.asyncio
    async def test_mcp_routes_subcommands(self):
        """Should route to appropriate subcommand handler."""
        from tg_bot.handlers.mcp import handle_mcp

        update = MagicMock()
        update.message = MagicMock()
        update.message.text = "/mcp servers"
        update.message.reply_text = AsyncMock()
        update.effective_user.id = 12345

        context = MagicMock()
        context.args = ["servers"]

        with patch('tg_bot.handlers.mcp.handle_mcp_servers', new_callable=AsyncMock) as mock_handler:
            await handle_mcp(update, context)
            mock_handler.assert_called_once()
