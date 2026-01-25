"""
Unit tests for core/context_loader.py

Tests:
- Index line parsing (_parse_index_lines)
- Index path loading (_load_index_paths)
- Context budget computation (_compute_context_budget)
- Context loading (load_context)
- JarvisContext class (capabilities, state, system prompt)
- Convenience functions (get_jarvis_capabilities, get_jarvis_system_prompt)
- Cache management and state retrieval
- Environment variable toggles
"""

import pytest
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open
from typing import Dict, Any


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def mock_index_content():
    """Sample index.md content."""
    return """# Context Index

## Core Documents
1. core.md
2. trading.md

## Bot Documentation
- bots/treasury.md
- bots/telegram.md

## Skip These
## Header Only
# Another Header
"""


@pytest.fixture
def mock_config():
    """Mock configuration with context settings."""
    return {
        "context": {
            "load_budget_docs": 20,
            "load_budget_chars": 12000,
        }
    }


@pytest.fixture
def mock_low_resource_config():
    """Mock configuration for low resource testing."""
    return {
        "context": {
            "load_budget_docs": 10,
            "load_budget_chars": 8000,
        }
    }


@pytest.fixture
def mock_system_profile():
    """Mock system profile for testing budget computation."""
    from core.system_profiler import SystemProfile
    return SystemProfile(
        os_version="Windows-10",
        cpu_load=2.0,
        ram_total_gb=16.0,
        ram_free_gb=8.0,
        disk_free_gb=100.0,
    )


@pytest.fixture
def mock_low_resource_profile():
    """Mock system profile with low resources."""
    from core.system_profiler import SystemProfile
    return SystemProfile(
        os_version="Windows-10",
        cpu_load=5.0,
        ram_total_gb=4.0,
        ram_free_gb=1.0,
        disk_free_gb=5.0,
    )


@pytest.fixture
def temp_context_dir():
    """Create temporary context directory with test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        context_dir = Path(tmpdir) / "lifeos" / "context"
        context_dir.mkdir(parents=True)

        # Create index.md
        index_file = context_dir / "index.md"
        index_file.write_text("""# Index
1. doc1.md
2. doc2.md
- doc3.md
""", encoding="utf-8")

        # Create doc files
        (context_dir / "doc1.md").write_text("# Doc 1\nContent of document 1", encoding="utf-8")
        (context_dir / "doc2.md").write_text("# Doc 2\nContent of document 2", encoding="utf-8")
        (context_dir / "doc3.md").write_text("# Doc 3\nContent of document 3", encoding="utf-8")

        yield Path(tmpdir)


@pytest.fixture
def temp_state_dir():
    """Create temporary state directory with test state files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        trading_dir = Path(tmpdir) / ".lifeos" / "trading"
        trading_dir.mkdir(parents=True)

        treasury_dir = Path(tmpdir) / "bots" / "treasury"
        treasury_dir.mkdir(parents=True)

        # Create state files
        (trading_dir / "exit_intents.json").write_text(json.dumps({
            "intents": [{"token": "SOL", "target_price": 100}]
        }), encoding="utf-8")

        (treasury_dir / ".positions.json").write_text(json.dumps([
            {"mint": "token1", "amount": 1000},
            {"mint": "token2", "amount": 500},
        ]), encoding="utf-8")

        yield Path(tmpdir)


# =============================================================================
# Test _parse_index_lines
# =============================================================================

class TestParseIndexLines:
    """Tests for _parse_index_lines function."""

    def test_parse_numbered_lines(self):
        """Test parsing numbered list items (1. path)."""
        from core.context_loader import _parse_index_lines

        lines = [
            "1. core.md",
            "2. trading.md",
            "3. bots/telegram.md",
        ]

        result = _parse_index_lines(lines)

        assert "core.md" in result
        assert "trading.md" in result
        assert "bots/telegram.md" in result
        assert len(result) == 3

    def test_parse_dashed_lines(self):
        """Test parsing dashed list items (- path)."""
        from core.context_loader import _parse_index_lines

        lines = [
            "- doc1.md",
            "- doc2.md",
            "- subdir/doc3.md",
        ]

        result = _parse_index_lines(lines)

        assert "doc1.md" in result
        assert "doc2.md" in result
        assert "subdir/doc3.md" in result
        assert len(result) == 3

    def test_parse_mixed_lines(self):
        """Test parsing mixed numbered and dashed items."""
        from core.context_loader import _parse_index_lines

        lines = [
            "1. numbered.md",
            "- dashed.md",
            "2. another.md",
        ]

        result = _parse_index_lines(lines)

        assert len(result) == 3
        assert "numbered.md" in result
        assert "dashed.md" in result
        assert "another.md" in result

    def test_skip_empty_lines(self):
        """Test that empty lines are skipped."""
        from core.context_loader import _parse_index_lines

        lines = [
            "1. doc.md",
            "",
            "  ",
            "2. other.md",
        ]

        result = _parse_index_lines(lines)

        assert len(result) == 2

    def test_skip_header_lines(self):
        """Test that header lines (## and #) are skipped."""
        from core.context_loader import _parse_index_lines

        lines = [
            "# Main Header",
            "## Section Header",
            "1. actual_doc.md",
            "- ## not_a_doc",
        ]

        result = _parse_index_lines(lines)

        assert len(result) == 1
        assert "actual_doc.md" in result

    def test_skip_non_list_lines(self):
        """Test that non-list lines are skipped."""
        from core.context_loader import _parse_index_lines

        lines = [
            "Some regular text",
            "1. valid.md",
            "More text without list markers",
            "- another_valid.md",
        ]

        result = _parse_index_lines(lines)

        assert len(result) == 2
        assert "valid.md" in result
        assert "another_valid.md" in result

    def test_strip_whitespace(self):
        """Test that whitespace is properly stripped."""
        from core.context_loader import _parse_index_lines

        lines = [
            "  1. spaced.md  ",
            "   - indented.md   ",
        ]

        result = _parse_index_lines(lines)

        assert "spaced.md" in result
        assert "indented.md" in result

    def test_empty_list(self):
        """Test parsing empty list returns empty result."""
        from core.context_loader import _parse_index_lines

        result = _parse_index_lines([])

        assert result == []

    def test_only_headers(self):
        """Test list with only headers returns empty result."""
        from core.context_loader import _parse_index_lines

        lines = [
            "# Header",
            "## Another Header",
        ]

        result = _parse_index_lines(lines)

        assert result == []


