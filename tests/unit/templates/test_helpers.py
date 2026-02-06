"""
Comprehensive unit tests for Template Helpers.

Tests cover:
- format_date(date, format) - date formatting
- format_number(n, decimals) - number formatting
- format_currency(amount, symbol) - currency formatting
- truncate(text, length) - text truncation
- uppercase, lowercase, capitalize - case transformations
- Custom helper registration
"""

import pytest
from datetime import datetime, date, timezone
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from core.templates.helpers import (
    format_date,
    format_number,
    format_currency,
    truncate,
    uppercase,
    lowercase,
    capitalize,
    get_builtin_helpers,
    HelperError,
)


# =============================================================================
# format_date Tests
# =============================================================================

class TestFormatDate:
    """Tests for the format_date helper."""

    def test_format_date_default(self):
        """Test date formatting with default format."""
        dt = datetime(2026, 2, 2, 14, 30, 0)
        result = format_date(dt)
        assert "2026" in result
        assert "02" in result

    def test_format_date_custom_format(self):
        """Test date formatting with custom format."""
        dt = datetime(2026, 2, 2, 14, 30, 0)
        result = format_date(dt, "%Y-%m-%d")
        assert result == "2026-02-02"

    def test_format_date_time_included(self):
        """Test date formatting with time included."""
        dt = datetime(2026, 2, 2, 14, 30, 45)
        result = format_date(dt, "%Y-%m-%d %H:%M:%S")
        assert result == "2026-02-02 14:30:45"

    def test_format_date_from_string_iso(self):
        """Test formatting date from ISO string."""
        result = format_date("2026-02-02T14:30:00", "%Y-%m-%d")
        assert result == "2026-02-02"

    def test_format_date_from_string_various(self):
        """Test formatting date from various string formats."""
        result = format_date("2026-02-02", "%d/%m/%Y")
        assert result == "02/02/2026"

    def test_format_date_timestamp(self):
        """Test formatting from Unix timestamp."""
        timestamp = 1738512000  # 2025-02-02 16:00:00 UTC
        result = format_date(timestamp, "%Y-%m-%d")
        assert "2025" in result or "2026" in result

    def test_format_date_none(self):
        """Test formatting None returns empty or placeholder."""
        result = format_date(None)
        assert result == "" or result == "N/A" or result is None

    def test_format_date_invalid(self):
        """Test formatting invalid input."""
        with pytest.raises((ValueError, HelperError)):
            format_date("not a date", "%Y-%m-%d")

    def test_format_date_date_object(self):
        """Test formatting date object (not datetime)."""
        d = date(2026, 2, 2)
        result = format_date(d, "%Y-%m-%d")
        assert result == "2026-02-02"

    def test_format_date_timezone_aware(self):
        """Test formatting timezone-aware datetime."""
        dt = datetime(2026, 2, 2, 14, 30, 0, tzinfo=timezone.utc)
        result = format_date(dt, "%Y-%m-%d %H:%M:%S %Z")
        assert "2026-02-02" in result


# =============================================================================
# format_number Tests
# =============================================================================

class TestFormatNumber:
    """Tests for the format_number helper."""

    def test_format_number_default(self):
        """Test number formatting with default decimals."""
        result = format_number(1234.5678)
        assert "1234" in result or "1,234" in result

    def test_format_number_decimals(self):
        """Test number formatting with specific decimals."""
        result = format_number(1234.5678, decimals=2)
        assert "1234.57" in result or "1,234.57" in result

    def test_format_number_zero_decimals(self):
        """Test number formatting with zero decimals."""
        result = format_number(1234.5678, decimals=0)
        assert result == "1235" or result == "1,235"

    def test_format_number_thousands_separator(self):
        """Test number formatting with thousands separator."""
        result = format_number(1234567.89, decimals=2)
        assert "," in result or result == "1234567.89"

    def test_format_number_negative(self):
        """Test formatting negative numbers."""
        result = format_number(-1234.56, decimals=2)
        assert "-" in result
        assert "1234.56" in result or "1,234.56" in result

    def test_format_number_zero(self):
        """Test formatting zero."""
        result = format_number(0, decimals=2)
        assert result == "0.00" or result == "0"

    def test_format_number_from_string(self):
        """Test formatting from string number."""
        result = format_number("1234.56", decimals=2)
        assert "1234.56" in result or "1,234.56" in result

    def test_format_number_integer(self):
        """Test formatting integer."""
        result = format_number(1000, decimals=2)
        assert "1000.00" in result or "1,000.00" in result

    def test_format_number_none(self):
        """Test formatting None."""
        result = format_number(None)
        assert result == "0" or result == "" or result == "N/A"

    def test_format_number_invalid(self):
        """Test formatting invalid input."""
        with pytest.raises((ValueError, HelperError, TypeError)):
            format_number("not a number")


