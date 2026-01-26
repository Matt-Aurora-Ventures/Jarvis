"""
Comprehensive unit tests for core/actions.py - Actions Module.

Tests cover:
1. UI Permission Checks (_ui_allowed, _ui_blocked_msg)
2. Firefox Functions (_open_in_firefox)
3. Email Actions (open_mail_app, compose_email, send_email_via_mailto)
4. Browser Actions (open_browser, google_search)
5. File/Finder Actions (open_finder, open_terminal, open_notes, create_note)
6. Calendar Actions (open_calendar, create_calendar_event)
7. Messaging Actions (open_messages, send_imessage)
8. Utility Actions (set_reminder, speak, spotlight_search)
9. Window Management (minimize_window, close_window, new_window, new_tab)
10. Clipboard Actions (copy, paste, cut, undo, select_all, save_file)
11. App Management (get_current_app, list_running_apps, switch_to_app)
12. Action Registry (ACTION_REGISTRY)
13. Execute Functions (execute_action, execute_with_fallback, execute_with_discipline)
14. Alternative Actions (get_alternative_actions, get_available_actions)

Coverage target: 80%+ with 70+ tests
"""
import subprocess
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock

import pytest


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def mock_config_ui_allowed():
    """Mock config for UI actions allowed."""
    return {"actions": {"allow_ui": True, "require_confirm": False}}


@pytest.fixture
def mock_config_ui_blocked():
    """Mock config for UI actions blocked."""
    return {"actions": {"allow_ui": False, "require_confirm": False}}


@pytest.fixture
def mock_config_confirm_required():
    """Mock config requiring confirmation."""
    return {"actions": {"allow_ui": True, "require_confirm": True}}


@pytest.fixture
def mock_state_ui_enabled():
    """Mock state with UI actions enabled."""
    return {"ui_actions_enabled": True}


@pytest.fixture
def mock_state_ui_disabled():
    """Mock state with UI actions disabled."""
    return {"ui_actions_enabled": False}


@pytest.fixture
def mock_state_confirmed():
    """Mock state with UI actions confirmed."""
    return {"ui_actions_enabled": True, "ui_actions_confirmed": True}


@pytest.fixture
def mock_state_not_confirmed():
    """Mock state with UI actions not confirmed."""
    return {"ui_actions_enabled": True, "ui_actions_confirmed": False}


@pytest.fixture
def ui_allowed_patches(mock_config_ui_allowed, mock_state_ui_enabled):
    """Combined patches for UI allowed state."""
    return {
        "config": mock_config_ui_allowed,
        "state": mock_state_ui_enabled,
    }


@pytest.fixture
def mock_action_feedback():
    """Mock action feedback module."""
    mock = MagicMock()
    mock.record_action_intent.return_value = "test_intent_id"
    mock.record_action_outcome.return_value = MagicMock(
        outcome=MagicMock(success=True)
    )
    mock.get_feedback_loop.return_value.analyze_feedback = MagicMock()
    mock.get_action_recommendations.return_value = []
    return mock


# =============================================================================
# TEST CLASS: _ui_allowed Function
# =============================================================================


class TestUIAllowed:
    """Tests for the _ui_allowed function."""

    def test_ui_allowed_default_true(self, mock_config_ui_allowed, mock_state_ui_enabled):
        """UI actions should be allowed by default."""
        from core import actions

        with patch("core.config.load_config", return_value=mock_config_ui_allowed):
            with patch("core.state.read_state", return_value=mock_state_ui_enabled):
                result = actions._ui_allowed("test_action")
                assert result is True

    def test_ui_blocked_when_config_false(self, mock_config_ui_blocked, mock_state_ui_enabled):
        """UI actions should be blocked when config is false."""
        from core import actions

        with patch("core.config.load_config", return_value=mock_config_ui_blocked):
            with patch("core.state.read_state", return_value=mock_state_ui_enabled):
                result = actions._ui_allowed("test_action")
                assert result is False

    def test_ui_blocked_when_state_false(self, mock_config_ui_allowed, mock_state_ui_disabled):
        """UI actions should be blocked when state flag is false."""
        from core import actions

        with patch("core.config.load_config", return_value=mock_config_ui_allowed):
            with patch("core.state.read_state", return_value=mock_state_ui_disabled):
                result = actions._ui_allowed("test_action")
                assert result is False

    def test_ui_blocked_when_confirm_required_but_not_confirmed(
        self, mock_config_confirm_required, mock_state_not_confirmed
    ):
        """UI actions blocked when confirm required but not confirmed."""
        from core import actions

        with patch("core.config.load_config", return_value=mock_config_confirm_required):
            with patch("core.state.read_state", return_value=mock_state_not_confirmed):
                result = actions._ui_allowed("test_action")
                assert result is False

    def test_ui_allowed_when_confirmed(self, mock_config_confirm_required, mock_state_confirmed):
        """UI actions allowed when confirmed."""
        from core import actions

        with patch("core.config.load_config", return_value=mock_config_confirm_required):
            with patch("core.state.read_state", return_value=mock_state_confirmed):
                result = actions._ui_allowed("test_action")
                assert result is True

    def test_ui_allowed_missing_actions_config(self, mock_state_ui_enabled):
        """Should handle missing actions config section."""
        from core import actions

        empty_config = {}

        with patch("core.config.load_config", return_value=empty_config):
            with patch("core.state.read_state", return_value=mock_state_ui_enabled):
                result = actions._ui_allowed("test_action")
                # Default allow_ui=True
                assert result is True

    def test_ui_allowed_state_flag_none(self, mock_config_ui_allowed):
        """Should allow when state flag is None (not explicitly false)."""
        from core import actions

        state_no_flag = {}

        with patch("core.config.load_config", return_value=mock_config_ui_allowed):
            with patch("core.state.read_state", return_value=state_no_flag):
                result = actions._ui_allowed("test_action")
                assert result is True


# =============================================================================
# TEST CLASS: _ui_blocked_msg Function
# =============================================================================


