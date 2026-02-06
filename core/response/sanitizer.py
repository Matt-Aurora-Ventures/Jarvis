"""
Sanitizer - Text sanitization and security utilities.

Provides functions for cleaning user input and output text,
removing sensitive data, and ensuring safe encoding.

Example:
    from core.response.sanitizer import sanitize_output, remove_sensitive_data

    clean_text = sanitize_output("User input\\x00with\\x00nulls")
    safe_text = remove_sensitive_data("API key: sk-abc123")
"""

from __future__ import annotations

import re
from typing import List, Optional, Set, Union


# Control characters to remove (except newlines and tabs)
CONTROL_CHARS = set(chr(c) for c in range(32) if c not in (9, 10, 13))

# Patterns for sensitive data detection
SENSITIVE_PATTERNS = [
    # OpenAI-style keys
    (r'sk[-_][a-zA-Z0-9_]{20,}', '[REDACTED_API_KEY]'),
    # API keys in various formats (capture everything after = or :)
    (r'api[-_]?key["\'\s:=]+["\']?[a-zA-Z0-9_=-]+["\']?', 'api_key=[REDACTED]'),
    # Passwords (capture everything after = or :)
    (r'password["\'\s:=]+["\']?[^\s"\']+["\']?', 'password=[REDACTED]'),
    # Tokens (Bearer and general)
    (r'Bearer\s+[a-zA-Z0-9._=-]+', 'Bearer [REDACTED]'),
    (r'token["\'\s:=]+["\']?[a-zA-Z0-9._=-]+["\']?', 'token=[REDACTED]'),
    # Secrets
    (r'secret[-_]?key["\'\s:=]+["\']?[a-zA-Z0-9_=-]+["\']?', 'secret_key=[REDACTED]'),
    (r'secret["\'\s:=]+["\']?[a-zA-Z0-9_=-]+["\']?', 'secret=[REDACTED]'),
    # Private keys (multiline)
    (r'-----BEGIN[^-]+PRIVATE KEY-----[\s\S]*?-----END[^-]+PRIVATE KEY-----', '[REDACTED_PRIVATE_KEY]'),
    (r'-----BEGIN\s+PRIVATE KEY-----[^-]*', '[REDACTED_PRIVATE_KEY]'),
    (r'private[-_]?key["\'\s:=]+[^\s]+', 'private_key=[REDACTED]'),
    # Connection strings with passwords
    (r'://[^:]+:([^@]+)@', '://[user]:[REDACTED]@'),
    # Generic long hex/base64 keys (32+ chars)
    (r'\b([a-fA-F0-9]{32,})\b', '[REDACTED_KEY]'),
    # Credit card-like numbers
    (r'\b(\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4})\b', '[REDACTED_CARD]'),
]


def sanitize_output(text: Optional[str]) -> str:
    """
    Sanitize output text for safe display.

    Removes:
    - Leading/trailing whitespace
    - Null bytes
    - Control characters (except newlines/tabs)
    - Normalizes line endings

    Args:
        text: Text to sanitize

    Returns:
        Sanitized text
    """
    if not text:
        return ""

    # Remove null bytes
    text = text.replace('\x00', '')

    # Remove control characters
    text = ''.join(c for c in text if c not in CONTROL_CHARS or c in '\n\t')

    # Normalize line endings
    text = text.replace('\r\n', '\n').replace('\r', '\n')

    # Strip whitespace
    text = text.strip()

    return text


def remove_sensitive_data(
    text: Optional[str],
    additional_patterns: Optional[List[tuple]] = None
) -> str:
    """
    Remove potentially sensitive data from text.

    Args:
        text: Text to clean
        additional_patterns: Extra (pattern, replacement) tuples

    Returns:
        Text with sensitive data redacted
    """
    if not text:
        return ""

    patterns = SENSITIVE_PATTERNS.copy()
    if additional_patterns:
        patterns.extend(additional_patterns)

    for pattern, replacement in patterns:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

    return text


