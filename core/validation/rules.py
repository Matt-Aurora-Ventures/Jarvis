"""
JARVIS Validation Rules Module

Provides reusable validation rules for data validation.

Rules:
- Required, Optional: Presence validation
- String, Integer, Float, Boolean: Type validation
- MinLength, MaxLength, Pattern: String validation
- Min, Max, Range: Numeric validation
- Email, URL, UUID: Format validation
- Custom: Custom function validation

Usage:
    from core.validation.rules import Required, String, MinLength

    rules = [Required(), String(), MinLength(3)]
    for rule in rules:
        result = rule.validate(value)
        if not result.is_valid:
            print(result.errors)
"""

import re
import uuid as uuid_module
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, List, Optional, Pattern


@dataclass
class RuleError:
    """Represents a validation error from a rule."""
    message: str
    code: str = ""

    def __str__(self) -> str:
        return self.message


@dataclass
class RuleResult:
    """Result of a rule validation."""
    is_valid: bool
    errors: List[RuleError] = field(default_factory=list)
    value: Any = None

    @staticmethod
    def success(value: Any = None) -> "RuleResult":
        """Create a successful result."""
        return RuleResult(is_valid=True, errors=[], value=value)

    @staticmethod
    def failure(message: str, code: str = "") -> "RuleResult":
        """Create a failure result."""
        return RuleResult(
            is_valid=False,
            errors=[RuleError(message=message, code=code)],
            value=None
        )


class Rule(ABC):
    """Base class for all validation rules."""

    @abstractmethod
    def validate(self, value: Any) -> RuleResult:
        """Validate a value against this rule."""
        pass

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}()"


class Required(Rule):
    """
    Validates that a value is present (not None and not empty string).

    Args:
        message: Custom error message
        allow_empty: If True, allow empty strings (default False)
    """

    def __init__(self, message: Optional[str] = None, allow_empty: bool = False):
        self.message = message or "This field is required"
        self.allow_empty = allow_empty

    def validate(self, value: Any) -> RuleResult:
        if value is None:
            return RuleResult.failure(self.message, code="REQUIRED")

        if not self.allow_empty and value == "":
            return RuleResult.failure(self.message, code="REQUIRED")

        return RuleResult.success(value)


class Optional(Rule):
    """
    Marks a field as optional. Always passes validation.

    Args:
        default: Default value to use when value is None
    """

    def __init__(self, default: Any = None):
        self.default = default

    def validate(self, value: Any) -> RuleResult:
        if value is None:
            return RuleResult.success(self.default)
        return RuleResult.success(value)


class String(Rule):
    """
    Validates that a value is a string.

    Args:
        coerce: If True, attempt to convert value to string
    """

    def __init__(self, coerce: bool = False):
        self.coerce = coerce

    def validate(self, value: Any) -> RuleResult:
        if isinstance(value, str):
            return RuleResult.success(value)

        if self.coerce:
            try:
                coerced = str(value)
                return RuleResult.success(coerced)
            except (ValueError, TypeError) as e:
                return RuleResult.failure(f"Cannot convert to string: {e}", code="TYPE_ERROR")

        return RuleResult.failure(
            f"Expected string, got {type(value).__name__}",
            code="TYPE_ERROR"
        )


class Integer(Rule):
    """
    Validates that a value is an integer.

    Args:
        coerce: If True, attempt to convert value to int
    """

    def __init__(self, coerce: bool = False):
        self.coerce = coerce

    def validate(self, value: Any) -> RuleResult:
        if isinstance(value, bool):
            # Booleans are technically ints in Python, but we don't want them
            return RuleResult.failure("Expected integer, got boolean", code="TYPE_ERROR")

        if isinstance(value, int):
            return RuleResult.success(value)

        if self.coerce:
            try:
                coerced = int(value)
                return RuleResult.success(coerced)
            except (ValueError, TypeError) as e:
                return RuleResult.failure(f"Cannot convert to integer: {e}", code="TYPE_ERROR")

        return RuleResult.failure(
            f"Expected integer, got {type(value).__name__}",
            code="TYPE_ERROR"
        )


class Float(Rule):
    """
    Validates that a value is a float (or int, which is coercible to float).

    Args:
        coerce: If True, attempt to convert value to float
    """

    def __init__(self, coerce: bool = False):
        self.coerce = coerce

    def validate(self, value: Any) -> RuleResult:
        if isinstance(value, bool):
            return RuleResult.failure("Expected float, got boolean", code="TYPE_ERROR")

        if isinstance(value, (int, float)):
            return RuleResult.success(float(value))

        if self.coerce:
            try:
                coerced = float(value)
                return RuleResult.success(coerced)
            except (ValueError, TypeError) as e:
                return RuleResult.failure(f"Cannot convert to float: {e}", code="TYPE_ERROR")

        return RuleResult.failure(
            f"Expected float, got {type(value).__name__}",
            code="TYPE_ERROR"
        )


