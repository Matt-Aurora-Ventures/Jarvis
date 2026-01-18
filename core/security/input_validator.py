"""
Input Validation Module

Comprehensive input validation for security-critical operations.
Validates:
- Token symbols (alphanumeric, length limits)
- Amounts (positive, bounded)
- Solana addresses (format validation)
- General strings (SQL injection, XSS, path traversal)

Follows OWASP input validation guidelines.
"""

import re
import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Any, Pattern
from urllib.parse import unquote

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of an input validation check."""
    valid: bool
    reason: Optional[str] = None
    sanitized_value: Optional[Any] = None


# Compiled regex patterns for performance
PATTERNS = {
    # Token symbol: alphanumeric only, 1-20 chars
    "token_symbol": re.compile(r'^[A-Za-z0-9]{1,20}$'),

    # Solana address: base58, 32-44 chars
    "solana_address": re.compile(r'^[1-9A-HJ-NP-Za-km-z]{32,44}$'),

    # Ethereum address: 0x + 40 hex chars
    "ethereum_address": re.compile(r'^0x[0-9a-fA-F]{40}$'),

    # SQL injection patterns
    "sql_injection": [
        re.compile(r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|UNION|ALTER|CREATE|TRUNCATE)\b)", re.IGNORECASE),
        re.compile(r"(--)|(;)|(\/\*)|(\*\/)", re.IGNORECASE),
        re.compile(r"(\bOR\b.*=.*)|(\bAND\b.*=.*)", re.IGNORECASE),
        re.compile(r"'.*(\bOR\b|\bAND\b).*'", re.IGNORECASE),
    ],

    # XSS patterns
    "xss": [
        re.compile(r'<script[^>]*>.*?</script>', re.IGNORECASE | re.DOTALL),
        re.compile(r'javascript:', re.IGNORECASE),
        re.compile(r'on\w+\s*=', re.IGNORECASE),
        re.compile(r'<[^>]*\s(on\w+)=', re.IGNORECASE),
        re.compile(r'<(iframe|object|embed|form)', re.IGNORECASE),
    ],

    # Path traversal patterns
    "path_traversal": [
        re.compile(r'\.\.[\\/]'),
        re.compile(r'\.\.%2[fF]'),
        re.compile(r'%2e%2e[\\/]', re.IGNORECASE),
        re.compile(r'\.\.%5[cC]'),
    ],

    # Command injection patterns
    "command_injection": [
        re.compile(r'[;&|`$]'),
        re.compile(r'\$\(.*\)'),
        re.compile(r'`.*`'),
    ],
}


class InputValidator:
    """
    Comprehensive input validator for security-critical operations.

    Features:
    - Token symbol validation
    - Amount validation with bounds
    - Address format validation (Solana, Ethereum)
    - SQL injection detection
    - XSS detection
    - Path traversal detection
    - Optional logging of rejected inputs
    """

    def __init__(
        self,
        max_amount: float = 1_000_000_000,
        min_amount: float = 0.000001,
        max_string_length: int = 10000,
        log_rejected: bool = False,
        log_path: Optional[Path] = None
    ):
        """
        Initialize the validator.

        Args:
            max_amount: Maximum allowed amount
            min_amount: Minimum allowed amount (must be positive)
            max_string_length: Maximum string length
            log_rejected: Whether to log rejected inputs
            log_path: Path for rejection logs
        """
        self.max_amount = max_amount
        self.min_amount = min_amount
        self.max_string_length = max_string_length
        self.log_rejected = log_rejected
        self.log_path = log_path or Path("logs/rejected_inputs.log")

        if self.log_rejected:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def _log_rejection(
        self,
        input_type: str,
        value: str,
        reason: str
    ) -> None:
        """Log a rejected input for security monitoring."""
        if not self.log_rejected:
            return

        entry = {
            "timestamp": datetime.now().isoformat(),
            "input_type": input_type,
            "value_preview": value[:100] if len(value) > 100 else value,
            "reason": reason
        }

        with open(self.log_path, "a") as f:
            f.write(json.dumps(entry) + "\n")

        logger.warning(f"Rejected input: {input_type} - {reason}")

    def validate_token_symbol(self, symbol: str) -> ValidationResult:
        """
        Validate a token symbol.

        Rules:
        - Alphanumeric only
        - 1-20 characters
        - No special characters

        Args:
            symbol: Token symbol to validate

        Returns:
            ValidationResult
        """
        if not symbol or not isinstance(symbol, str):
            return ValidationResult(valid=False, reason="Symbol is empty or not a string")

        symbol = symbol.strip()

        if len(symbol) > 20:
            self._log_rejection("token_symbol", symbol, "Too long")
            return ValidationResult(valid=False, reason="Symbol too long (max 20 chars)")

        if not PATTERNS["token_symbol"].match(symbol):
            self._log_rejection("token_symbol", symbol, "Invalid characters")
            return ValidationResult(
                valid=False,
                reason="Symbol must be alphanumeric only"
            )

        return ValidationResult(valid=True, sanitized_value=symbol.upper())

    def validate_amount(
        self,
        amount: float,
        custom_max: Optional[float] = None,
        custom_min: Optional[float] = None
    ) -> ValidationResult:
        """
        Validate a numeric amount.

        Rules:
        - Must be positive (> 0)
        - Within configured bounds

        Args:
            amount: Amount to validate
            custom_max: Override max amount
            custom_min: Override min amount

        Returns:
            ValidationResult
        """
        max_amt = custom_max if custom_max is not None else self.max_amount
        min_amt = custom_min if custom_min is not None else self.min_amount

        if not isinstance(amount, (int, float)):
            return ValidationResult(valid=False, reason="Amount must be numeric")

        if amount <= 0:
            return ValidationResult(valid=False, reason="Amount must be positive")

        if amount < min_amt:
            return ValidationResult(
                valid=False,
                reason=f"Amount below minimum ({min_amt})"
            )

        if amount > max_amt:
            self._log_rejection("amount", str(amount), f"Exceeds max {max_amt}")
            return ValidationResult(
                valid=False,
                reason=f"Amount exceeds maximum ({max_amt})"
            )

        return ValidationResult(valid=True, sanitized_value=float(amount))

    def validate_solana_address(self, address: str) -> ValidationResult:
        """
        Validate a Solana address format.

        Rules:
        - Base58 characters only
        - 32-44 characters

        Args:
            address: Solana address to validate

        Returns:
            ValidationResult
        """
        if not address or not isinstance(address, str):
            return ValidationResult(valid=False, reason="Address is empty or not a string")

        address = address.strip()

        if not PATTERNS["solana_address"].match(address):
            self._log_rejection("solana_address", address, "Invalid format")
            return ValidationResult(
                valid=False,
                reason="Invalid Solana address format"
            )

        # Try base58 decode if available
        try:
            import base58
            decoded = base58.b58decode(address)
            if len(decoded) != 32:
                return ValidationResult(
                    valid=False,
                    reason=f"Invalid address length ({len(decoded)} bytes)"
                )
        except ImportError:
            pass  # base58 not available, format check is sufficient
        except Exception as e:
            return ValidationResult(valid=False, reason=f"Base58 decode failed: {e}")

        return ValidationResult(valid=True, sanitized_value=address)

    def validate_ethereum_address(self, address: str) -> ValidationResult:
        """
        Validate an Ethereum address format.

        Args:
            address: Ethereum address to validate

        Returns:
            ValidationResult
        """
        if not address or not isinstance(address, str):
            return ValidationResult(valid=False, reason="Address is empty or not a string")

        address = address.strip()

        if not PATTERNS["ethereum_address"].match(address):
            return ValidationResult(
                valid=False,
                reason="Invalid Ethereum address format"
            )

        return ValidationResult(valid=True, sanitized_value=address)

    def _check_sql_injection(self, value: str) -> Optional[str]:
        """Check for SQL injection patterns."""
        for pattern in PATTERNS["sql_injection"]:
            if pattern.search(value):
                return "Potential SQL injection detected"
        return None

    def _check_xss(self, value: str) -> Optional[str]:
        """Check for XSS patterns."""
        for pattern in PATTERNS["xss"]:
            if pattern.search(value):
                return "Potential XSS detected"
        return None

    def _check_path_traversal(self, value: str) -> Optional[str]:
        """Check for path traversal patterns."""
        # URL decode first
        decoded = unquote(value)

        for pattern in PATTERNS["path_traversal"]:
            if pattern.search(decoded) or pattern.search(value):
                return "Potential path traversal detected"
        return None

    def _check_command_injection(self, value: str) -> Optional[str]:
        """Check for command injection patterns."""
        for pattern in PATTERNS["command_injection"]:
            if pattern.search(value):
                return "Potential command injection detected"
        return None

    def validate_safe_string(
        self,
        value: str,
        check_sql: bool = True,
        check_xss: bool = True,
        check_path: bool = True,
        check_cmd: bool = True,
        max_length: Optional[int] = None
    ) -> ValidationResult:
        """
        Validate a string for common attack patterns.

        Checks for:
        - SQL injection
        - XSS
        - Path traversal
        - Command injection

        Args:
            value: String to validate
            check_sql: Check for SQL injection
            check_xss: Check for XSS
            check_path: Check for path traversal
            check_cmd: Check for command injection
            max_length: Override max string length

        Returns:
            ValidationResult
        """
        if not isinstance(value, str):
            return ValidationResult(valid=False, reason="Value is not a string")

        max_len = max_length or self.max_string_length

        if len(value) > max_len:
            self._log_rejection("string", value, "Too long")
            return ValidationResult(
                valid=False,
                reason=f"String exceeds maximum length ({max_len})"
            )

        # Check for various attack patterns
        if check_sql:
            reason = self._check_sql_injection(value)
            if reason:
                self._log_rejection("string", value, reason)
                return ValidationResult(valid=False, reason=reason)

        if check_xss:
            reason = self._check_xss(value)
            if reason:
                self._log_rejection("string", value, reason)
                return ValidationResult(valid=False, reason=reason)

        if check_path:
            reason = self._check_path_traversal(value)
            if reason:
                self._log_rejection("string", value, reason)
                return ValidationResult(valid=False, reason=reason)

        if check_cmd:
            reason = self._check_command_injection(value)
            if reason:
                self._log_rejection("string", value, reason)
                return ValidationResult(valid=False, reason=reason)

        return ValidationResult(valid=True, sanitized_value=value)

    def validate_json(
        self,
        data: Any,
        max_depth: int = 10,
        max_size: int = 1_000_000
    ) -> ValidationResult:
        """
        Validate JSON data structure.

        Args:
            data: JSON-serializable data
            max_depth: Maximum nesting depth
            max_size: Maximum serialized size in bytes

        Returns:
            ValidationResult
        """
        try:
            serialized = json.dumps(data)
            if len(serialized) > max_size:
                return ValidationResult(
                    valid=False,
                    reason=f"JSON exceeds maximum size ({max_size} bytes)"
                )

            def check_depth(obj, current_depth=0):
                if current_depth > max_depth:
                    return False
                if isinstance(obj, dict):
                    return all(check_depth(v, current_depth + 1) for v in obj.values())
                if isinstance(obj, list):
                    return all(check_depth(item, current_depth + 1) for item in obj)
                return True

            if not check_depth(data):
                return ValidationResult(
                    valid=False,
                    reason=f"JSON exceeds maximum depth ({max_depth})"
                )

            return ValidationResult(valid=True, sanitized_value=data)

        except (TypeError, ValueError) as e:
            return ValidationResult(valid=False, reason=f"Invalid JSON: {e}")


# Global validator instance
_validator: Optional[InputValidator] = None


def get_validator() -> InputValidator:
    """Get or create the global validator instance."""
    global _validator
    if _validator is None:
        _validator = InputValidator(log_rejected=True)
    return _validator


# Convenience functions
def validate_token(symbol: str) -> ValidationResult:
    """Validate a token symbol."""
    return get_validator().validate_token_symbol(symbol)


def validate_amount(amount: float) -> ValidationResult:
    """Validate an amount."""
    return get_validator().validate_amount(amount)


def validate_address(address: str) -> ValidationResult:
    """Validate a Solana address."""
    return get_validator().validate_solana_address(address)


def is_safe_string(value: str) -> bool:
    """Check if a string is safe (no attack patterns)."""
    return get_validator().validate_safe_string(value).valid
