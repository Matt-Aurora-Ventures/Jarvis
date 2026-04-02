"""
User-Friendly Error Handler.

Provides clear, helpful error messages with recovery suggestions.
"""

import logging
import re
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)


class ErrorCategory(Enum):
    """Categories of errors for appropriate handling."""
    TOKEN_NOT_FOUND = "token_not_found"
    API_ERROR = "api_error"
    RATE_LIMITED = "rate_limited"
    INVALID_INPUT = "invalid_input"
    PERMISSION_DENIED = "permission_denied"
    NETWORK_ERROR = "network_error"
    TIMEOUT = "timeout"
    INTERNAL = "internal"
    MAINTENANCE = "maintenance"


@dataclass
class FriendlyError:
    """A user-friendly error with suggestions."""
    emoji: str
    title: str
    message: str
    suggestions: list
    retry_after: Optional[int] = None  # seconds


# Error message templates
ERROR_TEMPLATES: Dict[ErrorCategory, FriendlyError] = {
    ErrorCategory.TOKEN_NOT_FOUND: FriendlyError(
        emoji="\U0001f50d",
        title="Token Not Found",
        message="I couldn't find info for that token.",
        suggestions=[
            "Double-check the token symbol or address",
            "Try `/analyze SOL` for common tokens",
            "Paste the full contract address from Solscan",
        ],
    ),
    ErrorCategory.API_ERROR: FriendlyError(
        emoji="\U0001f6e0\ufe0f",
        title="Data Unavailable",
        message="I'm having trouble reaching the market data.",
        suggestions=[
            "Please try again in 30 seconds",
            "Check if the token is on Solana mainnet",
            "Run `/status` to check data sources",
        ],
        retry_after=30,
    ),
    ErrorCategory.RATE_LIMITED: FriendlyError(
        emoji="\u23f0",
        title="Rate Limited",
        message="Too many requests. Taking a breather.",
        suggestions=[
            "Wait a minute before trying again",
            "Use `/costs` to check your usage",
        ],
        retry_after=60,
    ),
    ErrorCategory.INVALID_INPUT: FriendlyError(
        emoji="\U0001f4dd",
        title="Invalid Input",
        message="I didn't quite understand that.",
        suggestions=[
            "Check the command format with `/help`",
            "Token addresses should be 32-44 characters",
            "Amounts should be numbers only",
        ],
    ),
    ErrorCategory.PERMISSION_DENIED: FriendlyError(
        emoji="\U0001f512",
        title="Permission Denied",
        message="You don't have access to this command.",
        suggestions=[
            "This might be an admin-only feature",
            "Contact @lucidreamer for access",
        ],
    ),
    ErrorCategory.NETWORK_ERROR: FriendlyError(
        emoji="\U0001f4e1",
        title="Connection Issue",
        message="Network hiccup. Couldn't reach the server.",
        suggestions=[
            "Check your internet connection",
            "Try again in a few seconds",
            "Run `/status` to check service health",
        ],
        retry_after=10,
    ),
    ErrorCategory.TIMEOUT: FriendlyError(
        emoji="\u23f3",
        title="Request Timeout",
        message="The request took too long.",
        suggestions=[
            "Try a simpler query",
            "The blockchain might be congested",
            "Try again in a moment",
        ],
        retry_after=15,
    ),
    ErrorCategory.INTERNAL: FriendlyError(
        emoji="\U0001f41e",
        title="Something Went Wrong",
        message="Internal error. I've logged it for review.",
        suggestions=[
            "Try again in a few seconds",
            "If this persists, contact support",
        ],
    ),
    ErrorCategory.MAINTENANCE: FriendlyError(
        emoji="\U0001f527",
        title="Maintenance Mode",
        message="I'm being upgraded. Back shortly.",
        suggestions=[
            "Check back in a few minutes",
            "Follow @Jarvis_lifeos for updates",
        ],
    ),
}


def classify_error(error: Exception) -> ErrorCategory:
    """
    Classify an exception into an error category.

    Args:
        error: The exception to classify

    Returns:
        The most appropriate ErrorCategory
    """
    error_str = str(error).lower()
    error_type = type(error).__name__

    # Token not found patterns
    if any(p in error_str for p in ["not found", "token not found", "invalid token", "no data"]):
        return ErrorCategory.TOKEN_NOT_FOUND

    # Rate limiting patterns
    if any(p in error_str for p in ["rate limit", "too many", "429", "throttl"]):
        return ErrorCategory.RATE_LIMITED

    # Permission patterns
    if any(p in error_str for p in ["unauthorized", "permission", "forbidden", "403"]):
        return ErrorCategory.PERMISSION_DENIED

    # Network patterns
    if any(p in error_str for p in ["connection", "network", "unreachable", "dns"]):
        return ErrorCategory.NETWORK_ERROR

    # Timeout patterns
    if any(p in error_str for p in ["timeout", "timed out", "deadline"]):
        return ErrorCategory.TIMEOUT

    # API error patterns
    if any(p in error_str for p in ["api", "500", "502", "503", "service unavailable"]):
        return ErrorCategory.API_ERROR

    # Invalid input patterns
    if any(p in error_str for p in ["invalid", "parse", "format", "value error"]):
        return ErrorCategory.INVALID_INPUT

    # Maintenance patterns
    if any(p in error_str for p in ["maintenance", "upgrade", "down for"]):
        return ErrorCategory.MAINTENANCE

    return ErrorCategory.INTERNAL


