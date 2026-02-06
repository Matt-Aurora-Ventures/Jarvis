"""
Tests for ClawdBots Response Templates Module

TDD tests for bots/shared/response_templates.py
Tests written BEFORE implementation per TDD workflow.
"""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


class TestResponseTemplates:
    """Test suite for response_templates module."""

    @pytest.fixture
    def temp_templates_file(self, tmp_path):
        """Create a temporary templates file for testing."""
        templates_file = tmp_path / "templates.json"
        templates_file.write_text("{}")
        return str(templates_file)

    @pytest.fixture
    def sample_templates_file(self, tmp_path):
        """Create a temporary templates file with sample data."""
        templates_file = tmp_path / "templates.json"
        sample_data = {
            "version": "1.0",
            "global_templates": {
                "greeting": {
                    "template": "Hey {user_name}! I'm {bot_name}. {intro}",
                    "category": "greetings",
                    "defaults": {
                        "user_name": "friend",
                        "bot_name": "Bot",
                        "intro": "How can I help you?"
                    }
                },
                "error": {
                    "template": "Oops! Something went wrong: {error}. Let me try again.",
                    "category": "errors",
                    "defaults": {
                        "error": "Unknown error"
                    }
                },
                "status": {
                    "template": "Status: {status}\nUptime: {uptime}\nMessages: {msg_count}",
                    "category": "status",
                    "defaults": {
                        "status": "Unknown",
                        "uptime": "N/A",
                        "msg_count": "0"
                    }
                },
                "help_general": {
                    "template": "Here are the available commands:\n{command_list}",
                    "category": "help",
                    "defaults": {
                        "command_list": "No commands available"
                    }
                },
                "confirm_action": {
                    "template": "Action '{action}' completed successfully!",
                    "category": "confirmations",
                    "defaults": {
                        "action": "operation"
                    }
                }
            },
            "bot_templates": {
                "jarvis": {
                    "greeting": {
                        "template": "At your service, {user_name}. I am JARVIS. {intro}",
                        "category": "greetings",
                        "defaults": {
                            "user_name": "sir",
                            "intro": "How may I assist you today?"
                        }
                    }
                },
                "friday": {
                    "greeting": {
                        "template": "Hello {user_name}! Friday here, your email AI assistant. {intro}",
                        "category": "greetings",
                        "defaults": {
                            "user_name": "there",
                            "intro": "Ready to help with your emails."
                        }
                    }
                },
                "matt": {
                    "greeting": {
                        "template": "Hey {user_name}, PR Matt here. {intro}",
                        "category": "greetings",
                        "defaults": {
                            "user_name": "friend",
                            "intro": "Let's make your communications shine."
                        }
                    }
                }
            }
        }
        templates_file.write_text(json.dumps(sample_data, indent=2))
        return str(templates_file)

    # -------------------------
    # Test get_template()
    # -------------------------

    def test_get_template_global(self, sample_templates_file):
        """Test getting a global template without bot override."""
        from bots.shared.response_templates import ResponseTemplates

        rt = ResponseTemplates(templates_file=sample_templates_file)
        template = rt.get_template("greeting")

        assert template == "Hey {user_name}! I'm {bot_name}. {intro}"

    def test_get_template_bot_override(self, sample_templates_file):
        """Test getting a bot-specific template override."""
        from bots.shared.response_templates import ResponseTemplates

        rt = ResponseTemplates(templates_file=sample_templates_file)
        template = rt.get_template("greeting", bot_name="jarvis")

        assert template == "At your service, {user_name}. I am JARVIS. {intro}"

    def test_get_template_fallback_to_global(self, sample_templates_file):
        """Test that bot templates fall back to global if not overridden."""
        from bots.shared.response_templates import ResponseTemplates

        rt = ResponseTemplates(templates_file=sample_templates_file)
        # "error" template is not overridden for jarvis, should get global
        template = rt.get_template("error", bot_name="jarvis")

        assert template == "Oops! Something went wrong: {error}. Let me try again."

    def test_get_template_not_found(self, sample_templates_file):
        """Test getting a non-existent template returns None."""
        from bots.shared.response_templates import ResponseTemplates

        rt = ResponseTemplates(templates_file=sample_templates_file)
        template = rt.get_template("nonexistent")

        assert template is None

    def test_get_template_invalid_bot(self, sample_templates_file):
        """Test getting template with invalid bot falls back to global."""
        from bots.shared.response_templates import ResponseTemplates

        rt = ResponseTemplates(templates_file=sample_templates_file)
        template = rt.get_template("greeting", bot_name="nonexistent_bot")

        assert template == "Hey {user_name}! I'm {bot_name}. {intro}"

    # -------------------------
    # Test render_template()
    # -------------------------

    def test_render_template_with_vars(self, sample_templates_file):
        """Test rendering a template with provided variables."""
        from bots.shared.response_templates import ResponseTemplates

        rt = ResponseTemplates(templates_file=sample_templates_file)
        rendered = rt.render_template(
            "greeting",
            user_name="Alice",
            bot_name="TestBot",
            intro="Welcome!"
        )

        assert rendered == "Hey Alice! I'm TestBot. Welcome!"

    def test_render_template_with_defaults(self, sample_templates_file):
        """Test rendering uses default values when vars not provided."""
        from bots.shared.response_templates import ResponseTemplates

        rt = ResponseTemplates(templates_file=sample_templates_file)
        rendered = rt.render_template("greeting")

        assert rendered == "Hey friend! I'm Bot. How can I help you?"

    def test_render_template_partial_vars(self, sample_templates_file):
        """Test rendering with partial variables uses defaults for missing."""
        from bots.shared.response_templates import ResponseTemplates

        rt = ResponseTemplates(templates_file=sample_templates_file)
        rendered = rt.render_template("greeting", user_name="Bob")

        assert rendered == "Hey Bob! I'm Bot. How can I help you?"

    def test_render_template_bot_specific(self, sample_templates_file):
        """Test rendering a bot-specific template."""
        from bots.shared.response_templates import ResponseTemplates

        rt = ResponseTemplates(templates_file=sample_templates_file)
        rendered = rt.render_template("greeting", bot_name="jarvis")

        assert rendered == "At your service, sir. I am JARVIS. How may I assist you today?"

    def test_render_template_bot_specific_with_vars(self, sample_templates_file):
        """Test rendering a bot-specific template with custom vars."""
        from bots.shared.response_templates import ResponseTemplates

        rt = ResponseTemplates(templates_file=sample_templates_file)
        rendered = rt.render_template(
            "greeting",
            bot_name="friday",
            user_name="Carol",
            intro="Let's get started!"
        )

        assert rendered == "Hello Carol! Friday here, your email AI assistant. Let's get started!"

    def test_render_template_not_found(self, sample_templates_file):
        """Test rendering a non-existent template returns error message."""
        from bots.shared.response_templates import ResponseTemplates

        rt = ResponseTemplates(templates_file=sample_templates_file)
        rendered = rt.render_template("nonexistent")

        assert "Template 'nonexistent' not found" in rendered

    def test_render_template_extra_vars_ignored(self, sample_templates_file):
        """Test that extra variables not in template are ignored."""
        from bots.shared.response_templates import ResponseTemplates

        rt = ResponseTemplates(templates_file=sample_templates_file)
        rendered = rt.render_template(
            "error",
            error="Connection failed",
            extra_var="should be ignored"
        )

        assert rendered == "Oops! Something went wrong: Connection failed. Let me try again."

    # -------------------------
    # Test list_templates()
    # -------------------------

    def test_list_templates_all(self, sample_templates_file):
        """Test listing all templates."""
        from bots.shared.response_templates import ResponseTemplates

        rt = ResponseTemplates(templates_file=sample_templates_file)
        templates = rt.list_templates()

        assert "greeting" in templates
        assert "error" in templates
        assert "status" in templates
        assert "help_general" in templates
        assert "confirm_action" in templates
        assert len(templates) == 5

    def test_list_templates_by_category(self, sample_templates_file):
        """Test listing templates by category."""
        from bots.shared.response_templates import ResponseTemplates

        rt = ResponseTemplates(templates_file=sample_templates_file)

        greetings = rt.list_templates(category="greetings")
        assert greetings == ["greeting"]

        errors = rt.list_templates(category="errors")
        assert errors == ["error"]

        status = rt.list_templates(category="status")
        assert status == ["status"]

    def test_list_templates_empty_category(self, sample_templates_file):
        """Test listing templates for non-existent category returns empty."""
        from bots.shared.response_templates import ResponseTemplates

        rt = ResponseTemplates(templates_file=sample_templates_file)
        templates = rt.list_templates(category="nonexistent")

        assert templates == []

    def test_list_templates_returns_info(self, sample_templates_file):
        """Test list_templates returns template names."""
        from bots.shared.response_templates import ResponseTemplates

        rt = ResponseTemplates(templates_file=sample_templates_file)
        templates = rt.list_templates()

        # Verify it returns a list of strings
        assert all(isinstance(t, str) for t in templates)

    # -------------------------
    # Test add_template()
    # -------------------------

    def test_add_template_global(self, temp_templates_file):
        """Test adding a new global template."""
        from bots.shared.response_templates import ResponseTemplates

        rt = ResponseTemplates(templates_file=temp_templates_file)
        rt.add_template(
            name="farewell",
            template="Goodbye {user_name}! Have a great {time_of_day}!",
            category="greetings",
            defaults={"user_name": "friend", "time_of_day": "day"}
        )

        # Verify template was added
        template = rt.get_template("farewell")
        assert template == "Goodbye {user_name}! Have a great {time_of_day}!"

        # Verify template renders correctly
        rendered = rt.render_template("farewell", user_name="Alice", time_of_day="evening")
        assert rendered == "Goodbye Alice! Have a great evening!"

    def test_add_template_bot_specific(self, temp_templates_file):
        """Test adding a bot-specific template."""
        from bots.shared.response_templates import ResponseTemplates

        rt = ResponseTemplates(templates_file=temp_templates_file)
        rt.add_template(
            name="intro",
            template="I am JARVIS, your AI assistant.",
            category="greetings",
            bot_name="jarvis"
        )

        template = rt.get_template("intro", bot_name="jarvis")
        assert template == "I am JARVIS, your AI assistant."

    def test_add_template_overwrites_existing(self, sample_templates_file):
        """Test that adding a template with existing name overwrites it."""
        from bots.shared.response_templates import ResponseTemplates

        rt = ResponseTemplates(templates_file=sample_templates_file)

        # Overwrite the error template
        rt.add_template(
            name="error",
            template="Error occurred: {error}. Please try again later.",
            category="errors"
        )

        template = rt.get_template("error")
        assert template == "Error occurred: {error}. Please try again later."

    def test_add_template_persists_to_file(self, temp_templates_file):
        """Test that added templates are persisted to file."""
        from bots.shared.response_templates import ResponseTemplates

        rt = ResponseTemplates(templates_file=temp_templates_file)
        rt.add_template(
            name="test_persist",
            template="This should persist: {value}",
            category="testing"
        )

        # Create new instance and check template exists
        rt2 = ResponseTemplates(templates_file=temp_templates_file)
        template = rt2.get_template("test_persist")
        assert template == "This should persist: {value}"

    def test_add_template_with_defaults(self, temp_templates_file):
        """Test adding template with default values."""
        from bots.shared.response_templates import ResponseTemplates

        rt = ResponseTemplates(templates_file=temp_templates_file)
        rt.add_template(
            name="welcome",
            template="Welcome to {system}, {user}!",
            category="greetings",
            defaults={"system": "ClawdBots", "user": "User"}
        )

        # Render without vars should use defaults
        rendered = rt.render_template("welcome")
        assert rendered == "Welcome to ClawdBots, User!"

    # -------------------------
    # Test get_defaults()
    # -------------------------

    def test_get_defaults_global(self, sample_templates_file):
        """Test getting default values for a global template."""
        from bots.shared.response_templates import ResponseTemplates

        rt = ResponseTemplates(templates_file=sample_templates_file)
        defaults = rt.get_defaults("greeting")

        assert defaults == {
            "user_name": "friend",
            "bot_name": "Bot",
            "intro": "How can I help you?"
        }

    def test_get_defaults_bot_specific(self, sample_templates_file):
        """Test getting defaults for bot-specific template."""
        from bots.shared.response_templates import ResponseTemplates

        rt = ResponseTemplates(templates_file=sample_templates_file)
        defaults = rt.get_defaults("greeting", bot_name="jarvis")

        assert defaults == {
            "user_name": "sir",
            "intro": "How may I assist you today?"
        }

    def test_get_defaults_not_found(self, sample_templates_file):
        """Test getting defaults for non-existent template returns empty dict."""
        from bots.shared.response_templates import ResponseTemplates

        rt = ResponseTemplates(templates_file=sample_templates_file)
        defaults = rt.get_defaults("nonexistent")

        assert defaults == {}

    # -------------------------
    # Test file handling
    # -------------------------

    def test_creates_file_if_not_exists(self, tmp_path):
        """Test that templates file is created if it doesn't exist."""
        from bots.shared.response_templates import ResponseTemplates

        new_file = str(tmp_path / "new_templates.json")
        assert not os.path.exists(new_file)

        rt = ResponseTemplates(templates_file=new_file)

        assert os.path.exists(new_file)

    def test_creates_parent_directories(self, tmp_path):
        """Test that parent directories are created."""
        from bots.shared.response_templates import ResponseTemplates

        new_file = str(tmp_path / "subdir" / "deep" / "templates.json")
        assert not os.path.exists(os.path.dirname(new_file))

        rt = ResponseTemplates(templates_file=new_file)

        assert os.path.exists(new_file)

    def test_handles_corrupted_file(self, tmp_path):
        """Test handling of corrupted JSON file."""
        from bots.shared.response_templates import ResponseTemplates

        corrupted_file = tmp_path / "corrupted.json"
        corrupted_file.write_text("{ invalid json }")

        # Should not raise, should reset to default state
        rt = ResponseTemplates(templates_file=str(corrupted_file))

        # Should still be able to add templates
        rt.add_template("test", "test {val}", "testing")
        template = rt.get_template("test")
        assert template == "test {val}"

    # -------------------------
    # Test list_categories()
    # -------------------------

    def test_list_categories(self, sample_templates_file):
        """Test listing all available categories."""
        from bots.shared.response_templates import ResponseTemplates

        rt = ResponseTemplates(templates_file=sample_templates_file)
        categories = rt.list_categories()

        assert "greetings" in categories
        assert "errors" in categories
        assert "status" in categories
        assert "help" in categories
        assert "confirmations" in categories

    # -------------------------
    # Test convenience functions
    # -------------------------

    def test_module_level_get_template(self, sample_templates_file):
        """Test module-level get_template function."""
        from bots.shared import response_templates

        with patch.object(response_templates, '_default_templates_file', sample_templates_file):
            # Reset the global instance
            response_templates._instance = None
            template = response_templates.get_template("greeting")
            assert "{user_name}" in template

    def test_module_level_render_template(self, sample_templates_file):
        """Test module-level render_template function."""
        from bots.shared import response_templates

        with patch.object(response_templates, '_default_templates_file', sample_templates_file):
            response_templates._instance = None
            rendered = response_templates.render_template("error", error="Test error")
            assert "Test error" in rendered

    def test_module_level_list_templates(self, sample_templates_file):
        """Test module-level list_templates function."""
        from bots.shared import response_templates

        with patch.object(response_templates, '_default_templates_file', sample_templates_file):
            response_templates._instance = None
            templates = response_templates.list_templates()
            assert len(templates) > 0

    def test_module_level_add_template(self, temp_templates_file):
        """Test module-level add_template function."""
        from bots.shared import response_templates

        with patch.object(response_templates, '_default_templates_file', temp_templates_file):
            response_templates._instance = None
            response_templates.add_template(
                "test_module",
                "Test: {value}",
                "testing"
            )
            template = response_templates.get_template("test_module")
            assert template == "Test: {value}"


