"""
Jarvis Skill System.

A Clawdbot-style skill system that allows dynamic skill discovery,
execution, and management.

Skill Structure:
    skills/
        skill-name/
            SKILL.md         # Skill definition and documentation
            script.py        # Executable Python script
            requirements.txt # Dependencies (optional)
            config.json      # Skill configuration (optional)

Usage:
    from core.skills import SkillRegistry, SkillExecutor, SkillManager

    # Discover and run skills
    registry = SkillRegistry()
    registry.discover_skills()

    executor = SkillExecutor(registry)
    result = executor.execute("echo", ["Hello", "World"])
    print(result.output)

    # Manage skills
    manager = SkillManager()
    manager.install_skill("/path/to/skill")
    manager.remove_skill("old_skill")
"""

from core.skills.registry import SkillRegistry, DEFAULT_SKILLS_DIR
from core.skills.executor import SkillExecutor, SkillExecutionResult
from core.skills.manager import SkillManager, SkillInstallResult

__all__ = [
    "SkillRegistry",
    "SkillExecutor",
    "SkillExecutionResult",
    "SkillManager",
    "SkillInstallResult",
    "DEFAULT_SKILLS_DIR",
]