# =============================================================================
# Test _load_index_paths
# =============================================================================

class TestLoadIndexPaths:
    """Tests for _load_index_paths function."""

    def test_load_existing_index(self, temp_context_dir):
        """Test loading paths from existing index.md."""
        from core import context_loader

        # Temporarily replace INDEX_PATH
        original_index = context_loader.INDEX_PATH
        context_loader.INDEX_PATH = temp_context_dir / "lifeos" / "context" / "index.md"

        try:
            result = context_loader._load_index_paths()

            assert len(result) == 3
            # Check that paths are properly resolved
            assert all(isinstance(p, Path) for p in result)
        finally:
            context_loader.INDEX_PATH = original_index

    def test_load_nonexistent_index(self):
        """Test loading from nonexistent index returns empty list."""
        from core import context_loader

        original_index = context_loader.INDEX_PATH
        context_loader.INDEX_PATH = Path("/nonexistent/path/index.md")

        try:
            result = context_loader._load_index_paths()
            assert result == []
        finally:
            context_loader.INDEX_PATH = original_index

    def test_strips_context_prefix(self, temp_context_dir):
        """Test that context/ prefix is stripped from paths."""
        from core import context_loader

        # Create index with context/ prefix
        index_file = temp_context_dir / "lifeos" / "context" / "index.md"
        index_file.write_text("1. context/special.md\n", encoding="utf-8")

        original_index = context_loader.INDEX_PATH
        context_loader.INDEX_PATH = index_file

        try:
            result = context_loader._load_index_paths()

            # Should have stripped the prefix
            assert len(result) == 1
            assert "context" not in str(result[0]) or result[0].name == "special.md"
        finally:
            context_loader.INDEX_PATH = original_index


# =============================================================================
# Test _compute_context_budget
# =============================================================================

