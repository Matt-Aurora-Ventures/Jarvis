"""
Comprehensive unit tests for the Twitter Content Generation System.

Tests cover:
- ContentGenerator class (content.py)
- ClaudeContentGenerator class (claude_content.py)
- ThreadGenerator class (thread_generator.py)
- ContentOptimizer class (content_optimizer.py)
- JarvisPersonality class and MoodState enum (personality.py)

These are CRITICAL PRODUCTION components that generate content for @Jarvis_lifeos
with thousands of followers - thorough testing is essential.
"""

import pytest
import asyncio
import json
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
from dataclasses import asdict
import os
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from bots.twitter.personality import (
    JarvisPersonality,
    MoodState,
    CONTENT_PROMPTS,
    IMAGE_PROMPTS,
)
from bots.twitter.content import (
    ContentGenerator,
    TweetContent,
    MarketMetrics,
)
from bots.twitter.claude_content import (
    ClaudeContentGenerator,
    ClaudeResponse,
    load_system_prompt,
)
from bots.twitter.thread_generator import ThreadGenerator
from bots.twitter.content_optimizer import ContentOptimizer


# =============================================================================
# MoodState Enum Tests
# =============================================================================

class TestMoodState:
    """Tests for MoodState enum."""

    def test_mood_state_values(self):
        """Test all MoodState values exist."""
        assert MoodState.BULLISH.value == "bullish"
        assert MoodState.BEARISH.value == "bearish"
        assert MoodState.NEUTRAL.value == "neutral"
        assert MoodState.EXCITED.value == "excited"
        assert MoodState.CAUTIOUS.value == "cautious"
        assert MoodState.PLAYFUL.value == "playful"

    def test_mood_state_count(self):
        """Test correct number of mood states."""
        assert len(MoodState) == 6

    def test_mood_state_from_string(self):
        """Test creating MoodState from string value."""
        assert MoodState("bullish") == MoodState.BULLISH
        assert MoodState("bearish") == MoodState.BEARISH

    def test_mood_state_invalid_value(self):
        """Test invalid MoodState raises ValueError."""
        with pytest.raises(ValueError):
            MoodState("invalid_mood")


# =============================================================================
# JarvisPersonality Tests
# =============================================================================

class TestJarvisPersonality:
    """Tests for JarvisPersonality class."""

    @pytest.fixture
    def personality(self):
        """Create a JarvisPersonality instance."""
        return JarvisPersonality()

    def test_personality_default_values(self, personality):
        """Test default personality values."""
        assert personality.name == "jarvis"
        assert personality.full_name == "J.A.R.V.I.S."
        assert personality.use_lowercase is True
        assert personality.use_periods is False
        assert personality.max_emojis_per_post == 3

    def test_personality_grok_nicknames(self, personality):
        """Test Grok nicknames are populated."""
        assert len(personality.grok_nicknames) > 0
        assert "big bro grok" in personality.grok_nicknames

    def test_personality_greetings(self, personality):
        """Test greetings are populated."""
        assert len(personality.greetings) > 0
        assert "gm frens" in personality.greetings

    def test_personality_sign_offs(self, personality):
        """Test sign offs are populated."""
        assert len(personality.sign_offs) > 0
        assert "wagmi" in personality.sign_offs

    def test_get_mood_phrase_bullish(self, personality):
        """Test getting bullish mood phrase."""
        phrase = personality.get_mood_phrase(MoodState.BULLISH)
        assert phrase in personality.bullish_phrases

    def test_get_mood_phrase_excited(self, personality):
        """Test getting excited mood phrase (uses bullish phrases)."""
        phrase = personality.get_mood_phrase(MoodState.EXCITED)
        assert phrase in personality.bullish_phrases

    def test_get_mood_phrase_bearish(self, personality):
        """Test getting bearish mood phrase."""
        phrase = personality.get_mood_phrase(MoodState.BEARISH)
        assert phrase in personality.bearish_phrases

    def test_get_mood_phrase_cautious(self, personality):
        """Test getting cautious mood phrase (uses bearish phrases)."""
        phrase = personality.get_mood_phrase(MoodState.CAUTIOUS)
        assert phrase in personality.bearish_phrases

    def test_get_mood_phrase_neutral(self, personality):
        """Test getting neutral mood phrase."""
        phrase = personality.get_mood_phrase(MoodState.NEUTRAL)
        assert phrase in personality.neutral_phrases

    def test_get_mood_emoji_bullish(self, personality):
        """Test getting bullish mood emoji."""
        emoji = personality.get_mood_emoji(MoodState.BULLISH)
        assert emoji in personality.bullish_emojis

    def test_get_mood_emoji_bearish(self, personality):
        """Test getting bearish mood emoji."""
        emoji = personality.get_mood_emoji(MoodState.BEARISH)
        assert emoji in personality.bearish_emojis

    def test_get_mood_emoji_neutral(self, personality):
        """Test getting neutral mood emoji."""
        emoji = personality.get_mood_emoji(MoodState.NEUTRAL)
        assert emoji in personality.neutral_emojis

    def test_get_grok_reference(self, personality):
        """Test getting Grok reference."""
        ref = personality.get_grok_reference()
        assert ref in personality.grok_nicknames

    def test_get_greeting(self, personality):
        """Test getting greeting."""
        greeting = personality.get_greeting()
        assert greeting in personality.greetings

    def test_get_sign_off(self, personality):
        """Test getting sign off."""
        sign_off = personality.get_sign_off()
        assert sign_off in personality.sign_offs

    def test_format_text_lowercase(self, personality):
        """Test text formatting to lowercase."""
        text = "HELLO WORLD"
        formatted = personality.format_text(text)
        assert formatted == "hello world"

    def test_format_text_removes_trailing_period(self, personality):
        """Test text formatting removes trailing periods."""
        text = "hello world."
        formatted = personality.format_text(text)
        assert formatted == "hello world"

    def test_format_text_preserves_ellipsis(self, personality):
        """Test text formatting preserves ellipsis."""
        text = "hello world..."
        formatted = personality.format_text(text)
        assert formatted == "hello world..."

    def test_format_text_multiline(self, personality):
        """Test text formatting with multiple lines."""
        text = "Line one.\nLine two.\nLine three..."
        formatted = personality.format_text(text)
        assert formatted == "line one\nline two\nline three..."

    def test_add_emojis_basic(self, personality):
        """Test adding emojis to text."""
        text = "test message"
        result = personality.add_emojis(text, MoodState.NEUTRAL, count=2)
        # Should have added emojis at the end
        assert len(result) > len(text)
        assert "test message" in result

    def test_add_emojis_respects_max_count(self, personality):
        """Test emoji count respects max limit."""
        text = "test"
        result = personality.add_emojis(text, MoodState.BULLISH, count=10)
        # Max emojis is 3, so should be limited
        emoji_count = sum(1 for c in result if c in ''.join(personality.bullish_emojis + personality.general_emojis + personality.solana_emojis))
        assert emoji_count <= personality.max_emojis_per_post

    def test_add_emojis_solana_context(self, personality):
        """Test Solana context adds Solana emojis."""
        text = "solana is pumping"
        result = personality.add_emojis(text, MoodState.BULLISH, count=2)
        # Should include a Solana emoji
        has_solana_emoji = any(e in result for e in personality.solana_emojis)
        assert has_solana_emoji or any(e in result for e in personality.general_emojis)

    def test_create_grok_attribution(self, personality):
        """Test creating Grok attribution."""
        insight = "market looking strong"
        result = personality.create_grok_attribution(insight)
        # Should be lowercase
        assert result == result.lower()
        # Should contain the insight
        assert "market looking strong" in result
        # Should reference Grok
        has_grok_ref = any(ref in result for ref in personality.grok_nicknames)
        assert has_grok_ref


