"""
Tests for ReasoningEngine - TDD Phase 1

Tests cover:
- Thinking levels (off, minimal, low, medium, high, xhigh)
- Reasoning modes (on, off, stream)
- Verbose modes (on, off, full)
- Thought generation based on level
- Response formatting based on mode
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestReasoningEngineInit:
    """Test ReasoningEngine initialization."""

    def test_default_thinking_level_is_low(self):
        """Default thinking level should be 'low'."""
        from core.reasoning.engine import ReasoningEngine

        engine = ReasoningEngine()
        assert engine.thinking_level == "low"

    def test_default_reasoning_mode_is_off(self):
        """Default reasoning mode should be 'off'."""
        from core.reasoning.engine import ReasoningEngine

        engine = ReasoningEngine()
        assert engine.reasoning_mode == "off"

    def test_default_verbose_mode_is_off(self):
        """Default verbose mode should be 'off'."""
        from core.reasoning.engine import ReasoningEngine

        engine = ReasoningEngine()
        assert engine.verbose_mode == "off"

    def test_init_with_custom_defaults(self):
        """Can initialize with custom defaults."""
        from core.reasoning.engine import ReasoningEngine

        engine = ReasoningEngine(
            thinking_level="high",
            reasoning_mode="on",
            verbose_mode="full"
        )
        assert engine.thinking_level == "high"
        assert engine.reasoning_mode == "on"
        assert engine.verbose_mode == "full"


class TestThinkingLevels:
    """Test thinking level settings and validation."""

    @pytest.fixture
    def engine(self):
        from core.reasoning.engine import ReasoningEngine
        return ReasoningEngine()

    @pytest.mark.parametrize("level", ["off", "minimal", "low", "medium", "high", "xhigh"])
    def test_valid_thinking_levels(self, engine, level):
        """All valid thinking levels should be accepted."""
        engine.set_thinking_level(level)
        assert engine.thinking_level == level

    def test_invalid_thinking_level_raises(self, engine):
        """Invalid thinking level should raise ValueError."""
        with pytest.raises(ValueError, match="Invalid thinking level"):
            engine.set_thinking_level("super_duper_high")

    def test_thinking_level_case_insensitive(self, engine):
        """Thinking levels should be case insensitive."""
        engine.set_thinking_level("HIGH")
        assert engine.thinking_level == "high"

        engine.set_thinking_level("Medium")
        assert engine.thinking_level == "medium"


class TestReasoningModes:
    """Test reasoning mode settings and validation."""

    @pytest.fixture
    def engine(self):
        from core.reasoning.engine import ReasoningEngine
        return ReasoningEngine()

    @pytest.mark.parametrize("mode", ["on", "off", "stream"])
    def test_valid_reasoning_modes(self, engine, mode):
        """All valid reasoning modes should be accepted."""
        engine.set_reasoning_mode(mode)
        assert engine.reasoning_mode == mode

    def test_invalid_reasoning_mode_raises(self, engine):
        """Invalid reasoning mode should raise ValueError."""
        with pytest.raises(ValueError, match="Invalid reasoning mode"):
            engine.set_reasoning_mode("maybe")

    def test_reasoning_mode_case_insensitive(self, engine):
        """Reasoning modes should be case insensitive."""
        engine.set_reasoning_mode("ON")
        assert engine.reasoning_mode == "on"

        engine.set_reasoning_mode("Stream")
        assert engine.reasoning_mode == "stream"


class TestVerboseModes:
    """Test verbose mode settings and validation."""

    @pytest.fixture
    def engine(self):
        from core.reasoning.engine import ReasoningEngine
        return ReasoningEngine()

    @pytest.mark.parametrize("mode", ["on", "off", "full"])
    def test_valid_verbose_modes(self, engine, mode):
        """All valid verbose modes should be accepted."""
        engine.set_verbose_mode(mode)
        assert engine.verbose_mode == mode

    def test_invalid_verbose_mode_raises(self, engine):
        """Invalid verbose mode should raise ValueError."""
        with pytest.raises(ValueError, match="Invalid verbose mode"):
            engine.set_verbose_mode("partial")

    def test_verbose_mode_case_insensitive(self, engine):
        """Verbose modes should be case insensitive."""
        engine.set_verbose_mode("FULL")
        assert engine.verbose_mode == "full"


class TestThinkGeneration:
    """Test thought generation based on thinking level."""

    @pytest.fixture
    def engine(self):
        from core.reasoning.engine import ReasoningEngine
        return ReasoningEngine()

    def test_think_off_returns_empty(self, engine):
        """Thinking level 'off' should return empty string."""
        engine.set_thinking_level("off")
        result = engine.think("Should I buy this token?")
        assert result == ""

    def test_think_minimal_returns_one_liner(self, engine):
        """Thinking level 'minimal' should return brief one-liner."""
        engine.set_thinking_level("minimal")
        result = engine.think("Should I buy this token?")
        # Should be short - under 100 chars
        assert len(result) < 100
        assert result != ""

    def test_think_low_returns_short_analysis(self, engine):
        """Thinking level 'low' should return 2-3 sentence analysis."""
        engine.set_thinking_level("low")
        result = engine.think("Should I buy this token?")
        # Should be moderate - 100-500 chars
        assert 50 < len(result) < 500

    def test_think_medium_returns_paragraph(self, engine):
        """Thinking level 'medium' should return paragraph analysis."""
        engine.set_thinking_level("medium")
        result = engine.think("Should I buy this token?")
        # Should be longer - 200-1000 chars
        assert 100 < len(result) < 1000

    def test_think_high_returns_detailed(self, engine):
        """Thinking level 'high' should return detailed analysis."""
        engine.set_thinking_level("high")
        result = engine.think("Should I buy this token?")
        # Should be substantial - 300+ chars
        assert len(result) > 200

    def test_think_xhigh_returns_exhaustive(self, engine):
        """Thinking level 'xhigh' should return exhaustive breakdown."""
        engine.set_thinking_level("xhigh")
        result = engine.think("Should I buy this token?")
        # Should be comprehensive - 500+ chars
        assert len(result) > 400


class TestReasoningFormatting:
    """Test reasoning output formatting based on mode."""

    @pytest.fixture
    def engine(self):
        from core.reasoning.engine import ReasoningEngine
        return ReasoningEngine()

    def test_format_reasoning_off_returns_empty(self, engine):
        """Reasoning mode 'off' should hide reasoning from user."""
        engine.set_reasoning_mode("off")
        reasoning = "This is my analysis..."
        result = engine.format_reasoning(reasoning)
        assert result == ""

    def test_format_reasoning_on_returns_block(self, engine):
        """Reasoning mode 'on' should show reasoning in formatted block."""
        engine.set_reasoning_mode("on")
        reasoning = "This is my analysis..."
        result = engine.format_reasoning(reasoning)
        assert "Thinking" in result or "Reasoning" in result
        assert "analysis" in result

    def test_format_reasoning_stream_returns_streamable(self, engine):
        """Reasoning mode 'stream' should return streamable format."""
        engine.set_reasoning_mode("stream")
        reasoning = "This is my analysis..."
        result = engine.format_reasoning(reasoning)
        # Should have streaming-friendly format
        assert result != ""
        assert "analysis" in result


class TestVerboseOutput:
    """Test verbose output control."""

    @pytest.fixture
    def engine(self):
        from core.reasoning.engine import ReasoningEngine
        return ReasoningEngine()

    def test_verbose_off_minimal_output(self, engine):
        """Verbose 'off' should produce minimal output."""
        engine.set_verbose_mode("off")
        # With verbose off, intermediate steps should be hidden
        assert engine.should_show_intermediate_steps() is False

    def test_verbose_on_shows_steps(self, engine):
        """Verbose 'on' should show intermediate steps."""
        engine.set_verbose_mode("on")
        assert engine.should_show_intermediate_steps() is True

    def test_verbose_full_shows_debug(self, engine):
        """Verbose 'full' should show debug level output."""
        engine.set_verbose_mode("full")
        assert engine.should_show_intermediate_steps() is True
        assert engine.should_show_debug_info() is True


class TestStatusReport:
    """Test status reporting functionality."""

    @pytest.fixture
    def engine(self):
        from core.reasoning.engine import ReasoningEngine
        return ReasoningEngine()

    def test_get_status_returns_dict(self, engine):
        """get_status should return current settings as dict."""
        status = engine.get_status()
        assert isinstance(status, dict)
        assert "thinking_level" in status
        assert "reasoning_mode" in status
        assert "verbose_mode" in status

    def test_get_status_reflects_changes(self, engine):
        """get_status should reflect setting changes."""
        engine.set_thinking_level("high")
        engine.set_reasoning_mode("stream")
        engine.set_verbose_mode("full")

        status = engine.get_status()
        assert status["thinking_level"] == "high"
        assert status["reasoning_mode"] == "stream"
        assert status["verbose_mode"] == "full"

    def test_format_status_for_display(self, engine):
        """format_status should return human-readable string."""
        engine.set_thinking_level("medium")
        status_str = engine.format_status()

        assert "Thinking:" in status_str or "thinking:" in status_str
        assert "medium" in status_str.lower()


class TestProcessWithReasoning:
    """Test the main process_with_reasoning method."""

    @pytest.fixture
    def engine(self):
        from core.reasoning.engine import ReasoningEngine
        return ReasoningEngine()

    @pytest.mark.asyncio
    async def test_process_returns_response_and_reasoning(self, engine):
        """process_with_reasoning should return both response and reasoning."""
        engine.set_thinking_level("medium")
        engine.set_reasoning_mode("on")

        result = await engine.process_with_reasoning(
            prompt="What's the market sentiment?",
            context={"market": "crypto"}
        )

        assert "response" in result
        assert "reasoning" in result

    @pytest.mark.asyncio
    async def test_process_with_reasoning_off_skips_thinking(self, engine):
        """With thinking off, should skip the thinking phase."""
        engine.set_thinking_level("off")

        result = await engine.process_with_reasoning(
            prompt="Quick question",
            context={}
        )

        # Reasoning should be empty when thinking is off
        assert result.get("reasoning", "") == ""


class TestThinkingLevelDescriptions:
    """Test thinking level descriptions for user info."""

    @pytest.fixture
    def engine(self):
        from core.reasoning.engine import ReasoningEngine
        return ReasoningEngine()

    def test_get_level_description(self, engine):
        """Should return description for each level."""
        descriptions = engine.get_level_descriptions()

        assert "off" in descriptions
        assert "minimal" in descriptions
        assert "low" in descriptions
        assert "medium" in descriptions
        assert "high" in descriptions
        assert "xhigh" in descriptions

        # Each should have a description
        for level, desc in descriptions.items():
            assert isinstance(desc, str)
            assert len(desc) > 0
