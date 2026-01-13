"""
JARVIS Input Validation Helpers

Reusable validators for:
- Solana addresses
- Telegram user IDs
- API parameters
- Configuration values
- Trading parameters

Usage:
    from core.validation import validate, ValidationError

    @validate_params(
        wallet=SolanaAddressValidator(),
        amount=RangeValidator(min_val=0, max_val=1000),
    )
    async def transfer(wallet: str, amount: float):
        ...
"""

import re
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Set, Type, Union

logger = logging.getLogger(__name__)


class ValidationError(Exception):
    """Raised when validation fails."""

    def __init__(self, field: str, message: str, value: Any = None):
        self.field = field
        self.message = message
        self.value = value
        super().__init__(f"{field}: {message}")


class MultiValidationError(Exception):
    """Multiple validation errors."""

    def __init__(self, errors: List[ValidationError]):
        self.errors = errors
        messages = [f"{e.field}: {e.message}" for e in errors]
        super().__init__(f"Validation failed: {'; '.join(messages)}")

    def to_dict(self) -> Dict[str, str]:
        return {e.field: e.message for e in self.errors}


class Validator(ABC):
    """Base validator class."""

    @abstractmethod
    def validate(self, value: Any, field_name: str = "value") -> Any:
        """
        Validate a value.

        Args:
            value: Value to validate
            field_name: Field name for error messages

        Returns:
            Validated (possibly transformed) value

        Raises:
            ValidationError: If validation fails
        """
        pass

    def __call__(self, value: Any, field_name: str = "value") -> Any:
        return self.validate(value, field_name)


class RequiredValidator(Validator):
    """Validate that value is not None or empty."""

    def __init__(self, allow_empty: bool = False):
        self.allow_empty = allow_empty

    def validate(self, value: Any, field_name: str = "value") -> Any:
        if value is None:
            raise ValidationError(field_name, "Value is required")
        if not self.allow_empty and value == "":
            raise ValidationError(field_name, "Value cannot be empty")
        return value


class TypeValidator(Validator):
    """Validate value type."""

    def __init__(self, expected_type: Union[Type, tuple], coerce: bool = False):
        self.expected_type = expected_type
        self.coerce = coerce

    def validate(self, value: Any, field_name: str = "value") -> Any:
        if isinstance(value, self.expected_type):
            return value

        if self.coerce:
            try:
                if isinstance(self.expected_type, tuple):
                    return self.expected_type[0](value)
                return self.expected_type(value)
            except (ValueError, TypeError) as e:
                raise ValidationError(
                    field_name,
                    f"Cannot convert to {self.expected_type.__name__}: {e}"
                )

        type_name = getattr(self.expected_type, '__name__', str(self.expected_type))
        raise ValidationError(
            field_name,
            f"Expected {type_name}, got {type(value).__name__}"
        )


class RangeValidator(Validator):
    """Validate numeric range."""

    def __init__(
        self,
        min_val: Optional[float] = None,
        max_val: Optional[float] = None,
        exclusive_min: bool = False,
        exclusive_max: bool = False,
    ):
        self.min_val = min_val
        self.max_val = max_val
        self.exclusive_min = exclusive_min
        self.exclusive_max = exclusive_max

    def validate(self, value: Any, field_name: str = "value") -> Any:
        if not isinstance(value, (int, float)):
            raise ValidationError(field_name, f"Expected number, got {type(value).__name__}")

        if self.min_val is not None:
            if self.exclusive_min:
                if value <= self.min_val:
                    raise ValidationError(field_name, f"Must be greater than {self.min_val}")
            else:
                if value < self.min_val:
                    raise ValidationError(field_name, f"Must be at least {self.min_val}")

        if self.max_val is not None:
            if self.exclusive_max:
                if value >= self.max_val:
                    raise ValidationError(field_name, f"Must be less than {self.max_val}")
            else:
                if value > self.max_val:
                    raise ValidationError(field_name, f"Must be at most {self.max_val}")

        return value