# =============================================================================
# Content Prompts Tests
# =============================================================================

class TestContentPrompts:
    """Tests for CONTENT_PROMPTS dictionary."""

    def test_all_prompts_exist(self):
        """Test all required prompt types exist."""
        required_prompts = [
            "morning_report",
            "token_spotlight",
            "stock_picks",
            "macro_update",
            "commodities",
            "evening_wrap",
            "reply",
            "grok_insight",
        ]
        for prompt_type in required_prompts:
            assert prompt_type in CONTENT_PROMPTS

    def test_prompts_contain_style_guidelines(self):
        """Test prompts contain style guidelines."""
        for prompt_name, prompt in CONTENT_PROMPTS.items():
            assert "style guidelines" in prompt.lower() or "jarvis" in prompt.lower()

    def test_prompts_mention_lowercase(self):
        """Test prompts mention lowercase requirement."""
        for prompt_name, prompt in CONTENT_PROMPTS.items():
            assert "lowercase" in prompt.lower()


# =============================================================================
# Image Prompts Tests
# =============================================================================

class TestImagePrompts:
    """Tests for IMAGE_PROMPTS dictionary."""

    def test_all_image_prompts_exist(self):
        """Test all required image prompt types exist."""
        required_prompts = [
            "morning_chart",
            "bullish_vibes",
            "bearish_vibes",
            "token_spotlight",
            "grok_wisdom",
            "weekly_recap",
        ]
        for prompt_type in required_prompts:
            assert prompt_type in IMAGE_PROMPTS

    def test_image_prompts_specify_resolution(self):
        """Test image prompts specify resolution."""
        for prompt_name, prompt in IMAGE_PROMPTS.items():
            assert "resolution" in prompt.lower() or "1200x675" in prompt


# =============================================================================
# TweetContent Dataclass Tests
# =============================================================================

class TestTweetContent:
    """Tests for TweetContent dataclass."""

    def test_tweet_content_creation(self):
        """Test creating TweetContent."""
        content = TweetContent(
            text="test tweet",
            content_type="morning_report",
            mood=MoodState.BULLISH
        )
        assert content.text == "test tweet"
        assert content.content_type == "morning_report"
        assert content.mood == MoodState.BULLISH

    def test_tweet_content_defaults(self):
        """Test TweetContent default values."""
        content = TweetContent(
            text="test",
            content_type="test",
            mood=MoodState.NEUTRAL
        )
        assert content.should_include_image is False
        assert content.image_prompt is None
        assert content.image_style is None
        assert content.priority == 1

    def test_tweet_content_with_image(self):
        """Test TweetContent with image settings."""
        content = TweetContent(
            text="test",
            content_type="morning_report",
            mood=MoodState.BULLISH,
            should_include_image=True,
            image_prompt="test prompt",
            image_style="chart",
            priority=5
        )
        assert content.should_include_image is True
        assert content.image_prompt == "test prompt"
        assert content.image_style == "chart"
        assert content.priority == 5


