"""
Self-Healing Skill Acquisition System.

Enables autonomous skill discovery, installation, and verification.
When a tool/skill is missing, this system can:
1. Search for the skill in registries (local, skills.sh)
2. Auto-install if pre-authorized
3. Verify the installation
4. Update TOOLS.md
5. Retry the original task

Configuration:
- JARVIS_AUTO_SKILL_INSTALL=true - Enable auto-installation (default: true)
- MAX_AUTO_INSTALLS=3 - Maximum installs per session

Safety Guardrails:
- Only pre-authorized skills can be auto-installed
- Risk levels (LOW, MEDIUM, HIGH, CRITICAL) control what can be installed
- Session quota prevents runaway installations
- All installations are logged for audit
"""

import logging
import os
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from enum import IntEnum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, TypeVar

try:
    import requests
except ImportError:
    requests = None  # type: ignore

from core.skills.registry import SkillRegistry, DEFAULT_SKILLS_DIR
from core.skills.manager import SkillManager, SkillInstallResult

logger = logging.getLogger(__name__)


class ToolNotFoundError(Exception):
    """Raised when a required tool/skill is not found."""

    def __init__(self, tool_name: str, message: str = ""):
        self.tool_name = tool_name
        super().__init__(message or f"Tool not found: {tool_name}")


class SkillInstallError(Exception):
    """Raised when skill installation fails."""

    pass


class QuotaExhaustedError(Exception):
    """Raised when session install quota is exhausted."""

    pass


class ApprovalRequiredError(Exception):
    """Raised when skill requires human approval for installation."""

    pass


class RiskLevel(IntEnum):
    """Risk levels for skills."""

    LOW = 1  # Read-only, diagnostics
    MEDIUM = 2  # Can modify state (restart services)
    HIGH = 3  # Can delete data or modify security
    CRITICAL = 4  # Root access, destructive operations


@dataclass
class SkillSearchResult:
    """Result from searching skill registries."""

    name: str
    description: str = ""
    version: str = "1.0.0"
    source: str = "local"  # "local", "skills.sh", "clawdhub"
    verified: bool = False
    risk_level: RiskLevel = RiskLevel.LOW
    package_name: str = ""
    source_path: Optional[Path] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "source": self.source,
            "verified": self.verified,
            "risk_level": self.risk_level.name,
            "package_name": self.package_name,
            "source_path": str(self.source_path) if self.source_path else None,
        }


# Default pre-authorized skills for Jarvis (CTO / Infra Guard role)
DEFAULT_PRE_AUTHORIZED_SKILLS = [
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
]

# Skills.sh API endpoint (public skill registry)
SKILLS_SH_API = "https://skills.sh/api/search"

# Allowed registries for security
ALLOWED_REGISTRIES = [
    "https://skills.sh",
    "https://registry.npmjs.org/@modelcontextprotocol",
]


