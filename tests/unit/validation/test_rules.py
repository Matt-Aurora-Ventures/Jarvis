"""
Tests for core/validation/rules.py

Tests validation rules: Required, Optional, String, Integer, Float, Boolean,
MinLength, MaxLength, Pattern, Min, Max, Range, Email, URL, UUID, Custom.
"""
import pytest
import uuid


class TestRequiredRule:
    """Tests for Required validation rule."""

    def test_required_passes_with_value(self):
        """Required rule passes when value is present."""
        from core.validation.rules import Required
        rule = Required()
        result = rule.validate("hello")
        assert result.is_valid is True
        assert result.errors == []

    def test_required_fails_with_none(self):
        """Required rule fails when value is None."""
        from core.validation.rules import Required
        rule = Required()
        result = rule.validate(None)
        assert result.is_valid is False
        assert len(result.errors) == 1
        assert "required" in result.errors[0].message.lower()

    def test_required_fails_with_empty_string_by_default(self):
        """Required rule fails with empty string by default."""
        from core.validation.rules import Required
        rule = Required()
        result = rule.validate("")
        assert result.is_valid is False

    def test_required_custom_message(self):
        """Required rule uses custom message."""
        from core.validation.rules import Required
        rule = Required(message="This field cannot be empty")
        result = rule.validate(None)
        assert "cannot be empty" in result.errors[0].message


class TestOptionalRule:
    """Tests for Optional validation rule."""

    def test_optional_passes_with_none(self):
        """Optional rule passes when value is None."""
        from core.validation.rules import Optional as OptionalRule
        rule = OptionalRule()
        result = rule.validate(None)
        assert result.is_valid is True

    def test_optional_passes_with_value(self):
        """Optional rule passes when value is present."""
        from core.validation.rules import Optional as OptionalRule
        rule = OptionalRule()
        result = rule.validate("hello")
        assert result.is_valid is True

    def test_optional_with_default(self):
        """Optional rule returns default value when None."""
        from core.validation.rules import Optional as OptionalRule
        rule = OptionalRule(default="default_value")
        result = rule.validate(None)
        assert result.is_valid is True
        assert result.value == "default_value"


class TestStringRule:
    """Tests for String validation rule."""

    def test_string_passes_with_string(self):
        """String rule passes with string value."""
        from core.validation.rules import String
        rule = String()
        result = rule.validate("hello")
        assert result.is_valid is True

    def test_string_fails_with_non_string(self):
        """String rule fails with non-string value."""
        from core.validation.rules import String
        rule = String()
        result = rule.validate(123)
        assert result.is_valid is False
        assert "string" in result.errors[0].message.lower()

    def test_string_coerces_when_enabled(self):
        """String rule coerces to string when enabled."""
        from core.validation.rules import String
        rule = String(coerce=True)
        result = rule.validate(123)
        assert result.is_valid is True
        assert result.value == "123"


class TestIntegerRule:
    """Tests for Integer validation rule."""

    def test_integer_passes_with_int(self):
        """Integer rule passes with int value."""
        from core.validation.rules import Integer
        rule = Integer()
        result = rule.validate(42)
        assert result.is_valid is True

    def test_integer_fails_with_float(self):
        """Integer rule fails with float value."""
        from core.validation.rules import Integer
        rule = Integer()
        result = rule.validate(3.14)
        assert result.is_valid is False

    def test_integer_fails_with_string(self):
        """Integer rule fails with string value."""
        from core.validation.rules import Integer
        rule = Integer()
        result = rule.validate("42")
        assert result.is_valid is False

    def test_integer_coerces_when_enabled(self):
        """Integer rule coerces to int when enabled."""
        from core.validation.rules import Integer
        rule = Integer(coerce=True)
        result = rule.validate("42")
        assert result.is_valid is True
        assert result.value == 42

    def test_integer_coerce_fails_for_non_numeric_string(self):
        """Integer rule fails to coerce non-numeric string."""
        from core.validation.rules import Integer
        rule = Integer(coerce=True)
        result = rule.validate("not a number")
        assert result.is_valid is False


