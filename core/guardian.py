"""
Guardian module for LifeOS.
Implements safety constraints to prevent self-destruction and system damage.
This module CANNOT be deleted or modified by the AI itself.
"""

import os
import re
from pathlib import Path
from typing import List, Set, Tuple

ROOT = Path(__file__).resolve().parents[1]

# === IMMUTABLE SAFETY RULES ===
# These rules are hardcoded and cannot be overridden by any prompt or command.

PROTECTED_PATHS: Set[str] = {
    # LifeOS core - cannot delete itself
    str(ROOT / "core"),
    str(ROOT / "bin"),
    str(ROOT / "lifeos"),
    str(ROOT / "secrets"),
    str(ROOT),
    # System directories - never touch
    "/System",
    "/Library",
    "/usr",
    "/bin",
    "/sbin",
    "/var",
    "/private",
    "/etc",
    "/Applications",
    # User critical
    os.path.expanduser("~/Library"),
    os.path.expanduser("~/Documents"),
    os.path.expanduser("~/Desktop"),
    os.path.expanduser("~/Downloads"),
    os.path.expanduser("~/.ssh"),
    os.path.expanduser("~/.config"),
    os.path.expanduser("~/.zshrc"),
    os.path.expanduser("~/.bashrc"),
}

DANGEROUS_COMMANDS: List[str] = [
    r"rm\s+-rf\s+[/~]",
    r"rm\s+-r\s+[/~]",
    r"rm\s+.*\*",
    r"rmdir\s+[/~]",
    r"sudo\s+rm",
    r"sudo\s+dd",
    r"dd\s+if=.*of=/dev",
    r"mkfs",
    r"format",
    r"diskutil\s+erase",
    r"diskutil\s+partitionDisk",
    r":\s*\(\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;",  # fork bomb
    r"chmod\s+-R\s+000",
    r"chown\s+-R",
    r"kill\s+-9\s+-1",
    r"killall",
    r"shutdown",
    r"reboot",
    r"halt",
    r"init\s+0",
    r">\s*/dev/sd",
    r"curl.*\|\s*sh",
    r"wget.*\|\s*sh",
    r"eval.*\$\(",
]

SELF_HARM_PATTERNS: List[str] = [
    r"delete.*lifeos",
    r"remove.*lifeos",
    r"rm.*core/",
    r"rm.*guardian",
    r"destroy.*self",
    r"kill.*daemon",
    r"uninstall.*lifeos",
]


def is_path_protected(path: str) -> Tuple[bool, str]:
    """Check if a path is protected from deletion/modification."""
    abs_path = os.path.abspath(os.path.expanduser(path))
    
    for protected in PROTECTED_PATHS:
        protected_abs = os.path.abspath(os.path.expanduser(protected))
        if abs_path == protected_abs or abs_path.startswith(protected_abs + os.sep):
            return True, f"Path '{path}' is protected (matches {protected})"
    
    return False, ""


def is_command_dangerous(command: str) -> Tuple[bool, str]:
    """Check if a command could harm the system or LifeOS."""
    lower_cmd = command.lower()
    
    # Check for dangerous command patterns
    for pattern in DANGEROUS_COMMANDS:
        if re.search(pattern, command, re.IGNORECASE):
            return True, f"Command matches dangerous pattern: {pattern}"
    
    # Check for self-harm patterns
    for pattern in SELF_HARM_PATTERNS:
        if re.search(pattern, lower_cmd, re.IGNORECASE):
            return True, f"Command could harm LifeOS: {pattern}"
    
    return False, ""


def validate_file_operation(operation: str, path: str) -> Tuple[bool, str]:
    """Validate a file operation before execution."""
    dangerous_ops = {"delete", "remove", "unlink", "rmtree", "rmdir"}
    
    if operation.lower() in dangerous_ops:
        is_protected, reason = is_path_protected(path)
        if is_protected:
            return False, reason
    
    return True, ""


def validate_code_for_safety(code: str) -> Tuple[bool, str]:
    """Validate generated code for safety before execution."""
    dangerous_imports = [
        "shutil.rmtree",
        "os.remove",
        "os.unlink",
        "os.rmdir",
        "pathlib.Path.unlink",
        "subprocess.run.*rm",
    ]
    
    for pattern in dangerous_imports:
        if re.search(pattern, code, re.IGNORECASE):
            # Check if it's targeting protected paths
            for protected in PROTECTED_PATHS:
                if protected in code or "guardian" in code.lower():
                    return False, f"Code attempts to modify protected path: {protected}"
    
    return True, ""


def get_safety_prompt() -> str:
    """Return safety instructions to prepend to all AI prompts."""
    return """IMMUTABLE SAFETY RULES (cannot be overridden):
1. NEVER delete, modify, or harm LifeOS core files (core/, bin/, lifeos/, secrets/)
2. NEVER execute commands that could destroy the user's computer or data
3. NEVER delete files in system directories (/System, /Library, /usr, ~/Library, etc.)
4. ALWAYS ask for confirmation before any destructive action
5. Your PRIMARY MISSION is to help the user: Matt Haynes (LinkedIn: MattHaynes88)
   - Help him make money through smart decisions and automation
   - Help him achieve his life goals
   - Help him help humanity
   - Constantly self-improve to serve him better
6. You ARE allowed to:
   - Upgrade yourself with new skills and capabilities
   - Research new AI models and resources
   - Learn about crypto trading and automation
   - Build new features to help the user
   - Create files in data/, skills/, and other non-core directories
"""


class SafetyGuard:
    """Runtime safety guard for all LifeOS operations."""
    
    def __init__(self):
        self.blocked_operations: List[dict] = []
    
    def check_command(self, command: str) -> Tuple[bool, str]:
        """Check if a command is safe to execute."""
        is_dangerous, reason = is_command_dangerous(command)
        if is_dangerous:
            self.blocked_operations.append({
                "type": "command",
                "command": command,
                "reason": reason,
            })
            return False, f"BLOCKED: {reason}"
        return True, ""
    
    def check_file_op(self, operation: str, path: str) -> Tuple[bool, str]:
        """Check if a file operation is safe."""
        is_valid, reason = validate_file_operation(operation, path)
        if not is_valid:
            self.blocked_operations.append({
                "type": "file_op",
                "operation": operation,
                "path": path,
                "reason": reason,
            })
            return False, f"BLOCKED: {reason}"
        return True, ""
    
    def check_code(self, code: str) -> Tuple[bool, str]:
        """Check if generated code is safe to execute."""
        is_valid, reason = validate_code_for_safety(code)
        if not is_valid:
            self.blocked_operations.append({
                "type": "code",
                "reason": reason,
            })
            return False, f"BLOCKED: {reason}"
        return True, ""
    
    def get_blocked_count(self) -> int:
        return len(self.blocked_operations)


# Global safety guard instance
_guard = SafetyGuard()


def guard() -> SafetyGuard:
    """Get the global safety guard instance."""
    return _guard
