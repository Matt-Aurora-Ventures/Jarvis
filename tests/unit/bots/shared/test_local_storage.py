"""Tests for LocalMemoryStore - SQLite local storage with optional encryption."""

import json
import os
import sqlite3
import tempfile
import time

import pytest

# Will be created
from bots.shared.local_storage import LocalMemoryStore


@pytest.fixture
def tmp_db(tmp_path):
    """Return a temp DB path."""
    return str(tmp_path / "test_memory.db")


@pytest.fixture
def store(tmp_db):
    """Plain store without encryption."""
    return LocalMemoryStore(db_path=tmp_db)


@pytest.fixture
def encrypted_store(tmp_db):
    """Store with encryption key."""
    return LocalMemoryStore(db_path=tmp_db, encryption_key="test-secret-key")


class TestInit:
    def test_creates_db_file(self, tmp_db):
        store = LocalMemoryStore(db_path=tmp_db)
        assert os.path.exists(tmp_db)

    def test_creates_parent_dirs(self, tmp_path):
        db_path = str(tmp_path / "nested" / "dir" / "mem.db")
        store = LocalMemoryStore(db_path=db_path)
        assert os.path.exists(db_path)

    def test_tables_created(self, tmp_db):
        store = LocalMemoryStore(db_path=tmp_db)
        conn = sqlite3.connect(tmp_db)
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cursor.fetchall()}
        conn.close()
        assert "credentials" in tables
        assert "preferences" in tables
        assert "strategies" in tables
        assert "event_log" in tables
        assert "cache" in tables


class TestCredentials:
    def test_store_and_get(self, store):
        store.store_credential("api_key", "sk-12345")
        assert store.get_credential("api_key") == "sk-12345"

    def test_get_nonexistent(self, store):
        assert store.get_credential("nope") is None

    def test_bot_scoping(self, store):
        store.store_credential("token", "aaa", bot="bot1")
        store.store_credential("token", "bbb", bot="bot2")
        assert store.get_credential("token", bot="bot1") == "aaa"
        assert store.get_credential("token", bot="bot2") == "bbb"

    def test_list_credentials(self, store):
        store.store_credential("key1", "v1", bot="b1")
        store.store_credential("key2", "v2", bot="b1")
        store.store_credential("key3", "v3", bot="b2")
        names = store.list_credentials(bot="b1")
        assert set(names) == {"key1", "key2"}

    def test_list_all_credentials(self, store):
        store.store_credential("a", "1", bot="x")
        store.store_credential("b", "2", bot="y")
        names = store.list_credentials()
        assert len(names) >= 2

    def test_delete_credential(self, store):
        store.store_credential("temp", "val")
        assert store.delete_credential("temp") is True
        assert store.get_credential("temp") is None

    def test_delete_nonexistent(self, store):
        assert store.delete_credential("nope") is False

    def test_upsert_credential(self, store):
        store.store_credential("k", "v1")
        store.store_credential("k", "v2")
        assert store.get_credential("k") == "v2"


class TestCredentialsEncrypted:
    def test_encrypted_store_and_get(self, encrypted_store):
        encrypted_store.store_credential("secret", "my-password")
        assert encrypted_store.get_credential("secret") == "my-password"

    def test_encrypted_value_not_plaintext(self, encrypted_store, tmp_db):
        encrypted_store.store_credential("secret", "plaintext-value")
        # Read raw DB - value should NOT be plaintext
        conn = sqlite3.connect(tmp_db)
        row = conn.execute("SELECT value FROM credentials WHERE name='secret'").fetchone()
        conn.close()
        assert row[0] != "plaintext-value"

    def test_wrong_key_cannot_decrypt(self, tmp_db):
        s1 = LocalMemoryStore(db_path=tmp_db, encryption_key="key1")
        s1.store_credential("x", "secret-data")
        s2 = LocalMemoryStore(db_path=tmp_db, encryption_key="key2")
        # Should return None or raise - not the original value
        result = s2.get_credential("x")
        assert result is None


