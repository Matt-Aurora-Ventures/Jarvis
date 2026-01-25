"""
Tests for browser Telegram handler.

TDD Phase 1: Write failing tests that define expected behavior.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestBrowserTelegramHandler:
    """Tests for browser Telegram command handlers."""

    @pytest.fixture
    def mock_update(self):
        """Create mock Telegram update."""
        update = MagicMock()
        update.effective_user = MagicMock()
        update.effective_user.id = 12345
        update.effective_user.username = "testuser"
        update.message = MagicMock()
        update.message.reply_text = AsyncMock()
        update.message.reply_photo = AsyncMock()
        return update

    @pytest.fixture
    def mock_context(self):
        """Create mock Telegram context."""
        context = MagicMock()
        context.args = []
        context.bot = MagicMock()
        context.bot.send_message = AsyncMock()
        context.bot.send_photo = AsyncMock()
        return context

    @pytest.fixture
    def mock_browser_manager(self):
        """Mock browser manager."""
        with patch("tg_bot.handlers.browser.get_browser_manager") as mock:
            manager = MagicMock()
            manager.start = AsyncMock()
            manager.launch_browser = AsyncMock(return_value="browser-1")
            manager.new_page = AsyncMock(return_value="page-1")
            manager.navigate = AsyncMock()
            manager.click = AsyncMock()
            manager.fill = AsyncMock()
            manager.screenshot = AsyncMock(return_value=b"screenshot_bytes")
            manager.get_content = AsyncMock(return_value="<html>content</html>")
            manager.close_page = AsyncMock()
            manager.close_browser = AsyncMock()
            manager.stop = AsyncMock()
            manager.browsers = {}
            manager.pages = {}
            mock.return_value = manager
            yield manager

    @pytest.mark.asyncio
    async def test_browser_start_firefox(self, mock_update, mock_context, mock_browser_manager):
        """Test /browser start firefox command."""
        from tg_bot.handlers.browser import browser_start

        mock_context.args = ["firefox"]

        await browser_start(mock_update, mock_context)

        mock_browser_manager.start.assert_called_once()
        mock_browser_manager.launch_browser.assert_called_with("firefox", headless=True)
        mock_update.message.reply_text.assert_called()

    @pytest.mark.asyncio
    async def test_browser_start_chrome(self, mock_update, mock_context, mock_browser_manager):
        """Test /browser start chrome command."""
        from tg_bot.handlers.browser import browser_start

        mock_context.args = ["chrome"]

        await browser_start(mock_update, mock_context)

        mock_browser_manager.launch_browser.assert_called_with("chrome", headless=True)

    @pytest.mark.asyncio
    async def test_browser_start_headed(self, mock_update, mock_context, mock_browser_manager):
        """Test /browser start firefox headed command."""
        from tg_bot.handlers.browser import browser_start

        mock_context.args = ["firefox", "headed"]

        await browser_start(mock_update, mock_context)

        mock_browser_manager.launch_browser.assert_called_with("firefox", headless=False)

    @pytest.mark.asyncio
    async def test_browser_navigate(self, mock_update, mock_context, mock_browser_manager):
        """Test /browser navigate <url> command."""
        from tg_bot.handlers.browser import browser_navigate

        mock_context.args = ["https://example.com"]
        mock_browser_manager.pages = {"page-1": MagicMock()}

        await browser_navigate(mock_update, mock_context)

        mock_browser_manager.navigate.assert_called_with("page-1", "https://example.com")
        mock_update.message.reply_text.assert_called()

    @pytest.mark.asyncio
    async def test_browser_navigate_no_session(self, mock_update, mock_context, mock_browser_manager):
        """Test /browser navigate without active session."""
        from tg_bot.handlers.browser import browser_navigate

        mock_context.args = ["https://example.com"]
        mock_browser_manager.pages = {}

        await browser_navigate(mock_update, mock_context)

        # Should reply with error about no active session
        call_args = mock_update.message.reply_text.call_args
        assert "no active" in call_args[0][0].lower() or "start" in call_args[0][0].lower()

    @pytest.mark.asyncio
    async def test_browser_click(self, mock_update, mock_context, mock_browser_manager):
        """Test /browser click <selector> command."""
        from tg_bot.handlers.browser import browser_click

        mock_context.args = ["#submit-button"]
        mock_browser_manager.pages = {"page-1": MagicMock()}

        await browser_click(mock_update, mock_context)

        mock_browser_manager.click.assert_called_with("page-1", "#submit-button")

    @pytest.mark.asyncio
    async def test_browser_fill(self, mock_update, mock_context, mock_browser_manager):
        """Test /browser fill <selector> <text> command."""
        from tg_bot.handlers.browser import browser_fill

        mock_context.args = ["#username", "testuser"]
        mock_browser_manager.pages = {"page-1": MagicMock()}

        await browser_fill(mock_update, mock_context)

        mock_browser_manager.fill.assert_called_with("page-1", "#username", "testuser")

    @pytest.mark.asyncio
    async def test_browser_fill_with_spaces(self, mock_update, mock_context, mock_browser_manager):
        """Test /browser fill with text containing spaces."""
        from tg_bot.handlers.browser import browser_fill

        mock_context.args = ["#message", "hello", "world", "test"]
        mock_browser_manager.pages = {"page-1": MagicMock()}

        await browser_fill(mock_update, mock_context)

        # Should join args after selector
        mock_browser_manager.fill.assert_called_with("page-1", "#message", "hello world test")

    @pytest.mark.asyncio
    async def test_browser_screenshot(self, mock_update, mock_context, mock_browser_manager):
        """Test /browser screenshot command."""
        from tg_bot.handlers.browser import browser_screenshot

        mock_browser_manager.pages = {"page-1": MagicMock()}

        await browser_screenshot(mock_update, mock_context)

        mock_browser_manager.screenshot.assert_called_with("page-1")
        mock_update.message.reply_photo.assert_called()

    @pytest.mark.asyncio
    async def test_browser_html(self, mock_update, mock_context, mock_browser_manager):
        """Test /browser html command."""
        from tg_bot.handlers.browser import browser_html

        mock_browser_manager.pages = {"page-1": MagicMock()}

        await browser_html(mock_update, mock_context)

        mock_browser_manager.get_content.assert_called_with("page-1")
        # Should send HTML content (possibly truncated)
        mock_update.message.reply_text.assert_called()

    @pytest.mark.asyncio
    async def test_browser_close(self, mock_update, mock_context, mock_browser_manager):
        """Test /browser close command."""
        from tg_bot.handlers.browser import browser_close

        mock_browser_manager.browsers = {"browser-1": MagicMock()}
        mock_browser_manager.pages = {"page-1": MagicMock()}

        await browser_close(mock_update, mock_context)

        mock_browser_manager.stop.assert_called_once()
        mock_update.message.reply_text.assert_called()

    @pytest.mark.asyncio
    async def test_browser_status(self, mock_update, mock_context, mock_browser_manager):
        """Test /browser status command."""
        from tg_bot.handlers.browser import browser_status

        mock_browser_manager.browsers = {"browser-1": MagicMock()}
        mock_browser_manager.pages = {"page-1": MagicMock()}

        await browser_status(mock_update, mock_context)

        call_args = mock_update.message.reply_text.call_args
        # Should include browser count and page count
        response = call_args[0][0]
        assert "1" in response  # Should show count

    @pytest.mark.asyncio
    async def test_browser_command_admin_only(self, mock_update, mock_context, mock_browser_manager):
        """Test that browser commands are admin-only."""
        from tg_bot.handlers.browser import browser_start

        # Simulate non-admin user
        with patch("tg_bot.handlers.browser.get_config") as mock_config:
            config = MagicMock()
            config.admin_ids = {99999}  # Different from test user
            config.is_admin = lambda uid, uname=None: uid in config.admin_ids
            mock_config.return_value = config

            await browser_start(mock_update, mock_context)

            # Should have denied access
            call_args = mock_update.message.reply_text.call_args
            response = call_args[0][0]
            assert "unauthorized" in response.lower() or "admin" in response.lower()


class TestBrowserHandlerHelpers:
    """Tests for handler helper functions."""

    def test_parse_browser_type(self):
        """Test parsing browser type argument."""
        from tg_bot.handlers.browser import parse_browser_type

        assert parse_browser_type(["firefox"]) == "firefox"
        assert parse_browser_type(["chrome"]) == "chrome"
        assert parse_browser_type(["chromium"]) == "chrome"
        assert parse_browser_type([]) == "firefox"  # Default
        assert parse_browser_type(["invalid"]) == "firefox"  # Default on invalid

    def test_parse_headless_mode(self):
        """Test parsing headless mode argument."""
        from tg_bot.handlers.browser import parse_headless_mode

        assert parse_headless_mode([]) is True  # Default headless
        assert parse_headless_mode(["firefox"]) is True
        assert parse_headless_mode(["firefox", "headed"]) is False
        assert parse_headless_mode(["firefox", "visible"]) is False
        assert parse_headless_mode(["firefox", "headless"]) is True

    def test_truncate_html(self):
        """Test HTML truncation for Telegram."""
        from tg_bot.handlers.browser import truncate_html

        short_html = "<html><body>Short</body></html>"
        assert truncate_html(short_html, 4096) == short_html

        long_html = "<html>" + "x" * 5000 + "</html>"
        truncated = truncate_html(long_html, 4096)
        assert len(truncated) <= 4096
        assert "truncated" in truncated.lower()


class TestBrowserHandlerIntegration:
    """Integration tests for browser handler."""

    @pytest.fixture
    def mock_update(self):
        """Create mock Telegram update."""
        update = MagicMock()
        update.effective_user = MagicMock()
        update.effective_user.id = 12345
        update.effective_user.username = "testadmin"
        update.message = MagicMock()
        update.message.reply_text = AsyncMock()
        update.message.reply_photo = AsyncMock()
        return update

    @pytest.fixture
    def mock_context(self):
        """Create mock Telegram context."""
        context = MagicMock()
        context.args = []
        return context

    @pytest.mark.asyncio
    async def test_full_session_workflow(self, mock_update, mock_context):
        """Test complete browser session workflow."""
        with patch("tg_bot.handlers.browser.get_browser_manager") as mock_get_manager:
            manager = MagicMock()
            manager.start = AsyncMock()
            manager.launch_browser = AsyncMock(return_value="browser-1")
            manager.new_page = AsyncMock(return_value="page-1")
            manager.navigate = AsyncMock()
            manager.screenshot = AsyncMock(return_value=b"screenshot")
            manager.stop = AsyncMock()
            manager.browsers = {}
            manager.pages = {}
            mock_get_manager.return_value = manager

            from tg_bot.handlers.browser import (
                browser_start,
                browser_navigate,
                browser_screenshot,
                browser_close
            )

            # 1. Start browser
            mock_context.args = ["firefox"]
            await browser_start(mock_update, mock_context)
            manager.browsers = {"browser-1": MagicMock()}
            manager.pages = {"page-1": MagicMock()}

            # 2. Navigate
            mock_context.args = ["https://example.com"]
            await browser_navigate(mock_update, mock_context)

            # 3. Screenshot
            mock_context.args = []
            await browser_screenshot(mock_update, mock_context)

            # 4. Close
            await browser_close(mock_update, mock_context)

            # Verify flow
            manager.start.assert_called()
            manager.launch_browser.assert_called()
            manager.navigate.assert_called()
            manager.screenshot.assert_called()
            manager.stop.assert_called()
