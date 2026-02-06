"""
Tests for User permissions (core/users/permissions.py)

Tests the Permission enum and permission utilities:
- Permission enum (ADMIN, USER, GUEST)
- has_permission(user, permission) -> bool
- require_permission(permission) decorator
- Admin list from env
"""

import pytest
import os
from unittest.mock import patch, MagicMock
from functools import wraps


class TestPermissionEnum:
    """Tests for Permission enum."""

    def test_permission_enum_has_admin(self):
        """Permission enum has ADMIN value."""
        from core.users.permissions import Permission

        assert hasattr(Permission, "ADMIN")
        assert Permission.ADMIN.value == "admin"

    def test_permission_enum_has_user(self):
        """Permission enum has USER value."""
        from core.users.permissions import Permission

        assert hasattr(Permission, "USER")
        assert Permission.USER.value == "user"

    def test_permission_enum_has_guest(self):
        """Permission enum has GUEST value."""
        from core.users.permissions import Permission

        assert hasattr(Permission, "GUEST")
        assert Permission.GUEST.value == "guest"

    def test_permission_enum_values(self):
        """Permission enum has expected number of values."""
        from core.users.permissions import Permission

        # At minimum these three
        assert len(Permission) >= 3


class TestHasPermission:
    """Tests for has_permission function."""

    def test_has_permission_true(self):
        """has_permission returns True when user has permission."""
        from core.users.permissions import has_permission, Permission
        from core.users.model import User

        user = User(user_id="perm_user", permissions=["admin"])

        assert has_permission(user, Permission.ADMIN) is True

    def test_has_permission_false(self):
        """has_permission returns False when user lacks permission."""
        from core.users.permissions import has_permission, Permission
        from core.users.model import User

        user = User(user_id="no_perm", permissions=["guest"])

        assert has_permission(user, Permission.ADMIN) is False

    def test_has_permission_with_string(self):
        """has_permission works with string permission."""
        from core.users.permissions import has_permission
        from core.users.model import User

        user = User(user_id="str_perm", permissions=["user"])

        assert has_permission(user, "user") is True
        assert has_permission(user, "admin") is False

    def test_admin_has_all_permissions(self):
        """Admin users have all permissions."""
        from core.users.permissions import has_permission, Permission
        from core.users.model import User

        user = User(user_id="admin_user", is_admin=True)

        assert has_permission(user, Permission.USER) is True
        assert has_permission(user, Permission.GUEST) is True
        assert has_permission(user, Permission.ADMIN) is True

    def test_banned_user_has_no_permissions(self):
        """Banned users have no permissions."""
        from core.users.permissions import has_permission, Permission
        from core.users.model import User

        user = User(
            user_id="banned_user",
            permissions=["admin", "user"],
            is_banned=True
        )

        assert has_permission(user, Permission.ADMIN) is False
        assert has_permission(user, Permission.USER) is False


class TestRequirePermission:
    """Tests for require_permission decorator."""

    def test_require_permission_allows_authorized(self):
        """require_permission allows users with permission."""
        from core.users.permissions import require_permission, Permission
        from core.users.model import User

        @require_permission(Permission.USER)
        def protected_function(user):
            return "success"

        user = User(user_id="auth_user", permissions=["user"])
        result = protected_function(user)

        assert result == "success"

    def test_require_permission_blocks_unauthorized(self):
        """require_permission blocks users without permission."""
        from core.users.permissions import require_permission, Permission, PermissionDeniedError
        from core.users.model import User

        @require_permission(Permission.ADMIN)
        def admin_only(user):
            return "admin stuff"

        user = User(user_id="normal_user", permissions=["user"])

        with pytest.raises(PermissionDeniedError):
            admin_only(user)

    def test_require_permission_with_keyword_arg(self):
        """require_permission works with user as keyword argument."""
        from core.users.permissions import require_permission, Permission
        from core.users.model import User

        @require_permission(Permission.USER)
        def protected_function(user=None):
            return "success"

        user = User(user_id="kw_user", permissions=["user"])
        result = protected_function(user=user)

        assert result == "success"

    def test_require_permission_custom_user_arg(self):
        """require_permission can use custom argument name for user."""
        from core.users.permissions import require_permission, Permission
        from core.users.model import User

        @require_permission(Permission.USER, user_arg="current_user")
        def protected_function(current_user):
            return "success"

        user = User(user_id="custom_arg", permissions=["user"])
        result = protected_function(current_user=user)

        assert result == "success"

    def test_require_permission_preserves_function_name(self):
        """require_permission preserves decorated function name."""
        from core.users.permissions import require_permission, Permission

        @require_permission(Permission.USER)
        def my_special_function(user):
            """My docstring."""
            return "result"

        assert my_special_function.__name__ == "my_special_function"
        assert my_special_function.__doc__ == "My docstring."


class TestAdminList:
    """Tests for admin list from environment."""

    def test_get_admin_list_empty(self):
        """get_admin_list returns empty list when env not set."""
        from core.users.permissions import get_admin_list

        with patch.dict(os.environ, {}, clear=True):
            admins = get_admin_list()

        assert admins == []

    def test_get_admin_list_single(self):
        """get_admin_list returns single admin from env."""
        from core.users.permissions import get_admin_list

        with patch.dict(os.environ, {"JARVIS_ADMIN_IDS": "admin123"}):
            admins = get_admin_list()

        assert admins == ["admin123"]

    def test_get_admin_list_multiple(self):
        """get_admin_list returns multiple admins from env."""
        from core.users.permissions import get_admin_list

        with patch.dict(os.environ, {"JARVIS_ADMIN_IDS": "admin1,admin2,admin3"}):
            admins = get_admin_list()

        assert admins == ["admin1", "admin2", "admin3"]

    def test_get_admin_list_strips_whitespace(self):
        """get_admin_list strips whitespace from admin IDs."""
        from core.users.permissions import get_admin_list

        with patch.dict(os.environ, {"JARVIS_ADMIN_IDS": " admin1 , admin2 , admin3 "}):
            admins = get_admin_list()

        assert admins == ["admin1", "admin2", "admin3"]

    def test_is_admin_from_env(self):
        """is_admin_from_env correctly checks env admin list."""
        from core.users.permissions import is_admin_from_env

        with patch.dict(os.environ, {"JARVIS_ADMIN_IDS": "env_admin"}):
            assert is_admin_from_env("env_admin") is True
            assert is_admin_from_env("regular_user") is False


class TestPermissionDeniedError:
    """Tests for PermissionDeniedError exception."""

    def test_permission_denied_error_exists(self):
        """PermissionDeniedError can be imported and raised."""
        from core.users.permissions import PermissionDeniedError

        with pytest.raises(PermissionDeniedError):
            raise PermissionDeniedError("Not allowed")

    def test_permission_denied_error_message(self):
        """PermissionDeniedError includes message."""
        from core.users.permissions import PermissionDeniedError

        error = PermissionDeniedError("Custom message")

        assert "Custom message" in str(error)

    def test_permission_denied_error_includes_permission(self):
        """PermissionDeniedError can include required permission."""
        from core.users.permissions import PermissionDeniedError, Permission

        error = PermissionDeniedError(
            "Access denied",
            required_permission=Permission.ADMIN
        )

        assert error.required_permission == Permission.ADMIN
