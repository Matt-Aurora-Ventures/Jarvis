"""
Unit tests for MCP skill helpers.

Tests following TDD approach:
1. mcp_call helper function
2. Integration with skill system
3. Error handling in skills
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch


class TestMCPCallHelper:
    """Tests for mcp_call helper function."""

    @pytest.mark.asyncio
    async def test_mcp_call_basic(self):
        """mcp_call should execute tool and return result."""
        from core.mcp.skill_helpers import mcp_call

        with patch('core.mcp.skill_helpers.get_mcp_coordinator') as mock_coord:
            mock_coordinator = MagicMock()
            mock_coordinator.execute_tool = AsyncMock(return_value={"result": "success"})
            mock_coord.return_value = mock_coordinator

            result = await mcp_call("filesystem", "read_file", path="/test.txt")

            assert result == {"result": "success"}
            mock_coordinator.execute_tool.assert_called_once_with(
                server="filesystem",
                tool="read_file",
                params={"path": "/test.txt"}
            )

    @pytest.mark.asyncio
    async def test_mcp_call_with_timeout(self):
        """mcp_call should support timeout parameter."""
        from core.mcp.skill_helpers import mcp_call

        with patch('core.mcp.skill_helpers.get_mcp_coordinator') as mock_coord:
            mock_coordinator = MagicMock()
            mock_coordinator.execute_tool = AsyncMock(return_value={"result": "success"})
            mock_coord.return_value = mock_coordinator

            await mcp_call("filesystem", "read_file", path="/test.txt", _timeout=30.0)

            mock_coordinator.execute_tool.assert_called_once()
            call_kwargs = mock_coordinator.execute_tool.call_args[1]
            assert call_kwargs.get('timeout') == 30.0 or 'timeout' in str(mock_coordinator.execute_tool.call_args)

    @pytest.mark.asyncio
    async def test_mcp_call_error_handling(self):
        """mcp_call should raise MCPError on failure."""
        from core.mcp.skill_helpers import mcp_call, MCPError

        with patch('core.mcp.skill_helpers.get_mcp_coordinator') as mock_coord:
            mock_coordinator = MagicMock()
            mock_coordinator.execute_tool = AsyncMock(side_effect=Exception("Tool failed"))
            mock_coord.return_value = mock_coordinator

            with pytest.raises(MCPError):
                await mcp_call("filesystem", "read_file", path="/test.txt")


class TestMCPFileHelpers:
    """Tests for file operation helper functions."""

    @pytest.mark.asyncio
    async def test_mcp_read_file(self):
        """mcp_read_file should read file contents."""
        from core.mcp.skill_helpers import mcp_read_file

        with patch('core.mcp.skill_helpers.mcp_call', new_callable=AsyncMock) as mock_call:
            mock_call.return_value = {"content": "file contents"}

            content = await mcp_read_file("/path/to/file.txt")

            assert content == "file contents"
            mock_call.assert_called_once_with("filesystem", "read_file", path="/path/to/file.txt")

    @pytest.mark.asyncio
    async def test_mcp_write_file(self):
        """mcp_write_file should write content to file."""
        from core.mcp.skill_helpers import mcp_write_file

        with patch('core.mcp.skill_helpers.mcp_call', new_callable=AsyncMock) as mock_call:
            mock_call.return_value = {"success": True}

            result = await mcp_write_file("/path/to/file.txt", "new content")

            assert result is True
            mock_call.assert_called_once_with(
                "filesystem", "write_file",
                path="/path/to/file.txt",
                content="new content"
            )

    @pytest.mark.asyncio
    async def test_mcp_list_files(self):
        """mcp_list_files should list directory contents."""
        from core.mcp.skill_helpers import mcp_list_files

        with patch('core.mcp.skill_helpers.mcp_call', new_callable=AsyncMock) as mock_call:
            mock_call.return_value = {"files": ["a.txt", "b.txt"]}

            files = await mcp_list_files("/path/to/dir")

            assert files == ["a.txt", "b.txt"]


class TestMCPGitHelpers:
    """Tests for git operation helper functions."""

    @pytest.mark.asyncio
    async def test_mcp_git_status(self):
        """mcp_git_status should return git status."""
        from core.mcp.skill_helpers import mcp_git_status

        with patch('core.mcp.skill_helpers.mcp_call', new_callable=AsyncMock) as mock_call:
            mock_call.return_value = {
                "modified": ["file1.py"],
                "staged": [],
                "untracked": ["new.txt"]
            }

            status = await mcp_git_status()

            assert status["modified"] == ["file1.py"]

    @pytest.mark.asyncio
    async def test_mcp_git_diff(self):
        """mcp_git_diff should return git diff."""
        from core.mcp.skill_helpers import mcp_git_diff

        with patch('core.mcp.skill_helpers.mcp_call', new_callable=AsyncMock) as mock_call:
            mock_call.return_value = {"diff": "+added line\n-removed line"}

            diff = await mcp_git_diff()

            assert "+added line" in diff


class TestMCPDatabaseHelpers:
    """Tests for database operation helper functions."""

    @pytest.mark.asyncio
    async def test_mcp_query(self):
        """mcp_query should execute SQL query."""
        from core.mcp.skill_helpers import mcp_query

        with patch('core.mcp.skill_helpers.mcp_call', new_callable=AsyncMock) as mock_call:
            mock_call.return_value = {
                "rows": [{"id": 1, "name": "test"}],
                "columns": ["id", "name"]
            }

            result = await mcp_query("SELECT * FROM users")

            assert len(result["rows"]) == 1
            mock_call.assert_called_once()


class TestMCPThinkingHelpers:
    """Tests for thinking operation helper functions."""

    @pytest.mark.asyncio
    async def test_mcp_think_deeply(self):
        """mcp_think_deeply should use sequential-thinking server."""
        from core.mcp.skill_helpers import mcp_think_deeply

        with patch('core.mcp.skill_helpers.mcp_call', new_callable=AsyncMock) as mock_call:
            mock_call.return_value = {
                "steps": [
                    {"step": 1, "thought": "First..."},
                    {"step": 2, "thought": "Then..."},
                ],
                "conclusion": "Therefore..."
            }

            result = await mcp_think_deeply("Complex problem")

            assert "conclusion" in result
            mock_call.assert_called_once()


class TestMCPBrowserHelpers:
    """Tests for browser automation helper functions."""

    @pytest.mark.asyncio
    async def test_mcp_browse(self):
        """mcp_browse should navigate to URL."""
        from core.mcp.skill_helpers import mcp_browse

        with patch('core.mcp.skill_helpers.mcp_call', new_callable=AsyncMock) as mock_call:
            mock_call.return_value = {"success": True, "title": "Example Page"}

            result = await mcp_browse("https://example.com")

            assert result["success"] is True
            mock_call.assert_called_once()

    @pytest.mark.asyncio
    async def test_mcp_screenshot(self):
        """mcp_screenshot should capture page screenshot."""
        from core.mcp.skill_helpers import mcp_screenshot

        with patch('core.mcp.skill_helpers.mcp_call', new_callable=AsyncMock) as mock_call:
            mock_call.return_value = {"data": "base64_image"}

            screenshot = await mcp_screenshot()

            assert screenshot == "base64_image"


class TestMCPMemoryHelpers:
    """Tests for memory/knowledge graph helper functions."""

    @pytest.mark.asyncio
    async def test_mcp_remember(self):
        """mcp_remember should store information in knowledge graph."""
        from core.mcp.skill_helpers import mcp_remember

        with patch('core.mcp.skill_helpers.mcp_call', new_callable=AsyncMock) as mock_call:
            mock_call.return_value = {"id": "entity_123"}

            entity_id = await mcp_remember(
                name="Important Fact",
                entity_type="fact",
                observations=["This is important"]
            )

            assert entity_id == "entity_123"

    @pytest.mark.asyncio
    async def test_mcp_recall(self):
        """mcp_recall should search knowledge graph."""
        from core.mcp.skill_helpers import mcp_recall

        with patch('core.mcp.skill_helpers.mcp_call', new_callable=AsyncMock) as mock_call:
            mock_call.return_value = {
                "nodes": [
                    {"name": "Fact 1", "type": "fact"},
                    {"name": "Fact 2", "type": "fact"},
                ]
            }

            results = await mcp_recall("search query")

            assert len(results) == 2


class TestMCPSkillIntegration:
    """Tests for MCP integration with the skill system."""

    @pytest.mark.asyncio
    async def test_skill_can_use_mcp(self):
        """Skills should be able to use MCP helpers."""
        from core.mcp.skill_helpers import mcp_read_file, mcp_write_file

        # Mock a skill that uses MCP
        async def example_skill():
            # Read a config file via MCP
            with patch('core.mcp.skill_helpers.mcp_call', new_callable=AsyncMock) as mock_call:
                mock_call.return_value = {"content": '{"setting": "value"}'}
                content = await mcp_read_file("/config.json")
                return content

        result = await example_skill()
        assert result == '{"setting": "value"}'

    @pytest.mark.asyncio
    async def test_skill_error_propagation(self):
        """MCP errors should propagate to skills properly."""
        from core.mcp.skill_helpers import mcp_read_file, MCPError

        with patch('core.mcp.skill_helpers.mcp_call', new_callable=AsyncMock) as mock_call:
            mock_call.side_effect = MCPError("File not found")

            with pytest.raises(MCPError):
                await mcp_read_file("/nonexistent.txt")
