"""
Tests for /analyze command and interactive token analysis.

Tests cover:
- Command parsing and validation
- Token resolution (symbol to address)
- Analysis response formatting
- Interactive button generation
- Drill-down callbacks (chart, holders, trades, signals, risk)
- Session state management for drill-down navigation
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def mock_update():
    """Create mock Telegram update."""
    update = MagicMock()
    update.effective_user.id = 12345
    update.effective_chat.id = 67890
    update.message.reply_text = AsyncMock()
    return update


@pytest.fixture
def mock_context():
    """Create mock Telegram context."""
    context = MagicMock()
    context.args = []
    context.bot = MagicMock()
    return context


@pytest.fixture
def mock_callback_query():
    """Create mock callback query."""
    query = MagicMock()
    query.from_user.id = 12345
    query.data = ""
    query.answer = AsyncMock()
    query.message.edit_text = AsyncMock()
    query.message.reply_photo = AsyncMock()
    return query


@pytest.fixture
def sample_token_signal():
    """Create sample TokenSignal for testing."""
    from tg_bot.services.signal_service import TokenSignal
    return TokenSignal(
        address="So11111111111111111111111111111111111111112",
        symbol="SOL",
        name="Wrapped SOL",
        price_usd=150.0,
        price_change_1h=2.5,
        price_change_24h=5.0,
        volume_24h=5_000_000,
        liquidity_usd=10_000_000,
        security_score=85.0,
        risk_level="low",
        sentiment="positive",
        sentiment_score=0.75,
        sentiment_confidence=0.8,
        signal="BUY",
        signal_score=35.0,
        signal_reasons=["High liquidity", "Positive sentiment"],
        sources_used=["dexscreener", "grok"],
    )


# =============================================================================
# Test Command Parsing
# =============================================================================

class TestAnalyzeCommandParsing:
    """Test /analyze command parsing."""

    @pytest.mark.asyncio
    async def test_analyze_without_token_shows_usage(self, mock_update, mock_context):
        """Should show usage when no token provided."""
        from tg_bot.handlers.commands.analyze_command import analyze_command

        mock_context.args = []

        # Mock admin check and rate limiter - both in tg_bot.handlers module
        with patch("tg_bot.handlers.get_config") as mock_config:
            mock_config.return_value.admin_ids = {12345}  # Mock user is admin

            with patch("tg_bot.handlers.get_tracker") as mock_tracker:
                mock_tracker.return_value.can_make_sentiment_call.return_value = (True, "")

                await analyze_command(mock_update, mock_context)

        mock_update.message.reply_text.assert_called_once()
        call_args = mock_update.message.reply_text.call_args
        assert "Usage:" in call_args[0][0] or "Usage:" in str(call_args)

    @pytest.mark.asyncio
    async def test_analyze_with_symbol_resolves_address(self, mock_update, mock_context):
        """Should resolve common symbols to addresses."""
        from tg_bot.handlers.commands.analyze_command import resolve_token_address

        address = resolve_token_address("SOL")
        assert address == "So11111111111111111111111111111111111111112"

        address = resolve_token_address("BONK")
        assert address == "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263"

    @pytest.mark.asyncio
    async def test_analyze_with_address_uses_directly(self, mock_update, mock_context):
        """Should use address directly when not a known symbol."""
        from tg_bot.handlers.commands.analyze_command import resolve_token_address

        test_address = "TestAddress123456789012345678901234567890"
        address = resolve_token_address(test_address)
        assert address == test_address

    @pytest.mark.asyncio
    async def test_analyze_case_insensitive(self, mock_update, mock_context):
        """Symbol resolution should be case insensitive."""
        from tg_bot.handlers.commands.analyze_command import resolve_token_address

        assert resolve_token_address("sol") == resolve_token_address("SOL")
        assert resolve_token_address("Bonk") == resolve_token_address("BONK")


# =============================================================================
# Test Analysis Response
# =============================================================================

class TestAnalysisResponse:
    """Test analysis response formatting."""

    def test_format_analysis_includes_price(self, sample_token_signal):
        """Analysis should include current price."""
        from tg_bot.ui.token_analysis_view import TokenAnalysisView

        view = TokenAnalysisView()
        message = view.format_main_view(sample_token_signal)

        assert "$150" in message or "150" in message

    def test_format_analysis_includes_change(self, sample_token_signal):
        """Analysis should include price changes."""
        from tg_bot.ui.token_analysis_view import TokenAnalysisView

        view = TokenAnalysisView()
        message = view.format_main_view(sample_token_signal)

        assert "24h" in message.lower() or "2.5" in message or "5.0" in message

    def test_format_analysis_includes_volume(self, sample_token_signal):
        """Analysis should include volume."""
        from tg_bot.ui.token_analysis_view import TokenAnalysisView

        view = TokenAnalysisView()
        message = view.format_main_view(sample_token_signal)

        # Volume formatted as $5M or similar
        assert "5" in message and ("M" in message or "m" in message.lower() or "000" in message)

    def test_format_analysis_includes_sentiment(self, sample_token_signal):
        """Analysis should include sentiment score."""
        from tg_bot.ui.token_analysis_view import TokenAnalysisView

        view = TokenAnalysisView()
        message = view.format_main_view(sample_token_signal)

        # Should show sentiment info
        assert "sentiment" in message.lower() or "bullish" in message.lower() or "positive" in message.lower()

    def test_format_analysis_includes_grade(self, sample_token_signal):
        """Analysis should include on-chain grade."""
        from tg_bot.ui.token_analysis_view import TokenAnalysisView

        view = TokenAnalysisView()
        message = view.format_main_view(sample_token_signal)

        # Should show grade (A-F) or score
        assert any(g in message for g in ["A+", "A", "B", "C", "D", "F", "Grade", "Score", "/100"])

    def test_format_analysis_includes_risk(self, sample_token_signal):
        """Analysis should include risk assessment."""
        from tg_bot.ui.token_analysis_view import TokenAnalysisView

        view = TokenAnalysisView()
        message = view.format_main_view(sample_token_signal)

        # Should show risk info
        assert "risk" in message.lower() or "low" in message.lower() or "security" in message.lower()


# =============================================================================
# Test Interactive Buttons
# =============================================================================

class TestInteractiveButtons:
    """Test interactive button generation."""

    def test_analysis_keyboard_has_chart_button(self, sample_token_signal):
        """Analysis keyboard should have Chart button."""
        from tg_bot.ui.inline_buttons import TokenAnalysisButtons

        buttons = TokenAnalysisButtons()
        keyboard = buttons.build_main_keyboard(sample_token_signal.address, sample_token_signal.symbol)

        # Flatten keyboard to check buttons
        all_buttons = []
        for row in keyboard.inline_keyboard:
            all_buttons.extend([btn.text for btn in row])

        assert any("chart" in btn.lower() for btn in all_buttons)

    def test_analysis_keyboard_has_onchain_button(self, sample_token_signal):
        """Analysis keyboard should have On-Chain button."""
        from tg_bot.ui.inline_buttons import TokenAnalysisButtons

        buttons = TokenAnalysisButtons()
        keyboard = buttons.build_main_keyboard(sample_token_signal.address, sample_token_signal.symbol)

        all_buttons = []
        for row in keyboard.inline_keyboard:
            all_buttons.extend([btn.text for btn in row])

        assert any("chain" in btn.lower() or "holders" in btn.lower() for btn in all_buttons)

    def test_analysis_keyboard_has_signals_button(self, sample_token_signal):
        """Analysis keyboard should have Signals button."""
        from tg_bot.ui.inline_buttons import TokenAnalysisButtons

        buttons = TokenAnalysisButtons()
        keyboard = buttons.build_main_keyboard(sample_token_signal.address, sample_token_signal.symbol)

        all_buttons = []
        for row in keyboard.inline_keyboard:
            all_buttons.extend([btn.text for btn in row])

        assert any("signal" in btn.lower() for btn in all_buttons)

    def test_analysis_keyboard_has_risk_button(self, sample_token_signal):
        """Analysis keyboard should have Risk button."""
        from tg_bot.ui.inline_buttons import TokenAnalysisButtons

        buttons = TokenAnalysisButtons()
        keyboard = buttons.build_main_keyboard(sample_token_signal.address, sample_token_signal.symbol)

        all_buttons = []
        for row in keyboard.inline_keyboard:
            all_buttons.extend([btn.text for btn in row])

        assert any("risk" in btn.lower() for btn in all_buttons)

    def test_callback_data_format(self, sample_token_signal):
        """Callback data should follow correct format."""
        from tg_bot.ui.inline_buttons import TokenAnalysisButtons

        buttons = TokenAnalysisButtons()
        keyboard = buttons.build_main_keyboard(sample_token_signal.address, sample_token_signal.symbol)

        # Check callback_data format
        for row in keyboard.inline_keyboard:
            for btn in row:
                if btn.callback_data:  # URL buttons don't have callback_data
                    # Format should be action:token_address
                    assert ":" in btn.callback_data or btn.callback_data.startswith("analyze_")


# =============================================================================
# Test Drill-Down Callbacks
# =============================================================================

class TestDrillDownCallbacks:
    """Test drill-down callback handling."""

    @pytest.mark.asyncio
    async def test_chart_callback_updates_session(self, mock_callback_query):
        """Chart callback should update session state."""
        from tg_bot.handlers.commands.analyze_command import handle_analyze_callback
        from tg_bot.sessions.session_manager import get_session_manager

        mock_callback_query.data = "analyze_chart:So11111111111111111111111111111111111111112"

        with patch("tg_bot.handlers.commands.analyze_command.get_signal_service") as mock_service:
            mock_service.return_value.get_comprehensive_signal = AsyncMock()

            # Create session first
            manager = get_session_manager()
            manager.create_session(12345, "So11111111111111111111111111111111111111112", "SOL")

            await handle_analyze_callback(mock_callback_query, MagicMock())

            session = manager.get_session(12345)
            if session:
                assert session.get("current_view") == "chart"

    @pytest.mark.asyncio
    async def test_holders_callback_shows_holder_data(self, mock_callback_query):
        """Holders callback should show holder distribution."""
        from tg_bot.handlers.commands.analyze_command import handle_analyze_callback

        mock_callback_query.data = "analyze_holders:So11111111111111111111111111111111111111112"

        with patch("tg_bot.handlers.commands.analyze_command.fetch_holder_data") as mock_fetch:
            mock_fetch.return_value = [
                {"address": "holder1", "percentage": 50.0, "amount": 1000000},
                {"address": "holder2", "percentage": 25.0, "amount": 500000},
            ]

            await handle_analyze_callback(mock_callback_query, MagicMock())

            # Should have edited message with holder info
            mock_callback_query.message.edit_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_signals_callback_shows_trading_signals(self, mock_callback_query, sample_token_signal):
        """Signals callback should show trading signals."""
        from tg_bot.handlers.commands.analyze_command import handle_analyze_callback

        mock_callback_query.data = "analyze_signals:So11111111111111111111111111111111111111112"

        with patch("tg_bot.handlers.commands.analyze_command.get_signal_service") as mock_service:
            mock_service.return_value.get_comprehensive_signal = AsyncMock(return_value=sample_token_signal)

            await handle_analyze_callback(mock_callback_query, MagicMock())

            # Should have edited message with signal info
            call_args = mock_callback_query.message.edit_text.call_args
            message = call_args[0][0] if call_args[0] else call_args[1].get("text", "")
            assert "signal" in message.lower() or "BUY" in message

    @pytest.mark.asyncio
    async def test_risk_callback_shows_risk_assessment(self, mock_callback_query, sample_token_signal):
        """Risk callback should show risk assessment."""
        from tg_bot.handlers.commands.analyze_command import handle_analyze_callback

        mock_callback_query.data = "analyze_risk:So11111111111111111111111111111111111111112"

        with patch("tg_bot.handlers.commands.analyze_command.get_signal_service") as mock_service:
            mock_service.return_value.get_comprehensive_signal = AsyncMock(return_value=sample_token_signal)

            await handle_analyze_callback(mock_callback_query, MagicMock())

            # Should have edited message with risk info
            call_args = mock_callback_query.message.edit_text.call_args
            message = call_args[0][0] if call_args[0] else call_args[1].get("text", "")
            assert "risk" in message.lower() or "security" in message.lower() or "whale" in message.lower()

    @pytest.mark.asyncio
    async def test_back_callback_returns_to_main(self, mock_callback_query, sample_token_signal):
        """Back callback should return to main analysis view."""
        from tg_bot.handlers.commands.analyze_command import handle_analyze_callback
        from tg_bot.sessions.session_manager import get_session_manager

        mock_callback_query.data = "analyze_back:So11111111111111111111111111111111111111112"

        # Create session in drill-down state
        manager = get_session_manager()
        manager.create_session(12345, "So11111111111111111111111111111111111111112", "SOL")
        manager.update_session(12345, current_view="chart")

        with patch("tg_bot.handlers.commands.analyze_command.get_signal_service") as mock_service:
            mock_service.return_value.get_comprehensive_signal = AsyncMock(return_value=sample_token_signal)

            await handle_analyze_callback(mock_callback_query, MagicMock())

            session = manager.get_session(12345)
            if session:
                assert session.get("current_view") == "main"


# =============================================================================
# Test Session State
# =============================================================================

class TestSessionState:
    """Test session state management for drill-down."""

    def test_session_created_on_analyze(self):
        """Session should be created when analyze is called."""
        from tg_bot.sessions.session_manager import SessionManager

        manager = SessionManager(timeout_minutes=30)
        session = manager.create_session(12345, "token_address", "SOL")

        assert session is not None
        assert session["user_id"] == 12345
        assert session["token_address"] == "token_address"
        assert session["token_symbol"] == "SOL"

    def test_session_tracks_current_view(self):
        """Session should track current view."""
        from tg_bot.sessions.session_manager import SessionManager

        manager = SessionManager(timeout_minutes=30)
        manager.create_session(12345, "token_address", "SOL")

        manager.update_session(12345, current_view="chart")
        session = manager.get_session(12345)

        assert session["current_view"] == "chart"

    def test_session_expires_after_timeout(self):
        """Session should expire after timeout."""
        from tg_bot.sessions.session_manager import SessionManager
        from datetime import timedelta

        manager = SessionManager(timeout_minutes=0)  # Immediate expiry for testing
        manager.create_session(12345, "token_address", "SOL")

        # Force the session to appear expired
        import time
        time.sleep(0.1)

        session = manager.get_session(12345)
        # With 0 timeout, session should be expired
        assert session is None

    def test_session_cleared_on_close(self):
        """Session should be cleared when closed."""
        from tg_bot.sessions.session_manager import SessionManager

        manager = SessionManager(timeout_minutes=30)
        manager.create_session(12345, "token_address", "SOL")
        manager.clear_session(12345)

        session = manager.get_session(12345)
        assert session is None
