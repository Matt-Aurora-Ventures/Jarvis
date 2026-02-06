"""
Tests for User model (core/users/model.py)

Tests the User dataclass with all required fields:
- user_id, username, first_seen, last_seen
- preferences: Dict
- permissions: List[str]
- is_admin, is_banned
"""

import pytest
from datetime import datetime
from typing import Dict, List


class TestUserModel:
    """Tests for User dataclass."""

    def test_user_creation_with_required_fields(self):
        """User can be created with required fields."""
        from core.users.model import User

        user = User(user_id="123")

        assert user.user_id == "123"
        assert user.username is None
        assert isinstance(user.first_seen, datetime)
        assert isinstance(user.last_seen, datetime)
        assert user.preferences == {}
        assert user.permissions == []
        assert user.is_admin is False
        assert user.is_banned is False

    def test_user_creation_with_all_fields(self):
        """User can be created with all fields specified."""
        from core.users.model import User

        now = datetime.now()
        user = User(
            user_id="456",
            username="testuser",
            first_seen=now,
            last_seen=now,
            preferences={"theme": "dark"},
            permissions=["read", "write"],
            is_admin=True,
            is_banned=False
        )

        assert user.user_id == "456"
        assert user.username == "testuser"
        assert user.first_seen == now
        assert user.last_seen == now
        assert user.preferences == {"theme": "dark"}
        assert user.permissions == ["read", "write"]
        assert user.is_admin is True
        assert user.is_banned is False

    def test_user_to_dict(self):
        """User can be converted to dictionary."""
        from core.users.model import User

        user = User(
            user_id="789",
            username="dictuser",
            preferences={"lang": "en"},
            permissions=["admin"]
        )

        data = user.to_dict()

        assert data["user_id"] == "789"
        assert data["username"] == "dictuser"
        assert data["preferences"] == {"lang": "en"}
        assert data["permissions"] == ["admin"]
        assert "first_seen" in data
        assert "last_seen" in data

    def test_user_from_dict(self):
        """User can be created from dictionary."""
        from core.users.model import User

        data = {
            "user_id": "abc",
            "username": "fromdict",
            "first_seen": "2026-01-01T00:00:00",
            "last_seen": "2026-01-02T00:00:00",
            "preferences": {"notifications": True},
            "permissions": ["read"],
            "is_admin": False,
            "is_banned": True
        }

        user = User.from_dict(data)

        assert user.user_id == "abc"
        assert user.username == "fromdict"
        assert user.preferences == {"notifications": True}
        assert user.permissions == ["read"]
        assert user.is_banned is True

    def test_user_update_last_seen(self):
        """User last_seen can be updated."""
        from core.users.model import User

        user = User(user_id="update_test")
        original_last_seen = user.last_seen

        import time
        time.sleep(0.01)  # Small delay to ensure different timestamp

        user.touch()

        assert user.last_seen > original_last_seen

    def test_user_add_permission(self):
        """User can have permissions added."""
        from core.users.model import User

        user = User(user_id="perm_test")
        user.add_permission("write")

        assert "write" in user.permissions

    def test_user_remove_permission(self):
        """User can have permissions removed."""
        from core.users.model import User

        user = User(user_id="perm_test", permissions=["read", "write"])
        user.remove_permission("write")

        assert "write" not in user.permissions
        assert "read" in user.permissions

    def test_user_has_permission(self):
        """User permission check works correctly."""
        from core.users.model import User

        user = User(user_id="perm_check", permissions=["read"])

        assert user.has_permission("read") is True
        assert user.has_permission("write") is False

    def test_user_equality(self):
        """Users with same user_id are equal."""
        from core.users.model import User

        user1 = User(user_id="same_id", username="user1")
        user2 = User(user_id="same_id", username="user2")

        assert user1 == user2

    def test_user_str_representation(self):
        """User has a useful string representation."""
        from core.users.model import User

        user = User(user_id="str_test", username="struser")

        assert "str_test" in str(user)
        assert "struser" in str(user)
