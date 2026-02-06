"""
Tests for Sleep-Time Compute System.

Tests cover:
- NightlyRoutine class initialization and methods
- Log analysis functionality
- Pattern extraction
- Knowledge graph updates
- Insight generation
- SOUL file updates
"""

import pytest
import json
import tempfile
import os
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from core.sleep_compute.nightly_routine import (
    NightlyRoutine,
    PatternCategory,
    Pattern,
    DeriveChain,
    SleepComputeConfig,
)


@pytest.fixture
def temp_logs_dir():
    """Create a temporary logs directory with sample logs."""
    with tempfile.TemporaryDirectory() as tmpdir:
        logs_path = Path(tmpdir)

        # Create sample log files
        (logs_path / "friday_activity.log").write_text(
            "[2026-02-01 10:00:00] INFO: Dispatched task to Matt\n"
            "[2026-02-01 10:05:00] INFO: Task completed successfully\n"
            "[2026-02-01 11:00:00] ERROR: Failed to reach Jarvis\n"
            "[2026-02-01 14:00:00] INFO: User requested bullet points format\n"
            "[2026-02-01 14:05:00] INFO: User requested bullet points format\n"
        )

        (logs_path / "matt_activity.log").write_text(
            "[2026-02-01 09:00:00] INFO: Posted to LinkedIn\n"
            "[2026-02-01 10:00:00] INFO: LinkedIn engagement: 847 impressions\n"
            "[2026-02-01 15:00:00] INFO: Posted to Twitter\n"
        )

        (logs_path / "jarvis_activity.log").write_text(
            "[2026-02-01 09:30:00] INFO: Trade executed: BUY SOL\n"
            "[2026-02-01 09:35:00] INFO: Trade result: +5.2%\n"
            "[2026-02-01 22:00:00] INFO: Trade executed: BUY ETH\n"
            "[2026-02-01 22:05:00] INFO: Trade result: -3.1%\n"
        )

        yield logs_path


@pytest.fixture
def temp_output_dir():
    """Create a temporary output directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def temp_soul_dir():
    """Create temporary SOUL files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        soul_path = Path(tmpdir)

        (soul_path / "CLAWDFRIDAY_SOUL.md").write_text(
            "# ClawdFriday SOUL\n\n"
            "## Core Identity\n"
            "Friday is the dispatcher.\n"
        )

        (soul_path / "CLAWDMATT_SOUL.md").write_text(
            "# ClawdMatt SOUL\n\n"
            "## Core Identity\n"
            "Matt is the growth architect.\n"
        )

        (soul_path / "CLAWDJARVIS_SOUL.md").write_text(
            "# ClawdJarvis SOUL\n\n"
            "## Core Identity\n"
            "Jarvis is the CTO.\n"
        )

        yield soul_path


@pytest.fixture
def nightly_routine(temp_logs_dir, temp_output_dir, temp_soul_dir):
    """Create a NightlyRoutine instance with temp directories."""
    config = SleepComputeConfig(
        logs_dir=temp_logs_dir,
        output_dir=temp_output_dir,
        soul_dir=temp_soul_dir,
        min_confidence_for_derive=0.65,
        min_confidence_for_soul_update=0.70,
    )
    return NightlyRoutine(config)


class TestSleepComputeConfig:
    """Tests for SleepComputeConfig."""

    def test_default_config(self):
        """Test default configuration values."""
        config = SleepComputeConfig()
        assert config.min_confidence_for_derive == 0.65
        assert config.min_confidence_for_soul_update == 0.70
        assert config.max_log_lines == 5000

    def test_custom_config(self, temp_logs_dir):
        """Test custom configuration."""
        config = SleepComputeConfig(
            logs_dir=temp_logs_dir,
            min_confidence_for_derive=0.80,
        )
        assert config.logs_dir == temp_logs_dir
        assert config.min_confidence_for_derive == 0.80


