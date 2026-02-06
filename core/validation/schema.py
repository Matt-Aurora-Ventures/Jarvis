"""
JARVIS Validation Schema Module

Provides the Schema class for defining validation schemas.

Classes:
- Schema: Define validation schemas for data structures

Usage:
    from core.validation.schema import Schema
    from core.validation.rules import Required, String, Email, Integer, Min

    # Define a user schema
    user_schema = Schema(name="UserSchema")
    user_schema.define("name", [Required(), String()])
    user_schema.define("email", [Required(), Email()])
    user_schema.define("age", [Required(), Integer(), Min(0)])

    # Extend a schema
    admin_schema = Schema(name="AdminSchema").extend(user_schema)
    admin_schema.define("role", [Required(), String()])

    # Convert to dict for documentation
    schema_dict = user_schema.to_dict()
"""

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union, TYPE_CHECKING

if TYPE_CHECKING:
    from core.validation.rules import Rule
    from core.validation.validator import ValidationResult


@dataclass
class Schema:
    """
    Defines a validation schema for data structures.

    Args:
        name: Optional name for the schema

    Example:
        schema = Schema(name="UserSchema")
        schema.define("username", [Required(), String(), MinLength(3)])
        schema.define("email", [Required(), Email()])

        result = schema.validate({"username": "john", "email": "john@example.com"})
    """
    name: Optional[str] = None
    fields: Dict[str, List["Rule"]] = field(default_factory=dict)

    def define(self, field_name: str, rules: Union["Rule", List["Rule"]]) -> "Schema":
        """
        Define validation rules for a field.

        Args:
            field_name: Name of the field
            rules: Single rule or list of rules to apply

        Returns:
            Self for method chaining

        Example:
            schema.define("name", [Required(), String()])
            schema.define("age", Integer())
        """
        if not isinstance(rules, list):
            rules = [rules]

        self.fields[field_name] = rules
        return self

    def extend(self, parent: "Schema") -> "Schema":
        """
        Extend this schema with fields from a parent schema.

        Args:
            parent: Parent schema to inherit fields from

        Returns:
            Self for method chaining

        Note:
            Fields defined in this schema will override parent fields.

        Example:
            base_schema = Schema()
            base_schema.define("id", [Required(), Integer()])

            extended = Schema().extend(base_schema)
            extended.define("name", [Required(), String()])
        """
        # Deep copy parent fields to avoid modifying parent
        parent_fields = deepcopy(parent.fields)

        # Merge: parent fields first, then our fields (which override)
        merged_fields = {**parent_fields, **self.fields}
        self.fields = merged_fields

        return self

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert schema to dictionary representation.

        Returns:
            Dictionary with schema name and field definitions

        Example:
            {
                "name": "UserSchema",
                "fields": {
                    "username": {
                        "rules": ["Required", "String", "MinLength(3)"]
                    }
                }
            }
        """
        result: Dict[str, Any] = {}

        if self.name:
            result["name"] = self.name

        result["fields"] = {}

        for field_name, rules in self.fields.items():
            rule_descriptions = []
            for rule in rules:
                rule_descriptions.append(repr(rule))

            result["fields"][field_name] = {
                "rules": rule_descriptions
            }

        return result

    def validate(self, data: Dict[str, Any]) -> "ValidationResult":
        """
        Validate data against this schema.

        Args:
            data: Dictionary of data to validate

        Returns:
            ValidationResult with is_valid status and any errors

        Note:
            This is a convenience method that creates a DataValidator internally.
            For repeated validations, create a DataValidator instance directly.
        """
        from core.validation.validator import DataValidator, ValidationResult, ValidationError

        errors: List[ValidationError] = []
        validated_data: Dict[str, Any] = {}

        for field_name, rules in self.fields.items():
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
            field_valid = True

            for rule in rules:
                # Skip Optional rule in validation
                if rule.__class__.__name__ == "Optional":
                    continue

                result = rule.validate(current_value)

                if not result.is_valid:
                    for rule_error in result.errors:
                        errors.append(ValidationError(
                            field=field_name,
                            message=rule_error.message,
                            code=rule_error.code,
                            value=value
                        ))
                    field_valid = False
                    break
                else:
                    current_value = result.value

            if field_valid:
                validated_data[field_name] = current_value

        if errors:
            return ValidationResult(is_valid=False, errors=errors, value=None)

        return ValidationResult(is_valid=True, errors=[], value=validated_data)

    def __repr__(self) -> str:
        name_str = f"name={self.name!r}" if self.name else ""
        fields_count = len(self.fields)
        return f"Schema({name_str}, fields={fields_count})"


# Re-export for convenient importing
__all__ = [
    "Schema",
]
