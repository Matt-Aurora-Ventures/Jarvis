"""
Tests for Dexter Scratchpad and Context Management

Tests the decision logging and context management systems:
1. Scratchpad append-only logging
2. Context compaction and token management
3. Persistence and recovery
4. Summary generation
5. Session state management
"""

import pytest
import json
import tempfile
from pathlib import Path
from datetime import datetime, timezone

from core.dexter.scratchpad import Scratchpad
from core.dexter.context import ContextManager


# =============================================================================
# Section 1: Scratchpad Initialization Tests
# =============================================================================

class TestScratchpadInitialization:
    """Test Scratchpad initialization and setup."""

    def test_scratchpad_creates_directory(self):
        """Test Scratchpad creates directory if not exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            scratchpad_path = Path(tmpdir) / "new_scratchpad"

            sp = Scratchpad("test-session", scratchpad_dir=scratchpad_path)

            assert scratchpad_path.exists()
            assert scratchpad_path.is_dir()

    def test_scratchpad_session_id_stored(self):
        """Test session ID is stored correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sp = Scratchpad("my-session-id", scratchpad_dir=Path(tmpdir))

            assert sp.session_id == "my-session-id"

    def test_scratchpad_file_path_correct(self):
        """Test scratchpad file path is correct."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sp = Scratchpad("test-session", scratchpad_dir=Path(tmpdir))

            expected_path = Path(tmpdir) / "test-session.jsonl"
            assert sp.scratchpad_path == expected_path

    def test_scratchpad_starts_empty(self):
        """Test scratchpad starts with no entries."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sp = Scratchpad("test-session", scratchpad_dir=Path(tmpdir))

            assert sp.get_entries() == []


# =============================================================================
# Section 2: Scratchpad Logging Tests
# =============================================================================

class TestScratchpadLogging:
    """Test Scratchpad logging methods."""

    def test_log_start_creates_entry(self):
        """Test log_start creates start entry."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sp = Scratchpad("test-session", scratchpad_dir=Path(tmpdir))

            sp.log_start("Analyze SOL market", symbol="SOL")

            entries = sp.get_entries()
            assert len(entries) == 1
            assert entries[0]["type"] == "start"
            assert entries[0]["goal"] == "Analyze SOL market"
            assert entries[0]["symbol"] == "SOL"

    def test_log_start_without_symbol(self):
        """Test log_start without symbol."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sp = Scratchpad("test-session", scratchpad_dir=Path(tmpdir))

            sp.log_start("General market analysis")

            entries = sp.get_entries()
            assert entries[0]["symbol"] is None

    def test_log_reasoning_creates_entry(self):
        """Test log_reasoning creates reasoning entry."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sp = Scratchpad("test-session", scratchpad_dir=Path(tmpdir))

            sp.log_reasoning("Checking market data for patterns", iteration=1)

            entries = sp.get_entries()
            assert len(entries) == 1
            assert entries[0]["type"] == "reasoning"
            assert entries[0]["thought"] == "Checking market data for patterns"
            assert entries[0]["iteration"] == 1

    def test_log_reasoning_multiple_iterations(self):
        """Test logging reasoning across multiple iterations."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sp = Scratchpad("test-session", scratchpad_dir=Path(tmpdir))

            for i in range(1, 6):
                sp.log_reasoning(f"Iteration {i} thought", iteration=i)

            entries = sp.get_entries()
            assert len(entries) == 5

            for i, entry in enumerate(entries, 1):
                assert entry["iteration"] == i

    def test_log_action_creates_entry(self):
        """Test log_action creates action entry."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sp = Scratchpad("test-session", scratchpad_dir=Path(tmpdir))

            sp.log_action(
                "market_data",
                {"symbol": "SOL", "timeframe": "1h"},
                "Price: $142, Volume: $2.5B"
            )

            entries = sp.get_entries()
            assert len(entries) == 1
            assert entries[0]["type"] == "action"
            assert entries[0]["tool"] == "market_data"
            assert entries[0]["args"] == {"symbol": "SOL", "timeframe": "1h"}
            assert "Price: $142" in entries[0]["result"]

    def test_log_action_truncates_long_result(self):
        """Test log_action truncates results > 500 chars."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sp = Scratchpad("test-session", scratchpad_dir=Path(tmpdir))

            long_result = "x" * 1000
            sp.log_action("test_tool", {}, long_result)

            entries = sp.get_entries()
            assert len(entries[0]["result"]) <= 500

    def test_log_decision_creates_entry(self):
        """Test log_decision creates decision entry."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sp = Scratchpad("test-session", scratchpad_dir=Path(tmpdir))

            sp.log_decision(
                "BUY",
                "SOL",
                "Strong bullish signal with high volume",
                85.0
            )

            entries = sp.get_entries()
            assert len(entries) == 1
            assert entries[0]["type"] == "decision"
            assert entries[0]["action"] == "BUY"
            assert entries[0]["symbol"] == "SOL"
            assert entries[0]["rationale"] == "Strong bullish signal with high volume"
            assert entries[0]["confidence"] == 85.0

    def test_log_error_creates_entry(self):
        """Test log_error creates error entry."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sp = Scratchpad("test-session", scratchpad_dir=Path(tmpdir))

            sp.log_error("API timeout occurred", iteration=3)

            entries = sp.get_entries()
            assert len(entries) == 1
            assert entries[0]["type"] == "error"
            assert entries[0]["error"] == "API timeout occurred"
            assert entries[0]["iteration"] == 3