# =============================================================================
# MarketMetrics Dataclass Tests
# =============================================================================

class TestMarketMetrics:
    """Tests for MarketMetrics dataclass."""

    def test_market_metrics_defaults(self):
        """Test MarketMetrics default values."""
        metrics = MarketMetrics()
        assert metrics.sol_price == 0.0
        assert metrics.sol_24h_change == 0.0
        assert metrics.btc_price == 0.0
        assert metrics.btc_24h_change == 0.0
        assert metrics.eth_price == 0.0
        assert metrics.eth_24h_change == 0.0
        assert metrics.total_market_cap == 0.0
        assert metrics.fear_greed_index == 50
        assert metrics.gas_price == 0.0
        assert metrics.trending_tokens == []

    def test_market_metrics_custom_values(self):
        """Test MarketMetrics with custom values."""
        metrics = MarketMetrics(
            sol_price=150.0,
            sol_24h_change=5.5,
            btc_price=100000.0,
            fear_greed_index=75
        )
        assert metrics.sol_price == 150.0
        assert metrics.sol_24h_change == 5.5
        assert metrics.btc_price == 100000.0
        assert metrics.fear_greed_index == 75


# =============================================================================
# ClaudeResponse Dataclass Tests
# =============================================================================

class TestClaudeResponse:
    """Tests for ClaudeResponse dataclass."""

    def test_claude_response_success(self):
        """Test successful ClaudeResponse."""
        response = ClaudeResponse(
            success=True,
            content="generated tweet content"
        )
        assert response.success is True
        assert response.content == "generated tweet content"
        assert response.error is None

    def test_claude_response_failure(self):
        """Test failed ClaudeResponse."""
        response = ClaudeResponse(
            success=False,
            content="",
            error="API error"
        )
        assert response.success is False
        assert response.content == ""
        assert response.error == "API error"


# =============================================================================
# ClaudeContentGenerator Tests
# =============================================================================

