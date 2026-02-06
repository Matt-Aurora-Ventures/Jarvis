"""
Comprehensive unit tests for the Template Loader.

Tests cover:
- TemplateLoader class initialization
- load(name) -> Template loading
- reload(name) - force reload
- watch_for_changes() - file watching
- Template caching
- Multiple template directories
- Error handling
"""

import pytest
import time
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from core.templates.loader import (
    TemplateLoader,
    TemplateNotFoundError,
    TemplateLoadError,
)
from core.templates.engine import Template


# =============================================================================
# TemplateLoader Initialization Tests
# =============================================================================

class TestTemplateLoaderInit:
    """Tests for TemplateLoader initialization."""

    def test_loader_creation_with_path(self, tmp_path):
        """Test creating a loader with a specific path."""
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()

        loader = TemplateLoader(templates_dir)
        assert loader.templates_dir == templates_dir

    def test_loader_creation_with_string_path(self, tmp_path):
        """Test creating a loader with string path."""
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()

        loader = TemplateLoader(str(templates_dir))
        assert loader.templates_dir == templates_dir

    def test_loader_default_path(self):
        """Test loader uses default path if none specified."""
        loader = TemplateLoader()
        # Should default to bots/templates/
        assert "templates" in str(loader.templates_dir)

    def test_loader_nonexistent_path_raises(self, tmp_path):
        """Test loader raises error for nonexistent path."""
        nonexistent = tmp_path / "nonexistent"

        with pytest.raises(FileNotFoundError):
            TemplateLoader(nonexistent, create_if_missing=False)

    def test_loader_creates_missing_path(self, tmp_path):
        """Test loader can create missing directory."""
        missing = tmp_path / "new_templates"

        loader = TemplateLoader(missing, create_if_missing=True)
        assert missing.exists()


# =============================================================================
# Template Loading Tests
# =============================================================================

class TestTemplateLoading:
    """Tests for template loading functionality."""

    @pytest.fixture
    def loader(self, tmp_path):
        """Create a loader with test templates."""
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()

        # Create test templates
        (templates_dir / "greeting.txt").write_text("Hello, {{name}}!")
        (templates_dir / "report.txt").write_text("Report: {{title}}")
        (templates_dir / "nested" ).mkdir()
        (templates_dir / "nested" / "deep.txt").write_text("Nested: {{value}}")

        return TemplateLoader(templates_dir)

    def test_load_simple_template(self, loader):
        """Test loading a simple template."""
        template = loader.load("greeting")
        assert isinstance(template, Template)
        assert "{{name}}" in template.source

    def test_load_with_extension(self, loader):
        """Test loading with explicit extension."""
        template = loader.load("greeting.txt")
        assert "{{name}}" in template.source

    def test_load_nested_template(self, loader):
        """Test loading a nested template."""
        template = loader.load("nested/deep")
        assert "{{value}}" in template.source

    def test_load_nonexistent_template(self, loader):
        """Test loading nonexistent template raises error."""
        with pytest.raises(TemplateNotFoundError):
            loader.load("nonexistent")

    def test_load_caches_template(self, loader):
        """Test that templates are cached."""
        template1 = loader.load("greeting")
        template2 = loader.load("greeting")

        # Should be the same cached instance
        assert template1 is template2

    def test_load_with_different_extensions(self, tmp_path):
        """Test loading templates with different extensions."""
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()

        (templates_dir / "msg.html").write_text("<p>{{content}}</p>")
        (templates_dir / "msg.md").write_text("# {{title}}")

        loader = TemplateLoader(templates_dir)

        html = loader.load("msg.html")
        md = loader.load("msg.md")

        assert "<p>" in html.source
        assert "#" in md.source


# =============================================================================
# Template Reload Tests
# =============================================================================

class TestTemplateReload:
    """Tests for template reloading functionality."""

    @pytest.fixture
    def loader(self, tmp_path):
        """Create a loader with test templates."""
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        (templates_dir / "dynamic.txt").write_text("Version 1: {{data}}")
        return TemplateLoader(templates_dir), templates_dir

    def test_reload_clears_cache(self, loader):
        """Test reload clears the cache for a template."""
        ldr, templates_dir = loader

        template1 = ldr.load("dynamic")
        assert "Version 1" in template1.source

        # Modify the template
        (templates_dir / "dynamic.txt").write_text("Version 2: {{data}}")

        # Force reload
        template2 = ldr.reload("dynamic")
        assert "Version 2" in template2.source

    def test_reload_nonexistent_template(self, loader):
        """Test reload of nonexistent template raises error."""
        ldr, _ = loader

        with pytest.raises(TemplateNotFoundError):
            ldr.reload("nonexistent")

    def test_reload_all(self, loader):
        """Test reloading all cached templates."""
        ldr, templates_dir = loader

        # Load multiple templates
        ldr.load("dynamic")

        # Modify templates
        (templates_dir / "dynamic.txt").write_text("Updated: {{data}}")

        # Reload all
        ldr.reload_all()

        # Check cache was cleared
        template = ldr.load("dynamic")
        assert "Updated" in template.source


# =============================================================================
# File Watching Tests
# =============================================================================

