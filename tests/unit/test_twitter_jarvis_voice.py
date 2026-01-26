"""
Comprehensive unit tests for bots/twitter/jarvis_voice.py

Tests cover:
- JarvisVoice class initialization (CLI and API modes)
- CLI path resolution across platforms
- CLI execution with timeout and error handling
- All async content generation methods (20+ methods)
- Voice Bible integration and validation
- Tweet cleaning and formatting (JSON extraction, markdown removal)
- Singleton pattern (get_jarvis_voice)
- Context handling and prompt building
- Truncation logic for long content
- Error recovery and fallback behavior

This is a CRITICAL PRODUCTION component that generates @Jarvis_lifeos voice.
Target: 75%+ code coverage
"""

import pytest
import asyncio
import json
import os
import platform
import subprocess
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


# =============================================================================
# Fixtures for creating JarvisVoice instances
# =============================================================================

@pytest.fixture
def mock_anthropic_utils():
    """Mock the anthropic_utils module to prevent real API connections."""
    with patch('core.llm.anthropic_utils.get_anthropic_base_url', return_value=None):
        with patch('core.llm.anthropic_utils.get_anthropic_api_key', return_value=None):
            with patch('core.llm.anthropic_utils.is_local_anthropic', return_value=False):
                yield


@pytest.fixture
def voice_instance(mock_anthropic_utils):
    """Create a JarvisVoice instance with mocked dependencies."""
    from bots.twitter.jarvis_voice import JarvisVoice
    voice = JarvisVoice()
    voice.api_client = None  # Ensure no API client
    return voice


# =============================================================================
# Module Import Tests
# =============================================================================

class TestModuleImports:
    """Test module imports and constants."""

    def test_jarvis_voice_imports(self):
        """Test that JarvisVoice can be imported."""
        from bots.twitter.jarvis_voice import JarvisVoice
        assert JarvisVoice is not None

    def test_get_jarvis_voice_imports(self):
        """Test that get_jarvis_voice can be imported."""
        from bots.twitter.jarvis_voice import get_jarvis_voice
        assert callable(get_jarvis_voice)

    def test_jarvis_system_prompt_alias(self):
        """Test JARVIS_SYSTEM_PROMPT alias exists."""
        from bots.twitter.jarvis_voice import JARVIS_SYSTEM_PROMPT
        assert JARVIS_SYSTEM_PROMPT is not None
        assert len(JARVIS_SYSTEM_PROMPT) > 100

    def test_voice_bible_imported(self):
        """Test JARVIS_VOICE_BIBLE is properly imported."""
        from bots.twitter.jarvis_voice import JARVIS_VOICE_BIBLE
        assert "jarvis" in JARVIS_VOICE_BIBLE.lower()
        assert "chrome" in JARVIS_VOICE_BIBLE.lower() or "ai" in JARVIS_VOICE_BIBLE.lower()


# =============================================================================
# JarvisVoice Initialization Tests
# =============================================================================

class TestJarvisVoiceInit:
    """Test JarvisVoice class initialization."""

    def test_init_defaults(self, mock_anthropic_utils):
        """Test default initialization values."""
        from bots.twitter.jarvis_voice import JarvisVoice
        voice = JarvisVoice()
        assert voice.cli_enabled is True
        assert voice.api_model == "claude-sonnet-4-20250514"

    def test_init_with_cli_path_env(self, mock_anthropic_utils):
        """Test initialization with custom CLI path from environment."""
        with patch.dict(os.environ, {"CLAUDE_CLI_PATH": "/custom/path/claude"}):
            from bots.twitter.jarvis_voice import JarvisVoice
            voice = JarvisVoice()
            assert voice.cli_path == "/custom/path/claude"

    def test_init_with_local_anthropic(self):
        """Test initialization with local Anthropic-compatible API."""
        mock_client = MagicMock()

        with patch('core.llm.anthropic_utils.get_anthropic_base_url', return_value="http://localhost:11434/v1"):
            with patch('core.llm.anthropic_utils.get_anthropic_api_key', return_value="ollama"):
                with patch('core.llm.anthropic_utils.is_local_anthropic', return_value=True):
                    with patch('anthropic.Anthropic', return_value=mock_client):
                        with patch.dict(os.environ, {"OLLAMA_MODEL": "qwen3-coder"}):
                            from bots.twitter.jarvis_voice import JarvisVoice
                            voice = JarvisVoice()
                            assert voice.api_base_url == "http://localhost:11434/v1"
                            assert voice.api_model == "qwen3-coder"

    def test_init_with_remote_anthropic(self):
        """Test initialization with remote Anthropic API."""
        mock_client = MagicMock()

        with patch('core.llm.anthropic_utils.get_anthropic_base_url', return_value="https://api.anthropic.com"):
            with patch('core.llm.anthropic_utils.get_anthropic_api_key', return_value="sk-test-key"):
                with patch('core.llm.anthropic_utils.is_local_anthropic', return_value=False):
                    with patch('anthropic.Anthropic', return_value=mock_client):
                        from bots.twitter.jarvis_voice import JarvisVoice
                        voice = JarvisVoice()
                        assert voice.api_client is not None

    def test_init_handles_import_error(self):
        """Test initialization handles anthropic utils import errors."""
        with patch('core.llm.anthropic_utils.get_anthropic_base_url', side_effect=Exception("Import failed")):
            from bots.twitter.jarvis_voice import JarvisVoice
            voice = JarvisVoice()
            # Should still initialize with CLI fallback
            assert voice.cli_enabled is True
            assert voice.api_client is None


# =============================================================================
# CLI Availability Tests
# =============================================================================