class TestUIBlockedMsg:
    """Tests for the _ui_blocked_msg function."""

    def test_ui_blocked_msg_returns_tuple(self):
        """_ui_blocked_msg should return (False, message) tuple."""
        from core import actions

        success, msg = actions._ui_blocked_msg("test_action")
        assert success is False
        assert isinstance(msg, str)

    def test_ui_blocked_msg_contains_action_name(self):
        """Message should contain the blocked action name."""
        from core import actions

        success, msg = actions._ui_blocked_msg("my_blocked_action")
        assert "my_blocked_action" in msg

    def test_ui_blocked_msg_contains_disabled_info(self):
        """Message should explain that UI actions are disabled."""
        from core import actions

        success, msg = actions._ui_blocked_msg("test_action")
        assert "disabled" in msg.lower() or "blocked" in msg.lower()

    def test_ui_blocked_msg_mentions_config_options(self):
        """Message should mention configuration options."""
        from core import actions

        success, msg = actions._ui_blocked_msg("test_action")
        assert "allow_ui" in msg or "ui_actions_enabled" in msg


# =============================================================================
# TEST CLASS: _open_in_firefox Function
# =============================================================================


class TestOpenInFirefox:
    """Tests for the _open_in_firefox function."""

    def test_open_in_firefox_success(self):
        """Should return success when Firefox opens."""
        from core import actions

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock()
            success, msg = actions._open_in_firefox("https://example.com")
            assert success is True
            assert "example.com" in msg

    def test_open_in_firefox_with_target(self):
        """Should include target URL in command."""
        from core import actions

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock()
            actions._open_in_firefox("https://example.com")
            call_args = mock_run.call_args[0][0]
            assert "https://example.com" in call_args

    def test_open_in_firefox_without_target(self):
        """Should open Firefox without URL."""
        from core import actions

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock()
            success, msg = actions._open_in_firefox("")
            assert success is True
            assert "Firefox opened" in msg

    def test_open_in_firefox_handles_file_not_found(self):
        """Should handle FileNotFoundError."""
        from core import actions

        with patch("subprocess.run", side_effect=FileNotFoundError()):
            success, msg = actions._open_in_firefox("")
            assert success is False
            assert "not found" in msg.lower()

    def test_open_in_firefox_handles_called_process_error(self):
        """Should handle CalledProcessError."""
        from core import actions

        with patch("subprocess.run", side_effect=subprocess.CalledProcessError(1, "open")):
            success, msg = actions._open_in_firefox("")
            assert success is False
            assert "Failed" in msg

    def test_open_in_firefox_uses_correct_app_name(self):
        """Should use Firefox Developer Edition app name."""
        from core import actions

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock()
            actions._open_in_firefox("")
            call_args = mock_run.call_args[0][0]
            assert "Firefox Developer Edition" in call_args


# =============================================================================
# TEST CLASS: Email Actions
# =============================================================================


class TestEmailActions:
    """Tests for email-related actions."""

    def test_open_mail_respects_permission(self, mock_config_ui_blocked, mock_state_ui_enabled):
        """Should check UI permission before opening mail."""
        from core import actions

        with patch("core.config.load_config", return_value=mock_config_ui_blocked):
            with patch("core.state.read_state", return_value=mock_state_ui_enabled):
                success, msg = actions.open_mail_app()
                assert success is False
                assert "disabled" in msg.lower() or "blocked" in msg.lower()

    def test_open_mail_calls_computer(self, mock_config_ui_allowed, mock_state_ui_enabled):
        """Should call computer.open_app for Mail."""
        from core import actions

        with patch("core.config.load_config", return_value=mock_config_ui_allowed):
            with patch("core.state.read_state", return_value=mock_state_ui_enabled):
                with patch("core.computer.open_app", return_value=(True, "OK")) as mock_open:
                    actions.open_mail_app()
                    mock_open.assert_called_once_with("Mail")

    def test_compose_email_respects_permission(self, mock_config_ui_blocked, mock_state_ui_enabled):
        """Should check UI permission before composing email."""
        from core import actions

        with patch("core.config.load_config", return_value=mock_config_ui_blocked):
            with patch("core.state.read_state", return_value=mock_state_ui_enabled):
                success, msg = actions.compose_email("test@example.com", "Subject", "Body")
                assert success is False

    def test_compose_email_runs_applescript(self, mock_config_ui_allowed, mock_state_ui_enabled):
        """Should run AppleScript for composing email."""
        from core import actions

        with patch("core.config.load_config", return_value=mock_config_ui_allowed):
            with patch("core.state.read_state", return_value=mock_state_ui_enabled):
                with patch("core.computer._run_applescript", return_value=(True, "OK")) as mock_script:
                    success, msg = actions.compose_email("test@example.com", "Test Subject", "Test Body")
                    assert mock_script.called
                    script_arg = mock_script.call_args[0][0]
                    assert "Test Subject" in script_arg
                    assert "Test Body" in script_arg

    def test_compose_email_escapes_quotes(self, mock_config_ui_allowed, mock_state_ui_enabled):
        """Should escape quotes in subject and body."""
        from core import actions

        with patch("core.config.load_config", return_value=mock_config_ui_allowed):
            with patch("core.state.read_state", return_value=mock_state_ui_enabled):
                with patch("core.computer._run_applescript", return_value=(True, "OK")) as mock_script:
                    actions.compose_email("test@example.com", 'Say "Hello"', 'Body with "quotes"')
                    script_arg = mock_script.call_args[0][0]
                    assert '\\"' in script_arg

    def test_send_email_via_mailto_builds_url(self, mock_config_ui_allowed, mock_state_ui_enabled):
        """Should build mailto URL correctly."""
        from core import actions

        with patch("core.config.load_config", return_value=mock_config_ui_allowed):
            with patch("core.state.read_state", return_value=mock_state_ui_enabled):
                with patch("core.computer.open_url", return_value=(True, "OK")) as mock_open:
                    actions.send_email_via_mailto("test@example.com", "Subject", "Body")
                    call_args = mock_open.call_args[0][0]
                    assert call_args.startswith("mailto:test@example.com")
                    assert "subject=" in call_args.lower()

    def test_send_email_via_mailto_respects_permission(
        self, mock_config_ui_blocked, mock_state_ui_enabled
    ):
        """Should check UI permission."""
        from core import actions

        with patch("core.config.load_config", return_value=mock_config_ui_blocked):
            with patch("core.state.read_state", return_value=mock_state_ui_enabled):
                success, msg = actions.send_email_via_mailto("test@example.com")
                assert success is False


