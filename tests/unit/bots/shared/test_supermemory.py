"""
Tests for bots/shared/supermemory.py

SuperMemory knowledge graph module for ClawdBot team.

Tests cover:
- Fact storage (remember)
- Relationships (update, extend, derive)
- Recall with keyword search and tag filtering
- Access control (can_read, can_write)
- Temporal reasoning (get_timeline)
- Edge cases
"""

import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from bots.shared.supermemory import SuperMemory


class TestRemember:
    """Test fact storage."""

    @pytest.fixture
    def sm(self, tmp_path):
        return SuperMemory("matt", db_path=str(tmp_path / "sm.db"))

    def test_remember_returns_fact_id(self, sm):
        fid = sm.remember("VPS IP is 76.13.106.100", "company_core")
        assert isinstance(fid, int)
        assert fid > 0

    def test_remember_stores_content(self, sm):
        sm.remember("VPS IP is 76.13.106.100", "company_core")
        results = sm.recall("VPS IP")
        assert len(results) >= 1
        assert "76.13.106.100" in results[0]["content"]

    def test_remember_stores_author(self, sm):
        sm.remember("test fact", "company_core")
        results = sm.recall("test fact")
        assert results[0]["author"] == "matt"

    def test_remember_with_event_date(self, sm):
        sm.remember("Server deployed", "ops_logs", event_date="2026-01-15")
        results = sm.recall("Server deployed")
        assert results[0]["event_date"] == "2026-01-15"

    def test_remember_sets_document_date(self, sm):
        sm.remember("test", "company_core")
        results = sm.recall("test")
        assert results[0]["document_date"] is not None

    def test_remember_respects_write_permissions(self, tmp_path):
        sm = SuperMemory("friday", db_path=str(tmp_path / "sm.db"))
        with pytest.raises(PermissionError):
            sm.remember("should fail", "technical_stack")

    def test_remember_allows_valid_write(self, tmp_path):
        sm = SuperMemory("jarvis", db_path=str(tmp_path / "sm.db"))
        fid = sm.remember("tech fact", "technical_stack")
        assert fid > 0


class TestUpdate:
    """Test Updates relationship."""

    @pytest.fixture
    def sm(self, tmp_path):
        s = SuperMemory("matt", db_path=str(tmp_path / "sm.db"))
        return s

    def test_update_returns_new_fact_id(self, sm):
        old_id = sm.remember("VPS IP is 1.1.1.1", "company_core")
        new_id = sm.update(old_id, "VPS IP is 76.13.106.100")
        assert new_id != old_id
        assert new_id > 0

    def test_update_supersedes_old_fact(self, sm):
        old_id = sm.remember("old fact", "company_core")
        sm.update(old_id, "new fact")
        results = sm.recall("old fact")
        # Old fact should not appear in recall (superseded)
        assert all(r["content"] != "old fact" for r in results)

    def test_update_creates_relationship(self, sm):
        old_id = sm.remember("old", "company_core")
        new_id = sm.update(old_id, "new")
        # New fact should be findable
        results = sm.recall("new")
        assert len(results) >= 1


class TestExtend:
    """Test Extends relationship."""

    @pytest.fixture
    def sm(self, tmp_path):
        return SuperMemory("matt", db_path=str(tmp_path / "sm.db"))

    def test_extend_returns_new_fact_id(self, sm):
        fid = sm.remember("VPS IP is 76.13.106.100", "company_core")
        ext_id = sm.extend(fid, "Tailscale IP is 100.72.121.115")
        assert ext_id > 0
        assert ext_id != fid

    def test_extend_preserves_original(self, sm):
        fid = sm.remember("original fact", "company_core")
        sm.extend(fid, "additional context")
        results = sm.recall("original fact")
        assert len(results) >= 1


class TestDerive:
    """Test Derives relationship."""

    @pytest.fixture
    def sm(self, tmp_path):
        return SuperMemory("matt", db_path=str(tmp_path / "sm.db"))

    def test_derive_returns_new_fact_id(self, sm):
        f1 = sm.remember("SOL price is $100", "company_core")
        f2 = sm.remember("ETH price is $3000", "company_core")
        d = sm.derive([f1, f2], "SOL/ETH ratio is 0.033")
        assert d > 0

    def test_derive_fact_is_recallable(self, sm):
        f1 = sm.remember("fact 1", "company_core")
        f2 = sm.remember("fact 2", "company_core")
        sm.derive([f1, f2], "derived inference")
        results = sm.recall("derived inference")
        assert len(results) >= 1


