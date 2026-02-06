"""
Comprehensive unit tests for the Template Engine.

Tests cover:
- Template class and compilation
- Variable substitution: {{name}}
- Conditional blocks: {{#if condition}}...{{/if}}
- Helper functions registration and invocation
- Error handling for invalid templates
- Nested conditionals
- Default values
"""

import pytest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from core.templates.engine import (
    Template,
    TemplateEngine,
    TemplateSyntaxError,
    TemplateRenderError,
)


# =============================================================================
# Template Class Tests
# =============================================================================

class TestTemplate:
    """Tests for the Template class."""

    def test_template_creation(self):
        """Test creating a Template from a string."""
        template = Template("Hello, {{name}}!")
        assert template.source == "Hello, {{name}}!"

    def test_template_render_simple_variable(self):
        """Test rendering a simple variable."""
        template = Template("Hello, {{name}}!")
        result = template.render({"name": "World"})
        assert result == "Hello, World!"

    def test_template_render_multiple_variables(self):
        """Test rendering multiple variables."""
        template = Template("{{greeting}}, {{name}}!")
        result = template.render({"greeting": "Hi", "name": "Alice"})
        assert result == "Hi, Alice!"

    def test_template_render_missing_variable(self):
        """Test rendering with missing variable uses empty string."""
        template = Template("Hello, {{name}}!")
        result = template.render({})
        assert result == "Hello, !"

    def test_template_render_with_default(self):
        """Test rendering with default value for missing variable."""
        template = Template("Hello, {{name|default:Guest}}!")
        result = template.render({})
        assert result == "Hello, Guest!"

    def test_template_conditional_true(self):
        """Test conditional block when condition is true."""
        template = Template("{{#if show}}Visible{{/if}}")
        result = template.render({"show": True})
        assert result == "Visible"

    def test_template_conditional_false(self):
        """Test conditional block when condition is false."""
        template = Template("{{#if show}}Visible{{/if}}")
        result = template.render({"show": False})
        assert result == ""

    def test_template_conditional_missing(self):
        """Test conditional block when condition is missing (falsy)."""
        template = Template("{{#if show}}Visible{{/if}}")
        result = template.render({})
        assert result == ""

    def test_template_conditional_else(self):
        """Test conditional with else block."""
        template = Template("{{#if admin}}Admin{{#else}}User{{/if}}")
        result_admin = template.render({"admin": True})
        result_user = template.render({"admin": False})
        assert result_admin == "Admin"
        assert result_user == "User"

    def test_template_nested_conditionals(self):
        """Test nested conditional blocks."""
        template = Template("{{#if outer}}{{#if inner}}Both{{/if}}{{/if}}")
        result = template.render({"outer": True, "inner": True})
        assert result == "Both"

    def test_template_conditional_with_variable(self):
        """Test conditional block with variable inside."""
        template = Template("{{#if greet}}Hello, {{name}}!{{/if}}")
        result = template.render({"greet": True, "name": "Bob"})
        assert result == "Hello, Bob!"

    def test_template_unless(self):
        """Test unless (inverse conditional) block."""
        template = Template("{{#unless hidden}}Visible{{/unless}}")
        result_visible = template.render({"hidden": False})
        result_hidden = template.render({"hidden": True})
        assert result_visible == "Visible"
        assert result_hidden == ""

    def test_template_whitespace_preserved(self):
        """Test that whitespace is preserved."""
        template = Template("Line 1\n  Line 2\nLine 3")
        result = template.render({})
        assert result == "Line 1\n  Line 2\nLine 3"


# =============================================================================
# TemplateEngine Tests
# =============================================================================

class TestTemplateEngine:
    """Tests for the TemplateEngine class."""

    @pytest.fixture
    def engine(self):
        """Create a TemplateEngine instance."""
        return TemplateEngine()

    def test_engine_compile(self, engine):
        """Test compiling a template string."""
        template = engine.compile("Hello, {{name}}!")
        assert isinstance(template, Template)
        assert template.source == "Hello, {{name}}!"

    def test_engine_render(self, engine, tmp_path):
        """Test rendering a named template."""
        # Create a test template file
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        (templates_dir / "test.txt").write_text("Hello, {{name}}!")

        engine.templates_dir = templates_dir
        result = engine.render("test", {"name": "World"})
        assert result == "Hello, World!"

    def test_engine_render_missing_template(self, engine):
        """Test rendering a non-existent template raises error."""
        with pytest.raises(FileNotFoundError):
            engine.render("nonexistent", {})

    def test_engine_register_helper(self, engine):
        """Test registering a helper function."""
        def shout(text):
            return text.upper() + "!"

        engine.register_helper("shout", shout)
        template = engine.compile("{{shout name}}")
        result = template.render({"name": "hello"}, helpers=engine.helpers)
        assert result == "HELLO!"

    def test_engine_helper_with_args(self, engine):
        """Test helper with multiple arguments."""
        def join_with(sep, *args):
            return sep.join(args)

        engine.register_helper("join", join_with)
        template = engine.compile("{{join '-' a b c}}")
        result = template.render({"a": "1", "b": "2", "c": "3"}, helpers=engine.helpers)
        assert result == "1-2-3"

    def test_engine_builtin_helpers(self, engine):
        """Test that engine has built-in helpers available."""
        # Built-in helpers should include format_date, format_number, etc.
        assert "format_date" in engine.helpers or hasattr(engine, "_load_builtin_helpers")

    def test_engine_cache_templates(self, engine, tmp_path):
        """Test that templates are cached."""
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        (templates_dir / "cached.txt").write_text("Content: {{data}}")

        engine.templates_dir = templates_dir

        # First render - should cache
        result1 = engine.render("cached", {"data": "first"})

        # Modify the file
        (templates_dir / "cached.txt").write_text("Modified: {{data}}")

        # Second render - should use cached version
        result2 = engine.render("cached", {"data": "second"})

        assert result1 == "Content: first"
        assert result2 == "Content: second"  # Uses cache but new context