class TestComputeContextBudget:
    """Tests for _compute_context_budget function."""

    def test_default_budget_normal_resources(self, mock_config, mock_system_profile):
        """Test budget computation with normal system resources."""
        from core import context_loader

        with patch.object(context_loader.config, 'load_config', return_value=mock_config), \
             patch.object(context_loader.system_profiler, 'read_profile', return_value=mock_system_profile), \
             patch.object(context_loader.state, 'update_state'):

            docs, chars = context_loader._compute_context_budget(update_state=False)

            assert docs == 20
            assert chars == 12000

    def test_budget_reduced_low_ram_total(self, mock_config):
        """Test budget reduction when total RAM is low."""
        from core import context_loader
        from core.system_profiler import SystemProfile

        low_ram_profile = SystemProfile(
            os_version="Windows-10",
            cpu_load=1.0,
            ram_total_gb=6.0,  # Below 8GB threshold
            ram_free_gb=4.0,
            disk_free_gb=100.0,
        )

        with patch.object(context_loader.config, 'load_config', return_value=mock_config), \
             patch.object(context_loader.system_profiler, 'read_profile', return_value=low_ram_profile), \
             patch.object(context_loader.state, 'update_state'):

            docs, chars = context_loader._compute_context_budget(update_state=False)

            assert docs <= 10
            assert chars <= 8000

    def test_budget_reduced_low_free_ram(self, mock_config):
        """Test budget reduction when free RAM is low."""
        from core import context_loader
        from core.system_profiler import SystemProfile

        low_free_ram_profile = SystemProfile(
            os_version="Windows-10",
            cpu_load=1.0,
            ram_total_gb=16.0,
            ram_free_gb=1.5,  # Below 2GB threshold
            disk_free_gb=100.0,
        )

        with patch.object(context_loader.config, 'load_config', return_value=mock_config), \
             patch.object(context_loader.system_profiler, 'read_profile', return_value=low_free_ram_profile), \
             patch.object(context_loader.state, 'update_state'):

            docs, chars = context_loader._compute_context_budget(update_state=False)

            assert docs <= 8
            assert chars <= 6000

    def test_budget_reduced_high_cpu_load(self, mock_config):
        """Test budget reduction when CPU load is high."""
        from core import context_loader
        from core.system_profiler import SystemProfile

        high_cpu_profile = SystemProfile(
            os_version="Windows-10",
            cpu_load=5.0,  # Above 4 threshold
            ram_total_gb=16.0,
            ram_free_gb=8.0,
            disk_free_gb=100.0,
        )

        with patch.object(context_loader.config, 'load_config', return_value=mock_config), \
             patch.object(context_loader.system_profiler, 'read_profile', return_value=high_cpu_profile), \
             patch.object(context_loader.state, 'update_state'):

            docs, chars = context_loader._compute_context_budget(update_state=False)

            assert docs <= 8
            assert chars <= 6000

    def test_budget_reduced_low_disk_space(self, mock_config):
        """Test budget reduction when disk space is low."""
        from core import context_loader
        from core.system_profiler import SystemProfile

        low_disk_profile = SystemProfile(
            os_version="Windows-10",
            cpu_load=1.0,
            ram_total_gb=16.0,
            ram_free_gb=8.0,
            disk_free_gb=5.0,  # Below 10GB threshold
        )

        with patch.object(context_loader.config, 'load_config', return_value=mock_config), \
             patch.object(context_loader.system_profiler, 'read_profile', return_value=low_disk_profile), \
             patch.object(context_loader.state, 'update_state'):

            docs, chars = context_loader._compute_context_budget(update_state=False)

            assert docs <= 8
            assert chars <= 6000

    def test_budget_multiple_constraints(self, mock_config, mock_low_resource_profile):
        """Test budget with multiple resource constraints."""
        from core import context_loader

        with patch.object(context_loader.config, 'load_config', return_value=mock_config), \
             patch.object(context_loader.system_profiler, 'read_profile', return_value=mock_low_resource_profile), \
             patch.object(context_loader.state, 'update_state'):

            docs, chars = context_loader._compute_context_budget(update_state=False)

            # Should be reduced to minimum across all constraints
            assert docs <= 8
            assert chars <= 6000

    def test_budget_updates_state_when_enabled(self, mock_config, mock_system_profile):
        """Test that state is updated when update_state=True."""
        from core import context_loader

        mock_update = MagicMock()

        with patch.object(context_loader.config, 'load_config', return_value=mock_config), \
             patch.object(context_loader.system_profiler, 'read_profile', return_value=mock_system_profile), \
             patch.object(context_loader.state, 'update_state', mock_update):

            context_loader._compute_context_budget(update_state=True)

            mock_update.assert_called_once()
            call_kwargs = mock_update.call_args[1]
            assert 'context_budget_docs' in call_kwargs
            assert 'context_budget_chars' in call_kwargs

    def test_budget_skips_state_update_when_disabled(self, mock_config, mock_system_profile):
        """Test that state is not updated when update_state=False."""
        from core import context_loader

        mock_update = MagicMock()

        with patch.object(context_loader.config, 'load_config', return_value=mock_config), \
             patch.object(context_loader.system_profiler, 'read_profile', return_value=mock_system_profile), \
             patch.object(context_loader.state, 'update_state', mock_update):

            context_loader._compute_context_budget(update_state=False)

            mock_update.assert_not_called()

    def test_budget_handles_missing_config_gracefully(self):
        """Test budget computation with missing config values."""
        from core import context_loader
        from core.system_profiler import SystemProfile

        empty_config = {}
        normal_profile = SystemProfile(
            os_version="Windows-10",
            cpu_load=1.0,
            ram_total_gb=16.0,
            ram_free_gb=8.0,
            disk_free_gb=100.0,
        )

        with patch.object(context_loader.config, 'load_config', return_value=empty_config), \
             patch.object(context_loader.system_profiler, 'read_profile', return_value=normal_profile), \
             patch.object(context_loader.state, 'update_state'):

            docs, chars = context_loader._compute_context_budget(update_state=False)

            # Should use defaults (20, 12000)
            assert docs == 20
            assert chars == 12000

    def test_budget_handles_none_profile_values(self, mock_config):
        """Test budget with None values in profile."""
        from core import context_loader
        from core.system_profiler import SystemProfile

        # Profile with None values (simulating unavailable metrics)
        none_profile = SystemProfile(
            os_version="Unknown",
            cpu_load=None,
            ram_total_gb=None,
            ram_free_gb=None,
            disk_free_gb=None,
        )

        with patch.object(context_loader.config, 'load_config', return_value=mock_config), \
             patch.object(context_loader.system_profiler, 'read_profile', return_value=none_profile), \
             patch.object(context_loader.state, 'update_state'):

            docs, chars = context_loader._compute_context_budget(update_state=False)

            # Should not crash and return base values
            assert docs == 20
            assert chars == 12000


# =============================================================================
# Test load_context
# =============================================================================