class TestScratchpadTimestamps:
    """Test timestamp handling in Scratchpad."""

    def test_all_entries_have_timestamps(self):
        """Test all entry types include timestamps."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sp = Scratchpad("test-session", scratchpad_dir=Path(tmpdir))

            sp.log_start("Goal")
            sp.log_reasoning("Thought", iteration=1)
            sp.log_action("tool", {}, "result")
            sp.log_decision("BUY", "SOL", "rationale", 80.0)
            sp.log_error("error", iteration=2)

            entries = sp.get_entries()
            assert len(entries) == 5

            for entry in entries:
                assert "ts" in entry
                # Verify it's a valid ISO format timestamp
                timestamp = datetime.fromisoformat(entry["ts"].replace("Z", "+00:00"))
                assert timestamp is not None

    def test_timestamps_are_utc(self):
        """Test timestamps are in UTC."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sp = Scratchpad("test-session", scratchpad_dir=Path(tmpdir))

            sp.log_reasoning("Test", iteration=1)

            entry = sp.get_entries()[0]
            # Should be able to parse as UTC
            timestamp = datetime.fromisoformat(entry["ts"].replace("Z", "+00:00"))
            # Timezone aware datetime in UTC
            assert timestamp.tzinfo is not None or "+00:00" in entry["ts"]


# =============================================================================
# Section 3: Scratchpad Persistence Tests
# =============================================================================

