"""
Unit tests for Personality Validator.

Tests:
- validate_personality() returns List[Error]
- Required file existence checks
- SOUL format validation
- IDENTITY format validation
- Error types and messages
"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch


class TestPersonalityValidator:
    """Test the validate_personality function."""

    @pytest.fixture
    def temp_files(self):
        """Create temporary files for testing."""
        import tempfile
        import shutil

        temp_dir = tempfile.mkdtemp()

        yield {
            "temp_dir": temp_dir,
        }

        shutil.rmtree(temp_dir)

    def test_validate_minimal_personality(self):
        """Test validating a minimal valid personality."""
        from core.personality.model import Personality
        from core.personality.validator import validate_personality

        p = Personality(
            name="TestBot",
            role="Test",
            model="test",
        )

        errors = validate_personality(p)

        # Minimal personality should have no errors
        assert errors == []

    def test_validate_missing_soul_file(self, temp_files):
        """Test validation when soul_path points to nonexistent file."""
        from core.personality.model import Personality
        from core.personality.validator import validate_personality, ValidationError

        p = Personality(
            name="TestBot",
            role="Test",
            model="test",
            soul_path="/nonexistent/path/SOUL.md",
        )

        errors = validate_personality(p)

        assert len(errors) >= 1
        assert any("soul" in str(e).lower() for e in errors)

    def test_validate_missing_identity_file(self, temp_files):
        """Test validation when identity_path points to nonexistent file."""
        from core.personality.model import Personality
        from core.personality.validator import validate_personality

        p = Personality(
            name="TestBot",
            role="Test",
            model="test",
            identity_path="/nonexistent/path/IDENTITY.md",
        )

        errors = validate_personality(p)

        assert len(errors) >= 1
        assert any("identity" in str(e).lower() for e in errors)

    def test_validate_existing_files(self, temp_files):
        """Test validation with existing files."""
        from core.personality.model import Personality
        from core.personality.validator import validate_personality

        # Create valid files
        soul_path = Path(temp_files["temp_dir"]) / "SOUL.md"
        identity_path = Path(temp_files["temp_dir"]) / "IDENTITY.md"

        soul_path.write_text("# Soul\n\nCore personality and values.")
        identity_path.write_text("# Identity\n\nWho I am.")

        p = Personality(
            name="TestBot",
            role="Test",
            model="test",
            soul_path=str(soul_path),
            identity_path=str(identity_path),
        )

        errors = validate_personality(p)

        assert errors == []


class TestSOULFormatValidation:
    """Test SOUL file format validation."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory."""
        import tempfile
        import shutil

        temp_dir = tempfile.mkdtemp()

        yield temp_dir

        shutil.rmtree(temp_dir)

    def test_valid_soul_format(self, temp_dir):
        """Test validation of valid SOUL file format."""
        from core.personality.model import Personality
        from core.personality.validator import validate_personality

        soul_path = Path(temp_dir) / "SOUL.md"
        soul_path.write_text("""# Soul

## Core Values
- Helpfulness
- Honesty

## Personality
I am a helpful assistant.
""")

        p = Personality(
            name="Test",
            role="Test",
            model="test",
            soul_path=str(soul_path),
        )

        errors = validate_personality(p)

        # Valid format should have no errors
        assert len([e for e in errors if "format" in str(e).lower()]) == 0

    def test_empty_soul_file(self, temp_dir):
        """Test validation of empty SOUL file."""
        from core.personality.model import Personality
        from core.personality.validator import validate_personality

        soul_path = Path(temp_dir) / "SOUL.md"
        soul_path.write_text("")

        p = Personality(
            name="Test",
            role="Test",
            model="test",
            soul_path=str(soul_path),
        )

        errors = validate_personality(p)

        # Empty file should have warning/error
        assert len(errors) >= 1
        assert any("empty" in str(e).lower() for e in errors)

    def test_soul_missing_heading(self, temp_dir):
        """Test SOUL file without markdown heading."""
        from core.personality.model import Personality
        from core.personality.validator import validate_personality

        soul_path = Path(temp_dir) / "SOUL.md"
        soul_path.write_text("Just plain text without any headers")

        p = Personality(
            name="Test",
            role="Test",
            model="test",
            soul_path=str(soul_path),
        )

        errors = validate_personality(p)

        # Should warn about missing structure
        assert len(errors) >= 1


