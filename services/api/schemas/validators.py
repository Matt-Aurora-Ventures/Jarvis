"""Custom validators and validation utilities for API schemas."""
from pydantic import validator, field_validator, BaseModel
from typing import Any, Optional, List
import re


# Common regex patterns
PATTERNS = {
    "alphanumeric": re.compile(r"^[a-zA-Z0-9_-]+$"),
    "symbol": re.compile(r"^[A-Z]{1,10}(/[A-Z]{1,10})?$"),  # e.g., SOL/USDC
    "address": re.compile(r"^[A-Za-z0-9]{32,44}$"),  # Solana address
    "uuid": re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"),
    "iso8601": re.compile(
        r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})?$"
    ),
}


# Blacklist patterns (security)
BLACKLIST_PATTERNS = [
    re.compile(r"<script", re.IGNORECASE),
    re.compile(r"javascript:", re.IGNORECASE),
    re.compile(r"on\w+\s*=", re.IGNORECASE),  # Event handlers
    re.compile(r"(union|select|insert|update|delete|drop|create|alter|exec|execute)", re.IGNORECASE),
]


def sanitize_string(value: str, max_length: Optional[int] = None) -> str:
    """
    Sanitize string input.

    - Strips leading/trailing whitespace
    - Optionally enforces max length
    - Checks for blacklisted patterns
    """
    if not isinstance(value, str):
        raise ValueError("Value must be a string")

    # Strip whitespace
    value = value.strip()

    # Check length
    if max_length and len(value) > max_length:
        raise ValueError(f"String too long (max {max_length} characters)")

    # Check for blacklisted patterns
    for pattern in BLACKLIST_PATTERNS:
        if pattern.search(value):
            raise ValueError("String contains invalid or suspicious content")

    return value


def validate_pattern(value: str, pattern_name: str) -> str:
    """Validate string against a named pattern."""
    if pattern_name not in PATTERNS:
        raise ValueError(f"Unknown pattern: {pattern_name}")

    pattern = PATTERNS[pattern_name]
    if not pattern.match(value):
        raise ValueError(f"Invalid format for {pattern_name}")

    return value


def validate_alphanumeric(value: str) -> str:
    """Validate alphanumeric string (letters, numbers, underscore, hyphen only)."""
    return validate_pattern(value, "alphanumeric")


def validate_symbol(value: str) -> str:
    """Validate trading symbol (e.g., SOL/USDC, BTC)."""
    value = value.upper().strip()
    return validate_pattern(value, "symbol")


def validate_address(value: str) -> str:
    """Validate Solana address format."""
    return validate_pattern(value, "address")


def validate_positive_number(value: float, min_value: float = 0.0) -> float:
    """Validate positive number."""
    if value <= min_value:
        raise ValueError(f"Value must be greater than {min_value}")
    return value


def validate_range(value: float, min_val: float, max_val: float) -> float:
    """Validate number is within range."""
    if value < min_val or value > max_val:
        raise ValueError(f"Value must be between {min_val} and {max_val}")
    return value


def validate_enum_list(values: List[str], allowed: List[str]) -> List[str]:
    """Validate list contains only allowed values."""
    for value in values:
        if value not in allowed:
            raise ValueError(f"Invalid value '{value}'. Allowed: {', '.join(allowed)}")
    return values


def validate_no_duplicates(values: List[Any]) -> List[Any]:
    """Validate list has no duplicates."""
    if len(values) != len(set(values)):
        raise ValueError("List contains duplicate values")
    return values


def validate_max_items(values: List[Any], max_items: int) -> List[Any]:
    """Validate list doesn't exceed max items."""
    if len(values) > max_items:
        raise ValueError(f"Too many items (max {max_items})")
    return values


class ValidatedString(str):
    """String that validates on initialization."""

    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if not isinstance(v, str):
            raise TypeError("string required")
        return sanitize_string(v, max_length=1000)


class AlphanumericString(str):
    """Alphanumeric string (a-z, A-Z, 0-9, _, -)."""

    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if not isinstance(v, str):
            raise TypeError("string required")
        return validate_alphanumeric(v)


class TradingSymbol(str):
    """Trading pair symbol (e.g., SOL/USDC)."""

    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if not isinstance(v, str):
            raise TypeError("string required")
        return validate_symbol(v)


class SolanaAddress(str):
    """Solana blockchain address."""

    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if not isinstance(v, str):
            raise TypeError("string required")
        return validate_address(v)


class PositiveFloat(float):
    """Float that must be positive."""

    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if not isinstance(v, (int, float)):
            raise TypeError("number required")
        return validate_positive_number(float(v))


class Percentage(float):
    """Percentage value (0-100)."""

    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if not isinstance(v, (int, float)):
            raise TypeError("number required")
        return validate_range(float(v), 0.0, 100.0)


# Common reusable field constraints
CONSTRAINTS = {
    "symbol": {
        "min_length": 1,
        "max_length": 20,
        "pattern": r"^[A-Z]{1,10}(/[A-Z]{1,10})?$",
        "example": "SOL/USDC",
    },
    "address": {
        "min_length": 32,
        "max_length": 44,
        "pattern": r"^[A-Za-z0-9]{32,44}$",
        "example": "9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin",
    },
    "amount": {
        "gt": 0,
        "le": 1_000_000_000,  # 1 billion max
        "example": 100.50,
    },
    "price": {
        "gt": 0,
        "le": 1_000_000,  # 1 million max
        "example": 123.45,
    },
    "percentage": {
        "ge": 0,
        "le": 100,
        "example": 25.5,
    },
    "limit": {
        "ge": 1,
        "le": 1000,
        "example": 100,
    },
    "offset": {
        "ge": 0,
        "le": 100_000,
        "example": 0,
    },
}


class PaginationMixin(BaseModel):
    """Mixin for pagination parameters with validation."""

    limit: int = 100
    offset: int = 0

    @validator("limit")
    def validate_limit(cls, v):
        return validate_range(v, 1, 1000)

    @validator("offset")
    def validate_offset(cls, v):
        return validate_range(v, 0, 100_000)


class TimestampMixin(BaseModel):
    """Mixin for timestamp fields."""

    def validate_timestamp_order(self, start_time, end_time):
        """Validate that end_time is after start_time."""
        if end_time and start_time and end_time <= start_time:
            raise ValueError("end_time must be after start_time")
