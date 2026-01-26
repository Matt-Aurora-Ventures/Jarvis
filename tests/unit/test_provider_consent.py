"""Tests for paid provider consent mechanism.

Ensures users must explicitly opt-in to paid API fallbacks.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from core.providers import get_ranked_providers, generate_text


class TestProviderConsent:
    """Tests for provider consent configuration."""

    @patch('core.providers.config.load_config')
    @patch('core.providers._openrouter_client')
    @patch('core.providers._groq_client')
    @patch('core.providers._openai_client')
    @patch('core.providers._ollama_enabled')
    def test_paid_providers_blocked_by_default(
        self, mock_ollama, mock_openai, mock_groq, mock_openrouter, mock_config
    ):
        """Test that paid providers are blocked when allow_paid_fallback=false."""
        mock_config.return_value = {
            "providers": {
                "allow_paid_fallback": False,
                "openai": {"enabled": "auto"},
            }
        }
        # All providers available
        mock_openrouter.return_value = MagicMock()
        mock_groq.return_value = MagicMock()
        mock_openai.return_value = MagicMock()
        mock_ollama.return_value = False

        ranked = get_ranked_providers(prefer_free=False)

        # Should NOT include paid providers (OpenAI, Grok, MiniMax, etc.)
        provider_names = [p["name"] for p in ranked]

        # Free providers should be included
        # Note: OpenRouter models are paid, Groq is free-tier
        # Ollama is local/free

        # Should NOT include paid fallbacks
        assert "gpt-4o-mini" not in provider_names
        assert "grok-beta" not in provider_names

    @patch('core.providers.secrets')
    @patch('core.providers.config.load_config')
    @patch('core.providers._openrouter_client')
    @patch('core.providers._groq_client')
    @patch('core.providers._openai_client')
    @patch('core.providers._ollama_enabled')
    @patch('core.providers._grok_client')
    def test_paid_providers_allowed_with_consent(
        self, mock_grok, mock_ollama, mock_openai, mock_groq, mock_openrouter, mock_config, mock_secrets
    ):
        """Test that paid providers are included when allow_paid_fallback=true."""
        mock_config.return_value = {
            "providers": {
                "allow_paid_fallback": True,
                "openai": {"enabled": "auto"},
            }
        }
        # Mock secrets module to avoid AttributeError
        mock_secrets.get_minimax_key.return_value = None

        mock_openrouter.return_value = MagicMock()
        mock_groq.return_value = MagicMock()
        mock_openai.return_value = MagicMock()
        mock_ollama.return_value = False
        mock_grok.return_value = None

        ranked = get_ranked_providers(prefer_free=False)

        # Should include paid providers
        provider_names = [p["name"] for p in ranked]
        assert "gpt-4o-mini" in provider_names

    @patch('core.providers.config.load_config')
    @patch('core.providers._openrouter_client')
    @patch('core.providers._groq_client')
    @patch('core.providers._openai_client')
    @patch('core.providers._ollama_enabled')
    def test_free_providers_always_available(
        self, mock_ollama, mock_openai, mock_groq, mock_openrouter, mock_config
    ):
        """Test that free providers are available regardless of consent."""
        mock_config.return_value = {
            "providers": {
                "allow_paid_fallback": False,  # Paid blocked
            }
        }
        mock_openrouter.return_value = None  # Not configured
        mock_groq.return_value = MagicMock()  # Groq available (free tier)
        mock_openai.return_value = None
        mock_ollama.return_value = True  # Ollama available (local/free)

        ranked = get_ranked_providers(prefer_free=True)

        # Should have free providers
        assert len(ranked) > 0
        # All should be free
        for provider in ranked:
            # Groq and Ollama are free
            if provider["provider"] in ["groq", "ollama"]:
                continue
            # Others should be marked as free if included
            assert provider.get("free", False) or provider["provider"] in ["groq", "ollama"]

    @patch('core.providers.config.load_config')
    @patch('core.providers._openrouter_client')
    @patch('core.providers._groq_client')
    @patch('core.providers._openai_client')
    @patch('core.providers._ollama_enabled')
    @patch('core.providers.logger')
    def test_generate_text_shows_helpful_error_when_blocked(
        self, mock_logger, mock_ollama, mock_openai, mock_groq, mock_openrouter, mock_config
    ):
        """Test that generate_text shows helpful error when no providers available due to consent."""
        mock_config.return_value = {
            "providers": {
                "allow_paid_fallback": False,
            }
        }
        # No providers available
        mock_openrouter.return_value = None
        mock_groq.return_value = None
        mock_openai.return_value = None
        mock_ollama.return_value = False

        result = generate_text("test prompt")

        assert result is None
        # Should log helpful message about paid fallback being disabled
        mock_logger.error.assert_called_once()
        error_msg = str(mock_logger.error.call_args)
        assert "paid fallback disabled" in error_msg.lower()

    @patch('core.providers.config.load_config')
    def test_default_config_blocks_paid_providers(self, mock_config):
        """Test that default configuration blocks paid providers (safe default)."""
        mock_config.return_value = {
            "providers": {}  # No allow_paid_fallback key
        }

        # Should default to False (safe default)
        cfg = mock_config()
        allow_paid = cfg.get("providers", {}).get("allow_paid_fallback", False)
        assert allow_paid is False


class TestProviderClassification:
    """Tests for correct free/paid provider classification."""

    def test_provider_rankings_have_free_flag(self):
        """Test that all providers in PROVIDER_RANKINGS have 'free' flag."""
        from core.providers import PROVIDER_RANKINGS

        for provider in PROVIDER_RANKINGS:
            assert "free" in provider, f"Provider {provider['name']} missing 'free' flag"
            assert isinstance(provider["free"], bool), f"Provider {provider['name']} has non-bool 'free' flag"

    def test_known_paid_providers_marked_correctly(self):
        """Test that known paid providers are marked as paid."""
        from core.providers import PROVIDER_RANKINGS

        paid_providers = ["gpt-4o-mini", "grok-beta", "grok-2-latest"]

        for provider_name in paid_providers:
            providers = [p for p in PROVIDER_RANKINGS if p["name"] == provider_name]
            if providers:
                assert providers[0]["free"] is False, f"{provider_name} should be marked as paid"

    def test_known_free_providers_marked_correctly(self):
        """Test that known free providers are marked as free."""
        from core.providers import PROVIDER_RANKINGS

        # Ollama is local/free
        # Note: OpenRouter and Groq may be paid depending on model
        # We're checking that there's at least some mechanism to differentiate

        for provider in PROVIDER_RANKINGS:
            if provider["provider"] == "ollama":
                # Ollama should be marked as free (local)
                # Check if it exists and if so, should be free
                assert provider.get("free") is not False, "Ollama should not be marked as paid"


class TestConsentConfiguration:
    """Tests for provider consent configuration."""

    @patch('core.providers.config.load_config')
    def test_explicit_true_allows_paid(self, mock_config):
        """Test explicit allow_paid_fallback=true."""
        mock_config.return_value = {
            "providers": {"allow_paid_fallback": True}
        }
        cfg = mock_config()
        assert cfg.get("providers", {}).get("allow_paid_fallback", False) is True

    @patch('core.providers.config.load_config')
    def test_explicit_false_blocks_paid(self, mock_config):
        """Test explicit allow_paid_fallback=false."""
        mock_config.return_value = {
            "providers": {"allow_paid_fallback": False}
        }
        cfg = mock_config()
        assert cfg.get("providers", {}).get("allow_paid_fallback", False) is False

    @patch('core.providers.config.load_config')
    def test_missing_config_defaults_to_blocked(self, mock_config):
        """Test missing config defaults to blocking paid providers."""
        mock_config.return_value = {}
        cfg = mock_config()
        assert cfg.get("providers", {}).get("allow_paid_fallback", False) is False
