"""
Skill Manager - Handles skill lifecycle (install, update, remove).

Provides functionality for installing skills from various sources,
validating skill structure, and managing installed skills.
"""

import logging
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

from core.skills.registry import SkillRegistry, DEFAULT_SKILLS_DIR

logger = logging.getLogger(__name__)


@dataclass
class SkillInstallResult:
    """Result of a skill installation."""

    success: bool
    skill_name: str = ""
    path: Optional[Path] = None
    error: Optional[str] = None


class SkillManager:
    """
    Manages skill lifecycle operations.

    Supports:
    - Installing skills from local paths
    - Validating skill structure
    - Removing installed skills
    - Updating existing skills
    - Listing installed skills
    """

    def __init__(self, skills_dir: Optional[Path] = None):
        """
        Initialize the skill manager.

        Args:
            skills_dir: Directory for skills. Defaults to PROJECT_ROOT/skills/
        """
        self.skills_dir = Path(skills_dir) if skills_dir else DEFAULT_SKILLS_DIR
        self.registry = SkillRegistry(self.skills_dir)

        # Ensure skills directory exists
        self.skills_dir.mkdir(parents=True, exist_ok=True)

    def validate_skill(self, skill_path: Path) -> Tuple[bool, List[str]]:
        """
        Validate a skill's structure.

        Args:
            skill_path: Path to the skill directory.

        Returns:
            Tuple of (is_valid, list of error messages).
        """
        errors = []

        if not skill_path.exists():
            errors.append(f"Path does not exist: {skill_path}")
            return False, errors

        if not skill_path.is_dir():
            errors.append(f"Path is not a directory: {skill_path}")
            return False, errors

        # Check required files
        required_files = {
            "SKILL.md": "Skill definition file",
            "script.py": "Executable script",
        }

        for filename, description in required_files.items():
            if not (skill_path / filename).exists():
                errors.append(f"Missing {description}: {filename}")

        # Validate SKILL.md content if it exists
        skill_md = skill_path / "SKILL.md"
        if skill_md.exists():
            content = skill_md.read_text(encoding="utf-8")
            if not content.strip():
                errors.append("SKILL.md is empty")
            elif not content.strip().startswith("#"):
                errors.append("SKILL.md should start with a title (# Title)")

        # Validate script.py if it exists
        script_py = skill_path / "script.py"
        if script_py.exists():
            try:
                content = script_py.read_text(encoding="utf-8")
                compile(content, str(script_py), "exec")
            except SyntaxError as e:
                errors.append(f"Python syntax error in script.py: {e}")

        return len(errors) == 0, errors

    def install_skill(
        self,
        source: Path,
        force: bool = False,
    ) -> SkillInstallResult:
        """
        Install a skill from a local path.

        Args:
            source: Path to the skill source directory.
            force: If True, overwrite existing skill with same name.

        Returns:
            SkillInstallResult with installation details.
        """
        source = Path(source)

        # Validate source
        is_valid, errors = self.validate_skill(source)
        if not is_valid:
            return SkillInstallResult(
                success=False,
                error=f"Validation failed: {'; '.join(errors)}",
            )

        skill_name = source.name
        target_path = self.skills_dir / skill_name

        # Check if skill exists
        if target_path.exists():
            if not force:
                return SkillInstallResult(
                    success=False,
                    skill_name=skill_name,
                    error=f"Skill '{skill_name}' already exists. Use force=True to overwrite.",
                )
            # Remove existing skill
            shutil.rmtree(target_path)
            logger.info(f"Removed existing skill: {skill_name}")

        # Copy skill to skills directory
        try:
            shutil.copytree(source, target_path)
            logger.info(f"Installed skill: {skill_name}")

            # Refresh registry
            self.registry.discover_skills()

            return SkillInstallResult(
                success=True,
                skill_name=skill_name,
                path=target_path,
            )

        except Exception as e:
            logger.error(f"Failed to install skill {skill_name}: {e}")
            return SkillInstallResult(
                success=False,
                skill_name=skill_name,
                error=str(e),
            )

    def remove_skill(self, skill_name: str) -> SkillInstallResult:
        """
        Remove an installed skill.

        Args:
            skill_name: Name of the skill to remove.

        Returns:
            SkillInstallResult with removal details.
        """
        skill_path = self.skills_dir / skill_name

        if not skill_path.exists():
            return SkillInstallResult(
                success=False,
                skill_name=skill_name,
                error=f"Skill '{skill_name}' not found",
            )

        try:
            shutil.rmtree(skill_path)
            logger.info(f"Removed skill: {skill_name}")

            # Refresh registry
            self.registry.discover_skills()

            return SkillInstallResult(
                success=True,
                skill_name=skill_name,
            )

        except Exception as e:
            logger.error(f"Failed to remove skill {skill_name}: {e}")
            return SkillInstallResult(
                success=False,
                skill_name=skill_name,
                error=str(e),
            )

    def update_skill(
        self,
        skill_name: str,
        source: Path,
    ) -> SkillInstallResult:
        """
        Update an existing skill with a new version.

        Args:
            skill_name: Name of the skill to update.
            source: Path to the new skill version.

        Returns:
            SkillInstallResult with update details.
        """
        skill_path = self.skills_dir / skill_name

        if not skill_path.exists():
            return SkillInstallResult(
                success=False,
                skill_name=skill_name,
                error=f"Skill '{skill_name}' not found. Cannot update.",
            )

        # Install with force to overwrite
        return self.install_skill(source, force=True)

    def list_installed(self) -> List[str]:
        """
        List all installed skills.

        Returns:
            List of installed skill names.
        """
        # Refresh and return skill list
        self.registry.discover_skills()
        return self.registry.list_skills()

    def get_skill_info(self, skill_name: str) -> Optional[dict]:
        """
        Get detailed information about a skill.

        Args:
            skill_name: Name of the skill.

        Returns:
            Skill metadata dictionary, or None if not found.
        """
        return self.registry.get_skill(skill_name)