class Boolean(Rule):
    """
    Validates that a value is a boolean.

    Args:
        coerce: If True, attempt to convert string values to bool
    """

    TRUTHY_VALUES = {"true", "yes", "1", "on"}
    FALSY_VALUES = {"false", "no", "0", "off"}

    def __init__(self, coerce: bool = False):
        self.coerce = coerce

    def validate(self, value: Any) -> RuleResult:
        if isinstance(value, bool):
            return RuleResult.success(value)

        if self.coerce:
            if isinstance(value, str):
                lower_value = value.lower()
                if lower_value in self.TRUTHY_VALUES:
                    return RuleResult.success(True)
                if lower_value in self.FALSY_VALUES:
                    return RuleResult.success(False)

            return RuleResult.failure(
                f"Cannot convert '{value}' to boolean",
                code="TYPE_ERROR"
            )

        return RuleResult.failure(
            f"Expected boolean, got {type(value).__name__}",
            code="TYPE_ERROR"
        )


class MinLength(Rule):
    """
    Validates that a value has at least the specified length.

    Args:
        min_len: Minimum length required
        message: Custom error message
    """

    def __init__(self, min_len: int, message: Optional[str] = None):
        self.min_len = min_len
        self.message = message

    def validate(self, value: Any) -> RuleResult:
        if not hasattr(value, '__len__'):
            return RuleResult.failure("Value must have a length", code="LENGTH_ERROR")

        if len(value) < self.min_len:
            msg = self.message or f"Must be at least {self.min_len} characters"
            return RuleResult.failure(msg, code="MIN_LENGTH")

        return RuleResult.success(value)

    def __repr__(self) -> str:
        return f"MinLength({self.min_len})"


class MaxLength(Rule):
    """
    Validates that a value has at most the specified length.

    Args:
        max_len: Maximum length allowed
        message: Custom error message
    """

    def __init__(self, max_len: int, message: Optional[str] = None):
        self.max_len = max_len
        self.message = message

    def validate(self, value: Any) -> RuleResult:
        if not hasattr(value, '__len__'):
            return RuleResult.failure("Value must have a length", code="LENGTH_ERROR")

        if len(value) > self.max_len:
            msg = self.message or f"Must be at most {self.max_len} characters"
            return RuleResult.failure(msg, code="MAX_LENGTH")

        return RuleResult.success(value)

    def __repr__(self) -> str:
        return f"MaxLength({self.max_len})"


class Pattern(Rule):
    """
    Validates that a string matches a regex pattern.

    Args:
        pattern: Regular expression pattern
        message: Custom error message
    """

    def __init__(self, pattern: str, message: Optional[str] = None):
        self.pattern_str = pattern
        self.pattern: Pattern = re.compile(pattern)
        self.message = message or f"Must match pattern: {pattern}"

    def validate(self, value: Any) -> RuleResult:
        if not isinstance(value, str):
            return RuleResult.failure("Expected string for pattern matching", code="TYPE_ERROR")

        if not self.pattern.match(value):
            return RuleResult.failure(self.message, code="PATTERN_MISMATCH")

        return RuleResult.success(value)

    def __repr__(self) -> str:
        return f"Pattern({self.pattern_str!r})"


class Min(Rule):
    """
    Validates that a numeric value is at least the minimum.

    Args:
        min_value: Minimum value
        exclusive: If True, value must be strictly greater than min
        message: Custom error message
    """

    def __init__(self, min_value: float, exclusive: bool = False, message: Optional[str] = None):
        self.min_value = min_value
        self.exclusive = exclusive
        self.message = message

    def validate(self, value: Any) -> RuleResult:
        if not isinstance(value, (int, float)):
            return RuleResult.failure("Expected numeric value", code="TYPE_ERROR")

        if self.exclusive:
            if value <= self.min_value:
                msg = self.message or f"Must be greater than {self.min_value}"
                return RuleResult.failure(msg, code="MIN_EXCLUSIVE")
        else:
            if value < self.min_value:
                msg = self.message or f"Must be at least {self.min_value}"
                return RuleResult.failure(msg, code="MIN")

        return RuleResult.success(value)

    def __repr__(self) -> str:
        return f"Min({self.min_value}, exclusive={self.exclusive})"


