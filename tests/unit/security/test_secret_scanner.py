"""
Secret Scanner Tests

Comprehensive tests for the secret scanning system that provides:
- Pattern-based secret detection
- Text, file, and directory scanning
- Secret redaction with configurable styles
- Pre-log and pre-send hooks
"""
import pytest
import os
import tempfile
from pathlib import Path
from typing import List
from unittest.mock import MagicMock, patch


class TestSecretPatterns:
    """Tests for SECRET_PATTERNS dictionary."""

    def test_patterns_module_exists(self):
        """Test that patterns module can be imported."""
        from core.security.patterns import SECRET_PATTERNS
        assert isinstance(SECRET_PATTERNS, dict)

    def test_api_key_pattern_exists(self):
        """Test API key pattern is defined."""
        from core.security.patterns import SECRET_PATTERNS
        assert "api_key" in SECRET_PATTERNS

    def test_token_pattern_exists(self):
        """Test token pattern is defined (Slack-style)."""
        from core.security.patterns import SECRET_PATTERNS
        assert "slack_token" in SECRET_PATTERNS

    def test_private_key_pattern_exists(self):
        """Test private key pattern is defined."""
        from core.security.patterns import SECRET_PATTERNS
        assert "private_key" in SECRET_PATTERNS

    def test_password_pattern_exists(self):
        """Test password pattern is defined."""
        from core.security.patterns import SECRET_PATTERNS
        assert "password" in SECRET_PATTERNS

    def test_api_key_pattern_matches(self):
        """Test API key pattern matches typical keys."""
        from core.security.patterns import SECRET_PATTERNS
        import re
        pattern = re.compile(SECRET_PATTERNS["api_key"])

        # Should match 32+ char alphanumeric strings
        assert pattern.search("api_key=abcdefghij123456789012345678901234567890")
        assert pattern.search("key=ABCDEFGHIJKLMNOPQRSTUVWXYZ123456")

    def test_slack_token_pattern_matches(self):
        """Test Slack token pattern matches xox tokens."""
        from core.security.patterns import SECRET_PATTERNS
        import re
        pattern = re.compile(SECRET_PATTERNS["slack_token"])

        # Should match xoxb-, xoxa-, xoxp-, xoxr-, xoxs- patterns
        assert pattern.search("xoxb-FAKE00000000-abcFAKEghij")
        assert pattern.search("token: xoxp-987654321098-zyxwvutsrq")

    def test_private_key_pattern_matches(self):
        """Test private key pattern matches PEM format."""
        from core.security.patterns import SECRET_PATTERNS
        import re
        pattern = re.compile(SECRET_PATTERNS["private_key"], re.DOTALL)

        pem_key = """-----BEGIN RSA PRIVATE KEY-----
MIIBOgIBAAJBAK...
-----END RSA PRIVATE KEY-----"""
        assert pattern.search(pem_key)

    def test_password_pattern_matches(self):
        """Test password pattern matches common formats."""
        from core.security.patterns import SECRET_PATTERNS
        import re
        pattern = re.compile(SECRET_PATTERNS["password"], re.IGNORECASE)

        assert pattern.search('password = "mysecretpass123"')
        assert pattern.search("password='anothersecret'")
        assert pattern.search("PASSWORD=plaintext")