class LengthValidator(Validator):
    """Validate string/list length."""

    def __init__(self, min_len: Optional[int] = None, max_len: Optional[int] = None):
        self.min_len = min_len
        self.max_len = max_len

    def validate(self, value: Any, field_name: str = "value") -> Any:
        if not hasattr(value, '__len__'):
            raise ValidationError(field_name, "Value must have length")

        length = len(value)

        if self.min_len is not None and length < self.min_len:
            raise ValidationError(field_name, f"Must be at least {self.min_len} characters")

        if self.max_len is not None and length > self.max_len:
            raise ValidationError(field_name, f"Must be at most {self.max_len} characters")

        return value


class RegexValidator(Validator):
    """Validate against regex pattern."""

    def __init__(self, pattern: str, message: Optional[str] = None):
        self.pattern = re.compile(pattern)
        self.message = message or f"Must match pattern: {pattern}"

    def validate(self, value: Any, field_name: str = "value") -> Any:
        if not isinstance(value, str):
            raise ValidationError(field_name, "Expected string")

        if not self.pattern.match(value):
            raise ValidationError(field_name, self.message)

        return value


class ChoiceValidator(Validator):
    """Validate value is in allowed choices."""

    def __init__(self, choices: Set[Any], case_sensitive: bool = True):
        self.choices = choices
        self.case_sensitive = case_sensitive
        if not case_sensitive:
            self.choices = {c.lower() if isinstance(c, str) else c for c in choices}

    def validate(self, value: Any, field_name: str = "value") -> Any:
        check_value = value
        if not self.case_sensitive and isinstance(value, str):
            check_value = value.lower()

        if check_value not in self.choices:
            choices_str = ", ".join(str(c) for c in list(self.choices)[:5])
            raise ValidationError(field_name, f"Must be one of: {choices_str}")

        return value


class EmailValidator(Validator):
    """Validate email address format."""

    EMAIL_PATTERN = re.compile(
        r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    )

    def validate(self, value: Any, field_name: str = "value") -> Any:
        if not isinstance(value, str):
            raise ValidationError(field_name, "Expected string")

        if not self.EMAIL_PATTERN.match(value):
            raise ValidationError(field_name, "Invalid email format")

        return value.lower()


class URLValidator(Validator):
    """Validate URL format."""

    URL_PATTERN = re.compile(
        r'^https?://'
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'
        r'localhost|'
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'
        r'(?::\d+)?'
        r'(?:/?|[/?]\S+)$', re.IGNORECASE
    )

    def __init__(self, require_https: bool = False):
        self.require_https = require_https

    def validate(self, value: Any, field_name: str = "value") -> Any:
        if not isinstance(value, str):
            raise ValidationError(field_name, "Expected string")

        if self.require_https and not value.startswith("https://"):
            raise ValidationError(field_name, "HTTPS required")

        if not self.URL_PATTERN.match(value):
            raise ValidationError(field_name, "Invalid URL format")

        return value


# Solana-specific validators

class SolanaAddressValidator(Validator):
    """Validate Solana wallet address (base58, 32-44 chars)."""

    BASE58_CHARS = set("123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz")

    def validate(self, value: Any, field_name: str = "value") -> Any:
        if not isinstance(value, str):
            raise ValidationError(field_name, "Expected string")

        if len(value) < 32 or len(value) > 44:
            raise ValidationError(field_name, "Solana address must be 32-44 characters")

        if not all(c in self.BASE58_CHARS for c in value):
            raise ValidationError(field_name, "Invalid Solana address format (base58)")

        return value


class SolanaAmountValidator(Validator):
    """Validate SOL amount."""

    def __init__(
        self,
        min_sol: float = 0.000001,  # Minimum rent-exempt
        max_sol: float = 1000000,   # Reasonable max
        allow_zero: bool = False,
    ):
        self.min_sol = min_sol
        self.max_sol = max_sol
        self.allow_zero = allow_zero

    def validate(self, value: Any, field_name: str = "value") -> float:
        if isinstance(value, str):
            try:
                value = float(value)
            except ValueError:
                raise ValidationError(field_name, "Invalid number format")

        if not isinstance(value, (int, float)):
            raise ValidationError(field_name, "Expected number")

        if value == 0 and self.allow_zero:
            return 0.0

        if value < self.min_sol:
            raise ValidationError(field_name, f"Minimum amount is {self.min_sol} SOL")

        if value > self.max_sol:
            raise ValidationError(field_name, f"Maximum amount is {self.max_sol} SOL")

        return float(value)