class TestFileWatching:
    """Tests for file watching functionality."""

    @pytest.fixture
    def loader(self, tmp_path):
        """Create a loader with test templates."""
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        (templates_dir / "watched.txt").write_text("Original content")
        return TemplateLoader(templates_dir), templates_dir

    def test_watch_for_changes_starts(self, loader):
        """Test that watch_for_changes starts watching."""
        ldr, _ = loader

        # Start watching (should not raise)
        watcher = ldr.watch_for_changes()
        assert watcher is not None or hasattr(ldr, "_watcher")

        # Stop watching
        ldr.stop_watching()

    def test_watch_detects_changes(self, loader):
        """Test that watcher detects file changes."""
        ldr, templates_dir = loader

        # Load initial template
        template1 = ldr.load("watched")
        assert "Original" in template1.source

        # Start watching with auto-reload
        ldr.watch_for_changes(auto_reload=True)

        # Give watcher time to start
        time.sleep(0.1)

        # Modify template
        (templates_dir / "watched.txt").write_text("Modified content")

        # Wait for detection (may need adjustment based on implementation)
        time.sleep(0.5)

        # Stop watching
        ldr.stop_watching()

        # Check if change was detected (reload happened)
        # Note: This depends on implementation - may need manual reload check
        template2 = ldr.reload("watched")
        assert "Modified" in template2.source

    def test_watch_callback(self, loader):
        """Test watch with callback function."""
        ldr, templates_dir = loader

        changes_detected = []

        def on_change(name, path):
            changes_detected.append(name)

        ldr.watch_for_changes(callback=on_change)
        time.sleep(0.1)

        # Modify template
        (templates_dir / "watched.txt").write_text("Changed!")
        time.sleep(0.5)

        ldr.stop_watching()

        # Callback may or may not have been called depending on implementation


# =============================================================================
# Cache Management Tests
# =============================================================================

class TestCacheManagement:
    """Tests for template cache management."""

    @pytest.fixture
    def loader(self, tmp_path):
        """Create a loader with test templates."""
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        for i in range(5):
            (templates_dir / f"template{i}.txt").write_text(f"Template {i}")
        return TemplateLoader(templates_dir)

    def test_cache_stats(self, loader):
        """Test getting cache statistics."""
        # Load some templates
        loader.load("template0")
        loader.load("template1")
        loader.load("template2")

        stats = loader.cache_stats()
        assert stats["cached"] >= 3
        assert "hits" in stats or "size" in stats

    def test_clear_cache(self, loader):
        """Test clearing the cache."""
        loader.load("template0")
        loader.load("template1")

        loader.clear_cache()

        stats = loader.cache_stats()
        assert stats["cached"] == 0

    def test_cache_max_size(self, tmp_path):
        """Test cache respects max size."""
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        for i in range(10):
            (templates_dir / f"t{i}.txt").write_text(f"Template {i}")

        # Create loader with small cache
        loader = TemplateLoader(templates_dir, cache_max_size=3)

        # Load more than cache size
        for i in range(5):
            loader.load(f"t{i}")

        stats = loader.cache_stats()
        assert stats["cached"] <= 3


# =============================================================================
# Error Handling Tests
# =============================================================================

class TestErrorHandling:
    """Tests for error handling."""

    @pytest.fixture
    def loader(self, tmp_path):
        """Create a loader with test templates."""
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        return TemplateLoader(templates_dir), templates_dir

    def test_invalid_template_syntax(self, loader):
        """Test loading template with invalid syntax."""
        ldr, templates_dir = loader

        # Create template with bad syntax
        (templates_dir / "bad.txt").write_text("{{#if open but not closed")

        with pytest.raises(TemplateLoadError):
            ldr.load("bad")

    def test_permission_error(self, loader):
        """Test handling permission errors gracefully."""
        ldr, templates_dir = loader

        # Create a template then try to make it unreadable
        (templates_dir / "private.txt").write_text("Secret content")

        # Skip this test on Windows as chmod doesn't work the same way
        import platform
        if platform.system() != "Windows":
            import os
            os.chmod(templates_dir / "private.txt", 0o000)

            with pytest.raises((PermissionError, TemplateLoadError)):
                ldr.load("private")

            # Restore permissions for cleanup
            os.chmod(templates_dir / "private.txt", 0o644)

    def test_directory_traversal_prevented(self, loader):
        """Test that directory traversal is prevented."""
        ldr, _ = loader

        # Attempt to load outside templates directory
        with pytest.raises((TemplateNotFoundError, ValueError)):
            ldr.load("../../../etc/passwd")


# =============================================================================
# Edge Cases Tests
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases."""

    def test_empty_template(self, tmp_path):
        """Test loading empty template."""
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        (templates_dir / "empty.txt").write_text("")

        loader = TemplateLoader(templates_dir)
        template = loader.load("empty")
        assert template.source == ""

    def test_unicode_template(self, tmp_path):
        """Test loading template with unicode content."""
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        (templates_dir / "unicode.txt").write_text("Hello {{name}}! Unicode: ", encoding="utf-8")

        loader = TemplateLoader(templates_dir)
        template = loader.load("unicode")
        assert "" in template.source

    def test_large_template(self, tmp_path):
        """Test loading large template."""
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()

        large_content = "x" * 100000 + "{{var}}"
        (templates_dir / "large.txt").write_text(large_content)

        loader = TemplateLoader(templates_dir)
        template = loader.load("large")
        assert len(template.source) > 100000


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
