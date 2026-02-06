"""
Unit tests for Personality Data Model.

Tests:
- Personality dataclass creation
- Field validation
- load_files() method for loading SOUL/IDENTITY markdown
- Serialization (to_dict, from_dict)
"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock


class TestPersonalityModel:
    """Test the Personality dataclass."""

    def test_personality_creation_minimal(self):
        """Test creating a Personality with minimal required fields."""
        from core.personality.model import Personality

        p = Personality(
            name="TestBot",
            role="Test assistant",
            model="claude-3-opus",
        )

        assert p.name == "TestBot"
        assert p.role == "Test assistant"
        assert p.model == "claude-3-opus"

    def test_personality_creation_full(self):
        """Test creating a Personality with all fields."""
        from core.personality.model import Personality

        p = Personality(
            name="ClawdJarvis",
            role="System orchestrator and AI assistant",
            model="claude-3-opus",
            soul_path="bots/clawdjarvis/CLAWDJARVIS_SOUL.md",
            identity_path="bots/clawdjarvis/CLAWDJARVIS_IDENTITY.md",
            bootstrap_path="bots/clawdjarvis/CLAWDJARVIS_BOOTSTRAP.md",
            tone="professional but friendly",
            style="concise and technical",
            capabilities=["trading", "system control", "automation"],
        )

        assert p.name == "ClawdJarvis"
        assert p.soul_path == "bots/clawdjarvis/CLAWDJARVIS_SOUL.md"
        assert "trading" in p.capabilities

    def test_personality_default_values(self):
        """Test that optional fields have sensible defaults."""
        from core.personality.model import Personality

        p = Personality(
            name="TestBot",
            role="Test",
            model="claude-3-opus",
        )

        assert p.soul_path is None
        assert p.identity_path is None
        assert p.bootstrap_path is None
        assert p.tone == ""
        assert p.style == ""
        assert p.capabilities == []

    def test_personality_to_dict(self):
        """Test converting Personality to dictionary."""
        from core.personality.model import Personality

        p = Personality(
            name="TestBot",
            role="Test assistant",
            model="claude-3-opus",
            tone="friendly",
            capabilities=["chat", "help"],
        )

        data = p.to_dict()

        assert data["name"] == "TestBot"
        assert data["role"] == "Test assistant"
        assert data["model"] == "claude-3-opus"
        assert data["tone"] == "friendly"
        assert data["capabilities"] == ["chat", "help"]

    def test_personality_from_dict(self):
        """Test creating Personality from dictionary."""
        from core.personality.model import Personality

        data = {
            "name": "FromDict",
            "role": "Created from dict",
            "model": "claude-3-sonnet",
            "soul_path": "path/to/soul.md",
            "tone": "casual",
            "capabilities": ["test"],
        }

        p = Personality.from_dict(data)

        assert p.name == "FromDict"
        assert p.role == "Created from dict"
        assert p.soul_path == "path/to/soul.md"

    def test_personality_from_dict_partial(self):
        """Test creating Personality from partial dictionary."""
        from core.personality.model import Personality

        data = {
            "name": "Minimal",
            "role": "Minimal bot",
            "model": "gpt-4",
        }

        p = Personality.from_dict(data)

        assert p.name == "Minimal"
        assert p.soul_path is None
        assert p.capabilities == []


class TestPersonalityLoadFiles:
    """Test the load_files() method."""

    @pytest.fixture
    def temp_personality_files(self):
        """Create temporary SOUL and IDENTITY files."""
        import tempfile
        import os

        temp_dir = tempfile.mkdtemp()
        soul_path = Path(temp_dir) / "SOUL.md"
        identity_path = Path(temp_dir) / "IDENTITY.md"
        bootstrap_path = Path(temp_dir) / "BOOTSTRAP.md"

        soul_path.write_text("# Soul\n\nI am a test soul.")
        identity_path.write_text("# Identity\n\nMy identity.")
        bootstrap_path.write_text("# Bootstrap\n\nStartup instructions.")

        yield {
            "temp_dir": temp_dir,
            "soul_path": str(soul_path),
            "identity_path": str(identity_path),
            "bootstrap_path": str(bootstrap_path),
        }

        # Cleanup
        import shutil
        shutil.rmtree(temp_dir)

    def test_load_files_all(self, temp_personality_files):
        """Test loading all personality files."""
        from core.personality.model import Personality

        p = Personality(
            name="Test",
            role="Test",
            model="test",
            soul_path=temp_personality_files["soul_path"],
            identity_path=temp_personality_files["identity_path"],
            bootstrap_path=temp_personality_files["bootstrap_path"],
        )

        files = p.load_files()

        assert "soul" in files
        assert "identity" in files
        assert "bootstrap" in files
        assert "I am a test soul" in files["soul"]
        assert "My identity" in files["identity"]

    def test_load_files_partial(self, temp_personality_files):
        """Test loading only some personality files."""
        from core.personality.model import Personality

        p = Personality(
            name="Test",
            role="Test",
            model="test",
            soul_path=temp_personality_files["soul_path"],
        )

        files = p.load_files()

        assert "soul" in files
        assert files.get("identity") is None
        assert files.get("bootstrap") is None

    def test_load_files_missing(self):
        """Test loading when files don't exist."""
        from core.personality.model import Personality

        p = Personality(
            name="Test",
            role="Test",
            model="test",
            soul_path="/nonexistent/path/SOUL.md",
        )

        files = p.load_files()

        # Should return None for missing files, not raise
        assert files.get("soul") is None

    def test_load_files_empty(self):
        """Test loading when no paths are set."""
        from core.personality.model import Personality

        p = Personality(
            name="Test",
            role="Test",
            model="test",
        )

        files = p.load_files()

        assert files == {"soul": None, "identity": None, "bootstrap": None}


class TestPersonalityValidation:
    """Test personality validation."""

    def test_name_required(self):
        """Test that name is required."""
        from core.personality.model import Personality

        with pytest.raises((TypeError, ValueError)):
            Personality(role="Test", model="test")  # Missing name

    def test_role_required(self):
        """Test that role is required."""
        from core.personality.model import Personality

        with pytest.raises((TypeError, ValueError)):
            Personality(name="Test", model="test")  # Missing role

    def test_model_required(self):
        """Test that model is required."""
        from core.personality.model import Personality

        with pytest.raises((TypeError, ValueError)):
            Personality(name="Test", role="Test")  # Missing model


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