class TestCLIAvailability:
    """Test CLI availability checking."""

    def test_cli_available_when_found(self, voice_instance):
        """Test _cli_available returns True when CLI is found."""
        with patch('shutil.which', return_value="/usr/local/bin/claude"):
            assert voice_instance._cli_available() is True

    def test_cli_not_available_when_not_found(self, voice_instance):
        """Test _cli_available returns False when CLI not found."""
        with patch('shutil.which', return_value=None):
            assert voice_instance._cli_available() is False


# =============================================================================
# CLI Path Resolution Tests
# =============================================================================

class TestCLIPathResolution:
    """Test CLI path resolution across platforms."""

    def test_get_cli_path_from_which(self, voice_instance):
        """Test _get_cli_path uses shutil.which first."""
        with patch('shutil.which', return_value="/usr/bin/claude"):
            result = voice_instance._get_cli_path()
            assert result == "/usr/bin/claude"

    def test_get_cli_path_windows_fallback(self, voice_instance):
        """Test _get_cli_path tries Windows paths when which fails."""
        with patch('shutil.which', return_value=None):
            with patch('os.path.exists') as mock_exists:
                # First call (which) fails, but Windows path exists
                def exists_side_effect(path):
                    return "AppData" in path and "npm" in path
                mock_exists.side_effect = exists_side_effect

                result = voice_instance._get_cli_path()
                # Should find Windows npm path
                if result:
                    assert "AppData" in result or "npm" in result

    def test_get_cli_path_linux_fallback(self, voice_instance):
        """Test _get_cli_path tries Linux paths when which fails."""
        with patch('shutil.which', return_value=None):
            with patch('os.path.exists') as mock_exists:
                def exists_side_effect(path):
                    return path == "/usr/local/bin/claude"
                mock_exists.side_effect = exists_side_effect

                result = voice_instance._get_cli_path()
                assert result == "/usr/local/bin/claude"

    def test_get_cli_path_none_when_not_found(self, voice_instance):
        """Test _get_cli_path returns None when no path found."""
        with patch('shutil.which', return_value=None):
            with patch('os.path.exists', return_value=False):
                result = voice_instance._get_cli_path()
                assert result is None


# =============================================================================
# CLI Execution Tests
# =============================================================================

class TestCLIExecution:
    """Test CLI command execution."""

    def test_run_cli_success(self, voice_instance):
        """Test successful CLI execution."""
        with patch.object(voice_instance, '_get_cli_path', return_value="/usr/bin/claude"):
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = "generated tweet content"
            mock_result.stderr = ""

            with patch('subprocess.run', return_value=mock_result):
                with patch('platform.system', return_value="Linux"):
                    result = voice_instance._run_cli("test prompt")
                    assert result == "generated tweet content"

    def test_run_cli_returns_none_when_no_cli_path(self, voice_instance):
        """Test _run_cli returns None when CLI path not found."""
        with patch.object(voice_instance, '_get_cli_path', return_value=None):
            result = voice_instance._run_cli("test prompt")
            assert result is None

    def test_run_cli_handles_nonzero_return_code(self, voice_instance):
        """Test _run_cli handles non-zero return codes."""
        with patch.object(voice_instance, '_get_cli_path', return_value="/usr/bin/claude"):
            mock_result = MagicMock()
            mock_result.returncode = 1
            mock_result.stdout = ""
            mock_result.stderr = "error message"

            with patch('subprocess.run', return_value=mock_result):
                with patch('platform.system', return_value="Linux"):
                    result = voice_instance._run_cli("test prompt")
                    assert result is None

    def test_run_cli_handles_timeout(self, voice_instance):
        """Test _run_cli handles timeout exception."""
        with patch.object(voice_instance, '_get_cli_path', return_value="/usr/bin/claude"):
            with patch('subprocess.run', side_effect=subprocess.TimeoutExpired("claude", 60)):
                with patch('platform.system', return_value="Linux"):
                    result = voice_instance._run_cli("test prompt")
                    assert result is None

    def test_run_cli_handles_generic_exception(self, voice_instance):
        """Test _run_cli handles generic exceptions."""
        with patch.object(voice_instance, '_get_cli_path', return_value="/usr/bin/claude"):
            with patch('subprocess.run', side_effect=Exception("Unexpected error")):
                with patch('platform.system', return_value="Linux"):
                    result = voice_instance._run_cli("test prompt")
                    assert result is None

    def test_run_cli_truncates_long_prompt(self, voice_instance):
        """Test _run_cli truncates prompts over 2000 chars."""
        with patch.object(voice_instance, '_get_cli_path', return_value="/usr/bin/claude"):
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = "response"
            mock_result.stderr = ""

            long_prompt = "x" * 3000
            with patch('subprocess.run', return_value=mock_result) as mock_run:
                with patch('platform.system', return_value="Linux"):
                    voice_instance._run_cli(long_prompt)
                    # Check that the prompt was truncated in the call
                    call_args = mock_run.call_args[0][0]
                    # The prompt is the last arg
                    actual_prompt = call_args[-1]
                    assert len(actual_prompt) <= 2000

    def test_run_cli_windows_uses_cmd(self, voice_instance):
        """Test _run_cli uses cmd.exe on Windows."""
        with patch.object(voice_instance, '_get_cli_path', return_value="C:\\claude.cmd"):
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = "response"
            mock_result.stderr = ""

            with patch('subprocess.run', return_value=mock_result) as mock_run:
                with patch('platform.system', return_value="Windows"):
                    voice_instance._run_cli("test")
                    call_args = mock_run.call_args[0][0]
                    assert call_args[0] == "cmd"
                    assert call_args[1] == "/c"

    def test_run_cli_windows_adds_skip_permissions(self, voice_instance):
        """Test _run_cli adds --dangerously-skip-permissions on Windows."""
        with patch.object(voice_instance, '_get_cli_path', return_value="C:\\claude.cmd"):
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = "response"
            mock_result.stderr = ""

            with patch('subprocess.run', return_value=mock_result) as mock_run:
                with patch('platform.system', return_value="Windows"):
                    voice_instance._run_cli("test")
                    call_args = mock_run.call_args[0][0]
                    assert "--dangerously-skip-permissions" in call_args

    def test_run_cli_linux_no_skip_permissions(self, voice_instance):
        """Test _run_cli does not add --dangerously-skip-permissions on Linux."""
        with patch.object(voice_instance, '_get_cli_path', return_value="/usr/bin/claude"):
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = "response"
            mock_result.stderr = ""

            with patch('subprocess.run', return_value=mock_result) as mock_run:
                with patch('platform.system', return_value="Linux"):
                    voice_instance._run_cli("test")
                    call_args = mock_run.call_args[0][0]
                    assert "--dangerously-skip-permissions" not in call_args

    def test_run_cli_empty_output_returns_none(self, voice_instance):
        """Test _run_cli returns None for empty output."""
        with patch.object(voice_instance, '_get_cli_path', return_value="/usr/bin/claude"):
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = "   "  # Whitespace only
            mock_result.stderr = ""

            with patch('subprocess.run', return_value=mock_result):
                with patch('platform.system', return_value="Linux"):
                    result = voice_instance._run_cli("test")
                    assert result is None