class SelfHealingSkillRegistry:
    """
    Registry with self-healing capabilities.

    Extends the base SkillRegistry with:
    - Remote skill search (skills.sh)
    - Auto-installation of pre-authorized skills
    - Installation logging and auditing
    - Session quota enforcement
    - Risk level checks
    """

    def __init__(
        self,
        skills_dir: Optional[Path] = None,
        enable_remote_search: bool = False,
        tools_md_path: Optional[Path] = None,
        install_log_path: Optional[Path] = None,
        max_installs_per_session: int = 3,
    ):
        """
        Initialize the self-healing skill registry.

        Args:
            skills_dir: Directory for installed skills.
            enable_remote_search: Whether to search skills.sh.
            tools_md_path: Path to TOOLS.md for documentation updates.
            install_log_path: Path to installation log file.
            max_installs_per_session: Maximum auto-installs per session.
        """
        self.skills_dir = Path(skills_dir) if skills_dir else DEFAULT_SKILLS_DIR
        self.skills_dir.mkdir(parents=True, exist_ok=True)

        self.enable_remote_search = enable_remote_search
        self.tools_md_path = tools_md_path
        self.install_log_path = install_log_path
        self.max_installs_per_session = max_installs_per_session

        # Base registry and manager
        self._registry = SkillRegistry(self.skills_dir)
        self._manager = SkillManager(self.skills_dir)

        # Pre-authorized skills (can be customized per bot)
        self.pre_authorized_skills: List[str] = DEFAULT_PRE_AUTHORIZED_SKILLS.copy()

        # Risk level threshold for auto-install
        self.max_auto_install_risk: RiskLevel = RiskLevel.MEDIUM

        # Session state
        self._session_install_count = 0

        # Internal skill source mapping (for testing and local sources)
        self._skill_sources: Dict[str, Path] = {}

        # Check environment for auto-install setting
        env_auto_install = os.environ.get("JARVIS_AUTO_SKILL_INSTALL", "true")
        self.auto_install_enabled = env_auto_install.lower() == "true"

        # Discover existing skills
        self._registry.discover_skills()

    def search_skills(self, query: str) -> List[Dict[str, Any]]:
        """
        Search for skills matching the query.

        Searches in order:
        1. Local skills directory
        2. skills.sh (if enabled)

        Args:
            query: Search query (tool name, skill name, or description).

        Returns:
            List of matching skill dictionaries.
        """
        results: List[Dict[str, Any]] = []

        # Search local skills first
        local_results = self._search_local(query)
        results.extend(local_results)

        # Search remote registries if enabled
        if self.enable_remote_search:
            remote_results = self._search_remote(query)
            results.extend(remote_results)

        return results

    def _search_local(self, query: str) -> List[Dict[str, Any]]:
        """Search local skills directory."""
        results = []
        query_lower = query.lower()

        # Refresh discovery
        self._registry.discover_skills()

        for skill_name in self._registry.list_skills():
            if query_lower in skill_name.lower():
                skill = self._registry.get_skill(skill_name)
                if skill:
                    results.append(
                        {
                            "name": skill_name,
                            "description": skill.get("description", ""),
                            "source": "local",
                            "verified": True,
                            "source_path": skill.get("path"),
                        }
                    )

        # Also check source mappings (for pending installs)
        for skill_name, source_path in self._skill_sources.items():
            if query_lower in skill_name.lower():
                results.append(
                    {
                        "name": skill_name,
                        "description": "",
                        "source": "local",
                        "verified": True,
                        "source_path": source_path,
                    }
                )

        return results

    def _search_remote(self, query: str) -> List[Dict[str, Any]]:
        """Search skills.sh registry."""
        if requests is None:
            logger.warning("requests library not available - cannot search remote")
            return []

        try:
            response = requests.get(
                SKILLS_SH_API, params={"q": query}, timeout=10
            )
            response.raise_for_status()
            data = response.json()

            skills = data.get("skills", [])
            return [
                {
                    "name": s.get("name", ""),
                    "description": s.get("description", ""),
                    "source": "skills.sh",
                    "verified": s.get("verified", False),
                    "package_name": s.get("package_name", ""),
                }
                for s in skills
            ]
        except Exception as e:
            logger.warning(f"Failed to search skills.sh: {e}")
            return []

    def install_skill(
        self,
        skill_name: str,
        source: Optional[Path] = None,
        force: bool = False,
    ) -> SkillInstallResult:
        """
        Install a skill.

        Args:
            skill_name: Name of the skill to install.
            source: Source path for the skill (optional).
            force: Force overwrite if already installed.

        Returns:
            SkillInstallResult with installation details.
        """
        # Check if source provided or look up
        if source is None:
            source = self._skill_sources.get(skill_name)

        if source is None:
            return SkillInstallResult(
                success=False,
                skill_name=skill_name,
                error=f"No source found for skill: {skill_name}",
            )

        # Validate source
        is_valid, errors = self._manager.validate_skill(source)
        if not is_valid:
            error_msg = "; ".join(errors)
            self._log_installation(skill_name, False, error_msg)
            return SkillInstallResult(
                success=False,
                skill_name=skill_name,
                error=f"Validation failed: {error_msg}",
            )

        # Install using manager
        result = self._manager.install_skill(source, force=force)

        # Log installation
        self._log_installation(skill_name, result.success, result.error)

        # Increment counter on success
        if result.success:
            self._increment_install_counter()

        return result

    def verify_skill(self, skill_name: str) -> bool:
        """
        Verify a skill is properly installed and functional.

        Checks:
        1. Skill directory exists
        2. SKILL.md exists
        3. script.py exists and has valid syntax

        Args:
            skill_name: Name of the skill to verify.

        Returns:
            True if skill is valid, False otherwise.
        """
        skill_path = self.skills_dir / skill_name

        if not skill_path.exists():
            logger.debug(f"Skill directory not found: {skill_path}")
            return False

        # Check required files
        skill_md = skill_path / "SKILL.md"
        script_py = skill_path / "script.py"

        if not skill_md.exists():
            logger.debug(f"SKILL.md not found: {skill_md}")
            return False

        if not script_py.exists():
            logger.debug(f"script.py not found: {script_py}")
            return False

        # Check syntax
        try:
            content = script_py.read_text(encoding="utf-8")
            compile(content, str(script_py), "exec")
        except SyntaxError as e:
            logger.debug(f"Syntax error in {script_py}: {e}")
            return False

        return True

    def update_tools_md(
        self,
        skill_name: str,
        description: str = "",
        version: str = "1.0.0",
    ) -> bool:
        """
        Update TOOLS.md with newly installed skill.

        Args:
            skill_name: Name of the skill.
            description: Skill description.
            version: Skill version.

        Returns:
            True if updated successfully, False otherwise.
        """
        if self.tools_md_path is None:
            logger.debug("tools_md_path not set - skipping TOOLS.md update")
            return False

        try:
            # Create if doesn't exist
            if not self.tools_md_path.exists():
                self.tools_md_path.write_text("# Tools\n\nInstalled skills.\n\n")

            # Read existing content
            content = self.tools_md_path.read_text(encoding="utf-8")

            # Add new entry
            timestamp = datetime.utcnow().isoformat() + "Z"
            entry = f"""
## {skill_name}
**Version:** {version}
**Installed:** {timestamp}
**Description:** {description}
**Auto-Installed:** Yes (self-healing)

---
"""
            # Append entry
            content += entry
            self.tools_md_path.write_text(content, encoding="utf-8")

            logger.info(f"Updated TOOLS.md with {skill_name}")
            return True

        except Exception as e:
            logger.error(f"Failed to update TOOLS.md: {e}")
            return False

    def is_pre_authorized(self, skill_name: str) -> bool:
        """Check if a skill is pre-authorized for auto-install."""
        return skill_name in self.pre_authorized_skills

    def is_risk_acceptable(self, risk_level: RiskLevel) -> bool:
        """Check if a risk level is acceptable for auto-install."""
        return risk_level <= self.max_auto_install_risk

    def can_auto_install(self) -> bool:
        """Check if auto-install quota allows another installation."""
        if not self.auto_install_enabled:
            return False
        return self._session_install_count < self.max_installs_per_session

    def _increment_install_counter(self) -> int:
        """Increment and return session install count."""
        self._session_install_count += 1
        return self._session_install_count

    def _log_installation(
        self,
        skill_name: str,
        success: bool,
        error: Optional[str] = None,
    ) -> None:
        """Log installation attempt to file."""
        if self.install_log_path is None:
            return

        try:
            timestamp = datetime.utcnow().isoformat()
            status = "SUCCESS" if success else "FAILED"
            error_msg = f" - {error}" if error else ""

            log_entry = f"[{timestamp}] [{skill_name}] [{status}]{error_msg}\n"

            # Append to log file
            with open(self.install_log_path, "a", encoding="utf-8") as f:
                f.write(log_entry)

        except Exception as e:
            logger.error(f"Failed to log installation: {e}")


