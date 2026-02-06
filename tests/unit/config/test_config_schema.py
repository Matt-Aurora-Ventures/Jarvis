"""
Unit tests for ConfigSchema validation.

Tests:
- ConfigSchema class
- require() for required fields
- define types and validators
- validate(config) -> List[Error]
"""

import pytest
from typing import List, Dict, Any


class TestConfigSchemaBasics:
    """Test ConfigSchema basic functionality."""

    def test_create_empty_schema(self):
        """Empty schema should be valid."""
        from core.config.schema import ConfigSchema

        schema = ConfigSchema()
        assert schema is not None
        assert schema.fields == {}

    def test_require_field(self):
        """require() should add required field to schema."""
        from core.config.schema import ConfigSchema

        schema = ConfigSchema()
        schema.require("api_key", str)

        assert "api_key" in schema.fields
        assert schema.fields["api_key"].required is True
        assert schema.fields["api_key"].field_type is str

    def test_optional_field(self):
        """optional() should add optional field to schema."""
        from core.config.schema import ConfigSchema

        schema = ConfigSchema()
        schema.optional("debug", bool, default=False)

        assert "debug" in schema.fields
        assert schema.fields["debug"].required is False
        assert schema.fields["debug"].default is False


class TestConfigSchemaValidation:
    """Test ConfigSchema.validate() method."""

    def test_validate_valid_config(self):
        """validate() should return empty list for valid config."""
        from core.config.schema import ConfigSchema

        schema = ConfigSchema()
        schema.require("name", str)
        schema.require("port", int)

        config = {"name": "test", "port": 8080}
        errors = schema.validate(config)

        assert errors == []

    def test_validate_missing_required(self):
        """validate() should return error for missing required field."""
        from core.config.schema import ConfigSchema

        schema = ConfigSchema()
        schema.require("required_key", str)

        config = {}
        errors = schema.validate(config)

        assert len(errors) == 1
        assert errors[0].key == "required_key"
        assert "required" in errors[0].message.lower()

    def test_validate_wrong_type(self):
        """validate() should return error for wrong type."""
        from core.config.schema import ConfigSchema

        schema = ConfigSchema()
        schema.require("port", int)

        config = {"port": "not_an_int"}
        errors = schema.validate(config)

        assert len(errors) == 1
        assert errors[0].key == "port"
        assert "type" in errors[0].message.lower()

    def test_validate_optional_missing_uses_default(self):
        """validate() should accept missing optional field."""
        from core.config.schema import ConfigSchema

        schema = ConfigSchema()
        schema.optional("debug", bool, default=False)

        config = {}
        errors = schema.validate(config)

        assert errors == []

    def test_validate_optional_wrong_type(self):
        """validate() should error on wrong type for optional field."""
        from core.config.schema import ConfigSchema

        schema = ConfigSchema()
        schema.optional("count", int, default=0)

        config = {"count": "not_an_int"}
        errors = schema.validate(config)

        assert len(errors) == 1
        assert errors[0].key == "count"


class TestConfigSchemaCustomValidators:
    """Test custom validators in ConfigSchema."""

    def test_custom_validator_passes(self):
        """Custom validator returning True should pass."""
        from core.config.schema import ConfigSchema

        schema = ConfigSchema()
        schema.require("port", int, validator=lambda x: 1 <= x <= 65535)

        config = {"port": 8080}
        errors = schema.validate(config)

        assert errors == []

    def test_custom_validator_fails(self):
        """Custom validator returning False should fail."""
        from core.config.schema import ConfigSchema

        schema = ConfigSchema()
        schema.require("port", int, validator=lambda x: 1 <= x <= 65535)

        config = {"port": 70000}
        errors = schema.validate(config)

        assert len(errors) == 1
        assert errors[0].key == "port"

    def test_custom_validator_with_message(self):
        """Custom validator can return error message."""
        from core.config.schema import ConfigSchema

        def validate_port(value):
            if not (1 <= value <= 65535):
                return False, f"Port must be 1-65535, got {value}"
            return True, None

        schema = ConfigSchema()
        schema.require("port", int, validator=validate_port)

        config = {"port": 70000}
        errors = schema.validate(config)

        assert "70000" in errors[0].message

    def test_multiple_validators(self):
        """Field can have multiple validators."""
        from core.config.schema import ConfigSchema

        schema = ConfigSchema()
        schema.require(
            "email",
            str,
            validators=[
                lambda x: "@" in x,
                lambda x: len(x) >= 5,
                lambda x: x.endswith((".com", ".org", ".net")),
            ]
        )

        # Valid email
        errors = schema.validate({"email": "test@example.com"})
        assert errors == []

        # Missing @
        errors = schema.validate({"email": "testexample.com"})
        assert len(errors) >= 1

        # Too short
        errors = schema.validate({"email": "a@b"})
        assert len(errors) >= 1


