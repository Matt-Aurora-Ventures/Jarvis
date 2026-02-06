"""
Tests for core/validation/schema.py

Tests Schema class: define(), extend(), to_dict().
"""
import pytest


class TestSchemaDefinition:
    """Tests for Schema class definition."""

    def test_schema_define_field_with_single_rule(self):
        """Schema can define a field with a single rule."""
        from core.validation.schema import Schema
        from core.validation.rules import Required

        schema = Schema()
        schema.define("name", Required())
        assert "name" in schema.fields
        assert len(schema.fields["name"]) == 1

    def test_schema_define_field_with_multiple_rules(self):
        """Schema can define a field with multiple rules."""
        from core.validation.schema import Schema
        from core.validation.rules import Required, String, MinLength

        schema = Schema()
        schema.define("name", [Required(), String(), MinLength(3)])
        assert "name" in schema.fields
        assert len(schema.fields["name"]) == 3

    def test_schema_define_returns_self_for_chaining(self):
        """Schema.define() returns self for method chaining."""
        from core.validation.schema import Schema
        from core.validation.rules import Required, String

        schema = Schema()
        result = schema.define("name", Required()).define("email", String())
        assert result is schema
        assert "name" in schema.fields
        assert "email" in schema.fields


class TestSchemaExtension:
    """Tests for Schema inheritance/extension."""

    def test_schema_extend_copies_parent_fields(self):
        """Extended schema copies parent fields."""
        from core.validation.schema import Schema
        from core.validation.rules import Required, String, Email

        parent = Schema()
        parent.define("name", Required())
        parent.define("email", [Required(), Email()])

        child = Schema().extend(parent)
        assert "name" in child.fields
        assert "email" in child.fields

    def test_schema_extend_can_add_new_fields(self):
        """Extended schema can add new fields."""
        from core.validation.schema import Schema
        from core.validation.rules import Required, Integer

        parent = Schema()
        parent.define("name", Required())

        child = Schema().extend(parent)
        child.define("age", Integer())

        assert "name" in child.fields
        assert "age" in child.fields
        # Parent should not have the new field
        assert "age" not in parent.fields

    def test_schema_extend_can_override_fields(self):
        """Extended schema can override parent fields."""
        from core.validation.schema import Schema
        from core.validation.rules import Required, String, MinLength

        parent = Schema()
        parent.define("name", [Required(), MinLength(3)])

        child = Schema().extend(parent)
        child.define("name", [Required(), MinLength(10)])  # Override

        # Child should have overridden rules
        assert len(child.fields["name"]) == 2
        # Verify the MinLength is 10, not 3
        min_length_rule = [r for r in child.fields["name"] if hasattr(r, 'min_len')][0]
        assert min_length_rule.min_len == 10


class TestSchemaToDict:
    """Tests for Schema.to_dict() method."""

    def test_schema_to_dict_basic(self):
        """Schema.to_dict() returns proper structure."""
        from core.validation.schema import Schema
        from core.validation.rules import Required, String, MinLength

        schema = Schema()
        schema.define("name", [Required(), String(), MinLength(3)])
        schema.define("email", Required())

        result = schema.to_dict()
        assert "fields" in result
        assert "name" in result["fields"]
        assert "email" in result["fields"]

    def test_schema_to_dict_includes_rule_info(self):
        """Schema.to_dict() includes rule information."""
        from core.validation.schema import Schema
        from core.validation.rules import Required, MinLength, Max

        schema = Schema()
        schema.define("name", [Required(), MinLength(3)])
        schema.define("age", [Required(), Max(120)])

        result = schema.to_dict()

        # Should have rule names
        name_rules = result["fields"]["name"]["rules"]
        assert any("Required" in str(r) for r in name_rules)
        assert any("MinLength" in str(r) for r in name_rules)


class TestSchemaValidation:
    """Tests for Schema validation functionality."""

    def test_schema_validates_data(self):
        """Schema can validate data against defined rules."""
        from core.validation.schema import Schema
        from core.validation.rules import Required, String, MinLength

        schema = Schema()
        schema.define("name", [Required(), String(), MinLength(3)])

        result = schema.validate({"name": "John"})
        assert result.is_valid is True

    def test_schema_returns_errors_for_invalid_data(self):
        """Schema returns errors for invalid data."""
        from core.validation.schema import Schema
        from core.validation.rules import Required, String, MinLength

        schema = Schema()
        schema.define("name", [Required(), String(), MinLength(3)])

        result = schema.validate({"name": "Jo"})  # Too short
        assert result.is_valid is False
        assert len(result.errors) > 0

    def test_schema_validates_multiple_fields(self):
        """Schema validates all defined fields."""
        from core.validation.schema import Schema
        from core.validation.rules import Required, String, Integer, Min

        schema = Schema()
        schema.define("name", [Required(), String()])
        schema.define("age", [Required(), Integer(), Min(0)])

        # Valid data
        result = schema.validate({"name": "John", "age": 25})
        assert result.is_valid is True

        # Invalid data - multiple errors
        result = schema.validate({"name": "", "age": -5})
        assert result.is_valid is False

    def test_schema_handles_missing_required_fields(self):
        """Schema reports errors for missing required fields."""
        from core.validation.schema import Schema
        from core.validation.rules import Required, String

        schema = Schema()
        schema.define("name", [Required(), String()])
        schema.define("email", [Required(), String()])

        result = schema.validate({"name": "John"})  # Missing email
        assert result.is_valid is False
        assert any("email" in str(e.field) for e in result.errors)

    def test_schema_allows_optional_fields(self):
        """Schema allows optional fields to be missing."""
        from core.validation.schema import Schema
        from core.validation.rules import Optional as OptionalRule, String

        schema = Schema()
        schema.define("name", [String()])  # Not marked as required
        schema.define("nickname", [OptionalRule(), String()])

        result = schema.validate({"name": "John"})  # Missing nickname is OK
        assert result.is_valid is True


class TestSchemaWithName:
    """Tests for named schemas."""

    def test_schema_with_name(self):
        """Schema can have a name."""
        from core.validation.schema import Schema

        schema = Schema(name="UserSchema")
        assert schema.name == "UserSchema"

    def test_schema_to_dict_includes_name(self):
        """Schema.to_dict() includes schema name."""
        from core.validation.schema import Schema
        from core.validation.rules import Required

        schema = Schema(name="UserSchema")
        schema.define("name", Required())

        result = schema.to_dict()
        assert result.get("name") == "UserSchema"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