# =============================================================================
# TEST CLASS: Browser Actions
# =============================================================================


class TestBrowserActions:
    """Tests for browser-related actions."""

    def test_open_browser_adds_https(self, mock_config_ui_allowed, mock_state_ui_enabled):
        """Should add https:// if missing."""
        from core import actions

        with patch("core.config.load_config", return_value=mock_config_ui_allowed):
            with patch("core.state.read_state", return_value=mock_state_ui_enabled):
                with patch.object(actions, "_open_in_firefox", return_value=(True, "OK")) as mock_firefox:
                    success, _ = actions.open_browser("example.com")
                    mock_firefox.assert_called_once_with("https://example.com")

    def test_open_browser_preserves_https(self, mock_config_ui_allowed, mock_state_ui_enabled):
        """Should preserve https:// if present."""
        from core import actions

        with patch("core.config.load_config", return_value=mock_config_ui_allowed):
            with patch("core.state.read_state", return_value=mock_state_ui_enabled):
                with patch.object(actions, "_open_in_firefox", return_value=(True, "OK")) as mock_firefox:
                    success, _ = actions.open_browser("https://example.com")
                    mock_firefox.assert_called_once_with("https://example.com")

    def test_open_browser_preserves_http(self, mock_config_ui_allowed, mock_state_ui_enabled):
        """Should preserve http:// if present."""
        from core import actions

        with patch("core.config.load_config", return_value=mock_config_ui_allowed):
            with patch("core.state.read_state", return_value=mock_state_ui_enabled):
                with patch.object(actions, "_open_in_firefox", return_value=(True, "OK")) as mock_firefox:
                    success, _ = actions.open_browser("http://example.com")
                    mock_firefox.assert_called_once_with("http://example.com")

    def test_open_browser_uses_param_fallback(self, mock_config_ui_allowed, mock_state_ui_enabled):
        """Should use param if url is empty."""
        from core import actions

        with patch("core.config.load_config", return_value=mock_config_ui_allowed):
            with patch("core.state.read_state", return_value=mock_state_ui_enabled):
                with patch.object(actions, "_open_in_firefox", return_value=(True, "OK")) as mock_firefox:
                    success, _ = actions.open_browser(url="", param="test.com")
                    mock_firefox.assert_called_once_with("https://test.com")

    def test_open_browser_respects_ui_permission(self, mock_config_ui_blocked, mock_state_ui_enabled):
        """Should check UI permission before opening."""
        from core import actions

        with patch("core.config.load_config", return_value=mock_config_ui_blocked):
            with patch("core.state.read_state", return_value=mock_state_ui_enabled):
                success, msg = actions.open_browser("example.com")
                assert success is False
                assert "disabled" in msg.lower()

    def test_open_browser_empty_url(self, mock_config_ui_allowed, mock_state_ui_enabled):
        """Should open browser without URL."""
        from core import actions

        with patch("core.config.load_config", return_value=mock_config_ui_allowed):
            with patch("core.state.read_state", return_value=mock_state_ui_enabled):
                with patch.object(actions, "_open_in_firefox", return_value=(True, "OK")) as mock_firefox:
                    success, _ = actions.open_browser("")
                    mock_firefox.assert_called_once_with("")

    def test_google_search_encodes_query(self, mock_config_ui_allowed, mock_state_ui_enabled):
        """Should URL encode search query."""
        from core import actions

        with patch("core.config.load_config", return_value=mock_config_ui_allowed):
            with patch("core.state.read_state", return_value=mock_state_ui_enabled):
                with patch.object(actions, "_open_in_firefox", return_value=(True, "OK")) as mock_firefox:
                    actions.google_search("test query")
                    call_args = mock_firefox.call_args[0][0]
                    assert "test%20query" in call_args or "test+query" in call_args

    def test_google_search_respects_permission(self, mock_config_ui_blocked, mock_state_ui_enabled):
        """Should check UI permission."""
        from core import actions

        with patch("core.config.load_config", return_value=mock_config_ui_blocked):
            with patch("core.state.read_state", return_value=mock_state_ui_enabled):
                success, msg = actions.google_search("test")
                assert success is False


# =============================================================================
# TEST CLASS: File/Finder Actions
# =============================================================================


class TestFileActions:
    """Tests for file-related actions."""

    def test_open_finder_expands_tilde(self, mock_config_ui_allowed, mock_state_ui_enabled):
        """Should expand ~ to home directory."""
        from core import actions

        with patch("core.config.load_config", return_value=mock_config_ui_allowed):
            with patch("core.state.read_state", return_value=mock_state_ui_enabled):
                with patch("core.computer.open_file", return_value=(True, "OK")) as mock_open:
                    actions.open_finder("~")
                    call_args = mock_open.call_args[0][0]
                    assert "~" not in call_args

    def test_open_finder_default_home(self, mock_config_ui_allowed, mock_state_ui_enabled):
        """Should default to home directory."""
        from core import actions

        with patch("core.config.load_config", return_value=mock_config_ui_allowed):
            with patch("core.state.read_state", return_value=mock_state_ui_enabled):
                with patch("core.computer.open_file", return_value=(True, "OK")) as mock_open:
                    actions.open_finder()
                    assert mock_open.called

    def test_open_finder_respects_permission(self, mock_config_ui_blocked, mock_state_ui_enabled):
        """Should check UI permission."""
        from core import actions

        with patch("core.config.load_config", return_value=mock_config_ui_blocked):
            with patch("core.state.read_state", return_value=mock_state_ui_enabled):
                success, msg = actions.open_finder()
                assert success is False

    def test_open_terminal_calls_computer(self, mock_config_ui_allowed, mock_state_ui_enabled):
        """Should call computer.open_app for Terminal."""
        from core import actions

        with patch("core.config.load_config", return_value=mock_config_ui_allowed):
            with patch("core.state.read_state", return_value=mock_state_ui_enabled):
                with patch("core.computer.open_app", return_value=(True, "OK")) as mock_open:
                    actions.open_terminal()
                    mock_open.assert_called_once_with("Terminal")

    def test_open_terminal_respects_permission(self, mock_config_ui_blocked, mock_state_ui_enabled):
        """Should check UI permission."""
        from core import actions

        with patch("core.config.load_config", return_value=mock_config_ui_blocked):
            with patch("core.state.read_state", return_value=mock_state_ui_enabled):
                success, msg = actions.open_terminal()
                assert success is False