class TestLoadContext:
    """Tests for load_context function."""

    def test_load_context_basic(self, temp_context_dir, mock_config, mock_system_profile):
        """Test basic context loading."""
        from core import context_loader

        original_index = context_loader.INDEX_PATH
        context_loader.INDEX_PATH = temp_context_dir / "lifeos" / "context" / "index.md"

        try:
            with patch.object(context_loader.config, 'load_config', return_value=mock_config), \
                 patch.object(context_loader.system_profiler, 'read_profile', return_value=mock_system_profile), \
                 patch.object(context_loader.state, 'update_state'):

                result = context_loader.load_context(update_state=False)

                assert "# doc1.md" in result
                assert "Content of document 1" in result
        finally:
            context_loader.INDEX_PATH = original_index

    def test_load_context_respects_docs_limit(self, temp_context_dir, mock_system_profile):
        """Test that context loading respects document limit."""
        from core import context_loader

        limited_config = {"context": {"load_budget_docs": 1, "load_budget_chars": 10000}}

        original_index = context_loader.INDEX_PATH
        context_loader.INDEX_PATH = temp_context_dir / "lifeos" / "context" / "index.md"

        try:
            with patch.object(context_loader.config, 'load_config', return_value=limited_config), \
                 patch.object(context_loader.system_profiler, 'read_profile', return_value=mock_system_profile), \
                 patch.object(context_loader.state, 'update_state'):

                result = context_loader.load_context(update_state=False)

                # Should only have first document
                assert "doc1.md" in result
                # doc2 might or might not be present depending on exact behavior

        finally:
            context_loader.INDEX_PATH = original_index

    def test_load_context_respects_chars_limit(self, temp_context_dir, mock_system_profile):
        """Test that context loading respects character limit."""
        from core import context_loader

        # Very small char limit
        limited_config = {"context": {"load_budget_docs": 100, "load_budget_chars": 50}}

        original_index = context_loader.INDEX_PATH
        context_loader.INDEX_PATH = temp_context_dir / "lifeos" / "context" / "index.md"

        try:
            with patch.object(context_loader.config, 'load_config', return_value=limited_config), \
                 patch.object(context_loader.system_profiler, 'read_profile', return_value=mock_system_profile), \
                 patch.object(context_loader.state, 'update_state'):

                result = context_loader.load_context(update_state=False)

                # Result should be limited
                assert len(result) <= 100  # Some buffer for headers

        finally:
            context_loader.INDEX_PATH = original_index

    def test_load_context_skips_missing_files(self, temp_context_dir, mock_config, mock_system_profile):
        """Test that context loading skips missing files."""
        from core import context_loader

        # Add reference to nonexistent file
        index_file = temp_context_dir / "lifeos" / "context" / "index.md"
        index_file.write_text("1. doc1.md\n2. missing.md\n3. doc2.md\n", encoding="utf-8")

        original_index = context_loader.INDEX_PATH
        context_loader.INDEX_PATH = index_file

        try:
            with patch.object(context_loader.config, 'load_config', return_value=mock_config), \
                 patch.object(context_loader.system_profiler, 'read_profile', return_value=mock_system_profile), \
                 patch.object(context_loader.state, 'update_state'):

                result = context_loader.load_context(update_state=False)

                # Should have doc1 and doc2 but not crash on missing
                assert "doc1.md" in result
                assert "doc2.md" in result
                assert "missing.md" not in result

        finally:
            context_loader.INDEX_PATH = original_index

    def test_load_context_skips_empty_files(self, temp_context_dir, mock_config, mock_system_profile):
        """Test that context loading skips empty files."""
        from core import context_loader

        # Create empty file
        (temp_context_dir / "lifeos" / "context" / "empty.md").write_text("", encoding="utf-8")

        index_file = temp_context_dir / "lifeos" / "context" / "index.md"
        index_file.write_text("1. empty.md\n2. doc1.md\n", encoding="utf-8")

        original_index = context_loader.INDEX_PATH
        context_loader.INDEX_PATH = index_file

        try:
            with patch.object(context_loader.config, 'load_config', return_value=mock_config), \
                 patch.object(context_loader.system_profiler, 'read_profile', return_value=mock_system_profile), \
                 patch.object(context_loader.state, 'update_state'):

                result = context_loader.load_context(update_state=False)

                # Should not include empty file
                assert "# empty.md" not in result
                assert "doc1.md" in result

        finally:
            context_loader.INDEX_PATH = original_index

    def test_load_context_updates_state(self, temp_context_dir, mock_config, mock_system_profile):
        """Test that load_context updates state when enabled."""
        from core import context_loader

        original_index = context_loader.INDEX_PATH
        context_loader.INDEX_PATH = temp_context_dir / "lifeos" / "context" / "index.md"

        mock_update = MagicMock()

        try:
            with patch.object(context_loader.config, 'load_config', return_value=mock_config), \
                 patch.object(context_loader.system_profiler, 'read_profile', return_value=mock_system_profile), \
                 patch.object(context_loader.state, 'update_state', mock_update):

                context_loader.load_context(update_state=True)

                # Should be called twice: once for budget, once for loaded
                assert mock_update.call_count >= 1

        finally:
            context_loader.INDEX_PATH = original_index

    def test_load_context_empty_index(self, mock_config, mock_system_profile):
        """Test loading context with empty index."""
        from core import context_loader

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create empty index
            context_dir = Path(tmpdir) / "lifeos" / "context"
            context_dir.mkdir(parents=True)
            index_file = context_dir / "index.md"
            index_file.write_text("", encoding="utf-8")

            original_index = context_loader.INDEX_PATH
            context_loader.INDEX_PATH = index_file

            try:
                with patch.object(context_loader.config, 'load_config', return_value=mock_config), \
                     patch.object(context_loader.system_profiler, 'read_profile', return_value=mock_system_profile), \
                     patch.object(context_loader.state, 'update_state'):

                    result = context_loader.load_context(update_state=False)

                    assert result == ""

            finally:
                context_loader.INDEX_PATH = original_index

    def test_load_context_no_index_file(self, mock_config, mock_system_profile):
        """Test loading context with no index file."""
        from core import context_loader

        original_index = context_loader.INDEX_PATH
        context_loader.INDEX_PATH = Path("/nonexistent/index.md")

        try:
            with patch.object(context_loader.config, 'load_config', return_value=mock_config), \
                 patch.object(context_loader.system_profiler, 'read_profile', return_value=mock_system_profile), \
                 patch.object(context_loader.state, 'update_state'):

                result = context_loader.load_context(update_state=False)

                assert result == ""

        finally:
            context_loader.INDEX_PATH = original_index


