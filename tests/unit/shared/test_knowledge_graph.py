"""Tests for bots.shared.knowledge_graph."""

import json
import os
import sqlite3
import tempfile

import pytest

from bots.shared.knowledge_graph import KnowledgeGraph, seed_initial_entities


@pytest.fixture
def tmp_db(tmp_path):
    return str(tmp_path / "test_kg.db")


@pytest.fixture
def kg(tmp_db):
    return KnowledgeGraph(db_path=tmp_db)


class TestAddEntity:
    def test_add_new_entity(self, kg):
        eid = kg.add_entity("Alice", "person", {"role": "dev"})
        assert isinstance(eid, int)
        assert eid > 0

    def test_add_entity_merge_properties(self, kg):
        kg.add_entity("Alice", "person", {"role": "dev"})
        kg.add_entity("Alice", "person", {"team": "infra"})
        entity = kg.get_entity("Alice")
        assert entity is not None
        assert entity["properties"]["role"] == "dev"
        assert entity["properties"]["team"] == "infra"

    def test_add_entity_with_tags(self, kg):
        eid = kg.add_entity("Alice", "person", {"role": "dev"}, tags=["team", "eng"])
        entity = kg.get_entity("Alice")
        assert entity is not None
        assert "team" in entity.get("tags", [])


class TestGetEntity:
    def test_get_existing(self, kg):
        kg.add_entity("Bob", "person", {"age": 30})
        result = kg.get_entity("Bob")
        assert result is not None
        assert result["name"] == "Bob"
        assert result["type"] == "person"
        assert result["properties"]["age"] == 30

    def test_get_nonexistent(self, kg):
        result = kg.get_entity("Nobody")
        assert result is None


class TestAddRelationship:
    def test_basic_relationship(self, kg):
        kg.add_entity("A", "node")
        kg.add_entity("B", "node")
        rid = kg.add_relationship("A", "B", "CONNECTS")
        assert isinstance(rid, int)

    def test_auto_creates_entities(self, kg):
        rid = kg.add_relationship("X", "Y", "LINKS")
        assert rid > 0
        assert kg.get_entity("X") is not None
        assert kg.get_entity("Y") is not None


class TestGetRelated:
    def test_outgoing(self, kg):
        kg.add_entity("Parent", "person")
        kg.add_entity("Child", "person")
        kg.add_relationship("Parent", "Child", "OWNS")
        related = kg.get_related("Parent", direction="outgoing")
        assert len(related) == 1
        assert related[0]["name"] == "Child"

    def test_incoming(self, kg):
        kg.add_entity("Parent", "person")
        kg.add_entity("Child", "person")
        kg.add_relationship("Parent", "Child", "OWNS")
        related = kg.get_related("Child", direction="incoming")
        assert len(related) == 1
        assert related[0]["name"] == "Parent"

    def test_filter_by_rel_type(self, kg):
        kg.add_entity("A", "node")
        kg.add_entity("B", "node")
        kg.add_entity("C", "node")
        kg.add_relationship("A", "B", "OWNS")
        kg.add_relationship("A", "C", "MANAGES")
        related = kg.get_related("A", rel_type="OWNS")
        assert len(related) == 1
        assert related[0]["name"] == "B"

    def test_nonexistent_entity(self, kg):
        assert kg.get_related("Ghost") == []


class TestSearch:
    def test_search_by_name(self, kg):
        kg.add_entity("Trading Bot", "project", {"chain": "solana"})
        results = kg.search("Trading")
        assert any(r["name"] == "Trading Bot" for r in results)

    def test_search_no_results(self, kg):
        results = kg.search("nonexistent_xyz_abc")
        assert results == []


class TestUpdateFact:
    def test_creates_snapshot(self, kg):
        kg.add_entity("Server", "infra", {"status": "running"})
        kg.update_fact("Server", {"status": "stopped"})
        entity = kg.get_entity("Server")
        assert entity["properties"]["status"] == "stopped"
        history = kg.get_entity_history("Server")
        assert len(history) >= 2

    def test_nonexistent_entity(self, kg):
        # Should not raise
        kg.update_fact("Ghost", {"x": 1})


