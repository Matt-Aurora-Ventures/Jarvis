"""
Skill Handler for ClawdJarvis Telegram Bot.

Provides self-healing skill acquisition for the Jarvis bot.
When a skill is missing, it will:
1. Search local skills and skills.sh
2. Auto-install if pre-authorized
3. Execute the skill

Usage:
    from bots.clawdjarvis.skill_handler import JarvisSkillHandler

    handler = JarvisSkillHandler()
    result = await handler.execute_skill("docker", ["ps"])
"""

import logging
import os
import asyncio
from pathlib import Path
from typing import List, Optional, Dict, Any

# Setup logging
logger = logging.getLogger(__name__)

# Add parent paths for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.skills import (
    SkillRegistry,
    SkillExecutor,
    SkillExecutionResult,
)
from core.skills.self_healing import (
    SelfHealingSkillRegistry,
    ToolNotFoundError,
    SkillInstallError,
    QuotaExhaustedError,
    ApprovalRequiredError,
    RiskLevel,
    execute_with_healing,
)


# Jarvis-specific pre-authorized skills (CTO / Infra Guard role)
JARVIS_PRE_AUTHORIZED_SKILLS = [
    "linux-service-triage",
    "process-watch",
    "docker",
    "pm2",
    "npm-proxy",
    "git-ops",
    "file-watcher",
    "clawdbot-diagnostics",
    "log-analyzer",
    "network-trace",
    "echo",  # Basic test skill
]


class JarvisSkillHandler:
    """
    Skill handler for ClawdJarvis with self-healing capabilities.

    Integrates with the Jarvis Telegram bot to provide:
    - Skill execution with auto-installation
    - Pre-authorized skill list for Jarvis role
    - Configurable risk levels
    """

    def __init__(
        self,
        skills_dir: Optional[Path] = None,
        tools_md_path: Optional[Path] = None,
        install_log_path: Optional[Path] = None,
        enable_remote_search: bool = True,
    ):
        """
        Initialize the Jarvis skill handler.

        Args:
            skills_dir: Path to skills directory.
            tools_md_path: Path to TOOLS.md for documentation.
            install_log_path: Path to installation log.
            enable_remote_search: Whether to search skills.sh.
        """
        # Default paths
        project_root = Path(__file__).parent.parent.parent

        if skills_dir is None:
            skills_dir = project_root / "skills"

        if tools_md_path is None:
            tools_md_path = project_root / "TOOLS.md"

        if install_log_path is None:
            logs_dir = project_root / "logs"
            logs_dir.mkdir(exist_ok=True)
            install_log_path = logs_dir / "skill_installs.log"

        # Check environment for auto-install setting
        auto_install = os.environ.get("JARVIS_AUTO_SKILL_INSTALL", "true")
        self.auto_install_enabled = auto_install.lower() == "true"

        # Initialize self-healing registry
        self.registry = SelfHealingSkillRegistry(
            skills_dir=skills_dir,
            enable_remote_search=enable_remote_search,
            tools_md_path=tools_md_path,
            install_log_path=install_log_path,
            max_installs_per_session=3,
        )

        # Set Jarvis-specific pre-authorized skills
        self.registry.pre_authorized_skills = JARVIS_PRE_AUTHORIZED_SKILLS.copy()

        # Set risk level for Jarvis (MEDIUM allowed)
        self.registry.max_auto_install_risk = RiskLevel.MEDIUM

        # Initialize executor
        base_registry = SkillRegistry(skills_dir)
        base_registry.discover_skills()
        self.executor = SkillExecutor(base_registry, timeout=60)

        logger.info(
            f"JarvisSkillHandler initialized: "
            f"auto_install={self.auto_install_enabled}, "
            f"skills_dir={skills_dir}"
        )

    async def execute_skill(
        self,
        skill_name: str,
        args: List[str],
        env: Optional[Dict[str, str]] = None,
    ) -> SkillExecutionResult:
        """
        Execute a skill with self-healing.

        If the skill is missing:
        1. Search for it
        2. Install if pre-authorized
        3. Execute

        Args:
            skill_name: Name of the skill to execute.
            args: Arguments to pass to the skill.
            env: Environment variables for the skill.

        Returns:
            SkillExecutionResult with execution details.
        """
        # First try direct execution
        result = await self.executor.execute_async(skill_name, args, env)

        if result.success:
            return result

        # Check if it's a "not found" error
        if "not found" in (result.error or "").lower():
            logger.info(f"Skill '{skill_name}' not found. Attempting self-healing.")

            if not self.auto_install_enabled:
                return SkillExecutionResult(
                    success=False,
                    error=f"Skill '{skill_name}' not found. Auto-install disabled.",
                    exit_code=-1,
                )

            if not self.registry.can_auto_install():
                return SkillExecutionResult(
                    success=False,
                    error=f"Session quota exhausted. Cannot auto-install '{skill_name}'.",
                    exit_code=-1,
                )

            # Search for skill
            search_results = self.registry.search_skills(skill_name)

            if not search_results:
                return SkillExecutionResult(
                    success=False,
                    error=f"Skill '{skill_name}' not found in any registry.",
                    exit_code=-1,
                )

            # Check if pre-authorized
            skill_info = search_results[0]
            found_name = skill_info.get("name", skill_name)

            if not self.registry.is_pre_authorized(found_name):
                return SkillExecutionResult(
                    success=False,
                    error=f"Skill '{found_name}' requires approval. Not pre-authorized.",
                    exit_code=-1,
                )

            # Install skill
            source_path = skill_info.get("source_path")
            if source_path:
                source_path = Path(source_path)

            install_result = self.registry.install_skill(found_name, source=source_path)

            if not install_result.success:
                return SkillExecutionResult(
                    success=False,
                    error=f"Failed to install skill '{found_name}': {install_result.error}",
                    exit_code=-1,
                )

            # Verify installation
            if not self.registry.verify_skill(found_name):
                return SkillExecutionResult(
                    success=False,
                    error=f"Skill '{found_name}' installed but verification failed.",
                    exit_code=-1,
                )

            # Update TOOLS.md
            self.registry.update_tools_md(
                skill_name=found_name,
                description=skill_info.get("description", ""),
            )

            logger.info(f"Successfully installed skill '{found_name}'. Retrying execution.")

            # Refresh executor registry and retry
            self.executor.registry.discover_skills()
            return await self.executor.execute_async(skill_name, args, env)

        # Return original error if not a "not found" case
        return result

    def list_skills(self) -> List[str]:
        """List all available skills."""
        self.executor.registry.discover_skills()
        return self.executor.registry.list_skills()

    def list_pre_authorized(self) -> List[str]:
        """List pre-authorized skills for Jarvis."""
        return self.registry.pre_authorized_skills.copy()

    def get_status(self) -> Dict[str, Any]:
        """Get skill handler status."""
        return {
            "auto_install_enabled": self.auto_install_enabled,
            "session_installs": self.registry._session_install_count,
            "max_installs_per_session": self.registry.max_installs_per_session,
            "can_auto_install": self.registry.can_auto_install(),
            "available_skills": self.list_skills(),
            "pre_authorized_skills": self.list_pre_authorized(),
        }


# Singleton instance for the bot
_handler_instance: Optional[JarvisSkillHandler] = None


def get_skill_handler() -> JarvisSkillHandler:
    """Get or create the singleton skill handler instance."""
    global _handler_instance
    if _handler_instance is None:
        _handler_instance = JarvisSkillHandler()
    return _handler_instance
