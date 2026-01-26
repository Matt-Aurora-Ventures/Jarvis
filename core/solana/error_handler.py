"""
Structured Error Handler for Solana RPC Operations.

Provides:
- User-friendly error messages (sanitized, no internal details)
- Developer error logs (full context for debugging)
- Error categorization for retry/circuit breaker decisions
- RPC-specific error handling

Usage:
    from core.solana.error_handler import RPCErrorHandler, ErrorCategory

    handler = RPCErrorHandler()

    try:
        result = await rpc_call()
    except Exception as e:
        # For user-facing messages
        user_msg = handler.sanitize_for_user(e)
        await bot.send_message(user_id, user_msg)

        # For developer logging
        dev_log = handler.format_for_developer(e, {"endpoint": url, "method": "getBalance"})
        logger.error(dev_log)

        # Check retry eligibility
        if handler.should_retry(e):
            return await retry_call()
"""

from __future__ import annotations

import json
import logging
import re
import traceback
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Pattern

logger = logging.getLogger(__name__)


# =============================================================================
# ERROR CATEGORIES
# =============================================================================

class ErrorCategory(Enum):
    """Categories of RPC errors for handling decisions."""

    # Network/Connection errors
    TIMEOUT = "timeout"
    CONNECTION = "connection"
    RATE_LIMIT = "rate_limit"
    DNS = "dns"

    # RPC-specific errors
    NODE_UNHEALTHY = "node_unhealthy"
    TRANSACTION = "transaction"
    INSUFFICIENT_FUNDS = "insufficient_funds"
    INVALID_PARAMS = "invalid_params"
    BLOCKHASH_EXPIRED = "blockhash_expired"
    SLOT_SKIPPED = "slot_skipped"

    # Authentication/Authorization
    AUTH = "auth"
    FORBIDDEN = "forbidden"

    # Server errors
    SERVER_ERROR = "server_error"
    SERVICE_UNAVAILABLE = "service_unavailable"

    # Unknown/Other
    UNKNOWN = "unknown"


# =============================================================================
# USER-FRIENDLY MESSAGES
# =============================================================================

USER_MESSAGES: Dict[ErrorCategory, str] = {
    ErrorCategory.TIMEOUT: "The request is taking longer than expected. Please try again in a moment.",
    ErrorCategory.CONNECTION: "Unable to connect to the network. Please check your connection and try again.",
    ErrorCategory.RATE_LIMIT: "The system is busy at the moment. Please wait a moment and try again.",
    ErrorCategory.DNS: "Network configuration issue. Please try again in a moment.",

    ErrorCategory.NODE_UNHEALTHY: "The service is temporarily unavailable. We're working on it.",
    ErrorCategory.TRANSACTION: "Unable to complete the transaction. Please try again.",
    ErrorCategory.INSUFFICIENT_FUNDS: "Insufficient balance for this operation. Please check your wallet.",
    ErrorCategory.INVALID_PARAMS: "There was an issue with the request. Please try again.",
    ErrorCategory.BLOCKHASH_EXPIRED: "The transaction expired. Please try again.",
    ErrorCategory.SLOT_SKIPPED: "Network congestion detected. Please try again in a moment.",

    ErrorCategory.AUTH: "Authentication required. Please reconnect your wallet.",
    ErrorCategory.FORBIDDEN: "You don't have permission for this action.",

    ErrorCategory.SERVER_ERROR: "Something went wrong on our end. Please try again later.",
    ErrorCategory.SERVICE_UNAVAILABLE: "The service is temporarily unavailable. Please try again later.",

    ErrorCategory.UNKNOWN: "An unexpected issue occurred. Please try again.",
}


# =============================================================================
# ERROR PATTERNS
# =============================================================================

@dataclass
class ErrorPattern:
    """Pattern for matching errors to categories."""
    pattern: Pattern
    category: ErrorCategory
    is_retryable: bool = True


