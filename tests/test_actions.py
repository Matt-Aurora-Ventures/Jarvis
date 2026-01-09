"""
Tests for Actions Module.

Tests cover:
- UI action permission checks
- Action execution flow
- URL handling
- Error handling
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core import actions


# =============================================================================
# Test UI Permission Checks
# =============================================================================

class TestUIPermissions:
    """Test _ui_allowed and permission checks."""

    def test_ui_allowed_default_true(self):
        """UI actions should be allowed by default."""
        mock_cfg = {"actions": {"allow_ui": True, "require_confirm": False}}
        mock_state = {"ui_actions_enabled": True}

        with patch("core.config.load_config", return_value=mock_cfg):
            with patch("core.state.read_state", return_value=mock_state):
                result = actions._ui_allowed("test_action")
                assert result is True

    def test_ui_blocked_when_config_false(self):
        """UI actions should be blocked when config is false."""
        mock_cfg = {"actions": {"allow_ui": False, "require_confirm": False}}
        mock_state = {"ui_actions_enabled": True}

        with patch("core.config.load_config", return_value=mock_cfg):
            with patch("core.state.read_state", return_value=mock_state):
                result = actions._ui_allowed("test_action")
                assert result is False

    def test_ui_blocked_when_state_false(self):
        """UI actions should be blocked when state flag is false."""
        mock_cfg = {"actions": {"allow_ui": True, "require_confirm": False}}
        mock_state = {"ui_actions_enabled": False}

        with patch("core.config.load_config", return_value=mock_cfg):
            with patch("core.state.read_state", return_value=mock_state):
                result = actions._ui_allowed("test_action")
                assert result is False

    def test_ui_blocked_when_confirm_required_but_not_confirmed(self):
        """UI actions blocked when confirm required but not confirmed."""
        mock_cfg = {"actions": {"allow_ui": True, "require_confirm": True}}
        mock_state = {"ui_actions_enabled": True, "ui_actions_confirmed": False}

        with patch("core.config.load_config", return_value=mock_cfg):
            with patch("core.state.read_state", return_value=mock_state):
                result = actions._ui_allowed("test_action")
                assert result is False

    def test_ui_allowed_when_confirmed(self):
        """UI actions allowed when confirmed."""
        mock_cfg = {"actions": {"allow_ui": True, "require_confirm": True}}
        mock_state = {"ui_actions_enabled": True, "ui_actions_confirmed": True}

        with patch("core.config.load_config", return_value=mock_cfg):
            with patch("core.state.read_state", return_value=mock_state):
                result = actions._ui_allowed("test_action")
                assert result is True

    def test_ui_blocked_msg_returns_tuple(self):
        """_ui_blocked_msg should return (False, message) tuple."""
        success, msg = actions._ui_blocked_msg("test_action")
        assert success is False
        assert "test_action" in msg
        assert "disabled" in msg.lower()


# =============================================================================
# Test Browser Actions
# =============================================================================

class TestBrowserActions:
    """Test browser-related actions."""

    def test_open_browser_adds_https(self):
        """Should add https:// if missing."""
        mock_cfg = {"actions": {"allow_ui": True, "require_confirm": False}}
        mock_state = {"ui_actions_enabled": True}

        with patch("core.config.load_config", return_value=mock_cfg):
            with patch("core.state.read_state", return_value=mock_state):
                with patch.object(actions, "_open_in_firefox", return_value=(True, "OK")) as mock_firefox:
                    success, _ = actions.open_browser("example.com")
                    mock_firefox.assert_called_once_with("https://example.com")

    def test_open_browser_preserves_https(self):
        """Should preserve https:// if present."""
        mock_cfg = {"actions": {"allow_ui": True, "require_confirm": False}}
        mock_state = {"ui_actions_enabled": True}

        with patch("core.config.load_config", return_value=mock_cfg):
            with patch("core.state.read_state", return_value=mock_state):
                with patch.object(actions, "_open_in_firefox", return_value=(True, "OK")) as mock_firefox:
                    success, _ = actions.open_browser("https://example.com")
                    mock_firefox.assert_called_once_with("https://example.com")

    def test_open_browser_respects_ui_permission(self):
        """Should check UI permission before opening."""
        mock_cfg = {"actions": {"allow_ui": False, "require_confirm": False}}
        mock_state = {"ui_actions_enabled": True}

        with patch("core.config.load_config", return_value=mock_cfg):
            with patch("core.state.read_state", return_value=mock_state):
                success, msg = actions.open_browser("example.com")
                assert success is False
                assert "disabled" in msg.lower()

    def test_google_search_encodes_query(self):
        """Should URL encode search query."""
        mock_cfg = {"actions": {"allow_ui": True, "require_confirm": False}}
        mock_state = {"ui_actions_enabled": True}

        with patch("core.config.load_config", return_value=mock_cfg):
            with patch("core.state.read_state", return_value=mock_state):
                with patch.object(actions, "_open_in_firefox", return_value=(True, "OK")) as mock_firefox:
                    actions.google_search("test query")
                    call_args = mock_firefox.call_args[0][0]
                    assert "test%20query" in call_args or "test+query" in call_args


