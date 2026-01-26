"""
Tests for Deep Observer privacy controls (P1-4 fix).

Validates:
- Sensitive context detection
- Keystroke redaction in password fields
- App-level blocklist
- Privacy modes (redact, metadata, disabled)
- Redaction statistics
"""

import pytest
from unittest.mock import Mock, patch
from core.observer import PrivacyFilter, DeepObserver, ALWAYS_SENSITIVE_APPS


class TestPrivacyFilter:
    """Tests for PrivacyFilter class."""

    def test_privacy_filter_initialization(self):
        """Test privacy filter initialization with defaults."""
        pf = PrivacyFilter()
        assert "1Password" in pf.always_sensitive
        assert "LastPass" in pf.always_sensitive
        assert "Chrome" in pf.context_sensitive
        assert len(pf.sensitive_patterns) > 0

    def test_privacy_filter_custom_apps(self):
        """Test privacy filter with custom sensitive apps."""
        custom_apps = ["CustomBank", "MyWallet"]
        pf = PrivacyFilter(sensitive_apps=custom_apps)
        assert "CustomBank" in pf.always_sensitive
        assert "MyWallet" in pf.always_sensitive

    def test_sensitive_context_app_blocklist(self):
        """Test sensitive context detection via app blocklist."""
        pf = PrivacyFilter()

        # Password managers (always sensitive)
        assert pf.is_sensitive_context("1Password", "")
        assert pf.is_sensitive_context("LastPass - Vault", "")
        assert pf.is_sensitive_context("Bitwarden", "")

        # Browsers (context-sensitive, NOT always sensitive)
        assert not pf.is_sensitive_context("Chrome", "")  # No window = not sensitive
        assert not pf.is_sensitive_context("Firefox", "")
        assert not pf.is_sensitive_context("Chrome", "Google Search")  # Non-sensitive window

        # Browsers ARE sensitive with password/login windows
        assert pf.is_sensitive_context("Chrome", "Enter Password")
        assert pf.is_sensitive_context("Firefox", "Login to GitHub")

        # Terminal (always sensitive - shell commands can have secrets)
        assert pf.is_sensitive_context("Terminal", "")
        assert pf.is_sensitive_context("iTerm", "")

        # Non-sensitive apps without sensitive windows
        assert not pf.is_sensitive_context("VSCode", "")
        assert not pf.is_sensitive_context("Slack", "")

    def test_sensitive_context_window_patterns(self):
        """Test sensitive context detection via window title patterns."""
        pf = PrivacyFilter()

        # Password patterns
        assert pf.is_sensitive_context("Chrome", "Enter Password - Gmail")
        assert pf.is_sensitive_context("Firefox", "Login to GitHub")
        assert pf.is_sensitive_context("Edge", "Sign In - Microsoft")

        # Payment patterns
        assert pf.is_sensitive_context("Safari", "Credit Card Payment")
        assert pf.is_sensitive_context("Chrome", "Billing Information")

        # SSN patterns
        assert pf.is_sensitive_context("Chrome", "Social Security Number Required")

        # Private/confidential patterns
        assert pf.is_sensitive_context("Notes", "Private Notes")
        assert pf.is_sensitive_context("Word", "Confidential Document")

        # Non-sensitive windows
        assert not pf.is_sensitive_context("Chrome", "Google Search")
        assert not pf.is_sensitive_context("Slack", "General Channel")

    def test_sensitive_context_case_insensitive(self):
        """Test case-insensitive pattern matching."""
        pf = PrivacyFilter()

        assert pf.is_sensitive_context("Chrome", "PASSWORD entry")
        assert pf.is_sensitive_context("Chrome", "Enter password")
        assert pf.is_sensitive_context("Chrome", "CREDIT CARD")

    def test_redact_key_in_sensitive_context(self):
        """Test key redaction in sensitive contexts."""
        pf = PrivacyFilter()

        # Actual characters should be redacted
        assert pf.redact_key("a", True) == "[REDACTED]"
        assert pf.redact_key("1", True) == "[REDACTED]"
        assert pf.redact_key("!", True) == "[REDACTED]"

        # Special keys kept as-is
        assert pf.redact_key("[enter]", True) == "[enter]"
        assert pf.redact_key("[tab]", True) == "[tab]"
        assert pf.redact_key("[backspace]", True) == "[backspace]"

    def test_redact_key_in_non_sensitive_context(self):
        """Test key NOT redacted in non-sensitive contexts."""
        pf = PrivacyFilter()

        assert pf.redact_key("a", False) == "a"
        assert pf.redact_key("password123", False) == "password123"
        assert pf.redact_key("[enter]", False) == "[enter]"


