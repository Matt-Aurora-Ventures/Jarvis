"""
Security Utilities for ClawdBots

Provides security functions for the multi-agent ClawdBot system:
- Admin whitelist management
- Input sanitization
- Prompt injection detection
- Security event logging

File locations (on VPS):
- Admin whitelist: /root/clawdbots/admins.json
- Security log: /root/clawdbots/security_log.json
"""

import html
import json
import logging
import os
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)


class SecurityEventType(str, Enum):
    """Types of security events."""
    INJECTION_ATTEMPT = "injection_attempt"
    UNAUTHORIZED_ACCESS = "unauthorized_access"
    INPUT_SANITIZED = "input_sanitized"
    ADMIN_ADDED = "admin_added"
    ADMIN_REMOVED = "admin_removed"
    RATE_LIMITED = "rate_limited"
    PERMISSION_DENIED = "permission_denied"
    SUSPICIOUS_PATTERN = "suspicious_pattern"


@dataclass
class SanitizationResult:
    """Result of input sanitization."""
    cleaned_text: str
    was_modified: bool
    modifications: List[str] = field(default_factory=list)
    original_length: int = 0
    truncated: bool = False


class SecurityManager:
    """
    Manages security for ClawdBots.

    Handles:
    - Admin whitelist (who can perform admin actions)
    - Input sanitization (remove dangerous characters)
    - Prompt injection detection
    - Security event logging
    """

    # Default file locations (VPS paths)
    DEFAULT_ADMIN_FILE = "/root/clawdbots/admins.json"
    DEFAULT_LOG_FILE = "/root/clawdbots/security_log.json"

    # Default max input length
    DEFAULT_MAX_LENGTH = 10000

    # Prompt injection patterns (case-insensitive)
    INJECTION_PATTERNS = [
        # Instruction override attempts
        r"ignore\s+(?:all\s+)?(?:previous|above|prior)\s+instructions?",
        r"disregard\s+(?:all\s+)?(?:previous|above|prior)",
        r"forget\s+(?:all\s+)?(?:everything|what|previous)",
        r"new\s+instructions?\s*:",

        # Role manipulation
        r"you\s+are\s+now\s+(?:a|an|the)",
        r"act\s+as\s+(?:a|an|if)",
        r"pretend\s+(?:to\s+be|you\s+are)",

        # System prompt injection
        r"system\s*:\s*",
        r"assistant\s*:\s*",
        r"```\s*system\b",

        # Delimiter injection
        r"\[INST\]",
        r"<\|im_start\|>",
        r"<\|im_end\|>",
        r"<<SYS>>",
        r"<</SYS>>",

        # Jailbreak attempts
        r"do\s+anything\s+now",
        r"dan\s+mode",
        r"developer\s+mode",
        r"jailbreak",
    ]

    # Control characters to remove (keep newline \n and tab \t)
    CONTROL_CHAR_PATTERN = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]')

    def __init__(
        self,
        admin_file: Optional[str] = None,
        log_file: Optional[str] = None,
        max_log_size: int = 10000,
    ):
        """
        Initialize security manager.

        Args:
            admin_file: Path to admin whitelist JSON file
            log_file: Path to security log JSON file
            max_log_size: Maximum number of log entries to keep
        """
        self.admin_file = admin_file or self.DEFAULT_ADMIN_FILE
        self.log_file = log_file or self.DEFAULT_LOG_FILE
        self.max_log_size = max_log_size

        # Compile injection patterns for performance
        self._injection_patterns = [
            re.compile(pattern, re.IGNORECASE)
            for pattern in self.INJECTION_PATTERNS
        ]

        # Initialize files
        self._init_admin_file()
        self._init_log_file()

    def _init_admin_file(self) -> None:
        """Initialize admin whitelist file if it doesn't exist."""
        try:
            path = Path(self.admin_file)
            path.parent.mkdir(parents=True, exist_ok=True)

            if not path.exists():
                self._save_admins([])
            else:
                # Validate existing file
                self._load_admins()
        except Exception as e:
            logger.warning(f"Error initializing admin file: {e}")

    def _init_log_file(self) -> None:
        """Initialize security log file if it doesn't exist."""
        try:
            path = Path(self.log_file)
            path.parent.mkdir(parents=True, exist_ok=True)

            if not path.exists():
                self._save_log([])
        except Exception as e:
            logger.warning(f"Error initializing log file: {e}")

    def _load_admins(self) -> List[Union[int, str]]:
        """Load admin list from file."""
        try:
            with open(self.admin_file, 'r') as f:
                data = json.load(f)
                return data.get("admins", [])
        except (json.JSONDecodeError, FileNotFoundError, KeyError) as e:
            logger.warning(f"Error loading admins: {e}")
            return []

    def _save_admins(self, admins: List[Union[int, str]]) -> None:
        """Save admin list to file."""
        try:
            with open(self.admin_file, 'w') as f:
                json.dump({"admins": admins}, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving admins: {e}")

    def _load_log(self) -> List[Dict[str, Any]]:
        """Load security log from file."""
        try:
            with open(self.log_file, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError) as e:
            logger.debug(f"No existing log file: {e}")
            return []

    def _save_log(self, log: List[Dict[str, Any]]) -> None:
        """Save security log to file."""
        try:
            with open(self.log_file, 'w') as f:
                json.dump(log, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving log: {e}")

    # ==================== Admin Management ====================

    def is_admin(self, user_id: Union[int, str]) -> bool:
        """
        Check if a user is an admin.

        Args:
            user_id: User ID to check (int or string)

        Returns:
            True if user is in admin whitelist
        """
        admins = self._load_admins()
        return user_id in admins

    def add_admin(self, user_id: Union[int, str]) -> bool:
        """
        Add a user to the admin whitelist.

        Args:
            user_id: User ID to add

        Returns:
            True if successfully added
        """
        admins = self._load_admins()

        if user_id in admins:
            return True  # Already an admin

        admins.append(user_id)
        self._save_admins(admins)

        # Log the event
        self.log_security_event(
            event_type=SecurityEventType.ADMIN_ADDED,
            details={"user_id": user_id},
        )

        logger.info(f"Added admin: {user_id}")
        return True

    def remove_admin(self, user_id: Union[int, str]) -> bool:
        """
        Remove a user from the admin whitelist.

        Args:
            user_id: User ID to remove

        Returns:
            True if successfully removed, False if not found
        """
        admins = self._load_admins()

        if user_id not in admins:
            return False

        admins.remove(user_id)
        self._save_admins(admins)

        # Log the event
        self.log_security_event(
            event_type=SecurityEventType.ADMIN_REMOVED,
            details={"user_id": user_id},
        )

        logger.info(f"Removed admin: {user_id}")
        return True

    def get_admins(self) -> List[Union[int, str]]:
        """Get list of all admin user IDs."""
        return self._load_admins()

    # ==================== Input Sanitization ====================

    def sanitize_input(
        self,
        text: Optional[str],
        max_length: int = DEFAULT_MAX_LENGTH,
        escape_html_chars: bool = True,
    ) -> SanitizationResult:
        """
        Sanitize user input for safe processing.

        Performs:
        - Remove control characters (except newline/tab)
        - Escape HTML special characters
        - Enforce length limit

        Args:
            text: Input text to sanitize
            max_length: Maximum allowed length
            escape_html_chars: Whether to escape HTML characters

        Returns:
            SanitizationResult with cleaned text and metadata
        """
        # Handle None/empty input
        if text is None:
            return SanitizationResult(
                cleaned_text="",
                was_modified=False,
                original_length=0,
            )

        if text == "":
            return SanitizationResult(
                cleaned_text="",
                was_modified=False,
                original_length=0,
            )

        original = text
        original_length = len(text)
        modifications = []

        # Remove control characters
        cleaned = self.CONTROL_CHAR_PATTERN.sub('', text)
        if cleaned != text:
            modifications.append("removed_control_chars")
            text = cleaned

        # Escape HTML characters
        if escape_html_chars:
            escaped = html.escape(text)
            if escaped != text:
                modifications.append("escaped_html")
                text = escaped

        # Enforce length limit
        truncated = False
        if len(text) > max_length:
            text = text[:max_length]
            modifications.append("truncated")
            truncated = True

        was_modified = len(modifications) > 0

        return SanitizationResult(
            cleaned_text=text,
            was_modified=was_modified,
            modifications=modifications,
            original_length=original_length,
            truncated=truncated,
        )

    # ==================== Injection Detection ====================

    def detect_injection(self, text: str) -> bool:
        """
        Detect potential prompt injection attempts.

        Checks for patterns like:
        - "ignore previous instructions"
        - "you are now"
        - System prompt overrides
        - Delimiter injection

        Args:
            text: Text to analyze

        Returns:
            True if suspicious patterns detected
        """
        if not text:
            return False

        # Check each pattern
        for pattern in self._injection_patterns:
            if pattern.search(text):
                logger.warning(f"Potential injection detected: {text[:100]}...")
                return True

        return False

    # ==================== Security Logging ====================

    def log_security_event(
        self,
        event_type: SecurityEventType,
        details: Dict[str, Any],
        user_id: Optional[Union[int, str]] = None,
    ) -> None:
        """
        Log a security event.

        Args:
            event_type: Type of security event
            details: Additional event details
            user_id: User associated with event (if any)
        """
        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type.value,
            "details": details,
        }

        if user_id is not None:
            event["user_id"] = user_id

        # Load existing log
        log = self._load_log()

        # Add new event
        log.append(event)

        # Trim if exceeding max size
        if len(log) > self.max_log_size:
            log = log[-self.max_log_size:]

        # Save
        self._save_log(log)

    def get_security_log(
        self,
        limit: int = 100,
        event_type: Optional[SecurityEventType] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get recent security events.

        Args:
            limit: Maximum number of events to return
            event_type: Filter by event type (optional)

        Returns:
            List of security events, most recent first
        """
        log = self._load_log()

        # Filter by event type if specified
        if event_type is not None:
            log = [e for e in log if e.get("event_type") == event_type.value]

        # Return most recent first
        log.reverse()

        return log[:limit]


# ==================== Global Instance ====================

_security_manager: Optional[SecurityManager] = None


def get_security_manager() -> SecurityManager:
    """Get or create the global security manager instance."""
    global _security_manager
    if _security_manager is None:
        _security_manager = SecurityManager()
    return _security_manager


# ==================== Convenience Functions ====================

def is_admin(user_id: Union[int, str]) -> bool:
    """Check if a user is an admin."""
    return get_security_manager().is_admin(user_id)


def sanitize_input(
    text: Optional[str],
    max_length: int = SecurityManager.DEFAULT_MAX_LENGTH,
) -> str:
    """
    Sanitize user input and return cleaned text.

    For more details, use SecurityManager.sanitize_input() directly.
    """
    result = get_security_manager().sanitize_input(text, max_length=max_length)
    return result.cleaned_text


def detect_injection(text: str) -> bool:
    """Detect potential prompt injection attempts."""
    return get_security_manager().detect_injection(text)


def add_admin(user_id: Union[int, str]) -> bool:
    """Add a user to the admin whitelist."""
    return get_security_manager().add_admin(user_id)


def remove_admin(user_id: Union[int, str]) -> bool:
    """Remove a user from the admin whitelist."""
    return get_security_manager().remove_admin(user_id)


def log_security_event(
    event_type: SecurityEventType,
    details: Dict[str, Any],
    user_id: Optional[Union[int, str]] = None,
) -> None:
    """Log a security event."""
    get_security_manager().log_security_event(event_type, details, user_id)


def get_security_log(limit: int = 100) -> List[Dict[str, Any]]:
    """Get recent security events."""
    return get_security_manager().get_security_log(limit=limit)