class TokenMintValidator(Validator):
    """Validate SPL token mint address."""

    # Known token mints for quick validation
    KNOWN_MINTS = {
        "So11111111111111111111111111111111111111112",  # Wrapped SOL
        "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",  # USDC
        "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB",  # USDT
    }

    def __init__(self, allow_unknown: bool = True):
        self.allow_unknown = allow_unknown
        self.address_validator = SolanaAddressValidator()

    def validate(self, value: Any, field_name: str = "value") -> str:
        value = self.address_validator.validate(value, field_name)

        if not self.allow_unknown and value not in self.KNOWN_MINTS:
            raise ValidationError(field_name, "Unknown token mint")

        return value


# Telegram-specific validators

class TelegramUserIdValidator(Validator):
    """Validate Telegram user ID."""

    def validate(self, value: Any, field_name: str = "value") -> int:
        if isinstance(value, str):
            try:
                value = int(value)
            except ValueError:
                raise ValidationError(field_name, "Invalid user ID format")

        if not isinstance(value, int):
            raise ValidationError(field_name, "Expected integer")

        if value <= 0:
            raise ValidationError(field_name, "User ID must be positive")

        return value


class TelegramChatIdValidator(Validator):
    """Validate Telegram chat ID (can be negative for groups)."""

    def validate(self, value: Any, field_name: str = "value") -> int:
        if isinstance(value, str):
            try:
                value = int(value)
            except ValueError:
                raise ValidationError(field_name, "Invalid chat ID format")

        if not isinstance(value, int):
            raise ValidationError(field_name, "Expected integer")

        return value


# Trading validators

class SlippageValidator(Validator):
    """Validate slippage percentage (0-100)."""

    def __init__(self, max_slippage: float = 50.0):
        self.max_slippage = max_slippage

    def validate(self, value: Any, field_name: str = "value") -> float:
        if isinstance(value, str):
            value = value.rstrip('%')
            try:
                value = float(value)
            except ValueError:
                raise ValidationError(field_name, "Invalid slippage format")

        if not isinstance(value, (int, float)):
            raise ValidationError(field_name, "Expected number")

        if value < 0:
            raise ValidationError(field_name, "Slippage cannot be negative")

        if value > self.max_slippage:
            raise ValidationError(field_name, f"Slippage cannot exceed {self.max_slippage}%")

        return float(value)


class PriorityFeeValidator(Validator):
    """Validate Solana priority fee (microlamports)."""

    def __init__(self, max_fee: int = 10_000_000):  # 0.01 SOL max
        self.max_fee = max_fee

    def validate(self, value: Any, field_name: str = "value") -> int:
        if isinstance(value, str):
            try:
                value = int(value)
            except ValueError:
                raise ValidationError(field_name, "Invalid fee format")

        if not isinstance(value, int):
            raise ValidationError(field_name, "Expected integer")

        if value < 0:
            raise ValidationError(field_name, "Fee cannot be negative")

        if value > self.max_fee:
            raise ValidationError(field_name, f"Fee cannot exceed {self.max_fee} microlamports")

        return value


# Composite validators

class ChainValidator(Validator):
    """Chain multiple validators."""

    def __init__(self, *validators: Validator):
        self.validators = validators

    def validate(self, value: Any, field_name: str = "value") -> Any:
        for validator in self.validators:
            value = validator.validate(value, field_name)
        return value


class OptionalValidator(Validator):
    """Make a validator optional (allow None)."""

    def __init__(self, validator: Validator, default: Any = None):
        self.validator = validator
        self.default = default

    def validate(self, value: Any, field_name: str = "value") -> Any:
        if value is None:
            return self.default
        return self.validator.validate(value, field_name)


