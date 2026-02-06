"""
Tests for core/validation/validator.py

Tests Validator class: validate(), is_valid(), get_errors().
"""
import pytest


class TestValidatorClass:
    """Tests for the main Validator class."""

    def test_validator_validate_returns_validation_result(self):
        """Validator.validate() returns ValidationResult."""
        from core.validation.validator import DataValidator, ValidationResult
        from core.validation.schema import Schema
        from core.validation.rules import Required, String

        schema = Schema()
        schema.define("name", [Required(), String()])

        validator = DataValidator(schema)
        result = validator.validate({"name": "John"})

        assert isinstance(result, ValidationResult)
        assert result.is_valid is True

    def test_validator_validate_with_invalid_data(self):
        """Validator.validate() returns errors for invalid data."""
        from core.validation.validator import DataValidator
        from core.validation.schema import Schema
        from core.validation.rules import Required, Integer

        schema = Schema()
        schema.define("age", [Required(), Integer()])

        validator = DataValidator(schema)
        result = validator.validate({"age": "not a number"})

        assert result.is_valid is False
        assert len(result.errors) > 0

    def test_validator_is_valid_returns_bool(self):
        """Validator.is_valid() returns boolean."""
        from core.validation.validator import DataValidator
        from core.validation.schema import Schema
        from core.validation.rules import Required, String

        schema = Schema()
        schema.define("name", [Required(), String()])

        validator = DataValidator(schema)

        assert validator.is_valid({"name": "John"}) is True
        assert validator.is_valid({"name": 123}) is False

    def test_validator_get_errors_returns_list(self):
        """Validator.get_errors() returns list of errors."""
        from core.validation.validator import DataValidator
        from core.validation.schema import Schema
        from core.validation.rules import Required, Integer, Min

        schema = Schema()
        schema.define("age", [Required(), Integer(), Min(0)])

        validator = DataValidator(schema)
        errors = validator.get_errors({"age": -5})

        assert isinstance(errors, list)
        assert len(errors) > 0
        # Each error should have field and message
        assert all(hasattr(e, 'field') for e in errors)
        assert all(hasattr(e, 'message') for e in errors)

    def test_validator_get_errors_empty_for_valid_data(self):
        """Validator.get_errors() returns empty list for valid data."""
        from core.validation.validator import DataValidator
        from core.validation.schema import Schema
        from core.validation.rules import Required, String

        schema = Schema()
        schema.define("name", [Required(), String()])

        validator = DataValidator(schema)
        errors = validator.get_errors({"name": "John"})

        assert errors == []


class TestValidationResult:
    """Tests for ValidationResult class."""

    def test_validation_result_is_valid_property(self):
        """ValidationResult.is_valid property works correctly."""
        from core.validation.validator import ValidationResult

        valid_result = ValidationResult(is_valid=True, errors=[])
        assert valid_result.is_valid is True

        invalid_result = ValidationResult(is_valid=False, errors=[])
        assert invalid_result.is_valid is False

    def test_validation_result_errors_property(self):
        """ValidationResult.errors property contains error objects."""
        from core.validation.validator import ValidationResult, ValidationError

        error = ValidationError(field="name", message="Required field")
        result = ValidationResult(is_valid=False, errors=[error])

        assert len(result.errors) == 1
        assert result.errors[0].field == "name"
        assert result.errors[0].message == "Required field"

    def test_validation_result_value_property(self):
        """ValidationResult.value contains validated/transformed value."""
        from core.validation.validator import ValidationResult

        result = ValidationResult(is_valid=True, errors=[], value={"name": "JOHN"})
        assert result.value == {"name": "JOHN"}

    def test_validation_result_to_dict(self):
        """ValidationResult.to_dict() returns dictionary representation."""
        from core.validation.validator import ValidationResult, ValidationError

        error = ValidationError(field="name", message="Required")
        result = ValidationResult(is_valid=False, errors=[error])

        result_dict = result.to_dict()
        assert "is_valid" in result_dict
        assert "errors" in result_dict
        assert result_dict["is_valid"] is False