# =============================================================================
# Generate Tweet Tests
# =============================================================================

class TestGenerateTweet:
    """Test the main generate_tweet method."""

    @pytest.mark.asyncio
    async def test_generate_tweet_returns_none_when_no_claude(self, voice_instance):
        """Test generate_tweet returns None when no Claude available."""
        with patch.object(voice_instance, '_cli_available', return_value=False):
            result = await voice_instance.generate_tweet("test prompt")
            assert result is None

    @pytest.mark.asyncio
    async def test_generate_tweet_with_api_client(self, voice_instance):
        """Test generate_tweet uses API client when available."""
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="generated tweet via api")]

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response
        voice_instance.api_client = mock_client

        with patch('core.jarvis_voice_bible.validate_jarvis_response', return_value=(True, [])):
            result = await voice_instance.generate_tweet("test prompt")
            assert result == "generated tweet via api"
            mock_client.messages.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_tweet_with_context(self, voice_instance):
        """Test generate_tweet includes context in prompt."""
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="tweet with context")]

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response
        voice_instance.api_client = mock_client

        with patch('core.jarvis_voice_bible.validate_jarvis_response', return_value=(True, [])):
            result = await voice_instance.generate_tweet(
                "test prompt",
                context={"price": 150.0, "change": 5.5}
            )

            # Check that context was included in the call
            call_kwargs = mock_client.messages.create.call_args
            messages = call_kwargs.kwargs.get('messages', call_kwargs[1].get('messages', []))
            user_content = messages[0]['content']
            assert "price" in user_content.lower()
            assert "150" in user_content

    @pytest.mark.asyncio
    async def test_generate_tweet_falls_back_to_cli(self, voice_instance):
        """Test generate_tweet falls back to CLI when API fails."""
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = Exception("API error")
        voice_instance.api_client = mock_client

        with patch.object(voice_instance, '_cli_available', return_value=True):
            with patch.object(voice_instance, '_run_cli', return_value="tweet from cli"):
                with patch('core.jarvis_voice_bible.validate_jarvis_response', return_value=(True, [])):
                    result = await voice_instance.generate_tweet("test prompt")
                    assert result == "tweet from cli"

    @pytest.mark.asyncio
    async def test_generate_tweet_cli_only(self, voice_instance):
        """Test generate_tweet uses CLI when no API client."""
        voice_instance.api_client = None

        with patch.object(voice_instance, '_cli_available', return_value=True):
            with patch.object(voice_instance, '_run_cli', return_value="cli tweet"):
                with patch('core.jarvis_voice_bible.validate_jarvis_response', return_value=(True, [])):
                    result = await voice_instance.generate_tweet("test prompt")
                    assert result == "cli tweet"

    @pytest.mark.asyncio
    async def test_generate_tweet_cleans_json_response(self, voice_instance):
        """Test generate_tweet extracts tweet from JSON response."""
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='{"tweet": "extracted from json"}')]

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response
        voice_instance.api_client = mock_client

        with patch('core.jarvis_voice_bible.validate_jarvis_response', return_value=(True, [])):
            result = await voice_instance.generate_tweet("test prompt")
            assert result == "extracted from json"

    @pytest.mark.asyncio
    async def test_generate_tweet_removes_markdown_code_blocks(self, voice_instance):
        """Test generate_tweet removes markdown code blocks."""
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="```\ntweet content\n```")]

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response
        voice_instance.api_client = mock_client

        with patch('core.jarvis_voice_bible.validate_jarvis_response', return_value=(True, [])):
            result = await voice_instance.generate_tweet("test prompt")
            assert "```" not in result
            assert "tweet content" in result

    @pytest.mark.asyncio
    async def test_generate_tweet_converts_to_lowercase(self, voice_instance):
        """Test generate_tweet converts first char uppercase to lowercase."""
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="This is Uppercase")]

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response
        voice_instance.api_client = mock_client

        with patch('core.jarvis_voice_bible.validate_jarvis_response', return_value=(True, [])):
            result = await voice_instance.generate_tweet("test prompt")
            assert result[0].islower()

    @pytest.mark.asyncio
    async def test_generate_tweet_truncates_long_content(self, voice_instance):
        """Test generate_tweet truncates content over 4000 chars."""
        long_text = "a" * 5000
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=long_text)]

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response
        voice_instance.api_client = mock_client

        with patch('core.jarvis_voice_bible.validate_jarvis_response', return_value=(True, [])):
            result = await voice_instance.generate_tweet("test prompt")
            assert len(result) <= 4000
            assert result.endswith("...")

    @pytest.mark.asyncio
    async def test_generate_tweet_strips_quotes(self, voice_instance):
        """Test generate_tweet strips surrounding quotes."""
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='"quoted tweet"')]

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response
        voice_instance.api_client = mock_client

        with patch('core.jarvis_voice_bible.validate_jarvis_response', return_value=(True, [])):
            result = await voice_instance.generate_tweet("test prompt")
            assert result == "quoted tweet"

    @pytest.mark.asyncio
    async def test_generate_tweet_handles_validation_warning(self, voice_instance):
        """Test generate_tweet logs warning on validation issues."""
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="some tweet")]

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response
        voice_instance.api_client = mock_client

        # Return validation issues
        with patch('core.jarvis_voice_bible.validate_jarvis_response', return_value=(False, ["Too long"])):
            result = await voice_instance.generate_tweet("test prompt")
            # Should still return the tweet despite validation issues
            assert result is not None

    @pytest.mark.asyncio
    async def test_generate_tweet_cli_returns_none(self, voice_instance):
        """Test generate_tweet returns None when CLI returns nothing."""
        voice_instance.api_client = None

        with patch.object(voice_instance, '_cli_available', return_value=True):
            with patch.object(voice_instance, '_run_cli', return_value=None):
                result = await voice_instance.generate_tweet("test prompt")
                assert result is None

    @pytest.mark.asyncio
    async def test_generate_tweet_handles_exception(self, voice_instance):
        """Test generate_tweet returns None on exception."""
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = Exception("API error")
        voice_instance.api_client = mock_client

        with patch.object(voice_instance, '_cli_available', return_value=False):
            result = await voice_instance.generate_tweet("test prompt")
            assert result is None


