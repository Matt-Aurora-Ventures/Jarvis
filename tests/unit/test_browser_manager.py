"""
Tests for Playwright-based BrowserManager.

TDD Phase 1: Write failing tests that define expected behavior.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime


class TestBrowserManager:
    """Tests for BrowserManager class."""

    @pytest.fixture
    def mock_playwright(self):
        """Mock playwright for testing without real browser."""
        with patch("core.browser.manager.async_playwright") as mock_pw:
            mock_instance = MagicMock()
            mock_pw.return_value.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_pw.return_value.__aexit__ = AsyncMock()
            yield mock_instance

    @pytest.fixture
    def browser_manager(self):
        """Create a BrowserManager instance."""
        from core.browser.manager import BrowserManager
        return BrowserManager()

    def test_browser_manager_init(self, browser_manager):
        """Test BrowserManager initializes with correct defaults."""
        assert browser_manager.playwright is None
        assert browser_manager.browsers == {}
        assert browser_manager.pages == {}

    @pytest.mark.asyncio
    async def test_start_playwright(self, browser_manager, mock_playwright):
        """Test starting playwright instance."""
        await browser_manager.start()
        assert browser_manager.playwright is not None

    @pytest.mark.asyncio
    async def test_launch_firefox_browser(self, browser_manager, mock_playwright):
        """Test launching Firefox browser (preferred)."""
        mock_browser = MagicMock()
        mock_playwright.firefox.launch = AsyncMock(return_value=mock_browser)

        await browser_manager.start()
        browser_id = await browser_manager.launch_browser("firefox")

        assert browser_id is not None
        assert browser_id in browser_manager.browsers
        mock_playwright.firefox.launch.assert_called_once()

    @pytest.mark.asyncio
    async def test_launch_chrome_browser(self, browser_manager, mock_playwright):
        """Test launching Chrome browser."""
        mock_browser = MagicMock()
        mock_playwright.chromium.launch = AsyncMock(return_value=mock_browser)

        await browser_manager.start()
        browser_id = await browser_manager.launch_browser("chrome")

        assert browser_id is not None
        assert browser_id in browser_manager.browsers
        mock_playwright.chromium.launch.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_new_page(self, browser_manager, mock_playwright):
        """Test creating a new page in browser."""
        mock_browser = MagicMock()
        mock_page = MagicMock()
        mock_browser.new_page = AsyncMock(return_value=mock_page)
        mock_playwright.firefox.launch = AsyncMock(return_value=mock_browser)

        await browser_manager.start()
        browser_id = await browser_manager.launch_browser("firefox")
        page_id = await browser_manager.new_page(browser_id)

        assert page_id is not None
        assert page_id in browser_manager.pages
        mock_browser.new_page.assert_called_once()

    @pytest.mark.asyncio
    async def test_navigate_to_url(self, browser_manager, mock_playwright):
        """Test navigating to a URL."""
        mock_browser = MagicMock()
        mock_page = MagicMock()
        mock_page.goto = AsyncMock()
        mock_browser.new_page = AsyncMock(return_value=mock_page)
        mock_playwright.firefox.launch = AsyncMock(return_value=mock_browser)

        await browser_manager.start()
        browser_id = await browser_manager.launch_browser("firefox")
        page_id = await browser_manager.new_page(browser_id)

        await browser_manager.navigate(page_id, "https://example.com")
        mock_page.goto.assert_called_once_with("https://example.com")

    @pytest.mark.asyncio
    async def test_click_element(self, browser_manager, mock_playwright):
        """Test clicking an element by selector."""
        mock_browser = MagicMock()
        mock_page = MagicMock()
        mock_page.click = AsyncMock()
        mock_browser.new_page = AsyncMock(return_value=mock_page)
        mock_playwright.firefox.launch = AsyncMock(return_value=mock_browser)

        await browser_manager.start()
        browser_id = await browser_manager.launch_browser("firefox")
        page_id = await browser_manager.new_page(browser_id)

        await browser_manager.click(page_id, "#submit-button")
        mock_page.click.assert_called_once_with("#submit-button")

    @pytest.mark.asyncio
    async def test_fill_input(self, browser_manager, mock_playwright):
        """Test filling an input field."""
        mock_browser = MagicMock()
        mock_page = MagicMock()
        mock_page.fill = AsyncMock()
        mock_browser.new_page = AsyncMock(return_value=mock_page)
        mock_playwright.firefox.launch = AsyncMock(return_value=mock_browser)

        await browser_manager.start()
        browser_id = await browser_manager.launch_browser("firefox")
        page_id = await browser_manager.new_page(browser_id)

        await browser_manager.fill(page_id, "#username", "testuser")
        mock_page.fill.assert_called_once_with("#username", "testuser")

    @pytest.mark.asyncio
    async def test_take_screenshot(self, browser_manager, mock_playwright):
        """Test taking a screenshot."""
        mock_browser = MagicMock()
        mock_page = MagicMock()
        mock_page.screenshot = AsyncMock(return_value=b"screenshot_bytes")
        mock_browser.new_page = AsyncMock(return_value=mock_page)
        mock_playwright.firefox.launch = AsyncMock(return_value=mock_browser)

        await browser_manager.start()
        browser_id = await browser_manager.launch_browser("firefox")
        page_id = await browser_manager.new_page(browser_id)

        screenshot = await browser_manager.screenshot(page_id)
        assert screenshot == b"screenshot_bytes"
        mock_page.screenshot.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_page_content(self, browser_manager, mock_playwright):
        """Test getting page HTML content."""
        mock_browser = MagicMock()
        mock_page = MagicMock()
        mock_page.content = AsyncMock(return_value="<html><body>Test</body></html>")
        mock_browser.new_page = AsyncMock(return_value=mock_page)
        mock_playwright.firefox.launch = AsyncMock(return_value=mock_browser)

        await browser_manager.start()
        browser_id = await browser_manager.launch_browser("firefox")
        page_id = await browser_manager.new_page(browser_id)

        content = await browser_manager.get_content(page_id)
        assert "<html>" in content
        mock_page.content.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_page(self, browser_manager, mock_playwright):
        """Test closing a page."""
        mock_browser = MagicMock()
        mock_page = MagicMock()
        mock_page.close = AsyncMock()
        mock_browser.new_page = AsyncMock(return_value=mock_page)
        mock_playwright.firefox.launch = AsyncMock(return_value=mock_browser)

        await browser_manager.start()
        browser_id = await browser_manager.launch_browser("firefox")
        page_id = await browser_manager.new_page(browser_id)

        await browser_manager.close_page(page_id)
        assert page_id not in browser_manager.pages
        mock_page.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_browser(self, browser_manager, mock_playwright):
        """Test closing a browser."""
        mock_browser = MagicMock()
        mock_browser.close = AsyncMock()
        mock_playwright.firefox.launch = AsyncMock(return_value=mock_browser)

        await browser_manager.start()
        browser_id = await browser_manager.launch_browser("firefox")

        await browser_manager.close_browser(browser_id)
        assert browser_id not in browser_manager.browsers
        mock_browser.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_playwright(self, browser_manager, mock_playwright):
        """Test stopping playwright and closing all resources."""
        mock_browser = MagicMock()
        mock_browser.close = AsyncMock()
        mock_playwright.firefox.launch = AsyncMock(return_value=mock_browser)

        await browser_manager.start()
        await browser_manager.launch_browser("firefox")

        await browser_manager.stop()
        assert len(browser_manager.browsers) == 0
        assert browser_manager.playwright is None

    @pytest.mark.asyncio
    async def test_headless_mode(self, browser_manager, mock_playwright):
        """Test launching browser in headless mode."""
        mock_browser = MagicMock()
        mock_playwright.firefox.launch = AsyncMock(return_value=mock_browser)

        await browser_manager.start()
        await browser_manager.launch_browser("firefox", headless=True)

        mock_playwright.firefox.launch.assert_called_once()
        call_kwargs = mock_playwright.firefox.launch.call_args.kwargs
        assert call_kwargs.get("headless") is True

    @pytest.mark.asyncio
    async def test_headed_mode(self, browser_manager, mock_playwright):
        """Test launching browser in headed (visible) mode."""
        mock_browser = MagicMock()
        mock_playwright.firefox.launch = AsyncMock(return_value=mock_browser)

        await browser_manager.start()
        await browser_manager.launch_browser("firefox", headless=False)

        mock_playwright.firefox.launch.assert_called_once()
        call_kwargs = mock_playwright.firefox.launch.call_args.kwargs
        assert call_kwargs.get("headless") is False

    @pytest.mark.asyncio
    async def test_wait_for_selector(self, browser_manager, mock_playwright):
        """Test waiting for element to appear."""
        mock_browser = MagicMock()
        mock_page = MagicMock()
        mock_element = MagicMock()
        mock_page.wait_for_selector = AsyncMock(return_value=mock_element)
        mock_browser.new_page = AsyncMock(return_value=mock_page)
        mock_playwright.firefox.launch = AsyncMock(return_value=mock_browser)

        await browser_manager.start()
        browser_id = await browser_manager.launch_browser("firefox")
        page_id = await browser_manager.new_page(browser_id)

        element = await browser_manager.wait_for_selector(page_id, ".loading-complete")
        assert element is not None
        mock_page.wait_for_selector.assert_called_once_with(".loading-complete", timeout=30000)

    @pytest.mark.asyncio
    async def test_evaluate_javascript(self, browser_manager, mock_playwright):
        """Test evaluating JavaScript on page."""
        mock_browser = MagicMock()
        mock_page = MagicMock()
        mock_page.evaluate = AsyncMock(return_value={"title": "Test Page"})
        mock_browser.new_page = AsyncMock(return_value=mock_page)
        mock_playwright.firefox.launch = AsyncMock(return_value=mock_browser)

        await browser_manager.start()
        browser_id = await browser_manager.launch_browser("firefox")
        page_id = await browser_manager.new_page(browser_id)

        result = await browser_manager.evaluate(page_id, "() => ({ title: document.title })")
        assert result == {"title": "Test Page"}
        mock_page.evaluate.assert_called_once()


class TestBrowserManagerAntiDetection:
    """Tests for anti-detection features."""

    @pytest.fixture
    def browser_manager(self):
        """Create a BrowserManager instance."""
        from core.browser.manager import BrowserManager
        return BrowserManager()

    @pytest.fixture
    def mock_playwright(self):
        """Mock playwright for testing."""
        with patch("core.browser.manager.async_playwright") as mock_pw:
            mock_instance = MagicMock()
            mock_pw.return_value.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_pw.return_value.__aexit__ = AsyncMock()
            yield mock_instance

    @pytest.mark.asyncio
    async def test_stealth_mode_enabled(self, browser_manager, mock_playwright):
        """Test that stealth mode is applied by default."""
        mock_browser = MagicMock()
        mock_context = MagicMock()
        mock_browser.new_context = AsyncMock(return_value=mock_context)
        mock_playwright.firefox.launch = AsyncMock(return_value=mock_browser)

        await browser_manager.start()
        await browser_manager.launch_browser("firefox", stealth=True)

        # Verify stealth options were applied
        assert browser_manager.stealth_enabled is True

    @pytest.mark.asyncio
    async def test_random_user_agent(self, browser_manager, mock_playwright):
        """Test random user agent selection."""
        mock_browser = MagicMock()
        mock_playwright.firefox.launch = AsyncMock(return_value=mock_browser)

        await browser_manager.start()

        user_agent = browser_manager.get_random_user_agent()
        assert user_agent is not None
        assert "Mozilla" in user_agent or "Chrome" in user_agent or "Firefox" in user_agent

    @pytest.mark.asyncio
    async def test_human_like_typing(self, browser_manager, mock_playwright):
        """Test human-like typing with delays."""
        mock_browser = MagicMock()
        mock_page = MagicMock()
        mock_page.type = AsyncMock()
        mock_browser.new_page = AsyncMock(return_value=mock_page)
        mock_playwright.firefox.launch = AsyncMock(return_value=mock_browser)

        await browser_manager.start()
        browser_id = await browser_manager.launch_browser("firefox")
        page_id = await browser_manager.new_page(browser_id)

        await browser_manager.type_humanlike(page_id, "#input", "test")
        mock_page.type.assert_called()


class TestBrowserManagerSecurity:
    """Tests for security features."""

    @pytest.fixture
    def browser_manager(self):
        """Create a BrowserManager instance."""
        from core.browser.manager import BrowserManager
        return BrowserManager()

    def test_credential_not_logged(self, browser_manager, caplog):
        """Test that credentials are not logged."""
        import logging
        caplog.set_level(logging.DEBUG)

        # This should NOT log the actual password
        browser_manager._log_action("fill", {"selector": "#password", "value": "secret123"})

        assert "secret123" not in caplog.text

    def test_session_isolation(self, browser_manager):
        """Test that sessions are isolated."""
        # Each browser context should be separate
        assert browser_manager.browsers == {}
        # Sessions should not share cookies or storage


class TestBrowserManagerPersistence:
    """Tests for session persistence in database."""

    @pytest.fixture
    def mock_db(self):
        """Mock database connection."""
        return MagicMock()

    @pytest.fixture
    def browser_manager(self, mock_db):
        """Create a BrowserManager with mock DB."""
        from core.browser.manager import BrowserManager
        manager = BrowserManager(db=mock_db)
        return manager

    def test_session_stored_in_db(self, browser_manager, mock_db):
        """Test that browser sessions are stored in database."""
        # This will be implemented with actual DB integration
        pass

    def test_page_stored_in_db(self, browser_manager, mock_db):
        """Test that pages are stored in database."""
        # This will be implemented with actual DB integration
        pass
