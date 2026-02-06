"""
JARVIS Validation Module

Comprehensive validation framework for input validation across the system.

Components:
- validators: Original decorator-based validators (RequiredValidator, etc.)
- rules: Rule classes for schema-based validation (Required, String, etc.)
- schema: Schema definition for structured validation
- validator: DataValidator class for validating against schemas
- sanitizer: Input sanitization utilities

Usage:
    # Original validators (decorator-based)
    from core.validation import ValidationError, SolanaAddressValidator

    # New schema-based validation
    from core.validation.rules import Required, String, Email
    from core.validation.schema import Schema
    from core.validation.validator import DataValidator
    from core.validation.sanitizer import Sanitizer
"""

from .validators import (
    # Exceptions
    ValidationError,
    MultiValidationError,

    # Base
    Validator,

    # Generic validators
    RequiredValidator,
    TypeValidator,
    RangeValidator,
    LengthValidator,
    RegexValidator,
    ChoiceValidator,
    EmailValidator,
    URLValidator,

    # Solana validators
    SolanaAddressValidator,
    SolanaAmountValidator,
    TokenMintValidator,

    # Telegram validators
    TelegramUserIdValidator,
    TelegramChatIdValidator,

    # Trading validators
    SlippageValidator,
    PriorityFeeValidator,

    # Composite validators
    ChainValidator,
    OptionalValidator,
    ListValidator,

    # Decorator
    validate_params,

    # Convenience functions
    validate_solana_address,
    validate_sol_amount,
    validate_telegram_user,
    validate_slippage,
)

# New validation framework components
from .rules import (
    Rule,
    RuleResult,
    RuleError,
    Required,
    Optional as OptionalRule,
    String,
    Integer,
    Float,
    Boolean,
    MinLength,
    MaxLength,
    Pattern,
    Min,
    Max,
    Range,
    Email,
    URL,
    UUID,
    Custom,
)

from .schema import Schema

from .validator import (
    ValidationError as SchemaValidationError,
    ValidationResult,
    DataValidator,
)

from .sanitizer import Sanitizer

__all__ = [
    # Original validators
    "ValidationError",
    "MultiValidationError",
    "Validator",
    "RequiredValidator",
    "TypeValidator",
    "RangeValidator",
    "LengthValidator",
    "RegexValidator",
    "ChoiceValidator",
    "EmailValidator",
    "URLValidator",
    "SolanaAddressValidator",
    "SolanaAmountValidator",
    "TokenMintValidator",
    "TelegramUserIdValidator",
    "TelegramChatIdValidator",
    "SlippageValidator",
    "PriorityFeeValidator",
    "ChainValidator",
    "OptionalValidator",
    "ListValidator",
    "validate_params",
    "validate_solana_address",
    "validate_sol_amount",
    "validate_telegram_user",
    "validate_slippage",
    # New validation framework
    "Rule",
    "RuleResult",
    "RuleError",
    "Required",
    "OptionalRule",
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
    "Schema",
    "SchemaValidationError",
    "ValidationResult",
    "DataValidator",
    "Sanitizer",
]
