"""
Unit tests for MCP Service Wrappers.

Tests following TDD approach:
1. Typed interfaces for each service
2. Error handling
3. Logging
4. Caching
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch


class TestFilesystemService:
    """Tests for filesystem MCP service wrapper."""

    @pytest.mark.asyncio
    async def test_read_file(self):
        """read_file should return file contents."""
        from core.mcp.services.filesystem import FilesystemService

        service = FilesystemService()

        with patch.object(service, '_call_mcp', new_callable=AsyncMock) as mock_call:
            mock_call.return_value = {"content": "file contents"}

            result = await service.read_file("/path/to/file.txt")

            assert result == "file contents"
            mock_call.assert_called_once()

    @pytest.mark.asyncio
    async def test_write_file(self):
        """write_file should write content to file."""
        from core.mcp.services.filesystem import FilesystemService

        service = FilesystemService()

        with patch.object(service, '_call_mcp', new_callable=AsyncMock) as mock_call:
            mock_call.return_value = {"success": True}

            result = await service.write_file("/path/to/file.txt", "new content")

            assert result is True
            mock_call.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_directory(self):
        """list_directory should return directory contents."""
        from core.mcp.services.filesystem import FilesystemService

        service = FilesystemService()

        with patch.object(service, '_call_mcp', new_callable=AsyncMock) as mock_call:
            mock_call.return_value = {"files": ["a.txt", "b.txt"]}

            result = await service.list_directory("/path/to/dir")

            assert result == ["a.txt", "b.txt"]

    @pytest.mark.asyncio
    async def test_read_file_not_found(self):
        """read_file should raise FileNotFoundError for missing files."""
        from core.mcp.services.filesystem import FilesystemService, MCPFileNotFoundError

        service = FilesystemService()

        with patch.object(service, '_call_mcp', new_callable=AsyncMock) as mock_call:
            mock_call.side_effect = Exception("File not found")

            with pytest.raises(MCPFileNotFoundError):
                await service.read_file("/nonexistent/file.txt")


class TestGitService:
    """Tests for git MCP service wrapper."""

    @pytest.mark.asyncio
    async def test_get_status(self):
        """get_status should return git status."""
        from core.mcp.services.git import GitService

        service = GitService()

        with patch.object(service, '_call_mcp', new_callable=AsyncMock) as mock_call:
            mock_call.return_value = {
                "modified": ["file1.py"],
                "staged": [],
                "untracked": ["new_file.txt"]
            }

            status = await service.get_status()

            assert status.modified == ["file1.py"]
            assert status.untracked == ["new_file.txt"]

    @pytest.mark.asyncio
    async def test_get_log(self):
        """get_log should return commit history."""
        from core.mcp.services.git import GitService

        service = GitService()

        with patch.object(service, '_call_mcp', new_callable=AsyncMock) as mock_call:
            mock_call.return_value = {
                "commits": [
                    {"hash": "abc123", "message": "Initial commit"},
                    {"hash": "def456", "message": "Add feature"},
                ]
            }

            log = await service.get_log(limit=2)

            assert len(log) == 2
            assert log[0].hash == "abc123"

    @pytest.mark.asyncio
    async def test_get_diff(self):
        """get_diff should return file diffs."""
        from core.mcp.services.git import GitService

        service = GitService()

        with patch.object(service, '_call_mcp', new_callable=AsyncMock) as mock_call:
            mock_call.return_value = {
                "diff": "+added line\n-removed line"
            }

            diff = await service.get_diff()

            assert "+added line" in diff


class TestSQLiteService:
    """Tests for SQLite MCP service wrapper."""

    @pytest.mark.asyncio
    async def test_execute_query(self):
        """execute_query should run SQL and return results."""
        from core.mcp.services.sqlite import SQLiteService

        service = SQLiteService()

        with patch.object(service, '_call_mcp', new_callable=AsyncMock) as mock_call:
            mock_call.return_value = {
                "rows": [{"id": 1, "name": "test"}],
                "columns": ["id", "name"]
            }

            result = await service.execute_query("SELECT * FROM users")

            assert len(result.rows) == 1
            assert result.rows[0]["name"] == "test"

    @pytest.mark.asyncio
    async def test_execute_query_with_params(self):
        """execute_query should support parameterized queries."""
        from core.mcp.services.sqlite import SQLiteService

        service = SQLiteService()

        with patch.object(service, '_call_mcp', new_callable=AsyncMock) as mock_call:
            mock_call.return_value = {"rows": [], "columns": []}

            await service.execute_query(
                "SELECT * FROM users WHERE id = ?",
                params=[1]
            )

            mock_call.assert_called_once()


class TestMemoryService:
    """Tests for memory/knowledge graph MCP service wrapper."""

    @pytest.mark.asyncio
    async def test_create_entity(self):
        """create_entity should add entity to knowledge graph."""
        from core.mcp.services.memory import MemoryService

        service = MemoryService()

        with patch.object(service, '_call_mcp', new_callable=AsyncMock) as mock_call:
            mock_call.return_value = {"id": "entity_123"}

            entity_id = await service.create_entity(
                name="Test Entity",
                entity_type="concept",
                observations=["observation 1"]
            )

            assert entity_id == "entity_123"

    @pytest.mark.asyncio
    async def test_search_nodes(self):
        """search_nodes should find matching entities."""
        from core.mcp.services.memory import MemoryService

        service = MemoryService()

        with patch.object(service, '_call_mcp', new_callable=AsyncMock) as mock_call:
            mock_call.return_value = {
                "nodes": [
                    {"name": "Entity A", "type": "concept"},
                    {"name": "Entity B", "type": "concept"},
                ]
            }

            results = await service.search_nodes("test query")

            assert len(results) == 2

    @pytest.mark.asyncio
    async def test_add_relation(self):
        """add_relation should create relation between entities."""
        from core.mcp.services.memory import MemoryService

        service = MemoryService()

        with patch.object(service, '_call_mcp', new_callable=AsyncMock) as mock_call:
            mock_call.return_value = {"success": True}

            result = await service.add_relation(
                from_entity="entity_1",
                to_entity="entity_2",
                relation_type="relates_to"
            )

            assert result is True


class TestSequentialThinkingService:
    """Tests for sequential-thinking MCP service wrapper."""

    @pytest.mark.asyncio
    async def test_think(self):
        """think should return step-by-step reasoning."""
        from core.mcp.services.thinking import SequentialThinkingService

        service = SequentialThinkingService()

        with patch.object(service, '_call_mcp', new_callable=AsyncMock) as mock_call:
            mock_call.return_value = {
                "steps": [
                    {"step": 1, "thought": "First, consider..."},
                    {"step": 2, "thought": "Then, analyze..."},
                ],
                "conclusion": "Therefore..."
            }

            result = await service.think("Complex problem to solve")

            assert len(result.steps) == 2
            assert result.conclusion == "Therefore..."


class TestPuppeteerService:
    """Tests for puppeteer MCP service wrapper."""

    @pytest.mark.asyncio
    async def test_navigate(self):
        """navigate should load a URL."""
        from core.mcp.services.puppeteer import PuppeteerService

        service = PuppeteerService()

        with patch.object(service, '_call_mcp', new_callable=AsyncMock) as mock_call:
            mock_call.return_value = {"success": True, "title": "Test Page"}

            result = await service.navigate("https://example.com")

            assert result.success is True
            assert result.title == "Test Page"

    @pytest.mark.asyncio
    async def test_screenshot(self):
        """screenshot should capture page image."""
        from core.mcp.services.puppeteer import PuppeteerService

        service = PuppeteerService()

        with patch.object(service, '_call_mcp', new_callable=AsyncMock) as mock_call:
            mock_call.return_value = {"data": "base64_image_data"}

            screenshot = await service.screenshot()

            assert screenshot == "base64_image_data"

    @pytest.mark.asyncio
    async def test_click_element(self):
        """click should interact with page elements."""
        from core.mcp.services.puppeteer import PuppeteerService

        service = PuppeteerService()

        with patch.object(service, '_call_mcp', new_callable=AsyncMock) as mock_call:
            mock_call.return_value = {"clicked": True}

            result = await service.click("button#submit")

            assert result is True


class TestYouTubeTranscriptService:
    """Tests for youtube-transcript MCP service wrapper."""

    @pytest.mark.asyncio
    async def test_get_transcript(self):
        """get_transcript should return video transcript."""
        from core.mcp.services.youtube import YouTubeTranscriptService

        service = YouTubeTranscriptService()

        with patch.object(service, '_call_mcp', new_callable=AsyncMock) as mock_call:
            mock_call.return_value = {
                "transcript": [
                    {"text": "Hello world", "start": 0.0, "duration": 2.0},
                    {"text": "Welcome to the video", "start": 2.0, "duration": 3.0},
                ]
            }

            transcript = await service.get_transcript("video_id_123")

            assert len(transcript) == 2
            assert transcript[0].text == "Hello world"


class TestServiceCaching:
    """Tests for service-level caching."""

    @pytest.mark.asyncio
    async def test_cached_response(self):
        """Service should cache responses when enabled."""
        from core.mcp.services.filesystem import FilesystemService

        service = FilesystemService(cache_enabled=True)

        with patch.object(service, '_call_mcp', new_callable=AsyncMock) as mock_call:
            mock_call.return_value = {"content": "file contents"}

            # First call
            result1 = await service.read_file("/path/to/file.txt")
            # Second call (should be cached)
            result2 = await service.read_file("/path/to/file.txt")

            assert result1 == result2
            # Should only call MCP once due to caching
            assert mock_call.call_count == 1

    @pytest.mark.asyncio
    async def test_cache_invalidation(self):
        """Service should invalidate cache on write operations."""
        from core.mcp.services.filesystem import FilesystemService

        service = FilesystemService(cache_enabled=True)

        with patch.object(service, '_call_mcp', new_callable=AsyncMock) as mock_call:
            mock_call.return_value = {"content": "file contents"}

            # Read file (cached)
            await service.read_file("/path/to/file.txt")

            # Write invalidates cache
            mock_call.return_value = {"success": True}
            await service.write_file("/path/to/file.txt", "new content")

            # Read again (should call MCP again)
            mock_call.return_value = {"content": "new content"}
            await service.read_file("/path/to/file.txt")

            # Should have called MCP 3 times (read, write, read)
            assert mock_call.call_count == 3


class TestServiceLogging:
    """Tests for service-level logging."""

    @pytest.mark.asyncio
    async def test_logs_operations(self):
        """Service should log all operations."""
        from core.mcp.services.filesystem import FilesystemService
        import logging

        service = FilesystemService()

        with patch.object(service, '_call_mcp', new_callable=AsyncMock) as mock_call:
            mock_call.return_value = {"content": "file contents"}

            with patch('core.mcp.services.filesystem.logger') as mock_logger:
                await service.read_file("/path/to/file.txt")

                # Should have logged the operation
                assert mock_logger.debug.called or mock_logger.info.called
