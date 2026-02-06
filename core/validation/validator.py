"""
JARVIS Data Validator Module

Provides the main DataValidator class for validating data against schemas.

Classes:
- ValidationError: Represents a single validation error
- ValidationResult: Contains validation status and errors
- DataValidator: Main validator class

Usage:
    from core.validation.validator import DataValidator
    from core.validation.schema import Schema
    from core.validation.rules import Required, String

    schema = Schema()
    schema.define("name", [Required(), String()])

    validator = DataValidator(schema)
    result = validator.validate({"name": "John"})

    if result.is_valid:
        print("Valid!")
    else:
        for error in result.errors:
            print(f"{error.field}: {error.message}")
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from core.validation.schema import Schema


@dataclass
class ValidationError:
    """
    Represents a single validation error.

    Attributes:
        field: The field name that failed validation
        message: Human-readable error message
        code: Machine-readable error code
        value: The value that failed validation (optional)
    """
    field: str
    message: str
    code: str = ""
    value: Any = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary representation."""
        result = {
            "field": self.field,
            "message": self.message,
        }
        if self.code:
            result["code"] = self.code
        if self.value is not None:
            result["value"] = self.value
        return result

    def __str__(self) -> str:
        return f"{self.field}: {self.message}"


@dataclass
class ValidationResult:
    """
    Result of a validation operation.

    Attributes:
        is_valid: True if validation passed
        errors: List of validation errors
        value: The validated (possibly transformed) data
    """
    is_valid: bool
    errors: List[ValidationError] = field(default_factory=list)
    value: Any = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary representation."""
        return {
            "is_valid": self.is_valid,
            "errors": [e.to_dict() for e in self.errors],
            "value": self.value,
        }

    @staticmethod
    def success(value: Any = None) -> "ValidationResult":
        """Create a successful validation result."""
        return ValidationResult(is_valid=True, errors=[], value=value)

    @staticmethod
    def failure(errors: List[ValidationError]) -> "ValidationResult":
        """Create a failed validation result."""
        return ValidationResult(is_valid=False, errors=errors, value=None)


class DataValidator:
    """
    Validates data against a schema.

    Args:
        schema: The Schema to validate against
        fail_fast: If True, stop on first error (default False)

    Example:
        schema = Schema()
        schema.define("name", [Required(), String()])
        schema.define("age", [Required(), Integer(), Min(0)])

        validator = DataValidator(schema)

        # Check if valid
        if validator.is_valid({"name": "John", "age": 30}):
            print("Valid!")

        # Get all errors
        errors = validator.get_errors({"name": "", "age": -5})
        for error in errors:
            print(f"{error.field}: {error.message}")

        # Full validation with result
        result = validator.validate(data)
        if not result.is_valid:
            for error in result.errors:
                print(error)
    """

    def __init__(self, schema: "Schema", fail_fast: bool = False):
        self.schema = schema
        self.fail_fast = fail_fast

    def validate(self, data: Dict[str, Any]) -> ValidationResult:
        """
        Validate data against the schema.

        Args:
            data: Dictionary of data to validate

        Returns:
            ValidationResult with is_valid status and any errors
        """
        errors: List[ValidationError] = []
        validated_data: Dict[str, Any] = {}

        for field_name, rules in self.schema.fields.items():
            value = data.get(field_name)

            # Track if this field should be skipped due to Optional rule
            is_optional = False
            default_value = None

            # First pass: check for Optional rule
            for rule in rules:
                if rule.__class__.__name__ == "Optional":
                    is_optional = True
                    default_value = getattr(rule, 'default', None)
                    break

            # If value is None and field is optional, use default
            if value is None and is_optional:
                validated_data[field_name] = default_value
                continue

            # Validate against all rules
            current_value = value
            field_errors: List[ValidationError] = []

            for rule in rules:
                # Skip Optional rule in validation (it's a marker, not a real validator)
                if rule.__class__.__name__ == "Optional":
                    continue

                result = rule.validate(current_value)

                if not result.is_valid:
                    for rule_error in result.errors:
                        field_errors.append(ValidationError(
                            field=field_name,
                            message=rule_error.message,
                            code=rule_error.code,
                            value=value
                        ))

                    if self.fail_fast:
                        errors.extend(field_errors)
                        return ValidationResult.failure(errors)

                    break  # Stop validating this field on first error
                else:
                    # Update value with potentially transformed value
                    current_value = result.value

            if field_errors:
                errors.extend(field_errors)
            else:
                validated_data[field_name] = current_value

        if errors:
            return ValidationResult.failure(errors)

        return ValidationResult.success(validated_data)

    def is_valid(self, data: Dict[str, Any]) -> bool:
        """
        Check if data is valid against the schema.

        Args:
            data: Dictionary of data to validate

        Returns:
            True if data is valid, False otherwise
        """
        result = self.validate(data)
        return result.is_valid

    def get_errors(self, data: Dict[str, Any]) -> List[ValidationError]:
        """
        Get all validation errors for data.

        Args:
            data: Dictionary of data to validate

        Returns:
            List of ValidationError objects (empty if valid)
        """
        result = self.validate(data)
        return result.errors


# Re-export for convenient importing
__all__ = [
    "ValidationError",
    "ValidationResult",
    "DataValidator",
]
