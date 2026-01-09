"""
Tests for core/providers.py

Tests cover:
- Provider status checking
- Retry delay calculation
- Gemini text extraction
- Ollama configuration
- Model name resolution
- Provider attempt tracking
- Error handling
"""

import sys
import time
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from dataclasses import asdict

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.providers import (
    _retry_delay_seconds,
    _retryable_gemini_error,
    _extract_gemini_text,
    _gemini_model_name,
    _openai_model_name,
    _ollama_model_name,
    _ollama_base_url,
    _ollama_enabled,
    _safe_error_message,
    ProviderAttempt,
    last_generation_attempts,
    last_provider_errors,
    provider_status,
)


class TestRetryDelaySeconds:
    """Test retry delay calculation."""

    def test_extracts_delay_from_message(self):
        """Should extract delay from 'retry in X s' message."""
        exc = Exception("Rate limited. Please retry in 5.5s")
        delay = _retry_delay_seconds(exc, attempt=0)
        assert delay == 5.5

    def test_caps_delay_at_30_seconds(self):
        """Should cap delay at 30 seconds."""
        exc = Exception("retry in 60s please")
        delay = _retry_delay_seconds(exc, attempt=0)
        assert delay == 30.0

    def test_minimum_delay(self):
        """Should have minimum delay of 0.1s."""
        exc = Exception("retry in 0.01s")
        delay = _retry_delay_seconds(exc, attempt=0)
        assert delay >= 0.1

    def test_exponential_backoff_without_message(self):
        """Should use exponential backoff when no retry message."""
        exc = Exception("Some error without retry info")
        delay_0 = _retry_delay_seconds(exc, attempt=0)
        delay_1 = _retry_delay_seconds(exc, attempt=1)
        delay_2 = _retry_delay_seconds(exc, attempt=2)

        assert delay_0 == 2.0  # 2 * 2^0 = 2
        assert delay_1 == 4.0  # 2 * 2^1 = 4
        assert delay_2 == 8.0  # 2 * 2^2 = 8

    def test_backoff_caps_at_8_seconds(self):
        """Backoff should cap at 8 seconds."""
        exc = Exception("No retry info")
        delay = _retry_delay_seconds(exc, attempt=10)
        assert delay == 8.0


class TestRetryableGeminiError:
    """Test Gemini error retry logic."""

    def test_quota_exceeded_is_retryable(self):
        """Quota exceeded should be retryable."""
        exc = Exception("Quota exceeded for this API")
        assert _retryable_gemini_error(exc)

    def test_429_is_retryable(self):
        """429 status should be retryable."""
        exc = Exception("Error 429: Too many requests")
        assert _retryable_gemini_error(exc)

    def test_rate_limit_is_retryable(self):
        """Rate limit message should be retryable."""
        exc = Exception("Rate limit reached")
        assert _retryable_gemini_error(exc)

    def test_empty_response_is_retryable(self):
        """Empty Gemini response should be retryable."""
        exc = RuntimeError("Empty Gemini response received")
        assert _retryable_gemini_error(exc)

    def test_regular_error_not_retryable(self):
        """Regular errors should not be retryable."""
        exc = Exception("Invalid API key")
        assert not _retryable_gemini_error(exc)

    def test_value_error_not_retryable(self):
        """Value errors should not be retryable."""
        exc = ValueError("Invalid input")
        assert not _retryable_gemini_error(exc)


class TestExtractGeminiText:
    """Test Gemini response text extraction."""

    def test_extracts_from_text_attribute(self):
        """Should extract text from .text attribute."""
        mock_response = Mock()
        mock_response.text = "Hello, world!"
        result = _extract_gemini_text(mock_response)
        assert result == "Hello, world!"

    def test_extracts_from_candidates(self):
        """Should extract text from candidates when .text fails."""
        mock_response = Mock()
        mock_response.text = None

        mock_part = Mock()
        mock_part.text = "Response from candidate"

        mock_content = Mock()
        mock_content.parts = [mock_part]

        mock_candidate = Mock()
        mock_candidate.content = mock_content

        mock_response.candidates = [mock_candidate]

        result = _extract_gemini_text(mock_response)
        assert result == "Response from candidate"

    def test_returns_empty_on_failure(self):
        """Should return empty string on extraction failure."""
        mock_response = Mock()
        mock_response.text = None
        mock_response.candidates = None

        result = _extract_gemini_text(mock_response)
        assert result == ""

    def test_handles_whitespace_only_text(self):
        """Should handle whitespace-only text."""
        mock_response = Mock()
        mock_response.text = "   \n\t   "
        mock_response.candidates = []

        result = _extract_gemini_text(mock_response)
        assert result == ""