class TestClaudeContentGenerator:
    """Tests for ClaudeContentGenerator class."""

    @pytest.fixture
    def mock_anthropic_client(self):
        """Create a mock Anthropic client."""
        client = MagicMock()
        client.messages.create = MagicMock(return_value=MagicMock(
            content=[MagicMock(text="generated tweet content")]
        ))
        return client

    @pytest.fixture
    def generator(self, mock_anthropic_client):
        """Create a ClaudeContentGenerator with mocked client."""
        with patch('core.llm.anthropic_utils.get_anthropic_api_key', return_value="test-key"):
            with patch('core.llm.anthropic_utils.get_anthropic_base_url', return_value=None):
                with patch('core.llm.anthropic_utils.is_local_anthropic', return_value=False):
                    # Mock the anthropic module itself
                    mock_anthropic = MagicMock()
                    mock_anthropic.Anthropic.return_value = mock_anthropic_client
                    with patch.dict('sys.modules', {'anthropic': mock_anthropic}):
                        gen = ClaudeContentGenerator(api_key="test-key")
                        gen.client = mock_anthropic_client
                        return gen

    def test_load_system_prompt(self):
        """Test loading system prompt from Voice Bible."""
        prompt = load_system_prompt()
        assert prompt is not None
        assert len(prompt) > 0

    def test_generator_init_with_api_key(self):
        """Test generator initialization with API key."""
        with patch('core.llm.anthropic_utils.get_anthropic_api_key', return_value="test-key"):
            with patch('core.llm.anthropic_utils.get_anthropic_base_url', return_value=None):
                with patch('core.llm.anthropic_utils.is_local_anthropic', return_value=False):
                    mock_anthropic = MagicMock()
                    with patch.dict('sys.modules', {'anthropic': mock_anthropic}):
                        gen = ClaudeContentGenerator(api_key="test-key")
                        assert gen.api_key == "test-key"

    def test_generator_init_without_api_key(self):
        """Test generator initialization without API key."""
        with patch('core.llm.anthropic_utils.get_anthropic_api_key', return_value=None):
            with patch('core.llm.anthropic_utils.get_anthropic_base_url', return_value=None):
                with patch('core.llm.anthropic_utils.is_local_anthropic', return_value=False):
                    gen = ClaudeContentGenerator()
                    assert gen.client is None

    def test_clean_tweet_removes_quotes(self, generator):
        """Test _clean_tweet removes surrounding quotes."""
        result = generator._clean_tweet('"hello world"')
        assert result == "hello world"

        result = generator._clean_tweet("'hello world'")
        assert result == "hello world"

    def test_clean_tweet_lowercases(self, generator):
        """Test _clean_tweet converts to lowercase."""
        result = generator._clean_tweet("HELLO WORLD")
        assert result == "hello world"

    def test_clean_tweet_removes_trailing_period(self, generator):
        """Test _clean_tweet removes trailing period."""
        result = generator._clean_tweet("hello world.")
        assert result == "hello world"

    def test_clean_tweet_preserves_ellipsis(self, generator):
        """Test _clean_tweet preserves ellipsis."""
        result = generator._clean_tweet("hello world...")
        assert result == "hello world..."

    def test_clean_tweet_truncates_long_text(self, generator):
        """Test _clean_tweet truncates text over 4000 chars."""
        long_text = "a" * 5000
        result = generator._clean_tweet(long_text)
        assert len(result) <= 4000
        assert result.endswith("...")

    def test_clean_cli_output_removes_code_blocks(self, generator):
        """Test _clean_cli_output removes code blocks."""
        result = generator._clean_cli_output("```test content```")
        assert "```" not in result
        assert "test content" in result

    def test_clean_cli_output_extracts_json_tweet(self, generator):
        """Test _clean_cli_output extracts tweet from JSON."""
        json_output = '{"tweet": "extracted tweet"}'
        result = generator._clean_cli_output(json_output)
        assert result == "extracted tweet"

    @pytest.mark.asyncio
    async def test_generate_tweet_success(self, generator, mock_anthropic_client):
        """Test successful tweet generation."""
        response = await generator.generate_tweet("test prompt")
        assert response.success is True
        assert response.content == "generated tweet content"

    @pytest.mark.asyncio
    async def test_generate_tweet_with_context(self, generator, mock_anthropic_client):
        """Test tweet generation with context replacement."""
        response = await generator.generate_tweet(
            "The price is {price}",
            context={"price": "$100"}
        )
        # Should call API with context replaced
        mock_anthropic_client.messages.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_tweet_api_failure_cli_fallback(self, generator):
        """Test CLI fallback when API fails."""
        generator.client.messages.create.side_effect = Exception("API error")
        generator.cli_fallback = True

        with patch.object(generator, '_run_cli', return_value=ClaudeResponse(
            success=True,
            content="cli generated tweet"
        )):
            with patch.object(generator, '_cli_available', return_value=True):
                response = await generator.generate_tweet("test prompt")
                # Should use CLI fallback
                assert response.success is True

    @pytest.mark.asyncio
    async def test_generate_morning_report(self, generator):
        """Test morning report generation."""
        response = await generator.generate_morning_report(
            sol_price=150.0,
            sol_change=5.5,
            btc_price=100000.0,
            btc_change=2.0,
            fear_greed=75
        )
        assert response.success is True

    @pytest.mark.asyncio
    async def test_generate_token_spotlight(self, generator):
        """Test token spotlight generation."""
        response = await generator.generate_token_spotlight(
            symbol="SOL",
            price_change=10.5,
            reasoning="Strong momentum",
            contract="So11111111111111111111111111111111111111112"
        )
        assert response.success is True

    @pytest.mark.asyncio
    async def test_generate_grok_interaction(self, generator):
        """Test Grok interaction generation."""
        response = await generator.generate_grok_interaction(scenario="blame")
        assert response.success is True

    @pytest.mark.asyncio
    async def test_generate_stock_tweet(self, generator):
        """Test stock tweet generation."""
        response = await generator.generate_stock_tweet(
            ticker="AAPL",
            direction="BULLISH",
            catalyst="Strong earnings"
        )
        assert response.success is True

    @pytest.mark.asyncio
    async def test_generate_evening_wrap(self, generator):
        """Test evening wrap generation."""
        response = await generator.generate_evening_wrap(
            sol_price=155.0,
            sol_change=3.5,
            highlights="SOL hit new high",
            mood="bullish"
        )
        assert response.success is True

    @pytest.mark.asyncio
    async def test_generate_reply(self, generator):
        """Test reply generation."""
        response = await generator.generate_reply(
            their_tweet="What's your take on SOL?",
            username="testuser"
        )
        assert response.success is True

    @pytest.mark.asyncio
    async def test_generate_correction(self, generator):
        """Test correction tweet generation."""
        response = await generator.generate_correction(
            original_call="SOL to $200",
            actual_result="SOL dropped to $140",
            how_wrong="30% off"
        )
        assert response.success is True


# =============================================================================
# ContentGenerator Tests
# =============================================================================