# =============================================================================
# TEST CLASS: Notes Actions
# =============================================================================


class TestNotesActions:
    """Tests for notes-related actions."""

    def test_open_notes_creates_directory(self, mock_config_ui_allowed, mock_state_ui_enabled, tmp_path):
        """Should create topic directory if missing."""
        from core import actions

        mock_dir = tmp_path / "notes" / "test-topic"

        with patch("core.config.load_config", return_value=mock_config_ui_allowed):
            with patch("core.state.read_state", return_value=mock_state_ui_enabled):
                with patch("core.notes_manager.topic_dir", return_value=mock_dir):
                    with patch("core.computer.open_file", return_value=(True, "OK")):
                        success, msg = actions.open_notes("test-topic")
                        assert mock_dir.exists()

    def test_open_notes_respects_permission(self, mock_config_ui_blocked, mock_state_ui_enabled):
        """Should check UI permission."""
        from core import actions

        with patch("core.config.load_config", return_value=mock_config_ui_blocked):
            with patch("core.state.read_state", return_value=mock_state_ui_enabled):
                success, msg = actions.open_notes("test")
                assert success is False

    def test_open_notes_fallback_to_finder(self, mock_config_ui_allowed, mock_state_ui_enabled, tmp_path):
        """Should try to reveal in Finder if open_file fails."""
        from core import actions

        mock_dir = tmp_path / "notes" / "test-topic"

        with patch("core.config.load_config", return_value=mock_config_ui_allowed):
            with patch("core.state.read_state", return_value=mock_state_ui_enabled):
                with patch("core.notes_manager.topic_dir", return_value=mock_dir):
                    with patch("core.computer.open_file", return_value=(False, "Error")):
                        with patch("subprocess.run") as mock_run:
                            mock_run.return_value = MagicMock()
                            success, msg = actions.open_notes("test-topic")
                            assert success is True
                            assert "Revealed" in msg or "ready at" in msg

    def test_create_note_saves_note(self, tmp_path):
        """Should save note and return paths."""
        from core import actions

        note_path = tmp_path / "note.md"
        summary_path = tmp_path / "summary.md"

        with patch("core.notes_manager.extract_topic_and_body", return_value=("test", "body")):
            with patch("core.notes_manager.save_note", return_value=(note_path, summary_path, "content")):
                success, msg = actions.create_note("Test Title", "Test Body", "test")
                assert success is True
                assert str(note_path) in msg

    def test_create_note_handles_empty_topic(self, tmp_path):
        """Should handle empty topic."""
        from core import actions

        note_path = tmp_path / "note.md"
        summary_path = tmp_path / "summary.md"

        with patch("core.notes_manager.extract_topic_and_body", return_value=("general", "body")):
            with patch("core.notes_manager.save_note", return_value=(note_path, summary_path, "content")):
                success, msg = actions.create_note("Test Title", "Test Body")
                assert success is True


# =============================================================================
# TEST CLASS: Calendar Actions
# =============================================================================


class TestCalendarActions:
    """Tests for calendar-related actions."""

    def test_open_calendar_respects_permission(self, mock_config_ui_blocked, mock_state_ui_enabled):
        """Should check UI permission."""
        from core import actions

        with patch("core.config.load_config", return_value=mock_config_ui_blocked):
            with patch("core.state.read_state", return_value=mock_state_ui_enabled):
                success, msg = actions.open_calendar()
                assert success is False

    def test_open_calendar_calls_computer(self, mock_config_ui_allowed, mock_state_ui_enabled):
        """Should call computer.open_app for Calendar."""
        from core import actions

        with patch("core.config.load_config", return_value=mock_config_ui_allowed):
            with patch("core.state.read_state", return_value=mock_state_ui_enabled):
                with patch("core.computer.open_app", return_value=(True, "OK")) as mock_open:
                    actions.open_calendar()
                    mock_open.assert_called_once_with("Calendar")

    def test_create_calendar_event_respects_permission(
        self, mock_config_ui_blocked, mock_state_ui_enabled
    ):
        """Should check UI permission."""
        from core import actions

        with patch("core.config.load_config", return_value=mock_config_ui_blocked):
            with patch("core.state.read_state", return_value=mock_state_ui_enabled):
                success, msg = actions.create_calendar_event("Event", "2024-01-01")
                assert success is False

    def test_create_calendar_event_runs_applescript(
        self, mock_config_ui_allowed, mock_state_ui_enabled
    ):
        """Should run AppleScript for creating event."""
        from core import actions

        with patch("core.config.load_config", return_value=mock_config_ui_allowed):
            with patch("core.state.read_state", return_value=mock_state_ui_enabled):
                with patch("core.computer._run_applescript", return_value=(True, "OK")) as mock_script:
                    success, msg = actions.create_calendar_event(
                        "Test Event", "2024-01-01", "10:00", 2
                    )
                    assert mock_script.called
                    script_arg = mock_script.call_args[0][0]
                    assert "Test Event" in script_arg


# =============================================================================
# TEST CLASS: Messaging Actions
# =============================================================================