class TestModelNameResolution:
    """Test model name resolution functions."""

    def test_gemini_model_default(self):
        """Should return default Gemini model."""
        cfg = {}
        model = _gemini_model_name(cfg)
        assert "gemini" in model.lower()

    def test_gemini_model_from_config(self):
        """Should read Gemini model from config."""
        cfg = {"providers": {"gemini": {"model": "gemini-2.5-pro"}}}
        model = _gemini_model_name(cfg)
        assert model == "gemini-2.5-pro"

    def test_gemini_strips_models_prefix(self):
        """Should strip 'models/' prefix from model name."""
        cfg = {"providers": {"gemini": {"model": "models/gemini-2.0-flash"}}}
        model = _gemini_model_name(cfg)
        assert not model.startswith("models/")

    def test_gemini_model_aliases(self):
        """Should resolve model aliases."""
        cfg = {"providers": {"gemini": {"model": "gemini-1.5-flash"}}}
        model = _gemini_model_name(cfg)
        assert model == "gemini-2.5-flash"  # Redirected

    def test_openai_model_default(self):
        """Should return default OpenAI model."""
        cfg = {}
        model = _openai_model_name(cfg)
        assert model == "gpt-4o-mini"

    def test_openai_model_from_config(self):
        """Should read OpenAI model from config."""
        cfg = {"providers": {"openai": {"model": "gpt-4-turbo"}}}
        model = _openai_model_name(cfg)
        assert model == "gpt-4-turbo"

    def test_ollama_model_default(self):
        """Should return default Ollama model."""
        cfg = {}
        model = _ollama_model_name(cfg)
        assert "llama" in model.lower() or "qwen" in model.lower() or "3b" in model or "3.2" in model

    def test_ollama_model_from_config(self):
        """Should read Ollama model from config."""
        cfg = {"providers": {"ollama": {"model": "mistral:7b"}}}
        model = _ollama_model_name(cfg)
        assert model == "mistral:7b"


class TestOllamaConfiguration:
    """Test Ollama configuration functions."""

    def test_ollama_base_url_default(self):
        """Should return default Ollama URL."""
        cfg = {}
        url = _ollama_base_url(cfg)
        assert url == "http://localhost:11434"

    def test_ollama_base_url_from_config(self):
        """Should read Ollama URL from config."""
        cfg = {"providers": {"ollama": {"base_url": "http://192.168.1.100:11434"}}}
        url = _ollama_base_url(cfg)
        assert url == "http://192.168.1.100:11434"

    def test_ollama_base_url_strips_trailing_slash(self):
        """Should strip trailing slash from URL."""
        cfg = {"providers": {"ollama": {"base_url": "http://localhost:11434/"}}}
        url = _ollama_base_url(cfg)
        assert not url.endswith("/")

    def test_ollama_enabled_default(self):
        """Should be enabled by default."""
        cfg = {}
        assert _ollama_enabled(cfg)

    def test_ollama_enabled_from_config(self):
        """Should read enabled status from config."""
        cfg = {"providers": {"ollama": {"enabled": False}}}
        assert not _ollama_enabled(cfg)

    def test_ollama_enabled_true(self):
        """Should handle explicit True."""
        cfg = {"providers": {"ollama": {"enabled": True}}}
        assert _ollama_enabled(cfg)


