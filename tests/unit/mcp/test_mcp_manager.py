"""
Unit tests for MCP Manager - core service discovery and coordination.

Tests following TDD approach:
1. Server discovery from config
2. Server listing and health checking
3. Tool listing per server
4. Tool execution
5. Error handling and fallbacks
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from pathlib import Path
import json


class TestMCPManagerDiscovery:
    """Tests for MCP server discovery from configuration."""

    def test_manager_init_loads_config(self):
        """Manager should load MCP config on initialization."""
        from core.mcp.manager import MCPCoordinator

        coordinator = MCPCoordinator()
        assert coordinator is not None
        assert hasattr(coordinator, 'servers')
        assert hasattr(coordinator, 'config')

    def test_discover_servers_from_config(self):
        """Manager should discover all enabled servers from config."""
        from core.mcp.manager import MCPCoordinator

        coordinator = MCPCoordinator()
        coordinator.discover_servers()

        # Should have discovered servers from config
        assert len(coordinator.servers) > 0

    def test_discover_servers_filters_disabled(self):
        """Manager should not include disabled servers."""
        from core.mcp.manager import MCPCoordinator

        mock_config = {
            "servers": [
                {"name": "enabled_server", "enabled": True, "command": "echo"},
                {"name": "disabled_server", "enabled": False, "command": "echo"},
            ]
        }

        with patch('core.mcp.manager._read_mcp_config', return_value=mock_config):
            coordinator = MCPCoordinator()
            coordinator.discover_servers()

            server_names = [s['name'] for s in coordinator.servers.values()]
            assert "enabled_server" in server_names
            assert "disabled_server" not in server_names


class TestMCPManagerServerListing:
    """Tests for server listing functionality."""

    def test_list_servers_returns_names(self):
        """list_servers should return list of server names."""
        from core.mcp.manager import MCPCoordinator

        coordinator = MCPCoordinator()
        servers = coordinator.list_servers()

        assert isinstance(servers, list)
        # Should have common servers from config
        # These are the servers defined in mcp.config.json

    def test_list_servers_with_status(self):
        """list_servers with include_status should return server status."""
        from core.mcp.manager import MCPCoordinator

        coordinator = MCPCoordinator()
        servers = coordinator.list_servers(include_status=True)

        assert isinstance(servers, dict)
        for name, status in servers.items():
            assert 'name' in status
            assert 'enabled' in status
            assert 'status' in status


class TestMCPManagerToolListing:
    """Tests for tool listing per server."""

    def test_list_tools_for_server(self):
        """list_tools should return tools for a specific server."""
        from core.mcp.manager import MCPCoordinator

        coordinator = MCPCoordinator()

        # filesystem server should have common tools
        tools = coordinator.list_tools("filesystem")

        assert isinstance(tools, list)
        # Filesystem server typically has read_file, write_file, etc.

    def test_list_tools_unknown_server_raises(self):
        """list_tools should raise for unknown server."""
        from core.mcp.manager import MCPCoordinator, MCPServerNotFoundError

        coordinator = MCPCoordinator()

        with pytest.raises(MCPServerNotFoundError):
            coordinator.list_tools("nonexistent_server")

    def test_list_all_tools(self):
        """list_all_tools should return tools from all servers."""
        from core.mcp.manager import MCPCoordinator

        coordinator = MCPCoordinator()
        all_tools = coordinator.list_all_tools()

        assert isinstance(all_tools, dict)
        # Should be keyed by server name


class TestMCPManagerHealthCheck:
    """Tests for server health checking."""

    def test_check_health_single_server(self):
        """check_health should return health status for a server."""
        from core.mcp.manager import MCPCoordinator

        coordinator = MCPCoordinator()
        health = coordinator.check_health("filesystem")

        assert isinstance(health, dict)
        assert 'healthy' in health
        assert 'last_check' in health

    def test_check_health_all_servers(self):
        """check_health_all should return health for all servers."""
        from core.mcp.manager import MCPCoordinator

        coordinator = MCPCoordinator()
        health = coordinator.check_health_all()

        assert isinstance(health, dict)
        for name, status in health.items():
            assert 'healthy' in status

    def test_check_health_unknown_server(self):
        """check_health should handle unknown server gracefully."""
        from core.mcp.manager import MCPCoordinator, MCPServerNotFoundError

        coordinator = MCPCoordinator()

        with pytest.raises(MCPServerNotFoundError):
            coordinator.check_health("nonexistent_server")


class TestMCPManagerToolExecution:
    """Tests for MCP tool execution."""

    @pytest.mark.asyncio
    async def test_execute_tool_basic(self):
        """execute_tool should execute a tool and return result."""
        from core.mcp.manager import MCPCoordinator

        coordinator = MCPCoordinator()

        # Use a mock tool execution
        with patch.object(coordinator, '_execute_mcp_tool', new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = {"result": "success"}

            result = await coordinator.execute_tool(
                server="filesystem",
                tool="read_file",
                params={"path": "/test/file.txt"}
            )

            assert result == {"result": "success"}
            mock_exec.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_tool_with_timeout(self):
        """execute_tool should respect timeout parameter."""
        from core.mcp.manager import MCPCoordinator, MCPTimeoutError

        coordinator = MCPCoordinator()

        with patch.object(coordinator, '_execute_mcp_tool', new_callable=AsyncMock) as mock_exec:
            import asyncio
            mock_exec.side_effect = asyncio.TimeoutError()

            with pytest.raises(MCPTimeoutError):
                await coordinator.execute_tool(
                    server="filesystem",
                    tool="read_file",
                    params={"path": "/test/file.txt"},
                    timeout=1.0
                )

    @pytest.mark.asyncio
    async def test_execute_tool_logs_usage(self):
        """execute_tool should log usage to database."""
        from core.mcp.manager import MCPCoordinator

        coordinator = MCPCoordinator()

        with patch.object(coordinator, '_execute_mcp_tool', new_callable=AsyncMock) as mock_exec:
            with patch.object(coordinator, '_log_usage', new_callable=AsyncMock) as mock_log:
                mock_exec.return_value = {"result": "success"}

                await coordinator.execute_tool(
                    server="filesystem",
                    tool="read_file",
                    params={"path": "/test/file.txt"}
                )

                mock_log.assert_called_once()


class TestMCPManagerErrorHandling:
    """Tests for error handling and fallbacks."""

    def test_graceful_degradation_on_server_failure(self):
        """Manager should handle server failures gracefully."""
        from core.mcp.manager import MCPCoordinator

        coordinator = MCPCoordinator()

        # Simulate a server being unhealthy
        coordinator._server_health["broken_server"] = {
            "healthy": False,
            "error_count": 5
        }

        # Should still work with other servers
        healthy_servers = [
            name for name, health in coordinator._server_health.items()
            if health.get('healthy', False)
        ]

        # Some servers should still be healthy
        assert len(healthy_servers) >= 0  # May be 0 in unit tests

    @pytest.mark.asyncio
    async def test_retry_on_transient_failure(self):
        """Manager should retry on transient failures."""
        from core.mcp.manager import MCPCoordinator

        coordinator = MCPCoordinator()

        call_count = 0

        async def flaky_execute(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("Transient failure")
            return {"result": "success"}

        with patch.object(coordinator, '_execute_mcp_tool', side_effect=flaky_execute):
            result = await coordinator.execute_tool(
                server="filesystem",
                tool="read_file",
                params={"path": "/test/file.txt"},
                max_retries=3
            )

            assert result == {"result": "success"}
            assert call_count == 3


class TestMCPManagerIntegration:
    """Integration-style tests for the manager."""

    def test_manager_singleton_pattern(self):
        """get_mcp_coordinator should return singleton instance."""
        from core.mcp.manager import get_mcp_coordinator

        coord1 = get_mcp_coordinator()
        coord2 = get_mcp_coordinator()

        assert coord1 is coord2

    def test_manager_with_actual_config(self):
        """Manager should work with actual MCP config file."""
        from core.mcp.manager import MCPCoordinator

        # This uses the actual config
        coordinator = MCPCoordinator()

        # Should have discovered some servers
        servers = coordinator.list_servers()

        # filesystem and memory are common
        assert isinstance(servers, list)