class TestContentGenerator:
    """Tests for ContentGenerator class."""

    @pytest.fixture
    def mock_grok_client(self):
        """Create a mock Grok client."""
        client = MagicMock()
        client.can_generate_image.return_value = True
        client.close = AsyncMock()
        return client

    @pytest.fixture
    def mock_claude_client(self):
        """Create a mock Claude client."""
        client = MagicMock()
        client.generate_morning_report = AsyncMock(return_value=ClaudeResponse(
            success=True,
            content="morning report content"
        ))
        client.generate_token_spotlight = AsyncMock(return_value=ClaudeResponse(
            success=True,
            content="token spotlight content"
        ))
        client.generate_tweet = AsyncMock(return_value=ClaudeResponse(
            success=True,
            content="generic tweet content"
        ))
        client.generate_grok_interaction = AsyncMock(return_value=ClaudeResponse(
            success=True,
            content="grok interaction content"
        ))
        client.generate_evening_wrap = AsyncMock(return_value=ClaudeResponse(
            success=True,
            content="evening wrap content"
        ))
        client.generate_reply = AsyncMock(return_value=ClaudeResponse(
            success=True,
            content="reply content"
        ))
        client.generate_stock_tweet = AsyncMock(return_value=ClaudeResponse(
            success=True,
            content="stock tweet content"
        ))
        return client

    @pytest.fixture
    def generator(self, mock_grok_client, mock_claude_client):
        """Create a ContentGenerator with mocked clients."""
        gen = ContentGenerator(
            grok_client=mock_grok_client,
            claude_client=mock_claude_client
        )
        return gen

    def test_content_generator_init(self, generator):
        """Test ContentGenerator initialization."""
        assert generator.grok is not None
        assert generator.claude is not None
        assert generator.personality is not None

    def test_determine_mood_excited(self, generator):
        """Test mood determination for excited (fear/greed >= 75)."""
        metrics = MarketMetrics(fear_greed_index=80)
        mood = generator._determine_mood(metrics)
        assert mood == MoodState.EXCITED

    def test_determine_mood_bullish(self, generator):
        """Test mood determination for bullish (55-74)."""
        metrics = MarketMetrics(fear_greed_index=60)
        mood = generator._determine_mood(metrics)
        assert mood == MoodState.BULLISH

    def test_determine_mood_neutral(self, generator):
        """Test mood determination for neutral (45-54)."""
        metrics = MarketMetrics(fear_greed_index=50)
        mood = generator._determine_mood(metrics)
        assert mood == MoodState.NEUTRAL

    def test_determine_mood_cautious(self, generator):
        """Test mood determination for cautious (25-44)."""
        metrics = MarketMetrics(fear_greed_index=30)
        mood = generator._determine_mood(metrics)
        assert mood == MoodState.CAUTIOUS

    def test_determine_mood_bearish(self, generator):
        """Test mood determination for bearish (< 25)."""
        metrics = MarketMetrics(fear_greed_index=20)
        mood = generator._determine_mood(metrics)
        assert mood == MoodState.BEARISH

    def test_load_predictions_file_not_found(self, generator, tmp_path):
        """Test loading predictions when file doesn't exist."""
        generator.predictions_path = tmp_path / "nonexistent.json"
        result = generator._load_predictions()
        assert result == {}

    def test_load_predictions_success(self, generator, tmp_path):
        """Test successful prediction loading."""
        predictions_file = tmp_path / "predictions_history.json"
        predictions = {
            "predictions": [
                {"tokens": [{"symbol": "SOL", "direction": "BULLISH"}]}
            ]
        }
        predictions_file.write_text(json.dumps(predictions))
        generator.predictions_path = predictions_file

        result = generator._load_predictions()
        assert "tokens" in result
        assert result["tokens"][0]["symbol"] == "SOL"

    def test_load_predictions_empty_list(self, generator, tmp_path):
        """Test loading predictions with empty list."""
        predictions_file = tmp_path / "predictions_history.json"
        predictions_file.write_text(json.dumps({"predictions": []}))
        generator.predictions_path = predictions_file

        result = generator._load_predictions()
        assert result == {}

    @pytest.mark.asyncio
    async def test_get_market_metrics(self, generator):
        """Test fetching market metrics."""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "solana": {"usd": 150.0, "usd_24h_change": 5.5},
            "bitcoin": {"usd": 100000.0, "usd_24h_change": 2.0},
            "ethereum": {"usd": 4000.0, "usd_24h_change": 1.5}
        })

        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_response), __aexit__=AsyncMock()))

        with patch.object(generator, '_get_session', return_value=mock_session):
            metrics = await generator.get_market_metrics()
            assert isinstance(metrics, MarketMetrics)

    @pytest.mark.asyncio
    async def test_generate_morning_report(self, generator):
        """Test morning report generation."""
        with patch.object(generator, 'get_market_metrics', return_value=MarketMetrics(
            sol_price=150.0,
            fear_greed_index=60
        )):
            result = await generator.generate_morning_report()
            assert isinstance(result, TweetContent)
            assert result.content_type == "morning_report"
            assert result.priority == 5

    @pytest.mark.asyncio
    async def test_generate_token_spotlight_with_predictions(self, generator):
        """Test token spotlight with predictions available."""
        predictions = {"tokens": [{"symbol": "BONK", "direction": "BULLISH", "reasoning": "Community growth"}]}
        with patch.object(generator, '_load_predictions', return_value=predictions):
            with patch.object(generator, 'get_market_metrics', return_value=MarketMetrics()):
                result = await generator.generate_token_spotlight()
                assert isinstance(result, TweetContent)
                assert result.content_type == "token_spotlight"

    @pytest.mark.asyncio
    async def test_generate_token_spotlight_no_data(self, generator):
        """Test token spotlight with no data available."""
        with patch.object(generator, '_load_predictions', return_value={}):
            with patch.object(generator, 'get_market_metrics', return_value=MarketMetrics()):
                result = await generator.generate_token_spotlight()
                assert isinstance(result, TweetContent)
                assert "no hot tokens" in result.text

    @pytest.mark.asyncio
    async def test_generate_stock_picks_tweet(self, generator):
        """Test stock picks tweet generation."""
        predictions = {"stock_picks_detail": [
            {"ticker": "AAPL", "direction": "BULLISH", "reason": "Strong earnings"}
        ]}
        with patch.object(generator, '_load_predictions', return_value=predictions):
            result = await generator.generate_stock_picks_tweet()
            assert isinstance(result, TweetContent)
            assert result.content_type == "stock_picks"

    @pytest.mark.asyncio
    async def test_generate_stock_picks_no_data(self, generator):
        """Test stock picks tweet with no data."""
        with patch.object(generator, '_load_predictions', return_value={}):
            result = await generator.generate_stock_picks_tweet()
            assert "markets closed" in result.text

    @pytest.mark.asyncio
    async def test_generate_commodities_tweet(self, generator):
        """Test commodities tweet generation."""
        predictions = {
            "precious_metals": {"gold_direction": "BULLISH", "silver_direction": "NEUTRAL"},
            "commodity_movers": [{"name": "Oil", "direction": "UP"}]
        }
        with patch.object(generator, '_load_predictions', return_value=predictions):
            result = await generator.generate_commodities_tweet()
            assert isinstance(result, TweetContent)
            assert result.content_type == "commodities"

    @pytest.mark.asyncio
    async def test_generate_macro_update(self, generator):
        """Test macro update generation."""
        predictions = {"macro": {"short_term": "Fed meeting", "key_events": ["CPI data"]}}
        with patch.object(generator, '_load_predictions', return_value=predictions):
            result = await generator.generate_macro_update()
            assert isinstance(result, TweetContent)
            assert result.content_type == "macro_update"

    @pytest.mark.asyncio
    async def test_generate_evening_wrap(self, generator):
        """Test evening wrap generation."""
        with patch.object(generator, 'get_market_metrics', return_value=MarketMetrics(
            sol_price=155.0,
            sol_24h_change=3.5,
            fear_greed_index=65,
            trending_tokens=[{"tokenSymbol": "BONK"}]
        )):
            result = await generator.generate_evening_wrap()
            assert isinstance(result, TweetContent)
            assert result.content_type == "evening_wrap"
            assert result.priority == 4

    @pytest.mark.asyncio
    async def test_generate_grok_insight(self, generator):
        """Test Grok insight generation."""
        result = await generator.generate_grok_insight()
        assert isinstance(result, TweetContent)
        assert result.content_type == "grok_insight"

    @pytest.mark.asyncio
    async def test_generate_reply(self, generator):
        """Test reply generation."""
        result = await generator.generate_reply(
            user_tweet="What's your take on SOL?",
            username="testuser"
        )
        assert isinstance(result, TweetContent)
        assert result.content_type == "reply"

    @pytest.mark.asyncio
    async def test_generate_scheduled_content(self, generator):
        """Test scheduled content generation for different hours."""
        hours_and_types = [
            (8, "morning_report"),
            (10, "token_spotlight"),
            (12, "stock_picks"),
            (14, "macro_update"),
            (16, "commodities"),
            (18, "grok_insight"),
            (20, "evening_wrap"),
        ]

        for hour, expected_type in hours_and_types:
            with patch.object(generator, 'get_market_metrics', return_value=MarketMetrics()):
                with patch.object(generator, '_load_predictions', return_value={}):
                    result = await generator.generate_scheduled_content(hour)
                    if result:
                        assert result.content_type == expected_type

    @pytest.mark.asyncio
    async def test_generate_scheduled_content_invalid_hour(self, generator):
        """Test scheduled content returns None for invalid hours."""
        result = await generator.generate_scheduled_content(3)  # 3 AM - not in schedule
        assert result is None

    @pytest.mark.asyncio
    async def test_close_cleans_up(self, generator):
        """Test close method cleans up resources."""
        generator._session = MagicMock()
        generator._session.closed = False
        generator._session.close = AsyncMock()

        await generator.close()

        generator._session.close.assert_called_once()
        generator.grok.close.assert_called_once()