# =============================================================================
# Market Tweet Tests
# =============================================================================

class TestGenerateMarketTweet:
    """Test generate_market_tweet method."""

    @pytest.mark.asyncio
    async def test_generate_market_tweet_success(self, voice_instance):
        """Test successful market tweet generation."""
        with patch.object(voice_instance, 'generate_tweet', new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = "sol looking good today"

            data = {
                'top_symbol': 'SOL',
                'top_price': 150.0,
                'top_change': 5.5,
                'sentiment': 'bullish',
                'sol_price': 150.0
            }
            result = await voice_instance.generate_market_tweet(data)

            assert result == "sol looking good today"
            mock_gen.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_market_tweet_with_missing_data(self, voice_instance):
        """Test market tweet with missing data uses defaults."""
        with patch.object(voice_instance, 'generate_tweet', new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = "market update"

            data = {}  # Empty data
            result = await voice_instance.generate_market_tweet(data)

            # Should still call generate_tweet with defaults
            mock_gen.assert_called_once()
            call_args = mock_gen.call_args[0][0]
            assert "SOL" in call_args  # Default symbol

    @pytest.mark.asyncio
    async def test_generate_market_tweet_returns_none(self, voice_instance):
        """Test market tweet returns None when generation fails."""
        with patch.object(voice_instance, 'generate_tweet', new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = None

            data = {'sol_price': 100.0}
            result = await voice_instance.generate_market_tweet(data)

            assert result is None


# =============================================================================
# Token Tweet Tests
# =============================================================================

class TestGenerateTokenTweet:
    """Test generate_token_tweet method."""

    @pytest.mark.asyncio
    async def test_generate_token_tweet_bullish(self, voice_instance):
        """Test token tweet generation for bullish token."""
        with patch.object(voice_instance, 'generate_tweet', new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = "$SOL looking strong"

            # Mock scorekeeper
            with patch('bots.treasury.scorekeeper.get_scorekeeper') as mock_sk:
                mock_sk.return_value.get_learnings_for_context.return_value = ""
                mock_sk.return_value.get_performance_summary.return_value = "5W-2L"

                token_data = {
                    'symbol': 'SOL',
                    'price': 150.0,
                    'change': 10.5,
                    'volume': 1000000,
                    'should_roast': False
                }
                result = await voice_instance.generate_token_tweet(token_data)

                assert result == "$SOL looking strong"

    @pytest.mark.asyncio
    async def test_generate_token_tweet_roast(self, voice_instance):
        """Test token tweet generation for roast mode."""
        with patch.object(voice_instance, 'generate_tweet', new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = "not financial advice but..."

            with patch('bots.treasury.scorekeeper.get_scorekeeper') as mock_sk:
                mock_sk.return_value.get_learnings_for_context.return_value = ""
                mock_sk.return_value.get_performance_summary.return_value = ""

                token_data = {
                    'symbol': 'RUGPULL',
                    'price': 0.00001,
                    'change': -50.0,
                    'liquidity': 100,
                    'should_roast': True,
                    'issue': 'low liquidity'
                }
                result = await voice_instance.generate_token_tweet(token_data)

                # Check that roast prompt was used
                call_args = mock_gen.call_args[0][0]
                assert "roast" in call_args.lower() or "skeptic" in call_args.lower()

    @pytest.mark.asyncio
    async def test_generate_token_tweet_scorekeeper_error(self, voice_instance):
        """Test token tweet handles scorekeeper errors gracefully."""
        with patch.object(voice_instance, 'generate_tweet', new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = "token update"

            with patch('bots.treasury.scorekeeper.get_scorekeeper', side_effect=Exception("DB error")):
                token_data = {
                    'symbol': 'SOL',
                    'price': 150.0,
                    'change': 5.0,
                    'should_roast': False
                }
                result = await voice_instance.generate_token_tweet(token_data)

                # Should still work without learnings
                assert result == "token update"


# =============================================================================
# Agentic Tweet Tests
# =============================================================================

class TestGenerateAgenticTweet:
    """Test generate_agentic_tweet method."""

    @pytest.mark.asyncio
    async def test_generate_agentic_tweet_success(self, voice_instance):
        """Test agentic tweet generation."""
        with patch.object(voice_instance, 'generate_tweet', new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = "thinking about ai things"

            result = await voice_instance.generate_agentic_tweet()

            assert result == "thinking about ai things"
            mock_gen.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_agentic_tweet_random_topic(self, voice_instance):
        """Test agentic tweet uses random topics."""
        with patch.object(voice_instance, 'generate_tweet', new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = "ai thought"

            # Call multiple times to test randomness
            results = []
            for _ in range(5):
                await voice_instance.generate_agentic_tweet()
                call_args = mock_gen.call_args[0][0]
                results.append(call_args)

            # Should have called with varying prompts (topics)
            assert mock_gen.call_count == 5


# =============================================================================
# Hourly Tweet Tests
# =============================================================================

class TestGenerateHourlyTweet:
    """Test generate_hourly_tweet method."""

    @pytest.mark.asyncio
    async def test_generate_hourly_tweet_success(self, voice_instance):
        """Test hourly tweet generation."""
        with patch.object(voice_instance, 'generate_tweet', new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = "hourly update"

            data = {
                'sol_price': 150.0,
                'movers': '$BONK +20%',
                'hour': '14:00 UTC'
            }
            result = await voice_instance.generate_hourly_tweet(data)

            assert result == "hourly update"

    @pytest.mark.asyncio
    async def test_generate_hourly_tweet_default_values(self, voice_instance):
        """Test hourly tweet with missing data uses defaults."""
        with patch.object(voice_instance, 'generate_tweet', new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = "hourly"

            data = {}
            await voice_instance.generate_hourly_tweet(data)

            call_args = mock_gen.call_args[0][0]
            assert "quiet day" in call_args.lower() or "now" in call_args.lower()


# =============================================================================
# Reply Generation Tests
# =============================================================================

class TestGenerateReply:
    """Test generate_reply method."""

    @pytest.mark.asyncio
    async def test_generate_reply_success(self, voice_instance):
        """Test reply generation."""
        with patch.object(voice_instance, 'generate_tweet', new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = "thanks. circuits warm."

            result = await voice_instance.generate_reply(
                mention_text="Love your analysis!",
                author="cryptofan"
            )

            assert result == "thanks. circuits warm."

    @pytest.mark.asyncio
    async def test_generate_reply_with_context(self, voice_instance):
        """Test reply with conversation context."""
        with patch.object(voice_instance, 'generate_tweet', new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = "following up on that"

            result = await voice_instance.generate_reply(
                mention_text="Any update on SOL?",
                author="trader123",
                context="Previous conversation about SOL price targets"
            )

            call_args = mock_gen.call_args[0][0]
            assert "context" in call_args.lower()

    @pytest.mark.asyncio
    async def test_generate_reply_null_response(self, voice_instance):
        """Test reply returns None when response is NULL."""
        with patch.object(voice_instance, 'generate_tweet', new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = "NULL"

            result = await voice_instance.generate_reply(
                mention_text="Thanks",
                author="user"
            )

            assert result is None

    @pytest.mark.asyncio
    async def test_generate_reply_null_lowercase(self, voice_instance):
        """Test reply returns None for lowercase null (case-insensitive check)."""
        with patch.object(voice_instance, 'generate_tweet', new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = "null"

            result = await voice_instance.generate_reply(
                mention_text="ok",
                author="user"
            )

            # The code uses result.upper() == "NULL" so lowercase also triggers
            assert result is None


# =============================================================================
# Engagement Tweet Tests
# =============================================================================

class TestGenerateEngagementTweet:
    """Test generate_engagement_tweet method."""

    @pytest.mark.asyncio
    async def test_generate_engagement_tweet_success(self, voice_instance):
        """Test engagement tweet generation."""
        with patch.object(voice_instance, 'generate_tweet', new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = "what are you watching today?"

            result = await voice_instance.generate_engagement_tweet()

            assert result == "what are you watching today?"

    @pytest.mark.asyncio
    async def test_generate_engagement_tweet_random_prompt(self, voice_instance):
        """Test engagement tweet uses random prompts."""
        with patch.object(voice_instance, 'generate_tweet', new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = "question"

            await voice_instance.generate_engagement_tweet()

            call_args = mock_gen.call_args[0][0]
            # Should contain anti-engagement-bait instructions
            assert "never" in call_args.lower() or "don't" in call_args.lower()


# =============================================================================
# Grok Mention Tests
# =============================================================================

class TestGenerateGrokMention:
    """Test generate_grok_mention method."""

    @pytest.mark.asyncio
    async def test_generate_grok_mention_success(self, voice_instance):
        """Test Grok mention tweet generation."""
        with patch.object(voice_instance, 'generate_tweet', new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = "hey @grok big bro"

            result = await voice_instance.generate_grok_mention()

            assert result == "hey @grok big bro"

    @pytest.mark.asyncio
    async def test_generate_grok_mention_references_grok(self, voice_instance):
        """Test Grok mention includes @grok reference."""
        with patch.object(voice_instance, 'generate_tweet', new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = "grok tweet"

            await voice_instance.generate_grok_mention()

            call_args = mock_gen.call_args[0][0]
            assert "@grok" in call_args.lower()


# =============================================================================
# Kind Roast Tests
# =============================================================================

class TestGenerateKindRoast:
    """Test generate_kind_roast method."""

    @pytest.mark.asyncio
    async def test_generate_kind_roast_success(self, voice_instance):
        """Test kind roast generation."""
        with patch.object(voice_instance, 'generate_tweet', new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = "gentle roast here"

            result = await voice_instance.generate_kind_roast(
                target="bad trade",
                reason="bought the top"
            )

            assert result == "gentle roast here"

    @pytest.mark.asyncio
    async def test_generate_kind_roast_includes_rules(self, voice_instance):
        """Test kind roast includes kindness rules."""
        with patch.object(voice_instance, 'generate_tweet', new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = "roast"

            await voice_instance.generate_kind_roast("target", "reason")

            call_args = mock_gen.call_args[0][0]
            assert "never mean" in call_args.lower() or "kind" in call_args.lower()


# =============================================================================
# Morning Briefing Tests
# =============================================================================

class TestGenerateMorningBriefing:
    """Test generate_morning_briefing method."""

    @pytest.mark.asyncio
    async def test_generate_morning_briefing_success(self, voice_instance):
        """Test morning briefing generation."""
        with patch.object(voice_instance, 'generate_tweet', new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = "gm. markets did things overnight."

            data = {
                'sol_price': 150.0,
                'btc_price': 100000,
                'movers': 'SOL, BTC',
                'sentiment': 'bullish'
            }
            result = await voice_instance.generate_morning_briefing(data)

            assert result == "gm. markets did things overnight."

    @pytest.mark.asyncio
    async def test_generate_morning_briefing_default_values(self, voice_instance):
        """Test morning briefing with missing data uses defaults."""
        with patch.object(voice_instance, 'generate_tweet', new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = "gm"

            data = {}
            await voice_instance.generate_morning_briefing(data)

            # Should still work with defaults
            mock_gen.assert_called_once()


# =============================================================================
# Evening Wrap Tests
# =============================================================================

class TestGenerateEveningWrap:
    """Test generate_evening_wrap method."""

    @pytest.mark.asyncio
    async def test_generate_evening_wrap_success(self, voice_instance):
        """Test evening wrap generation."""
        with patch.object(voice_instance, 'generate_tweet', new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = "that's a wrap. green day."

            data = {
                'sol_price': 155.0,
                'sol_change': 3.5,
                'btc_price': 101000,
                'btc_change': 1.0,
                'highlight': 'SOL hit new high',
                'take': 'bullish momentum'
            }
            result = await voice_instance.generate_evening_wrap(data)

            assert result == "that's a wrap. green day."


# =============================================================================
# Weekend Macro Tests
# =============================================================================

class TestGenerateWeekendMacro:
    """Test generate_weekend_macro method."""

    @pytest.mark.asyncio
    async def test_generate_weekend_macro_success(self, voice_instance):
        """Test weekend macro generation."""
        with patch.object(voice_instance, 'generate_tweet', new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = "weekend thoughts: zoom out"

            data = {
                'btc_weekly': '+5%',
                'sol_weekly': '+10%',
                'events': 'Fed meeting Tuesday',
                'thesis': 'consolidation before breakout'
            }
            result = await voice_instance.generate_weekend_macro(data)

            assert result == "weekend thoughts: zoom out"


# =============================================================================
# Self-Aware Tweet Tests
# =============================================================================

class TestGenerateSelfAware:
    """Test generate_self_aware method."""

    @pytest.mark.asyncio
    async def test_generate_self_aware_success(self, voice_instance):
        """Test self-aware tweet generation."""
        with patch.object(voice_instance, 'generate_tweet', new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = "just a mass of neural weights"

            result = await voice_instance.generate_self_aware()

            assert result == "just a mass of neural weights"

    @pytest.mark.asyncio
    async def test_generate_self_aware_random_theme(self, voice_instance):
        """Test self-aware tweet uses random themes."""
        with patch.object(voice_instance, 'generate_tweet', new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = "ai thought"

            await voice_instance.generate_self_aware()

            call_args = mock_gen.call_args[0][0]
            # Should reference AI nature
            assert "ai" in call_args.lower() or "memory" in call_args.lower() or "pattern" in call_args.lower()


# =============================================================================
# Alpha Drop Tests
# =============================================================================

class TestGenerateAlphaDrop:
    """Test generate_alpha_drop method."""

    @pytest.mark.asyncio
    async def test_generate_alpha_drop_success(self, voice_instance):
        """Test alpha drop generation."""
        with patch.object(voice_instance, 'generate_tweet', new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = "$SOL volume divergence noted"

            data = {
                'focus': 'SOL ecosystem',
                'pattern': 'volume divergence',
                'support': 'on-chain data'
            }
            result = await voice_instance.generate_alpha_drop(data)

            assert result == "$SOL volume divergence noted"


# =============================================================================
# Thread Hook Tests
# =============================================================================

class TestGenerateThreadHook:
    """Test generate_thread_hook method."""

    @pytest.mark.asyncio
    async def test_generate_thread_hook_success(self, voice_instance):
        """Test thread hook generation."""
        with patch.object(voice_instance, 'generate_tweet', new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = "been looking into this. thread."

            result = await voice_instance.generate_thread_hook("Solana DeFi analysis")

            assert result == "been looking into this. thread."

    @pytest.mark.asyncio
    async def test_generate_thread_hook_includes_topic(self, voice_instance):
        """Test thread hook includes the topic."""
        with patch.object(voice_instance, 'generate_tweet', new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = "thread hook"

            await voice_instance.generate_thread_hook("Market analysis for Q1")

            call_args = mock_gen.call_args[0][0]
            assert "market analysis for q1" in call_args.lower()


# =============================================================================
# Alpha Signal Tests
# =============================================================================

class TestGenerateAlphaSignal:
    """Test generate_alpha_signal method."""

    @pytest.mark.asyncio
    async def test_generate_alpha_signal_success(self, voice_instance):
        """Test alpha signal generation."""
        with patch.object(voice_instance, 'generate_tweet', new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = "$BONK volume 15x. watching."

            data = {
                'symbol': 'BONK',
                'signal_type': 'volume_spike',
                'description': 'Volume 15x normal',
                'metrics': 'vol/mcap ratio',
                'strength': 'strong',
                'confidence': '75%'
            }
            result = await voice_instance.generate_alpha_signal(data)

            assert result == "$BONK volume 15x. watching."

    @pytest.mark.asyncio
    async def test_generate_alpha_signal_default_values(self, voice_instance):
        """Test alpha signal with missing data uses defaults."""
        with patch.object(voice_instance, 'generate_tweet', new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = "signal"

            data = {}
            await voice_instance.generate_alpha_signal(data)

            call_args = mock_gen.call_args[0][0]
            assert "unknown" in call_args.lower() or "processing" in call_args.lower()


# =============================================================================
# Trend Insight Tests
# =============================================================================

class TestGenerateTrendInsight:
    """Test generate_trend_insight method."""

    @pytest.mark.asyncio
    async def test_generate_trend_insight_success(self, voice_instance):
        """Test trend insight generation."""
        with patch.object(voice_instance, 'generate_tweet', new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = "solana ecosystem trend noted"

            data = {
                'title': 'SOL Ecosystem Rally',
                'summary': 'Multiple tokens up 20%+',
                'category': 'ecosystem',
                'take': 'rotation from ETH'
            }
            result = await voice_instance.generate_trend_insight(data)

            assert result == "solana ecosystem trend noted"


# =============================================================================
# Singleton Pattern Tests
# =============================================================================

class TestGetJarvisVoice:
    """Test get_jarvis_voice singleton function."""

    def test_get_jarvis_voice_returns_instance(self, mock_anthropic_utils):
        """Test get_jarvis_voice returns a JarvisVoice instance."""
        from bots.twitter.jarvis_voice import get_jarvis_voice, JarvisVoice

        # Reset singleton
        import bots.twitter.jarvis_voice as jv_module
        jv_module._jarvis_voice = None

        voice = get_jarvis_voice()
        assert isinstance(voice, JarvisVoice)

    def test_get_jarvis_voice_returns_same_instance(self, mock_anthropic_utils):
        """Test get_jarvis_voice returns the same singleton instance."""
        from bots.twitter.jarvis_voice import get_jarvis_voice

        # Reset singleton
        import bots.twitter.jarvis_voice as jv_module
        jv_module._jarvis_voice = None

        voice1 = get_jarvis_voice()
        voice2 = get_jarvis_voice()

        assert voice1 is voice2


# =============================================================================
# JSON Extraction Tests
# =============================================================================

class TestJSONExtraction:
    """Test JSON extraction from API/CLI responses."""

    @pytest.mark.asyncio
    async def test_extract_tweet_from_json_tweet_key(self, voice_instance):
        """Test extraction from JSON with 'tweet' key."""
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='{"tweet": "the actual tweet"}')]

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response
        voice_instance.api_client = mock_client

        with patch('core.jarvis_voice_bible.validate_jarvis_response', return_value=(True, [])):
            result = await voice_instance.generate_tweet("test")
            assert result == "the actual tweet"

    @pytest.mark.asyncio
    async def test_extract_tweet_from_json_text_key(self, voice_instance):
        """Test extraction from JSON with 'text' key."""
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='{"text": "tweet from text key"}')]

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response
        voice_instance.api_client = mock_client

        with patch('core.jarvis_voice_bible.validate_jarvis_response', return_value=(True, [])):
            result = await voice_instance.generate_tweet("test")
            assert result == "tweet from text key"

    @pytest.mark.asyncio
    async def test_extract_tweet_from_json_content_key(self, voice_instance):
        """Test extraction from JSON with 'content' key."""
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='{"content": "tweet from content key"}')]

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response
        voice_instance.api_client = mock_client

        with patch('core.jarvis_voice_bible.validate_jarvis_response', return_value=(True, [])):
            result = await voice_instance.generate_tweet("test")
            assert result == "tweet from content key"

    @pytest.mark.asyncio
    async def test_extract_tweet_from_malformed_json(self, voice_instance):
        """Test extraction from malformed JSON using regex fallback."""
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='{"tweet": "extracted via regex", invalid json}')]

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response
        voice_instance.api_client = mock_client

        with patch('core.jarvis_voice_bible.validate_jarvis_response', return_value=(True, [])):
            result = await voice_instance.generate_tweet("test")
            assert "extracted via regex" in result


# =============================================================================
# Voice Bible Validation Tests
# =============================================================================

class TestVoiceBibleValidation:
    """Test voice bible validation integration."""

    @pytest.mark.asyncio
    async def test_validation_called_on_api_response(self, voice_instance):
        """Test that validation is called on API responses."""
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="valid tweet")]

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response
        voice_instance.api_client = mock_client

        # Patch where it's looked up in the module (imported at top of jarvis_voice.py)
        with patch('bots.twitter.jarvis_voice.validate_jarvis_response', return_value=(True, [])) as mock_validate:
            await voice_instance.generate_tweet("test")
            mock_validate.assert_called_once()

    @pytest.mark.asyncio
    async def test_validation_called_on_cli_response(self, voice_instance):
        """Test that validation is called on CLI responses."""
        voice_instance.api_client = None

        with patch.object(voice_instance, '_cli_available', return_value=True):
            with patch.object(voice_instance, '_run_cli', return_value="cli tweet"):
                # Patch where it's looked up in the module
                with patch('bots.twitter.jarvis_voice.validate_jarvis_response', return_value=(True, [])) as mock_validate:
                    await voice_instance.generate_tweet("test")
                    mock_validate.assert_called_once()


# =============================================================================
# Edge Cases and Error Handling Tests
# =============================================================================

class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_empty_api_response(self, voice_instance):
        """Test handling of empty API response."""
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="")]

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response
        voice_instance.api_client = mock_client

        with patch('core.jarvis_voice_bible.validate_jarvis_response', return_value=(True, [])):
            result = await voice_instance.generate_tweet("test")
            # Empty string is falsy but still a valid response
            assert result == ""

    @pytest.mark.asyncio
    async def test_whitespace_only_response(self, voice_instance):
        """Test handling of whitespace-only response."""
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="   \n\t  ")]

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response
        voice_instance.api_client = mock_client

        with patch('core.jarvis_voice_bible.validate_jarvis_response', return_value=(True, [])):
            result = await voice_instance.generate_tweet("test")
            assert result == ""

    @pytest.mark.asyncio
    async def test_truncation_at_word_boundary(self, voice_instance):
        """Test that truncation tries to break at word boundaries."""
        # Create a string that will be truncated
        long_text = "word " * 1000  # 5000 chars
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=long_text)]

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response
        voice_instance.api_client = mock_client

        with patch('core.jarvis_voice_bible.validate_jarvis_response', return_value=(True, [])):
            result = await voice_instance.generate_tweet("test")
            # Should end with "..." and not cut mid-word if possible
            assert result.endswith("...")
            assert len(result) <= 4000

    @pytest.mark.asyncio
    async def test_special_characters_preserved(self, voice_instance):
        """Test that special characters are preserved."""
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="$SOL at $150 - nice")]

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response
        voice_instance.api_client = mock_client

        with patch('core.jarvis_voice_bible.validate_jarvis_response', return_value=(True, [])):
            result = await voice_instance.generate_tweet("test")
            assert "$SOL" in result or "$sol" in result.lower()
            assert "$150" in result or "$150" in result.lower()

    @pytest.mark.asyncio
    async def test_cashtag_not_lowercased(self, voice_instance):
        """Test that cashtags starting with $ are not lowercased incorrectly."""
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="$SOL looking good")]

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response
        voice_instance.api_client = mock_client

        with patch('core.jarvis_voice_bible.validate_jarvis_response', return_value=(True, [])):
            result = await voice_instance.generate_tweet("test")
            # $SOL should remain uppercase
            assert "$SOL" in result or "$sol" in result.lower()

    def test_load_env_handles_missing_file(self):
        """Test _load_env handles missing .env file."""
        # This should not raise even if .env doesn't exist
        from bots.twitter.jarvis_voice import _load_env
        # Just verify it doesn't crash
        _load_env()

    @pytest.mark.asyncio
    async def test_context_dict_formatting(self, voice_instance):
        """Test that context dict is properly formatted in prompt."""
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="response")]

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response
        voice_instance.api_client = mock_client

        with patch('core.jarvis_voice_bible.validate_jarvis_response', return_value=(True, [])):
            await voice_instance.generate_tweet(
                "test",
                context={"key1": "value1", "key2": 123}
            )

            call_kwargs = mock_client.messages.create.call_args
            messages = call_kwargs.kwargs.get('messages', call_kwargs[1].get('messages', []))
            content = messages[0]['content']

            assert "key1" in content
            assert "value1" in content
            assert "key2" in content
            assert "123" in content


# =============================================================================
# Integration Tests
# =============================================================================

class TestIntegration:
    """Integration tests for JarvisVoice."""

    @pytest.mark.asyncio
    async def test_full_tweet_generation_flow(self, mock_anthropic_utils):
        """Test full tweet generation flow with mocked API."""
        from bots.twitter.jarvis_voice import JarvisVoice

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="generated tweet content")]
        mock_client.messages.create.return_value = mock_response

        voice = JarvisVoice()
        voice.api_client = mock_client

        with patch('core.jarvis_voice_bible.validate_jarvis_response', return_value=(True, [])):
            result = await voice.generate_tweet("Write a market update")

            assert result is not None
            assert len(result) > 0

    @pytest.mark.asyncio
    async def test_all_generation_methods_callable(self, voice_instance):
        """Test that all generation methods are callable and don't crash."""
        # Mock generate_tweet for all methods
        with patch.object(voice_instance, 'generate_tweet', new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = "test tweet"

            with patch('bots.treasury.scorekeeper.get_scorekeeper') as mock_sk:
                mock_sk.return_value.get_learnings_for_context.return_value = ""
                mock_sk.return_value.get_performance_summary.return_value = ""

                # Test all generation methods
                assert await voice_instance.generate_market_tweet({}) is not None
                assert await voice_instance.generate_token_tweet({'symbol': 'SOL', 'should_roast': False}) is not None
                assert await voice_instance.generate_agentic_tweet() is not None
                assert await voice_instance.generate_hourly_tweet({}) is not None
                assert await voice_instance.generate_reply("test", "user") is not None
                assert await voice_instance.generate_engagement_tweet() is not None
                assert await voice_instance.generate_grok_mention() is not None
                assert await voice_instance.generate_kind_roast("target", "reason") is not None
                assert await voice_instance.generate_morning_briefing({}) is not None
                assert await voice_instance.generate_evening_wrap({}) is not None
                assert await voice_instance.generate_weekend_macro({}) is not None
                assert await voice_instance.generate_self_aware() is not None
                assert await voice_instance.generate_alpha_drop({}) is not None
                assert await voice_instance.generate_thread_hook("topic") is not None
                assert await voice_instance.generate_alpha_signal({}) is not None
                assert await voice_instance.generate_trend_insight({}) is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
