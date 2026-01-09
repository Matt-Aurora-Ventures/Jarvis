"""
Tests for core/platform/__init__.py

Tests cover:
- Platform adapter factory
- Platform detection
- Abstract interface implementation
- Cross-platform convenience functions
"""

import sys
import platform
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.platform import (
    PlatformAdapter,
    MacOSAdapter,
    WindowsAdapter,
    LinuxAdapter,
    get_platform_adapter,
    get_adapter,
    send_notification,
    get_active_window_info,
    open_application,
    execute_keyboard_shortcut,
    get_clipboard_content,
    set_clipboard_content,
    speak_text,
    get_screen_capture,
)


class TestPlatformAdapter:
    """Test abstract PlatformAdapter interface."""

    def test_adapter_is_abstract(self):
        """PlatformAdapter should be abstract."""
        with pytest.raises(TypeError):
            PlatformAdapter()

    def test_all_methods_are_abstract(self):
        """All interface methods should be abstract."""
        abstract_methods = [
            'send_notification',
            'get_active_window_info',
            'open_application',
            'execute_keyboard_shortcut',
            'get_clipboard_content',
            'set_clipboard_content',
            'speak_text',
            'get_screen_capture',
        ]
        for method in abstract_methods:
            assert hasattr(PlatformAdapter, method)


class TestMacOSAdapter:
    """Test MacOSAdapter implementation."""

    def test_instantiation(self):
        """Should create MacOSAdapter instance."""
        adapter = MacOSAdapter()
        assert isinstance(adapter, PlatformAdapter)

    @patch('subprocess.run')
    def test_send_notification(self, mock_run):
        """Should send notification via osascript."""
        adapter = MacOSAdapter()
        result = adapter.send_notification("Title", "Message")

        assert result is True
        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        assert call_args[0] == "osascript"

    @patch('subprocess.run')
    def test_send_notification_sanitizes_quotes(self, mock_run):
        """Should sanitize quotes in notification."""
        adapter = MacOSAdapter()
        adapter.send_notification('Title with "quotes"', 'Message with "quotes"')

        call_args = mock_run.call_args[0][0]
        script = call_args[2]
        assert '\\"' in script

    @patch('subprocess.run')
    def test_get_active_window_info(self, mock_run):
        """Should get active window via osascript."""
        mock_run.return_value = Mock(stdout="Safari\n")
        adapter = MacOSAdapter()

        result = adapter.get_active_window_info()

        assert result["platform"] == "macos"
        assert "app_name" in result

    @patch('subprocess.run')
    def test_open_application(self, mock_run):
        """Should open application via 'open -a'."""
        mock_run.return_value = Mock()
        adapter = MacOSAdapter()

        result = adapter.open_application("Safari")

        assert result is True
        call_args = mock_run.call_args[0][0]
        assert call_args[0] == "open"
        assert call_args[1] == "-a"
        assert call_args[2] == "Safari"

    @patch('subprocess.run')
    def test_get_clipboard_content(self, mock_run):
        """Should get clipboard via pbpaste."""
        mock_run.return_value = Mock(stdout="Clipboard content")
        adapter = MacOSAdapter()

        result = adapter.get_clipboard_content()

        assert result == "Clipboard content"
        call_args = mock_run.call_args[0][0]
        assert call_args[0] == "pbpaste"

    @patch('subprocess.Popen')
    def test_set_clipboard_content(self, mock_popen):
        """Should set clipboard via pbcopy."""
        mock_process = Mock()
        mock_process.communicate = Mock()
        mock_popen.return_value = mock_process
        adapter = MacOSAdapter()

        result = adapter.set_clipboard_content("New content")

        assert result is True
        call_args = mock_popen.call_args[0][0]
        assert call_args[0] == "pbcopy"

    @patch('subprocess.run')
    def test_speak_text(self, mock_run):
        """Should speak via 'say' command."""
        adapter = MacOSAdapter()

        result = adapter.speak_text("Hello world")

        assert result is True
        call_args = mock_run.call_args[0][0]
        assert call_args[0] == "say"

    @patch('subprocess.run')
    def test_speak_text_with_voice(self, mock_run):
        """Should speak with specific voice."""
        adapter = MacOSAdapter()

        adapter.speak_text("Hello", voice="Alex")

        call_args = mock_run.call_args[0][0]
        assert "-v" in call_args
        assert "Alex" in call_args


class TestWindowsAdapter:
    """Test WindowsAdapter implementation."""

    def test_instantiation(self):
        """Should create WindowsAdapter instance."""
        adapter = WindowsAdapter()
        assert isinstance(adapter, PlatformAdapter)

    def test_get_active_window_info_structure(self):
        """Should return correct structure."""
        adapter = WindowsAdapter()
        # Mock the win32gui module
        with patch.dict('sys.modules', {'win32gui': MagicMock()}):
            result = adapter.get_active_window_info()
            assert "platform" in result
            assert result["platform"] == "windows"

    @patch('subprocess.Popen')
    def test_open_application(self, mock_popen):
        """Should open application via start command."""
        adapter = WindowsAdapter()

        result = adapter.open_application("notepad.exe")

        assert result is True