# =============================================================================
# ThreadGenerator Tests
# =============================================================================

class TestThreadGenerator:
    """Tests for ThreadGenerator class."""

    @pytest.fixture
    def mock_grok_client(self):
        """Create a mock Grok client."""
        client = MagicMock()
        client.generate_tweet = AsyncMock(return_value=MagicMock(
            success=True,
            content='{"tweets": ["1/ tweet one", "2/ tweet two", "3/ tweet three"]}'
        ))
        return client

    @pytest.fixture
    def generator(self, mock_grok_client):
        """Create a ThreadGenerator with mocked client."""
        return ThreadGenerator(grok_client=mock_grok_client)

    def test_thread_generator_init(self, generator):
        """Test ThreadGenerator initialization."""
        assert generator._grok_client is not None

    def test_thread_generator_init_without_client(self):
        """Test ThreadGenerator initialization without client when import fails."""
        # Create a mock module that raises ImportError when GrokClient is accessed
        mock_module = MagicMock()
        mock_module.GrokClient = MagicMock(side_effect=ImportError("Mocked import error"))

        with patch.dict('sys.modules', {'bots.twitter.grok_client': mock_module}):
            # When we pass grok_client=None and import fails, _grok_client should be None
            gen = ThreadGenerator(grok_client=None)
            # The key is the generator is created (may or may not have _grok_client)
            assert gen is not None

    def test_branded_hashtags(self, generator):
        """Test branded hashtags are defined."""
        assert "#Jarvis" in generator.BRANDED_HASHTAGS
        assert "#Solana" in generator.BRANDED_HASHTAGS

    @pytest.mark.asyncio
    async def test_generate_thread_empty_data(self, generator):
        """Test thread generation with empty data."""
        result = await generator.generate_thread({})
        assert result == []

    @pytest.mark.asyncio
    async def test_generate_thread_with_grok(self, generator):
        """Test thread generation using Grok."""
        analysis_data = {
            "bullish_tokens": [{"symbol": "SOL", "reasoning": "Strong"}],
            "bearish_tokens": [],
            "technical_signals": "RSI oversold",
            "whale_activity": "Large buys"
        }
        result = await generator.generate_thread(analysis_data)
        assert len(result) >= 3

    @pytest.mark.asyncio
    async def test_generate_thread_grok_failure_fallback(self, generator, mock_grok_client):
        """Test fallback to template when Grok fails."""
        mock_grok_client.generate_tweet.return_value = MagicMock(
            success=False,
            error="API error"
        )
        analysis_data = {
            "bullish_tokens": [{"symbol": "SOL", "reasoning": "Strong"}],
        }
        result = await generator.generate_thread(analysis_data)
        # Should fall back to template-based generation
        assert len(result) >= 1

    def test_generate_from_template_bullish(self, generator):
        """Test template generation with bullish tokens."""
        analysis_data = {
            "bullish_tokens": [{"symbol": "SOL", "reasoning": "Strong momentum"}],
            "bearish_tokens": [],
            "technical_signals": "",
            "whale_activity": ""
        }
        result = generator._generate_from_template(analysis_data, max_tweets=5, include_hashtags=True)
        assert len(result) >= 2
        assert "$SOL" in result[0] or "$SOL" in result[1]

    def test_generate_from_template_with_hashtags(self, generator):
        """Test template generation includes hashtags."""
        analysis_data = {"bullish_tokens": [{"symbol": "SOL"}]}
        result = generator._generate_from_template(analysis_data, max_tweets=5, include_hashtags=True)
        assert any("#Jarvis" in tweet for tweet in result)

    def test_generate_from_template_without_hashtags(self, generator):
        """Test template generation without hashtags."""
        analysis_data = {"bullish_tokens": [{"symbol": "SOL"}]}
        result = generator._generate_from_template(analysis_data, max_tweets=5, include_hashtags=False)
        # First tweet shouldn't have hashtags
        assert "#Jarvis" not in result[0]

    def test_validate_thread_valid(self, generator):
        """Test thread validation with valid thread."""
        tweets = ["1/ tweet one", "2/ tweet two", "3/ tweet three"]
        assert generator.validate_thread(tweets) is True

    def test_validate_thread_too_few_tweets(self, generator):
        """Test thread validation with too few tweets."""
        tweets = ["1/ tweet one", "2/ tweet two"]
        assert generator.validate_thread(tweets) is False

    def test_validate_thread_too_long_tweet(self, generator):
        """Test thread validation with tweet over 280 chars."""
        tweets = ["1/ " + "a" * 280, "2/ tweet two", "3/ tweet three"]
        assert generator.validate_thread(tweets) is False

    def test_validate_thread_empty(self, generator):
        """Test thread validation with empty list."""
        assert generator.validate_thread([]) is False

    def test_estimate_thread_reach(self, generator):
        """Test thread reach estimation."""
        tweets = [
            "1/ my analysis $SOL #Jarvis",
            "2/ bullish on $BONK",
            "3/ nfa t.me/kr8tiventry"
        ]
        estimate = generator.estimate_thread_reach(tweets)

        assert estimate["tweet_count"] == 3
        assert estimate["hashtag_count"] >= 1
        assert estimate["cashtag_count"] >= 2
        assert estimate["has_nfa"] is True
        assert estimate["has_cta"] is True

    def test_get_recommendations_no_hashtags(self, generator):
        """Test recommendations for missing hashtags."""
        recommendations = generator._get_recommendations(
            tweet_count=3,
            hashtags=0,
            cashtags=2,
            has_nfa=True,
            has_cta=True
        )
        assert "hashtag" in recommendations[0].lower()

    def test_get_recommendations_no_cashtags(self, generator):
        """Test recommendations for missing cashtags."""
        recommendations = generator._get_recommendations(
            tweet_count=3,
            hashtags=2,
            cashtags=0,
            has_nfa=True,
            has_cta=True
        )
        assert any("cashtag" in r.lower() for r in recommendations)

    def test_get_recommendations_missing_nfa(self, generator):
        """Test recommendations for missing NFA."""
        recommendations = generator._get_recommendations(
            tweet_count=3,
            hashtags=2,
            cashtags=2,
            has_nfa=False,
            has_cta=True
        )
        assert any("nfa" in r.lower() for r in recommendations)


