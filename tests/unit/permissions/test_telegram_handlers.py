"""
Unit tests for Telegram permission handlers.

Tests:
- /approve command
- /deny command
- /allowlist command
- /permissions command
- Inline approval buttons
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta


class MockUpdate:
    """Mock Telegram Update object."""

    def __init__(self, user_id=12345, username="testuser", chat_id=12345, text=""):
        self.effective_user = MagicMock()
        self.effective_user.id = user_id
        self.effective_user.username = username
        self.effective_chat = MagicMock()
        self.effective_chat.id = chat_id
        self.message = MagicMock()
        self.message.text = text
        self.message.reply_text = AsyncMock()
        self.callback_query = None


class MockContext:
    """Mock Telegram Context object."""

    def __init__(self, args=None):
        self.args = args or []
        self.bot = MagicMock()
        self.bot.send_message = AsyncMock()


class TestApproveHandler:
    """Test /approve command handler."""

    @pytest.fixture
    def mock_manager(self):
        """Create mock PermissionManager."""
        with patch("core.permissions.manager.get_permission_manager") as mock:
            manager = MagicMock()
            mock.return_value = manager
            yield manager

    @pytest.mark.asyncio
    async def test_approve_valid_request(self, mock_manager):
        """Test approving a valid pending request."""
        from tg_bot.handlers.permissions import approve_cmd

        # Setup mock request
        mock_request = MagicMock()
        mock_request.id = "req_123"
        mock_request.command = "git push"
        mock_request.user_id = 12345
        mock_manager.get_request.return_value = mock_request
        mock_manager.approve_request.return_value = True

        update = MockUpdate(user_id=12345)
        context = MockContext(args=["req_123"])

        await approve_cmd(update, context)

        mock_manager.approve_request.assert_called_once_with("req_123")
        update.message.reply_text.assert_called_once()
        call_args = update.message.reply_text.call_args
        assert "approved" in call_args[0][0].lower()

    @pytest.mark.asyncio
    async def test_approve_no_request_id(self, mock_manager):
        """Test /approve without request ID shows pending requests."""
        from tg_bot.handlers.permissions import approve_cmd

        mock_request = MagicMock()
        mock_request.id = "req_456"
        mock_request.command = "rm -rf /tmp"
        mock_request.risk_level = "high"
        mock_request.expires_at = datetime.now() + timedelta(minutes=5)
        mock_manager.list_pending_requests.return_value = [mock_request]

        update = MockUpdate(user_id=12345)
        context = MockContext(args=[])

        await approve_cmd(update, context)

        update.message.reply_text.assert_called_once()
        call_args = update.message.reply_text.call_args
        assert "req_456" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_approve_invalid_request(self, mock_manager):
        """Test approving a nonexistent request."""
        from tg_bot.handlers.permissions import approve_cmd

        mock_manager.get_request.return_value = None
        mock_manager.approve_request.return_value = False

        update = MockUpdate(user_id=12345)
        context = MockContext(args=["nonexistent"])

        await approve_cmd(update, context)

        call_args = update.message.reply_text.call_args
        assert "not found" in call_args[0][0].lower()


class TestDenyHandler:
    """Test /deny command handler."""

    @pytest.fixture
    def mock_manager(self):
        """Create mock PermissionManager."""
        with patch("core.permissions.manager.get_permission_manager") as mock:
            manager = MagicMock()
            mock.return_value = manager
            yield manager

    @pytest.mark.asyncio
    async def test_deny_valid_request(self, mock_manager):
        """Test denying a valid pending request."""
        from tg_bot.handlers.permissions import deny_cmd

        mock_request = MagicMock()
        mock_request.id = "req_123"
        mock_manager.get_request.return_value = mock_request
        mock_manager.deny_request.return_value = True

        update = MockUpdate(user_id=12345)
        context = MockContext(args=["req_123"])

        await deny_cmd(update, context)

        mock_manager.deny_request.assert_called_once_with("req_123")
        update.message.reply_text.assert_called_once()
        call_args = update.message.reply_text.call_args
        assert "denied" in call_args[0][0].lower()

    @pytest.mark.asyncio
    async def test_deny_no_request_id(self, mock_manager):
        """Test /deny without request ID shows error."""
        from tg_bot.handlers.permissions import deny_cmd

        update = MockUpdate(user_id=12345)
        context = MockContext(args=[])

        await deny_cmd(update, context)

        call_args = update.message.reply_text.call_args
        assert "usage" in call_args[0][0].lower()


class TestAllowlistHandler:
    """Test /allowlist command handler."""

    @pytest.fixture
    def mock_manager(self):
        """Create mock PermissionManager."""
        with patch("core.permissions.manager.get_permission_manager") as mock:
            manager = MagicMock()
            mock.return_value = manager
            yield manager

    @pytest.mark.asyncio
    async def test_allowlist_show(self, mock_manager):
        """Test /allowlist with no args shows current allowlist."""
        from tg_bot.handlers.permissions import allowlist_cmd

        mock_manager.get_allowlist.return_value = ["git commit*", "npm install*"]

        update = MockUpdate(user_id=12345)
        context = MockContext(args=[])

        await allowlist_cmd(update, context)

        mock_manager.get_allowlist.assert_called_once_with(12345)
        call_args = update.message.reply_text.call_args
        assert "git commit*" in call_args[0][0]
        assert "npm install*" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_allowlist_add(self, mock_manager):
        """Test /allowlist add <pattern>."""
        from tg_bot.handlers.permissions import allowlist_cmd

        mock_manager.add_to_allowlist.return_value = True

        update = MockUpdate(user_id=12345)
        context = MockContext(args=["add", "python", "scripts/*.py"])

        await allowlist_cmd(update, context)

        mock_manager.add_to_allowlist.assert_called_once_with(12345, "python scripts/*.py")
        call_args = update.message.reply_text.call_args
        assert "added" in call_args[0][0].lower()

    @pytest.mark.asyncio
    async def test_allowlist_remove(self, mock_manager):
        """Test /allowlist remove <pattern>."""
        from tg_bot.handlers.permissions import allowlist_cmd

        mock_manager.remove_from_allowlist.return_value = True

        update = MockUpdate(user_id=12345)
        context = MockContext(args=["remove", "git", "commit*"])

        await allowlist_cmd(update, context)

        mock_manager.remove_from_allowlist.assert_called_once_with(12345, "git commit*")
        call_args = update.message.reply_text.call_args
        assert "removed" in call_args[0][0].lower()


class TestPermissionsHandler:
    """Test /permissions command handler."""

    @pytest.fixture
    def mock_manager(self):
        """Create mock PermissionManager."""
        with patch("core.permissions.manager.get_permission_manager") as mock:
            manager = MagicMock()
            mock.return_value = manager
            yield manager

    @pytest.mark.asyncio
    async def test_permissions_show(self, mock_manager):
        """Test /permissions shows current level."""
        from tg_bot.handlers.permissions import permissions_cmd
        from core.permissions.manager import PermissionLevel

        mock_manager.get_user_level.return_value = PermissionLevel.ELEVATED

        update = MockUpdate(user_id=12345)
        context = MockContext(args=[])

        await permissions_cmd(update, context)

        call_args = update.message.reply_text.call_args
        assert "elevated" in call_args[0][0].lower()

    @pytest.mark.asyncio
    async def test_permissions_set_admin_only(self, mock_manager):
        """Test /permissions set requires admin."""
        from tg_bot.handlers.permissions import permissions_cmd
        from core.permissions.manager import PermissionLevel

        # User is not admin
        mock_manager.get_user_level.return_value = PermissionLevel.BASIC

        update = MockUpdate(user_id=12345)
        context = MockContext(args=["admin"])

        await permissions_cmd(update, context)

        call_args = update.message.reply_text.call_args
        # Should be denied or show current level, not change
        mock_manager.set_user_level.assert_not_called()


class TestApprovalUI:
    """Test approval UI with inline buttons."""

    @pytest.mark.asyncio
    async def test_build_approval_message(self):
        """Test building approval request message."""
        from tg_bot.handlers.permissions import build_approval_message
        from core.permissions.manager import ExecRequest

        request = ExecRequest(
            id="req_789",
            user_id=12345,
            session_id="sess_abc",
            command="git reset --hard HEAD~1",
            description="Discard last commit",
            risk_level="high",
        )

        text, keyboard = build_approval_message(request)

        # Check text content
        assert "approval required" in text.lower()
        assert "git reset --hard HEAD~1" in text
        assert "high" in text.lower()
        assert "discard last commit" in text.lower()

        # Check keyboard has approve/deny buttons
        assert keyboard is not None
        button_texts = [b.text.lower() for row in keyboard.inline_keyboard for b in row]
        assert any("approve" in t for t in button_texts)
        assert any("deny" in t for t in button_texts)

    @pytest.mark.asyncio
    async def test_callback_approve(self):
        """Test callback handler for approve button."""
        from tg_bot.handlers.permissions import approval_callback

        with patch("core.permissions.manager.get_permission_manager") as mock_get:
            manager = MagicMock()
            mock_get.return_value = manager
            manager.approve_request.return_value = True

            # Create callback query mock
            callback = MagicMock()
            callback.data = "approve:req_123"
            callback.answer = AsyncMock()
            callback.edit_message_text = AsyncMock()
            callback.from_user = MagicMock()
            callback.from_user.id = 12345

            update = MagicMock()
            update.callback_query = callback

            context = MockContext()

            await approval_callback(update, context)

            manager.approve_request.assert_called_once_with("req_123")
            callback.answer.assert_called_once()
            callback.edit_message_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_callback_deny(self):
        """Test callback handler for deny button."""
        from tg_bot.handlers.permissions import approval_callback

        with patch("core.permissions.manager.get_permission_manager") as mock_get:
            manager = MagicMock()
            mock_get.return_value = manager
            manager.deny_request.return_value = True

            callback = MagicMock()
            callback.data = "deny:req_456"
            callback.answer = AsyncMock()
            callback.edit_message_text = AsyncMock()
            callback.from_user = MagicMock()
            callback.from_user.id = 12345

            update = MagicMock()
            update.callback_query = callback

            context = MockContext()

            await approval_callback(update, context)

            manager.deny_request.assert_called_once_with("req_456")


class TestApprovalExpiration:
    """Test approval request expiration display."""

    @pytest.mark.asyncio
    async def test_expiration_countdown(self):
        """Test expiration countdown in approval message."""
        from tg_bot.handlers.permissions import build_approval_message
        from core.permissions.manager import ExecRequest

        request = ExecRequest(
            id="req_abc",
            user_id=12345,
            session_id="sess_xyz",
            command="rm -rf /tmp/cache",
            description="Clear cache",
            risk_level="high",
        )
        # Set expires_at to 3 minutes from now
        request.expires_at = datetime.now() + timedelta(minutes=3)

        text, keyboard = build_approval_message(request)

        # Should show expiration time
        assert "expires" in text.lower() or "3m" in text or "3 min" in text.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
