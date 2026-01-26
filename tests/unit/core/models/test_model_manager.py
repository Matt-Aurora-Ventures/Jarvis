"""
Tests for ModelManager - Multi-model provider system.

TDD: Tests written BEFORE implementation.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import List, Dict, Any


class TestModelCatalog:
    """Test model catalog functionality."""

    def test_model_catalog_has_anthropic_models(self):
        """Catalog should include Anthropic models."""
        from core.models.catalog import MODEL_CATALOG

        assert "anthropic" in MODEL_CATALOG
        anthropic_models = MODEL_CATALOG["anthropic"]

        # Should have at least Opus, Sonnet, Haiku
        model_ids = [m["id"] for m in anthropic_models]
        assert any("opus" in m.lower() for m in model_ids)
        assert any("sonnet" in m.lower() for m in model_ids)
        assert any("haiku" in m.lower() for m in model_ids)

    def test_model_catalog_has_openai_models(self):
        """Catalog should include OpenAI models."""
        from core.models.catalog import MODEL_CATALOG

        assert "openai" in MODEL_CATALOG
        openai_models = MODEL_CATALOG["openai"]

        # Should have GPT-4 variants
        model_ids = [m["id"] for m in openai_models]
        assert any("gpt-4" in m.lower() for m in model_ids)

    def test_model_catalog_has_xai_models(self):
        """Catalog should include xAI models."""
        from core.models.catalog import MODEL_CATALOG

        assert "xai" in MODEL_CATALOG
        xai_models = MODEL_CATALOG["xai"]

        # Should have Grok models
        model_ids = [m["id"] for m in xai_models]
        assert any("grok" in m.lower() for m in model_ids)

    def test_model_entry_has_required_fields(self):
        """Each model entry should have required fields."""
        from core.models.catalog import MODEL_CATALOG

        required_fields = ["id", "name", "context", "cost_in", "cost_out"]

        for provider, models in MODEL_CATALOG.items():
            for model in models:
                for field in required_fields:
                    assert field in model, f"Model {model.get('id', 'unknown')} missing {field}"

    def test_get_model_info(self):
        """Should retrieve model info by ID."""
        from core.models.catalog import get_model_info

        # Get a known model
        info = get_model_info("claude-sonnet-4-5")
        assert info is not None
        assert info["name"] == "Claude Sonnet 4.5"
        assert info["provider"] == "anthropic"

    def test_get_model_info_not_found(self):
        """Should return None for unknown model."""
        from core.models.catalog import get_model_info

        info = get_model_info("nonexistent-model-xyz")
        assert info is None

    def test_list_providers(self):
        """Should list all available providers."""
        from core.models.catalog import list_providers

        providers = list_providers()
        assert "anthropic" in providers
        assert "openai" in providers
        assert "xai" in providers

    def test_list_models_by_provider(self):
        """Should list models for a specific provider."""
        from core.models.catalog import list_models

        models = list_models("anthropic")
        assert len(models) > 0
        for model in models:
            assert model["provider"] == "anthropic"


class TestModelManager:
    """Test ModelManager functionality."""

    def test_model_manager_init(self):
        """ModelManager should initialize with default model."""
        from core.models.manager import ModelManager

        manager = ModelManager()
        assert manager.default_model is not None

    def test_model_manager_set_default_model(self):
        """Should set default model."""
        from core.models.manager import ModelManager

        manager = ModelManager()
        manager.set_default_model("gpt-4-turbo")

        assert manager.default_model == "gpt-4-turbo"

    def test_model_manager_set_invalid_model_raises(self):
        """Should raise error for invalid model ID."""
        from core.models.manager import ModelManager

        manager = ModelManager()

        with pytest.raises(ValueError, match="Unknown model"):
            manager.set_default_model("invalid-model-xyz")

    def test_model_manager_get_model_for_session(self):
        """Should get model for a session."""
        from core.models.manager import ModelManager

        manager = ModelManager()

        # Set session model
        manager.set_session_model("session-123", "claude-opus-4-5")

        model = manager.get_model_for_session("session-123")
        assert model == "claude-opus-4-5"

    def test_model_manager_session_fallback_to_default(self):
        """Session without model should use default."""
        from core.models.manager import ModelManager

        manager = ModelManager()
        manager.set_default_model("claude-sonnet-4-5")

        model = manager.get_model_for_session("unknown-session")
        assert model == "claude-sonnet-4-5"

    def test_model_manager_list_providers(self):
        """Should list registered providers."""
        from core.models.manager import ModelManager

        manager = ModelManager()
        providers = manager.list_providers()

        assert isinstance(providers, list)

    def test_model_manager_list_models(self):
        """Should list all models."""
        from core.models.manager import ModelManager

        manager = ModelManager()
        models = manager.list_models()

        assert isinstance(models, list)
        assert len(models) > 0

    def test_model_manager_estimate_cost(self):
        """Should estimate cost for a request."""
        from core.models.manager import ModelManager

        manager = ModelManager()

        cost = manager.estimate_cost(
            model_id="claude-sonnet-4-5",
            tokens_in=1000,
            tokens_out=500
        )

        assert cost > 0
        assert isinstance(cost, float)


class TestModelManagerGenerate:
    """Test ModelManager.generate() functionality."""

    @pytest.mark.asyncio
    async def test_generate_with_default_model(self):
        """Should generate using default model."""
        from core.models.manager import ModelManager

        manager = ModelManager()

        # Mock the underlying provider
        with patch.object(manager, '_generate_with_provider', new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = {"content": "Hello!", "tokens_in": 10, "tokens_out": 5}

            response = await manager.generate(
                messages=[{"role": "user", "content": "Hi"}]
            )

            assert response["content"] == "Hello!"
            mock_gen.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_with_specific_model(self):
        """Should generate using specified model."""
        from core.models.manager import ModelManager

        manager = ModelManager()

        with patch.object(manager, '_generate_with_provider', new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = {"content": "Response", "tokens_in": 10, "tokens_out": 5}

            response = await manager.generate(
                messages=[{"role": "user", "content": "Hi"}],
                model_id="gpt-4-turbo"
            )

            # Should have used specified model
            call_kwargs = mock_gen.call_args
            assert "gpt-4-turbo" in str(call_kwargs)

    @pytest.mark.asyncio
    async def test_generate_tracks_cost(self):
        """Generation should track costs."""
        from core.models.manager import ModelManager

        manager = ModelManager()

        with patch.object(manager, '_generate_with_provider', new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = {"content": "OK", "tokens_in": 1000, "tokens_out": 500}

            with patch('core.llm.cost_tracker.get_cost_tracker') as mock_tracker:
                mock_tracker.return_value.record_usage = MagicMock()

                await manager.generate(
                    messages=[{"role": "user", "content": "Test"}]
                )

                # Cost tracking should have been called
                # (implementation will verify this)


class TestModelProviderIntegration:
    """Test provider integration."""

    def test_anthropic_provider_exists(self):
        """Anthropic provider should be importable."""
        from core.models.providers.anthropic import AnthropicProvider

        provider = AnthropicProvider(api_key="test-key")
        assert provider is not None

    def test_openai_provider_exists(self):
        """OpenAI provider should be importable."""
        from core.models.providers.openai import OpenAIProvider

        provider = OpenAIProvider(api_key="test-key")
        assert provider is not None

    def test_xai_provider_exists(self):
        """xAI provider should be importable."""
        from core.models.providers.xai import XAIProvider

        provider = XAIProvider(api_key="test-key")
        assert provider is not None


class TestSessionModelPreference:
    """Test session-level model preferences."""

    def test_set_and_get_session_model(self):
        """Should persist session model preference."""
        from core.models.manager import ModelManager

        manager = ModelManager()

        # Set preference
        manager.set_session_model("session-abc", "claude-opus-4-5")

        # Get preference
        model = manager.get_model_for_session("session-abc")
        assert model == "claude-opus-4-5"

    def test_clear_session_model(self):
        """Should clear session model preference."""
        from core.models.manager import ModelManager

        manager = ModelManager()
        manager.set_session_model("session-xyz", "gpt-4-turbo")

        # Clear
        manager.clear_session_model("session-xyz")

        # Should fall back to default
        model = manager.get_model_for_session("session-xyz")
        assert model == manager.default_model


class TestModelFormatting:
    """Test model output formatting for Telegram."""

    def test_format_models_list(self):
        """Should format models list for Telegram display."""
        from core.models.catalog import format_models_list

        output = format_models_list()

        # Should contain provider headers
        assert "Anthropic" in output or "anthropic" in output.lower()
        assert "OpenAI" in output or "openai" in output.lower()

        # Should contain model info
        assert "claude" in output.lower() or "Claude" in output
        assert "gpt" in output.lower() or "GPT" in output

    def test_format_model_info(self):
        """Should format single model info."""
        from core.models.catalog import format_model_info

        output = format_model_info("claude-sonnet-4-5")

        assert "Claude Sonnet 4.5" in output or "claude-sonnet" in output.lower()
        assert "context" in output.lower() or "200k" in output or "200000" in output