class TestMessagingActions:
    """Tests for messaging-related actions."""

    def test_open_messages_respects_permission(self, mock_config_ui_blocked, mock_state_ui_enabled):
        """Should check UI permission."""
        from core import actions

        with patch("core.config.load_config", return_value=mock_config_ui_blocked):
            with patch("core.state.read_state", return_value=mock_state_ui_enabled):
                success, msg = actions.open_messages()
                assert success is False

    def test_open_messages_calls_computer(self, mock_config_ui_allowed, mock_state_ui_enabled):
        """Should call computer.open_app for Messages."""
        from core import actions

        with patch("core.config.load_config", return_value=mock_config_ui_allowed):
            with patch("core.state.read_state", return_value=mock_state_ui_enabled):
                with patch("core.computer.open_app", return_value=(True, "OK")) as mock_open:
                    actions.open_messages()
                    mock_open.assert_called_once_with("Messages")

    def test_send_imessage_respects_permission(self, mock_config_ui_blocked, mock_state_ui_enabled):
        """Should check UI permission."""
        from core import actions

        with patch("core.config.load_config", return_value=mock_config_ui_blocked):
            with patch("core.state.read_state", return_value=mock_state_ui_enabled):
                success, msg = actions.send_imessage("+1234567890", "Test message")
                assert success is False

    def test_send_imessage_runs_applescript(self, mock_config_ui_allowed, mock_state_ui_enabled):
        """Should run AppleScript for sending iMessage."""
        from core import actions

        with patch("core.config.load_config", return_value=mock_config_ui_allowed):
            with patch("core.state.read_state", return_value=mock_state_ui_enabled):
                with patch("core.computer._run_applescript", return_value=(True, "OK")) as mock_script:
                    success, msg = actions.send_imessage("+1234567890", "Hello!")
                    assert mock_script.called
                    script_arg = mock_script.call_args[0][0]
                    assert "Hello!" in script_arg


# =============================================================================
# TEST CLASS: Reminder Actions
# =============================================================================


class TestReminderActions:
    """Tests for reminder-related actions."""

    def test_set_reminder_respects_permission(self, mock_config_ui_blocked, mock_state_ui_enabled):
        """Should check UI permission."""
        from core import actions

        with patch("core.config.load_config", return_value=mock_config_ui_blocked):
            with patch("core.state.read_state", return_value=mock_state_ui_enabled):
                success, msg = actions.set_reminder("Test reminder")
                assert success is False

    def test_set_reminder_without_due_date(self, mock_config_ui_allowed, mock_state_ui_enabled):
        """Should create reminder without due date."""
        from core import actions

        with patch("core.config.load_config", return_value=mock_config_ui_allowed):
            with patch("core.state.read_state", return_value=mock_state_ui_enabled):
                with patch("core.computer._run_applescript", return_value=(True, "OK")) as mock_script:
                    success, msg = actions.set_reminder("Buy milk")
                    assert mock_script.called
                    script_arg = mock_script.call_args[0][0]
                    assert "Buy milk" in script_arg
                    assert "due date" not in script_arg.lower()

    def test_set_reminder_with_due_date(self, mock_config_ui_allowed, mock_state_ui_enabled):
        """Should create reminder with due date."""
        from core import actions

        with patch("core.config.load_config", return_value=mock_config_ui_allowed):
            with patch("core.state.read_state", return_value=mock_state_ui_enabled):
                with patch("core.computer._run_applescript", return_value=(True, "OK")) as mock_script:
                    success, msg = actions.set_reminder("Buy milk", "2024-01-01")
                    assert mock_script.called
                    script_arg = mock_script.call_args[0][0]
                    assert "due date" in script_arg


# =============================================================================
# TEST CLASS: Speak Action
# =============================================================================


class TestSpeakAction:
    """Tests for speak action."""

    def test_speak_success(self):
        """Should speak text successfully."""
        from core import actions

        mock_voice = MagicMock()
        mock_voice.resolve_say_voice.return_value = "Alex"

        with patch.dict(sys.modules, {"core.voice": mock_voice}):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock()
                success, msg = actions.speak("Hello world")
                assert success is True
                assert "Spoke" in msg

    def test_speak_handles_error(self):
        """Should handle errors."""
        from core import actions

        mock_voice = MagicMock()
        mock_voice.resolve_say_voice.side_effect = Exception("Voice error")

        with patch.dict(sys.modules, {"core.voice": mock_voice}):
            success, msg = actions.speak("Hello")
            assert success is False
            assert "Voice error" in msg

    def test_speak_with_custom_voice(self):
        """Should use custom voice."""
        from core import actions

        mock_voice = MagicMock()
        mock_voice.resolve_say_voice.return_value = "Samantha"

        with patch.dict(sys.modules, {"core.voice": mock_voice}):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock()
                success, msg = actions.speak("Hello", voice="Samantha")
                mock_voice.resolve_say_voice.assert_called_with("Samantha")


# =============================================================================
# TEST CLASS: Window Management Actions
# =============================================================================


class TestWindowManagementActions:
    """Tests for window management actions."""

    def test_minimize_window(self):
        """Should press Cmd+M to minimize."""
        from core import actions

        with patch("core.computer.press_key", return_value=(True, "OK")) as mock_press:
            success, msg = actions.minimize_window()
            mock_press.assert_called_once_with("m", ["command"])

    def test_close_window(self):
        """Should press Cmd+W to close."""
        from core import actions

        with patch("core.computer.press_key", return_value=(True, "OK")) as mock_press:
            success, msg = actions.close_window()
            mock_press.assert_called_once_with("w", ["command"])

    def test_new_window(self):
        """Should press Cmd+N for new window."""
        from core import actions

        with patch("core.computer.press_key", return_value=(True, "OK")) as mock_press:
            success, msg = actions.new_window()
            mock_press.assert_called_once_with("n", ["command"])

    def test_new_tab(self):
        """Should press Cmd+T for new tab."""
        from core import actions

        with patch("core.computer.press_key", return_value=(True, "OK")) as mock_press:
            success, msg = actions.new_tab()
            mock_press.assert_called_once_with("t", ["command"])

    def test_save_file(self):
        """Should press Cmd+S to save."""
        from core import actions

        with patch("core.computer.press_key", return_value=(True, "OK")) as mock_press:
            success, msg = actions.save_file()
            mock_press.assert_called_once_with("s", ["command"])


# =============================================================================
# TEST CLASS: Clipboard Actions
# =============================================================================


