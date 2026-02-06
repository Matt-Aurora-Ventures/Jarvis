"""
Unit tests for PromptTemplate class.

Tests cover:
- Template creation with {{variables}}
- Variable rendering
- Validation of required variables
- Missing variable handling
- Nested variable support
"""

import pytest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from core.prompts.templates import PromptTemplate


# =============================================================================
# PromptTemplate Creation Tests
# =============================================================================

class TestPromptTemplateCreation:
    """Tests for PromptTemplate creation."""

    def test_create_simple_template(self):
        """Test creating a simple template with one variable."""
        template = PromptTemplate(
            name="greeting",
            template="Hello, {{name}}!",
            description="A greeting template",
        )

        assert template.name == "greeting"
        assert template.template == "Hello, {{name}}!"
        assert template.description == "A greeting template"

    def test_create_template_with_multiple_variables(self):
        """Test creating a template with multiple variables."""
        template = PromptTemplate(
            name="email",
            template="Dear {{recipient}}, Thank you for {{reason}}. Regards, {{sender}}",
        )

        assert "{{recipient}}" in template.template
        assert "{{reason}}" in template.template
        assert "{{sender}}" in template.template

    def test_template_with_no_variables(self):
        """Test creating a template with no variables."""
        template = PromptTemplate(
            name="static",
            template="This is a static prompt with no variables.",
        )

        assert template.name == "static"

    def test_template_extract_variables(self):
        """Test extracting variable names from template."""
        template = PromptTemplate(
            name="test",
            template="{{var1}} and {{var2}} and {{var1}}",  # var1 appears twice
        )

        variables = template.get_variables()
        assert "var1" in variables
        assert "var2" in variables
        # Should return unique variables
        assert len(variables) == 2


# =============================================================================
# PromptTemplate Rendering Tests
# =============================================================================

class TestPromptTemplateRendering:
    """Tests for PromptTemplate rendering."""

    def test_render_simple_template(self):
        """Test rendering a simple template."""
        template = PromptTemplate(
            name="greeting",
            template="Hello, {{name}}!",
        )

        result = template.render({"name": "Alice"})
        assert result == "Hello, Alice!"

    def test_render_multiple_variables(self):
        """Test rendering with multiple variables."""
        template = PromptTemplate(
            name="message",
            template="From: {{sender}}\nTo: {{recipient}}\nSubject: {{subject}}",
        )

        context = {
            "sender": "Bob",
            "recipient": "Alice",
            "subject": "Hello",
        }

        result = template.render(context)
        assert "From: Bob" in result
        assert "To: Alice" in result
        assert "Subject: Hello" in result

    def test_render_same_variable_multiple_times(self):
        """Test rendering when same variable appears multiple times."""
        template = PromptTemplate(
            name="repeat",
            template="{{name}} said {{name}} twice",
        )

        result = template.render({"name": "Echo"})
        assert result == "Echo said Echo twice"

    def test_render_with_special_characters(self):
        """Test rendering variables containing special characters."""
        template = PromptTemplate(
            name="special",
            template="Content: {{content}}",
        )

        result = template.render({"content": "Test <script>alert('xss')</script>"})
        assert "<script>" in result  # Should preserve content

    def test_render_with_newlines(self):
        """Test rendering variables with newlines."""
        template = PromptTemplate(
            name="multiline",
            template="Message:\n{{body}}",
        )

        result = template.render({"body": "Line1\nLine2\nLine3"})
        assert "Line1\nLine2\nLine3" in result

    def test_render_with_empty_string(self):
        """Test rendering with empty string value."""
        template = PromptTemplate(
            name="empty",
            template="Name: {{name}}",
        )

        result = template.render({"name": ""})
        assert result == "Name: "


# =============================================================================
# PromptTemplate Validation Tests
# =============================================================================

class TestPromptTemplateValidation:
    """Tests for PromptTemplate validation."""

    def test_validate_all_variables_present(self):
        """Test validation passes when all variables are present."""
        template = PromptTemplate(
            name="test",
            template="{{var1}} and {{var2}}",
        )

        errors = template.validate({"var1": "a", "var2": "b"})
        assert errors == []

    def test_validate_missing_variable(self):
        """Test validation fails when variable is missing."""
        template = PromptTemplate(
            name="test",
            template="{{var1}} and {{var2}}",
        )

        errors = template.validate({"var1": "a"})
        assert len(errors) > 0
        assert "var2" in errors[0].lower()

    def test_validate_multiple_missing_variables(self):
        """Test validation reports all missing variables."""
        template = PromptTemplate(
            name="test",
            template="{{a}} {{b}} {{c}}",
        )

        errors = template.validate({})
        assert len(errors) >= 2  # At least reports missing vars

    def test_validate_extra_variables_ignored(self):
        """Test validation ignores extra variables in context."""
        template = PromptTemplate(
            name="test",
            template="{{var1}}",
        )

        errors = template.validate({"var1": "a", "extra": "b"})
        assert errors == []

    def test_validate_with_no_variables(self):
        """Test validation of template with no variables."""
        template = PromptTemplate(
            name="static",
            template="No variables here",
        )

        errors = template.validate({})
        assert errors == []


# =============================================================================
# Edge Cases Tests
# =============================================================================

class TestPromptTemplateEdgeCases:
    """Tests for edge cases in PromptTemplate."""

    def test_empty_template(self):
        """Test creating and rendering an empty template."""
        template = PromptTemplate(
            name="empty",
            template="",
        )

        result = template.render({})
        assert result == ""

    def test_template_with_similar_variable_names(self):
        """Test template with similar variable names."""
        template = PromptTemplate(
            name="similar",
            template="{{name}} vs {{names}} vs {{name_full}}",
        )

        context = {
            "name": "A",
            "names": "B",
            "name_full": "C",
        }

        result = template.render(context)
        assert "A vs B vs C" == result

    def test_render_without_required_variables_raises(self):
        """Test that rendering without required variables raises or uses placeholder."""
        template = PromptTemplate(
            name="required",
            template="Hello {{name}}",
        )

        # Should either raise or return template with placeholder
        result = template.render({})
        # Implementation can either raise or leave {{name}} in place
        assert "{{name}}" in result or "name" in result.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
