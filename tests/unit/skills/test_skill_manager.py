"""
Unit tests for the Skill Manager.

Tests skill lifecycle: install, update, remove, validate.
"""

import pytest
import tempfile
import os
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock


class TestSkillManager:
    """Tests for SkillManager class."""

    def test_manager_initializes_with_skills_dir(self, tmp_path):
        """Manager should initialize with skills directory."""
        from core.skills.manager import SkillManager

        manager = SkillManager(skills_dir=tmp_path)

        assert manager.skills_dir == tmp_path
        assert manager.registry is not None

    def test_validate_skill_returns_true_for_valid(self, tmp_path):
        """validate_skill should return True for valid skill structure."""
        from core.skills.manager import SkillManager

        manager = SkillManager(skills_dir=tmp_path)

        # Create valid skill
        skill_path = tmp_path / "valid_skill"
        skill_path.mkdir()
        (skill_path / "SKILL.md").write_text("# Valid Skill\nDescription.")
        (skill_path / "script.py").write_text("print('valid')")

        is_valid, errors = manager.validate_skill(skill_path)

        assert is_valid is True
        assert len(errors) == 0

    def test_validate_skill_returns_errors_for_invalid(self, tmp_path):
        """validate_skill should return errors for invalid skill."""
        from core.skills.manager import SkillManager

        manager = SkillManager(skills_dir=tmp_path)

        # Create invalid skill (missing SKILL.md)
        skill_path = tmp_path / "invalid_skill"
        skill_path.mkdir()
        (skill_path / "script.py").write_text("print('invalid')")

        is_valid, errors = manager.validate_skill(skill_path)

        assert is_valid is False
        assert len(errors) > 0
        assert any("SKILL.md" in e for e in errors)

    def test_install_skill_from_path(self, tmp_path):
        """install_skill should copy skill from source path."""
        from core.skills.manager import SkillManager

        # Set up skills directory and source
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        source_dir = tmp_path / "source" / "my_skill"
        source_dir.mkdir(parents=True)
        (source_dir / "SKILL.md").write_text("# My Skill\nInstalled skill.")
        (source_dir / "script.py").write_text("print('installed')")

        manager = SkillManager(skills_dir=skills_dir)

        result = manager.install_skill(source_dir)

        assert result.success is True
        assert (skills_dir / "my_skill" / "SKILL.md").exists()
        assert (skills_dir / "my_skill" / "script.py").exists()

    def test_install_skill_fails_for_invalid_source(self, tmp_path):
        """install_skill should fail for invalid source path."""
        from core.skills.manager import SkillManager

        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()

        # Create invalid source (missing SKILL.md)
        source_dir = tmp_path / "invalid_source"
        source_dir.mkdir()
        (source_dir / "script.py").write_text("print('broken')")

        manager = SkillManager(skills_dir=skills_dir)

        result = manager.install_skill(source_dir)

        assert result.success is False
        assert "validation" in result.error.lower() or "invalid" in result.error.lower()

    def test_install_skill_fails_if_exists(self, tmp_path):
        """install_skill should fail if skill already exists."""
        from core.skills.manager import SkillManager

        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()

        # Create existing skill
        existing = skills_dir / "existing"
        existing.mkdir()
        (existing / "SKILL.md").write_text("# Existing\nAlready here.")
        (existing / "script.py").write_text("print('existing')")

        # Create source with same name
        source = tmp_path / "existing"
        source.mkdir()
        (source / "SKILL.md").write_text("# Existing\nNew version.")
        (source / "script.py").write_text("print('new')")

        manager = SkillManager(skills_dir=skills_dir)

        result = manager.install_skill(source)

        assert result.success is False
        assert "exists" in result.error.lower()

    def test_install_skill_with_force_overwrites(self, tmp_path):
        """install_skill with force=True should overwrite existing."""
        from core.skills.manager import SkillManager

        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()

        # Create existing skill
        existing = skills_dir / "overwrite"
        existing.mkdir()
        (existing / "SKILL.md").write_text("# Old\nOld version.")
        (existing / "script.py").write_text("print('old')")

        # Create source with same name
        source = tmp_path / "overwrite"
        source.mkdir()
        (source / "SKILL.md").write_text("# New\nNew version.")
        (source / "script.py").write_text("print('new')")

        manager = SkillManager(skills_dir=skills_dir)

        result = manager.install_skill(source, force=True)

        assert result.success is True
        assert "New version" in (skills_dir / "overwrite" / "SKILL.md").read_text()

    def test_remove_skill(self, tmp_path):
        """remove_skill should delete skill directory."""
        from core.skills.manager import SkillManager

        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()

        # Create skill to remove
        to_remove = skills_dir / "removable"
        to_remove.mkdir()
        (to_remove / "SKILL.md").write_text("# Removable\nWill be removed.")
        (to_remove / "script.py").write_text("print('bye')")

        manager = SkillManager(skills_dir=skills_dir)

        result = manager.remove_skill("removable")

        assert result.success is True
        assert not to_remove.exists()

    def test_remove_skill_fails_for_nonexistent(self, tmp_path):
        """remove_skill should fail for non-existent skill."""
        from core.skills.manager import SkillManager

        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()

        manager = SkillManager(skills_dir=skills_dir)

        result = manager.remove_skill("nonexistent")

        assert result.success is False
        assert "not found" in result.error.lower()

    def test_update_skill(self, tmp_path):
        """update_skill should replace skill with new version."""
        from core.skills.manager import SkillManager

        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()

        # Create existing skill
        existing = skills_dir / "updatable"
        existing.mkdir()
        (existing / "SKILL.md").write_text("# v1\nVersion 1.")
        (existing / "script.py").write_text("print('v1')")

        # Create new version source
        source = tmp_path / "updatable_v2"
        source.mkdir()
        (source / "SKILL.md").write_text("# v2\nVersion 2.")
        (source / "script.py").write_text("print('v2')")

        manager = SkillManager(skills_dir=skills_dir)

        result = manager.update_skill("updatable", source)

        assert result.success is True
        assert "Version 2" in (skills_dir / "updatable" / "SKILL.md").read_text()

    def test_list_installed_skills(self, tmp_path):
        """list_installed should return all installed skills."""
        from core.skills.manager import SkillManager

        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()

        # Create multiple skills
        for name in ["alpha", "beta", "gamma"]:
            skill_dir = skills_dir / name
            skill_dir.mkdir()
            (skill_dir / "SKILL.md").write_text(f"# {name}\nDescription.")
            (skill_dir / "script.py").write_text(f"print('{name}')")

        manager = SkillManager(skills_dir=skills_dir)

        installed = manager.list_installed()

        assert len(installed) == 3
        assert "alpha" in installed
        assert "beta" in installed
        assert "gamma" in installed


class TestSkillInstallResult:
    """Tests for SkillInstallResult dataclass."""

    def test_result_attributes(self):
        """SkillInstallResult should have expected attributes."""
        from core.skills.manager import SkillInstallResult

        result = SkillInstallResult(
            success=True,
            skill_name="test",
            path=Path("/skills/test"),
            error=None,
        )

        assert result.success is True
        assert result.skill_name == "test"
        assert result.path == Path("/skills/test")
        assert result.error is None