class TestClipboardActions:
    """Tests for clipboard actions."""

    def test_copy(self):
        """Should press Cmd+C to copy."""
        from core import actions

        with patch("core.computer.press_key", return_value=(True, "OK")) as mock_press:
            success, msg = actions.copy()
            mock_press.assert_called_once_with("c", ["command"])

    def test_paste(self):
        """Should press Cmd+V to paste."""
        from core import actions

        with patch("core.computer.press_key", return_value=(True, "OK")) as mock_press:
            success, msg = actions.paste()
            mock_press.assert_called_once_with("v", ["command"])

    def test_cut(self):
        """Should press Cmd+X to cut."""
        from core import actions

        with patch("core.computer.press_key", return_value=(True, "OK")) as mock_press:
            success, msg = actions.cut()
            mock_press.assert_called_once_with("x", ["command"])

    def test_undo(self):
        """Should press Cmd+Z to undo."""
        from core import actions

        with patch("core.computer.press_key", return_value=(True, "OK")) as mock_press:
            success, msg = actions.undo()
            mock_press.assert_called_once_with("z", ["command"])

    def test_select_all(self):
        """Should press Cmd+A to select all."""
        from core import actions

        with patch("core.computer.press_key", return_value=(True, "OK")) as mock_press:
            success, msg = actions.select_all()
            mock_press.assert_called_once_with("a", ["command"])


# =============================================================================
# TEST CLASS: Spotlight Search
# =============================================================================


class TestSpotlightSearch:
    """Tests for spotlight search action."""

    def test_spotlight_search_opens_spotlight(self):
        """Should press Cmd+Space to open Spotlight."""
        from core import actions

        with patch("core.computer.press_key", return_value=(True, "OK")) as mock_press:
            with patch("core.computer.type_text", return_value=(True, "OK")):
                success, msg = actions.spotlight_search()
                mock_press.assert_called_with("space", ["command"])

    def test_spotlight_search_with_query(self):
        """Should type query after opening Spotlight."""
        from core import actions

        with patch("core.computer.press_key", return_value=(True, "OK")):
            with patch("core.computer.type_text", return_value=(True, "OK")) as mock_type:
                with patch("time.sleep"):
                    success, msg = actions.spotlight_search("test query")
                    mock_type.assert_called_with("test query")

    def test_spotlight_search_waits_before_typing(self):
        """Should wait before typing query."""
        from core import actions

        with patch("core.computer.press_key", return_value=(True, "OK")):
            with patch("core.computer.type_text", return_value=(True, "OK")):
                with patch("time.sleep") as mock_sleep:
                    actions.spotlight_search("query")
                    mock_sleep.assert_called_with(0.3)


# =============================================================================
# TEST CLASS: App Management Actions
# =============================================================================


class TestAppManagementActions:
    """Tests for app management actions."""

    def test_get_current_app(self):
        """Should get current app name."""
        from core import actions

        with patch("core.computer._run_applescript", return_value=(True, "Finder")):
            result = actions.get_current_app()
            assert result == "Finder"

    def test_get_current_app_failure(self):
        """Should return Unknown on failure."""
        from core import actions

        with patch("core.computer._run_applescript", return_value=(False, "Error")):
            result = actions.get_current_app()
            assert result == "Unknown"

    def test_list_running_apps(self):
        """Should list running apps."""
        from core import actions

        with patch("core.computer._run_applescript", return_value=(True, "Finder, Safari, Mail")):
            result = actions.list_running_apps()
            assert len(result) == 3
            assert "Finder" in result
            assert "Safari" in result

    def test_list_running_apps_empty(self):
        """Should return empty list on failure."""
        from core import actions

        with patch("core.computer._run_applescript", return_value=(False, "")):
            result = actions.list_running_apps()
            assert result == []

    def test_switch_to_app(self):
        """Should switch to app."""
        from core import actions

        with patch("core.computer.open_app", return_value=(True, "OK")) as mock_open:
            success, msg = actions.switch_to_app("Finder")
            mock_open.assert_called_once_with("Finder")


# =============================================================================
# TEST CLASS: Action Registry
# =============================================================================


class TestActionRegistry:
    """Tests for ACTION_REGISTRY."""

    def test_registry_has_expected_actions(self):
        """Registry should have all expected actions."""
        from core.actions import ACTION_REGISTRY

        expected_actions = [
            "open_mail",
            "compose_email",
            "send_email",
            "open_browser",
            "google",
            "search",
            "open_finder",
            "open_terminal",
            "open_notes",
            "create_note",
            "open_calendar",
            "create_event",
            "open_messages",
            "send_message",
            "set_reminder",
            "speak",
            "switch_app",
            "minimize",
            "close_window",
            "new_window",
            "new_tab",
            "save",
            "copy",
            "paste",
            "cut",
            "undo",
            "select_all",
            "spotlight",
        ]

        for action in expected_actions:
            assert action in ACTION_REGISTRY, f"Missing action: {action}"

    def test_registry_values_are_callable(self):
        """All registry values should be callable."""
        from core.actions import ACTION_REGISTRY

        for name, func in ACTION_REGISTRY.items():
            assert callable(func), f"Action {name} is not callable"


# =============================================================================
# TEST CLASS: execute_action Function
# =============================================================================


