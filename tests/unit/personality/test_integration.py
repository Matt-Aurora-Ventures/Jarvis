"""
Integration tests for Personality System.

Tests loading actual bot personalities from the bots/ directory.
"""

import pytest
from pathlib import Path


class TestRealBotPersonalities:
    """Test loading actual bot personalities."""

    @pytest.fixture
    def real_bots_dir(self):
        """Get the real bots directory."""
        project_root = Path(__file__).parent.parent.parent.parent
        return project_root / "bots"

    def test_clawdjarvis_personality_exists(self, real_bots_dir):
        """Test that ClawdJarvis personality config exists."""
        from core.personality.loader import PersonalityLoader, _reset_loader

        _reset_loader()
        loader = PersonalityLoader(bots_dir=str(real_bots_dir))

        personality = loader.load("clawdjarvis")

        assert personality is not None
        assert personality.name == "ClawdJarvis"
        assert personality.role == "System orchestrator and AI assistant"
        assert "trading" in personality.capabilities

        _reset_loader()

    def test_clawdfriday_personality_exists(self, real_bots_dir):
        """Test that ClawdFriday personality config exists."""
        from core.personality.loader import PersonalityLoader, _reset_loader

        _reset_loader()
        loader = PersonalityLoader(bots_dir=str(real_bots_dir))

        personality = loader.load("clawdfriday")

        assert personality is not None
        assert personality.name == "ClawdFriday"
        assert personality.role == "Email AI assistant"
        assert "email_processing" in personality.capabilities

        _reset_loader()

    def test_clawdmatt_personality_exists(self, real_bots_dir):
        """Test that ClawdMatt personality config exists."""
        from core.personality.loader import PersonalityLoader, _reset_loader

        _reset_loader()
        loader = PersonalityLoader(bots_dir=str(real_bots_dir))

        personality = loader.load("clawdmatt")

        assert personality is not None
        assert personality.name == "ClawdMatt"
        assert personality.role == "Marketing communications filter"
        assert "pr_filter" in personality.capabilities

        _reset_loader()

    def test_all_bots_have_soul_files(self, real_bots_dir):
        """Test that all clawdbots have SOUL files."""
        from core.personality.loader import PersonalityLoader, _reset_loader

        _reset_loader()
        loader = PersonalityLoader(bots_dir=str(real_bots_dir))

        for bot_name in ["clawdjarvis", "clawdfriday", "clawdmatt"]:
            personality = loader.load(bot_name)
            files = personality.load_files()

            assert files.get("soul") is not None, f"{bot_name} missing SOUL file"
            assert "# " in files["soul"], f"{bot_name} SOUL missing header"

        _reset_loader()

    def test_all_bots_validate_successfully(self, real_bots_dir):
        """Test that all clawdbot personalities pass validation."""
        from core.personality.loader import PersonalityLoader, _reset_loader
        from core.personality.validator import validate_personality, ErrorSeverity

        _reset_loader()
        loader = PersonalityLoader(bots_dir=str(real_bots_dir))

        for bot_name in ["clawdjarvis", "clawdfriday", "clawdmatt"]:
            personality = loader.load(bot_name)
            errors = validate_personality(personality)

            # Should have no ERROR-level issues
            critical_errors = [e for e in errors if e.severity == ErrorSeverity.ERROR]
            assert len(critical_errors) == 0, f"{bot_name} has validation errors: {critical_errors}"

        _reset_loader()

    def test_get_all_returns_clawdbots(self, real_bots_dir):
        """Test get_all() includes all clawdbots."""
        from core.personality.loader import PersonalityLoader, _reset_loader

        _reset_loader()
        loader = PersonalityLoader(bots_dir=str(real_bots_dir))

        all_personalities = loader.get_all()

        # Should include at least the three clawdbots
        assert "clawdjarvis" in all_personalities
        assert "clawdfriday" in all_personalities
        assert "clawdmatt" in all_personalities

        _reset_loader()


class TestPersonalityFileLoading:
    """Test loading personality markdown files."""

    @pytest.fixture
    def real_bots_dir(self):
        """Get the real bots directory."""
        project_root = Path(__file__).parent.parent.parent.parent
        return project_root / "bots"

    def test_jarvis_soul_content(self, real_bots_dir):
        """Test ClawdJarvis SOUL file content."""
        from core.personality.loader import PersonalityLoader, _reset_loader

        _reset_loader()
        loader = PersonalityLoader(bots_dir=str(real_bots_dir))

        personality = loader.load("clawdjarvis")
        files = personality.load_files()

        soul = files.get("soul")
        assert soul is not None
        assert "JARVIS" in soul
        assert "Core Values" in soul or "Core Identity" in soul

        _reset_loader()

    def test_friday_soul_content(self, real_bots_dir):
        """Test ClawdFriday SOUL file content."""
        from core.personality.loader import PersonalityLoader, _reset_loader

        _reset_loader()
        loader = PersonalityLoader(bots_dir=str(real_bots_dir))

        personality = loader.load("clawdfriday")
        files = personality.load_files()

        soul = files.get("soul")
        assert soul is not None
        assert "Friday" in soul
        assert "email" in soul.lower() or "Email" in soul

        _reset_loader()

    def test_matt_soul_content(self, real_bots_dir):
        """Test ClawdMatt SOUL file content."""
        from core.personality.loader import PersonalityLoader, _reset_loader

        _reset_loader()
        loader = PersonalityLoader(bots_dir=str(real_bots_dir))

        personality = loader.load("clawdmatt")
        files = personality.load_files()

        soul = files.get("soul")
        assert soul is not None
        assert "PR" in soul or "Matt" in soul
        assert "filter" in soul.lower() or "review" in soul.lower()

        _reset_loader()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
