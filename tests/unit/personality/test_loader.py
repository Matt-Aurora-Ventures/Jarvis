"""
Unit tests for PersonalityLoader.

Tests:
- load(bot_name) returns Personality
- reload(bot_name) refreshes from disk
- get_all() returns all personalities
- Error handling for missing bots
- Caching behavior
"""

import pytest
import tempfile
import os
import json
from pathlib import Path
from unittest.mock import patch, MagicMock


class TestPersonalityLoader:
    """Test the PersonalityLoader class."""

    @pytest.fixture
    def temp_bots_dir(self):
        """Create temporary bots directory with personality configs."""
        import tempfile
        import shutil

        temp_dir = tempfile.mkdtemp()
        bots_dir = Path(temp_dir) / "bots"

        # Create clawdjarvis
        jarvis_dir = bots_dir / "clawdjarvis"
        jarvis_dir.mkdir(parents=True)
        (jarvis_dir / "CLAWDJARVIS_SOUL.md").write_text(
            "# ClawdJarvis Soul\n\nI am JARVIS - Just A Rather Very Intelligent System."
        )
        (jarvis_dir / "CLAWDJARVIS_IDENTITY.md").write_text(
            "# Identity\n\nSystem orchestrator for KR8TIV AI."
        )
        (jarvis_dir / "personality.json").write_text(json.dumps({
            "name": "ClawdJarvis",
            "role": "System orchestrator and AI assistant",
            "model": "claude-3-opus",
            "soul_path": "CLAWDJARVIS_SOUL.md",
            "identity_path": "CLAWDJARVIS_IDENTITY.md",
            "tone": "professional, Iron Man's Jarvis style",
            "style": "concise and technical",
            "capabilities": ["trading", "system_control", "automation"],
        }))

        # Create clawdfriday
        friday_dir = bots_dir / "clawdfriday"
        friday_dir.mkdir(parents=True)
        (friday_dir / "CLAWDFRIDAY_SOUL.md").write_text(
            "# ClawdFriday Soul\n\nI am Friday, the email AI assistant."
        )
        (friday_dir / "personality.json").write_text(json.dumps({
            "name": "ClawdFriday",
            "role": "Email AI assistant",
            "model": "claude-3-sonnet",
            "soul_path": "CLAWDFRIDAY_SOUL.md",
            "tone": "warm, professional",
            "style": "email-focused",
            "capabilities": ["email_processing", "drafting"],
        }))

        # Create clawdmatt
        matt_dir = bots_dir / "clawdmatt"
        matt_dir.mkdir(parents=True)
        (matt_dir / "CLAWDMATT_SOUL.md").write_text(
            "# ClawdMatt Soul\n\nI am PR Matt, the communications filter."
        )
        (matt_dir / "personality.json").write_text(json.dumps({
            "name": "ClawdMatt",
            "role": "Marketing communications filter",
            "model": "claude-3-haiku",
            "soul_path": "CLAWDMATT_SOUL.md",
            "tone": "professional",
            "style": "pr-focused",
            "capabilities": ["content_review", "pr_filter"],
        }))

        yield {
            "temp_dir": temp_dir,
            "bots_dir": str(bots_dir),
        }

        shutil.rmtree(temp_dir)

    def test_load_single_bot(self, temp_bots_dir):
        """Test loading a single bot personality."""
        from core.personality.loader import PersonalityLoader

        loader = PersonalityLoader(bots_dir=temp_bots_dir["bots_dir"])
        personality = loader.load("clawdjarvis")

        assert personality is not None
        assert personality.name == "ClawdJarvis"
        assert personality.role == "System orchestrator and AI assistant"
        assert personality.model == "claude-3-opus"
        assert "trading" in personality.capabilities

    def test_load_nonexistent_bot(self, temp_bots_dir):
        """Test loading a bot that doesn't exist."""
        from core.personality.loader import PersonalityLoader, PersonalityNotFoundError

        loader = PersonalityLoader(bots_dir=temp_bots_dir["bots_dir"])

        with pytest.raises(PersonalityNotFoundError):
            loader.load("nonexistent_bot")

    def test_load_all_bots(self, temp_bots_dir):
        """Test loading all bot personalities."""
        from core.personality.loader import PersonalityLoader

        loader = PersonalityLoader(bots_dir=temp_bots_dir["bots_dir"])
        all_personalities = loader.get_all()

        assert len(all_personalities) == 3
        assert "clawdjarvis" in all_personalities
        assert "clawdfriday" in all_personalities
        assert "clawdmatt" in all_personalities

    def test_get_all_returns_dict(self, temp_bots_dir):
        """Test get_all() returns Dict[str, Personality]."""
        from core.personality.loader import PersonalityLoader
        from core.personality.model import Personality

        loader = PersonalityLoader(bots_dir=temp_bots_dir["bots_dir"])
        all_personalities = loader.get_all()

        assert isinstance(all_personalities, dict)
        for name, personality in all_personalities.items():
            assert isinstance(name, str)
            assert isinstance(personality, Personality)

    def test_reload_bot(self, temp_bots_dir):
        """Test reloading a bot personality from disk."""
        from core.personality.loader import PersonalityLoader

        loader = PersonalityLoader(bots_dir=temp_bots_dir["bots_dir"])

        # Load initially
        personality1 = loader.load("clawdjarvis")
        assert personality1.tone == "professional, Iron Man's Jarvis style"

        # Modify the file
        config_path = Path(temp_bots_dir["bots_dir"]) / "clawdjarvis" / "personality.json"
        config = json.loads(config_path.read_text())
        config["tone"] = "updated tone"
        config_path.write_text(json.dumps(config))

        # Reload should get new value
        personality2 = loader.reload("clawdjarvis")
        assert personality2.tone == "updated tone"

    def test_caching_behavior(self, temp_bots_dir):
        """Test that loading is cached until reload."""
        from core.personality.loader import PersonalityLoader

        loader = PersonalityLoader(bots_dir=temp_bots_dir["bots_dir"])

        # Load twice - should return cached
        personality1 = loader.load("clawdjarvis")
        personality2 = loader.load("clawdjarvis")

        assert personality1 is personality2  # Same object reference

    def test_reload_clears_cache(self, temp_bots_dir):
        """Test that reload clears cache."""
        from core.personality.loader import PersonalityLoader

        loader = PersonalityLoader(bots_dir=temp_bots_dir["bots_dir"])

        personality1 = loader.load("clawdjarvis")
        personality2 = loader.reload("clawdjarvis")

        assert personality1 is not personality2  # Different object after reload


