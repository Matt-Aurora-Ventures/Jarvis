"""
Sensitive Data Scrubber for Claude API

Scrubs sensitive information (API keys, passwords, wallet keys, etc.) from
text before sending to external AI APIs like Claude.

This is CRITICAL for security - never send raw secrets to external services.
"""

import re
import logging
from typing import Dict, List, Tuple, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class SensitiveScrubber:
    """
    Scrub sensitive data before sending to Claude API.

    Patterns are comprehensive and designed to catch:
    - API keys (OpenAI, XAI, Helius, generic)
    - Wallet private keys (Solana base58, Ethereum hex)
    - Passwords and secrets
    - Telegram bot tokens
    - Database credentials
    - JWT tokens
    """

    # Pattern -> Replacement mapping
    # Uses named groups where possible for better reporting
    PATTERNS: Dict[str, Tuple[str, str]] = {
        # OpenAI API keys
        "openai_key": (
            r'sk-[a-zA-Z0-9]{48,}',
            '[REDACTED_OPENAI_KEY]'
        ),

        # XAI/Grok API keys
        "xai_key": (
            r'xai-[a-zA-Z0-9]{48,}',
            '[REDACTED_XAI_KEY]'
        ),

        # Anthropic API keys
        "anthropic_key": (
            r'sk-ant-[a-zA-Z0-9\-]{40,}',
            '[REDACTED_ANTHROPIC_KEY]'
        ),

        # Generic API keys in env format
        "api_key_env": (
            r'(?:api[_-]?key|apikey)\s*[=:]\s*["\']?([a-zA-Z0-9_\-]{20,})["\']?',
            '[REDACTED_API_KEY]'
        ),

        # Solana private keys (base58, 64-88 chars)
        "solana_private_key": (
            r'\b[1-9A-HJ-NP-Za-km-z]{64,88}\b',
            '[REDACTED_SOLANA_KEY]'
        ),

        # Ethereum private keys (hex)
        "eth_private_key": (
            r'(?:0x)?[a-fA-F0-9]{64}',
            '[REDACTED_ETH_KEY]'
        ),

        # Private key in env format
        "private_key_env": (
            r'(?:private[_-]?key|secret[_-]?key)\s*[=:]\s*["\']?([^\s"\']{20,})["\']?',
            'private_key=[REDACTED_PRIVATE_KEY]'
        ),

        # Passwords
        "password": (
            r'(?:password|passwd|pwd)\s*[=:]\s*["\']?([^\s"\']+)["\']?',
            'password=[REDACTED_PASSWORD]'
        ),

        # JARVIS wallet password specifically
        "jarvis_wallet_password": (
            r'JARVIS_WALLET_PASSWORD\s*[=:]\s*["\']?([^\s"\']+)["\']?',
            'JARVIS_WALLET_PASSWORD=[REDACTED_PASSWORD]'
        ),

        # Telegram bot tokens (digits:alphanumeric)
        "telegram_token": (
            r'\b\d{8,10}:[A-Za-z0-9_-]{35}\b',
            '[REDACTED_TELEGRAM_TOKEN]'
        ),

        # Helius/RPC API keys
        "helius_key": (
            r'(?:helius|rpc)[_-]?(?:api[_-]?)?(?:key|url)\s*[=:]\s*["\']?([a-zA-Z0-9\-_:/.]{30,})["\']?',
            '[REDACTED_RPC_KEY]'
        ),

        # Generic secrets/tokens
        "generic_secret": (
            r'(?:secret|token|auth)[_-]?(?:key)?\s*[=:]\s*["\']?([a-zA-Z0-9_\-]{20,})["\']?',
            '[REDACTED_SECRET]'
        ),

        # JWT tokens
        "jwt_token": (
            r'eyJ[a-zA-Z0-9_-]*\.eyJ[a-zA-Z0-9_-]*\.[a-zA-Z0-9_-]*',
            '[REDACTED_JWT]'
        ),

        # Database URLs with credentials
        "database_url": (
            r'(?:postgres(?:ql)?|mysql|mongodb|redis)://[^:]+:[^@]+@[^\s]+',
            '[REDACTED_DATABASE_URL]'
        ),

        # Bearer tokens
        "bearer_token": (
            r'Bearer\s+[a-zA-Z0-9_\-\.]+',
            'Bearer [REDACTED_TOKEN]'
        ),

        # SSH private keys
        "ssh_key": (
            r'-----BEGIN (?:RSA |OPENSSH )?PRIVATE KEY-----[\s\S]*?-----END (?:RSA |OPENSSH )?PRIVATE KEY-----',
            '[REDACTED_SSH_KEY]'
        ),

        # AWS keys
        "aws_key": (
            r'(?:AKIA|ASIA)[A-Z0-9]{16}',
            '[REDACTED_AWS_KEY]'
        ),

        # Credit card numbers (basic)
        "credit_card": (
            r'\b(?:\d{4}[- ]?){3}\d{4}\b',
            '[REDACTED_CARD]'
        ),
    }

    def __init__(self, additional_patterns: Dict[str, Tuple[str, str]] = None):
        """
        Initialize scrubber with optional additional patterns.

        Args:
            additional_patterns: Dict of name -> (pattern, replacement)
        """
        self.patterns = dict(self.PATTERNS)
        if additional_patterns:
            self.patterns.update(additional_patterns)

        # Compile patterns
        self._compiled = {
            name: (re.compile(pattern, re.IGNORECASE | re.MULTILINE), replacement)
            for name, (pattern, replacement) in self.patterns.items()
        }

    def scrub(self, text: str) -> Tuple[str, List[str]]:
        """
        Scrub sensitive data from text.

        Args:
            text: Text to scrub

        Returns:
            (scrubbed_text, list_of_redacted_types)
        """
        redacted_types = []
        scrubbed = text

        for name, (pattern, replacement) in self._compiled.items():
            if pattern.search(scrubbed):
                redacted_types.append(replacement)
                scrubbed = pattern.sub(replacement, scrubbed)

        if redacted_types:
            logger.info(f"Scrubbed {len(redacted_types)} sensitive items: {redacted_types}")

        return scrubbed, redacted_types

    def scrub_file_content(self, filepath: str) -> Tuple[str, List[str]]:
        """
        Read and scrub a file's content.

        Args:
            filepath: Path to file

        Returns:
            (scrubbed_content, list_of_redacted_types)
        """
        path = Path(filepath)

        if not path.exists():
            logger.warning(f"File not found: {filepath}")
            return "", []

        try:
            content = path.read_text(encoding='utf-8', errors='replace')
            return self.scrub(content)
        except Exception as e:
            logger.error(f"Error reading file {filepath}: {e}")
            return "", []

    def scrub_dict(self, data: dict, depth: int = 0, max_depth: int = 10) -> Tuple[dict, List[str]]:
        """
        Recursively scrub sensitive data from a dictionary.

        Args:
            data: Dictionary to scrub
            depth: Current recursion depth
            max_depth: Maximum recursion depth

        Returns:
            (scrubbed_dict, list_of_redacted_types)
        """
        if depth > max_depth:
            return data, []

        all_redacted = []
        result = {}

        for key, value in data.items():
            if isinstance(value, str):
                scrubbed, redacted = self.scrub(value)
                result[key] = scrubbed
                all_redacted.extend(redacted)
            elif isinstance(value, dict):
                scrubbed, redacted = self.scrub_dict(value, depth + 1, max_depth)
                result[key] = scrubbed
                all_redacted.extend(redacted)
            elif isinstance(value, list):
                scrubbed_list = []
                for item in value:
                    if isinstance(item, str):
                        s, r = self.scrub(item)
                        scrubbed_list.append(s)
                        all_redacted.extend(r)
                    elif isinstance(item, dict):
                        s, r = self.scrub_dict(item, depth + 1, max_depth)
                        scrubbed_list.append(s)
                        all_redacted.extend(r)
                    else:
                        scrubbed_list.append(item)
                result[key] = scrubbed_list
            else:
                result[key] = value

        return result, list(set(all_redacted))

    def is_sensitive(self, text: str) -> bool:
        """Check if text contains sensitive data."""
        for name, (pattern, _) in self._compiled.items():
            if pattern.search(text):
                return True
        return False

    def get_sensitive_types(self, text: str) -> List[str]:
        """Get list of sensitive data types found in text."""
        found = []
        for name, (pattern, replacement) in self._compiled.items():
            if pattern.search(text):
                found.append(name)
        return found


# Singleton instance
_scrubber: Optional[SensitiveScrubber] = None


def get_scrubber() -> SensitiveScrubber:
    """Get the singleton scrubber instance."""
    global _scrubber
    if _scrubber is None:
        _scrubber = SensitiveScrubber()
    return _scrubber


def scrub_for_claude(text: str) -> Tuple[str, List[str]]:
    """
    Convenience function to scrub text for Claude API.

    Args:
        text: Text to scrub

    Returns:
        (scrubbed_text, list_of_redacted_types)
    """
    return get_scrubber().scrub(text)