class Max(Rule):
    """
    Validates that a numeric value is at most the maximum.

    Args:
        max_value: Maximum value
        exclusive: If True, value must be strictly less than max
        message: Custom error message
    """

    def __init__(self, max_value: float, exclusive: bool = False, message: Optional[str] = None):
        self.max_value = max_value
        self.exclusive = exclusive
        self.message = message

    def validate(self, value: Any) -> RuleResult:
        if not isinstance(value, (int, float)):
            return RuleResult.failure("Expected numeric value", code="TYPE_ERROR")

        if self.exclusive:
            if value >= self.max_value:
                msg = self.message or f"Must be less than {self.max_value}"
                return RuleResult.failure(msg, code="MAX_EXCLUSIVE")
        else:
            if value > self.max_value:
                msg = self.message or f"Must be at most {self.max_value}"
                return RuleResult.failure(msg, code="MAX")

        return RuleResult.success(value)

    def __repr__(self) -> str:
        return f"Max({self.max_value}, exclusive={self.exclusive})"


class Range(Rule):
    """
    Validates that a numeric value is within a range.

    Args:
        min_value: Minimum value (inclusive)
        max_value: Maximum value (inclusive)
        message: Custom error message
    """

    def __init__(self, min_value: float, max_value: float, message: Optional[str] = None):
        self.min_value = min_value
        self.max_value = max_value
        self.message = message

    def validate(self, value: Any) -> RuleResult:
        if not isinstance(value, (int, float)):
            return RuleResult.failure("Expected numeric value", code="TYPE_ERROR")

        if value < self.min_value:
            msg = self.message or f"Must be at least {self.min_value}"
            return RuleResult.failure(msg, code="RANGE_MIN")

        if value > self.max_value:
            msg = self.message or f"Must be at most {self.max_value}"
            return RuleResult.failure(msg, code="RANGE_MAX")

        return RuleResult.success(value)

    def __repr__(self) -> str:
        return f"Range({self.min_value}, {self.max_value})"


class Email(Rule):
    """
    Validates that a string is a valid email address.

    Args:
        message: Custom error message
    """

    EMAIL_PATTERN = re.compile(
        r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    )

    def __init__(self, message: Optional[str] = None):
        self.message = message or "Invalid email format"

    def validate(self, value: Any) -> RuleResult:
        if not isinstance(value, str):
            return RuleResult.failure("Expected string", code="TYPE_ERROR")

        if not self.EMAIL_PATTERN.match(value):
            return RuleResult.failure(self.message, code="INVALID_EMAIL")

        return RuleResult.success(value.lower())


class URL(Rule):
    """
    Validates that a string is a valid URL.

    Args:
        require_https: If True, only HTTPS URLs are valid
        message: Custom error message
    """

    URL_PATTERN = re.compile(
        r'^https?://'
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'
        r'localhost|'
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'
        r'(?::\d+)?'
        r'(?:/?|[/?]\S+)$',
        re.IGNORECASE
    )

    def __init__(self, require_https: bool = False, message: Optional[str] = None):
        self.require_https = require_https
        self.message = message or "Invalid URL format"

    def validate(self, value: Any) -> RuleResult:
        if not isinstance(value, str):
            return RuleResult.failure("Expected string", code="TYPE_ERROR")

        if self.require_https and not value.startswith("https://"):
            return RuleResult.failure("HTTPS required", code="HTTPS_REQUIRED")

        if not self.URL_PATTERN.match(value):
            return RuleResult.failure(self.message, code="INVALID_URL")

        return RuleResult.success(value)


class UUID(Rule):
    """
    Validates that a string is a valid UUID.

    Args:
        message: Custom error message
    """

    def __init__(self, message: Optional[str] = None):
        self.message = message or "Invalid UUID format"

    def validate(self, value: Any) -> RuleResult:
        if not isinstance(value, str):
            return RuleResult.failure("Expected string", code="TYPE_ERROR")

        try:
            uuid_module.UUID(value)
            return RuleResult.success(value)
        except ValueError:
            return RuleResult.failure(self.message, code="INVALID_UUID")


class Custom(Rule):
    """
    Validates using a custom function.

    Args:
        func: Function that takes a value and returns True/False
        message: Custom error message

    Example:
        def is_even(x):
            return x % 2 == 0

        rule = Custom(is_even, message="Must be an even number")
    """

    def __init__(self, func: Callable[[Any], bool], message: Optional[str] = None):
        self.func = func
        self.message = message or "Custom validation failed"

    def validate(self, value: Any) -> RuleResult:
        try:
            if self.func(value):
                return RuleResult.success(value)
            return RuleResult.failure(self.message, code="CUSTOM_VALIDATION")
        except Exception as e:
            return RuleResult.failure(f"Validation error: {e}", code="CUSTOM_ERROR")

    def __repr__(self) -> str:
        return f"Custom({self.func.__name__ if hasattr(self.func, '__name__') else 'fn'})"


# Re-export all rules for convenient importing
__all__ = [
    "Rule",
    "RuleResult",
    "RuleError",
    "Required",
    "Optional",
    "String",
    "Integer",
    "Float",
    "Boolean",
    "MinLength",
    "MaxLength",
    "Pattern",
    "Min",
    "Max",
    "Range",
    "Email",
    "URL",
    "UUID",
    "Custom",
]
