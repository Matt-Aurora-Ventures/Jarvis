"""
Unit tests for Permission Manager.

Tests:
- Permission level checks (none, basic, elevated, admin)
- User permission management
- ExecRequest creation and lifecycle
- Approval/denial workflow
- Pending request listing
- Request expiration
"""

import pytest
import time
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock, AsyncMock


class TestPermissionLevels:
    """Test permission level definitions and comparisons."""

    def test_permission_levels_defined(self):
        """Test all permission levels are defined."""
        from core.permissions.manager import PermissionLevel

        assert hasattr(PermissionLevel, "NONE")
        assert hasattr(PermissionLevel, "BASIC")
        assert hasattr(PermissionLevel, "ELEVATED")
        assert hasattr(PermissionLevel, "ADMIN")

    def test_permission_level_ordering(self):
        """Test permission levels have correct ordering."""
        from core.permissions.manager import PermissionLevel

        assert PermissionLevel.NONE.value < PermissionLevel.BASIC.value
        assert PermissionLevel.BASIC.value < PermissionLevel.ELEVATED.value
        assert PermissionLevel.ELEVATED.value < PermissionLevel.ADMIN.value

    def test_permission_level_from_string(self):
        """Test converting string to permission level."""
        from core.permissions.manager import PermissionLevel

        assert PermissionLevel.from_string("none") == PermissionLevel.NONE
        assert PermissionLevel.from_string("basic") == PermissionLevel.BASIC
        assert PermissionLevel.from_string("elevated") == PermissionLevel.ELEVATED
        assert PermissionLevel.from_string("admin") == PermissionLevel.ADMIN
        assert PermissionLevel.from_string("ADMIN") == PermissionLevel.ADMIN
        assert PermissionLevel.from_string("invalid") == PermissionLevel.NONE


class TestExecRequest:
    """Test ExecRequest dataclass."""

    def test_exec_request_creation(self):
        """Test creating an ExecRequest."""
        from core.permissions.manager import ExecRequest

        request = ExecRequest(
            id="req_123",
            user_id=12345,
            session_id="sess_abc",
            command="git reset --hard",
            description="Reset repository",
            risk_level="high",
        )

        assert request.id == "req_123"
        assert request.user_id == 12345
        assert request.session_id == "sess_abc"
        assert request.command == "git reset --hard"
        assert request.description == "Reset repository"
        assert request.risk_level == "high"
        assert request.status == "pending"
        assert request.created_at is not None
        assert request.expires_at is not None

    def test_exec_request_default_expiration(self):
        """Test ExecRequest has default expiration of 5 minutes."""
        from core.permissions.manager import ExecRequest

        request = ExecRequest(
            id="req_123",
            user_id=12345,
            session_id="sess_abc",
            command="ls",
            description="List files",
            risk_level="safe",
        )

        # Should expire in ~5 minutes
        diff = request.expires_at - request.created_at
        assert 290 <= diff.total_seconds() <= 310  # 5 min +/- 10 sec

    def test_exec_request_is_expired(self):
        """Test checking if request is expired."""
        from core.permissions.manager import ExecRequest

        request = ExecRequest(
            id="req_123",
            user_id=12345,
            session_id="sess_abc",
            command="ls",
            description="List files",
            risk_level="safe",
        )

        assert request.is_expired() is False

        # Manually set expiration to past
        request.expires_at = datetime.now() - timedelta(minutes=1)
        assert request.is_expired() is True

    def test_exec_request_to_dict(self):
        """Test converting ExecRequest to dictionary."""
        from core.permissions.manager import ExecRequest

        request = ExecRequest(
            id="req_123",
            user_id=12345,
            session_id="sess_abc",
            command="git push",
            description="Push changes",
            risk_level="moderate",
        )

        data = request.to_dict()
        assert data["id"] == "req_123"
        assert data["user_id"] == 12345
        assert data["command"] == "git push"
        assert data["risk_level"] == "moderate"
        assert data["status"] == "pending"
        assert "created_at" in data
        assert "expires_at" in data

    def test_exec_request_from_dict(self):
        """Test creating ExecRequest from dictionary."""
        from core.permissions.manager import ExecRequest

        data = {
            "id": "req_456",
            "user_id": 67890,
            "session_id": "sess_xyz",
            "command": "rm -rf /tmp/cache",
            "description": "Clear cache",
            "risk_level": "high",
            "status": "approved",
            "created_at": "2026-01-25T12:00:00",
            "expires_at": "2026-01-25T12:05:00",
        }

        request = ExecRequest.from_dict(data)
        assert request.id == "req_456"
        assert request.user_id == 67890
        assert request.command == "rm -rf /tmp/cache"
        assert request.status == "approved"