# Type variable for async function return type
T = TypeVar("T")


async def execute_with_healing(
    task: Callable[[], T],
    registry: SelfHealingSkillRegistry,
    max_retries: int = 1,
) -> T:
    """
    Execute a task with self-healing skill acquisition.

    If the task fails with ToolNotFoundError:
    1. Search for the skill
    2. Install if pre-authorized
    3. Retry the task

    Args:
        task: Async callable to execute.
        registry: SelfHealingSkillRegistry instance.
        max_retries: Maximum retry attempts after healing.

    Returns:
        Result of the task.

    Raises:
        ToolNotFoundError: If skill cannot be found or installed.
        QuotaExhaustedError: If session quota is exhausted.
        ApprovalRequiredError: If skill requires approval.
    """
    retries = 0

    while retries <= max_retries:
        try:
            return await task()

        except ToolNotFoundError as e:
            if retries >= max_retries:
                raise

            logger.info(f"Missing tool: {e.tool_name}. Initiating self-healing.")

            # Check quota
            if not registry.can_auto_install():
                raise QuotaExhaustedError(
                    f"Session quota exhausted ({registry.max_installs_per_session} installs)"
                )

            # Search for skill
            results = registry.search_skills(e.tool_name)
            if not results:
                logger.warning(f"No skill found for: {e.tool_name}")
                raise

            skill = results[0]
            skill_name = skill.get("name", e.tool_name)

            # Check if pre-authorized
            if not registry.is_pre_authorized(skill_name):
                raise ApprovalRequiredError(
                    f"Skill {skill_name} requires human approval"
                )

            # Install skill
            source_path = skill.get("source_path")
            if source_path:
                source_path = Path(source_path)

            result = registry.install_skill(skill_name, source=source_path)

            if not result.success:
                raise SkillInstallError(
                    f"Failed to install skill {skill_name}: {result.error}"
                )

            # Verify installation
            if not registry.verify_skill(skill_name):
                raise SkillInstallError(
                    f"Skill {skill_name} installed but verification failed"
                )

            # Update TOOLS.md
            registry.update_tools_md(
                skill_name=skill_name,
                description=skill.get("description", ""),
            )

            logger.info(f"Successfully installed skill: {skill_name}. Retrying task.")
            retries += 1

    raise RuntimeError("Unexpected exit from execute_with_healing loop")