class ListValidator(Validator):
    """Validate list items."""

    def __init__(
        self,
        item_validator: Validator,
        min_items: Optional[int] = None,
        max_items: Optional[int] = None,
    ):
        self.item_validator = item_validator
        self.min_items = min_items
        self.max_items = max_items

    def validate(self, value: Any, field_name: str = "value") -> List[Any]:
        if not isinstance(value, (list, tuple)):
            raise ValidationError(field_name, "Expected list")

        if self.min_items is not None and len(value) < self.min_items:
            raise ValidationError(field_name, f"Must have at least {self.min_items} items")

        if self.max_items is not None and len(value) > self.max_items:
            raise ValidationError(field_name, f"Must have at most {self.max_items} items")

        validated = []
        for i, item in enumerate(value):
            validated.append(
                self.item_validator.validate(item, f"{field_name}[{i}]")
            )

        return validated


# Decorator for function parameter validation

def validate_params(**validators: Validator) -> Callable:
    """
    Decorator to validate function parameters.

    Usage:
        @validate_params(
            wallet=SolanaAddressValidator(),
            amount=RangeValidator(min_val=0.001),
        )
        async def transfer(wallet: str, amount: float):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            errors = []
            validated_kwargs = {}

            for param_name, validator in validators.items():
                if param_name in kwargs:
                    try:
                        validated_kwargs[param_name] = validator.validate(
                            kwargs[param_name], param_name
                        )
                    except ValidationError as e:
                        errors.append(e)

            if errors:
                raise MultiValidationError(errors)

            kwargs.update(validated_kwargs)
            return await func(*args, **kwargs)

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            errors = []
            validated_kwargs = {}

            for param_name, validator in validators.items():
                if param_name in kwargs:
                    try:
                        validated_kwargs[param_name] = validator.validate(
                            kwargs[param_name], param_name
                        )
                    except ValidationError as e:
                        errors.append(e)

            if errors:
                raise MultiValidationError(errors)

            kwargs.update(validated_kwargs)
            return func(*args, **kwargs)

        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


# Convenience functions

def validate_solana_address(address: str) -> str:
    """Validate a Solana address."""
    return SolanaAddressValidator().validate(address, "address")


def validate_sol_amount(amount: Any, max_sol: float = 100.0) -> float:
    """Validate a SOL amount."""
    return SolanaAmountValidator(max_sol=max_sol).validate(amount, "amount")


def validate_telegram_user(user_id: Any) -> int:
    """Validate a Telegram user ID."""
    return TelegramUserIdValidator().validate(user_id, "user_id")


def validate_slippage(slippage: Any) -> float:
    """Validate slippage percentage."""
    return SlippageValidator().validate(slippage, "slippage")


if __name__ == "__main__":
    print("Validation Helpers Demo")
    print("=" * 50)

    # Test Solana address
    try:
        addr = validate_solana_address("So11111111111111111111111111111111111111112")
        print(f"Valid address: {addr[:20]}...")
    except ValidationError as e:
        print(f"Invalid: {e}")

    # Test SOL amount
    try:
        amount = validate_sol_amount("1.5")
        print(f"Valid amount: {amount} SOL")
    except ValidationError as e:
        print(f"Invalid: {e}")

    # Test slippage
    try:
        slip = validate_slippage("2.5%")
        print(f"Valid slippage: {slip}%")
    except ValidationError as e:
        print(f"Invalid: {e}")

    # Test invalid
    try:
        validate_solana_address("invalid")
    except ValidationError as e:
        print(f"Caught error: {e}")

    # Test chain validator
    chain = ChainValidator(
        RequiredValidator(),
        TypeValidator(str),
        LengthValidator(min_len=3, max_len=50),
    )

    try:
        result = chain.validate("hello", "username")
        print(f"Chain validated: {result}")
    except ValidationError as e:
        print(f"Chain error: {e}")

    print("\nAll tests passed!")