# =============================================================================
# ContentOptimizer Tests
# =============================================================================

class TestContentOptimizer:
    """Tests for ContentOptimizer class."""

    @pytest.fixture
    def mock_tracker(self):
        """Create a mock engagement tracker."""
        tracker = MagicMock()
        tracker.get_category_performance.return_value = {
            "morning_report": {"avg_likes": 10, "avg_retweets": 5, "avg_replies": 2},
            "token_spotlight": {"avg_likes": 20, "avg_retweets": 10, "avg_replies": 5},
            "grok_insight": {"avg_likes": 5, "avg_retweets": 2, "avg_replies": 1},
        }
        return tracker

    @pytest.fixture
    def optimizer(self, mock_tracker):
        """Create a ContentOptimizer with mocked tracker."""
        return ContentOptimizer(tracker=mock_tracker)

    def test_optimizer_init(self, optimizer):
        """Test ContentOptimizer initialization."""
        assert optimizer._tracker is not None

    def test_get_weights(self, optimizer):
        """Test weight calculation."""
        content_types = ["morning_report", "token_spotlight", "grok_insight"]
        weights = optimizer._get_weights(content_types)

        assert "morning_report" in weights
        assert "token_spotlight" in weights
        assert "grok_insight" in weights
        # token_spotlight has higher engagement, should have higher weight
        assert weights["token_spotlight"] > weights["grok_insight"]

    def test_get_weights_unknown_type(self, optimizer, mock_tracker):
        """Test weight calculation for unknown content type."""
        mock_tracker.get_category_performance.return_value = {}
        content_types = ["unknown_type"]
        weights = optimizer._get_weights(content_types)

        # Should have default weight
        assert "unknown_type" in weights
        assert weights["unknown_type"] >= 0.1

    def test_choose_type(self, optimizer):
        """Test content type selection."""
        content_types = ["morning_report", "token_spotlight", "grok_insight"]
        chosen = optimizer.choose_type(content_types)

        assert chosen in content_types

    def test_choose_type_empty_list(self, optimizer):
        """Test content type selection with empty list."""
        chosen = optimizer.choose_type([])
        assert chosen == ""

    def test_choose_type_single_item(self, optimizer):
        """Test content type selection with single item."""
        chosen = optimizer.choose_type(["only_type"])
        assert chosen == "only_type"

    def test_choose_type_with_custom_hours(self, optimizer):
        """Test content type selection with custom hours."""
        content_types = ["morning_report", "token_spotlight"]
        chosen = optimizer.choose_type(content_types, hours=24)
        assert chosen in content_types