class TestExtendFact:
    def test_adds_without_replacing(self, kg):
        kg.add_entity("Bot", "bot", {"version": "1.0"})
        kg.extend_fact("Bot", {"uptime": "99%"})
        entity = kg.get_entity("Bot")
        assert entity["properties"]["version"] == "1.0"
        assert entity["properties"]["uptime"] == "99%"

    def test_nonexistent_entity(self, kg):
        kg.extend_fact("Ghost", {"x": 1})


class TestDeriveFact:
    def test_creates_derived_entity(self, kg):
        kg.add_entity("Sales", "metric", {"q1": 100})
        kg.add_entity("Costs", "metric", {"q1": 50})
        kg.derive_fact(["Sales", "Costs"], "Profit", "derived_metric", "Sales - Costs")
        entity = kg.get_entity("Profit")
        assert entity is not None
        assert entity["properties"]["reasoning"] == "Sales - Costs"


class TestGetEntityHistory:
    def test_history_chain(self, kg):
        kg.add_entity("Config", "config", {"v": 1})
        kg.update_fact("Config", {"v": 2})
        kg.update_fact("Config", {"v": 3})
        history = kg.get_entity_history("Config")
        assert len(history) >= 3

    def test_nonexistent(self, kg):
        assert kg.get_entity_history("Ghost") == []


class TestExportGraph:
    def test_export_structure(self, kg):
        kg.add_entity("A", "node")
        kg.add_entity("B", "node")
        kg.add_relationship("A", "B", "LINKS")
        export = kg.export_graph()
        assert "entities" in export
        assert "relationships" in export
        assert len(export["entities"]) >= 2
        assert len(export["relationships"]) >= 1


class TestSeedInitialEntities:
    def test_seed(self, tmp_db):
        kg = seed_initial_entities(db_path=tmp_db)
        daryl = kg.get_entity("Daryl")
        assert daryl is not None
        assert daryl["properties"]["role"] == "founder"
        related = kg.get_related("Daryl", rel_type="OWNS")
        assert len(related) == 3


class TestMemoryTags:
    """Tests for bots.shared.memory_tags."""

    def test_can_read_valid(self):
        from bots.shared.memory_tags import MemoryTagManager
        mgr = MemoryTagManager()
        assert mgr.can_read("matt", "company_core") is True
        assert mgr.can_read("friday", "company_core") is True
        assert mgr.can_read("jarvis", "company_core") is True

    def test_can_read_invalid(self):
        from bots.shared.memory_tags import MemoryTagManager
        mgr = MemoryTagManager()
        assert mgr.can_read("friday", "technical_stack") is False

    def test_can_write_valid(self):
        from bots.shared.memory_tags import MemoryTagManager
        mgr = MemoryTagManager()
        assert mgr.can_write("jarvis", "technical_stack") is True
        assert mgr.can_write("friday", "marketing_creative") is True

    def test_can_write_invalid(self):
        from bots.shared.memory_tags import MemoryTagManager
        mgr = MemoryTagManager()
        assert mgr.can_write("friday", "technical_stack") is False

    def test_unknown_tag(self):
        from bots.shared.memory_tags import MemoryTagManager
        mgr = MemoryTagManager()
        assert mgr.can_read("matt", "nonexistent") is False
        assert mgr.can_write("matt", "nonexistent") is False

    def test_get_accessible_tags(self):
        from bots.shared.memory_tags import MemoryTagManager
        mgr = MemoryTagManager()
        tags = mgr.get_accessible_tags("friday")
        assert "company_core" in tags
        assert "marketing_creative" in tags
        assert "technical_stack" not in tags

    def test_case_insensitive(self):
        from bots.shared.memory_tags import MemoryTagManager
        mgr = MemoryTagManager()
        assert mgr.can_read("MATT", "company_core") is True
        assert mgr.can_read("Matt", "company_core") is True