class TestSecretScanner:
    """Tests for SecretScanner class."""

    @pytest.fixture
    def scanner(self):
        """Create a scanner instance."""
        from core.security.scanner import SecretScanner
        return SecretScanner()

    def test_scanner_initialization(self):
        """Test scanner initializes correctly."""
        from core.security.scanner import SecretScanner
        scanner = SecretScanner()
        assert scanner is not None

    def test_scan_text_no_secrets(self, scanner):
        """Test scanning text with no secrets."""
        text = "This is just normal text with no secrets."
        findings = scanner.scan_text(text)

        assert isinstance(findings, list)
        assert len(findings) == 0

    def test_scan_text_finds_api_key(self, scanner):
        """Test scanning text finds API keys."""
        text = "API_KEY=sk_test_FAKE_abcdefghij12345678901234"
        findings = scanner.scan_text(text)

        assert len(findings) >= 1
        assert any(f.pattern_name == "api_key" for f in findings)

    def test_scan_text_finds_password(self, scanner):
        """Test scanning text finds passwords."""
        text = 'config = {"password": "super_secret_123"}'
        findings = scanner.scan_text(text)

        assert len(findings) >= 1
        assert any(f.pattern_name == "password" for f in findings)

    def test_scan_text_finds_private_key(self, scanner):
        """Test scanning text finds private keys."""
        text = """-----BEGIN PRIVATE KEY-----
MIIEvQIBADANBgkqhkiG9w0BAQEF...
-----END PRIVATE KEY-----"""
        findings = scanner.scan_text(text)

        assert len(findings) >= 1
        assert any(f.pattern_name == "private_key" for f in findings)

    def test_scan_text_finds_slack_token(self, scanner):
        """Test scanning text finds Slack tokens."""
        text = "SLACK_BOT_TOKEN=xoxb-FAKE000000-FAKE00000000-abcdefghijklFAKETOKEN"
        findings = scanner.scan_text(text)

        assert len(findings) >= 1
        assert any(f.pattern_name == "slack_token" for f in findings)

    def test_scan_text_multiple_secrets(self, scanner):
        """Test scanning text finds multiple secrets."""
        text = """
        API_KEY=abcdefghijklmnopqrstuvwxyz123456
        password = "mypassword123"
        token: xoxb-123-456-abc
        """
        findings = scanner.scan_text(text)

        assert len(findings) >= 3

    def test_finding_has_required_attributes(self, scanner):
        """Test that Finding objects have required attributes."""
        text = "password='secret123'"
        findings = scanner.scan_text(text)

        assert len(findings) >= 1
        finding = findings[0]

        assert hasattr(finding, 'pattern_name')
        assert hasattr(finding, 'matched_text')
        assert hasattr(finding, 'line_number')
        assert hasattr(finding, 'start_pos')
        assert hasattr(finding, 'end_pos')

    def test_scan_file_not_found(self, scanner):
        """Test scanning non-existent file."""
        findings = scanner.scan_file("/nonexistent/path/to/file.txt")

        assert isinstance(findings, list)
        assert len(findings) == 0

    def test_scan_file_finds_secrets(self, scanner, tmp_path):
        """Test scanning file finds secrets."""
        test_file = tmp_path / "config.txt"
        test_file.write_text('API_KEY=abcdefghijklmnopqrstuvwxyz12345678901234')

        findings = scanner.scan_file(str(test_file))

        assert len(findings) >= 1

    def test_scan_file_reports_correct_line_number(self, scanner, tmp_path):
        """Test that file scanning reports correct line numbers."""
        test_file = tmp_path / "config.txt"
        test_file.write_text("""line 1
line 2
password = "secret_on_line_3"
line 4
""")
        findings = scanner.scan_file(str(test_file))

        assert len(findings) >= 1
        assert any(f.line_number == 3 for f in findings)

    def test_scan_directory_empty(self, scanner, tmp_path):
        """Test scanning empty directory."""
        findings = scanner.scan_directory(str(tmp_path))

        assert isinstance(findings, list)
        assert len(findings) == 0

    def test_scan_directory_finds_secrets(self, scanner, tmp_path):
        """Test scanning directory finds secrets in files."""
        # Create files with secrets
        (tmp_path / "config.py").write_text('API_KEY = "abcdefghijklmnopqrstuvwxyz1234567890"')
        (tmp_path / "settings.json").write_text('{"password": "mysecretpass"}')

        findings = scanner.scan_directory(str(tmp_path))

        assert len(findings) >= 2

    def test_scan_directory_recursive(self, scanner, tmp_path):
        """Test scanning directory recursively."""
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        (subdir / "nested.txt").write_text('password="nested_secret"')

        findings = scanner.scan_directory(str(tmp_path))

        assert len(findings) >= 1

    def test_scan_directory_respects_gitignore(self, scanner, tmp_path):
        """Test that scanning respects .gitignore patterns."""
        # Create gitignore
        (tmp_path / ".gitignore").write_text("ignored/\n*.secret")

        # Create ignored files
        ignored_dir = tmp_path / "ignored"
        ignored_dir.mkdir()
        (ignored_dir / "secret.txt").write_text('password="should_be_ignored"')
        (tmp_path / "test.secret").write_text('API_KEY=should_be_ignored')

        # Create non-ignored file
        (tmp_path / "config.txt").write_text('password="should_be_found"')

        findings = scanner.scan_directory(str(tmp_path), respect_gitignore=True)

        # Should only find the non-ignored secret
        assert len(findings) == 1

    def test_scanner_custom_patterns(self):
        """Test scanner with custom patterns."""
        from core.security.scanner import SecretScanner

        custom_patterns = {
            "custom_token": r"CUSTOM_[A-Z0-9]{16}"
        }
        scanner = SecretScanner(additional_patterns=custom_patterns)

        text = "token=CUSTOM_ABCDEFGH12345678"
        findings = scanner.scan_text(text)

        assert any(f.pattern_name == "custom_token" for f in findings)