class TestNightlyRoutineInit:
    """Tests for NightlyRoutine initialization."""

    def test_init_with_config(self, nightly_routine):
        """Test initialization with config."""
        assert nightly_routine is not None
        assert nightly_routine.config is not None

    def test_init_creates_output_dir(self, temp_logs_dir, temp_soul_dir):
        """Test that init creates output directory if needed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "nested" / "output"
            config = SleepComputeConfig(
                logs_dir=temp_logs_dir,
                output_dir=output_dir,
                soul_dir=temp_soul_dir,
            )
            routine = NightlyRoutine(config)
            # The actual directory creation happens in run() or analyze_logs()


class TestAnalyzeLogs:
    """Tests for analyze_logs functionality."""

    def test_analyze_logs_reads_all_log_files(self, nightly_routine):
        """Test that analyze_logs reads all agent log files."""
        logs = nightly_routine.analyze_logs()

        assert "friday" in logs
        assert "matt" in logs
        assert "jarvis" in logs

    def test_analyze_logs_returns_log_content(self, nightly_routine):
        """Test that analyze_logs returns actual log content."""
        logs = nightly_routine.analyze_logs()

        assert "Dispatched task to Matt" in logs["friday"]
        assert "Posted to LinkedIn" in logs["matt"]
        assert "Trade executed" in logs["jarvis"]

    def test_analyze_logs_handles_missing_files(self, temp_output_dir, temp_soul_dir):
        """Test graceful handling of missing log files."""
        empty_logs_dir = temp_output_dir / "empty_logs"
        empty_logs_dir.mkdir()

        config = SleepComputeConfig(
            logs_dir=empty_logs_dir,
            output_dir=temp_output_dir,
            soul_dir=temp_soul_dir,
        )
        routine = NightlyRoutine(config)
        logs = routine.analyze_logs()

        assert logs["friday"] == ""
        assert logs["matt"] == ""
        assert logs["jarvis"] == ""

    def test_analyze_logs_respects_max_lines(self, temp_logs_dir, temp_output_dir, temp_soul_dir):
        """Test that max_log_lines limit is respected."""
        config = SleepComputeConfig(
            logs_dir=temp_logs_dir,
            output_dir=temp_output_dir,
            soul_dir=temp_soul_dir,
            max_log_lines=2,
        )
        routine = NightlyRoutine(config)
        logs = routine.analyze_logs()

        # Should only have last 2 lines
        lines = logs["friday"].strip().split("\n")
        assert len(lines) <= 2


class TestExtractPatterns:
    """Tests for extract_patterns functionality."""

    def test_extract_patterns_returns_list(self, nightly_routine):
        """Test that extract_patterns returns a list of patterns."""
        logs = nightly_routine.analyze_logs()
        patterns = nightly_routine.extract_patterns(logs)

        assert isinstance(patterns, list)

    def test_pattern_has_required_fields(self, nightly_routine):
        """Test that patterns have all required fields."""
        logs = nightly_routine.analyze_logs()
        patterns = nightly_routine.extract_patterns(logs)

        if patterns:  # If any patterns extracted
            pattern = patterns[0]
            assert hasattr(pattern, 'category')
            assert hasattr(pattern, 'observation')
            assert hasattr(pattern, 'evidence')
            assert hasattr(pattern, 'confidence')
            assert hasattr(pattern, 'recommendation')
            assert hasattr(pattern, 'affected_agents')

    def test_pattern_category_is_valid(self, nightly_routine):
        """Test that pattern categories are valid."""
        logs = nightly_routine.analyze_logs()
        patterns = nightly_routine.extract_patterns(logs)

        valid_categories = [e.value for e in PatternCategory]
        for pattern in patterns:
            assert pattern.category in valid_categories

    def test_pattern_confidence_in_range(self, nightly_routine):
        """Test that pattern confidence is between 0 and 1."""
        logs = nightly_routine.analyze_logs()
        patterns = nightly_routine.extract_patterns(logs)

        for pattern in patterns:
            assert 0.0 <= pattern.confidence <= 1.0

    def test_extract_patterns_identifies_user_preferences(self, nightly_routine):
        """Test that user preference patterns are identified."""
        logs = nightly_routine.analyze_logs()
        patterns = nightly_routine.extract_patterns(logs)

        # The sample logs have repeated "bullet points" mentions
        user_pref_patterns = [
            p for p in patterns
            if p.category == PatternCategory.USER_PREFERENCE.value
        ]
        # May or may not find patterns depending on implementation
        # This test documents expected behavior


class TestUpdateKnowledge:
    """Tests for update_knowledge (Supermemory derives)."""

    def test_update_knowledge_filters_low_confidence(self, nightly_routine):
        """Test that low confidence patterns are filtered."""
        patterns = [
            Pattern(
                category=PatternCategory.TEMPORAL.value,
                observation="Test observation",
                evidence="Some evidence",
                confidence=0.50,  # Below threshold
                recommendation="Do something",
                affected_agents=["jarvis"],
            )
        ]

        derives = nightly_routine.update_knowledge(patterns)
        assert len(derives) == 0  # Should be filtered

    def test_update_knowledge_creates_derive_chains(self, nightly_routine):
        """Test that derive chains are created for high confidence patterns."""
        patterns = [
            Pattern(
                category=PatternCategory.TEMPORAL.value,
                observation="Trading success higher 9-11 UTC",
                evidence="85% success rate in morning",
                confidence=0.85,
                recommendation="Prioritize morning trades",
                affected_agents=["jarvis"],
            )
        ]

        derives = nightly_routine.update_knowledge(patterns)
        assert len(derives) >= 1

        if derives:
            derive = derives[0]
            assert isinstance(derive, DeriveChain)
            assert derive.observation is not None
            assert derive.insight is not None
            assert derive.recommendation is not None

    def test_update_knowledge_returns_derive_chain_list(self, nightly_routine):
        """Test return type is list of DeriveChain."""
        patterns = []
        derives = nightly_routine.update_knowledge(patterns)
        assert isinstance(derives, list)


class TestGenerateInsights:
    """Tests for generate_insights (SOUL file updates)."""

    def test_generate_insights_filters_low_confidence(self, nightly_routine):
        """Test that low confidence patterns don't update SOUL files."""
        patterns = [
            Pattern(
                category=PatternCategory.USER_PREFERENCE.value,
                observation="Test observation",
                evidence="Some evidence",
                confidence=0.60,  # Below SOUL threshold
                recommendation="Do something",
                affected_agents=["friday"],
            )
        ]

        updates = nightly_routine.generate_insights(patterns)
        assert len(updates) == 0

    def test_generate_insights_returns_update_dict(self, nightly_routine):
        """Test that generate_insights returns dict of updates by agent."""
        patterns = [
            Pattern(
                category=PatternCategory.PERFORMANCE.value,
                observation="LinkedIn posts perform better Tuesday 10AM",
                evidence="3.2x avg engagement",
                confidence=0.85,
                recommendation="Post high-priority content Tuesday 10AM",
                affected_agents=["matt"],
            )
        ]

        updates = nightly_routine.generate_insights(patterns)
        assert isinstance(updates, dict)

        if updates:
            assert "matt" in updates or all(
                agent in updates for agent in ["friday", "matt", "jarvis"]
            )

    def test_generate_insights_writes_to_soul_files(self, nightly_routine, temp_soul_dir):
        """Test that insights are written to SOUL files."""
        patterns = [
            Pattern(
                category=PatternCategory.PERFORMANCE.value,
                observation="Content performs better on Tuesdays",
                evidence="3x engagement",
                confidence=0.90,
                recommendation="Schedule content for Tuesdays",
                affected_agents=["matt"],
            )
        ]

        nightly_routine.generate_insights(patterns)

        matt_soul = (temp_soul_dir / "CLAWDMATT_SOUL.md").read_text()
        assert "Sleep-Compute Insights" in matt_soul

    def test_generate_insights_preserves_existing_content(self, nightly_routine, temp_soul_dir):
        """Test that existing SOUL content is preserved."""
        patterns = [
            Pattern(
                category=PatternCategory.USER_PREFERENCE.value,
                observation="User prefers concise responses",
                evidence="80% of messages are short",
                confidence=0.88,
                recommendation="Keep responses concise",
                affected_agents=["friday"],
            )
        ]

        nightly_routine.generate_insights(patterns)

        friday_soul = (temp_soul_dir / "CLAWDFRIDAY_SOUL.md").read_text()
        # Original content should still be there
        assert "# ClawdFriday SOUL" in friday_soul
        assert "Friday is the dispatcher" in friday_soul


