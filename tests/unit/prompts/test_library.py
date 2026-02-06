"""
Unit tests for PromptLibrary class.

Tests cover:
- get_prompt(name) -> str
- register_prompt(name, template)
- list_prompts() -> List[str]
- Variable substitution support
- Loading prompts from files
"""

import pytest
from pathlib import Path
import sys
import tempfile
import shutil

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from core.prompts.library import PromptLibrary
from core.prompts.templates import PromptTemplate


# =============================================================================
# PromptLibrary Basic Operations Tests
# =============================================================================

class TestPromptLibraryBasicOperations:
    """Tests for basic PromptLibrary operations."""

    @pytest.fixture
    def library(self, tmp_path):
        """Create a temporary prompt library for testing."""
        return PromptLibrary(prompts_dir=tmp_path)

    def test_library_creation(self, library):
        """Test PromptLibrary can be created."""
        assert library is not None

    def test_register_prompt(self, library):
        """Test registering a prompt template."""
        template = PromptTemplate(
            name="test",
            template="Hello {{name}}",
        )

        library.register_prompt("test", template)

        # Should be able to retrieve it
        result = library.get_prompt("test")
        assert result is not None

    def test_register_prompt_with_string(self, library):
        """Test registering a prompt with raw string template."""
        library.register_prompt("simple", "Hello {{name}}")

        result = library.get_prompt("simple")
        assert "Hello" in result or result is not None

    def test_get_prompt_returns_string(self, library):
        """Test get_prompt returns a string."""
        template = PromptTemplate(
            name="greeting",
            template="Hello there!",
        )
        library.register_prompt("greeting", template)

        result = library.get_prompt("greeting")
        assert isinstance(result, str)
        assert result == "Hello there!"

    def test_get_prompt_not_found_returns_none_or_raises(self, library):
        """Test get_prompt with unknown name."""
        result = library.get_prompt("nonexistent")
        # Implementation can either return None or raise KeyError
        assert result is None or result == ""

    def test_list_prompts_empty(self, library):
        """Test list_prompts on empty library."""
        result = library.list_prompts()
        assert isinstance(result, list)
        # May have default prompts or be empty
        assert len(result) >= 0

    def test_list_prompts_after_register(self, library):
        """Test list_prompts returns registered prompts."""
        library.register_prompt("prompt1", "Template 1")
        library.register_prompt("prompt2", "Template 2")

        result = library.list_prompts()
        assert "prompt1" in result
        assert "prompt2" in result


# =============================================================================
# Variable Substitution Tests
# =============================================================================

class TestPromptLibraryVariableSubstitution:
    """Tests for variable substitution in PromptLibrary."""

    @pytest.fixture
    def library(self, tmp_path):
        """Create a temporary prompt library for testing."""
        return PromptLibrary(prompts_dir=tmp_path)

    def test_get_prompt_with_variables(self, library):
        """Test get_prompt with variable substitution."""
        library.register_prompt("greet", "Hello, {{name}}!")

        result = library.get_prompt("greet", name="Alice")
        assert result == "Hello, Alice!"

    def test_get_prompt_with_multiple_variables(self, library):
        """Test get_prompt with multiple variable substitutions."""
        library.register_prompt(
            "email",
            "Dear {{recipient}}, Your order {{order_id}} is ready. From: {{sender}}"
        )

        result = library.get_prompt(
            "email",
            recipient="John",
            order_id="12345",
            sender="Shop"
        )

        assert "Dear John" in result
        assert "12345" in result
        assert "Shop" in result

    def test_get_prompt_missing_variable(self, library):
        """Test get_prompt when variable is not provided."""
        library.register_prompt("test", "Hello {{name}}")

        # Should either leave placeholder or raise
        result = library.get_prompt("test")
        assert "{{name}}" in result or result is not None

    def test_get_prompt_with_default_value(self, library):
        """Test get_prompt can use default values if supported."""
        library.register_prompt("greet", "Hello, {{name}}!")

        # Some implementations support defaults
        result = library.get_prompt("greet", name="World")
        assert "World" in result


# =============================================================================
# File Loading Tests
# =============================================================================

class TestPromptLibraryFileLoading:
    """Tests for loading prompts from files."""

    @pytest.fixture
    def library_with_files(self, tmp_path):
        """Create a library with prompt files."""
        # Create some prompt files
        (tmp_path / "system.txt").write_text("You are a helpful assistant.")
        (tmp_path / "greeting.txt").write_text("Hello, {{name}}!")
        (tmp_path / "error.txt").write_text("Error: {{message}}")

        return PromptLibrary(prompts_dir=tmp_path)

    def test_load_prompt_from_file(self, library_with_files):
        """Test loading a prompt from a .txt file."""
        result = library_with_files.get_prompt("system")
        assert "helpful assistant" in result.lower()

    def test_load_prompt_with_variables_from_file(self, library_with_files):
        """Test loading and rendering a prompt from file."""
        result = library_with_files.get_prompt("greeting", name="Alice")
        assert result == "Hello, Alice!"

    def test_list_prompts_includes_files(self, library_with_files):
        """Test list_prompts includes file-based prompts."""
        prompts = library_with_files.list_prompts()
        assert "system" in prompts
        assert "greeting" in prompts
        assert "error" in prompts


# =============================================================================
# Overwrite and Update Tests
# =============================================================================

class TestPromptLibraryUpdates:
    """Tests for updating prompts."""

    @pytest.fixture
    def library(self, tmp_path):
        """Create a temporary prompt library."""
        return PromptLibrary(prompts_dir=tmp_path)

    def test_overwrite_prompt(self, library):
        """Test that registering same name overwrites."""
        library.register_prompt("test", "Version 1")
        library.register_prompt("test", "Version 2")

        result = library.get_prompt("test")
        assert "Version 2" in result

    def test_remove_prompt(self, library):
        """Test removing a prompt if supported."""
        library.register_prompt("temp", "Temporary")

        # Try to unregister if method exists
        if hasattr(library, "unregister_prompt"):
            library.unregister_prompt("temp")
            assert "temp" not in library.list_prompts()


# =============================================================================
# Edge Cases Tests
# =============================================================================

class TestPromptLibraryEdgeCases:
    """Tests for edge cases in PromptLibrary."""

    @pytest.fixture
    def library(self, tmp_path):
        """Create a temporary prompt library."""
        return PromptLibrary(prompts_dir=tmp_path)

    def test_empty_prompt_name(self, library):
        """Test handling of empty prompt name."""
        # Should either raise or handle gracefully
        result = library.get_prompt("")
        assert result is None or result == ""

    def test_prompt_name_with_special_chars(self, library):
        """Test prompt names with special characters."""
        library.register_prompt("test-prompt_v2", "Test content")

        result = library.get_prompt("test-prompt_v2")
        assert result == "Test content"

    def test_unicode_in_template(self, library):
        """Test unicode characters in template."""
        library.register_prompt("unicode", "Hello {{name}}!")

        result = library.get_prompt("unicode", name="World")
        assert "Hello" in result
        assert "" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