def truncate_safely(
    text: Optional[str],
    max_len: int = 100,
    max_length: Optional[int] = None,
    suffix: str = "..."
) -> str:
    """
    Truncate text safely at word boundaries.

    Args:
        text: Text to truncate
        max_len: Maximum length (alias for max_length)
        max_length: Maximum length
        suffix: Suffix to add when truncated

    Returns:
        Truncated text
    """
    # Use max_length if provided, otherwise max_len
    limit = max_length if max_length is not None else max_len

    if text is None:
        return ""
    if not text or len(text) <= limit:
        return text or ""

    # Account for suffix
    target_len = limit - len(suffix)
    if target_len <= 0:
        return text[:limit]

    # Try to break at word boundary
    truncated = text[:target_len]
    last_space = truncated.rfind(' ')

    if last_space > target_len // 2:
        truncated = truncated[:last_space]

    return truncated + suffix


def ensure_valid_encoding(
    text: Union[str, bytes, None],
    encoding: str = "utf-8",
    errors: str = "replace"
) -> str:
    """
    Ensure text has valid encoding.

    Args:
        text: Text or bytes to validate
        encoding: Target encoding
        errors: Error handling strategy

    Returns:
        Text with valid encoding
    """
    if not text:
        return ""

    # Handle bytes input
    if isinstance(text, bytes):
        return text.decode(encoding, errors=errors)

    # Encode and decode to fix invalid characters
    # Use 'surrogateescape' for encoding to catch any issues, then decode
    try:
        encoded = text.encode(encoding, errors='surrogateescape')
        return encoded.decode(encoding, errors=errors)
    except UnicodeError:
        # Fallback: just replace problematic characters
        return text.encode(encoding, errors='replace').decode(encoding)


def escape_html(text: str) -> str:
    """
    Escape HTML special characters.

    Args:
        text: Text to escape

    Returns:
        HTML-escaped text
    """
    if not text:
        return ""

    return (
        text
        .replace('&', '&amp;')
        .replace('<', '&lt;')
        .replace('>', '&gt;')
        .replace('"', '&quot;')
        .replace("'", '&#x27;')
    )


def unescape_html(text: str) -> str:
    """
    Unescape HTML entities.

    Args:
        text: Text to unescape

    Returns:
        Unescaped text
    """
    if not text:
        return ""

    return (
        text
        .replace('&lt;', '<')
        .replace('&gt;', '>')
        .replace('&quot;', '"')
        .replace('&#x27;', "'")
        .replace('&amp;', '&')
    )


def normalize_whitespace(text: str) -> str:
    """
    Normalize whitespace in text.

    Collapses multiple spaces, removes leading/trailing whitespace from lines.

    Args:
        text: Text to normalize

    Returns:
        Text with normalized whitespace
    """
    if not text:
        return ""

    # Split into lines
    lines = text.split('\n')

    # Strip each line and collapse multiple spaces
    normalized_lines = []
    for line in lines:
        line = ' '.join(line.split())
        normalized_lines.append(line)

    return '\n'.join(normalized_lines).strip()


def remove_urls(text: str, replacement: str = "[URL]") -> str:
    """
    Remove URLs from text.

    Args:
        text: Text to process
        replacement: String to replace URLs with

    Returns:
        Text with URLs removed
    """
    if not text:
        return ""

    url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
    return re.sub(url_pattern, replacement, text)


def limit_line_length(text: str, max_length: int = 80) -> str:
    """
    Limit line length by wrapping long lines.

    Args:
        text: Text to wrap
        max_length: Maximum line length

    Returns:
        Text with limited line lengths
    """
    if not text:
        return ""

    lines = text.split('\n')
    wrapped_lines = []

    for line in lines:
        while len(line) > max_length:
            # Find break point
            break_point = line.rfind(' ', 0, max_length)
            if break_point <= 0:
                break_point = max_length

            wrapped_lines.append(line[:break_point])
            line = line[break_point:].lstrip()

        wrapped_lines.append(line)

    return '\n'.join(wrapped_lines)