class TestPersonalityLoaderSingleton:
    """Test singleton behavior of PersonalityLoader."""

    @pytest.fixture
    def temp_bots_dir(self):
        """Create minimal temp bots directory."""
        import tempfile
        import shutil

        temp_dir = tempfile.mkdtemp()
        bots_dir = Path(temp_dir) / "bots"
        bots_dir.mkdir()

        yield {
            "temp_dir": temp_dir,
            "bots_dir": str(bots_dir),
        }

        shutil.rmtree(temp_dir)

    def test_get_loader_singleton(self, temp_bots_dir):
        """Test get_loader returns singleton."""
        from core.personality.loader import get_loader, _reset_loader

        _reset_loader()

        loader1 = get_loader(bots_dir=temp_bots_dir["bots_dir"])
        loader2 = get_loader()

        assert loader1 is loader2

        _reset_loader()


class TestPersonalityLoaderFilePaths:
    """Test file path resolution in PersonalityLoader."""

    @pytest.fixture
    def temp_bots_dir(self):
        """Create temp bots directory with relative paths."""
        import tempfile
        import shutil

        temp_dir = tempfile.mkdtemp()
        bots_dir = Path(temp_dir) / "bots"
        bot_dir = bots_dir / "testbot"
        bot_dir.mkdir(parents=True)

        (bot_dir / "SOUL.md").write_text("Soul content")
        (bot_dir / "personality.json").write_text(json.dumps({
            "name": "TestBot",
            "role": "Test",
            "model": "test",
            "soul_path": "SOUL.md",  # Relative path
        }))

        yield {
            "temp_dir": temp_dir,
            "bots_dir": str(bots_dir),
            "bot_dir": str(bot_dir),
        }

        shutil.rmtree(temp_dir)

    def test_relative_path_resolution(self, temp_bots_dir):
        """Test that relative soul_path is resolved correctly."""
        from core.personality.loader import PersonalityLoader

        loader = PersonalityLoader(bots_dir=temp_bots_dir["bots_dir"])
        personality = loader.load("testbot")

        files = personality.load_files()

        assert files.get("soul") is not None
        assert "Soul content" in files["soul"]


class TestPersonalityLoaderEdgeCases:
    """Test edge cases for PersonalityLoader."""

    @pytest.fixture
    def temp_bots_dir(self):
        """Create temp bots directory."""
        import tempfile
        import shutil

        temp_dir = tempfile.mkdtemp()
        bots_dir = Path(temp_dir) / "bots"
        bots_dir.mkdir()

        yield {
            "temp_dir": temp_dir,
            "bots_dir": str(bots_dir),
        }

        shutil.rmtree(temp_dir)

    def test_empty_bots_dir(self, temp_bots_dir):
        """Test loading from empty bots directory."""
        from core.personality.loader import PersonalityLoader

        loader = PersonalityLoader(bots_dir=temp_bots_dir["bots_dir"])
        all_personalities = loader.get_all()

        assert all_personalities == {}

    def test_bot_dir_without_config(self, temp_bots_dir):
        """Test bot directory without personality.json."""
        from core.personality.loader import PersonalityLoader, PersonalityNotFoundError

        # Create directory without config
        bot_dir = Path(temp_bots_dir["bots_dir"]) / "noconfig"
        bot_dir.mkdir()

        loader = PersonalityLoader(bots_dir=temp_bots_dir["bots_dir"])

        with pytest.raises(PersonalityNotFoundError):
            loader.load("noconfig")

    def test_invalid_json_config(self, temp_bots_dir):
        """Test handling of invalid JSON in personality.json."""
        from core.personality.loader import PersonalityLoader, PersonalityLoadError

        bot_dir = Path(temp_bots_dir["bots_dir"]) / "badjson"
        bot_dir.mkdir()
        (bot_dir / "personality.json").write_text("{ invalid json }")

        loader = PersonalityLoader(bots_dir=temp_bots_dir["bots_dir"])

        with pytest.raises(PersonalityLoadError):
            loader.load("badjson")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
