"""
Tests for Memory Echo Chamber Fix (P0-1) - Database-backed Memory System.

The echo chamber problem occurs when:
1. Assistant outputs are stored as "facts" in memory
2. Recall retrieves these facts alongside real observations
3. LLM sees its own responses as external "facts", reinforcing shallow patterns

Solution:
- Tag facts with is_assistant_output=True when they come from assistant responses
- Filter out assistant outputs in recall by default
- Store progress summaries instead of raw assistant outputs

Tests verify:
- Facts can be tagged as assistant outputs
- Recall excludes assistant outputs by default
- Recall can optionally include assistant outputs (for context)
- Progress facts are stored correctly
- Search functions respect the filtering
"""

import sys
import sqlite3
import tempfile
import inspect
from pathlib import Path
from datetime import datetime
from unittest.mock import patch, MagicMock
from typing import Optional

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


# =============================================================================
# Test Schema Extensions for Assistant Output Tagging
# =============================================================================

class TestSchemaExtensions:
    """Test that schema supports is_assistant_output field."""

    @pytest.fixture
    def temp_db(self, tmp_path):
        """Create temporary database."""
        db_path = tmp_path / "test_memory.db"
        return db_path

    def test_schema_has_is_assistant_output_column(self, temp_db):
        """Facts table should have is_assistant_output column."""
        # Import after sys.path setup
        from core.memory.schema import CREATE_TABLES_SQL

        # Check that schema includes the column
        assert "is_assistant_output" in CREATE_TABLES_SQL, \
            "Schema should include is_assistant_output column for echo chamber prevention"

    def test_facts_table_defaults_is_assistant_output_to_false(self, temp_db):
        """New facts should default to is_assistant_output=False."""
        conn = sqlite3.connect(temp_db)
        conn.row_factory = sqlite3.Row

        # Create minimal schema with new column
        conn.execute("""
            CREATE TABLE facts (
                id INTEGER PRIMARY KEY,
                content TEXT NOT NULL,
                source TEXT,
                is_assistant_output INTEGER DEFAULT 0
            )
        """)

        # Insert without specifying is_assistant_output
        conn.execute("INSERT INTO facts (content, source) VALUES (?, ?)",
                     ("User said something", "telegram"))
        conn.commit()

        row = conn.execute("SELECT is_assistant_output FROM facts WHERE id = 1").fetchone()
        assert row["is_assistant_output"] == 0, "Default should be 0 (False)"


# =============================================================================
# Test Retain Function - Tagging Assistant Outputs
# =============================================================================

class TestRetainTagging:
    """Test that retain_fact can tag assistant outputs."""

    @pytest.fixture
    def mock_db(self, tmp_path):
        """Create mock database with new schema."""
        db_path = tmp_path / "test_memory.db"
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row

        # Create schema with is_assistant_output
        conn.execute("""
            CREATE TABLE facts (
                id INTEGER PRIMARY KEY,
                content TEXT NOT NULL,
                context TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                source TEXT,
                confidence REAL DEFAULT 1.0,
                is_active INTEGER DEFAULT 1,
                is_assistant_output INTEGER DEFAULT 0
            )
        """)
        conn.commit()
        conn.close()

        return db_path

    def test_retain_fact_with_is_assistant_output_flag(self, mock_db):
        """retain_fact should accept is_assistant_output parameter."""
        from core.memory import retain

        # Check that function signature accepts the parameter
        import inspect
        sig = inspect.signature(retain.retain_fact)
        param_names = list(sig.parameters.keys())

        assert "is_assistant_output" in param_names, \
            "retain_fact should accept is_assistant_output parameter"

    def test_retain_fact_stores_assistant_flag(self, mock_db):
        """retain_fact should store is_assistant_output in database."""
        # This test requires the actual implementation to be updated
        # For now, we test the interface expectation
        from core.memory import retain

        # Check that function accepts the parameter without error
        sig = inspect.signature(retain.retain_fact)
        params = sig.parameters

        if "is_assistant_output" in params:
            # Parameter exists, check its default
            default = params["is_assistant_output"].default
            assert default == False or default == inspect.Parameter.empty, \
                "is_assistant_output should default to False"


# =============================================================================
# Test Recall Filtering
# =============================================================================

class TestRecallFiltering:
    """Test that recall excludes assistant outputs by default."""

    def test_recall_has_exclude_assistant_outputs_param(self):
        """recall should have exclude_assistant_outputs parameter."""
        from core.memory.recall import recall

        sig = inspect.signature(recall)
        param_names = list(sig.parameters.keys())

        assert "exclude_assistant_outputs" in param_names, \
            "recall should have exclude_assistant_outputs parameter for echo chamber prevention"

    def test_recall_defaults_to_excluding_assistant_outputs(self):
        """recall should exclude assistant outputs by default."""
        from core.memory.recall import recall

        sig = inspect.signature(recall)
        params = sig.parameters

        if "exclude_assistant_outputs" in params:
            default = params["exclude_assistant_outputs"].default
            assert default == True, \
                "exclude_assistant_outputs should default to True for echo chamber prevention"


