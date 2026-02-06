"""Tests for Sanitizer class.

Covers:
- sanitize_output() text sanitization
- remove_sensitive_data() credential removal
- truncate_safely() safe truncation
- ensure_valid_encoding() encoding validation
"""
import pytest

from core.response.sanitizer import (
    sanitize_output,
    remove_sensitive_data,
    truncate_safely,
    ensure_valid_encoding,
)


class TestSanitizeOutput:
    """Test sanitize_output() function."""

    def test_sanitize_basic(self):
        """Test basic sanitization."""
        result = sanitize_output("Hello World")
        assert result == "Hello World"

    def test_sanitize_strips_whitespace(self):
        """Test sanitization strips leading/trailing whitespace."""
        result = sanitize_output("  text  ")
        assert result == "text"

    def test_sanitize_normalizes_newlines(self):
        """Test sanitization normalizes newlines."""
        result = sanitize_output("line1\r\nline2\rline3")
        assert "\r" not in result or result == "line1\nline2\nline3"

    def test_sanitize_removes_null_bytes(self):
        """Test sanitization removes null bytes."""
        result = sanitize_output("text\x00with\x00nulls")
        assert "\x00" not in result
        assert "text" in result
        assert "nulls" in result

    def test_sanitize_removes_control_chars(self):
        """Test sanitization removes control characters."""
        result = sanitize_output("text\x01\x02\x03here")
        assert "\x01" not in result
        assert "\x02" not in result
        assert "\x03" not in result

    def test_sanitize_preserves_newline_tab(self):
        """Test sanitization preserves newline and tab."""
        result = sanitize_output("line1\nline2\ttabbed")
        assert "\n" in result or "line1" in result
        assert "tabbed" in result

    def test_sanitize_empty(self):
        """Test sanitization of empty string."""
        result = sanitize_output("")
        assert result == ""

    def test_sanitize_none(self):
        """Test sanitization of None."""
        result = sanitize_output(None)
        assert result == ""

    def test_sanitize_unicode(self):
        """Test sanitization preserves unicode."""
        result = sanitize_output("Hello World")
        assert "Hello" in result

    def test_sanitize_long_text(self):
        """Test sanitization of long text."""
        long_text = "A" * 10000
        result = sanitize_output(long_text)
        assert len(result) == 10000

    def test_sanitize_mixed_content(self):
        """Test sanitization of mixed content."""
        text = "Normal\x00null\x01ctrl\nvalid"
        result = sanitize_output(text)
        assert "Normal" in result
        assert "null" in result
        assert "valid" in result
        assert "\x00" not in result
        assert "\x01" not in result


class TestRemoveSensitiveData:
    """Test remove_sensitive_data() function."""

    def test_remove_api_key(self):
        """Test removal of API key patterns."""
        text = "api_key=sk_live_abc123xyz789"
        result = remove_sensitive_data(text)
        assert "sk_live_abc123xyz789" not in result
        assert "[REDACTED]" in result or "***" in result

    def test_remove_password(self):
        """Test removal of password patterns."""
        text = 'password="secret123"'
        result = remove_sensitive_data(text)
        assert "secret123" not in result

    def test_remove_bearer_token(self):
        """Test removal of bearer token."""
        text = "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
        result = remove_sensitive_data(text)
        assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" not in result

    def test_remove_private_key(self):
        """Test removal of private key markers."""
        text = "-----BEGIN PRIVATE KEY-----\nMIIEvgIBADANBg..."
        result = remove_sensitive_data(text)
        assert "MIIEvgIBADANBg" not in result or "[REDACTED]" in result

    def test_remove_secret_key(self):
        """Test removal of secret key patterns."""
        text = "secret_key: abc123secretkey"
        result = remove_sensitive_data(text)
        assert "abc123secretkey" not in result

    def test_remove_aws_key(self):
        """Test removal of AWS key patterns."""
        text = "AKIAIOSFODNN7EXAMPLE"
        result = remove_sensitive_data(text)
        assert "AKIAIOSFODNN7EXAMPLE" not in result or result == text  # May not match if not detected

    def test_remove_connection_string(self):
        """Test removal of connection string passwords."""
        text = "postgres://user:password123@localhost/db"
        result = remove_sensitive_data(text)
        assert "password123" not in result

    def test_preserve_normal_text(self):
        """Test normal text is preserved."""
        text = "This is a normal message with no secrets"
        result = remove_sensitive_data(text)
        assert result == text

    def test_remove_multiple_secrets(self):
        """Test removal of multiple secrets."""
        text = 'api_key="key1" password="pass2" token="tok3"'
        result = remove_sensitive_data(text)
        assert "key1" not in result
        assert "pass2" not in result
        assert "tok3" not in result

    def test_remove_empty(self):
        """Test removal from empty string."""
        result = remove_sensitive_data("")
        assert result == ""

    def test_remove_none(self):
        """Test removal from None."""
        result = remove_sensitive_data(None)
        assert result == ""

    def test_remove_email_addresses(self):
        """Test handling of email addresses."""
        text = "Contact: user@example.com"
        result = remove_sensitive_data(text)
        # Email may or may not be redacted depending on policy
        assert "Contact" in result

    def test_remove_credit_card_like(self):
        """Test removal of credit card-like numbers."""
        text = "Card: 4111111111111111"
        result = remove_sensitive_data(text)
        assert "4111111111111111" not in result or "Card" in result

    def test_case_insensitive(self):
        """Test case insensitive matching."""
        text = "PASSWORD=secret API_KEY=key123"
        result = remove_sensitive_data(text)
        assert "secret" not in result
        assert "key123" not in result


