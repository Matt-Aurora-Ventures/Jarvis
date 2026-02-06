"""Tests for Memory Guard."""

import json
import os
import tempfile
import pytest
from pathlib import Path

from bots.shared.memory_guard import MemoryGuard


class TestMemoryGuard:
    """Tests for MemoryGuard."""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.guard = MemoryGuard(
            data_dir=self.tmpdir,
            limits={"max_memories_per_bot": 100, "max_conversation_history": 5, "max_memory_age_days": 30},
        )

    def _make_bot_memory(self, bot_name: str, count: int):
        """Create a bot memory dir with N entries."""
        mem_dir = Path(self.tmpdir) / "memory" / bot_name
        mem_dir.mkdir(parents=True, exist_ok=True)
        for i in range(count):
            entry = {
                "messages": [{"role": "user", "content": f"msg {j}", "timestamp": f"2025-01-0{min(j+1,9)}T00:00:00Z"} for j in range(8)],
                "last_access": "2025-01-10T00:00:00Z",
            }
            (mem_dir / f"user{i}.json").write_text(json.dumps(entry))

    def _make_state_file(self, name: str, size_bytes: int):
        """Create a state file of given size."""
        path = Path(self.tmpdir) / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("x" * size_bytes)

    # Health check
    def test_check_health_empty(self):
        result = self.guard.check_health()
        assert "warnings" in result
        assert "stats" in result

    def test_check_health_with_data(self):
        self._make_bot_memory("friday", 5)
        result = self.guard.check_health()
        assert "stats" in result

    # Enforce limits
    def test_enforce_limits_under_quota(self):
        self._make_bot_memory("jarvis", 3)
        result = self.guard.enforce_limits("jarvis")
        assert "actions" in result

    def test_enforce_limits_over_quota(self):
        self._make_bot_memory("jarvis", 150)
        result = self.guard.enforce_limits("jarvis")
        # Should have pruned some
        remaining = len(list((Path(self.tmpdir) / "memory" / "jarvis").glob("*.json")))
        assert remaining <= 100

    # Compress conversations
    def test_compress_conversations(self):
        self._make_bot_memory("friday", 3)
        trimmed = self.guard.compress_conversations("friday")
        # Each had 8 messages, limit is 5 - should trim
        assert trimmed > 0
        for f in (Path(self.tmpdir) / "memory" / "friday").glob("*.json"):
            data = json.loads(f.read_text())
            assert len(data["messages"]) <= 5

    def test_compress_conversations_already_under_limit(self):
        mem_dir = Path(self.tmpdir) / "memory" / "matt"
        mem_dir.mkdir(parents=True, exist_ok=True)
        entry = {"messages": [{"role": "user", "content": "hi"}], "last_access": "2025-01-10T00:00:00Z"}
        (mem_dir / "user0.json").write_text(json.dumps(entry))
        trimmed = self.guard.compress_conversations("matt")
        assert trimmed == 0

    # Deduplication
    def test_deduplicate_removes_near_duplicates(self):
        mem_dir = Path(self.tmpdir) / "memory" / "friday"
        mem_dir.mkdir(parents=True, exist_ok=True)
        base = {"messages": [{"role": "user", "content": "hello world how are you doing today"}], "last_access": "2025-01-10T00:00:00Z"}
        # Write two nearly identical files
        (mem_dir / "user0.json").write_text(json.dumps(base))
        dup = {"messages": [{"role": "user", "content": "hello world how are you doing today"}], "last_access": "2025-01-09T00:00:00Z"}
        (mem_dir / "user1.json").write_text(json.dumps(dup))
        removed = self.guard.deduplicate("friday")
        assert removed >= 1

    def test_deduplicate_keeps_different_entries(self):
        mem_dir = Path(self.tmpdir) / "memory" / "friday"
        mem_dir.mkdir(parents=True, exist_ok=True)
        (mem_dir / "user0.json").write_text(json.dumps({"messages": [{"role": "user", "content": "hello"}], "last_access": "2025-01-10T00:00:00Z"}))
        (mem_dir / "user1.json").write_text(json.dumps({"messages": [{"role": "user", "content": "completely different topic about trading"}], "last_access": "2025-01-10T00:00:00Z"}))
        removed = self.guard.deduplicate("friday")
        assert removed == 0

    # File size checks
    def test_check_file_sizes(self):
        self._make_state_file("state.json", 100)
        result = self.guard.check_file_sizes()
        assert isinstance(result, list)

    def test_check_file_sizes_warns_on_large(self):
        self._make_state_file("big_state.json", 11 * 1024 * 1024)  # 11MB
        result = self.guard.check_file_sizes()
        warnings = [r for r in result if r.get("warning")]
        assert len(warnings) >= 1

    # Stats
    def test_get_memory_stats(self):
        self._make_bot_memory("jarvis", 3)
        self._make_bot_memory("friday", 5)
        stats = self.guard.get_memory_stats()
        assert "jarvis" in stats
        assert "friday" in stats
        assert stats["jarvis"]["file_count"] == 3
        assert stats["friday"]["file_count"] == 5

    def test_get_memory_stats_empty(self):
        stats = self.guard.get_memory_stats()
        assert isinstance(stats, dict)

    # Prune old entries
    def test_prune_old_entries(self):
        mem_dir = Path(self.tmpdir) / "memory" / "jarvis"
        mem_dir.mkdir(parents=True, exist_ok=True)
        old = {"messages": [], "last_access": "2024-01-01T00:00:00Z"}
        (mem_dir / "old_user.json").write_text(json.dumps(old))
        new = {"messages": [], "last_access": "2026-01-30T00:00:00Z"}
        (mem_dir / "new_user.json").write_text(json.dumps(new))
        pruned = self.guard.prune_old_entries("jarvis")
        assert pruned >= 1
        assert not (mem_dir / "old_user.json").exists()
        assert (mem_dir / "new_user.json").exists()

    # Graceful with missing dirs
    def test_nonexistent_bot_no_crash(self):
        result = self.guard.enforce_limits("nonexistent_bot")
        assert "actions" in result

    def test_compress_nonexistent_bot(self):
        trimmed = self.guard.compress_conversations("nonexistent")
        assert trimmed == 0

    def test_deduplicate_nonexistent_bot(self):
        removed = self.guard.deduplicate("nonexistent")
        assert removed == 0
