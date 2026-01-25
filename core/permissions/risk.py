"""
Risk Assessor for Jarvis.

Analyzes commands to determine their risk level and whether they require approval.
"""

import logging
import re
from enum import Enum
from typing import List, Optional, Tuple, Union

logger = logging.getLogger(__name__)


class RiskLevel(Enum):
    """Risk levels for commands."""

    SAFE = "safe"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


# Pattern categories for risk assessment
CRITICAL_PATTERNS = [
    # Destructive file operations
    r"rm\s+-rf\s+/($|\s|\*)",  # rm -rf / or rm -rf /*
    r"rm\s+-rf\s+/\*",
    r"rm\s+-fr\s+/($|\s|\*)",
    r"rm\s+-rf\s+~/?(\*|$)",  # rm -rf ~/*
    # Git force operations
    r"git\s+push\s+(--force|-f)",
    r"git\s+push\s+.*(-f|--force)",
    # System destruction
    r"dd\s+if=.*/dev/",
    r"chmod\s+-R\s+777\s+/($|\s)",
    r":()\s*\{\s*:\|\:&\s*\}",  # Fork bomb
    r">\s*/etc/(passwd|shadow)",
    # Download and execute
    r"curl\s+.*\|\s*(sh|bash)",
    r"wget\s+.*\|\s*(sh|bash)",
    r"curl\s+.*-O\s*-\s*\|\s*(sh|bash)",
    r"wget\s+.*-O\s*-\s*\|\s*(sh|bash)",
    # With sudo prefix
    r"sudo\s+rm\s+-rf\s+/",
]

HIGH_PATTERNS = [
    # Git destructive operations
    r"git\s+reset\s+--hard",
    r"git\s+checkout\s+\.$",
    r"git\s+clean\s+-f",
    r"git\s+clean\s+-fd",
    r"git\s+push(?!\s+--force)(?!\s+-f)",  # git push without force (still high)
    # File deletion
    r"rm\s+(-[a-z]*r|-[a-z]*f)",  # rm with -r or -f flags
    r"rm\s+[^|]+$",  # Simple rm
    # Package removal
    r"pip\s+uninstall",
    r"npm\s+uninstall",
    r"npm\s+remove",
    # Docker operations
    r"docker\s+run",
    r"docker\s+stop",
    r"docker\s+rm",
    r"docker\s+kill",
]

MODERATE_PATTERNS = [
    # Git operations
    r"git\s+add",
    r"git\s+commit",
    r"git\s+stash",
    r"git\s+checkout\s+(?!\.)[\w/-]+",  # git checkout <branch>
    r"git\s+reset\s+--soft",
    r"git\s+merge",
    r"git\s+rebase",
    # File operations
    r"mkdir\s+",
    r"touch\s+",
    r"cp\s+",
    r"mv\s+",
    # Script execution
    r"python\s+\w+\.py",
    r"node\s+\w+\.js",
    r"bash\s+\w+\.sh",
    # Package installation
    r"pip\s+install",
    r"npm\s+install",
    r"npm\s+i\s+",
]

SAFE_PATTERNS = [
    # Read-only operations
    r"^ls",
    r"^cat\s+",
    r"^head\s+",
    r"^tail\s+",
    r"^less\s+",
    r"^more\s+",
    r"^pwd$",
    r"^echo\s+",
    r"^wc\s+",
    r"^grep\s+",
    r"^find\s+",
    # Git read-only
    r"git\s+status",
    r"git\s+log",
    r"git\s+diff",
    r"git\s+branch(?!\s+-[dD])",  # git branch without -d/-D
    r"git\s+show",
    r"git\s+blame",
    # Version checks
    r"python\s+--version",
    r"node\s+--version",
    r"npm\s+--version",
    r"pip\s+--version",
    r"pip\s+list",
    r"pip\s+show",
    r"npm\s+list",
    r"npm\s+show",
]