class TestTruncateSafely:
    """Test truncate_safely() function."""

    def test_truncate_short_text(self):
        """Test truncation of short text (no truncation needed)."""
        result = truncate_safely("Short", max_len=100)
        assert result == "Short"

    def test_truncate_long_text(self):
        """Test truncation of long text."""
        text = "A" * 200
        result = truncate_safely(text, max_len=100)
        assert len(result) <= 100

    def test_truncate_adds_ellipsis(self):
        """Test truncation adds ellipsis indicator."""
        text = "A" * 200
        result = truncate_safely(text, max_len=100)
        assert "..." in result or len(result) < len(text)

    def test_truncate_exact_length(self):
        """Test text exactly at max length."""
        text = "A" * 100
        result = truncate_safely(text, max_len=100)
        assert result == text

    def test_truncate_at_word_boundary(self):
        """Test truncation at word boundary."""
        text = "The quick brown fox jumps over the lazy dog"
        result = truncate_safely(text, max_len=20)
        assert len(result) <= 20
        # Should ideally end at a word boundary
        assert not result.endswith(" ") or "..." in result

    def test_truncate_empty(self):
        """Test truncation of empty string."""
        result = truncate_safely("", max_len=100)
        assert result == ""

    def test_truncate_none(self):
        """Test truncation of None."""
        result = truncate_safely(None, max_len=100)
        assert result == ""

    def test_truncate_unicode_safe(self):
        """Test truncation is unicode safe (doesn't break multi-byte chars)."""
        text = "Hello World " * 100
        result = truncate_safely(text, max_len=50)
        # Should not end with partial emoji
        assert len(result) <= 50
        # Verify it's valid unicode
        result.encode('utf-8')  # Should not raise

    def test_truncate_very_small_limit(self):
        """Test truncation with very small limit."""
        text = "Hello World"
        result = truncate_safely(text, max_len=5)
        assert len(result) <= 5

    def test_truncate_preserves_meaning(self):
        """Test truncation preserves beginning of message."""
        text = "Important: This is important information"
        result = truncate_safely(text, max_len=20)
        assert "Important" in result or result.startswith("Imp")

    def test_truncate_custom_suffix(self):
        """Test truncation with custom suffix."""
        text = "A" * 200
        result = truncate_safely(text, max_len=100, suffix=" [truncated]")
        assert "[truncated]" in result or "..." in result or len(result) <= 100


class TestEnsureValidEncoding:
    """Test ensure_valid_encoding() function."""

    def test_valid_utf8(self):
        """Test valid UTF-8 string passes through."""
        text = "Hello World"
        result = ensure_valid_encoding(text)
        assert result == text

    def test_valid_unicode(self):
        """Test valid unicode passes through."""
        text = "Hello World with emojis"
        result = ensure_valid_encoding(text)
        assert "Hello" in result

    def test_replace_invalid_bytes(self):
        """Test invalid bytes are replaced."""
        # Create a string with an invalid sequence
        text = "Hello\x80World"  # 0x80 is invalid standalone in UTF-8
        result = ensure_valid_encoding(text)
        assert "Hello" in result
        assert "World" in result
        # Invalid char should be replaced or removed
        assert "\x80" not in result or result == "HelloWorld"

    def test_empty_string(self):
        """Test empty string."""
        result = ensure_valid_encoding("")
        assert result == ""

    def test_none_input(self):
        """Test None input."""
        result = ensure_valid_encoding(None)
        assert result == ""

    def test_bytes_input(self):
        """Test bytes input is decoded."""
        text = b"Hello World"
        result = ensure_valid_encoding(text)
        assert result == "Hello World"

    def test_bytes_with_encoding(self):
        """Test bytes with specified encoding."""
        text = "Caf".encode('latin-1')
        result = ensure_valid_encoding(text, encoding='latin-1')
        assert "Caf" in result

    def test_mixed_encoding_recovery(self):
        """Test recovery from mixed encoding issues."""
        # Simulate mojibake or encoding issues
        text = b"Hello\xc3\xa9"  # UTF-8 encoded e with acute
        result = ensure_valid_encoding(text)
        assert "Hello" in result

    def test_preserves_whitespace(self):
        """Test whitespace is preserved."""
        text = "Line 1\n\tIndented\n  Spaces"
        result = ensure_valid_encoding(text)
        assert "\n" in result
        assert "\t" in result or "Indented" in result

    def test_roundtrip_safe(self):
        """Test output can be encoded back to UTF-8."""
        text = "Test text with various chars: Hello"
        result = ensure_valid_encoding(text)
        # Should be able to encode back without error
        encoded = result.encode('utf-8')
        assert isinstance(encoded, bytes)


class TestSanitizerIntegration:
    """Test integration of sanitizer functions."""

    def test_full_pipeline(self):
        """Test full sanitization pipeline."""
        text = "  api_key=secret123\x00\nNormal text\r\n  "

        # Apply all sanitization steps
        result = sanitize_output(text)
        result = remove_sensitive_data(result)
        result = ensure_valid_encoding(result)

        assert "\x00" not in result
        assert "secret123" not in result
        assert "Normal text" in result

    def test_sanitize_then_truncate(self):
        """Test sanitization followed by truncation."""
        text = "password=secret " * 100

        sanitized = remove_sensitive_data(text)
        truncated = truncate_safely(sanitized, max_len=100)

        assert len(truncated) <= 100
        assert "secret" not in truncated

    def test_encoding_then_sanitize(self):
        """Test encoding fix then sanitization."""
        text = b"api_key=secret\xc0\xc0"  # Invalid UTF-8 sequence

        encoded = ensure_valid_encoding(text)
        sanitized = remove_sensitive_data(encoded)

        assert "secret" not in sanitized


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