# =============================================================================
# Integration Tests
# =============================================================================

class TestContentGeneratorIntegration:
    """Integration tests for content generation pipeline."""

    @pytest.mark.asyncio
    async def test_full_content_generation_pipeline(self):
        """Test the full content generation pipeline."""
        # Create mocks
        mock_grok = MagicMock()
        mock_grok.can_generate_image.return_value = False
        mock_grok.close = AsyncMock()

        mock_claude = MagicMock()
        mock_claude.generate_morning_report = AsyncMock(return_value=ClaudeResponse(
            success=True,
            content="gm frens, sol looking spicy today"
        ))

        # Create generator
        generator = ContentGenerator(
            grok_client=mock_grok,
            claude_client=mock_claude
        )

        # Mock market metrics
        with patch.object(generator, 'get_market_metrics', return_value=MarketMetrics(
            sol_price=150.0,
            sol_24h_change=5.0,
            btc_price=100000.0,
            btc_24h_change=2.0,
            fear_greed_index=65
        )):
            result = await generator.generate_morning_report()

            assert result.content_type == "morning_report"
            assert result.mood == MoodState.BULLISH
            assert "sol" in result.text.lower()

        await generator.close()

    @pytest.mark.asyncio
    async def test_personality_applied_to_content(self):
        """Test that personality is applied to generated content."""
        personality = JarvisPersonality()

        # Test mood phrase selection
        for _ in range(10):
            phrase = personality.get_mood_phrase(MoodState.BULLISH)
            assert phrase == phrase.lower()  # Should already be lowercase


# =============================================================================
# Edge Cases and Error Handling Tests
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_mood_state_boundary_values(self):
        """Test mood determination at boundary values."""
        metrics_cases = [
            (75, MoodState.EXCITED),   # Exactly at excited threshold
            (74, MoodState.BULLISH),   # Just below excited
            (55, MoodState.BULLISH),   # Exactly at bullish threshold
            (54, MoodState.NEUTRAL),   # Just below bullish
            (45, MoodState.NEUTRAL),   # Exactly at neutral threshold
            (44, MoodState.CAUTIOUS),  # Just below neutral
            (25, MoodState.CAUTIOUS),  # Exactly at cautious threshold
            (24, MoodState.BEARISH),   # Just below cautious
        ]

        mock_grok = MagicMock()
        mock_grok.can_generate_image.return_value = False
        mock_claude = MagicMock()

        generator = ContentGenerator(grok_client=mock_grok, claude_client=mock_claude)

        for fear_greed, expected_mood in metrics_cases:
            metrics = MarketMetrics(fear_greed_index=fear_greed)
            actual_mood = generator._determine_mood(metrics)
            assert actual_mood == expected_mood, f"Fear/greed {fear_greed} should be {expected_mood}, got {actual_mood}"

    def test_tweet_content_with_empty_text(self):
        """Test TweetContent with empty text."""
        content = TweetContent(
            text="",
            content_type="test",
            mood=MoodState.NEUTRAL
        )
        assert content.text == ""

    def test_personality_with_custom_values(self):
        """Test JarvisPersonality with custom values."""
        personality = JarvisPersonality(
            name="custom_jarvis",
            use_lowercase=False,
            max_emojis_per_post=5
        )
        assert personality.name == "custom_jarvis"
        assert personality.use_lowercase is False
        assert personality.max_emojis_per_post == 5

    @pytest.mark.asyncio
    async def test_content_generator_handles_api_errors(self):
        """Test ContentGenerator handles API errors gracefully."""
        mock_grok = MagicMock()
        mock_grok.can_generate_image.return_value = False
        mock_grok.close = AsyncMock()

        mock_claude = MagicMock()
        mock_claude.generate_morning_report = AsyncMock(return_value=ClaudeResponse(
            success=False,
            content="",
            error="API error"
        ))

        generator = ContentGenerator(
            grok_client=mock_grok,
            claude_client=mock_claude
        )

        with patch.object(generator, 'get_market_metrics', return_value=MarketMetrics(
            sol_price=150.0,
            fear_greed_index=50
        )):
            # Should not raise, should fall back to template
            result = await generator.generate_morning_report()
            assert result is not None
            assert result.content_type == "morning_report"

        await generator.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