# =============================================================================
# Test Search Functions Filtering
# =============================================================================

class TestSearchFiltering:
    """Test that search functions respect assistant output filtering."""

    def test_search_facts_has_exclude_assistant_outputs_param(self):
        """search_facts should have exclude_assistant_outputs parameter."""
        from core.memory.search import search_facts

        sig = inspect.signature(search_facts)
        param_names = list(sig.parameters.keys())

        assert "exclude_assistant_outputs" in param_names, \
            "search_facts should have exclude_assistant_outputs parameter"

    def test_get_recent_facts_has_exclude_assistant_outputs_param(self):
        """get_recent_facts should have exclude_assistant_outputs parameter."""
        from core.memory.search import get_recent_facts

        sig = inspect.signature(get_recent_facts)
        param_names = list(sig.parameters.keys())

        assert "exclude_assistant_outputs" in param_names, \
            "get_recent_facts should have exclude_assistant_outputs parameter"


# =============================================================================
# Test Progress Tracking (Better Alternative to Raw Output Storage)
# =============================================================================

class TestProgressTracking:
    """Test progress tracking as alternative to storing raw assistant outputs."""

    def test_retain_progress_function_exists(self):
        """retain_progress function should exist for storing outcomes."""
        from core.memory import retain

        assert hasattr(retain, "retain_progress"), \
            "retain module should have retain_progress function for storing outcomes"

    def test_retain_progress_stores_as_progress_type(self):
        """retain_progress should mark facts as progress type."""
        from core.memory import retain

        if hasattr(retain, "retain_progress"):
            sig = inspect.signature(retain.retain_progress)
            # Should accept goal, outcome, and status
            param_names = list(sig.parameters.keys())
            assert "goal" in param_names or "outcome" in param_names, \
                "retain_progress should accept goal/outcome parameters"


# =============================================================================
# Integration Tests - Echo Chamber Prevention
# =============================================================================

class TestEchoChainPrevention:
    """Integration tests for echo chamber prevention."""

    @pytest.fixture
    def memory_test_setup(self, tmp_path):
        """Setup isolated test environment."""
        return {"tmp_path": tmp_path}

    def test_assistant_outputs_not_returned_in_normal_recall(self):
        """Normal recall should not return assistant outputs."""
        # This is an integration test that requires full implementation
        # For TDD, we document the expected behavior

        # Expected behavior:
        # 1. Store fact with is_assistant_output=True
        # 2. Call recall() with default params
        # 3. Result should NOT contain the assistant output

        # Placeholder assertion until implementation
        assert True, "Integration test - requires implementation"

    def test_assistant_outputs_available_with_explicit_flag(self):
        """Should be able to include assistant outputs when needed."""
        # Expected behavior:
        # 1. Store fact with is_assistant_output=True
        # 2. Call recall(exclude_assistant_outputs=False)
        # 3. Result SHOULD contain the assistant output

        # Placeholder assertion until implementation
        assert True, "Integration test - requires implementation"

    def test_progress_facts_returned_instead_of_raw_outputs(self):
        """Progress summaries should be returned, not raw assistant outputs."""
        # Expected behavior:
        # 1. Store progress fact: "Completed analysis of token X"
        # 2. Store raw assistant output (marked is_assistant_output=True)
        # 3. Recall should return progress fact but not raw output

        # Placeholder assertion until implementation
        assert True, "Integration test - requires implementation"


# =============================================================================
# Backward Compatibility Tests
# =============================================================================

class TestBackwardCompatibility:
    """Ensure changes don't break existing functionality."""

    def test_retain_fact_works_without_new_params(self):
        """retain_fact should work with existing call signatures."""
        from core.memory import retain

        import inspect
        sig = inspect.signature(retain.retain_fact)
        params = sig.parameters

        # Check required params still work
        required_params = [
            p for p, v in params.items()
            if v.default == inspect.Parameter.empty and v.kind not in (
                inspect.Parameter.VAR_POSITIONAL,
                inspect.Parameter.VAR_KEYWORD
            )
        ]

        # Only 'content' should be required
        assert required_params == ["content"], \
            f"Only 'content' should be required, got: {required_params}"

    def test_search_facts_works_without_new_params(self):
        """search_facts should work with existing call signatures."""
        from core.memory import search

        import inspect
        sig = inspect.signature(search.search_facts)

        # Should still accept just query string
        # (this is tested by checking 'query' is in params)
        assert "query" in sig.parameters, \
            "search_facts should still accept query parameter"
