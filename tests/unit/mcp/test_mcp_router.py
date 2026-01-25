"""
Unit tests for MCP Router - intelligent request routing.

Tests following TDD approach:
1. Request type detection
2. Server selection
3. Tool matching
4. Fallback strategies
5. Parallel execution
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch


class TestMCPRouterRequestDetection:
    """Tests for request type detection."""

    def test_detect_file_operations(self):
        """Router should detect file operation requests."""
        from core.mcp.router import MCPRouter

        router = MCPRouter()

        # File read operations
        assert router.detect_request_type("read file /path/to/file") == "file_read"
        assert router.detect_request_type("get contents of config.json") == "file_read"

        # File write operations
        assert router.detect_request_type("write to /path/to/file") == "file_write"
        assert router.detect_request_type("save content to file.txt") == "file_write"

    def test_detect_git_operations(self):
        """Router should detect git operation requests."""
        from core.mcp.router import MCPRouter

        router = MCPRouter()

        assert router.detect_request_type("git status") == "git_operation"
        assert router.detect_request_type("show recent commits") == "git_operation"
        assert router.detect_request_type("git diff main") == "git_operation"

    def test_detect_database_operations(self):
        """Router should detect database operation requests."""
        from core.mcp.router import MCPRouter

        router = MCPRouter()

        assert router.detect_request_type("query database") == "database"
        assert router.detect_request_type("SELECT * FROM users") == "database"
        assert router.detect_request_type("run SQL query") == "database"

    def test_detect_thinking_requests(self):
        """Router should detect deep thinking requests."""
        from core.mcp.router import MCPRouter

        router = MCPRouter()

        assert router.detect_request_type("think deeply about this problem") == "thinking"
        assert router.detect_request_type("analyze this complex scenario step by step") == "thinking"

    def test_detect_browser_operations(self):
        """Router should detect browser automation requests."""
        from core.mcp.router import MCPRouter

        router = MCPRouter()

        assert router.detect_request_type("open browser to url") == "browser"
        assert router.detect_request_type("take screenshot of page") == "browser"
        assert router.detect_request_type("click on button") == "browser"


class TestMCPRouterServerSelection:
    """Tests for server selection logic."""

    def test_route_file_to_filesystem(self):
        """File operations should route to filesystem server."""
        from core.mcp.router import MCPRouter

        router = MCPRouter()
        server = router.select_server("file_read", {})

        assert server == "filesystem"

    def test_route_git_to_git_server(self):
        """Git operations should route to git server."""
        from core.mcp.router import MCPRouter

        router = MCPRouter()
        server = router.select_server("git_operation", {})

        assert server == "git"

    def test_route_database_to_sqlite_or_postgres(self):
        """Database operations should route to available db server."""
        from core.mcp.router import MCPRouter

        router = MCPRouter()
        server = router.select_server("database", {})

        assert server in ["sqlite", "postgres"]

    def test_route_thinking_to_sequential_thinking(self):
        """Thinking operations should route to sequential-thinking."""
        from core.mcp.router import MCPRouter

        router = MCPRouter()
        server = router.select_server("thinking", {})

        assert server == "sequential-thinking"

    def test_route_browser_to_puppeteer(self):
        """Browser operations should route to puppeteer."""
        from core.mcp.router import MCPRouter

        router = MCPRouter()
        server = router.select_server("browser", {})

        assert server == "puppeteer"

    def test_route_with_context_override(self):
        """Router should respect context-based overrides."""
        from core.mcp.router import MCPRouter

        router = MCPRouter()

        # Context can force a specific server
        server = router.select_server(
            "file_read",
            {"preferred_server": "memory"}
        )

        assert server == "memory"


class TestMCPRouterToolMatching:
    """Tests for tool matching within servers."""

    def test_match_read_file_tool(self):
        """Router should match read_file tool for file reads."""
        from core.mcp.router import MCPRouter

        router = MCPRouter()
        tool = router.match_tool("filesystem", "file_read", {"path": "/test.txt"})

        assert tool in ["read_file", "readFile"]

    def test_match_write_file_tool(self):
        """Router should match write_file tool for file writes."""
        from core.mcp.router import MCPRouter

        router = MCPRouter()
        tool = router.match_tool("filesystem", "file_write", {"path": "/test.txt", "content": "hello"})

        assert tool in ["write_file", "writeFile"]

    def test_match_git_status_tool(self):
        """Router should match git_status tool."""
        from core.mcp.router import MCPRouter

        router = MCPRouter()
        tool = router.match_tool("git", "git_operation", {"operation": "status"})

        assert tool in ["git_status", "status"]

    def test_match_tool_with_fuzzy_matching(self):
        """Router should use fuzzy matching for tool names."""
        from core.mcp.router import MCPRouter

        router = MCPRouter()

        # Should match even with slightly different naming
        tool = router.match_tool(
            "filesystem",
            "file_read",
            {"path": "/test.txt"},
            fuzzy=True
        )

        assert tool is not None


class TestMCPRouterFallback:
    """Tests for fallback strategies."""

    @pytest.mark.asyncio
    async def test_fallback_on_primary_failure(self):
        """Router should fallback when primary server fails."""
        from core.mcp.router import MCPRouter

        router = MCPRouter()

        # Configure fallback
        router.set_fallback("filesystem", "memory")

        # Simulate primary failure
        with patch.object(router, '_check_server_available') as mock_check:
            mock_check.side_effect = lambda s: s != "filesystem"

            server = router.select_server_with_fallback("file_read", {})

            assert server == "memory"

    @pytest.mark.asyncio
    async def test_no_fallback_available(self):
        """Router should raise when no fallback available."""
        from core.mcp.router import MCPRouter, MCPNoServerAvailableError

        router = MCPRouter()

        with patch.object(router, '_check_server_available', return_value=False):
            with pytest.raises(MCPNoServerAvailableError):
                router.select_server_with_fallback("unknown_type", {})

    def test_get_fallback_chain(self):
        """Router should return fallback chain for a server."""
        from core.mcp.router import MCPRouter

        router = MCPRouter()
        router.set_fallback("filesystem", "memory")
        router.set_fallback("memory", "sqlite")

        chain = router.get_fallback_chain("filesystem")

        assert chain == ["filesystem", "memory", "sqlite"]


class TestMCPRouterParallelExecution:
    """Tests for parallel request execution."""

    @pytest.mark.asyncio
    async def test_execute_parallel_requests(self):
        """Router should execute independent requests in parallel."""
        from core.mcp.router import MCPRouter

        router = MCPRouter()

        requests = [
            {"type": "file_read", "params": {"path": "/a.txt"}},
            {"type": "file_read", "params": {"path": "/b.txt"}},
            {"type": "git_operation", "params": {"operation": "status"}},
        ]

        with patch.object(router, '_route_single_request', new_callable=AsyncMock) as mock_route:
            mock_route.return_value = {"result": "success"}

            results = await router.route_parallel(requests)

            assert len(results) == 3
            assert mock_route.call_count == 3

    @pytest.mark.asyncio
    async def test_parallel_execution_collects_errors(self):
        """Parallel execution should collect errors without stopping."""
        from core.mcp.router import MCPRouter

        router = MCPRouter()

        requests = [
            {"type": "file_read", "params": {"path": "/good.txt"}},
            {"type": "file_read", "params": {"path": "/bad.txt"}},
        ]

        async def mock_route(req):
            if "bad" in req["params"]["path"]:
                raise ValueError("File not found")
            return {"result": "success"}

        with patch.object(router, '_route_single_request', side_effect=mock_route):
            results = await router.route_parallel(requests, collect_errors=True)

            assert len(results) == 2
            assert results[0] == {"result": "success"}
            assert "error" in results[1]


class TestMCPRouterComplete:
    """Complete routing workflow tests."""

    @pytest.mark.asyncio
    async def test_route_request_end_to_end(self):
        """route_request should handle full routing workflow."""
        from core.mcp.router import MCPRouter

        router = MCPRouter()

        with patch.object(router, '_execute_on_server', new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = {"content": "file contents"}

            result = await router.route_request(
                request_type="file_read",
                context={"path": "/test/file.txt"}
            )

            assert result is not None
            mock_exec.assert_called_once()

    @pytest.mark.asyncio
    async def test_route_natural_language_request(self):
        """Router should handle natural language requests."""
        from core.mcp.router import MCPRouter

        router = MCPRouter()

        with patch.object(router, '_execute_on_server', new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = {"result": "done"}

            result = await router.route_request(
                request_type=None,  # Will be auto-detected
                context={"query": "read the contents of config.json"}
            )

            assert result is not None
