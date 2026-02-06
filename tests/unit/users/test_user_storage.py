"""
Tests for User storage (core/users/storage.py)

Tests the UserStorage abstract class and JSONUserStorage implementation:
- load_users() -> Dict
- save_user(user)
- File-based JSON storage
"""

import pytest
import json
import tempfile
from pathlib import Path
from datetime import datetime


class TestUserStorageAbstract:
    """Tests for UserStorage abstract class."""

    def test_storage_is_abstract(self):
        """UserStorage cannot be instantiated directly."""
        from core.users.storage import UserStorage

        with pytest.raises(TypeError):
            UserStorage()

    def test_storage_defines_required_methods(self):
        """UserStorage defines required abstract methods."""
        from core.users.storage import UserStorage
        import inspect

        # Check abstract methods exist
        assert hasattr(UserStorage, 'load_users')
        assert hasattr(UserStorage, 'save_user')
        assert hasattr(UserStorage, 'delete_user')
        assert hasattr(UserStorage, 'get_user')


class TestJSONUserStorage:
    """Tests for JSONUserStorage implementation."""

    @pytest.fixture
    def temp_storage_dir(self, tmp_path):
        """Create a temporary storage directory."""
        storage_dir = tmp_path / "users"
        storage_dir.mkdir()
        return storage_dir

    @pytest.fixture
    def storage(self, temp_storage_dir):
        """Create JSONUserStorage with temp directory."""
        from core.users.storage import JSONUserStorage

        return JSONUserStorage(storage_path=temp_storage_dir)

    def test_json_storage_creation(self, temp_storage_dir):
        """JSONUserStorage can be created with a path."""
        from core.users.storage import JSONUserStorage

        storage = JSONUserStorage(storage_path=temp_storage_dir)

        assert storage.storage_path == temp_storage_dir

    def test_json_storage_creates_directory(self, tmp_path):
        """JSONUserStorage creates directory if it does not exist."""
        from core.users.storage import JSONUserStorage

        new_dir = tmp_path / "new_users_dir"
        storage = JSONUserStorage(storage_path=new_dir)

        assert new_dir.exists()

    def test_load_users_empty(self, storage):
        """load_users returns empty dict when no users exist."""
        users = storage.load_users()

        assert users == {}

    def test_save_and_load_user(self, storage):
        """User can be saved and loaded back."""
        from core.users.model import User

        user = User(
            user_id="save_test",
            username="saver",
            preferences={"color": "blue"}
        )

        storage.save_user(user)
        loaded = storage.get_user("save_test")

        assert loaded is not None
        assert loaded.user_id == "save_test"
        assert loaded.username == "saver"
        assert loaded.preferences == {"color": "blue"}

    def test_save_user_creates_file(self, storage, temp_storage_dir):
        """save_user creates a JSON file for the user."""
        from core.users.model import User

        user = User(user_id="file_test")
        storage.save_user(user)

        user_file = temp_storage_dir / "file_test.json"
        assert user_file.exists()

    def test_load_users_multiple(self, storage):
        """load_users returns all saved users."""
        from core.users.model import User

        user1 = User(user_id="multi1", username="first")
        user2 = User(user_id="multi2", username="second")
        user3 = User(user_id="multi3", username="third")

        storage.save_user(user1)
        storage.save_user(user2)
        storage.save_user(user3)

        users = storage.load_users()

        assert len(users) == 3
        assert "multi1" in users
        assert "multi2" in users
        assert "multi3" in users

    def test_delete_user(self, storage):
        """delete_user removes user from storage."""
        from core.users.model import User

        user = User(user_id="delete_me")
        storage.save_user(user)

        assert storage.get_user("delete_me") is not None

        storage.delete_user("delete_me")

        assert storage.get_user("delete_me") is None

    def test_delete_nonexistent_user(self, storage):
        """delete_user does not raise for nonexistent user."""
        # Should not raise
        storage.delete_user("does_not_exist")

    def test_get_user_nonexistent(self, storage):
        """get_user returns None for nonexistent user."""
        result = storage.get_user("nonexistent")

        assert result is None

    def test_update_existing_user(self, storage):
        """save_user updates existing user."""
        from core.users.model import User

        user = User(user_id="update_test", username="original")
        storage.save_user(user)

        user.username = "updated"
        storage.save_user(user)

        loaded = storage.get_user("update_test")
        assert loaded.username == "updated"

    def test_user_data_persistence(self, temp_storage_dir):
        """User data persists across storage instances."""
        from core.users.storage import JSONUserStorage
        from core.users.model import User

        # First instance
        storage1 = JSONUserStorage(storage_path=temp_storage_dir)
        user = User(user_id="persist_test", username="persistent")
        storage1.save_user(user)

        # New instance
        storage2 = JSONUserStorage(storage_path=temp_storage_dir)
        loaded = storage2.get_user("persist_test")

        assert loaded is not None
        assert loaded.username == "persistent"

    def test_handles_corrupted_file(self, storage, temp_storage_dir):
        """Storage handles corrupted JSON files gracefully."""
        # Create a corrupted file
        corrupted_file = temp_storage_dir / "corrupted.json"
        corrupted_file.write_text("not valid json {{{")

        # Should not raise, should skip corrupted file
        users = storage.load_users()

        # Corrupted user should not be in results
        assert "corrupted" not in users

    def test_user_id_sanitization(self, storage, temp_storage_dir):
        """User IDs are sanitized for file names."""
        from core.users.model import User

        # User ID with special characters
        user = User(user_id="user@test.com", username="email_user")
        storage.save_user(user)

        # Should be retrievable
        loaded = storage.get_user("user@test.com")
        assert loaded is not None
        assert loaded.username == "email_user"