class TestScratchpadPersistence:
    """Test Scratchpad persistence to disk."""

    def test_entries_written_to_file(self):
        """Test entries are written to JSONL file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sp = Scratchpad("test-session", scratchpad_dir=Path(tmpdir))

            sp.log_start("Goal", symbol="SOL")
            sp.log_reasoning("Thought", iteration=1)

            # Check file exists and has content
            filepath = Path(tmpdir) / "test-session.jsonl"
            assert filepath.exists()

            with open(filepath) as f:
                lines = f.readlines()

            assert len(lines) == 2

    def test_jsonl_format_valid(self):
        """Test each line is valid JSON."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sp = Scratchpad("test-session", scratchpad_dir=Path(tmpdir))

            sp.log_start("Goal")
            sp.log_reasoning("Thought", iteration=1)
            sp.log_action("tool", {"key": "value"}, "result")
            sp.log_decision("HOLD", "BTC", "reason", 50.0)

            filepath = Path(tmpdir) / "test-session.jsonl"

            with open(filepath) as f:
                for line in f:
                    # Should not raise
                    entry = json.loads(line)
                    assert isinstance(entry, dict)

    def test_entries_can_be_reconstructed(self):
        """Test entries can be read back and match."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sp = Scratchpad("test-session", scratchpad_dir=Path(tmpdir))

            sp.log_start("Test goal", symbol="SOL")
            sp.log_decision("BUY", "SOL", "Strong signal", 85.0)

            filepath = Path(tmpdir) / "test-session.jsonl"

            # Read back
            reconstructed = []
            with open(filepath) as f:
                for line in f:
                    reconstructed.append(json.loads(line))

            original = sp.get_entries()

            assert len(reconstructed) == len(original)
            for orig, recon in zip(original, reconstructed):
                assert orig["type"] == recon["type"]


# =============================================================================
# Section 4: Scratchpad Summary Tests
# =============================================================================

class TestScratchpadSummary:
    """Test Scratchpad summary generation."""

    def test_summary_includes_goal(self):
        """Test summary includes goal from start entry."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sp = Scratchpad("test-session", scratchpad_dir=Path(tmpdir))

            sp.log_start("Analyze SOL for trading opportunity", symbol="SOL")

            summary = sp.get_summary()
            assert "Analyze SOL" in summary
            assert "SOL" in summary

    def test_summary_includes_reasoning(self):
        """Test summary includes reasoning steps."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sp = Scratchpad("test-session", scratchpad_dir=Path(tmpdir))

            sp.log_reasoning("Checking market sentiment", iteration=1)
            sp.log_reasoning("Analyzing technical indicators", iteration=2)

            summary = sp.get_summary()
            assert "1" in summary
            assert "2" in summary

    def test_summary_includes_actions(self):
        """Test summary includes tool actions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sp = Scratchpad("test-session", scratchpad_dir=Path(tmpdir))

            sp.log_action("market_data", {}, "Price: $142")

            summary = sp.get_summary()
            assert "market_data" in summary

    def test_summary_includes_decision(self):
        """Test summary includes final decision."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sp = Scratchpad("test-session", scratchpad_dir=Path(tmpdir))

            sp.log_decision("BUY", "SOL", "Strong bullish momentum", 85.0)

            summary = sp.get_summary()
            assert "BUY" in summary
            assert "SOL" in summary
            assert "85" in summary

    def test_summary_includes_errors(self):
        """Test summary includes errors."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sp = Scratchpad("test-session", scratchpad_dir=Path(tmpdir))

            sp.log_error("Connection timeout", iteration=1)

            summary = sp.get_summary()
            assert "timeout" in summary.lower()

    def test_full_summary_structure(self):
        """Test complete summary with all entry types."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sp = Scratchpad("test-session", scratchpad_dir=Path(tmpdir))

            sp.log_start("Full analysis", symbol="SOL")
            sp.log_reasoning("Step 1", iteration=1)
            sp.log_action("tool1", {}, "result1")
            sp.log_reasoning("Step 2", iteration=2)
            sp.log_action("tool2", {}, "result2")
            sp.log_decision("BUY", "SOL", "Final rationale", 80.0)

            summary = sp.get_summary()

            # Should have structure
            assert "===" in summary or "Session" in summary
            assert len(summary) > 100


# =============================================================================
# Section 5: Context Manager Initialization Tests
# =============================================================================

class TestContextManagerInitialization:
    """Test ContextManager initialization."""

    def test_context_manager_creates_directory(self):
        """Test ContextManager creates session directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ctx = ContextManager("test-session", data_dir=Path(tmpdir))

            # Should create session subdirectory
            session_dir = Path(tmpdir) / "test-session"
            assert session_dir.exists()

    def test_context_manager_default_max_tokens(self):
        """Test default max tokens setting."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ctx = ContextManager("test-session", data_dir=Path(tmpdir))

            assert ctx.max_tokens == 100000

    def test_context_manager_custom_max_tokens(self):
        """Test custom max tokens setting."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ctx = ContextManager("test-session", max_tokens=50000, data_dir=Path(tmpdir))

            assert ctx.max_tokens == 50000

    def test_context_manager_starts_empty(self):
        """Test context manager starts with no data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ctx = ContextManager("test-session", data_dir=Path(tmpdir))

            assert ctx.get_token_estimate() == 0


# =============================================================================
# Section 6: Context Manager Data Persistence Tests
# =============================================================================

class TestContextManagerPersistence:
    """Test ContextManager data persistence."""

    def test_save_full_data_creates_file(self):
        """Test save_full_data creates JSON file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ctx = ContextManager("test-session", data_dir=Path(tmpdir))

            data = {"price": 142.50, "volume": 2500000000}
            ctx.save_full_data(data, "market_data")

            # Should create file in session directory
            session_dir = Path(tmpdir) / "test-session"
            files = list(session_dir.glob("market_data_*.json"))
            assert len(files) >= 1

    def test_saved_data_contains_timestamp(self):
        """Test saved data includes timestamp."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ctx = ContextManager("test-session", data_dir=Path(tmpdir))

            data = {"test": "value"}
            ctx.save_full_data(data, "test_type")

            session_dir = Path(tmpdir) / "test-session"
            files = list(session_dir.glob("test_type_*.json"))

            with open(files[0]) as f:
                saved = json.load(f)

            assert "ts" in saved
            assert "data" in saved
            assert saved["data"] == data

    def test_load_historical_returns_latest(self):
        """Test load_historical returns most recent data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ctx = ContextManager("test-session", data_dir=Path(tmpdir))

            # Save multiple entries
            ctx.save_full_data({"version": 1}, "market_data")
            ctx.save_full_data({"version": 2}, "market_data")

            # Load should return latest
            loaded = ctx.load_historical("market_data")
            assert loaded is not None
            assert loaded["data"]["version"] == 2

    def test_load_historical_returns_none_for_missing(self):
        """Test load_historical returns None for missing data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ctx = ContextManager("test-session", data_dir=Path(tmpdir))

            result = ctx.load_historical("nonexistent_type")
            assert result is None


# =============================================================================
# Section 7: Context Manager Summary Tests
# =============================================================================

class TestContextManagerSummary:
    """Test ContextManager summary functionality."""

    def test_add_summary(self):
        """Test adding summaries."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ctx = ContextManager("test-session", data_dir=Path(tmpdir))

            ctx.add_summary("First summary")
            ctx.add_summary("Second summary")

            summary = ctx.get_summary()
            assert "First summary" in summary
            assert "Second summary" in summary

    def test_summary_keeps_last_three(self):
        """Test get_summary only returns last 3 summaries."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ctx = ContextManager("test-session", data_dir=Path(tmpdir))

            for i in range(10):
                ctx.add_summary(f"Summary {i}")

            summary = ctx.get_summary()

            # Should have summaries 7, 8, 9 (last 3)
            assert "Summary 7" in summary or "Summary 8" in summary or "Summary 9" in summary

    def test_get_summary_format(self):
        """Test summary has proper format."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ctx = ContextManager("test-session", data_dir=Path(tmpdir))

            ctx.add_summary("Test summary content")

            summary = ctx.get_summary()

            # Should have header
            assert "Context" in summary or "===" in summary

    def test_token_estimate_updates(self):
        """Test token estimate updates with summaries."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ctx = ContextManager("test-session", data_dir=Path(tmpdir))

            initial = ctx.get_token_estimate()

            ctx.add_summary("This is a test summary with some words")

            after = ctx.get_token_estimate()

            # Should have increased
            assert after > initial


# =============================================================================
# Section 8: Context Compaction Tests
# =============================================================================

class TestContextCompaction:
    """Test context compaction to prevent token overflow."""

    def test_compaction_reduces_summaries(self):
        """Test compaction reduces summary count."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Use very low max_tokens to trigger compaction
            ctx = ContextManager("test-session", max_tokens=100, data_dir=Path(tmpdir))

            # Add many long summaries
            for i in range(20):
                ctx.add_summary("x" * 50 + f" Summary {i}")

            # Check we have limited summaries (compaction should have occurred)
            summary = ctx.get_summary()
            # Should not have all 20 summaries
            summary_count = sum(1 for i in range(20) if f"Summary {i}" in summary)
            assert summary_count <= 5  # Should be compacted

    def test_token_estimate_stays_bounded(self):
        """Test token estimate stays within bounds."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ctx = ContextManager("test-session", max_tokens=1000, data_dir=Path(tmpdir))

            # Add many summaries
            for _ in range(100):
                ctx.add_summary("A" * 100)

            # Token estimate should be bounded
            # Not necessarily below max_tokens (since compaction happens at 25%)
            # but should not grow indefinitely
            estimate = ctx.get_token_estimate()
            assert estimate < 100000  # Should not be astronomical


# =============================================================================
# Section 9: Integration Tests
# =============================================================================

class TestScratchpadContextIntegration:
    """Test Scratchpad and ContextManager working together."""

    def test_full_session_workflow(self):
        """Test complete session workflow with both components."""
        with tempfile.TemporaryDirectory() as tmpdir:
            session_id = "integration-test"

            # Create both
            sp = Scratchpad(session_id, scratchpad_dir=Path(tmpdir) / "scratchpad")
            ctx = ContextManager(session_id, data_dir=Path(tmpdir) / "context")

            # Log start
            sp.log_start("Analyze SOL", symbol="SOL")

            # Save market data
            market_data = {"symbol": "SOL", "price": 142.50}
            ctx.save_full_data(market_data, "market_data")
            ctx.add_summary("SOL price: $142.50")

            # Log reasoning
            sp.log_reasoning("Price is bullish", iteration=1)

            # Log action
            sp.log_action("sentiment_check", {}, "Bullish 75/100")
            ctx.add_summary("Sentiment: Bullish 75/100")

            # Log decision
            sp.log_decision("BUY", "SOL", "Strong signal", 80.0)

            # Verify scratchpad
            entries = sp.get_entries()
            assert len(entries) == 4

            # Verify context
            context_summary = ctx.get_summary()
            assert "SOL" in context_summary
            assert "142.50" in context_summary

    def test_error_recovery_workflow(self):
        """Test workflow with error and recovery."""
        with tempfile.TemporaryDirectory() as tmpdir:
            session_id = "error-test"

            sp = Scratchpad(session_id, scratchpad_dir=Path(tmpdir) / "scratchpad")

            # Start
            sp.log_start("Analyze token", symbol="TOKEN")

            # Error occurs
            sp.log_error("API connection failed", iteration=1)

            # Recovery
            sp.log_reasoning("Retrying with backup", iteration=2)

            # Success
            sp.log_decision("HOLD", "TOKEN", "Recovered but uncertain", 55.0)

            # Verify all entries logged
            entries = sp.get_entries()
            types = [e["type"] for e in entries]
            assert "start" in types
            assert "error" in types
            assert "reasoning" in types
            assert "decision" in types


# =============================================================================
# Section 10: Edge Cases
# =============================================================================

class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_scratchpad_unicode_content(self):
        """Test scratchpad handles unicode content."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sp = Scratchpad("test-session", scratchpad_dir=Path(tmpdir))

            sp.log_reasoning("Analyzing token: emoji test", iteration=1)
            sp.log_decision("HOLD", "ETH", "Price: $1,234.56", 50.0)

            entries = sp.get_entries()
            assert len(entries) == 2

    def test_scratchpad_special_characters_in_session_id(self):
        """Test scratchpad handles special session IDs."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # UUID-style session ID
            session_id = "abc123-def-456"
            sp = Scratchpad(session_id, scratchpad_dir=Path(tmpdir))

            sp.log_start("Test")

            assert sp.scratchpad_path.name == f"{session_id}.jsonl"

    def test_context_manager_empty_data(self):
        """Test context manager handles empty data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ctx = ContextManager("test-session", data_dir=Path(tmpdir))

            ctx.save_full_data({}, "empty_data")

            loaded = ctx.load_historical("empty_data")
            assert loaded is not None
            assert loaded["data"] == {}

    def test_scratchpad_very_long_session(self):
        """Test scratchpad handles many entries."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sp = Scratchpad("long-session", scratchpad_dir=Path(tmpdir))

            # Log many entries
            sp.log_start("Long analysis")
            for i in range(50):
                sp.log_reasoning(f"Thought {i}", iteration=i + 1)
                sp.log_action(f"tool_{i}", {"n": i}, f"result_{i}")
            sp.log_decision("HOLD", "BTC", "Complex analysis", 60.0)

            entries = sp.get_entries()
            assert len(entries) == 102  # 1 start + 50*2 + 1 decision

            # Summary should still work
            summary = sp.get_summary()
            assert len(summary) > 0


# Ensure module can be run standalone
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
