"""
Tests for bots/shared/memory_tags.py

Tag-based access control for memory between ClawdBots.

Tests cover:
- Permission checking (read/write)
- Tag listing per bot
- Default tag permissions
- Edge cases (unknown tags, unknown bots)
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from bots.shared.memory_tags import MemoryTagManager


class TestReadPermissions:
    """Test read access control."""

    @pytest.fixture
    def mgr(self):
        return MemoryTagManager()

    def test_matt_reads_company_core(self, mgr):
        assert mgr.can_read("matt", "company_core") is True

    def test_friday_reads_company_core(self, mgr):
        assert mgr.can_read("friday", "company_core") is True

    def test_jarvis_reads_company_core(self, mgr):
        assert mgr.can_read("jarvis", "company_core") is True

    def test_jarvis_reads_technical_stack(self, mgr):
        assert mgr.can_read("jarvis", "technical_stack") is True

    def test_friday_cannot_read_technical_stack(self, mgr):
        assert mgr.can_read("friday", "technical_stack") is False

    def test_friday_reads_marketing_creative(self, mgr):
        assert mgr.can_read("friday", "marketing_creative") is True

    def test_jarvis_cannot_read_marketing_creative(self, mgr):
        assert mgr.can_read("jarvis", "marketing_creative") is False

    def test_jarvis_reads_crypto_ops(self, mgr):
        assert mgr.can_read("jarvis", "crypto_ops") is True

    def test_friday_cannot_read_crypto_ops(self, mgr):
        assert mgr.can_read("friday", "crypto_ops") is False

    def test_all_read_ops_logs(self, mgr):
        for bot in ["matt", "friday", "jarvis"]:
            assert mgr.can_read(bot, "ops_logs") is True

    def test_unknown_tag_returns_false(self, mgr):
        assert mgr.can_read("matt", "nonexistent_tag") is False

    def test_unknown_bot_returns_false(self, mgr):
        assert mgr.can_read("unknown_bot", "company_core") is False


class TestWritePermissions:
    """Test write access control."""

    @pytest.fixture
    def mgr(self):
        return MemoryTagManager()

    def test_matt_writes_company_core(self, mgr):
        assert mgr.can_write("matt", "company_core") is True

    def test_friday_cannot_write_company_core(self, mgr):
        assert mgr.can_write("friday", "company_core") is False

    def test_jarvis_writes_technical_stack(self, mgr):
        assert mgr.can_write("jarvis", "technical_stack") is True

    def test_matt_cannot_write_technical_stack(self, mgr):
        assert mgr.can_write("matt", "technical_stack") is False

    def test_friday_writes_marketing_creative(self, mgr):
        assert mgr.can_write("friday", "marketing_creative") is True

    def test_jarvis_writes_crypto_ops(self, mgr):
        assert mgr.can_write("jarvis", "crypto_ops") is True

    def test_matt_writes_ops_logs(self, mgr):
        assert mgr.can_write("matt", "ops_logs") is True

    def test_friday_cannot_write_ops_logs(self, mgr):
        assert mgr.can_write("friday", "ops_logs") is False

    def test_unknown_tag_write_returns_false(self, mgr):
        assert mgr.can_write("matt", "nonexistent") is False


class TestAccessibleTags:
    """Test tag listing."""

    @pytest.fixture
    def mgr(self):
        return MemoryTagManager()

    def test_matt_accessible_tags(self, mgr):
        tags = mgr.get_accessible_tags("matt")
        assert "company_core" in tags
        assert "technical_stack" in tags
        assert "ops_logs" in tags
        assert "crypto_ops" in tags

    def test_friday_accessible_tags(self, mgr):
        tags = mgr.get_accessible_tags("friday")
        assert "company_core" in tags
        assert "marketing_creative" in tags
        assert "ops_logs" in tags
        assert "technical_stack" not in tags
        assert "crypto_ops" not in tags

    def test_jarvis_accessible_tags(self, mgr):
        tags = mgr.get_accessible_tags("jarvis")
        assert "company_core" in tags
        assert "technical_stack" in tags
        assert "crypto_ops" in tags
        assert "ops_logs" in tags
        assert "marketing_creative" not in tags

    def test_unknown_bot_no_tags(self, mgr):
        tags = mgr.get_accessible_tags("unknown")
        assert tags == []