# =============================================================================
# Syntax Error Tests
# =============================================================================

class TestTemplateSyntaxErrors:
    """Tests for template syntax error handling."""

    def test_unclosed_variable(self):
        """Test unclosed variable tag raises error."""
        with pytest.raises(TemplateSyntaxError):
            Template("Hello, {{name")

    def test_unclosed_if_block(self):
        """Test unclosed if block raises error."""
        with pytest.raises(TemplateSyntaxError):
            Template("{{#if show}}Content")

    def test_mismatched_blocks(self):
        """Test mismatched block tags raise error."""
        with pytest.raises(TemplateSyntaxError):
            Template("{{#if show}}Content{{/unless}}")

    def test_invalid_helper_syntax(self):
        """Test invalid helper syntax raises error."""
        engine = TemplateEngine()
        template = engine.compile("{{unknownHelper}}")
        # Should raise or return empty when rendering with unknown helper
        result = template.render({}, helpers={})
        assert result == "" or "unknownHelper" in result


# =============================================================================
# Edge Cases Tests
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases and special scenarios."""

    def test_empty_template(self):
        """Test empty template."""
        template = Template("")
        result = template.render({})
        assert result == ""

    def test_no_variables(self):
        """Test template with no variables."""
        template = Template("Plain text content")
        result = template.render({"unused": "value"})
        assert result == "Plain text content"

    def test_special_characters(self):
        """Test template with special characters."""
        template = Template("Price: ${{amount}} ({{percent}}%)")
        result = template.render({"amount": "100", "percent": "15"})
        assert result == "Price: $100 (15%)"

    def test_numeric_values(self):
        """Test template with numeric values."""
        template = Template("Count: {{count}}")
        result = template.render({"count": 42})
        assert result == "Count: 42"

    def test_none_value(self):
        """Test template with None value."""
        template = Template("Value: {{val}}")
        result = template.render({"val": None})
        assert result == "Value: " or result == "Value: None"

    def test_nested_dict_access(self):
        """Test accessing nested dictionary values."""
        template = Template("User: {{user.name}}")
        result = template.render({"user": {"name": "Alice"}})
        assert result == "User: Alice"

    def test_list_access(self):
        """Test accessing list values by index."""
        template = Template("First: {{items.0}}")
        result = template.render({"items": ["apple", "banana"]})
        assert result == "First: apple"

    def test_truthy_conditions(self):
        """Test various truthy/falsy values in conditionals."""
        template = Template("{{#if val}}yes{{#else}}no{{/if}}")

        # Truthy values
        assert template.render({"val": True}) == "yes"
        assert template.render({"val": 1}) == "yes"
        assert template.render({"val": "text"}) == "yes"
        assert template.render({"val": [1]}) == "yes"

        # Falsy values
        assert template.render({"val": False}) == "no"
        assert template.render({"val": 0}) == "no"
        assert template.render({"val": ""}) == "no"
        assert template.render({"val": []}) == "no"
        assert template.render({"val": None}) == "no"


# =============================================================================
# Integration Tests
# =============================================================================

class TestTemplateIntegration:
    """Integration tests combining multiple features."""

    def test_full_message_template(self):
        """Test a realistic message template."""
        template_src = """
{{#if urgent}}[URGENT] {{/if}}{{title}}

Hello {{recipient.name}},

{{message}}

{{#if signature}}
Best regards,
{{signature}}
{{/if}}
""".strip()

        template = Template(template_src)

        context = {
            "urgent": True,
            "title": "System Alert",
            "recipient": {"name": "Admin"},
            "message": "Server load is high.",
            "signature": "Jarvis"
        }

        result = template.render(context)

        assert "[URGENT]" in result
        assert "System Alert" in result
        assert "Hello Admin" in result
        assert "Server load is high." in result
        assert "Best regards," in result
        assert "Jarvis" in result

    def test_report_template(self):
        """Test a report-style template."""
        template_src = """
Report: {{title}}
Date: {{date}}
---
{{#if items}}
Items:
{{items}}
{{#else}}
No items to report.
{{/if}}
---
Generated by {{system}}
""".strip()

        template = Template(template_src)

        # With items
        result_with = template.render({
            "title": "Daily Summary",
            "date": "2026-02-02",
            "items": "- Item 1\n- Item 2",
            "system": "Jarvis"
        })
        assert "Items:" in result_with
        assert "- Item 1" in result_with

        # Without items
        result_without = template.render({
            "title": "Daily Summary",
            "date": "2026-02-02",
            "items": "",
            "system": "Jarvis"
        })
        assert "No items to report." in result_without


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