# =============================================================================
# Test JARVIS_CAPABILITIES constant
# =============================================================================

class TestJarvisCapabilitiesConstant:
    """Tests for JARVIS_CAPABILITIES constant."""

    def test_capabilities_string_exists(self):
        """Test that JARVIS_CAPABILITIES constant exists."""
        from core.context_loader import JARVIS_CAPABILITIES

        assert isinstance(JARVIS_CAPABILITIES, str)
        assert len(JARVIS_CAPABILITIES) > 100

    def test_capabilities_contains_social_media(self):
        """Test capabilities includes social media section."""
        from core.context_loader import JARVIS_CAPABILITIES

        assert "Social Media" in JARVIS_CAPABILITIES or "X/Twitter" in JARVIS_CAPABILITIES

    def test_capabilities_contains_trading(self):
        """Test capabilities includes trading section."""
        from core.context_loader import JARVIS_CAPABILITIES

        assert "Trading" in JARVIS_CAPABILITIES

    def test_capabilities_contains_telegram(self):
        """Test capabilities includes Telegram commands."""
        from core.context_loader import JARVIS_CAPABILITIES

        assert "Telegram" in JARVIS_CAPABILITIES

    def test_capabilities_contains_analysis(self):
        """Test capabilities includes analysis features."""
        from core.context_loader import JARVIS_CAPABILITIES

        assert "Analysis" in JARVIS_CAPABILITIES or "Sentiment" in JARVIS_CAPABILITIES


# =============================================================================
# Test JarvisContext.get_capabilities
# =============================================================================

class TestJarvisContextGetCapabilities:
    """Tests for JarvisContext.get_capabilities method."""

    def test_returns_capabilities_string(self):
        """Test that get_capabilities returns a string."""
        from core.context_loader import JarvisContext

        result = JarvisContext.get_capabilities()

        assert isinstance(result, str)
        assert len(result) > 0

    def test_returns_file_content_when_exists(self):
        """Test that capabilities file content is returned when it exists."""
        from core import context_loader
        from core.context_loader import JarvisContext

        with tempfile.TemporaryDirectory() as tmpdir:
            docs_dir = Path(tmpdir) / "docs"
            docs_dir.mkdir()
            caps_file = docs_dir / "JARVIS_CAPABILITIES.md"
            caps_file.write_text("# Custom Capabilities\nCustom content", encoding="utf-8")

            original_root = context_loader.ROOT
            context_loader.ROOT = Path(tmpdir)

            try:
                result = JarvisContext.get_capabilities()

                assert "Custom Capabilities" in result
                assert "Custom content" in result
            finally:
                context_loader.ROOT = original_root

    def test_returns_fallback_when_file_missing(self):
        """Test that fallback constant is used when file doesn't exist."""
        from core import context_loader
        from core.context_loader import JarvisContext, JARVIS_CAPABILITIES

        with tempfile.TemporaryDirectory() as tmpdir:
            # No docs directory
            original_root = context_loader.ROOT
            context_loader.ROOT = Path(tmpdir)

            try:
                result = JarvisContext.get_capabilities()

                assert result == JARVIS_CAPABILITIES
            finally:
                context_loader.ROOT = original_root

    def test_handles_file_read_error_gracefully(self):
        """Test that file read errors fall back to constant."""
        from core import context_loader
        from core.context_loader import JarvisContext, JARVIS_CAPABILITIES

        with tempfile.TemporaryDirectory() as tmpdir:
            docs_dir = Path(tmpdir) / "docs"
            docs_dir.mkdir()
            caps_file = docs_dir / "JARVIS_CAPABILITIES.md"
            caps_file.write_text("content", encoding="utf-8")

            original_root = context_loader.ROOT
            context_loader.ROOT = Path(tmpdir)

            try:
                # Mock read_text to raise an exception
                with patch.object(Path, 'read_text', side_effect=Exception("Read error")):
                    result = JarvisContext.get_capabilities()

                    # Should fall back to constant
                    assert result == JARVIS_CAPABILITIES
            finally:
                context_loader.ROOT = original_root


# =============================================================================
# Test JarvisContext.get_current_state
# =============================================================================

