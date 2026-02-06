"""
Tests for bots/shared/knowledge_graph.py

SQLite-backed Personal Knowledge Graph (PKG) for ClawdBots.

Tests cover:
- Entity CRUD (add, query, update)
- Relationship management
- Full-text search via FTS5
- Fact mutation (UPDATES, EXTENDS, DERIVES)
- Entity history tracking
- Graph export
- Error handling and edge cases
"""

import json
import os
import sys
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from bots.shared.knowledge_graph import KnowledgeGraph


class TestEntityCRUD:
    """Test entity creation, retrieval, and updates."""

    @pytest.fixture
    def kg(self, tmp_path):
        db_path = str(tmp_path / "test_kg.db")
        return KnowledgeGraph(db_path=db_path)

    def test_add_entity(self, kg):
        """Should add entity and return its ID."""
        eid = kg.add_entity("Daryl", "person", {"role": "founder"})
        assert isinstance(eid, int)
        assert eid > 0

    def test_add_entity_returns_existing_id(self, kg):
        """Should return same ID for duplicate name+type."""
        id1 = kg.add_entity("Daryl", "person", {"role": "founder"})
        id2 = kg.add_entity("Daryl", "person", {"role": "ceo"})
        assert id1 == id2

    def test_add_entity_updates_properties(self, kg):
        """Should merge properties on duplicate add."""
        kg.add_entity("Daryl", "person", {"role": "founder"})
        kg.add_entity("Daryl", "person", {"title": "CEO"})
        results = kg.query(entity_name="Daryl")
        assert len(results) == 1
        props = results[0]["properties"]
        assert props.get("role") == "founder"
        assert props.get("title") == "CEO"

    def test_query_by_name(self, kg):
        """Should find entity by name."""
        kg.add_entity("Jarvis", "bot", {"purpose": "trading"})
        results = kg.query(entity_name="Jarvis")
        assert len(results) == 1
        assert results[0]["name"] == "Jarvis"
        assert results[0]["type"] == "bot"

    def test_query_by_type(self, kg):
        """Should find entities by type."""
        kg.add_entity("Jarvis", "bot")
        kg.add_entity("Friday", "bot")
        kg.add_entity("Daryl", "person")
        results = kg.query(entity_type="bot")
        assert len(results) == 2
        names = {r["name"] for r in results}
        assert names == {"Jarvis", "Friday"}

    def test_query_nonexistent(self, kg):
        """Should return empty list for missing entity."""
        results = kg.query(entity_name="Nobody")
        assert results == []

    def test_query_no_filters(self, kg):
        """Should return all entities when no filters given."""
        kg.add_entity("A", "type1")
        kg.add_entity("B", "type2")
        results = kg.query()
        assert len(results) == 2


class TestRelationships:
    """Test relationship management."""

    @pytest.fixture
    def kg(self, tmp_path):
        db_path = str(tmp_path / "test_kg.db")
        g = KnowledgeGraph(db_path=db_path)
        g.add_entity("Daryl", "person")
        g.add_entity("Jarvis", "bot")
        g.add_entity("Friday", "bot")
        return g

    def test_add_relationship(self, kg):
        """Should create relationship between entities."""
        rid = kg.add_relationship("Daryl", "Jarvis", "OWNS")
        assert isinstance(rid, int)
        assert rid > 0

    def test_add_relationship_with_properties(self, kg):
        """Should store relationship properties."""
        kg.add_relationship("Daryl", "Jarvis", "MANAGES", {"since": "2026-01"})
        related = kg.get_related("Daryl", rel_type="MANAGES")
        assert len(related) == 1
        assert related[0]["rel_properties"].get("since") == "2026-01"

    def test_add_relationship_auto_creates_entities(self, kg):
        """Should auto-create entities if they don't exist."""
        kg.add_relationship("NewEntity", "AnotherNew", "DEPENDS_ON")
        results = kg.query(entity_name="NewEntity")
        assert len(results) == 1

    def test_get_related_outgoing(self, kg):
        """Should get outgoing relationships."""
        kg.add_relationship("Daryl", "Jarvis", "OWNS")
        kg.add_relationship("Daryl", "Friday", "OWNS")
        related = kg.get_related("Daryl", direction="outgoing")
        assert len(related) == 2
        names = {r["name"] for r in related}
        assert names == {"Jarvis", "Friday"}

    def test_get_related_incoming(self, kg):
        """Should get incoming relationships."""
        kg.add_relationship("Daryl", "Jarvis", "OWNS")
        related = kg.get_related("Jarvis", direction="incoming")
        assert len(related) == 1
        assert related[0]["name"] == "Daryl"

    def test_get_related_filtered_by_type(self, kg):
        """Should filter relationships by type."""
        kg.add_relationship("Daryl", "Jarvis", "OWNS")
        kg.add_relationship("Daryl", "Jarvis", "MANAGES")
        related = kg.get_related("Daryl", rel_type="OWNS")
        assert len(related) == 1

    def test_get_related_empty(self, kg):
        """Should return empty for no relationships."""
        related = kg.get_related("Daryl")
        assert related == []

    def test_query_by_rel_type(self, kg):
        """Should query relationships by type."""
        kg.add_relationship("Daryl", "Jarvis", "OWNS")
        kg.add_relationship("Jarvis", "Friday", "DEPENDS_ON")
        results = kg.query(rel_type="OWNS")
        assert len(results) >= 1