class TestPermissionManager:
    """Test PermissionManager class."""

    @pytest.fixture
    def manager(self):
        """Create a fresh PermissionManager for testing."""
        from core.permissions.manager import PermissionManager, _reset_manager

        _reset_manager()
        mgr = PermissionManager()
        yield mgr
        _reset_manager()

    def test_manager_singleton(self):
        """Test PermissionManager is a singleton."""
        from core.permissions.manager import PermissionManager, _reset_manager

        _reset_manager()
        mgr1 = PermissionManager()
        mgr2 = PermissionManager()
        assert mgr1 is mgr2
        _reset_manager()

    def test_get_user_level_default(self, manager):
        """Test default user level is BASIC."""
        from core.permissions.manager import PermissionLevel

        level = manager.get_user_level(12345)
        assert level == PermissionLevel.BASIC

    def test_set_user_level(self, manager):
        """Test setting user permission level."""
        from core.permissions.manager import PermissionLevel

        manager.set_user_level(12345, PermissionLevel.ELEVATED)
        level = manager.get_user_level(12345)
        assert level == PermissionLevel.ELEVATED

    def test_set_user_level_from_string(self, manager):
        """Test setting user level from string."""
        from core.permissions.manager import PermissionLevel

        manager.set_user_level(12345, "admin")
        level = manager.get_user_level(12345)
        assert level == PermissionLevel.ADMIN

    def test_check_permission_basic_actions(self, manager):
        """Test basic users can perform safe actions."""
        from core.permissions.manager import PermissionLevel

        manager.set_user_level(12345, PermissionLevel.BASIC)

        # Safe actions should be allowed
        assert manager.check_permission(12345, "read_file") is True
        assert manager.check_permission(12345, "list_files") is True

    def test_check_permission_elevated_required(self, manager):
        """Test elevated actions require elevated permissions."""
        from core.permissions.manager import PermissionLevel

        # Basic user cannot do elevated actions
        manager.set_user_level(12345, PermissionLevel.BASIC)
        assert manager.check_permission(12345, "write_file") is False

        # Elevated user can
        manager.set_user_level(12345, PermissionLevel.ELEVATED)
        assert manager.check_permission(12345, "write_file") is True

    def test_check_permission_admin_required(self, manager):
        """Test admin actions require admin permissions."""
        from core.permissions.manager import PermissionLevel

        # Elevated user cannot do admin actions
        manager.set_user_level(12345, PermissionLevel.ELEVATED)
        assert manager.check_permission(12345, "delete_system") is False

        # Admin user can
        manager.set_user_level(12345, PermissionLevel.ADMIN)
        assert manager.check_permission(12345, "delete_system") is True

    def test_check_permission_none_level(self, manager):
        """Test NONE level cannot do anything."""
        from core.permissions.manager import PermissionLevel

        manager.set_user_level(12345, PermissionLevel.NONE)
        assert manager.check_permission(12345, "read_file") is False
        assert manager.check_permission(12345, "list_files") is False

    def test_request_approval(self, manager):
        """Test requesting approval for a command."""
        request = manager.request_approval(
            user_id=12345,
            command="git reset --hard HEAD~1",
            risk_level="high",
            description="Discard last commit",
        )

        assert request is not None
        assert request.id.startswith("req_")
        assert request.user_id == 12345
        assert request.command == "git reset --hard HEAD~1"
        assert request.risk_level == "high"
        assert request.status == "pending"

    def test_approve_request(self, manager):
        """Test approving a pending request."""
        request = manager.request_approval(
            user_id=12345,
            command="rm -rf /tmp/old",
            risk_level="high",
        )

        result = manager.approve_request(request.id)
        assert result is True

        # Request should now be approved
        updated = manager.get_request(request.id)
        assert updated.status == "approved"
        assert updated.approved_at is not None

    def test_deny_request(self, manager):
        """Test denying a pending request."""
        request = manager.request_approval(
            user_id=12345,
            command="rm -rf /",
            risk_level="critical",
        )

        result = manager.deny_request(request.id)
        assert result is True

        # Request should now be denied
        updated = manager.get_request(request.id)
        assert updated.status == "denied"

    def test_approve_nonexistent_request(self, manager):
        """Test approving a nonexistent request returns False."""
        result = manager.approve_request("nonexistent_id")
        assert result is False

    def test_deny_nonexistent_request(self, manager):
        """Test denying a nonexistent request returns False."""
        result = manager.deny_request("nonexistent_id")
        assert result is False

    def test_list_pending_requests(self, manager):
        """Test listing pending requests for a user."""
        # Create multiple requests
        req1 = manager.request_approval(user_id=12345, command="cmd1", risk_level="safe")
        req2 = manager.request_approval(user_id=12345, command="cmd2", risk_level="moderate")
        req3 = manager.request_approval(user_id=67890, command="cmd3", risk_level="high")

        # Approve one
        manager.approve_request(req1.id)

        # Get pending for user 12345
        pending = manager.list_pending_requests(12345)
        assert len(pending) == 1
        assert pending[0].id == req2.id

    def test_list_pending_requests_all_users(self, manager):
        """Test listing all pending requests."""
        manager.request_approval(user_id=12345, command="cmd1", risk_level="safe")
        manager.request_approval(user_id=67890, command="cmd2", risk_level="high")

        all_pending = manager.list_pending_requests()
        assert len(all_pending) == 2

    def test_expired_requests_filtered(self, manager):
        """Test expired requests are filtered from pending list."""
        request = manager.request_approval(
            user_id=12345,
            command="cmd1",
            risk_level="safe",
        )

        # Manually expire the request
        request.expires_at = datetime.now() - timedelta(minutes=1)

        pending = manager.list_pending_requests(12345)
        assert len(pending) == 0


