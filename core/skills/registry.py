"""
Skill Registry - Discovers and loads skills from the skills directory.

Skills are discovered by scanning for directories containing SKILL.md and script.py.
Metadata is extracted from the SKILL.md file.
"""

import logging
import re
from pathlib import Path
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

# Default skills directory at project root
DEFAULT_SKILLS_DIR = Path(__file__).resolve().parents[2] / "skills"


class SkillRegistry:
    """
    Registry for discovering and loading skills.

    Scans the skills directory for valid skill packages and maintains
    a cache of skill metadata.
    """

    def __init__(self, skills_dir: Optional[Path] = None):
        """
        Initialize the skill registry.

        Args:
            skills_dir: Directory containing skills. Defaults to PROJECT_ROOT/skills/
        """
        self.skills_dir = Path(skills_dir) if skills_dir else DEFAULT_SKILLS_DIR
        self._skills: Dict[str, Dict[str, Any]] = {}

    def discover_skills(self) -> Dict[str, Dict[str, Any]]:
        """
        Scan skills directory and discover all valid skills.

        Returns:
            Dictionary mapping skill names to their metadata.
        """
        self._skills = {}

        if not self.skills_dir.exists():
            logger.warning(f"Skills directory does not exist: {self.skills_dir}")
            return self._skills

        for skill_path in self.skills_dir.iterdir():
            if not skill_path.is_dir():
                continue

            if skill_path.name.startswith(".") or skill_path.name.startswith("_"):
                continue

            if not self.validate_skill_structure(skill_path):
                logger.debug(f"Skipping invalid skill: {skill_path.name}")
                continue

            try:
                metadata = self._extract_metadata(skill_path)
                self._skills[skill_path.name] = metadata
                logger.info(f"Discovered skill: {skill_path.name}")
            except Exception as e:
                logger.error(f"Failed to load skill {skill_path.name}: {e}")

        return self._skills

    def validate_skill_structure(self, skill_path: Path) -> bool:
        """
        Validate that a directory contains required skill files.

        Args:
            skill_path: Path to the skill directory.

        Returns:
            True if skill structure is valid, False otherwise.
        """
        required_files = ["SKILL.md", "script.py"]

        for filename in required_files:
            if not (skill_path / filename).exists():
                return False

        return True

    def load_skill(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Load a specific skill by name.

        Args:
            name: Name of the skill to load.

        Returns:
            Skill metadata dictionary, or None if not found.
        """
        # Check cache first
        if name in self._skills:
            return self._skills[name]

        # Try to load from disk
        skill_path = self.skills_dir / name
        if not skill_path.exists() or not self.validate_skill_structure(skill_path):
            return None

        try:
            metadata = self._extract_metadata(skill_path)
            self._skills[name] = metadata
            return metadata
        except Exception as e:
            logger.error(f"Failed to load skill {name}: {e}")
            return None

    def get_skill(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Get a skill from the cache.

        Args:
            name: Name of the skill.

        Returns:
            Skill metadata, or None if not cached.
        """
        return self._skills.get(name)

    def list_skills(self) -> List[str]:
        """
        List all discovered skill names.

        Returns:
            List of skill names.
        """
        return list(self._skills.keys())

    def _extract_metadata(self, skill_path: Path) -> Dict[str, Any]:
        """
        Extract metadata from a skill's SKILL.md file.

        Args:
            skill_path: Path to the skill directory.

        Returns:
            Dictionary containing skill metadata.
        """
        skill_md = skill_path / "SKILL.md"
        content = skill_md.read_text(encoding="utf-8")

        # Extract title from first H1
        title_match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
        title = title_match.group(1).strip() if title_match else skill_path.name

        # Extract description (first paragraph after title)
        description = ""
        lines = content.split("\n")
        in_description = False
        for line in lines:
            if line.startswith("# "):
                in_description = True
                continue
            if in_description:
                if line.strip() and not line.startswith("#"):
                    description = line.strip()
                    break
                elif line.startswith("#"):
                    break

        # Check for optional files
        has_requirements = (skill_path / "requirements.txt").exists()
        has_config = (skill_path / "config.json").exists()

        return {
            "name": skill_path.name,
            "title": title,
            "description": description,
            "path": skill_path,
            "has_script": True,
            "has_requirements": has_requirements,
            "has_config": has_config,
            "raw_content": content,
        }