# Patterns for categorizing errors
ERROR_PATTERNS: List[ErrorPattern] = [
    # Timeout errors
    ErrorPattern(re.compile(r"timeout|timed?\s*out", re.I), ErrorCategory.TIMEOUT, True),
    ErrorPattern(re.compile(r"deadline\s*exceeded", re.I), ErrorCategory.TIMEOUT, True),

    # Connection errors
    ErrorPattern(re.compile(r"connection\s*(refused|reset|closed)", re.I), ErrorCategory.CONNECTION, True),
    ErrorPattern(re.compile(r"ECONNREFUSED|ECONNRESET|EPIPE", re.I), ErrorCategory.CONNECTION, True),
    ErrorPattern(re.compile(r"network\s*(is\s+)?unreachable", re.I), ErrorCategory.CONNECTION, True),
    ErrorPattern(re.compile(r"socket\s*(closed|error)", re.I), ErrorCategory.CONNECTION, True),

    # Rate limiting
    ErrorPattern(re.compile(r"429|too\s*many\s*requests|rate\s*limit", re.I), ErrorCategory.RATE_LIMIT, False),
    ErrorPattern(re.compile(r"throttl", re.I), ErrorCategory.RATE_LIMIT, False),

    # DNS errors
    ErrorPattern(re.compile(r"DNS|name\s*resolution|getaddrinfo", re.I), ErrorCategory.DNS, True),

    # Node health
    ErrorPattern(re.compile(r"node\s*(is\s+)?unhealthy", re.I), ErrorCategory.NODE_UNHEALTHY, True),
    ErrorPattern(re.compile(r"behind\s+by\s+\d+\s+slots?", re.I), ErrorCategory.NODE_UNHEALTHY, True),

    # Transaction errors
    ErrorPattern(re.compile(r"blockhash\s*(not\s+found|expired)", re.I), ErrorCategory.BLOCKHASH_EXPIRED, True),
    ErrorPattern(re.compile(r"slot\s*(was\s+)?skipped", re.I), ErrorCategory.SLOT_SKIPPED, True),
    ErrorPattern(re.compile(r"transaction\s*simulation\s*failed", re.I), ErrorCategory.TRANSACTION, True),

    # Insufficient funds
    ErrorPattern(re.compile(r"insufficient\s*(funds|balance|lamports)", re.I), ErrorCategory.INSUFFICIENT_FUNDS, False),
    ErrorPattern(re.compile(r"not\s*enough\s*(funds|balance)", re.I), ErrorCategory.INSUFFICIENT_FUNDS, False),

    # Invalid params
    ErrorPattern(re.compile(r"invalid\s*(param|argument|input)", re.I), ErrorCategory.INVALID_PARAMS, False),
    ErrorPattern(re.compile(r"malformed", re.I), ErrorCategory.INVALID_PARAMS, False),

    # Auth errors
    ErrorPattern(re.compile(r"401|unauthorized", re.I), ErrorCategory.AUTH, False),
    ErrorPattern(re.compile(r"403|forbidden", re.I), ErrorCategory.FORBIDDEN, False),
    ErrorPattern(re.compile(r"invalid\s*api\s*key", re.I), ErrorCategory.AUTH, False),

    # Server errors
    ErrorPattern(re.compile(r"500|internal\s*server\s*error", re.I), ErrorCategory.SERVER_ERROR, True),
    ErrorPattern(re.compile(r"502|bad\s*gateway", re.I), ErrorCategory.SERVER_ERROR, True),
    ErrorPattern(re.compile(r"503|service\s*unavailable", re.I), ErrorCategory.SERVICE_UNAVAILABLE, True),
    ErrorPattern(re.compile(r"504|gateway\s*timeout", re.I), ErrorCategory.TIMEOUT, True),
]


# =============================================================================
# SANITIZATION PATTERNS
# =============================================================================