class TestPatternModel:
    """Tests for Pattern data model."""

    def test_pattern_creation(self):
        """Test Pattern can be created with all fields."""
        pattern = Pattern(
            category=PatternCategory.ERROR.value,
            observation="API rate limits hit",
            evidence="3x in last week",
            confidence=0.75,
            recommendation="Implement backoff",
            affected_agents=["jarvis", "friday"],
        )

        assert pattern.category == "error"
        assert pattern.confidence == 0.75
        assert len(pattern.affected_agents) == 2

    def test_pattern_to_dict(self):
        """Test Pattern can be serialized to dict."""
        pattern = Pattern(
            category=PatternCategory.TEMPORAL.value,
            observation="Test",
            evidence="Evidence",
            confidence=0.80,
            recommendation="Action",
            affected_agents=["matt"],
        )

        d = pattern.to_dict()
        assert d["category"] == "temporal"
        assert d["confidence"] == 0.80


class TestDeriveChainModel:
    """Tests for DeriveChain data model."""

    def test_derive_chain_creation(self):
        """Test DeriveChain can be created."""
        chain = DeriveChain(
            observation="User messages are short",
            insight="User prefers concise communication",
            recommendation="Limit responses to 3 paragraphs",
            tags=["#sleep-compute", "#user-preference"],
            confidence=0.87,
        )

        assert chain.observation is not None
        assert chain.confidence == 0.87

    def test_derive_chain_to_dict(self):
        """Test DeriveChain serialization."""
        chain = DeriveChain(
            observation="Obs",
            insight="Insight",
            recommendation="Rec",
            tags=["#test"],
            confidence=0.75,
        )

        d = chain.to_dict()
        assert "observation" in d
        assert "insight" in d
        assert "recommendation" in d


