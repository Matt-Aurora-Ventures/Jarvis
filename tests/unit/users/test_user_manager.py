"""
Tests for UserManager (core/users/manager.py)

Tests the UserManager class with CRUD operations:
- get_user(user_id) -> User
- create_user(user_id, data) -> User
- update_user(user_id, data)
- delete_user(user_id)
- list_users() -> List[User]
"""

import pytest
import tempfile
from pathlib import Path
from datetime import datetime


class TestUserManager:
    """Tests for UserManager class."""

    @pytest.fixture
    def temp_storage_dir(self, tmp_path):
        """Create a temporary storage directory."""
        storage_dir = tmp_path / "users"
        storage_dir.mkdir()
        return storage_dir

    @pytest.fixture
    def manager(self, temp_storage_dir):
        """Create UserManager with temp storage."""
        from core.users.manager import UserManager
        from core.users.storage import JSONUserStorage

        storage = JSONUserStorage(storage_path=temp_storage_dir)
        return UserManager(storage=storage)

    def test_manager_creation(self, temp_storage_dir):
        """UserManager can be created with storage."""
        from core.users.manager import UserManager
        from core.users.storage import JSONUserStorage

        storage = JSONUserStorage(storage_path=temp_storage_dir)
        manager = UserManager(storage=storage)

        assert manager is not None

    def test_manager_default_storage(self, monkeypatch, tmp_path):
        """UserManager uses default storage path when none provided."""
        from core.users.manager import UserManager

        # Set the default path env
        default_path = tmp_path / "default_users"
        monkeypatch.setenv("JARVIS_USER_DATA_PATH", str(default_path))

        manager = UserManager()

        assert manager is not None

    def test_create_user_minimal(self, manager):
        """create_user creates user with just ID."""
        user = manager.create_user(user_id="new_user")

        assert user is not None
        assert user.user_id == "new_user"
        assert user.username is None

    def test_create_user_with_data(self, manager):
        """create_user creates user with provided data."""
        user = manager.create_user(
            user_id="data_user",
            data={
                "username": "testname",
                "preferences": {"theme": "dark"},
                "permissions": ["user"]
            }
        )

        assert user.user_id == "data_user"
        assert user.username == "testname"
        assert user.preferences == {"theme": "dark"}
        assert "user" in user.permissions

    def test_create_user_already_exists(self, manager):
        """create_user raises error if user already exists."""
        from core.users.manager import UserAlreadyExistsError

        manager.create_user(user_id="duplicate")

        with pytest.raises(UserAlreadyExistsError):
            manager.create_user(user_id="duplicate")

    def test_get_user_exists(self, manager):
        """get_user returns existing user."""
        manager.create_user(user_id="get_me", data={"username": "getter"})

        user = manager.get_user("get_me")

        assert user is not None
        assert user.user_id == "get_me"
        assert user.username == "getter"

    def test_get_user_not_exists(self, manager):
        """get_user returns None for nonexistent user."""
        user = manager.get_user("does_not_exist")

        assert user is None

    def test_get_or_create_user_new(self, manager):
        """get_or_create_user creates new user if not exists."""
        user = manager.get_or_create_user("new_or_create")

        assert user is not None
        assert user.user_id == "new_or_create"

    def test_get_or_create_user_existing(self, manager):
        """get_or_create_user returns existing user."""
        original = manager.create_user(
            user_id="existing_or_create",
            data={"username": "original"}
        )

        user = manager.get_or_create_user("existing_or_create")

        assert user.username == "original"

    def test_update_user(self, manager):
        """update_user updates user data."""
        manager.create_user(user_id="update_me", data={"username": "old"})

        manager.update_user("update_me", data={"username": "new"})

        user = manager.get_user("update_me")
        assert user.username == "new"

    def test_update_user_partial(self, manager):
        """update_user only updates provided fields."""
        manager.create_user(
            user_id="partial_update",
            data={
                "username": "original",
                "preferences": {"theme": "light", "lang": "en"}
            }
        )

        manager.update_user(
            "partial_update",
            data={"preferences": {"theme": "dark"}}
        )

        user = manager.get_user("partial_update")
        assert user.username == "original"  # Not changed
        assert user.preferences.get("theme") == "dark"  # Changed

    def test_update_user_not_exists(self, manager):
        """update_user raises error for nonexistent user."""
        from core.users.manager import UserNotFoundError

        with pytest.raises(UserNotFoundError):
            manager.update_user("ghost", data={"username": "casper"})

    def test_delete_user(self, manager):
        """delete_user removes user."""
        manager.create_user(user_id="delete_me")

        manager.delete_user("delete_me")

        assert manager.get_user("delete_me") is None

    def test_delete_user_not_exists(self, manager):
        """delete_user raises error for nonexistent user."""
        from core.users.manager import UserNotFoundError

        with pytest.raises(UserNotFoundError):
            manager.delete_user("never_existed")

    def test_list_users_empty(self, manager):
        """list_users returns empty list when no users."""
        users = manager.list_users()

        assert users == []

    def test_list_users_multiple(self, manager):
        """list_users returns all users."""
        manager.create_user(user_id="list1")
        manager.create_user(user_id="list2")
        manager.create_user(user_id="list3")

        users = manager.list_users()

        assert len(users) == 3
        user_ids = [u.user_id for u in users]
        assert "list1" in user_ids
        assert "list2" in user_ids
        assert "list3" in user_ids

    def test_ban_user(self, manager):
        """ban_user sets is_banned to True."""
        manager.create_user(user_id="ban_target")

        manager.ban_user("ban_target")

        user = manager.get_user("ban_target")
        assert user.is_banned is True

    def test_unban_user(self, manager):
        """unban_user sets is_banned to False."""
        manager.create_user(
            user_id="unban_target",
            data={"is_banned": True}
        )

        manager.unban_user("unban_target")

        user = manager.get_user("unban_target")
        assert user.is_banned is False

    def test_grant_admin(self, manager):
        """grant_admin sets is_admin to True."""
        manager.create_user(user_id="new_admin")

        manager.grant_admin("new_admin")

        user = manager.get_user("new_admin")
        assert user.is_admin is True

    def test_revoke_admin(self, manager):
        """revoke_admin sets is_admin to False."""
        manager.create_user(
            user_id="ex_admin",
            data={"is_admin": True}
        )

        manager.revoke_admin("ex_admin")

        user = manager.get_user("ex_admin")
        assert user.is_admin is False

    def test_user_count(self, manager):
        """user_count returns total number of users."""
        manager.create_user(user_id="count1")
        manager.create_user(user_id="count2")

        assert manager.user_count() == 2

    def test_get_admins(self, manager):
        """get_admins returns only admin users."""
        manager.create_user(user_id="admin1", data={"is_admin": True})
        manager.create_user(user_id="admin2", data={"is_admin": True})
        manager.create_user(user_id="regular")

        admins = manager.get_admins()

        assert len(admins) == 2
        admin_ids = [a.user_id for a in admins]
        assert "admin1" in admin_ids
        assert "admin2" in admin_ids
        assert "regular" not in admin_ids

    def test_get_banned_users(self, manager):
        """get_banned_users returns only banned users."""
        manager.create_user(user_id="banned1", data={"is_banned": True})
        manager.create_user(user_id="good_user")

        banned = manager.get_banned_users()

        assert len(banned) == 1
        assert banned[0].user_id == "banned1"

    def test_touch_user(self, manager):
        """touch_user updates last_seen timestamp."""
        import time

        manager.create_user(user_id="touch_test")
        user_before = manager.get_user("touch_test")
        original_last_seen = user_before.last_seen

        time.sleep(0.01)
        manager.touch_user("touch_test")

        user_after = manager.get_user("touch_test")
        assert user_after.last_seen > original_last_seen