# =============================================================================
# format_currency Tests
# =============================================================================

class TestFormatCurrency:
    """Tests for the format_currency helper."""

    def test_format_currency_default_symbol(self):
        """Test currency formatting with default symbol."""
        result = format_currency(1234.56)
        assert "$" in result
        assert "1234.56" in result or "1,234.56" in result

    def test_format_currency_custom_symbol(self):
        """Test currency formatting with custom symbol."""
        result = format_currency(1234.56, symbol="EUR")
        assert "EUR" in result or "E" in result
        assert "1234.56" in result or "1,234.56" in result

    def test_format_currency_euro_symbol(self):
        """Test currency formatting with euro symbol."""
        result = format_currency(1234.56, symbol="")
        assert "" in result

    def test_format_currency_crypto(self):
        """Test formatting crypto amounts."""
        result = format_currency(0.00123456, symbol="SOL")
        assert "SOL" in result
        assert "0.00" in result

    def test_format_currency_negative(self):
        """Test formatting negative currency."""
        result = format_currency(-50.00, symbol="$")
        assert "-" in result
        assert "50.00" in result

    def test_format_currency_zero(self):
        """Test formatting zero currency."""
        result = format_currency(0, symbol="$")
        assert "$" in result
        assert "0" in result

    def test_format_currency_large_amount(self):
        """Test formatting large currency amounts."""
        result = format_currency(1000000.00, symbol="$")
        assert "1" in result and "000" in result

    def test_format_currency_small_decimals(self):
        """Test formatting with many decimal places."""
        result = format_currency(0.000001, symbol="BTC")
        assert "BTC" in result


# =============================================================================
# truncate Tests
# =============================================================================

class TestTruncate:
    """Tests for the truncate helper."""

    def test_truncate_long_text(self):
        """Test truncating long text."""
        text = "This is a long piece of text that should be truncated"
        result = truncate(text, 20)
        assert len(result) <= 23  # 20 + "..."
        assert result.endswith("...")

    def test_truncate_short_text(self):
        """Test text shorter than limit is unchanged."""
        text = "Short"
        result = truncate(text, 20)
        assert result == "Short"

    def test_truncate_exact_length(self):
        """Test text exactly at limit."""
        text = "Exactly20Characters!"
        result = truncate(text, 20)
        assert result == text

    def test_truncate_custom_suffix(self):
        """Test truncating with custom suffix."""
        text = "This is a long text"
        result = truncate(text, 10, suffix=" [more]")
        assert result.endswith("[more]")

    def test_truncate_no_suffix(self):
        """Test truncating without suffix."""
        text = "This is a long text"
        result = truncate(text, 10, suffix="")
        assert len(result) == 10
        assert not result.endswith("...")

    def test_truncate_empty_string(self):
        """Test truncating empty string."""
        result = truncate("", 10)
        assert result == ""

    def test_truncate_word_boundary(self):
        """Test truncating respects word boundaries."""
        text = "This is a sentence with words"
        result = truncate(text, 15, word_boundary=True)
        # Should cut at word boundary
        assert not result.endswith(" ") or result.endswith("...")

    def test_truncate_none(self):
        """Test truncating None."""
        result = truncate(None, 10)
        assert result == "" or result is None


# =============================================================================
# Case Transformation Tests
# =============================================================================