class TestAllowlist:
    """Test allowlist management."""

    @pytest.fixture
    def manager(self):
        """Create a fresh PermissionManager for testing."""
        from core.permissions.manager import PermissionManager, _reset_manager

        _reset_manager()
        mgr = PermissionManager()
        yield mgr
        _reset_manager()

    def test_add_to_allowlist(self, manager):
        """Test adding pattern to allowlist."""
        result = manager.add_to_allowlist(12345, "git commit*")
        assert result is True

        allowlist = manager.get_allowlist(12345)
        assert "git commit*" in allowlist

    def test_remove_from_allowlist(self, manager):
        """Test removing pattern from allowlist."""
        manager.add_to_allowlist(12345, "git commit*")
        manager.add_to_allowlist(12345, "npm install*")

        result = manager.remove_from_allowlist(12345, "git commit*")
        assert result is True

        allowlist = manager.get_allowlist(12345)
        assert "git commit*" not in allowlist
        assert "npm install*" in allowlist

    def test_remove_nonexistent_pattern(self, manager):
        """Test removing nonexistent pattern returns False."""
        result = manager.remove_from_allowlist(12345, "nonexistent*")
        assert result is False

    def test_check_allowlist_match(self, manager):
        """Test checking if command matches allowlist."""
        manager.add_to_allowlist(12345, "git commit*")
        manager.add_to_allowlist(12345, "npm install*")

        assert manager.is_allowlisted(12345, "git commit -m 'test'") is True
        assert manager.is_allowlisted(12345, "npm install lodash") is True
        assert manager.is_allowlisted(12345, "rm -rf /") is False

    def test_allowlist_glob_patterns(self, manager):
        """Test glob patterns in allowlist."""
        manager.add_to_allowlist(12345, "python scripts/*.py")

        assert manager.is_allowlisted(12345, "python scripts/test.py") is True
        assert manager.is_allowlisted(12345, "python scripts/main.py") is True
        assert manager.is_allowlisted(12345, "python other/test.py") is False


class TestPermissionManagerPersistence:
    """Test PermissionManager database persistence."""

    @pytest.fixture
    def manager_with_db(self, tmp_path):
        """Create PermissionManager with test database."""
        from core.permissions.manager import PermissionManager, _reset_manager

        _reset_manager()
        db_path = tmp_path / "test_permissions.db"
        mgr = PermissionManager(db_path=str(db_path))
        yield mgr
        _reset_manager()

    def test_persist_user_level(self, manager_with_db):
        """Test user level is persisted to database."""
        from core.permissions.manager import PermissionLevel

        manager_with_db.set_user_level(12345, PermissionLevel.ADMIN)

        # Verify from database
        level = manager_with_db.get_user_level(12345)
        assert level == PermissionLevel.ADMIN

    def test_persist_exec_request(self, manager_with_db):
        """Test exec request is persisted to database."""
        request = manager_with_db.request_approval(
            user_id=12345,
            command="dangerous command",
            risk_level="critical",
        )

        # Retrieve from database
        retrieved = manager_with_db.get_request(request.id)
        assert retrieved is not None
        assert retrieved.command == "dangerous command"
        assert retrieved.risk_level == "critical"

    def test_persist_allowlist(self, manager_with_db):
        """Test allowlist is persisted to database."""
        manager_with_db.add_to_allowlist(12345, "git *")
        manager_with_db.add_to_allowlist(12345, "npm *")

        allowlist = manager_with_db.get_allowlist(12345)
        assert "git *" in allowlist
        assert "npm *" in allowlist


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