class RiskAssessor:
    """
    Assesses the risk level of commands.

    Uses pattern matching to classify commands into risk categories:
    - SAFE: Read operations, queries
    - MODERATE: Writes, modifications
    - HIGH: Deletions, system changes
    - CRITICAL: Irreversible operations
    """

    def __init__(self):
        """Initialize RiskAssessor with compiled patterns."""
        self._critical_patterns = [re.compile(p, re.IGNORECASE) for p in CRITICAL_PATTERNS]
        self._high_patterns = [re.compile(p, re.IGNORECASE) for p in HIGH_PATTERNS]
        self._moderate_patterns = [re.compile(p, re.IGNORECASE) for p in MODERATE_PATTERNS]
        self._safe_patterns = [re.compile(p, re.IGNORECASE) for p in SAFE_PATTERNS]

        # Risk descriptions
        self._descriptions = {
            "rm -rf /": "Will recursively delete all files from root",
            "git push --force": "Will overwrite remote history",
            "git reset --hard": "Will discard all uncommitted changes",
            "curl | sh": "Will download and execute untrusted code",
            "rm -r": "Will recursively delete files",
            "git push": "Will push changes to remote repository",
            "git checkout .": "Will discard all uncommitted file changes",
        }

    def assess_command(
        self, command: str, include_description: bool = False
    ) -> Union[RiskLevel, Tuple[RiskLevel, str]]:
        """
        Assess the risk level of a command.

        Args:
            command: The command to assess
            include_description: If True, return (risk_level, description) tuple

        Returns:
            RiskLevel or (RiskLevel, description) if include_description=True
        """
        # Empty command is safe
        if not command or not command.strip():
            if include_description:
                return RiskLevel.SAFE, "Empty command"
            return RiskLevel.SAFE

        command = command.strip()

        # Check for piped commands - assess each component
        if "|" in command:
            risk_level = self._assess_piped_command(command)
            if include_description:
                return risk_level, self._get_description(command, risk_level)
            return risk_level

        # Check sudo prefix - may escalate risk
        has_sudo = command.startswith("sudo ")
        base_command = command[5:] if has_sudo else command

        # Check patterns in order of severity
        risk_level = self._match_patterns(base_command)

        # Sudo escalation
        if has_sudo and risk_level in [RiskLevel.MODERATE, RiskLevel.HIGH]:
            risk_level = RiskLevel(min(risk_level.value, "high"))

        if include_description:
            return risk_level, self._get_description(command, risk_level)

        return risk_level

    def _match_patterns(self, command: str) -> RiskLevel:
        """Match command against pattern lists."""
        # Check critical first
        for pattern in self._critical_patterns:
            if pattern.search(command):
                return RiskLevel.CRITICAL

        # Check high risk
        for pattern in self._high_patterns:
            if pattern.search(command):
                return RiskLevel.HIGH

        # Check safe patterns (before moderate to catch read-only ops)
        for pattern in self._safe_patterns:
            if pattern.search(command):
                return RiskLevel.SAFE

        # Check moderate
        for pattern in self._moderate_patterns:
            if pattern.search(command):
                return RiskLevel.MODERATE

        # Default to moderate for unknown commands
        return RiskLevel.MODERATE

    def _assess_piped_command(self, command: str) -> RiskLevel:
        """Assess risk of piped commands (highest component wins)."""
        parts = [p.strip() for p in command.split("|")]

        # Check for download-and-execute patterns first
        command_lower = command.lower()
        if ("curl" in command_lower or "wget" in command_lower) and (
            "| sh" in command_lower or "| bash" in command_lower
        ):
            return RiskLevel.CRITICAL

        # Assess each component
        max_risk = RiskLevel.SAFE
        for part in parts:
            part_risk = self._match_patterns(part)
            if part_risk.value > max_risk.value:
                max_risk = part_risk

        return max_risk

    def _get_description(self, command: str, risk_level: RiskLevel) -> str:
        """Get description for command risk."""
        command_lower = command.lower()

        for key, desc in self._descriptions.items():
            if key in command_lower:
                return desc

        # Generic descriptions by risk level
        descriptions = {
            RiskLevel.SAFE: "Safe read-only operation",
            RiskLevel.MODERATE: "File or configuration modification",
            RiskLevel.HIGH: "Destructive operation that may cause data loss",
            RiskLevel.CRITICAL: "Highly destructive, potentially irreversible operation",
        }

        return descriptions.get(risk_level, "Unknown operation")

    def requires_approval(
        self, command: str, user_level: "PermissionLevel"
    ) -> bool:
        """
        Check if command requires approval for user's permission level.

        Args:
            command: The command to check
            user_level: User's permission level

        Returns:
            True if approval is required, False otherwise
        """
        from core.permissions.manager import PermissionLevel

        # Admin never needs approval
        if user_level == PermissionLevel.ADMIN:
            return False

        risk = self.assess_command(command)

        # CRITICAL always requires approval (except admin)
        if risk == RiskLevel.CRITICAL:
            return True

        # HIGH requires approval for BASIC and ELEVATED
        if risk == RiskLevel.HIGH:
            return user_level.value < PermissionLevel.ADMIN.value

        # MODERATE requires approval for BASIC
        if risk == RiskLevel.MODERATE:
            return user_level.value < PermissionLevel.ELEVATED.value

        # SAFE never requires approval
        return False


# Convenience function
def assess_command(command: str) -> RiskLevel:
    """Assess command risk level using default assessor."""
    return RiskAssessor().assess_command(command)