def format_error_message(
    error: Exception,
    category: Optional[ErrorCategory] = None,
    context: Optional[str] = None,
) -> str:
    """
    Format an error into a user-friendly message.

    Args:
        error: The exception to format
        category: Optional override for error category
        context: Optional context about what was being attempted

    Returns:
        Formatted markdown message
    """
    if category is None:
        category = classify_error(error)

    template = ERROR_TEMPLATES.get(category, ERROR_TEMPLATES[ErrorCategory.INTERNAL])

    lines = [
        f"{template.emoji} *{template.title}*",
        "",
        f"_{template.message}_",
    ]

    if context:
        lines.append(f"\n_Context: {context}_")

    if template.suggestions:
        lines.append("")
        lines.append("*Try this:*")
        for suggestion in template.suggestions:
            lines.append(f"  - {suggestion}")

    if template.retry_after:
        lines.append(f"\n_Retry in {template.retry_after}s_")

    return "\n".join(lines)


def format_simple_error(message: str, suggestion: Optional[str] = None) -> str:
    """
    Format a simple error message.

    Args:
        message: The error message
        suggestion: Optional suggestion for recovery

    Returns:
        Formatted markdown message
    """
    lines = [f"\u274c _{message}_"]

    if suggestion:
        lines.append(f"\n\U0001f4a1 _{suggestion}_")

    return "\n".join(lines)


def format_validation_error(field: str, issue: str, example: Optional[str] = None) -> str:
    """
    Format a validation error for user input.

    Args:
        field: The field that failed validation
        issue: Description of the issue
        example: Optional example of valid input

    Returns:
        Formatted markdown message
    """
    lines = [
        f"\U0001f4dd *Invalid {field}*",
        "",
        f"_{issue}_",
    ]

    if example:
        lines.append(f"\n*Example:* `{example}`")

    return "\n".join(lines)


def extract_error_code(error: Exception) -> Optional[str]:
    """
    Extract an error code from an exception if present.

    Args:
        error: The exception to inspect

    Returns:
        Error code string or None
    """
    error_str = str(error)

    # Look for HTTP status codes
    http_match = re.search(r'\b([45]\d{2})\b', error_str)
    if http_match:
        return f"HTTP_{http_match.group(1)}"

    # Look for custom error codes
    code_match = re.search(r'error[_-]?code[:\s]+(\w+)', error_str, re.IGNORECASE)
    if code_match:
        return code_match.group(1).upper()

    return None


class ErrorFormatter:
    """
    Error formatter with customization options.
    """

    def __init__(
        self,
        include_code: bool = False,
        include_timestamp: bool = False,
        max_suggestion_count: int = 3,
    ):
        """
        Initialize ErrorFormatter.

        Args:
            include_code: Whether to include error codes
            include_timestamp: Whether to include timestamps
            max_suggestion_count: Maximum number of suggestions to show
        """
        self.include_code = include_code
        self.include_timestamp = include_timestamp
        self.max_suggestion_count = max_suggestion_count

    def format(
        self,
        error: Exception,
        context: Optional[str] = None,
    ) -> str:
        """
        Format an error with configured options.

        Args:
            error: The exception to format
            context: Optional context about what was being attempted

        Returns:
            Formatted markdown message
        """
        category = classify_error(error)
        template = ERROR_TEMPLATES.get(category, ERROR_TEMPLATES[ErrorCategory.INTERNAL])

        lines = [
            f"{template.emoji} *{template.title}*",
            "",
            f"_{template.message}_",
        ]

        if context:
            lines.append(f"\n_Context: {context}_")

        if self.include_code:
            code = extract_error_code(error)
            if code:
                lines.append(f"\n_Code: `{code}`_")

        if template.suggestions:
            lines.append("")
            lines.append("*Try this:*")
            for suggestion in template.suggestions[:self.max_suggestion_count]:
                lines.append(f"  - {suggestion}")

        if template.retry_after:
            lines.append(f"\n_Retry in {template.retry_after}s_")

        if self.include_timestamp:
            from datetime import datetime, timezone
            now = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")
            lines.append(f"\n_Time: {now}_")

        return "\n".join(lines)


# Singleton formatter
_formatter: Optional[ErrorFormatter] = None


def get_formatter() -> ErrorFormatter:
    """Get the global error formatter."""
    global _formatter
    if _formatter is None:
        _formatter = ErrorFormatter()
    return _formatter


__all__ = [
    "ErrorCategory",
    "FriendlyError",
    "ErrorFormatter",
    "classify_error",
    "format_error_message",
    "format_simple_error",
    "format_validation_error",
    "extract_error_code",
    "get_formatter",
    "ERROR_TEMPLATES",
]
