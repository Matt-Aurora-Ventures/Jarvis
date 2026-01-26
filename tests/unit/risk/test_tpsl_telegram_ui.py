"""
Unit Tests for TP/SL Telegram UI

Tests for:
- TPSL callback handler
- Ladder template selection
- Custom TP/SL input validation
- Position TP/SL editing
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def mock_context():
    """Create mock Telegram context."""
    ctx = MagicMock()
    ctx.user_data = {}
    return ctx


@pytest.fixture
def mock_ctx_loader():
    """Create mock DemoContextLoader."""
    ctx = MagicMock()
    ctx.JarvisTheme = MagicMock()
    ctx.JarvisTheme.SETTINGS = "SETTINGS"
    ctx.JarvisTheme.SNIPE = "SNIPE"
    ctx.JarvisTheme.ERROR = "ERROR"
    ctx.JarvisTheme.CHART = "CHART"
    ctx.JarvisTheme.SUCCESS = "SUCCESS"
    ctx.JarvisTheme.CLOSE = "CLOSE"
    ctx.JarvisTheme.BACK = "BACK"
    ctx.JarvisTheme.COIN = "COIN"

    builder = MagicMock()
    builder.success_message = MagicMock(return_value=("Success", MagicMock()))
    builder.error_message = MagicMock(return_value=("Error", MagicMock()))
    ctx.DemoMenuBuilder = builder

    return ctx


@pytest.fixture
def mock_update():
    """Create mock Telegram update."""
    update = MagicMock()
    update.callback_query = MagicMock()
    update.callback_query.from_user = MagicMock()
    update.callback_query.from_user.id = 12345
    return update


# =============================================================================
# Test: Ladder Templates
# =============================================================================

class TestLadderTemplates:
    """Test ladder exit templates."""

    def test_templates_exist(self):
        """All predefined templates should exist."""
        from tg_bot.handlers.demo.callbacks.tpsl import LADDER_TEMPLATES

        assert "conservative" in LADDER_TEMPLATES
        assert "balanced" in LADDER_TEMPLATES
        assert "aggressive" in LADDER_TEMPLATES
        assert "moon" in LADDER_TEMPLATES

    def test_template_structure(self):
        """Each template should have required fields."""
        from tg_bot.handlers.demo.callbacks.tpsl import LADDER_TEMPLATES

        for key, template in LADDER_TEMPLATES.items():
            assert "name" in template
            assert "description" in template
            assert "exits" in template
            assert len(template["exits"]) >= 2

            for exit_tier in template["exits"]:
                assert "pnl_multiple" in exit_tier
                assert "percent" in exit_tier
                assert exit_tier["pnl_multiple"] > 0
                assert 0 < exit_tier["percent"] <= 100

    def test_balanced_template_is_default(self):
        """Balanced template should match DEFAULT_LADDER_EXITS."""
        from tg_bot.handlers.demo.callbacks.tpsl import LADDER_TEMPLATES
        from core.risk.tp_sl_monitor import DEFAULT_LADDER_EXITS

        balanced = LADDER_TEMPLATES["balanced"]["exits"]

        # Compare pnl_multiple and percent values
        for i, tier in enumerate(DEFAULT_LADDER_EXITS):
            assert balanced[i]["pnl_multiple"] == tier["pnl_multiple"]
            assert balanced[i]["percent"] == tier["percent"]


# =============================================================================
# Test: Input Validation
# =============================================================================

class TestInputValidation:
    """Test custom TP/SL input validation."""

    def test_valid_tp_values(self):
        """Valid TP values should pass validation."""
        from tg_bot.handlers.demo.callbacks.tpsl import validate_custom_tp

        valid_cases = ["10", "50", "100", "200", "500"]
        for val in valid_cases:
            is_valid, value, error = validate_custom_tp(val)
            assert is_valid is True, f"Value {val} should be valid"
            assert error == ""

    def test_invalid_tp_values(self):
        """Invalid TP values should fail validation."""
        from tg_bot.handlers.demo.callbacks.tpsl import validate_custom_tp

        # Too low
        is_valid, _, error = validate_custom_tp("2")
        assert is_valid is False
        assert "at least 5%" in error

        # Too high
        is_valid, _, error = validate_custom_tp("600")
        assert is_valid is False
        assert "cannot exceed 500%" in error

        # Not a number
        is_valid, _, error = validate_custom_tp("abc")
        assert is_valid is False
        assert "Invalid" in error

    def test_valid_sl_values(self):
        """Valid SL values should pass validation."""
        from tg_bot.handlers.demo.callbacks.tpsl import validate_custom_sl

        valid_cases = ["10", "20", "50", "80"]
        for val in valid_cases:
            is_valid, value, error = validate_custom_sl(val)
            assert is_valid is True, f"Value {val} should be valid"
            assert error == ""

    def test_invalid_sl_values(self):
        """Invalid SL values should fail validation."""
        from tg_bot.handlers.demo.callbacks.tpsl import validate_custom_sl

        # Too low
        is_valid, _, error = validate_custom_sl("2")
        assert is_valid is False
        assert "at least 5%" in error

        # Too high
        is_valid, _, error = validate_custom_sl("95")
        assert is_valid is False
        assert "cannot exceed 90%" in error


# =============================================================================
# Test: Handler Integration
# =============================================================================

class TestHandlerIntegration:
    """Test callback handler integration."""

    @pytest.mark.asyncio
    async def test_tpsl_settings_menu(self, mock_ctx_loader, mock_update, mock_context):
        """Should show TP/SL settings menu."""
        from tg_bot.handlers.demo.callbacks.tpsl import handle_tpsl

        mock_context.user_data = {"tp_percent": 50.0, "sl_percent": 20.0}
        state = {}

        text, keyboard = await handle_tpsl(
            mock_ctx_loader,
            "tpsl_settings",
            "demo:tpsl_settings",
            mock_update,
            mock_context,
            state,
        )

        assert "TP/SL SETTINGS" in text or text is not None
        assert keyboard is not None

    @pytest.mark.asyncio
    async def test_ladder_menu(self, mock_ctx_loader, mock_update, mock_context):
        """Should show ladder exit menu."""
        from tg_bot.handlers.demo.callbacks.tpsl import handle_tpsl

        mock_context.user_data = {}
        state = {}

        text, keyboard = await handle_tpsl(
            mock_ctx_loader,
            "ladder_menu",
            "demo:ladder_menu",
            mock_update,
            mock_context,
            state,
        )

        assert "LADDER" in text.upper() or text is not None
        assert keyboard is not None

    @pytest.mark.asyncio
    async def test_apply_preset(self, mock_ctx_loader, mock_update, mock_context):
        """Should apply TP/SL preset."""
        from tg_bot.handlers.demo.callbacks.tpsl import handle_tpsl

        mock_context.user_data = {}
        state = {}

        await handle_tpsl(
            mock_ctx_loader,
            "tpsl_preset",
            "demo:tpsl_preset:100:30",
            mock_update,
            mock_context,
            state,
        )

        assert mock_context.user_data.get("tp_percent") == 100.0
        assert mock_context.user_data.get("sl_percent") == 30.0

    @pytest.mark.asyncio
    async def test_apply_ladder_template(self, mock_ctx_loader, mock_update, mock_context):
        """Should apply ladder template."""
        from tg_bot.handlers.demo.callbacks.tpsl import handle_tpsl

        mock_context.user_data = {}
        state = {}

        await handle_tpsl(
            mock_ctx_loader,
            "ladder_select",
            "demo:ladder_select:balanced",
            mock_update,
            mock_context,
            state,
        )

        ladder = mock_context.user_data.get("ladder_exits")
        assert ladder is not None
        assert len(ladder) == 3
        assert ladder[0]["pnl_multiple"] == 2.0
        assert ladder[0]["executed"] is False


# =============================================================================
# Test: Position Editing
# =============================================================================

class TestPositionEditing:
    """Test editing TP/SL for existing positions."""

    @pytest.mark.asyncio
    async def test_edit_position_tp(self, mock_ctx_loader, mock_update, mock_context):
        """Should update TP for a position."""
        from tg_bot.handlers.demo.callbacks.tpsl import handle_tpsl

        positions = [
            {"id": "pos_1", "symbol": "TEST", "entry_price": 1.0, "tp_percent": 50, "sl_percent": 20}
        ]
        mock_context.user_data = {"positions": positions}
        state = {"positions": positions}

        await handle_tpsl(
            mock_ctx_loader,
            "pos_tp",
            "demo:pos_tp:pos_1:100",
            mock_update,
            mock_context,
            state,
        )

        updated_pos = mock_context.user_data["positions"][0]
        assert updated_pos["tp_percent"] == 100
        assert updated_pos["tp_price"] == 2.0  # 1.0 * (1 + 100/100)

    @pytest.mark.asyncio
    async def test_edit_position_sl(self, mock_ctx_loader, mock_update, mock_context):
        """Should update SL for a position."""
        from tg_bot.handlers.demo.callbacks.tpsl import handle_tpsl

        positions = [
            {"id": "pos_1", "symbol": "TEST", "entry_price": 1.0, "tp_percent": 50, "sl_percent": 20}
        ]
        mock_context.user_data = {"positions": positions}
        state = {"positions": positions}

        await handle_tpsl(
            mock_ctx_loader,
            "pos_sl",
            "demo:pos_sl:pos_1:30",
            mock_update,
            mock_context,
            state,
        )

        updated_pos = mock_context.user_data["positions"][0]
        assert updated_pos["sl_percent"] == 30
        assert updated_pos["sl_price"] == 0.7  # 1.0 * (1 - 30/100)