class TestRedactor:
    """Tests for Redactor class."""

    @pytest.fixture
    def redactor(self):
        """Create a redactor instance."""
        from core.security.redactor import Redactor
        return Redactor()

    def test_redactor_initialization(self):
        """Test redactor initializes correctly."""
        from core.security.redactor import Redactor
        redactor = Redactor()
        assert redactor is not None

    def test_redact_no_secrets(self, redactor):
        """Test redacting text with no secrets."""
        text = "This is just normal text."
        result = redactor.redact(text)

        assert result == text

    def test_redact_api_key(self, redactor):
        """Test redacting API key."""
        text = "API_KEY=sk_test_FAKE_abcdefghijklmnopqrstuv1234"
        result = redactor.redact(text)

        assert "sk_test_FAKE_abcdefghijklmnopqrstuv1234" not in result
        assert "REDACTED" in result or "..." in result

    def test_redact_password(self, redactor):
        """Test redacting password."""
        text = 'password = "mysecretpassword123"'
        result = redactor.redact(text)

        assert "mysecretpassword123" not in result

    def test_redact_preserves_structure(self, redactor):
        """Test that redaction preserves text structure."""
        text = 'config = {\n  "api_key": "abcdefghijklmnopqrstuvwxyz123456"\n}'
        result = redactor.redact(text)

        # Should still have the structure
        assert "config" in result
        assert "api_key" in result
        assert "{" in result
        assert "}" in result

    def test_mask_secret_default_style(self, redactor):
        """Test mask_secret with default style."""
        secret = "sk_test_FAKE_abcdefghijklmnopqrstuv1234"
        masked = redactor.mask_secret(secret)

        # Should show prefix and suffix with ... in between
        assert masked.startswith("sk")
        assert "..." in masked

    def test_mask_secret_full_redact_style(self):
        """Test mask_secret with full redact style."""
        from core.security.redactor import Redactor
        redactor = Redactor(style="full")

        secret = "sk_test_FAKE_abcdefghijklmnopqrstuv1234"
        masked = redactor.mask_secret(secret)

        assert masked == "[REDACTED]"

    def test_mask_secret_partial_style(self):
        """Test mask_secret with partial style."""
        from core.security.redactor import Redactor
        redactor = Redactor(style="partial")

        secret = "sk_test_FAKE_a"
        masked = redactor.mask_secret(secret)

        # Should show first 3 and last 3 chars
        assert masked.startswith("sk_")
        assert masked.endswith("def")
        assert "..." in masked

    def test_mask_secret_hash_style(self):
        """Test mask_secret with hash style."""
        from core.security.redactor import Redactor
        redactor = Redactor(style="hash")

        secret = "mysecretkey"
        masked = redactor.mask_secret(secret)

        # Should be a hash representation
        assert "[SHA256:" in masked or len(masked) == 64 or "hash" in masked.lower()

    def test_redact_multiple_secrets(self, redactor):
        """Test redacting multiple secrets in one text."""
        text = """
        API_KEY=abcdefghijklmnopqrstuvwxyz1234567890
        password = "secret123"
        SLACK_TOKEN=xoxb-123-456-abc
        """
        result = redactor.redact(text)

        assert "abcdefghijklmnopqrstuvwxyz1234567890" not in result
        assert "secret123" not in result
        assert "xoxb-123-456-abc" not in result

    def test_configure_style(self, redactor):
        """Test configuring redaction style."""
        redactor.configure(style="full")

        secret = "mysecret123"
        masked = redactor.mask_secret(secret)

        assert masked == "[REDACTED]"

    def test_configure_preserve_length(self):
        """Test configuring to preserve length."""
        from core.security.redactor import Redactor
        redactor = Redactor(preserve_length=True)

        secret = "12345678901234567890"
        masked = redactor.mask_secret(secret)

        # Should be same length as original
        assert len(masked) == len(secret)


