"""
Tests for signal handling module.

Verifies:
- Signal handler registration
- SIGTERM/SIGINT handling
- SIGHUP config reload
- Cross-platform compatibility
"""

import asyncio
import signal
import sys
import pytest
from unittest.mock import AsyncMock, Mock, patch, MagicMock


class TestSignalHandler:
    """Test SignalHandler class functionality."""

    def test_import_signal_handler(self):
        """Test that SignalHandler can be imported."""
        from core.lifecycle.signals import SignalHandler
        assert SignalHandler is not None

    def test_signal_handler_init(self):
        """Test SignalHandler initialization."""
        from core.lifecycle.signals import SignalHandler

        handler = SignalHandler()
        assert handler is not None
        assert not handler.is_registered()

    def test_register_sigterm_handler(self):
        """Test SIGTERM handler registration."""
        from core.lifecycle.signals import SignalHandler

        handler = SignalHandler()
        callback = AsyncMock()

        handler.on_sigterm(callback)

        assert handler._sigterm_callback is not None

    def test_register_sigint_handler(self):
        """Test SIGINT handler registration."""
        from core.lifecycle.signals import SignalHandler

        handler = SignalHandler()
        callback = AsyncMock()

        handler.on_sigint(callback)

        assert handler._sigint_callback is not None

    def test_register_sighup_handler(self):
        """Test SIGHUP handler registration for config reload."""
        from core.lifecycle.signals import SignalHandler

        handler = SignalHandler()
        callback = AsyncMock()

        handler.on_sighup(callback)

        assert handler._sighup_callback is not None

    @pytest.mark.asyncio
    async def test_handle_sigterm(self):
        """Test that SIGTERM triggers the registered callback."""
        from core.lifecycle.signals import SignalHandler

        handler = SignalHandler()
        callback = AsyncMock()

        handler.on_sigterm(callback)
        await handler.handle_sigterm()

        callback.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_sigint(self):
        """Test that SIGINT triggers the registered callback."""
        from core.lifecycle.signals import SignalHandler

        handler = SignalHandler()
        callback = AsyncMock()

        handler.on_sigint(callback)
        await handler.handle_sigint()

        callback.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_sighup_config_reload(self):
        """Test that SIGHUP triggers config reload callback."""
        from core.lifecycle.signals import SignalHandler

        handler = SignalHandler()
        reload_callback = AsyncMock()

        handler.on_sighup(reload_callback)
        await handler.handle_sighup()

        reload_callback.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_callback_registered(self):
        """Test that handling signals with no callback is safe."""
        from core.lifecycle.signals import SignalHandler

        handler = SignalHandler()

        # Should not raise
        await handler.handle_sigterm()
        await handler.handle_sigint()
        await handler.handle_sighup()

    def test_register_all_handlers(self):
        """Test registering signal handlers with the OS."""
        from core.lifecycle.signals import SignalHandler

        handler = SignalHandler()

        # Mock the signal module
        with patch('core.lifecycle.signals.signal') as mock_signal:
            handler.register()

            # Should be registered now
            assert handler.is_registered()

    def test_unregister_handlers(self):
        """Test unregistering signal handlers."""
        from core.lifecycle.signals import SignalHandler

        handler = SignalHandler()

        with patch('core.lifecycle.signals.signal') as mock_signal:
            handler.register()
            handler.unregister()

            assert not handler.is_registered()

    def test_get_signal_handler_singleton(self):
        """Test global signal handler singleton."""
        from core.lifecycle.signals import get_signal_handler

        handler1 = get_signal_handler()
        handler2 = get_signal_handler()

        assert handler1 is handler2


class TestSignalHandlerIntegration:
    """Integration tests for signal handling."""

    @pytest.mark.asyncio
    async def test_signal_chain(self):
        """Test that signals can trigger shutdown chain."""
        from core.lifecycle.signals import SignalHandler

        handler = SignalHandler()
        shutdown_initiated = False

        async def shutdown():
            nonlocal shutdown_initiated
            shutdown_initiated = True

        handler.on_sigterm(shutdown)
        await handler.handle_sigterm()

        assert shutdown_initiated

    @pytest.mark.asyncio
    async def test_sighup_reloads_config(self):
        """Test SIGHUP triggers configuration reload."""
        from core.lifecycle.signals import SignalHandler

        handler = SignalHandler()
        config_reloaded = False

        async def reload_config():
            nonlocal config_reloaded
            config_reloaded = True

        handler.on_sighup(reload_config)
        await handler.handle_sighup()

        assert config_reloaded

    @pytest.mark.asyncio
    async def test_multiple_signals_in_sequence(self):
        """Test handling multiple signals in sequence."""
        from core.lifecycle.signals import SignalHandler

        handler = SignalHandler()
        events = []

        async def on_hup():
            events.append("hup")

        async def on_term():
            events.append("term")

        handler.on_sighup(on_hup)
        handler.on_sigterm(on_term)

        # First reload config
        await handler.handle_sighup()
        # Then terminate
        await handler.handle_sigterm()

        assert events == ["hup", "term"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