class TestFullTextSearch:
    """Test FTS5 full-text search."""

    @pytest.fixture
    def kg(self, tmp_path):
        db_path = str(tmp_path / "test_kg.db")
        g = KnowledgeGraph(db_path=db_path)
        g.add_entity("Solana Trading Bot", "service", {"chain": "solana", "type": "dex"})
        g.add_entity("Telegram Bot", "service", {"platform": "telegram"})
        g.add_entity("Bitcoin Analysis", "project", {"focus": "btc"})
        return g

    def test_search_by_name(self, kg):
        """Should find entities matching name."""
        results = kg.search("Trading")
        assert len(results) >= 1
        assert any("Trading" in r["name"] for r in results)

    def test_search_no_results(self, kg):
        """Should return empty for no match."""
        results = kg.search("nonexistent_xyz_query")
        assert results == []

    def test_search_partial(self, kg):
        """Should match partial terms."""
        results = kg.search("Tele*")
        assert len(results) >= 1


class TestFactMutation:
    """Test UPDATES, EXTENDS, DERIVES relationships."""

    @pytest.fixture
    def kg(self, tmp_path):
        db_path = str(tmp_path / "test_kg.db")
        g = KnowledgeGraph(db_path=db_path)
        g.add_entity("SOL_Price", "fact", {"value": "100", "date": "2026-01-01"})
        return g

    def test_update_fact(self, kg):
        """Should create UPDATES relationship and update properties."""
        kg.update_fact("SOL_Price", {"value": "150", "date": "2026-02-01"})
        results = kg.query(entity_name="SOL_Price")
        assert results[0]["properties"]["value"] == "150"

    def test_update_fact_creates_history(self, kg):
        """Should maintain history via UPDATES chain."""
        kg.update_fact("SOL_Price", {"value": "150"})
        kg.update_fact("SOL_Price", {"value": "200"})
        history = kg.get_entity_history("SOL_Price")
        assert len(history) >= 2

    def test_extend_fact(self, kg):
        """Should add properties without replacing existing."""
        kg.extend_fact("SOL_Price", {"source": "coingecko", "confidence": "high"})
        results = kg.query(entity_name="SOL_Price")
        props = results[0]["properties"]
        assert props["value"] == "100"  # original preserved
        assert props["source"] == "coingecko"

    def test_derive_fact(self, kg):
        """Should create derived entity with DERIVES relationships."""
        kg.add_entity("ETH_Price", "fact", {"value": "3000"})
        kg.derive_fact(
            source_entities=["SOL_Price", "ETH_Price"],
            derived_name="SOL_ETH_Ratio",
            derived_type="derived_fact",
            reasoning="SOL/ETH price ratio calculation",
        )
        results = kg.query(entity_name="SOL_ETH_Ratio")
        assert len(results) == 1
        assert results[0]["type"] == "derived_fact"

        # Should have DERIVES relationships from sources
        related = kg.get_related("SOL_ETH_Ratio", rel_type="DERIVES", direction="outgoing")
        assert len(related) == 2

    def test_get_entity_history_empty(self, kg):
        """Should return single entry for entity with no updates."""
        history = kg.get_entity_history("SOL_Price")
        assert len(history) >= 1

    def test_get_entity_history_nonexistent(self, kg):
        """Should return empty for nonexistent entity."""
        history = kg.get_entity_history("NonExistent")
        assert history == []


class TestExport:
    """Test graph export."""

    @pytest.fixture
    def kg(self, tmp_path):
        db_path = str(tmp_path / "test_kg.db")
        g = KnowledgeGraph(db_path=db_path)
        g.add_entity("A", "type1", {"key": "val"})
        g.add_entity("B", "type2")
        g.add_relationship("A", "B", "LINKS_TO")
        return g

    def test_export_graph(self, kg):
        """Should export entire graph as dict."""
        data = kg.export_graph()
        assert "entities" in data
        assert "relationships" in data
        assert len(data["entities"]) == 2
        assert len(data["relationships"]) == 1

    def test_export_is_json_serializable(self, kg):
        """Should be JSON serializable."""
        data = kg.export_graph()
        serialized = json.dumps(data)
        assert isinstance(serialized, str)


class TestEdgeCases:
    """Test error handling and edge cases."""

    def test_init_creates_db(self, tmp_path):
        """Should create database file on init."""
        db_path = str(tmp_path / "new_kg.db")
        KnowledgeGraph(db_path=db_path)
        assert Path(db_path).exists()

    def test_init_creates_parent_dirs(self, tmp_path):
        """Should create parent directories."""
        db_path = str(tmp_path / "sub" / "dir" / "kg.db")
        KnowledgeGraph(db_path=db_path)
        assert Path(db_path).exists()

    def test_empty_properties(self, tmp_path):
        """Should handle None/empty properties."""
        kg = KnowledgeGraph(db_path=str(tmp_path / "kg.db"))
        eid = kg.add_entity("Test", "type")
        assert eid > 0
        results = kg.query(entity_name="Test")
        assert results[0]["properties"] == {}

    def test_special_characters_in_name(self, tmp_path):
        """Should handle special characters."""
        kg = KnowledgeGraph(db_path=str(tmp_path / "kg.db"))
        kg.add_entity("O'Reilly & Sons", "company")
        results = kg.query(entity_name="O'Reilly & Sons")
        assert len(results) == 1

    def test_concurrent_safe(self, tmp_path):
        """Should handle WAL mode for concurrent access."""
        db_path = str(tmp_path / "kg.db")
        kg = KnowledgeGraph(db_path=db_path)
        # Just verify it doesn't crash with WAL
        kg.add_entity("Test", "type")
        results = kg.query(entity_name="Test")
        assert len(results) == 1