# Patterns for removing sensitive information from error messages
SANITIZE_PATTERNS: List[tuple] = [
    # API keys and secrets
    (re.compile(r"api[-_]?key[=:]\s*[\w-]+", re.I), "[API_KEY_REDACTED]"),
    (re.compile(r"secret[=:]\s*[\w-]+", re.I), "[SECRET_REDACTED]"),
    (re.compile(r"token[=:]\s*[\w.-]+", re.I), "[TOKEN_REDACTED]"),
    (re.compile(r"password[=:]\s*\S+", re.I), "[PASSWORD_REDACTED]"),
    (re.compile(r"auth[=:]\s*\S+", re.I), "[AUTH_REDACTED]"),

    # URLs with credentials
    (re.compile(r"https?://[^:]+:[^@]+@", re.I), "https://[REDACTED]@"),

    # Full URLs (all URLs are potentially sensitive - redact host)
    (re.compile(r"https?://[^\s'\"]+", re.I), "[URL_REDACTED]"),

    # IP addresses
    (re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}(:\d+)?\b"), "[IP_REDACTED]"),

    # Private keys (base58 solana-like)
    (re.compile(r"\b[1-9A-HJ-NP-Za-km-z]{87,88}\b"), "[PRIVATE_KEY_REDACTED]"),

    # Wallet addresses (only if they appear in error context, keep them normally)
    # Not redacting these as they're often needed for user reference

    # File paths
    (re.compile(r"[A-Za-z]:\\[^\s]+", re.I), "[PATH_REDACTED]"),  # Windows paths
    (re.compile(r"/home/[^\s]+", re.I), "[PATH_REDACTED]"),  # Unix home paths
    (re.compile(r"/Users/[^\s]+", re.I), "[PATH_REDACTED]"),  # macOS paths
]


# =============================================================================
# ERROR HANDLER
# =============================================================================

