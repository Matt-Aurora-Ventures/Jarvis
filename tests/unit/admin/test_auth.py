"""
Tests for core/admin/auth.py - Admin authentication and authorization.
"""

import os
import pytest
from unittest.mock import patch, MagicMock


class TestIsAdmin:
    """Tests for is_admin function."""

    def test_is_admin_with_valid_id(self):
        """Admin user ID should return True."""
        from core.admin.auth import is_admin

        with patch.dict(os.environ, {"ADMIN_USER_IDS": "123456789,987654321"}):
            # Force reload of admin IDs
            from core.admin import auth
            auth._admin_user_ids = None

            assert is_admin(123456789) is True
            assert is_admin(987654321) is True

    def test_is_admin_with_invalid_id(self):
        """Non-admin user ID should return False."""
        from core.admin.auth import is_admin

        with patch.dict(os.environ, {"ADMIN_USER_IDS": "123456789"}):
            from core.admin import auth
            auth._admin_user_ids = None

            assert is_admin(999999999) is False

    def test_is_admin_with_empty_env(self):
        """Empty ADMIN_USER_IDS should deny all."""
        from core.admin.auth import is_admin

        with patch.dict(os.environ, {"ADMIN_USER_IDS": ""}, clear=True):
            from core.admin import auth
            auth._admin_user_ids = None

            assert is_admin(123456789) is False

    def test_is_admin_with_missing_env(self):
        """Missing ADMIN_USER_IDS should deny all."""
        from core.admin.auth import is_admin

        # Remove the env var if it exists
        env = os.environ.copy()
        env.pop("ADMIN_USER_IDS", None)

        with patch.dict(os.environ, env, clear=True):
            from core.admin import auth
            auth._admin_user_ids = None

            assert is_admin(123456789) is False


class TestRequireAdmin:
    """Tests for require_admin decorator."""

    def test_require_admin_allows_admin_user(self):
        """Decorated function should execute for admin users."""
        from core.admin.auth import require_admin

        with patch.dict(os.environ, {"ADMIN_USER_IDS": "123456789"}):
            from core.admin import auth
            auth._admin_user_ids = None

            @require_admin
            def protected_func(user_id: int, data: str) -> str:
                return f"Success: {data}"

            result = protected_func(123456789, "test_data")
            assert result == "Success: test_data"

    def test_require_admin_denies_non_admin(self):
        """Decorated function should raise for non-admin users."""
        from core.admin.auth import require_admin, UnauthorizedError

        with patch.dict(os.environ, {"ADMIN_USER_IDS": "123456789"}):
            from core.admin import auth
            auth._admin_user_ids = None

            @require_admin
            def protected_func(user_id: int) -> str:
                return "Should not reach here"

            with pytest.raises(UnauthorizedError) as exc_info:
                protected_func(999999999)

            assert "not authorized" in str(exc_info.value).lower()

    def test_require_admin_logs_unauthorized_attempts(self):
        """Unauthorized attempts should be logged."""
        from core.admin.auth import require_admin, UnauthorizedError

        with patch.dict(os.environ, {"ADMIN_USER_IDS": "123456789"}):
            from core.admin import auth
            auth._admin_user_ids = None

            @require_admin
            def protected_func(user_id: int) -> str:
                return "Should not reach here"

            with patch("core.admin.auth.logger") as mock_logger:
                with pytest.raises(UnauthorizedError):
                    protected_func(999999999)

                # Check that warning was logged
                mock_logger.warning.assert_called()
                call_args = str(mock_logger.warning.call_args)
                assert "999999999" in call_args or "unauthorized" in call_args.lower()


class TestAsyncRequireAdmin:
    """Tests for async require_admin decorator."""

    @pytest.mark.asyncio
    async def test_async_require_admin_allows_admin(self):
        """Async decorated function should execute for admin users."""
        from core.admin.auth import require_admin

        with patch.dict(os.environ, {"ADMIN_USER_IDS": "123456789"}):
            from core.admin import auth
            auth._admin_user_ids = None

            @require_admin
            async def async_protected(user_id: int) -> str:
                return "Async success"

            result = await async_protected(123456789)
            assert result == "Async success"

    @pytest.mark.asyncio
    async def test_async_require_admin_denies_non_admin(self):
        """Async decorated function should raise for non-admin."""
        from core.admin.auth import require_admin, UnauthorizedError

        with patch.dict(os.environ, {"ADMIN_USER_IDS": "123456789"}):
            from core.admin import auth
            auth._admin_user_ids = None

            @require_admin
            async def async_protected(user_id: int) -> str:
                return "Should not reach"

            with pytest.raises(UnauthorizedError):
                await async_protected(999999999)


class TestGetAdminUserIds:
    """Tests for get_admin_user_ids function."""

    def test_get_admin_user_ids_parses_correctly(self):
        """Should parse comma-separated IDs correctly."""
        from core.admin.auth import get_admin_user_ids

        with patch.dict(os.environ, {"ADMIN_USER_IDS": "111,222,333"}):
            from core.admin import auth
            auth._admin_user_ids = None

            ids = get_admin_user_ids()
            assert ids == {111, 222, 333}

    def test_get_admin_user_ids_handles_whitespace(self):
        """Should handle whitespace in IDs."""
        from core.admin.auth import get_admin_user_ids

        with patch.dict(os.environ, {"ADMIN_USER_IDS": " 111 , 222 , 333 "}):
            from core.admin import auth
            auth._admin_user_ids = None

            ids = get_admin_user_ids()
            assert ids == {111, 222, 333}

    def test_get_admin_user_ids_ignores_invalid(self):
        """Should ignore non-numeric values."""
        from core.admin.auth import get_admin_user_ids

        with patch.dict(os.environ, {"ADMIN_USER_IDS": "111,abc,222,@user,333"}):
            from core.admin import auth
            auth._admin_user_ids = None

            ids = get_admin_user_ids()
            assert ids == {111, 222, 333}

    def test_get_admin_user_ids_caches_result(self):
        """Should cache the result after first parse."""
        from core.admin.auth import get_admin_user_ids

        with patch.dict(os.environ, {"ADMIN_USER_IDS": "111,222"}):
            from core.admin import auth
            auth._admin_user_ids = None

            ids1 = get_admin_user_ids()

            # Change env (should not affect cached result)
            os.environ["ADMIN_USER_IDS"] = "999"
            ids2 = get_admin_user_ids()

            assert ids1 == ids2 == {111, 222}
