"""
Tests for browser automation flows.

TDD Phase 1: Write failing tests that define expected behavior.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestAutomationFlows:
    """Tests for AutomationFlows class."""

    @pytest.fixture
    def mock_browser_manager(self):
        """Mock BrowserManager for testing."""
        manager = MagicMock()
        manager.start = AsyncMock()
        manager.launch_browser = AsyncMock(return_value="browser-1")
        manager.new_page = AsyncMock(return_value="page-1")
        manager.navigate = AsyncMock()
        manager.click = AsyncMock()
        manager.fill = AsyncMock()
        manager.wait_for_selector = AsyncMock()
        manager.screenshot = AsyncMock(return_value=b"screenshot")
        manager.get_content = AsyncMock(return_value="<html></html>")
        manager.close_page = AsyncMock()
        manager.close_browser = AsyncMock()
        manager.stop = AsyncMock()
        return manager

    @pytest.fixture
    def automation_flows(self, mock_browser_manager):
        """Create AutomationFlows instance with mock manager."""
        from core.browser.flows import AutomationFlows
        flows = AutomationFlows(browser_manager=mock_browser_manager)
        return flows

    @pytest.mark.asyncio
    async def test_gmail_login_flow(self, automation_flows, mock_browser_manager):
        """Test Gmail login automation flow."""
        # Setup mock responses
        mock_browser_manager.wait_for_selector.return_value = MagicMock()

        result = await automation_flows.gmail_login("test@gmail.com", "password123")

        assert result["success"] is True
        mock_browser_manager.navigate.assert_called()
        # Verify email field was filled
        mock_browser_manager.fill.assert_any_call("page-1", 'input[type="email"]', "test@gmail.com")

    @pytest.mark.asyncio
    async def test_gmail_login_with_2fa(self, automation_flows, mock_browser_manager):
        """Test Gmail login with 2FA detection."""
        # Simulate 2FA screen appearing
        mock_browser_manager.wait_for_selector.side_effect = [
            MagicMock(),  # email field
            MagicMock(),  # password field
            MagicMock(),  # 2FA prompt
        ]

        result = await automation_flows.gmail_login(
            "test@gmail.com",
            "password123",
            handle_2fa=True
        )

        assert "requires_2fa" in result or result["success"] is True

    @pytest.mark.asyncio
    async def test_drive_login_flow(self, automation_flows, mock_browser_manager):
        """Test Google Drive login automation flow."""
        mock_browser_manager.wait_for_selector.return_value = MagicMock()

        result = await automation_flows.drive_login("test@gmail.com", "password123")

        assert result["success"] is True
        # Verify navigation to drive
        navigate_calls = mock_browser_manager.navigate.call_args_list
        assert any("drive.google.com" in str(call) for call in navigate_calls)

    @pytest.mark.asyncio
    async def test_scrape_page_with_selectors(self, automation_flows, mock_browser_manager):
        """Test scraping page with custom selectors."""
        mock_browser_manager.evaluate = AsyncMock(return_value={
            "title": "Test Page",
            "links": ["link1", "link2"]
        })

        result = await automation_flows.scrape_page(
            "https://example.com",
            selectors={"title": "h1", "links": "a"}
        )

        assert "title" in result
        mock_browser_manager.navigate.assert_called_with("page-1", "https://example.com")

    @pytest.mark.asyncio
    async def test_scrape_page_returns_screenshot(self, automation_flows, mock_browser_manager):
        """Test that scrape_page can return screenshot."""
        result = await automation_flows.scrape_page(
            "https://example.com",
            take_screenshot=True
        )

        assert "screenshot" in result
        mock_browser_manager.screenshot.assert_called_once()

    @pytest.mark.asyncio
    async def test_fill_form_flow(self, automation_flows, mock_browser_manager):
        """Test form filling automation flow."""
        form_data = {
            "#name": "John Doe",
            "#email": "john@example.com",
            "#message": "Hello World"
        }

        result = await automation_flows.fill_form(
            "https://example.com/contact",
            form_data
        )

        assert result["success"] is True
        # Verify each field was filled
        for selector, value in form_data.items():
            mock_browser_manager.fill.assert_any_call("page-1", selector, value)

    @pytest.mark.asyncio
    async def test_submit_form_flow(self, automation_flows, mock_browser_manager):
        """Test form submission automation flow."""
        form_data = {"#name": "Test"}

        result = await automation_flows.fill_form(
            "https://example.com/form",
            form_data,
            submit_selector="#submit"
        )

        mock_browser_manager.click.assert_called_with("page-1", "#submit")

    @pytest.mark.asyncio
    async def test_multi_step_navigation(self, automation_flows, mock_browser_manager):
        """Test multi-step navigation flow."""
        steps = [
            {"action": "navigate", "url": "https://example.com"},
            {"action": "click", "selector": "#login"},
            {"action": "fill", "selector": "#username", "value": "test"},
            {"action": "click", "selector": "#submit"}
        ]

        result = await automation_flows.execute_steps(steps)

        assert result["success"] is True
        assert result["steps_completed"] == len(steps)

    @pytest.mark.asyncio
    async def test_wait_for_navigation(self, automation_flows, mock_browser_manager):
        """Test waiting for navigation after action."""
        mock_browser_manager.wait_for_load_state = AsyncMock()

        await automation_flows.scrape_page(
            "https://example.com",
            wait_for_load=True
        )

        # Should wait for page to load
        mock_browser_manager.wait_for_load_state.assert_called()

    @pytest.mark.asyncio
    async def test_handle_popup(self, automation_flows, mock_browser_manager):
        """Test handling popup windows."""
        mock_popup = MagicMock()
        mock_browser_manager.wait_for_popup = AsyncMock(return_value=mock_popup)

        result = await automation_flows.handle_popup(
            "page-1",
            trigger_selector="#open-popup"
        )

        assert result["popup_handled"] is True

    @pytest.mark.asyncio
    async def test_download_file(self, automation_flows, mock_browser_manager):
        """Test file download automation."""
        mock_download = MagicMock()
        mock_download.path = AsyncMock(return_value="/tmp/file.pdf")
        mock_browser_manager.wait_for_download = AsyncMock(return_value=mock_download)

        result = await automation_flows.download_file(
            "page-1",
            trigger_selector="#download-btn"
        )

        assert "path" in result


class TestGoogleWorkspaceFlows:
    """Tests for Google Workspace automation flows."""

    @pytest.fixture
    def mock_browser_manager(self):
        """Mock BrowserManager for testing."""
        manager = MagicMock()
        manager.start = AsyncMock()
        manager.launch_browser = AsyncMock(return_value="browser-1")
        manager.new_page = AsyncMock(return_value="page-1")
        manager.navigate = AsyncMock()
        manager.click = AsyncMock()
        manager.fill = AsyncMock()
        manager.wait_for_selector = AsyncMock(return_value=MagicMock())
        manager.screenshot = AsyncMock(return_value=b"screenshot")
        manager.get_content = AsyncMock(return_value="<html></html>")
        manager.evaluate = AsyncMock()
        return manager

    @pytest.fixture
    def google_flows(self, mock_browser_manager):
        """Create Google-specific flows instance."""
        from core.browser.flows import GoogleWorkspaceFlows
        flows = GoogleWorkspaceFlows(browser_manager=mock_browser_manager)
        return flows

    @pytest.mark.asyncio
    async def test_create_google_doc(self, google_flows, mock_browser_manager):
        """Test creating a new Google Doc."""
        result = await google_flows.create_document(
            title="Test Document",
            content="Hello World"
        )

        assert result["success"] is True
        assert "doc_url" in result

    @pytest.mark.asyncio
    async def test_upload_to_drive(self, google_flows, mock_browser_manager):
        """Test uploading file to Google Drive."""
        result = await google_flows.upload_to_drive(
            file_path="/tmp/test.txt",
            folder_name="Test Folder"
        )

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_read_gmail_inbox(self, google_flows, mock_browser_manager):
        """Test reading Gmail inbox."""
        mock_browser_manager.evaluate.return_value = [
            {"subject": "Email 1", "from": "test@example.com"},
            {"subject": "Email 2", "from": "test2@example.com"}
        ]

        result = await google_flows.read_inbox(limit=10)

        assert "emails" in result
        mock_browser_manager.navigate.assert_called()

    @pytest.mark.asyncio
    async def test_compose_email(self, google_flows, mock_browser_manager):
        """Test composing and sending email."""
        result = await google_flows.compose_email(
            to="recipient@example.com",
            subject="Test Subject",
            body="Test body content"
        )

        assert result["success"] is True
        # Should have filled the compose form
        mock_browser_manager.fill.assert_called()


class TestAutomationFlowsErrorHandling:
    """Tests for error handling in automation flows."""

    @pytest.fixture
    def mock_browser_manager(self):
        """Mock BrowserManager for testing."""
        manager = MagicMock()
        manager.start = AsyncMock()
        manager.launch_browser = AsyncMock(return_value="browser-1")
        manager.new_page = AsyncMock(return_value="page-1")
        manager.navigate = AsyncMock()
        manager.screenshot = AsyncMock(return_value=b"screenshot")
        return manager

    @pytest.fixture
    def automation_flows(self, mock_browser_manager):
        """Create AutomationFlows instance."""
        from core.browser.flows import AutomationFlows
        return AutomationFlows(browser_manager=mock_browser_manager)

    @pytest.mark.asyncio
    async def test_navigation_timeout(self, automation_flows, mock_browser_manager):
        """Test handling navigation timeout."""
        from playwright.async_api import TimeoutError as PlaywrightTimeout

        mock_browser_manager.navigate.side_effect = PlaywrightTimeout("Navigation timeout")

        result = await automation_flows.scrape_page("https://slow-site.com")

        assert result["success"] is False
        assert "timeout" in result.get("error", "").lower()

    @pytest.mark.asyncio
    async def test_element_not_found(self, automation_flows, mock_browser_manager):
        """Test handling element not found."""
        mock_browser_manager.click = AsyncMock(
            side_effect=Exception("Element not found")
        )

        result = await automation_flows.fill_form(
            "https://example.com",
            {"#nonexistent": "value"},
            submit_selector="#submit"
        )

        # Should handle gracefully
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_retry_on_failure(self, automation_flows, mock_browser_manager):
        """Test automatic retry on transient failures."""
        # First call fails, second succeeds
        mock_browser_manager.navigate.side_effect = [
            Exception("Network error"),
            None  # Success
        ]

        result = await automation_flows.scrape_page(
            "https://example.com",
            retry_count=3
        )

        # Should have retried
        assert mock_browser_manager.navigate.call_count >= 2

    @pytest.mark.asyncio
    async def test_screenshot_on_error(self, automation_flows, mock_browser_manager):
        """Test that screenshot is taken on error for debugging."""
        mock_browser_manager.click = AsyncMock(side_effect=Exception("Click failed"))

        result = await automation_flows.fill_form(
            "https://example.com",
            {"#field": "value"},
            capture_error_screenshot=True
        )

        # Should have taken error screenshot
        mock_browser_manager.screenshot.assert_called()