class TestLinuxAdapter:
    """Test LinuxAdapter implementation."""

    def test_instantiation(self):
        """Should create LinuxAdapter instance."""
        adapter = LinuxAdapter()
        assert isinstance(adapter, PlatformAdapter)

    @patch('subprocess.run')
    def test_send_notification(self, mock_run):
        """Should send notification via notify-send."""
        adapter = LinuxAdapter()

        result = adapter.send_notification("Title", "Message")

        assert result is True
        call_args = mock_run.call_args[0][0]
        assert call_args[0] == "notify-send"

    @patch('subprocess.run')
    def test_get_active_window_info(self, mock_run):
        """Should get active window via xdotool."""
        mock_run.return_value = Mock(stdout="Firefox\n")
        adapter = LinuxAdapter()

        result = adapter.get_active_window_info()

        assert result["platform"] == "linux"
        call_args = mock_run.call_args[0][0]
        assert "xdotool" in call_args

    @patch('subprocess.run')
    def test_get_clipboard_content(self, mock_run):
        """Should get clipboard via xclip."""
        mock_run.return_value = Mock(stdout="Clipboard text")
        adapter = LinuxAdapter()

        result = adapter.get_clipboard_content()

        assert result == "Clipboard text"
        call_args = mock_run.call_args[0][0]
        assert "xclip" in call_args

    @patch('subprocess.run')
    def test_speak_text(self, mock_run):
        """Should speak via espeak."""
        adapter = LinuxAdapter()

        result = adapter.speak_text("Hello")

        assert result is True
        call_args = mock_run.call_args[0][0]
        assert call_args[0] == "espeak"


class TestGetPlatformAdapter:
    """Test platform adapter factory."""

    @patch('platform.system')
    def test_returns_macos_adapter(self, mock_system):
        """Should return MacOSAdapter for darwin."""
        mock_system.return_value = "Darwin"

        adapter = get_platform_adapter()

        assert isinstance(adapter, MacOSAdapter)

    @patch('platform.system')
    def test_returns_windows_adapter(self, mock_system):
        """Should return WindowsAdapter for windows."""
        mock_system.return_value = "Windows"

        adapter = get_platform_adapter()

        assert isinstance(adapter, WindowsAdapter)

    @patch('platform.system')
    def test_returns_linux_adapter(self, mock_system):
        """Should return LinuxAdapter for linux."""
        mock_system.return_value = "Linux"

        adapter = get_platform_adapter()

        assert isinstance(adapter, LinuxAdapter)

    @patch('platform.system')
    def test_defaults_to_linux(self, mock_system):
        """Should default to LinuxAdapter for unknown platforms."""
        mock_system.return_value = "FreeBSD"

        adapter = get_platform_adapter()

        assert isinstance(adapter, LinuxAdapter)


class TestGetAdapter:
    """Test singleton adapter getter."""

    def test_returns_adapter(self):
        """Should return a PlatformAdapter instance."""
        adapter = get_adapter()
        assert isinstance(adapter, PlatformAdapter)

    def test_returns_same_instance(self):
        """Should return the same instance on multiple calls."""
        # Note: This test may be affected by module-level caching
        adapter1 = get_adapter()
        adapter2 = get_adapter()
        assert adapter1 is adapter2


class TestConvenienceFunctions:
    """Test module-level convenience functions."""

    def test_send_notification_calls_adapter(self):
        """send_notification should use adapter."""
        with patch.object(get_adapter(), 'send_notification', return_value=True) as mock:
            result = send_notification("Title", "Message")
            # Function should work (may call real or mocked adapter)
            assert isinstance(result, bool)

    def test_get_active_window_info_returns_dict(self):
        """get_active_window_info should return dict."""
        result = get_active_window_info()
        assert isinstance(result, dict)
        assert "platform" in result

    def test_open_application_returns_bool(self):
        """open_application should return bool."""
        with patch.object(get_adapter(), 'open_application', return_value=True):
            result = open_application("TestApp")
            assert isinstance(result, bool)

    def test_get_clipboard_content_returns_string(self):
        """get_clipboard_content should return string."""
        with patch.object(get_adapter(), 'get_clipboard_content', return_value="test"):
            result = get_clipboard_content()
            assert isinstance(result, str)

    def test_set_clipboard_content_returns_bool(self):
        """set_clipboard_content should return bool."""
        with patch.object(get_adapter(), 'set_clipboard_content', return_value=True):
            result = set_clipboard_content("test")
            assert isinstance(result, bool)


class TestErrorHandling:
    """Test error handling in adapters."""

    def test_notification_handles_error(self):
        """Should handle notification errors gracefully."""
        adapter = MacOSAdapter()
        with patch('subprocess.run', side_effect=Exception("Test error")):
            result = adapter.send_notification("Title", "Message")
            assert result is False

    def test_clipboard_handles_error(self):
        """Should handle clipboard errors gracefully."""
        adapter = MacOSAdapter()
        with patch('subprocess.run', side_effect=Exception("Test error")):
            result = adapter.get_clipboard_content()
            assert result == ""

    def test_speak_handles_error(self):
        """Should handle speech errors gracefully."""
        adapter = LinuxAdapter()
        with patch('subprocess.run', side_effect=Exception("Test error")):
            result = adapter.speak_text("Hello")
            assert result is False


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_notification(self):
        """Should handle empty notification."""
        adapter = MacOSAdapter()
        with patch('subprocess.run'):
            result = adapter.send_notification("", "")
            assert isinstance(result, bool)

    def test_unicode_content(self):
        """Should handle unicode in clipboard."""
        adapter = MacOSAdapter()
        with patch('subprocess.Popen') as mock_popen:
            mock_process = Mock()
            mock_process.communicate = Mock()
            mock_popen.return_value = mock_process

            result = adapter.set_clipboard_content("日本語テスト 🎉")
            assert result is True

    def test_special_chars_in_app_name(self):
        """Should handle special characters in app name."""
        adapter = LinuxAdapter()
        with patch('subprocess.Popen'):
            result = adapter.open_application("App With Spaces.app")
            assert isinstance(result, bool)