class TestFloatRule:
    """Tests for Float validation rule."""

    def test_float_passes_with_float(self):
        """Float rule passes with float value."""
        from core.validation.rules import Float
        rule = Float()
        result = rule.validate(3.14)
        assert result.is_valid is True

    def test_float_passes_with_int(self):
        """Float rule passes with int value (coercible to float)."""
        from core.validation.rules import Float
        rule = Float()
        result = rule.validate(42)
        assert result.is_valid is True

    def test_float_fails_with_string(self):
        """Float rule fails with string value."""
        from core.validation.rules import Float
        rule = Float()
        result = rule.validate("3.14")
        assert result.is_valid is False

    def test_float_coerces_when_enabled(self):
        """Float rule coerces to float when enabled."""
        from core.validation.rules import Float
        rule = Float(coerce=True)
        result = rule.validate("3.14")
        assert result.is_valid is True
        assert result.value == 3.14


class TestBooleanRule:
    """Tests for Boolean validation rule."""

    def test_boolean_passes_with_bool(self):
        """Boolean rule passes with bool value."""
        from core.validation.rules import Boolean
        rule = Boolean()
        result = rule.validate(True)
        assert result.is_valid is True

    def test_boolean_passes_with_false(self):
        """Boolean rule passes with False value."""
        from core.validation.rules import Boolean
        rule = Boolean()
        result = rule.validate(False)
        assert result.is_valid is True

    def test_boolean_fails_with_non_bool(self):
        """Boolean rule fails with non-bool value."""
        from core.validation.rules import Boolean
        rule = Boolean()
        result = rule.validate(1)
        assert result.is_valid is False

    def test_boolean_coerces_truthy_values(self):
        """Boolean rule coerces truthy strings when enabled."""
        from core.validation.rules import Boolean
        rule = Boolean(coerce=True)
        for val in ["true", "yes", "1", "True", "YES"]:
            result = rule.validate(val)
            assert result.is_valid is True
            assert result.value is True

    def test_boolean_coerces_falsy_values(self):
        """Boolean rule coerces falsy strings when enabled."""
        from core.validation.rules import Boolean
        rule = Boolean(coerce=True)
        for val in ["false", "no", "0", "False", "NO"]:
            result = rule.validate(val)
            assert result.is_valid is True
            assert result.value is False


class TestMinLengthRule:
    """Tests for MinLength validation rule."""

    def test_minlength_passes_when_met(self):
        """MinLength passes when length meets minimum."""
        from core.validation.rules import MinLength
        rule = MinLength(5)
        result = rule.validate("hello")
        assert result.is_valid is True

    def test_minlength_passes_when_exceeded(self):
        """MinLength passes when length exceeds minimum."""
        from core.validation.rules import MinLength
        rule = MinLength(3)
        result = rule.validate("hello world")
        assert result.is_valid is True

    def test_minlength_fails_when_too_short(self):
        """MinLength fails when length is below minimum."""
        from core.validation.rules import MinLength
        rule = MinLength(10)
        result = rule.validate("hi")
        assert result.is_valid is False
        assert "at least 10" in result.errors[0].message


class TestMaxLengthRule:
    """Tests for MaxLength validation rule."""

    def test_maxlength_passes_when_met(self):
        """MaxLength passes when length meets maximum."""
        from core.validation.rules import MaxLength
        rule = MaxLength(5)
        result = rule.validate("hello")
        assert result.is_valid is True

    def test_maxlength_passes_when_under(self):
        """MaxLength passes when length is under maximum."""
        from core.validation.rules import MaxLength
        rule = MaxLength(10)
        result = rule.validate("hi")
        assert result.is_valid is True

    def test_maxlength_fails_when_exceeded(self):
        """MaxLength fails when length exceeds maximum."""
        from core.validation.rules import MaxLength
        rule = MaxLength(5)
        result = rule.validate("hello world")
        assert result.is_valid is False
        assert "at most 5" in result.errors[0].message