class TestRecall:
    """Test fact retrieval."""

    @pytest.fixture
    def sm(self, tmp_path):
        s = SuperMemory("matt", db_path=str(tmp_path / "sm.db"))
        s.remember("VPS IP is 76.13.106.100", "company_core")
        s.remember("Telegram bot token refreshed", "ops_logs")
        s.remember("New marketing campaign launched", "ops_logs")
        return s

    def test_recall_by_keyword(self, sm):
        results = sm.recall("VPS")
        assert len(results) >= 1

    def test_recall_with_tag_filter(self, sm):
        results = sm.recall("", tag="ops_logs")
        assert len(results) >= 2
        assert all(r["tag"] == "ops_logs" for r in results)

    def test_recall_with_limit(self, sm):
        results = sm.recall("", limit=1)
        assert len(results) == 1

    def test_recall_ordered_by_recency(self, sm):
        results = sm.recall("")
        dates = [r["document_date"] for r in results]
        assert dates == sorted(dates, reverse=True)

    def test_recall_respects_read_permissions(self, tmp_path):
        sm_jarvis = SuperMemory("jarvis", db_path=str(tmp_path / "sm.db"))
        sm_jarvis.remember("tech secret", "technical_stack")
        sm_friday = SuperMemory("friday", db_path=str(tmp_path / "sm.db"))
        results = sm_friday.recall("tech secret", tag="technical_stack")
        assert len(results) == 0

    def test_recall_empty_query_returns_recent(self, sm):
        results = sm.recall("")
        assert len(results) >= 1


class TestTimeline:
    """Test temporal reasoning."""

    @pytest.fixture
    def sm(self, tmp_path):
        s = SuperMemory("matt", db_path=str(tmp_path / "sm.db"))
        s.remember("Event A", "ops_logs", event_date="2026-01-01")
        s.remember("Event B", "ops_logs", event_date="2026-01-03")
        s.remember("Event C", "ops_logs", event_date="2026-01-02")
        return s

    def test_timeline_ordered_by_event_date(self, sm):
        timeline = sm.get_timeline(tag="ops_logs")
        dates = [t["event_date"] for t in timeline]
        assert dates == sorted(dates)

    def test_timeline_with_tag_filter(self, sm):
        sm.remember("Tech event", "company_core", event_date="2026-01-01")
        timeline = sm.get_timeline(tag="ops_logs")
        assert all(t["tag"] == "ops_logs" for t in timeline)

    def test_timeline_with_days_filter(self, sm):
        timeline = sm.get_timeline(days=7)
        assert isinstance(timeline, list)


class TestAccessControl:
    """Test can_read and can_write."""

    def test_matt_can_read_all(self, tmp_path):
        sm = SuperMemory("matt", db_path=str(tmp_path / "sm.db"))
        for tag in ["company_core", "technical_stack", "crypto_ops", "ops_logs"]:
            assert sm.can_read(tag) is True

    def test_friday_cannot_read_technical(self, tmp_path):
        sm = SuperMemory("friday", db_path=str(tmp_path / "sm.db"))
        assert sm.can_read("technical_stack") is False

    def test_jarvis_can_write_technical(self, tmp_path):
        sm = SuperMemory("jarvis", db_path=str(tmp_path / "sm.db"))
        assert sm.can_write("technical_stack") is True

    def test_matt_can_write_company_core(self, tmp_path):
        sm = SuperMemory("matt", db_path=str(tmp_path / "sm.db"))
        assert sm.can_write("company_core") is True

    def test_friday_cannot_write_company_core(self, tmp_path):
        sm = SuperMemory("friday", db_path=str(tmp_path / "sm.db"))
        assert sm.can_write("company_core") is False


class TestEdgeCases:
    """Test error handling."""

    def test_init_creates_db(self, tmp_path):
        db_path = str(tmp_path / "new.db")
        SuperMemory("matt", db_path=db_path)
        assert Path(db_path).exists()

    def test_init_creates_parent_dirs(self, tmp_path):
        db_path = str(tmp_path / "sub" / "dir" / "sm.db")
        SuperMemory("matt", db_path=db_path)
        assert Path(db_path).exists()

    def test_update_nonexistent_fact(self, tmp_path):
        sm = SuperMemory("matt", db_path=str(tmp_path / "sm.db"))
        with pytest.raises(ValueError):
            sm.update(9999, "new content")

    def test_extend_nonexistent_fact(self, tmp_path):
        sm = SuperMemory("matt", db_path=str(tmp_path / "sm.db"))
        with pytest.raises(ValueError):
            sm.extend(9999, "extension")

    def test_derive_empty_sources(self, tmp_path):
        sm = SuperMemory("matt", db_path=str(tmp_path / "sm.db"))
        with pytest.raises(ValueError):
            sm.derive([], "inference")

    def test_case_insensitive_bot_name(self, tmp_path):
        sm = SuperMemory("Matt", db_path=str(tmp_path / "sm.db"))
        assert sm.can_write("company_core") is True