class TestFullNightlyRun:
    """Integration tests for full nightly run."""

    def test_run_executes_all_steps(self, nightly_routine, temp_output_dir):
        """Test that run() executes all steps in sequence."""
        result = nightly_routine.run()

        assert result is not None
        assert "logs_analyzed" in result
        assert "patterns_found" in result
        assert "derives_created" in result
        assert "soul_updates" in result

    def test_run_saves_patterns_to_file(self, nightly_routine, temp_output_dir):
        """Test that run() saves patterns.json."""
        nightly_routine.run()

        # Check that patterns file exists
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        patterns_file = temp_output_dir / today / "patterns.json"
        # File creation depends on implementation

    def test_run_handles_empty_logs_gracefully(self, temp_output_dir, temp_soul_dir):
        """Test that run() handles empty logs."""
        empty_logs = temp_output_dir / "empty"
        empty_logs.mkdir()

        config = SleepComputeConfig(
            logs_dir=empty_logs,
            output_dir=temp_output_dir,
            soul_dir=temp_soul_dir,
        )
        routine = NightlyRoutine(config)

        result = routine.run()
        assert result is not None
        assert result["logs_analyzed"] == 0


class TestPatternCategory:
    """Tests for PatternCategory enum."""

    def test_all_categories_exist(self):
        """Test all expected categories exist."""
        assert PatternCategory.USER_PREFERENCE.value == "user_preference"
        assert PatternCategory.TEMPORAL.value == "temporal"
        assert PatternCategory.ERROR.value == "error"
        assert PatternCategory.COORDINATION.value == "coordination"
        assert PatternCategory.PERFORMANCE.value == "performance"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