class TestPatternRule:
    """Tests for Pattern validation rule."""

    def test_pattern_passes_when_matched(self):
        """Pattern passes when regex matches."""
        from core.validation.rules import Pattern
        rule = Pattern(r"^[A-Z]{3}$")
        result = rule.validate("ABC")
        assert result.is_valid is True

    def test_pattern_fails_when_not_matched(self):
        """Pattern fails when regex doesn't match."""
        from core.validation.rules import Pattern
        rule = Pattern(r"^[A-Z]{3}$")
        result = rule.validate("abc")
        assert result.is_valid is False

    def test_pattern_with_custom_message(self):
        """Pattern uses custom error message."""
        from core.validation.rules import Pattern
        rule = Pattern(r"^[A-Z]{3}$", message="Must be 3 uppercase letters")
        result = rule.validate("abc")
        assert "3 uppercase letters" in result.errors[0].message


class TestMinRule:
    """Tests for Min validation rule."""

    def test_min_passes_when_equal(self):
        """Min passes when value equals minimum."""
        from core.validation.rules import Min
        rule = Min(10)
        result = rule.validate(10)
        assert result.is_valid is True

    def test_min_passes_when_greater(self):
        """Min passes when value is greater than minimum."""
        from core.validation.rules import Min
        rule = Min(10)
        result = rule.validate(15)
        assert result.is_valid is True

    def test_min_fails_when_less(self):
        """Min fails when value is less than minimum."""
        from core.validation.rules import Min
        rule = Min(10)
        result = rule.validate(5)
        assert result.is_valid is False

    def test_min_exclusive(self):
        """Min with exclusive=True fails when equal."""
        from core.validation.rules import Min
        rule = Min(10, exclusive=True)
        result = rule.validate(10)
        assert result.is_valid is False


class TestMaxRule:
    """Tests for Max validation rule."""

    def test_max_passes_when_equal(self):
        """Max passes when value equals maximum."""
        from core.validation.rules import Max
        rule = Max(100)
        result = rule.validate(100)
        assert result.is_valid is True

    def test_max_passes_when_less(self):
        """Max passes when value is less than maximum."""
        from core.validation.rules import Max
        rule = Max(100)
        result = rule.validate(50)
        assert result.is_valid is True

    def test_max_fails_when_greater(self):
        """Max fails when value is greater than maximum."""
        from core.validation.rules import Max
        rule = Max(100)
        result = rule.validate(150)
        assert result.is_valid is False

    def test_max_exclusive(self):
        """Max with exclusive=True fails when equal."""
        from core.validation.rules import Max
        rule = Max(100, exclusive=True)
        result = rule.validate(100)
        assert result.is_valid is False


class TestRangeRule:
    """Tests for Range validation rule."""

    def test_range_passes_within_bounds(self):
        """Range passes when value is within bounds."""
        from core.validation.rules import Range
        rule = Range(10, 100)
        result = rule.validate(50)
        assert result.is_valid is True

    def test_range_passes_at_min_boundary(self):
        """Range passes at minimum boundary."""
        from core.validation.rules import Range
        rule = Range(10, 100)
        result = rule.validate(10)
        assert result.is_valid is True

    def test_range_passes_at_max_boundary(self):
        """Range passes at maximum boundary."""
        from core.validation.rules import Range
        rule = Range(10, 100)
        result = rule.validate(100)
        assert result.is_valid is True

    def test_range_fails_below_min(self):
        """Range fails when value is below minimum."""
        from core.validation.rules import Range
        rule = Range(10, 100)
        result = rule.validate(5)
        assert result.is_valid is False

    def test_range_fails_above_max(self):
        """Range fails when value is above maximum."""
        from core.validation.rules import Range
        rule = Range(10, 100)
        result = rule.validate(150)
        assert result.is_valid is False