class TestCaseTransformations:
    """Tests for case transformation helpers."""

    def test_uppercase(self):
        """Test uppercase transformation."""
        assert uppercase("hello world") == "HELLO WORLD"

    def test_uppercase_already_upper(self):
        """Test uppercase on already uppercase."""
        assert uppercase("HELLO") == "HELLO"

    def test_uppercase_mixed(self):
        """Test uppercase on mixed case."""
        assert uppercase("HeLLo WoRLd") == "HELLO WORLD"

    def test_uppercase_empty(self):
        """Test uppercase on empty string."""
        assert uppercase("") == ""

    def test_uppercase_none(self):
        """Test uppercase on None."""
        result = uppercase(None)
        assert result == "" or result is None

    def test_lowercase(self):
        """Test lowercase transformation."""
        assert lowercase("HELLO WORLD") == "hello world"

    def test_lowercase_already_lower(self):
        """Test lowercase on already lowercase."""
        assert lowercase("hello") == "hello"

    def test_lowercase_mixed(self):
        """Test lowercase on mixed case."""
        assert lowercase("HeLLo WoRLd") == "hello world"

    def test_lowercase_empty(self):
        """Test lowercase on empty string."""
        assert lowercase("") == ""

    def test_lowercase_none(self):
        """Test lowercase on None."""
        result = lowercase(None)
        assert result == "" or result is None

    def test_capitalize_word(self):
        """Test capitalize single word."""
        assert capitalize("hello") == "Hello"

    def test_capitalize_sentence(self):
        """Test capitalize sentence."""
        result = capitalize("hello world")
        assert result == "Hello world" or result == "Hello World"

    def test_capitalize_all_caps(self):
        """Test capitalize on all caps."""
        result = capitalize("HELLO")
        assert result == "Hello" or result == "HELLO"

    def test_capitalize_empty(self):
        """Test capitalize on empty string."""
        assert capitalize("") == ""

    def test_capitalize_none(self):
        """Test capitalize on None."""
        result = capitalize(None)
        assert result == "" or result is None


# =============================================================================
# Built-in Helpers Tests
# =============================================================================

class TestBuiltinHelpers:
    """Tests for getting built-in helpers."""

    def test_get_builtin_helpers(self):
        """Test getting all built-in helpers."""
        helpers = get_builtin_helpers()

        assert isinstance(helpers, dict)
        assert "format_date" in helpers
        assert "format_number" in helpers
        assert "format_currency" in helpers
        assert "truncate" in helpers
        assert "uppercase" in helpers
        assert "lowercase" in helpers
        assert "capitalize" in helpers

    def test_builtin_helpers_callable(self):
        """Test all built-in helpers are callable."""
        helpers = get_builtin_helpers()

        for name, func in helpers.items():
            assert callable(func), f"{name} is not callable"

    def test_builtin_helpers_work(self):
        """Test built-in helpers work when called."""
        helpers = get_builtin_helpers()

        # Test a few helpers
        assert helpers["uppercase"]("test") == "TEST"
        assert "1234" in helpers["format_number"](1234.5, decimals=0)


# =============================================================================
# Edge Cases Tests
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases in helpers."""

    def test_format_date_far_future(self):
        """Test formatting far future date."""
        dt = datetime(2099, 12, 31, 23, 59, 59)
        result = format_date(dt, "%Y-%m-%d")
        assert result == "2099-12-31"

    def test_format_date_far_past(self):
        """Test formatting far past date."""
        dt = datetime(1900, 1, 1, 0, 0, 0)
        result = format_date(dt, "%Y-%m-%d")
        assert result == "1900-01-01"

    def test_format_number_very_large(self):
        """Test formatting very large numbers."""
        result = format_number(999999999999.99, decimals=2)
        assert "999" in result

    def test_format_number_very_small(self):
        """Test formatting very small numbers."""
        result = format_number(0.0000001, decimals=8)
        assert "0.0000001" in result or "1" in result

    def test_truncate_unicode(self):
        """Test truncating unicode text."""
        text = "Hello World!"  # With emoji
        result = truncate(text, 10)
        assert len(result) <= 13  # Accounting for multi-byte chars

    def test_case_unicode(self):
        """Test case transformations with unicode."""
        assert uppercase("cafe") == "CAFE" or uppercase("cafe") == "CAFE"
        assert lowercase("CAFE") == "cafe" or lowercase("CAFE") == "cafe"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