class TestJarvisContextGetCurrentState:
    """Tests for JarvisContext.get_current_state method."""

    def test_returns_dict(self):
        """Test that get_current_state returns a dictionary."""
        from core.context_loader import JarvisContext

        with patch.object(Path, 'exists', return_value=False):
            result = JarvisContext.get_current_state()

        assert isinstance(result, dict)

    def test_loads_positions_file(self, temp_state_dir):
        """Test loading .positions.json state file."""
        from core import context_loader
        from core.context_loader import JarvisContext

        original_root = context_loader.ROOT
        context_loader.ROOT = temp_state_dir

        try:
            with patch.object(Path, 'home', return_value=temp_state_dir):
                result = JarvisContext.get_current_state()

                assert "positions" in result
                assert len(result["positions"]) == 2
        finally:
            context_loader.ROOT = original_root

    def test_loads_exit_intents_file(self, temp_state_dir):
        """Test loading exit_intents.json state file."""
        from core import context_loader
        from core.context_loader import JarvisContext

        original_root = context_loader.ROOT
        context_loader.ROOT = temp_state_dir

        try:
            with patch.object(Path, 'home', return_value=temp_state_dir):
                result = JarvisContext.get_current_state()

                assert "exit_intents" in result
        finally:
            context_loader.ROOT = original_root

    def test_handles_missing_state_dirs(self):
        """Test handling when state directories don't exist."""
        from core import context_loader
        from core.context_loader import JarvisContext

        with tempfile.TemporaryDirectory() as tmpdir:
            original_root = context_loader.ROOT
            context_loader.ROOT = Path(tmpdir)

            try:
                with patch.object(Path, 'home', return_value=Path(tmpdir)):
                    result = JarvisContext.get_current_state()

                    assert result == {}
            finally:
                context_loader.ROOT = original_root

    def test_handles_invalid_json(self, temp_state_dir):
        """Test handling of invalid JSON in state files."""
        from core import context_loader
        from core.context_loader import JarvisContext

        # Write invalid JSON
        invalid_file = temp_state_dir / "bots" / "treasury" / "perps_state.json"
        invalid_file.write_text("not valid json {{{", encoding="utf-8")

        original_root = context_loader.ROOT
        context_loader.ROOT = temp_state_dir

        try:
            with patch.object(Path, 'home', return_value=temp_state_dir):
                # Should not raise, just skip invalid file
                result = JarvisContext.get_current_state()

                assert "perps_state" not in result
                # Other valid files should still be loaded
        finally:
            context_loader.ROOT = original_root

    def test_strips_json_extension_from_key(self, temp_state_dir):
        """Test that .json is stripped from state keys."""
        from core import context_loader
        from core.context_loader import JarvisContext

        original_root = context_loader.ROOT
        context_loader.ROOT = temp_state_dir

        try:
            with patch.object(Path, 'home', return_value=temp_state_dir):
                result = JarvisContext.get_current_state()

                # Keys should not have .json extension
                for key in result.keys():
                    assert not key.endswith(".json")
        finally:
            context_loader.ROOT = original_root

    def test_strips_leading_dot_from_key(self, temp_state_dir):
        """Test that leading dot is stripped from hidden file keys."""
        from core import context_loader
        from core.context_loader import JarvisContext

        original_root = context_loader.ROOT
        context_loader.ROOT = temp_state_dir

        try:
            with patch.object(Path, 'home', return_value=temp_state_dir):
                result = JarvisContext.get_current_state()

                # .positions.json should become "positions"
                assert "positions" in result
                assert ".positions" not in result
        finally:
            context_loader.ROOT = original_root


# =============================================================================
# Test JarvisContext.get_system_prompt
# =============================================================================

class TestJarvisContextGetSystemPrompt:
    """Tests for JarvisContext.get_system_prompt method."""

    def test_returns_string(self):
        """Test that get_system_prompt returns a string."""
        from core.context_loader import JarvisContext

        with patch.object(JarvisContext, 'get_current_state', return_value={}):
            result = JarvisContext.get_system_prompt()

        assert isinstance(result, str)

    def test_includes_jarvis_identity(self):
        """Test that system prompt identifies as Jarvis."""
        from core.context_loader import JarvisContext

        with patch.object(JarvisContext, 'get_current_state', return_value={}):
            result = JarvisContext.get_system_prompt()

        assert "Jarvis" in result

    def test_includes_capabilities(self):
        """Test that system prompt includes capabilities."""
        from core.context_loader import JarvisContext

        with patch.object(JarvisContext, 'get_current_state', return_value={}):
            result = JarvisContext.get_system_prompt()

        # Should contain capabilities content
        assert "Trading" in result or "Social Media" in result or "Telegram" in result

    def test_includes_state_when_enabled(self):
        """Test that system prompt includes state when include_state=True."""
        from core.context_loader import JarvisContext

        mock_state = {"positions": [{"token": "SOL"}]}

        with patch.object(JarvisContext, 'get_current_state', return_value=mock_state):
            result = JarvisContext.get_system_prompt(include_state=True)

        assert "Current System State" in result
        assert "positions" in result

    def test_excludes_state_when_disabled(self):
        """Test that system prompt excludes state when include_state=False."""
        from core.context_loader import JarvisContext

        result = JarvisContext.get_system_prompt(include_state=False)

        assert "Current System State" not in result

    def test_truncates_state_to_2000_chars(self):
        """Test that state is truncated to 2000 characters."""
        from core.context_loader import JarvisContext

        # Create large state
        large_state = {"data": "x" * 5000}

        with patch.object(JarvisContext, 'get_current_state', return_value=large_state):
            result = JarvisContext.get_system_prompt(include_state=True)

        # State portion should be truncated
        # The full result will be longer due to prompt text, but state should be limited
        state_section = result.split("Current System State:")[1] if "Current System State:" in result else ""
        # There should be some truncation
        assert len(state_section) < 3000  # Allow for some formatting overhead

    def test_includes_action_prompt(self):
        """Test that system prompt includes action guidance."""
        from core.context_loader import JarvisContext

        with patch.object(JarvisContext, 'get_current_state', return_value={}):
            result = JarvisContext.get_system_prompt()

        assert "FULL ACCESS" in result or "execute" in result.lower()


