"""
Dangerous Command Filtering for ClawdBots

Blocks shell injection patterns in user messages before they reach
command execution handlers (especially Jarvis skill/computer control).
"""

import logging
import re
from typing import Tuple

logger = logging.getLogger(__name__)

# Dangerous command patterns (case-insensitive)
DANGEROUS_PATTERNS = [
    (r"rm\s+-rf\s+/", "Recursive delete of root filesystem"),
    (r"rm\s+-rf\s+~", "Recursive delete of home directory"),
    (r"rm\s+-rf\s+\.", "Recursive delete of current directory"),
    (r"chmod\s+777", "Setting world-writable permissions"),
    (r"curl\s+.*\|\s*(?:ba)?sh", "Piping remote script to shell"),
    (r"wget\s+.*\|\s*sh", "Piping remote script to shell"),
    (r"dd\s+if=", "Direct disk write (dd)"),
    (r"mkfs\.", "Filesystem format command"),
    (r":\(\)\{\s*:\|:&\s*\};:", "Fork bomb"),
    (r">\s*/dev/sd[a-z]", "Direct write to block device"),
    (r"/etc/passwd", "Access to password file"),
    (r"/etc/shadow", "Access to shadow file"),
    (r"nc\s+-[le]", "Netcat listener (reverse shell)"),
    (r"python\s+-c\s+.*import\s+os", "Python OS command injection"),
    (r"eval\s*\(", "Eval injection"),
    (r"\bsudo\s+rm\b", "Sudo delete"),
]

# Compile patterns for performance
_compiled_patterns = [
    (re.compile(pattern, re.IGNORECASE), reason)
    for pattern, reason in DANGEROUS_PATTERNS
]


def is_dangerous_command(text: str) -> Tuple[bool, str]:
    """
    Check if text contains dangerous shell command patterns.

    Returns:
        (blocked, reason) - True and reason if dangerous, (False, "") if safe.
    """
    if not text:
        return False, ""

    for pattern, reason in _compiled_patterns:
        if pattern.search(text):
            logger.warning(f"Blocked dangerous command pattern: {reason} in: {text[:100]}")
            return True, reason

    return False, ""