class RPCErrorHandler:
    """
    Handles RPC errors with user-friendly and developer-friendly outputs.

    Provides:
    - Sanitized user messages (no internal details)
    - Full developer context (for debugging)
    - Error categorization (for retry decisions)
    """

    def __init__(self, custom_patterns: List[ErrorPattern] = None):
        """
        Initialize error handler.

        Args:
            custom_patterns: Additional error patterns for categorization
        """
        self._patterns = ERROR_PATTERNS + (custom_patterns or [])
        self._category_cache: Dict[str, ErrorCategory] = {}

    def categorize(self, error: Exception) -> ErrorCategory:
        """
        Categorize an error for handling decisions.

        Args:
            error: The exception to categorize

        Returns:
            ErrorCategory enum value
        """
        error_str = str(error).lower()
        error_type = type(error).__name__

        # Check cache first
        cache_key = f"{error_type}:{error_str[:100]}"
        if cache_key in self._category_cache:
            return self._category_cache[cache_key]

        # Check exception type
        if isinstance(error, TimeoutError):
            category = ErrorCategory.TIMEOUT
        elif isinstance(error, ConnectionError):
            category = ErrorCategory.CONNECTION
        elif isinstance(error, ValueError):
            category = ErrorCategory.INVALID_PARAMS
        else:
            # Pattern matching
            category = ErrorCategory.UNKNOWN
            for pattern in self._patterns:
                if pattern.pattern.search(error_str) or pattern.pattern.search(error_type):
                    category = pattern.category
                    break

        # Cache result
        self._category_cache[cache_key] = category

        return category

    def should_retry(self, error: Exception) -> bool:
        """
        Determine if an error is retryable.

        Args:
            error: The exception to check

        Returns:
            True if the operation should be retried
        """
        error_str = str(error).lower()

        # Check patterns for explicit retry flag
        for pattern in self._patterns:
            if pattern.pattern.search(error_str):
                return pattern.is_retryable

        # Default retry behavior by category
        category = self.categorize(error)

        # These categories should not be retried immediately
        non_retryable = {
            ErrorCategory.RATE_LIMIT,
            ErrorCategory.INSUFFICIENT_FUNDS,
            ErrorCategory.INVALID_PARAMS,
            ErrorCategory.AUTH,
            ErrorCategory.FORBIDDEN,
        }

        return category not in non_retryable

    def sanitize_for_user(self, error: Exception) -> str:
        """
        Create a user-friendly error message.

        Removes all internal details, API keys, URLs, etc.

        Args:
            error: The exception

        Returns:
            Safe, user-friendly error message
        """
        category = self.categorize(error)
        return self.get_user_message_for_category(category)

    def get_user_message_for_category(self, category: ErrorCategory) -> str:
        """
        Get the user-friendly message for an error category.

        Args:
            category: The error category

        Returns:
            User-friendly message string
        """
        return USER_MESSAGES.get(category, USER_MESSAGES[ErrorCategory.UNKNOWN])

    def format_for_developer(
        self,
        error: Exception,
        context: Dict[str, Any] = None
    ) -> str:
        """
        Format error with full context for developer debugging.

        Args:
            error: The exception
            context: Additional context (endpoint, method, params, etc.)

        Returns:
            Detailed error string for logging
        """
        context = context or {}

        dev_info = {
            "timestamp": datetime.utcnow().isoformat(),
            "error_type": type(error).__name__,
            "error_message": str(error),
            "category": self.categorize(error).value,
            "should_retry": self.should_retry(error),
            "context": context,
        }

        # Add traceback for unexpected errors
        if self.categorize(error) == ErrorCategory.UNKNOWN:
            dev_info["traceback"] = traceback.format_exc()

        return json.dumps(dev_info, indent=2, default=str)

    def get_user_log(self, error: Exception, context: Dict[str, Any] = None) -> str:
        """
        Get a sanitized log message safe for user-visible logs.

        Args:
            error: The exception
            context: Additional context

        Returns:
            Sanitized log string
        """
        category = self.categorize(error)
        user_msg = self.get_user_message_for_category(category)

        # Create log with sanitized info
        log_parts = [
            f"Error category: {category.value}",
            f"User message: {user_msg}",
        ]

        if context:
            # Sanitize context values
            sanitized_context = self._sanitize_dict(context)
            log_parts.append(f"Context: {sanitized_context}")

        return " | ".join(log_parts)

    def get_developer_log(self, error: Exception, context: Dict[str, Any] = None) -> str:
        """
        Get full developer log with all details.

        Args:
            error: The exception
            context: Additional context

        Returns:
            Full detail log string
        """
        return self.format_for_developer(error, context)

    def _sanitize_string(self, text: str) -> str:
        """Sanitize a string by removing sensitive patterns."""
        result = text
        for pattern, replacement in SANITIZE_PATTERNS:
            result = pattern.sub(replacement, result)
        return result

    def _sanitize_dict(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize a dictionary by removing sensitive values."""
        sanitized = {}
        sensitive_keys = {"api_key", "secret", "password", "token", "auth", "key"}

        for key, value in data.items():
            key_lower = key.lower()
            if any(s in key_lower for s in sensitive_keys):
                sanitized[key] = "[REDACTED]"
            elif isinstance(value, str):
                sanitized[key] = self._sanitize_string(value)
            elif isinstance(value, dict):
                sanitized[key] = self._sanitize_dict(value)
            else:
                sanitized[key] = value

        return sanitized


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

# Global handler instance
_global_handler: Optional[RPCErrorHandler] = None


def get_rpc_error_handler() -> RPCErrorHandler:
    """Get the global RPC error handler."""
    global _global_handler
    if _global_handler is None:
        _global_handler = RPCErrorHandler()
    return _global_handler


def categorize_error(error: Exception) -> ErrorCategory:
    """Categorize an error using the global handler."""
    return get_rpc_error_handler().categorize(error)


def get_user_error_message(error: Exception) -> str:
    """Get a user-friendly error message."""
    return get_rpc_error_handler().sanitize_for_user(error)


def should_retry_error(error: Exception) -> bool:
    """Check if an error should be retried."""
    return get_rpc_error_handler().should_retry(error)


def log_rpc_error(
    error: Exception,
    context: Dict[str, Any] = None,
    logger: logging.Logger = None
) -> None:
    """
    Log an RPC error with appropriate detail levels.

    Logs sanitized version at INFO level, full details at DEBUG level.

    Args:
        error: The exception
        context: Additional context
        logger: Logger to use (defaults to module logger)
    """
    handler = get_rpc_error_handler()
    log = logger or logging.getLogger(__name__)

    # Sanitized log for INFO level
    log.info(handler.get_user_log(error, context))

    # Full details for DEBUG level
    log.debug(handler.get_developer_log(error, context))


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "ErrorCategory",
    "ErrorPattern",
    "RPCErrorHandler",
    "get_rpc_error_handler",
    "categorize_error",
    "get_user_error_message",
    "should_retry_error",
    "log_rpc_error",
    "USER_MESSAGES",
]