class TestSecurityHooks:
    """Tests for security hooks."""

    def test_hooks_module_exists(self):
        """Test that hooks module can be imported."""
        from core.security.hooks import pre_log_hook, pre_send_hook
        assert callable(pre_log_hook)
        assert callable(pre_send_hook)

    def test_pre_log_hook_allows_clean_text(self):
        """Test pre_log_hook allows clean text."""
        from core.security.hooks import pre_log_hook

        text = "This is a normal log message."
        result = pre_log_hook(text)

        assert result.allowed is True
        assert result.text == text

    def test_pre_log_hook_redacts_secrets(self):
        """Test pre_log_hook redacts secrets."""
        from core.security.hooks import pre_log_hook

        text = 'Logging config: API_KEY=abcdefghijklmnopqrstuvwxyz12345678'
        result = pre_log_hook(text)

        assert "abcdefghijklmnopqrstuvwxyz12345678" not in result.text

    def test_pre_log_hook_blocks_on_critical(self):
        """Test pre_log_hook blocks on critical secrets."""
        from core.security.hooks import pre_log_hook

        text = """-----BEGIN PRIVATE KEY-----
MIIEvQIBADANBgkqhkiG9w0BAQEF...
-----END PRIVATE KEY-----"""

        result = pre_log_hook(text, block_on_critical=True)

        # Should either block or heavily redact
        assert result.allowed is False or "PRIVATE KEY" not in result.text

    def test_pre_send_hook_allows_clean_data(self):
        """Test pre_send_hook allows clean data."""
        from core.security.hooks import pre_send_hook

        data = {"message": "Hello world", "user": "test_user"}
        result = pre_send_hook(data)

        assert result.allowed is True
        assert result.data == data

    def test_pre_send_hook_redacts_secrets_in_dict(self):
        """Test pre_send_hook redacts secrets in dict."""
        from core.security.hooks import pre_send_hook

        data = {
            "api_key": "sk_test_FAKE_abcdefghijklmnopqrstuv1234567",
            "message": "Hello"
        }
        result = pre_send_hook(data)

        assert "sk_test_FAKE_abcdefghijklmnopqrstuv1234567" not in str(result.data)

    def test_pre_send_hook_blocks_if_secrets_found(self):
        """Test pre_send_hook can block if secrets found."""
        from core.security.hooks import pre_send_hook

        data = {
            "private_key": """-----BEGIN RSA PRIVATE KEY-----
MIIBOgIBAAJBAK...
-----END RSA PRIVATE KEY-----"""
        }
        result = pre_send_hook(data, block_on_secrets=True)

        assert result.allowed is False

    def test_pre_send_hook_nested_dict(self):
        """Test pre_send_hook handles nested dicts."""
        from core.security.hooks import pre_send_hook

        data = {
            "config": {
                "auth": {
                    "password": "nested_secret_password123"
                }
            }
        }
        result = pre_send_hook(data)

        assert "nested_secret_password123" not in str(result.data)

    def test_pre_send_hook_list_values(self):
        """Test pre_send_hook handles list values."""
        from core.security.hooks import pre_send_hook

        data = {
            "tokens": [
                "xoxb-123-456-abcdefghij",
                "safe_value"
            ]
        }
        result = pre_send_hook(data)

        assert "xoxb-123-456-abcdefghij" not in str(result.data)

    def test_hook_result_has_findings(self):
        """Test that hook results include findings."""
        from core.security.hooks import pre_log_hook

        text = 'password = "secret123"'
        result = pre_log_hook(text)

        assert hasattr(result, 'findings')
        assert len(result.findings) >= 1


class TestFinding:
    """Tests for Finding dataclass."""

    def test_finding_creation(self):
        """Test Finding can be created."""
        from core.security.scanner import Finding

        finding = Finding(
            pattern_name="api_key",
            matched_text="sk_test_FAKE23",
            line_number=1,
            start_pos=0,
            end_pos=14
        )

        assert finding.pattern_name == "api_key"
        assert finding.matched_text == "sk_test_FAKE23"
        assert finding.line_number == 1

    def test_finding_str_representation(self):
        """Test Finding string representation."""
        from core.security.scanner import Finding

        finding = Finding(
            pattern_name="password",
            matched_text="secret123",
            line_number=5,
            start_pos=10,
            end_pos=19
        )

        str_repr = str(finding)
        assert "password" in str_repr
        assert "5" in str_repr or "line" in str_repr.lower()

    def test_finding_optional_file_path(self):
        """Test Finding with optional file path."""
        from core.security.scanner import Finding

        finding = Finding(
            pattern_name="api_key",
            matched_text="abc123",
            line_number=1,
            start_pos=0,
            end_pos=6,
            file_path="/path/to/file.py"
        )

        assert finding.file_path == "/path/to/file.py"


class TestHookResult:
    """Tests for HookResult dataclass."""

    def test_hook_result_creation(self):
        """Test HookResult can be created."""
        from core.security.hooks import HookResult

        result = HookResult(
            allowed=True,
            text="clean text",
            findings=[]
        )

        assert result.allowed is True
        assert result.text == "clean text"

    def test_hook_result_with_data(self):
        """Test HookResult with data field."""
        from core.security.hooks import HookResult

        result = HookResult(
            allowed=True,
            data={"key": "value"},
            findings=[]
        )

        assert result.data == {"key": "value"}