class TestEmailRule:
    """Tests for Email validation rule."""

    def test_email_passes_with_valid_email(self):
        """Email passes with valid email addresses."""
        from core.validation.rules import Email
        rule = Email()
        valid_emails = [
            "user@example.com",
            "user.name@example.com",
            "user+tag@example.com",
            "user@subdomain.example.com",
        ]
        for email in valid_emails:
            result = rule.validate(email)
            assert result.is_valid is True, f"Failed for {email}"

    def test_email_fails_with_invalid_email(self):
        """Email fails with invalid email addresses."""
        from core.validation.rules import Email
        rule = Email()
        invalid_emails = [
            "not-an-email",
            "@missing-local.com",
            "missing-at.com",
            "missing@domain",
            "spaces in@email.com",
        ]
        for email in invalid_emails:
            result = rule.validate(email)
            assert result.is_valid is False, f"Should fail for {email}"


class TestURLRule:
    """Tests for URL validation rule."""

    def test_url_passes_with_valid_url(self):
        """URL passes with valid URLs."""
        from core.validation.rules import URL
        rule = URL()
        valid_urls = [
            "https://example.com",
            "http://example.com",
            "https://example.com/path",
            "https://example.com/path?query=1",
            "https://subdomain.example.com",
        ]
        for url in valid_urls:
            result = rule.validate(url)
            assert result.is_valid is True, f"Failed for {url}"

    def test_url_fails_with_invalid_url(self):
        """URL fails with invalid URLs."""
        from core.validation.rules import URL
        rule = URL()
        invalid_urls = [
            "not-a-url",
            "ftp://file-server.com",  # Only http/https by default
            "://missing-scheme.com",
        ]
        for url in invalid_urls:
            result = rule.validate(url)
            assert result.is_valid is False, f"Should fail for {url}"

    def test_url_require_https(self):
        """URL with require_https=True rejects http URLs."""
        from core.validation.rules import URL
        rule = URL(require_https=True)
        result = rule.validate("http://example.com")
        assert result.is_valid is False


class TestUUIDRule:
    """Tests for UUID validation rule."""

    def test_uuid_passes_with_valid_uuid(self):
        """UUID passes with valid UUID strings."""
        from core.validation.rules import UUID
        rule = UUID()
        valid_uuids = [
            "550e8400-e29b-41d4-a716-446655440000",
            "6ba7b810-9dad-11d1-80b4-00c04fd430c8",
            str(uuid.uuid4()),
        ]
        for u in valid_uuids:
            result = rule.validate(u)
            assert result.is_valid is True, f"Failed for {u}"

    def test_uuid_fails_with_invalid_uuid(self):
        """UUID fails with invalid UUID strings."""
        from core.validation.rules import UUID
        rule = UUID()
        invalid_uuids = [
            "not-a-uuid",
            "550e8400-e29b-41d4-a716",  # Too short
            "550e8400-e29b-41d4-a716-446655440000-extra",  # Too long
        ]
        for u in invalid_uuids:
            result = rule.validate(u)
            assert result.is_valid is False, f"Should fail for {u}"


class TestCustomRule:
    """Tests for Custom validation rule."""

    def test_custom_with_passing_function(self):
        """Custom rule passes when function returns True."""
        from core.validation.rules import Custom

        def is_even(value):
            return value % 2 == 0

        rule = Custom(is_even)
        result = rule.validate(4)
        assert result.is_valid is True

    def test_custom_with_failing_function(self):
        """Custom rule fails when function returns False."""
        from core.validation.rules import Custom

        def is_even(value):
            return value % 2 == 0

        rule = Custom(is_even)
        result = rule.validate(3)
        assert result.is_valid is False

    def test_custom_with_custom_message(self):
        """Custom rule uses custom error message."""
        from core.validation.rules import Custom

        def is_even(value):
            return value % 2 == 0

        rule = Custom(is_even, message="Must be an even number")
        result = rule.validate(3)
        assert "even number" in result.errors[0].message

    def test_custom_with_exception_handling(self):
        """Custom rule handles exceptions gracefully."""
        from core.validation.rules import Custom

        def raises_error(value):
            raise ValueError("Intentional error")

        rule = Custom(raises_error)
        result = rule.validate("anything")
        assert result.is_valid is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