class TestExecuteAction:
    """Tests for execute_action function."""

    def test_execute_action_unknown_action(self):
        """Should return failure for unknown action."""
        from core import actions

        success, msg = actions.execute_action("unknown_action_xyz")
        assert success is False
        assert "Unknown action" in msg

    def test_execute_action_calls_registry_function(
        self, mock_config_ui_allowed, mock_state_ui_enabled
    ):
        """Should call the registered function."""
        from core import actions

        with patch("core.config.load_config", return_value=mock_config_ui_allowed):
            with patch("core.state.read_state", return_value=mock_state_ui_enabled):
                with patch("core.computer.open_app", return_value=(True, "OK")):
                    with patch("core.action_feedback.record_action_intent", return_value="intent_1"):
                        with patch("core.action_feedback.record_action_outcome"):
                            with patch("core.action_feedback.get_feedback_loop"):
                                success, msg = actions.execute_action("open_calendar")
                                assert success is True

    def test_execute_action_with_kwargs(self, mock_config_ui_allowed, mock_state_ui_enabled):
        """Should pass kwargs to action function."""
        from core import actions

        with patch("core.config.load_config", return_value=mock_config_ui_allowed):
            with patch("core.state.read_state", return_value=mock_state_ui_enabled):
                with patch.object(actions, "_open_in_firefox", return_value=(True, "OK")) as mock_firefox:
                    with patch("core.action_feedback.record_action_intent", return_value="intent_1"):
                        with patch("core.action_feedback.record_action_outcome"):
                            with patch("core.action_feedback.get_feedback_loop"):
                                actions.execute_action("open_browser", url="https://test.com")
                                mock_firefox.assert_called_with("https://test.com")

    def test_execute_action_records_intent(self, mock_config_ui_allowed, mock_state_ui_enabled):
        """Should record action intent."""
        from core import actions

        with patch("core.config.load_config", return_value=mock_config_ui_allowed):
            with patch("core.state.read_state", return_value=mock_state_ui_enabled):
                with patch("core.computer.open_app", return_value=(True, "OK")):
                    with patch("core.action_feedback.record_action_intent") as mock_intent:
                        mock_intent.return_value = "intent_1"
                        with patch("core.action_feedback.record_action_outcome"):
                            with patch("core.action_feedback.get_feedback_loop"):
                                actions.execute_action(
                                    "open_calendar",
                                    why="Testing",
                                    expected_outcome="Calendar opens",
                                )
                                mock_intent.assert_called_once()
                                call_kwargs = mock_intent.call_args[1]
                                assert call_kwargs["why"] == "Testing"
                                assert call_kwargs["expected_outcome"] == "Calendar opens"

    def test_execute_action_records_outcome(self, mock_config_ui_allowed, mock_state_ui_enabled):
        """Should record action outcome."""
        from core import actions

        with patch("core.config.load_config", return_value=mock_config_ui_allowed):
            with patch("core.state.read_state", return_value=mock_state_ui_enabled):
                with patch("core.computer.open_app", return_value=(True, "Opened")):
                    with patch("core.action_feedback.record_action_intent", return_value="intent_1"):
                        with patch("core.action_feedback.record_action_outcome") as mock_outcome:
                            mock_outcome.return_value = MagicMock()
                            with patch("core.action_feedback.get_feedback_loop"):
                                actions.execute_action("open_calendar")
                                mock_outcome.assert_called_once()
                                call_kwargs = mock_outcome.call_args[1]
                                assert call_kwargs["success"] is True
                                assert call_kwargs["intent_id"] == "intent_1"

    def test_execute_action_handles_exception(self, mock_config_ui_allowed, mock_state_ui_enabled):
        """Should handle exceptions from action function."""
        from core import actions

        with patch("core.config.load_config", return_value=mock_config_ui_allowed):
            with patch("core.state.read_state", return_value=mock_state_ui_enabled):
                with patch("core.computer.open_app", side_effect=Exception("Test error")):
                    with patch("core.action_feedback.record_action_intent", return_value="intent_1"):
                        with patch("core.action_feedback.record_action_outcome") as mock_outcome:
                            success, msg = actions.execute_action("open_calendar")
                            assert success is False
                            assert "Test error" in msg
                            # Should still record outcome
                            mock_outcome.assert_called()

    def test_execute_action_default_why(self, mock_config_ui_allowed, mock_state_ui_enabled):
        """Should use default why if not provided."""
        from core import actions

        with patch("core.config.load_config", return_value=mock_config_ui_allowed):
            with patch("core.state.read_state", return_value=mock_state_ui_enabled):
                with patch("core.computer.open_app", return_value=(True, "OK")):
                    with patch("core.action_feedback.record_action_intent") as mock_intent:
                        mock_intent.return_value = "intent_1"
                        with patch("core.action_feedback.record_action_outcome"):
                            with patch("core.action_feedback.get_feedback_loop"):
                                actions.execute_action("open_calendar")
                                call_kwargs = mock_intent.call_args[1]
                                assert "open_calendar" in call_kwargs["why"]


# =============================================================================
# TEST CLASS: execute_with_fallback Function
# =============================================================================


class TestExecuteWithFallback:
    """Tests for execute_with_fallback function."""

    def test_fallback_primary_success(self, mock_config_ui_allowed, mock_state_ui_enabled):
        """Should return success if primary action succeeds."""
        from core import actions

        with patch("core.config.load_config", return_value=mock_config_ui_allowed):
            with patch("core.state.read_state", return_value=mock_state_ui_enabled):
                with patch("core.computer.open_app", return_value=(True, "OK")):
                    with patch("core.action_feedback.record_action_intent", return_value="i1"):
                        with patch("core.action_feedback.record_action_outcome"):
                            with patch("core.action_feedback.get_feedback_loop"):
                                success, msg = actions.execute_with_fallback("open_calendar")
                                assert success is True

    def test_fallback_uses_explicit_fallbacks(self, mock_config_ui_allowed, mock_state_ui_enabled):
        """Should try explicit fallbacks when primary fails."""
        from core import actions

        call_count = [0]

        def mock_execute(action_name, **kwargs):
            call_count[0] += 1
            if action_name == "primary":
                return False, "Primary failed"
            return True, "Fallback worked"

        with patch.object(actions, "execute_action", side_effect=mock_execute):
            with patch.object(actions, "get_alternative_actions", return_value=[]):
                success, msg = actions.execute_with_fallback(
                    "primary",
                    fallbacks=[{"action": "fallback_action", "params": {}}],
                )
                assert success is True
                assert "fallback" in msg.lower()

    def test_fallback_uses_alternatives(self, mock_config_ui_allowed, mock_state_ui_enabled):
        """Should try alternatives when primary and explicit fallbacks fail."""
        from core import actions

        def mock_execute(action_name, **kwargs):
            if action_name == "compose_email":
                return False, "Failed"
            if action_name == "send_email":
                return True, "Worked"
            return False, "Failed"

        with patch.object(actions, "execute_action", side_effect=mock_execute):
            success, msg = actions.execute_with_fallback("compose_email")
            assert success is True
            assert "alternative" in msg.lower()

    def test_fallback_all_fail(self):
        """Should return failure if all attempts fail."""
        from core import actions

        def mock_execute(action_name, **kwargs):
            return False, "Failed"

        with patch.object(actions, "execute_action", side_effect=mock_execute):
            with patch.object(actions, "get_alternative_actions", return_value=[]):
                success, msg = actions.execute_with_fallback("nonexistent")
                assert success is False
                assert "All attempts failed" in msg