class TestSafeErrorMessage:
    """Test error message sanitization."""

    def test_short_message_unchanged(self):
        """Short messages should be unchanged."""
        exc = Exception("Short error")
        msg = _safe_error_message(exc)
        assert msg == "Short error"

    def test_long_message_truncated(self):
        """Long messages should be truncated."""
        long_msg = "x" * 500
        exc = Exception(long_msg)
        msg = _safe_error_message(exc, limit=100)
        assert len(msg) <= 100
        assert msg.endswith("...")

    def test_newlines_replaced(self):
        """Newlines should be replaced with spaces."""
        exc = Exception("Line 1\nLine 2\nLine 3")
        msg = _safe_error_message(exc)
        assert "\n" not in msg
        assert "Line 1 Line 2 Line 3" == msg

    def test_empty_message_returns_class_name(self):
        """Empty message should return exception class name."""
        exc = Exception("")
        msg = _safe_error_message(exc)
        assert msg == "Exception"


class TestProviderAttempt:
    """Test ProviderAttempt dataclass."""

    def test_create_attempt(self):
        """Should create attempt with all fields."""
        attempt = ProviderAttempt(
            provider="groq-llama-70b",
            provider_type="groq",
            success=True,
            error="",
            latency_ms=150,
            timestamp=time.time(),
            metadata={"model": "llama-3.3-70b"},
        )
        assert attempt.provider == "groq-llama-70b"
        assert attempt.success
        assert attempt.latency_ms == 150

    def test_attempt_to_dict(self):
        """Should convert to dict."""
        attempt = ProviderAttempt(
            provider="test",
            provider_type="test",
            success=False,
            error="Test error",
            latency_ms=0,
            timestamp=0.0,
            metadata={},
        )
        d = asdict(attempt)
        assert isinstance(d, dict)
        assert d["provider"] == "test"
        assert d["error"] == "Test error"


class TestProviderStatus:
    """Test provider status functions."""

    def test_last_provider_errors_returns_dict(self):
        """Should return dict of provider errors."""
        errors = last_provider_errors()
        assert isinstance(errors, dict)
        # Should have keys for major providers
        expected_keys = {"openrouter", "gemini", "ollama", "groq", "openai"}
        assert expected_keys.issubset(set(errors.keys()))

    def test_last_generation_attempts_returns_list(self):
        """Should return list of attempts."""
        attempts = last_generation_attempts(limit=5)
        assert isinstance(attempts, list)

    @patch('core.providers.secrets')
    @patch('core.providers.config')
    def test_provider_status_structure(self, mock_config, mock_secrets):
        """Should return status dict with expected keys."""
        mock_config.load_config.return_value = {}
        mock_secrets.get_gemini_key.return_value = ""
        mock_secrets.get_openai_key.return_value = ""
        mock_secrets.get_groq_key.return_value = ""
        mock_secrets.get_minimax_key.return_value = ""

        status = provider_status()
        assert isinstance(status, dict)
        # Check for expected keys
        expected_keys = [
            "ollama_available",
            "gemini_available",
            "openai_available",
        ]
        for key in expected_keys:
            assert key in status


class TestIntegration:
    """Integration tests for provider module."""

    def test_provider_chain_concept(self):
        """Test that provider chain concept works."""
        # This tests the concept without making real API calls
        attempts = []

        # Simulate attempting multiple providers
        providers = ["groq", "ollama", "gemini", "openai"]
        for i, provider in enumerate(providers):
            attempt = ProviderAttempt(
                provider=f"{provider}-model",
                provider_type=provider,
                success=(i == 1),  # Only ollama succeeds
                error="" if i == 1 else "Connection failed",
                latency_ms=100 * (i + 1),
                timestamp=time.time(),
                metadata={},
            )
            attempts.append(attempt)
            if attempt.success:
                break

        # Verify chain behavior
        assert len(attempts) == 2  # Stopped after ollama succeeded
        assert attempts[-1].success
        assert attempts[-1].provider_type == "ollama"

    def test_error_accumulation(self):
        """Test that errors are properly tracked."""
        errors = last_provider_errors()
        # All values should be strings (possibly empty)
        for key, value in errors.items():
            assert isinstance(value, str)