class TestDeepObserverPrivacy:
    """Tests for DeepObserver privacy controls integration."""

    @patch('core.observer.config.load_config')
    @patch('core.observer.input_broker.get_input_broker')
    def test_observer_privacy_mode_redact(self, mock_broker, mock_config):
        """Test observer with privacy_mode=redact (default)."""
        mock_config.return_value = {
            "observer": {
                "enabled": True,
                "privacy_mode": "redact",
                "log_keys": True,
                "log_mouse": False,
            }
        }
        mock_broker.return_value = Mock()

        observer = DeepObserver()
        assert observer._privacy_mode == "redact"
        assert observer._privacy_filter is not None
        assert observer._total_redacted == 0

    @patch('core.observer.config.load_config')
    @patch('core.observer.input_broker.get_input_broker')
    def test_observer_privacy_mode_metadata(self, mock_broker, mock_config):
        """Test observer with privacy_mode=metadata (no keystrokes in sensitive contexts)."""
        mock_config.return_value = {
            "observer": {
                "enabled": True,
                "privacy_mode": "metadata",
                "log_keys": True,
                "log_mouse": False,
            }
        }
        mock_broker.return_value = Mock()

        observer = DeepObserver()
        assert observer._privacy_mode == "metadata"

    @patch('core.observer.config.load_config')
    @patch('core.observer.input_broker.get_input_broker')
    def test_observer_custom_sensitive_apps(self, mock_broker, mock_config):
        """Test observer with custom sensitive apps configuration."""
        custom_apps = ["MyBank", "CustomVault"]
        mock_config.return_value = {
            "observer": {
                "enabled": True,
                "sensitive_apps": custom_apps,
                "log_keys": True,
                "log_mouse": False,
            }
        }
        mock_broker.return_value = Mock()

        observer = DeepObserver()
        assert "MyBank" in observer._privacy_filter.always_sensitive
        assert "CustomVault" in observer._privacy_filter.always_sensitive

    @patch('core.observer.config.load_config')
    @patch('core.observer.input_broker.get_input_broker')
    def test_redaction_stats_tracked(self, mock_broker, mock_config):
        """Test that redaction statistics are tracked correctly."""
        mock_config.return_value = {
            "observer": {
                "enabled": True,
                "privacy_mode": "redact",
                "log_keys": True,
                "log_mouse": False,
            }
        }
        mock_broker.return_value = Mock()

        observer = DeepObserver()
        stats = observer.get_stats()

        assert "total_redacted" in stats
        assert "redaction_rate" in stats
        assert "privacy_mode" in stats
        assert stats["privacy_mode"] == "redact"
        assert stats["total_redacted"] == 0
        assert stats["redaction_rate"] == 0.0

    @patch('core.observer.config.load_config')
    @patch('core.observer.input_broker.get_input_broker')
    def test_get_recent_text_handles_redacted(self, mock_broker, mock_config):
        """Test get_recent_text() handles [REDACTED] entries."""
        mock_config.return_value = {
            "observer": {
                "enabled": True,
                "log_keys": True,
                "log_mouse": False,
            }
        }
        mock_broker.return_value = Mock()

        observer = DeepObserver()

        # Simulate some key events with redacted content
        observer._log_action("key", {"key": "h"})
        observer._log_action("key", {"key": "e"})
        observer._log_action("key", {"key": "l"})
        observer._log_action("key", {"key": "l"})
        observer._log_action("key", {"key": "o"})
        observer._log_action("key", {"key": "[REDACTED]"})
        observer._log_action("key", {"key": "[REDACTED]"})
        observer._log_action("key", {"key": "[REDACTED]"})

        # Without include_redacted, should show block chars
        text = observer.get_recent_text(seconds=60, include_redacted=False)
        assert "hello" in text
        assert "█" in text  # Visual indicator for redacted

        # With include_redacted=True, still shouldn't reconstruct actual content
        # (since actual content was never logged)
        text_with_redacted = observer.get_recent_text(seconds=60, include_redacted=True)
        assert "hello" in text_with_redacted


class TestPrivacyEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_empty_app_and_window(self):
        """Test privacy filter with empty app and window."""
        pf = PrivacyFilter()
        assert not pf.is_sensitive_context("", "")

    def test_partial_app_name_match(self):
        """Test that partial app name matches work."""
        pf = PrivacyFilter()
        # "1Password" in sensitive_apps should match "1Password 8"
        assert pf.is_sensitive_context("1Password 8 - Main Vault", "")

    def test_window_only_sensitive(self):
        """Test window title can trigger sensitivity without app match."""
        pf = PrivacyFilter()
        # Non-sensitive app, but sensitive window
        assert pf.is_sensitive_context("MyApp", "Enter your password")

    def test_multiple_pattern_matches(self):
        """Test window matching multiple sensitive patterns."""
        pf = PrivacyFilter()
        # Window with both "login" and "password"
        assert pf.is_sensitive_context("Chrome", "Login with Password")

    def test_special_characters_in_window(self):
        """Test window titles with special characters."""
        pf = PrivacyFilter()
        assert pf.is_sensitive_context("App", "Enter password (required)")
        assert pf.is_sensitive_context("App", "Payment: $99.99")


class TestPrivacyConfiguration:
    """Tests for privacy configuration options."""

    @patch('core.observer.config.load_config')
    @patch('core.observer.input_broker.get_input_broker')
    def test_default_privacy_mode(self, mock_broker, mock_config):
        """Test default privacy mode is 'redact'."""
        mock_config.return_value = {"observer": {"enabled": True}}
        mock_broker.return_value = Mock()

        observer = DeepObserver()
        assert observer._privacy_mode == "redact"

    @patch('core.observer.config.load_config')
    @patch('core.observer.input_broker.get_input_broker')
    def test_privacy_mode_case_insensitive(self, mock_broker, mock_config):
        """Test privacy mode configuration is case-insensitive."""
        mock_config.return_value = {
            "observer": {"privacy_mode": "METADATA"}
        }
        mock_broker.return_value = Mock()

        observer = DeepObserver()
        assert observer._privacy_mode == "metadata"

    def test_default_sensitive_apps_comprehensive(self):
        """Test default sensitive apps list is comprehensive."""
        assert "1Password" in ALWAYS_SENSITIVE_APPS
        assert "LastPass" in ALWAYS_SENSITIVE_APPS
        assert "Bitwarden" in ALWAYS_SENSITIVE_APPS
        assert "KeePass" in ALWAYS_SENSITIVE_APPS
        assert "Terminal" in ALWAYS_SENSITIVE_APPS
        assert "Signal" in ALWAYS_SENSITIVE_APPS

    @patch('core.observer.config.load_config')
    @patch('core.observer.input_broker.get_input_broker')
    def test_disabled_key_logging_skips_privacy(self, mock_broker, mock_config):
        """Test that privacy controls are skipped if key logging is disabled."""
        mock_config.return_value = {
            "observer": {
                "log_keys": False,  # Key logging disabled
                "privacy_mode": "redact",
            }
        }
        mock_broker.return_value = Mock()

        observer = DeepObserver()
        # Keyboard listener shouldn't start if log_keys=False
        result = observer._start_keyboard_listener()
        assert result is False