# =============================================================================
# TEST CLASS: execute_with_discipline Function
# =============================================================================


class TestExecuteWithDiscipline:
    """Tests for execute_with_discipline function."""

    def test_discipline_unknown_action(self):
        """Should return failure for unknown action."""
        from core import actions

        success, msg, feedback = actions.execute_with_discipline(
            "unknown_xyz",
            why="Testing",
            expected_outcome="Should fail",
        )
        assert success is False
        assert "Unknown action" in msg
        assert feedback == {}

    def test_discipline_returns_feedback_dict(self, mock_config_ui_allowed, mock_state_ui_enabled):
        """Should return feedback dictionary."""
        from core import actions

        with patch("core.config.load_config", return_value=mock_config_ui_allowed):
            with patch("core.state.read_state", return_value=mock_state_ui_enabled):
                with patch("core.computer.open_app", return_value=(True, "OK")):
                    with patch("core.action_feedback.record_action_intent", return_value="i1"):
                        with patch("core.action_feedback.record_action_outcome") as mock_out:
                            mock_out.return_value = MagicMock()
                            with patch("core.action_feedback.get_feedback_loop"):
                                with patch("core.action_feedback.get_action_recommendations", return_value=[]):
                                    success, msg, feedback = actions.execute_with_discipline(
                                        "open_calendar",
                                        why="Testing",
                                        expected_outcome="Calendar opens",
                                    )
                                    assert success is True
                                    assert "intent_id" in feedback
                                    assert "success" in feedback
                                    assert "duration_ms" in feedback

    def test_discipline_with_success_criteria(self, mock_config_ui_allowed, mock_state_ui_enabled):
        """Should handle success criteria."""
        from core import actions

        with patch("core.config.load_config", return_value=mock_config_ui_allowed):
            with patch("core.state.read_state", return_value=mock_state_ui_enabled):
                with patch("core.computer.open_app", return_value=(True, "OK")):
                    with patch("core.action_feedback.record_action_intent") as mock_intent:
                        mock_intent.return_value = "i1"
                        with patch("core.action_feedback.record_action_outcome"):
                            with patch("core.action_feedback.get_feedback_loop"):
                                with patch("core.action_feedback.get_action_recommendations", return_value=[]):
                                    success, msg, feedback = actions.execute_with_discipline(
                                        "open_calendar",
                                        why="Testing",
                                        expected_outcome="Calendar opens",
                                        success_criteria=["calendar_visible", "no_errors"],
                                    )
                                    call_kwargs = mock_intent.call_args[1]
                                    assert "calendar_visible" in call_kwargs["success_criteria"]

    def test_discipline_with_objective_id(self, mock_config_ui_allowed, mock_state_ui_enabled):
        """Should handle objective_id."""
        from core import actions

        with patch("core.config.load_config", return_value=mock_config_ui_allowed):
            with patch("core.state.read_state", return_value=mock_state_ui_enabled):
                with patch("core.computer.open_app", return_value=(True, "OK")):
                    with patch("core.action_feedback.record_action_intent") as mock_intent:
                        mock_intent.return_value = "i1"
                        with patch("core.action_feedback.record_action_outcome"):
                            with patch("core.action_feedback.get_feedback_loop"):
                                with patch("core.action_feedback.get_action_recommendations", return_value=[]):
                                    success, msg, feedback = actions.execute_with_discipline(
                                        "open_calendar",
                                        why="Testing",
                                        expected_outcome="Calendar opens",
                                        objective_id="obj_123",
                                    )
                                    call_kwargs = mock_intent.call_args[1]
                                    assert call_kwargs["objective_id"] == "obj_123"

    def test_discipline_handles_exception(self, mock_config_ui_allowed, mock_state_ui_enabled):
        """Should handle exceptions and return feedback."""
        from core import actions

        with patch("core.config.load_config", return_value=mock_config_ui_allowed):
            with patch("core.state.read_state", return_value=mock_state_ui_enabled):
                with patch("core.computer.open_app", side_effect=Exception("Test error")):
                    with patch("core.action_feedback.record_action_intent", return_value="i1"):
                        with patch("core.action_feedback.record_action_outcome"):
                            with patch("core.action_feedback.get_action_recommendations", return_value=[]):
                                success, msg, feedback = actions.execute_with_discipline(
                                    "open_calendar",
                                    why="Testing",
                                    expected_outcome="Calendar opens",
                                )
                                assert success is False
                                assert "Test error" in msg
                                assert "error" in feedback


# =============================================================================
# TEST CLASS: get_alternative_actions Function
# =============================================================================


class TestGetAlternativeActions:
    """Tests for get_alternative_actions function."""

    def test_alternatives_for_compose_email(self):
        """Should return alternatives for compose_email."""
        from core.actions import get_alternative_actions

        alts = get_alternative_actions("compose_email")
        assert "send_email" in alts or "open_mail" in alts

    def test_alternatives_for_google(self):
        """Should return alternatives for google."""
        from core.actions import get_alternative_actions

        alts = get_alternative_actions("google")
        assert "open_browser" in alts

    def test_alternatives_for_unknown(self):
        """Should return empty list for unknown action."""
        from core.actions import get_alternative_actions

        alts = get_alternative_actions("unknown_action_xyz")
        assert alts == []

    def test_alternatives_for_search(self):
        """Should return alternatives for search."""
        from core.actions import get_alternative_actions

        alts = get_alternative_actions("search")
        assert len(alts) > 0


# =============================================================================
# TEST CLASS: get_available_actions Function
# =============================================================================


class TestGetAvailableActions:
    """Tests for get_available_actions function."""

    def test_get_available_actions_returns_list(self):
        """Should return a list."""
        from core.actions import get_available_actions

        result = get_available_actions()
        assert isinstance(result, list)

    def test_get_available_actions_not_empty(self):
        """Should return non-empty list."""
        from core.actions import get_available_actions

        result = get_available_actions()
        assert len(result) > 0

    def test_get_available_actions_contains_known(self):
        """Should contain known actions."""
        from core.actions import get_available_actions

        result = get_available_actions()
        assert "open_browser" in result
        assert "copy" in result
        assert "paste" in result


# =============================================================================
# RUN CONFIGURATION
# =============================================================================


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