class TestPreferences:
    def test_set_and_get(self, store):
        store.set_preference("theme", "dark")
        assert store.get_preference("theme") == "dark"

    def test_default_value(self, store):
        assert store.get_preference("missing", default="light") == "light"

    def test_complex_value(self, store):
        val = {"nested": [1, 2, 3], "flag": True}
        store.set_preference("config", val)
        assert store.get_preference("config") == val

    def test_bot_scoping(self, store):
        store.set_preference("mode", "fast", bot="a")
        store.set_preference("mode", "slow", bot="b")
        assert store.get_preference("mode", bot="a") == "fast"

    def test_get_all_preferences(self, store):
        store.set_preference("k1", "v1", bot="bot")
        store.set_preference("k2", "v2", bot="bot")
        prefs = store.get_all_preferences(bot="bot")
        assert prefs == {"k1": "v1", "k2": "v2"}

    def test_upsert(self, store):
        store.set_preference("x", 1)
        store.set_preference("x", 2)
        assert store.get_preference("x") == 2


class TestStrategies:
    def test_save_and_get(self, store):
        strat = {"type": "momentum", "params": {"window": 20}}
        store.save_strategy("mom20", strat, bot="trader")
        result = store.get_strategy("mom20", bot="trader")
        assert result == strat

    def test_get_nonexistent(self, store):
        assert store.get_strategy("nope", bot="x") is None

    def test_list_strategies(self, store):
        store.save_strategy("s1", {"a": 1}, bot="b1")
        store.save_strategy("s2", {"b": 2}, bot="b1")
        result = store.list_strategies(bot="b1")
        assert len(result) == 2
        names = {s["name"] for s in result}
        assert names == {"s1", "s2"}

    def test_list_all(self, store):
        store.save_strategy("x", {}, bot="a")
        store.save_strategy("y", {}, bot="b")
        result = store.list_strategies()
        assert len(result) >= 2

    def test_upsert(self, store):
        store.save_strategy("s", {"v": 1}, bot="b")
        store.save_strategy("s", {"v": 2}, bot="b")
        assert store.get_strategy("s", bot="b") == {"v": 2}


class TestEventLog:
    def test_log_and_get(self, store):
        store.log_event("trade", {"symbol": "SOL", "amount": 10}, bot="trader")
        events = store.get_events(event_type="trade")
        assert len(events) == 1
        assert events[0]["data"]["symbol"] == "SOL"

    def test_filter_by_bot(self, store):
        store.log_event("ping", {}, bot="a")
        store.log_event("ping", {}, bot="b")
        events = store.get_events(bot="a")
        assert len(events) == 1

    def test_limit(self, store):
        for i in range(10):
            store.log_event("tick", {"i": i})
        events = store.get_events(limit=3)
        assert len(events) == 3

    def test_prune_events(self, store):
        store.log_event("old", {"x": 1})
        # Manually backdate the event
        conn = sqlite3.connect(store.db_path)
        conn.execute("UPDATE event_log SET timestamp = datetime('now', '-60 days')")
        conn.commit()
        conn.close()
        pruned = store.prune_events(older_than_days=30)
        assert pruned >= 1
        assert len(store.get_events()) == 0


class TestCache:
    def test_set_and_get(self, store):
        store.cache_set("k", {"data": 42})
        assert store.cache_get("k") == {"data": 42}

    def test_ttl_expiry(self, store):
        store.cache_set("short", "val", ttl_seconds=1)
        time.sleep(1.1)
        assert store.cache_get("short") is None

    def test_cache_clear_all(self, store):
        store.cache_set("a", 1)
        store.cache_set("b", 2)
        cleared = store.cache_clear()
        assert cleared >= 2
        assert store.cache_get("a") is None

    def test_cache_clear_pattern(self, store):
        store.cache_set("api:users", 1)
        store.cache_set("api:posts", 2)
        store.cache_set("other", 3)
        cleared = store.cache_clear(pattern="api:%")
        assert cleared == 2
        assert store.cache_get("other") == 3


class TestBackupRestore:
    def test_backup_creates_file(self, store, tmp_path):
        store.set_preference("x", "y")
        backup_path = store.backup(str(tmp_path / "backup.db"))
        assert os.path.exists(backup_path)

    def test_restore(self, store, tmp_path):
        store.set_preference("key", "value")
        backup_path = store.backup(str(tmp_path / "backup.db"))
        # Create fresh store
        new_db = str(tmp_path / "new.db")
        new_store = LocalMemoryStore(db_path=new_db)
        assert new_store.get_preference("key") is None
        new_store.restore(backup_path)
        assert new_store.get_preference("key") == "value"


class TestStats:
    def test_get_stats(self, store):
        store.store_credential("c", "v")
        store.set_preference("p", "v")
        store.log_event("e", {})
        stats = store.get_stats()
        assert stats["credentials"] >= 1
        assert stats["preferences"] >= 1
        assert stats["events"] >= 1
        assert "db_size_bytes" in stats