# =============================================================================
# Test Email Actions
# =============================================================================

class TestEmailActions:
    """Test email-related actions."""

    def test_open_mail_respects_permission(self):
        """Should check UI permission before opening mail."""
        mock_cfg = {"actions": {"allow_ui": False, "require_confirm": False}}
        mock_state = {"ui_actions_enabled": True}

        with patch("core.config.load_config", return_value=mock_cfg):
            with patch("core.state.read_state", return_value=mock_state):
                success, msg = actions.open_mail_app()
                assert success is False

    def test_open_mail_calls_computer(self):
        """Should call computer.open_app for Mail."""
        mock_cfg = {"actions": {"allow_ui": True, "require_confirm": False}}
        mock_state = {"ui_actions_enabled": True}

        with patch("core.config.load_config", return_value=mock_cfg):
            with patch("core.state.read_state", return_value=mock_state):
                with patch("core.computer.open_app", return_value=(True, "OK")) as mock_open:
                    actions.open_mail_app()
                    mock_open.assert_called_once_with("Mail")

    def test_send_email_via_mailto_builds_url(self):
        """Should build mailto URL correctly."""
        mock_cfg = {"actions": {"allow_ui": True, "require_confirm": False}}
        mock_state = {"ui_actions_enabled": True}

        with patch("core.config.load_config", return_value=mock_cfg):
            with patch("core.state.read_state", return_value=mock_state):
                with patch("core.computer.open_url", return_value=(True, "OK")) as mock_open:
                    actions.send_email_via_mailto("test@example.com", "Subject", "Body")
                    call_args = mock_open.call_args[0][0]
                    assert call_args.startswith("mailto:test@example.com")
                    assert "subject=" in call_args.lower()


# =============================================================================
# Test File/Finder Actions
# =============================================================================

class TestFileActions:
    """Test file-related actions."""

    def test_open_finder_expands_tilde(self):
        """Should expand ~ to home directory."""
        mock_cfg = {"actions": {"allow_ui": True, "require_confirm": False}}
        mock_state = {"ui_actions_enabled": True}

        with patch("core.config.load_config", return_value=mock_cfg):
            with patch("core.state.read_state", return_value=mock_state):
                with patch("core.computer.open_file", return_value=(True, "OK")) as mock_open:
                    actions.open_finder("~")
                    call_args = mock_open.call_args[0][0]
                    assert "~" not in call_args

    def test_open_terminal_calls_computer(self):
        """Should call computer.open_app for Terminal."""
        mock_cfg = {"actions": {"allow_ui": True, "require_confirm": False}}
        mock_state = {"ui_actions_enabled": True}

        with patch("core.config.load_config", return_value=mock_cfg):
            with patch("core.state.read_state", return_value=mock_state):
                with patch("core.computer.open_app", return_value=(True, "OK")) as mock_open:
                    actions.open_terminal()
                    mock_open.assert_called_once_with("Terminal")


# =============================================================================
# Test Firefox Functions
# =============================================================================

class TestFirefoxFunctions:
    """Test Firefox-specific functions."""

    def test_open_in_firefox_success(self):
        """Should return success when Firefox opens."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock()
            success, msg = actions._open_in_firefox("https://example.com")
            assert success is True
            assert "example.com" in msg

    def test_open_in_firefox_with_target(self):
        """Should include target URL in command."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock()
            actions._open_in_firefox("https://example.com")
            call_args = mock_run.call_args[0][0]
            assert "https://example.com" in call_args

    def test_open_in_firefox_without_target(self):
        """Should open Firefox without URL."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock()
            success, msg = actions._open_in_firefox("")
            assert success is True
            assert "Firefox opened" in msg

    def test_open_in_firefox_handles_error(self):
        """Should handle subprocess errors."""
        with patch("subprocess.run", side_effect=FileNotFoundError()):
            success, msg = actions._open_in_firefox("")
            assert success is False
            assert "not found" in msg.lower()

    def test_open_in_firefox_handles_called_process_error(self):
        """Should handle CalledProcessError."""
        import subprocess
        with patch("subprocess.run", side_effect=subprocess.CalledProcessError(1, "open")):
            success, msg = actions._open_in_firefox("")
            assert success is False
            assert "Failed" in msg
