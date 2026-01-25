"""
Unit tests for the Skill Registry.

Tests the ability to discover, load, and list skills from the skills/ directory.
"""

import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import patch, MagicMock


class TestSkillRegistry:
    """Tests for SkillRegistry class."""

    def test_registry_initializes_with_skills_dir(self, tmp_path):
        """Registry should initialize with a skills directory."""
        from core.skills.registry import SkillRegistry

        registry = SkillRegistry(skills_dir=tmp_path)
        assert registry.skills_dir == tmp_path
        assert registry._skills == {}

    def test_discover_skills_finds_valid_skill(self, tmp_path):
        """discover_skills should find skills with SKILL.md and script.py."""
        from core.skills.registry import SkillRegistry

        # Create a valid skill structure
        skill_dir = tmp_path / "echo"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("""# Echo Skill

Simple test skill that echoes back arguments.

## Usage
```
/skill run echo Hello World
```
""")
        (skill_dir / "script.py").write_text("""import sys
print(f"Echo: {' '.join(sys.argv[1:])}")
""")

        registry = SkillRegistry(skills_dir=tmp_path)
        skills = registry.discover_skills()

        assert "echo" in skills
        assert skills["echo"]["name"] == "echo"
        assert skills["echo"]["has_script"] is True

    def test_discover_skills_ignores_incomplete_skill(self, tmp_path):
        """discover_skills should ignore directories without SKILL.md."""
        from core.skills.registry import SkillRegistry

        # Create incomplete skill (no SKILL.md)
        skill_dir = tmp_path / "broken"
        skill_dir.mkdir()
        (skill_dir / "script.py").write_text("print('hello')")

        registry = SkillRegistry(skills_dir=tmp_path)
        skills = registry.discover_skills()

        assert "broken" not in skills

    def test_load_skill_returns_skill_metadata(self, tmp_path):
        """load_skill should return skill metadata from SKILL.md."""
        from core.skills.registry import SkillRegistry

        # Create a skill with metadata
        skill_dir = tmp_path / "test_skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("""# Test Skill

A skill for testing purposes.

## Usage
```
/skill run test_skill arg1
```

## Arguments
- arg1: First argument
""")
        (skill_dir / "script.py").write_text("print('test')")

        registry = SkillRegistry(skills_dir=tmp_path)
        registry.discover_skills()

        skill = registry.load_skill("test_skill")

        assert skill is not None
        assert skill["name"] == "test_skill"
        assert "Test Skill" in skill["description"]
        assert skill["path"] == skill_dir

    def test_load_skill_returns_none_for_nonexistent(self, tmp_path):
        """load_skill should return None for non-existent skill."""
        from core.skills.registry import SkillRegistry

        registry = SkillRegistry(skills_dir=tmp_path)
        registry.discover_skills()

        skill = registry.load_skill("nonexistent")
        assert skill is None

    def test_get_skill_returns_cached_skill(self, tmp_path):
        """get_skill should return skill from cache after discovery."""
        from core.skills.registry import SkillRegistry

        # Create skill
        skill_dir = tmp_path / "cached"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("# Cached Skill\nTest caching.")
        (skill_dir / "script.py").write_text("print('cached')")

        registry = SkillRegistry(skills_dir=tmp_path)
        registry.discover_skills()

        skill = registry.get_skill("cached")
        assert skill is not None
        assert skill["name"] == "cached"

    def test_list_skills_returns_all_discovered(self, tmp_path):
        """list_skills should return all discovered skills."""
        from core.skills.registry import SkillRegistry

        # Create multiple skills
        for name in ["skill1", "skill2", "skill3"]:
            skill_dir = tmp_path / name
            skill_dir.mkdir()
            (skill_dir / "SKILL.md").write_text(f"# {name}\nDescription.")
            (skill_dir / "script.py").write_text(f"print('{name}')")

        registry = SkillRegistry(skills_dir=tmp_path)
        registry.discover_skills()

        skills = registry.list_skills()

        assert len(skills) == 3
        assert "skill1" in skills
        assert "skill2" in skills
        assert "skill3" in skills

    def test_validate_skill_structure_checks_required_files(self, tmp_path):
        """validate_skill_structure should verify SKILL.md and script.py exist."""
        from core.skills.registry import SkillRegistry

        registry = SkillRegistry(skills_dir=tmp_path)

        # Valid skill
        valid_dir = tmp_path / "valid"
        valid_dir.mkdir()
        (valid_dir / "SKILL.md").write_text("# Valid\nOK.")
        (valid_dir / "script.py").write_text("print('ok')")

        assert registry.validate_skill_structure(valid_dir) is True

        # Invalid - missing SKILL.md
        invalid_dir = tmp_path / "invalid"
        invalid_dir.mkdir()
        (invalid_dir / "script.py").write_text("print('ok')")

        assert registry.validate_skill_structure(invalid_dir) is False

    def test_skill_metadata_extraction(self, tmp_path):
        """Should extract title, description, and usage from SKILL.md."""
        from core.skills.registry import SkillRegistry

        skill_dir = tmp_path / "meta_test"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("""# My Amazing Skill

This skill does amazing things.

## Usage
```
/skill run meta_test --verbose
```

## Arguments
- --verbose: Enable verbose output
""")
        (skill_dir / "script.py").write_text("print('amazing')")

        registry = SkillRegistry(skills_dir=tmp_path)
        registry.discover_skills()

        skill = registry.get_skill("meta_test")

        assert skill["title"] == "My Amazing Skill"
        assert "amazing things" in skill["description"]


class TestSkillRegistryIntegration:
    """Integration tests using the default skills directory."""

    def test_default_skills_dir_is_project_skills(self):
        """Default skills_dir should be PROJECT_ROOT/skills/."""
        from core.skills.registry import SkillRegistry, DEFAULT_SKILLS_DIR

        registry = SkillRegistry()
        assert registry.skills_dir == DEFAULT_SKILLS_DIR
        assert DEFAULT_SKILLS_DIR.name == "skills"