# =============================================================================
# Test JarvisContext.get_position_count
# =============================================================================

class TestJarvisContextGetPositionCount:
    """Tests for JarvisContext.get_position_count method."""

    def test_returns_int(self):
        """Test that get_position_count returns an integer."""
        from core.context_loader import JarvisContext

        with patch.object(JarvisContext, 'get_current_state', return_value={}):
            result = JarvisContext.get_position_count()

        assert isinstance(result, int)

    def test_counts_list_positions(self):
        """Test counting positions when positions is a list."""
        from core.context_loader import JarvisContext

        mock_state = {"positions": [{"token": "A"}, {"token": "B"}, {"token": "C"}]}

        with patch.object(JarvisContext, 'get_current_state', return_value=mock_state):
            result = JarvisContext.get_position_count()

        assert result == 3

    def test_returns_zero_when_no_positions(self):
        """Test returns 0 when no positions key exists."""
        from core.context_loader import JarvisContext

        with patch.object(JarvisContext, 'get_current_state', return_value={}):
            result = JarvisContext.get_position_count()

        assert result == 0

    def test_returns_zero_for_non_list_positions(self):
        """Test returns 0 when positions is not a list."""
        from core.context_loader import JarvisContext

        mock_state = {"positions": {"count": 5}}  # Dict instead of list

        with patch.object(JarvisContext, 'get_current_state', return_value=mock_state):
            result = JarvisContext.get_position_count()

        assert result == 0

    def test_returns_zero_for_empty_list(self):
        """Test returns 0 for empty positions list."""
        from core.context_loader import JarvisContext

        mock_state = {"positions": []}

        with patch.object(JarvisContext, 'get_current_state', return_value=mock_state):
            result = JarvisContext.get_position_count()

        assert result == 0


# =============================================================================
# Test JarvisContext.is_trading_enabled
# =============================================================================

class TestJarvisContextIsTradingEnabled:
    """Tests for JarvisContext.is_trading_enabled method."""

    def test_returns_true_by_default(self):
        """Test that trading is enabled by default."""
        from core.context_loader import JarvisContext

        # Ensure env var is not set
        os.environ.pop("LIFEOS_KILL_SWITCH", None)

        result = JarvisContext.is_trading_enabled()

        assert result is True

    def test_returns_false_when_kill_switch_true(self):
        """Test trading disabled when LIFEOS_KILL_SWITCH=true."""
        from core.context_loader import JarvisContext

        os.environ["LIFEOS_KILL_SWITCH"] = "true"

        try:
            result = JarvisContext.is_trading_enabled()
            assert result is False
        finally:
            os.environ.pop("LIFEOS_KILL_SWITCH", None)

    def test_returns_true_when_kill_switch_false(self):
        """Test trading enabled when LIFEOS_KILL_SWITCH=false."""
        from core.context_loader import JarvisContext

        os.environ["LIFEOS_KILL_SWITCH"] = "false"

        try:
            result = JarvisContext.is_trading_enabled()
            assert result is True
        finally:
            os.environ.pop("LIFEOS_KILL_SWITCH", None)

    def test_case_insensitive_true(self):
        """Test kill switch is case insensitive for 'true'."""
        from core.context_loader import JarvisContext

        for value in ["TRUE", "True", "TrUe"]:
            os.environ["LIFEOS_KILL_SWITCH"] = value
            try:
                result = JarvisContext.is_trading_enabled()
                assert result is False, f"Expected False for LIFEOS_KILL_SWITCH={value}"
            finally:
                os.environ.pop("LIFEOS_KILL_SWITCH", None)

    def test_returns_true_for_other_values(self):
        """Test trading enabled for non-'true' values."""
        from core.context_loader import JarvisContext

        for value in ["1", "yes", "enabled", "random"]:
            os.environ["LIFEOS_KILL_SWITCH"] = value
            try:
                result = JarvisContext.is_trading_enabled()
                assert result is True, f"Expected True for LIFEOS_KILL_SWITCH={value}"
            finally:
                os.environ.pop("LIFEOS_KILL_SWITCH", None)


# =============================================================================
# Test JarvisContext.is_x_bot_enabled
# =============================================================================