class TestConfigSchemaTypeCoercion:
    """Test type coercion in ConfigSchema."""

    def test_coerce_string_to_int(self):
        """String '42' should be coercible to int 42."""
        from core.config.schema import ConfigSchema

        schema = ConfigSchema()
        schema.require("count", int, coerce=True)

        config = {"count": "42"}
        errors = schema.validate(config)

        assert errors == []

    def test_coerce_string_to_bool(self):
        """String 'true' should be coercible to bool True."""
        from core.config.schema import ConfigSchema

        schema = ConfigSchema()
        schema.require("enabled", bool, coerce=True)

        config = {"enabled": "true"}
        errors = schema.validate(config)

        assert errors == []

    def test_coerce_failure(self):
        """Invalid coercion should fail gracefully."""
        from core.config.schema import ConfigSchema

        schema = ConfigSchema()
        schema.require("count", int, coerce=True)

        config = {"count": "not_a_number"}
        errors = schema.validate(config)

        assert len(errors) == 1


class TestConfigSchemaNestedFields:
    """Test nested field validation in ConfigSchema."""

    def test_nested_field_validation(self):
        """Nested fields (dot notation) should be validated."""
        from core.config.schema import ConfigSchema

        schema = ConfigSchema()
        schema.require("database.host", str)
        schema.require("database.port", int)

        config = {
            "database.host": "localhost",
            "database.port": 5432,
        }
        errors = schema.validate(config)

        assert errors == []

    def test_nested_field_missing(self):
        """Missing nested field should error."""
        from core.config.schema import ConfigSchema

        schema = ConfigSchema()
        schema.require("database.host", str)

        config = {"other.key": "value"}
        errors = schema.validate(config)

        assert len(errors) == 1
        assert errors[0].key == "database.host"


class TestConfigSchemaChoices:
    """Test enum/choices validation in ConfigSchema."""

    def test_choices_valid(self):
        """Value in choices should pass."""
        from core.config.schema import ConfigSchema

        schema = ConfigSchema()
        schema.require("env", str, choices=["dev", "staging", "prod"])

        config = {"env": "prod"}
        errors = schema.validate(config)

        assert errors == []

    def test_choices_invalid(self):
        """Value not in choices should fail."""
        from core.config.schema import ConfigSchema

        schema = ConfigSchema()
        schema.require("env", str, choices=["dev", "staging", "prod"])

        config = {"env": "invalid"}
        errors = schema.validate(config)

        assert len(errors) == 1
        assert "choices" in errors[0].message.lower() or "invalid" in errors[0].message.lower()


class TestConfigSchemaRanges:
    """Test numeric range validation in ConfigSchema."""

    def test_min_value(self):
        """Value below minimum should fail."""
        from core.config.schema import ConfigSchema

        schema = ConfigSchema()
        schema.require("count", int, min_value=0)

        errors = schema.validate({"count": -1})
        assert len(errors) == 1

        errors = schema.validate({"count": 0})
        assert errors == []

    def test_max_value(self):
        """Value above maximum should fail."""
        from core.config.schema import ConfigSchema

        schema = ConfigSchema()
        schema.require("percent", float, max_value=100.0)

        errors = schema.validate({"percent": 101.0})
        assert len(errors) == 1

        errors = schema.validate({"percent": 100.0})
        assert errors == []

    def test_min_max_range(self):
        """Value in range should pass, outside should fail."""
        from core.config.schema import ConfigSchema

        schema = ConfigSchema()
        schema.require("port", int, min_value=1, max_value=65535)

        errors = schema.validate({"port": 0})
        assert len(errors) == 1

        errors = schema.validate({"port": 8080})
        assert errors == []

        errors = schema.validate({"port": 70000})
        assert len(errors) == 1


class TestConfigSchemaPatterns:
    """Test regex pattern validation in ConfigSchema."""

    def test_pattern_match(self):
        """Value matching pattern should pass."""
        from core.config.schema import ConfigSchema

        schema = ConfigSchema()
        schema.require("version", str, pattern=r"^\d+\.\d+\.\d+$")

        errors = schema.validate({"version": "1.2.3"})
        assert errors == []

    def test_pattern_no_match(self):
        """Value not matching pattern should fail."""
        from core.config.schema import ConfigSchema

        schema = ConfigSchema()
        schema.require("version", str, pattern=r"^\d+\.\d+\.\d+$")

        errors = schema.validate({"version": "v1.2"})
        assert len(errors) == 1


class TestValidationError:
    """Test ValidationError dataclass."""

    def test_error_has_key_and_message(self):
        """ValidationError should have key and message."""
        from core.config.schema import ValidationError

        error = ValidationError(key="test.key", message="Test error message")

        assert error.key == "test.key"
        assert error.message == "Test error message"

    def test_error_has_optional_level(self):
        """ValidationError can have severity level."""
        from core.config.schema import ValidationError

        error = ValidationError(
            key="test.key",
            message="Warning message",
            level="warning"
        )

        assert error.level == "warning"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