class TestIDENTITYFormatValidation:
    """Test IDENTITY file format validation."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory."""
        import tempfile
        import shutil

        temp_dir = tempfile.mkdtemp()

        yield temp_dir

        shutil.rmtree(temp_dir)

    def test_valid_identity_format(self, temp_dir):
        """Test validation of valid IDENTITY file format."""
        from core.personality.model import Personality
        from core.personality.validator import validate_personality

        identity_path = Path(temp_dir) / "IDENTITY.md"
        identity_path.write_text("""# Identity

## Name
TestBot

## Role
A helpful test assistant.

## Background
Created for testing purposes.
""")

        p = Personality(
            name="Test",
            role="Test",
            model="test",
            identity_path=str(identity_path),
        )

        errors = validate_personality(p)

        # Valid format should have no errors
        assert len([e for e in errors if "identity" in str(e).lower()]) == 0

    def test_empty_identity_file(self, temp_dir):
        """Test validation of empty IDENTITY file."""
        from core.personality.model import Personality
        from core.personality.validator import validate_personality

        identity_path = Path(temp_dir) / "IDENTITY.md"
        identity_path.write_text("")

        p = Personality(
            name="Test",
            role="Test",
            model="test",
            identity_path=str(identity_path),
        )

        errors = validate_personality(p)

        # Empty file should have error
        assert len(errors) >= 1
        assert any("empty" in str(e).lower() for e in errors)


class TestValidationErrorTypes:
    """Test ValidationError class."""

    def test_validation_error_creation(self):
        """Test creating a ValidationError."""
        from core.personality.validator import ValidationError, ErrorSeverity

        error = ValidationError(
            field="soul_path",
            message="File not found",
            severity=ErrorSeverity.ERROR,
        )

        assert error.field == "soul_path"
        assert error.message == "File not found"
        assert error.severity == ErrorSeverity.ERROR

    def test_validation_error_str(self):
        """Test ValidationError string representation."""
        from core.personality.validator import ValidationError, ErrorSeverity

        error = ValidationError(
            field="name",
            message="Name too short",
            severity=ErrorSeverity.WARNING,
        )

        error_str = str(error)
        assert "name" in error_str
        assert "Name too short" in error_str

    def test_error_severity_levels(self):
        """Test error severity levels exist."""
        from core.personality.validator import ErrorSeverity

        assert ErrorSeverity.ERROR is not None
        assert ErrorSeverity.WARNING is not None
        assert ErrorSeverity.INFO is not None


class TestValidationWithPaths:
    """Test validation with different path configurations."""

    @pytest.fixture
    def temp_bot_dir(self):
        """Create a complete temp bot directory."""
        import tempfile
        import shutil

        temp_dir = tempfile.mkdtemp()
        bot_dir = Path(temp_dir) / "testbot"
        bot_dir.mkdir()

        (bot_dir / "SOUL.md").write_text("# Soul\n\nTest soul content.")
        (bot_dir / "IDENTITY.md").write_text("# Identity\n\nTest identity.")
        (bot_dir / "BOOTSTRAP.md").write_text("# Bootstrap\n\nStartup.")

        yield {
            "temp_dir": temp_dir,
            "bot_dir": str(bot_dir),
            "soul_path": str(bot_dir / "SOUL.md"),
            "identity_path": str(bot_dir / "IDENTITY.md"),
            "bootstrap_path": str(bot_dir / "BOOTSTRAP.md"),
        }

        shutil.rmtree(temp_dir)

    def test_validate_all_files_present(self, temp_bot_dir):
        """Test validation when all files are present and valid."""
        from core.personality.model import Personality
        from core.personality.validator import validate_personality

        p = Personality(
            name="TestBot",
            role="Test assistant",
            model="claude-3",
            soul_path=temp_bot_dir["soul_path"],
            identity_path=temp_bot_dir["identity_path"],
            bootstrap_path=temp_bot_dir["bootstrap_path"],
        )

        errors = validate_personality(p)

        # All files present and valid
        assert len([e for e in errors if "not found" in str(e).lower()]) == 0

    def test_validate_relative_paths(self, temp_bot_dir):
        """Test validation with relative paths and base_path."""
        from core.personality.model import Personality
        from core.personality.validator import validate_personality

        p = Personality(
            name="TestBot",
            role="Test",
            model="test",
            soul_path="SOUL.md",  # Relative
        )

        errors = validate_personality(p, base_path=temp_bot_dir["bot_dir"])

        # Should resolve relative path correctly
        assert len([e for e in errors if "not found" in str(e).lower()]) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