class TestResponseTemplatesEdgeCases:
    """Test edge cases and error handling."""

    @pytest.fixture
    def temp_templates_file(self, tmp_path):
        """Create a temporary templates file."""
        templates_file = tmp_path / "templates.json"
        templates_file.write_text("{}")
        return str(templates_file)

    def test_template_with_braces_in_content(self, temp_templates_file):
        """Test template with literal braces (escaped)."""
        from bots.shared.response_templates import ResponseTemplates

        rt = ResponseTemplates(templates_file=temp_templates_file)
        rt.add_template(
            name="json_example",
            template='JSON: {{"key": "{value}"}}',
            category="examples"
        )

        rendered = rt.render_template("json_example", value="test")
        assert rendered == 'JSON: {"key": "test"}'

    def test_template_with_missing_var_placeholder(self, temp_templates_file):
        """Test rendering when template has placeholders not in defaults."""
        from bots.shared.response_templates import ResponseTemplates

        rt = ResponseTemplates(templates_file=temp_templates_file)
        rt.add_template(
            name="incomplete",
            template="Hello {name}, your code is {code}",
            category="testing",
            defaults={"name": "User"}  # No default for 'code'
        )

        # Should handle gracefully - either keep placeholder or use empty
        rendered = rt.render_template("incomplete")
        # The template should render with default name and keep {code} or use empty
        assert "User" in rendered

    def test_empty_template(self, temp_templates_file):
        """Test adding and rendering empty template."""
        from bots.shared.response_templates import ResponseTemplates

        rt = ResponseTemplates(templates_file=temp_templates_file)
        rt.add_template(
            name="empty",
            template="",
            category="testing"
        )

        rendered = rt.render_template("empty")
        assert rendered == ""

    def test_template_with_special_characters(self, temp_templates_file):
        """Test template with special characters."""
        from bots.shared.response_templates import ResponseTemplates

        rt = ResponseTemplates(templates_file=temp_templates_file)
        rt.add_template(
            name="special",
            template="Status: {status}\n\tIndented\n---\nEmoji: *",
            category="testing",
            defaults={"status": "OK"}
        )

        rendered = rt.render_template("special")
        assert "Status: OK" in rendered
        assert "\tIndented" in rendered

    def test_concurrent_access_safety(self, temp_templates_file):
        """Test that concurrent access doesn't corrupt data."""
        from bots.shared.response_templates import ResponseTemplates

        rt1 = ResponseTemplates(templates_file=temp_templates_file)
        rt2 = ResponseTemplates(templates_file=temp_templates_file)

        # Both add templates
        rt1.add_template("from_rt1", "Template 1", "testing")
        rt2.add_template("from_rt2", "Template 2", "testing")

        # Both should see both templates after reload
        rt3 = ResponseTemplates(templates_file=temp_templates_file)
        templates = rt3.list_templates()
        assert "from_rt1" in templates
        assert "from_rt2" in templates

    def test_unicode_in_templates(self, temp_templates_file):
        """Test templates with unicode characters."""
        from bots.shared.response_templates import ResponseTemplates

        rt = ResponseTemplates(templates_file=temp_templates_file)
        rt.add_template(
            name="unicode",
            template="Hello {name}! Status: {status}",
            category="testing",
            defaults={"name": "User", "status": "OK"}
        )

        rendered = rt.render_template("unicode", status="Great!")
        assert "Great!" in rendered

    def test_very_long_template(self, temp_templates_file):
        """Test handling of very long templates."""
        from bots.shared.response_templates import ResponseTemplates

        rt = ResponseTemplates(templates_file=temp_templates_file)
        long_template = "Line {num}\n" * 1000

        rt.add_template(
            name="long",
            template=long_template,
            category="testing",
            defaults={"num": "X"}
        )

        rendered = rt.render_template("long", num="1")
        assert rendered.count("Line 1") == 1000
