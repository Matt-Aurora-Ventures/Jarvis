"""Tests for bots.shared.memory_management."""

import json
import pytest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch

from bots.shared.memory_management import MemoryManager


@pytest.fixture
def mm(tmp_path):
    return MemoryManager(data_dir=str(tmp_path), max_log_days=7)


class TestInit:
    def test_creates_memory_dir(self, mm):
        assert mm.logs_dir.exists()

    def test_custom_max_log_days(self, tmp_path):
        m = MemoryManager(data_dir=str(tmp_path), max_log_days=3)
        assert m.max_log_days == 3


class TestRotateLogs:
    def test_rotates_session_entries(self, mm):
        session_file = mm.data_dir / "session_log.json"
        entries = [{"content": "hello"}, {"content": "world"}]
        session_file.write_text(json.dumps(entries))

        mm.rotate_logs()

        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        log_file = mm.logs_dir / f"{today}.json"
        assert json.loads(log_file.read_text()) == entries
        assert json.loads(session_file.read_text()) == []

    def test_appends_to_existing_daily_log(self, mm):
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        log_file = mm.logs_dir / f"{today}.json"
        log_file.write_text(json.dumps([{"content": "old"}]))

        session_file = mm.data_dir / "session_log.json"
        session_file.write_text(json.dumps([{"content": "new"}]))

        mm.rotate_logs()

        result = json.loads(log_file.read_text())
        assert len(result) == 2

    def test_no_session_file_no_error(self, mm):
        mm.rotate_logs()  # Should not raise


class TestCleanupOldLogs:
    def test_removes_old_logs(self, mm):
        old_date = (datetime.now(timezone.utc) - timedelta(days=10)).strftime("%Y-%m-%d")
        old_file = mm.logs_dir / f"{old_date}.json"
        old_file.write_text("[]")

        mm._cleanup_old_logs()

        assert not old_file.exists()

    def test_keeps_recent_logs(self, mm):
        recent_date = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
        recent_file = mm.logs_dir / f"{recent_date}.json"
        recent_file.write_text("[]")

        mm._cleanup_old_logs()

        assert recent_file.exists()

    def test_skips_non_date_files(self, mm):
        bad_file = mm.logs_dir / "notes.json"
        bad_file.write_text("[]")

        mm._cleanup_old_logs()  # Should not raise

        assert bad_file.exists()


class TestCompactMemory:
    def test_reads_last_two_days(self, mm):
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")

        (mm.logs_dir / f"{today}.json").write_text(json.dumps([{"content": "a"}]))
        (mm.logs_dir / f"{yesterday}.json").write_text(json.dumps([{"content": "b"}, {"content": "c"}]))

        result = mm.compact_memory()
        assert "3 entries" in result


class TestStripHandoffHistory:
    def test_keeps_essential_fields(self, mm):
        data = {
            "task": "do thing",
            "context": "some ctx",
            "key_facts": ["fact1"],
            "conversation_history": ["msg1", "msg2"],
            "raw_responses": [{"big": "data"}],
            "full_logs": "lots of text",
        }
        result = mm.strip_handoff_history(data)

        assert result["task"] == "do thing"
        assert result["context"] == "some ctx"
        assert result["key_facts"] == ["fact1"]
        assert "timestamp" in result
        assert "conversation_history" not in result
        assert "raw_responses" not in result
        assert "full_logs" not in result


class TestGetRelevantMemory:
    def test_finds_matching_entries(self, mm):
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        entries = [
            {"content": "trading sol tokens"},
            {"content": "weather update"},
        ]
        (mm.logs_dir / f"{today}.json").write_text(json.dumps(entries))

        results = mm.get_relevant_memory("trading")
        assert len(results) == 1
        assert "trading" in results[0]["content"]

    def test_respects_max_age(self, mm):
        old_date = (datetime.now(timezone.utc) - timedelta(days=10)).strftime("%Y-%m-%d")
        (mm.logs_dir / f"{old_date}.json").write_text(
            json.dumps([{"content": "trading old"}])
        )

        results = mm.get_relevant_memory("trading", max_age_days=3)
        assert len(results) == 0


class TestGetStats:
    def test_returns_stats(self, mm):
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        (mm.logs_dir / f"{today}.json").write_text(json.dumps([{"x": 1}]))

        stats = mm.get_stats()
        assert stats["log_files"] == 1
        assert stats["total_size_kb"] >= 0
        assert stats["newest_log"] == today

    def test_empty_stats(self, mm):
        stats = mm.get_stats()
        assert stats["log_files"] == 0
        assert stats["oldest_log"] == "none"