class TestValidationError:
    """Tests for ValidationError class."""

    def test_validation_error_has_field(self):
        """ValidationError has field property."""
        from core.validation.validator import ValidationError

        error = ValidationError(field="email", message="Invalid format")
        assert error.field == "email"

    def test_validation_error_has_message(self):
        """ValidationError has message property."""
        from core.validation.validator import ValidationError

        error = ValidationError(field="email", message="Invalid format")
        assert error.message == "Invalid format"

    def test_validation_error_has_code(self):
        """ValidationError can have error code."""
        from core.validation.validator import ValidationError

        error = ValidationError(field="email", message="Invalid format", code="INVALID_EMAIL")
        assert error.code == "INVALID_EMAIL"

    def test_validation_error_to_dict(self):
        """ValidationError.to_dict() returns dictionary."""
        from core.validation.validator import ValidationError

        error = ValidationError(field="email", message="Invalid format", code="INVALID_EMAIL")
        error_dict = error.to_dict()

        assert error_dict["field"] == "email"
        assert error_dict["message"] == "Invalid format"
        assert error_dict["code"] == "INVALID_EMAIL"


class TestValidatorWithSchema:
    """Tests for Validator with Schema integration."""

    def test_validator_validates_against_schema(self):
        """Validator properly validates data against schema rules."""
        from core.validation.validator import DataValidator
        from core.validation.schema import Schema
        from core.validation.rules import Required, String, Email, Integer, Range

        schema = Schema()
        schema.define("name", [Required(), String()])
        schema.define("email", [Required(), Email()])
        schema.define("age", [Required(), Integer(), Range(0, 150)])

        validator = DataValidator(schema)

        # Valid data
        valid_data = {
            "name": "John Doe",
            "email": "john@example.com",
            "age": 30
        }
        assert validator.is_valid(valid_data) is True

        # Invalid email
        invalid_email = {
            "name": "John Doe",
            "email": "not-an-email",
            "age": 30
        }
        assert validator.is_valid(invalid_email) is False

        # Invalid age
        invalid_age = {
            "name": "John Doe",
            "email": "john@example.com",
            "age": 200
        }
        assert validator.is_valid(invalid_age) is False

    def test_validator_collects_all_errors(self):
        """Validator collects all validation errors, not just the first."""
        from core.validation.validator import DataValidator
        from core.validation.schema import Schema
        from core.validation.rules import Required, String, Integer, Min

        schema = Schema()
        schema.define("name", [Required(), String()])
        schema.define("age", [Required(), Integer(), Min(0)])
        schema.define("score", [Required(), Integer()])

        validator = DataValidator(schema)

        # Multiple invalid fields
        invalid_data = {
            "name": 123,      # Should be string
            "age": -5,        # Should be >= 0
            "score": "high"   # Should be integer
        }

        errors = validator.get_errors(invalid_data)

        # Should have errors for all three fields
        error_fields = {e.field for e in errors}
        assert "name" in error_fields
        assert "age" in error_fields
        assert "score" in error_fields


class TestValidatorStopOnFirstError:
    """Tests for Validator with fail_fast mode."""

    def test_validator_fail_fast_mode(self):
        """Validator in fail_fast mode stops on first error."""
        from core.validation.validator import DataValidator
        from core.validation.schema import Schema
        from core.validation.rules import Required, String, Integer

        schema = Schema()
        schema.define("name", [Required(), String()])
        schema.define("age", [Required(), Integer()])
        schema.define("score", [Required(), Integer()])

        validator = DataValidator(schema, fail_fast=True)

        invalid_data = {
            "name": 123,      # Error 1
            "age": "twenty",  # Error 2
            "score": "high"   # Error 3
        }

        errors = validator.get_errors(invalid_data)

        # In fail_fast mode, should only have one error
        assert len(errors) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