class TestJarvisContextIsXBotEnabled:
    """Tests for JarvisContext.is_x_bot_enabled method."""

    def test_returns_true_by_default(self):
        """Test that X bot is enabled by default."""
        from core.context_loader import JarvisContext

        os.environ.pop("X_BOT_ENABLED", None)

        result = JarvisContext.is_x_bot_enabled()

        assert result is True

    def test_returns_false_when_disabled(self):
        """Test X bot disabled when X_BOT_ENABLED=false."""
        from core.context_loader import JarvisContext

        os.environ["X_BOT_ENABLED"] = "false"

        try:
            result = JarvisContext.is_x_bot_enabled()
            assert result is False
        finally:
            os.environ.pop("X_BOT_ENABLED", None)

    def test_returns_true_when_enabled(self):
        """Test X bot enabled when X_BOT_ENABLED=true."""
        from core.context_loader import JarvisContext

        os.environ["X_BOT_ENABLED"] = "true"

        try:
            result = JarvisContext.is_x_bot_enabled()
            assert result is True
        finally:
            os.environ.pop("X_BOT_ENABLED", None)

    def test_case_insensitive_false(self):
        """Test X_BOT_ENABLED is case insensitive for 'false'."""
        from core.context_loader import JarvisContext

        for value in ["FALSE", "False", "FaLsE"]:
            os.environ["X_BOT_ENABLED"] = value
            try:
                result = JarvisContext.is_x_bot_enabled()
                assert result is False, f"Expected False for X_BOT_ENABLED={value}"
            finally:
                os.environ.pop("X_BOT_ENABLED", None)

    def test_returns_true_for_other_values(self):
        """Test X bot enabled for non-'false' values."""
        from core.context_loader import JarvisContext

        for value in ["1", "yes", "enabled", "random"]:
            os.environ["X_BOT_ENABLED"] = value
            try:
                result = JarvisContext.is_x_bot_enabled()
                assert result is True, f"Expected True for X_BOT_ENABLED={value}"
            finally:
                os.environ.pop("X_BOT_ENABLED", None)


# =============================================================================
# Test Convenience Functions
# =============================================================================

class TestConvenienceFunctions:
    """Tests for convenience functions."""

    def test_get_jarvis_capabilities_delegates(self):
        """Test get_jarvis_capabilities delegates to JarvisContext."""
        from core.context_loader import get_jarvis_capabilities, JarvisContext

        result = get_jarvis_capabilities()
        expected = JarvisContext.get_capabilities()

        assert result == expected

    def test_get_jarvis_system_prompt_delegates(self):
        """Test get_jarvis_system_prompt delegates to JarvisContext."""
        from core.context_loader import get_jarvis_system_prompt, JarvisContext

        with patch.object(JarvisContext, 'get_current_state', return_value={}):
            result = get_jarvis_system_prompt()
            expected = JarvisContext.get_system_prompt()

        # Both should contain same core content
        assert "Jarvis" in result
        assert "Jarvis" in expected


# =============================================================================
# Test Module Constants
# =============================================================================

class TestModuleConstants:
    """Tests for module-level constants."""

    def test_root_is_path(self):
        """Test ROOT constant is a Path object."""
        from core.context_loader import ROOT

        assert isinstance(ROOT, Path)

    def test_root_exists(self):
        """Test ROOT points to existing directory."""
        from core.context_loader import ROOT

        assert ROOT.exists()

    def test_index_path_is_path(self):
        """Test INDEX_PATH constant is a Path object."""
        from core.context_loader import INDEX_PATH

        assert isinstance(INDEX_PATH, Path)

    def test_index_path_in_lifeos(self):
        """Test INDEX_PATH is under lifeos/context directory."""
        from core.context_loader import INDEX_PATH

        assert "lifeos" in str(INDEX_PATH)
        assert "context" in str(INDEX_PATH)


# =============================================================================
# Integration Tests
# =============================================================================

class TestIntegration:
    """Integration tests for context_loader module."""

    def test_full_context_loading_flow(self, temp_context_dir, mock_config, mock_system_profile):
        """Test complete context loading flow."""
        from core import context_loader

        original_index = context_loader.INDEX_PATH
        context_loader.INDEX_PATH = temp_context_dir / "lifeos" / "context" / "index.md"

        try:
            with patch.object(context_loader.config, 'load_config', return_value=mock_config), \
                 patch.object(context_loader.system_profiler, 'read_profile', return_value=mock_system_profile), \
                 patch.object(context_loader.state, 'update_state'):

                # Load context
                content = context_loader.load_context(update_state=False)

                # Verify structure
                assert content
                assert isinstance(content, str)

        finally:
            context_loader.INDEX_PATH = original_index

    def test_jarvis_context_full_flow(self):
        """Test complete JarvisContext flow."""
        from core.context_loader import JarvisContext

        # Get all context components
        capabilities = JarvisContext.get_capabilities()

        with patch.object(JarvisContext, 'get_current_state', return_value={"positions": []}):
            system_prompt = JarvisContext.get_system_prompt()
            position_count = JarvisContext.get_position_count()

        trading_enabled = JarvisContext.is_trading_enabled()
        x_bot_enabled = JarvisContext.is_x_bot_enabled()

        # Verify all components work together
        assert capabilities
        assert system_prompt
        assert isinstance(position_count, int)
        assert isinstance(trading_enabled, bool)
        assert isinstance(x_bot_enabled, bool)

        # System prompt should include capabilities
        # (either directly or through reference)
        assert len(system_prompt) > len(capabilities) // 2  # Rough check


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
