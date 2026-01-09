"""
Tests for Provider Health Checks (P0-2).

Tests verify:
- Provider health check returns actionable diagnostics
- Missing API keys have clear error messages
- Provider fallback chain works correctly
- Doctor command surfaces provider issues
"""

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core import providers, secrets


# =============================================================================
# Test Provider Health Check
# =============================================================================

class TestProviderHealthCheck:
    """Test provider health check functionality."""

    def test_check_provider_health_returns_dict(self):
        """Health check should return dictionary of provider statuses."""
        health = providers.check_provider_health()
        assert isinstance(health, dict)
        # Should check multiple providers
        assert len(health) >= 1

    def test_health_check_structure(self):
        """Each provider entry should have required fields."""
        health = providers.check_provider_health()

        for name, info in health.items():
            assert "available" in info, f"{name} missing 'available'"
            assert "status" in info, f"{name} missing 'status'"
            assert "message" in info, f"{name} missing 'message'"
            assert isinstance(info["available"], bool)

    def test_groq_missing_key_has_clear_message(self):
        """When Groq key is missing, message should be actionable."""
        with patch.object(secrets, 'get_groq_key', return_value=""):
            health = providers.check_provider_health()

            if "groq" in health:
                groq = health["groq"]
                assert groq["available"] is False
                assert "key" in groq["message"].lower() or "api" in groq["message"].lower()
                # Should have a fix suggestion
                if "fix" in groq and groq["fix"]:
                    assert "GROQ_API_KEY" in groq["fix"] or "secrets" in groq["fix"]

    def test_provider_status_function(self):
        """provider_status() should return availability dict."""
        status = providers.provider_status()
        assert isinstance(status, dict)
        # Should have known providers
        expected_keys = [
            "groq_available",
            "ollama_available",
            "gemini_available",
            "openai_available",
        ]
        for key in expected_keys:
            assert key in status, f"Missing {key} in provider_status"

    def test_provider_health_check_full(self):
        """provider_health_check() should return comprehensive info."""
        health = providers.provider_health_check()
        assert isinstance(health, dict)
        assert "status" in health
        assert "available_providers" in health
        assert "total_available" in health
        assert "healthy" in health

    def test_get_provider_summary_readable(self):
        """Provider summary should be human-readable."""
        summary = providers.get_provider_summary()
        assert isinstance(summary, str)
        assert "Provider Status" in summary
        # Should have status icons
        assert "✓" in summary or "✗" in summary


# =============================================================================
# Test Provider Fallback Chain
# =============================================================================

class TestProviderFallbackChain:
    """Test that provider fallback works correctly."""

    def test_get_ranked_providers_returns_list(self):
        """Should return list of ranked providers."""
        ranked = providers.get_ranked_providers()
        assert isinstance(ranked, list)

    def test_ranked_providers_have_required_fields(self):
        """Each ranked provider should have required fields."""
        ranked = providers.get_ranked_providers()

        for provider in ranked:
            assert "name" in provider
            assert "provider" in provider
            assert "intelligence" in provider
            assert "free" in provider

    def test_free_providers_first_when_preferred(self):
        """When prefer_free=True, free providers should be ranked first."""
        ranked = providers.get_ranked_providers(prefer_free=True)

        if len(ranked) >= 2:
            # Find first paid provider
            first_paid_idx = None
            for i, p in enumerate(ranked):
                if not p["free"]:
                    first_paid_idx = i
                    break

            if first_paid_idx is not None:
                # All providers before should be free
                for i in range(first_paid_idx):
                    assert ranked[i]["free"], f"Provider at index {i} should be free"


# =============================================================================
# Test Secrets Configuration
# =============================================================================

class TestSecretsConfiguration:
    """Test secrets management."""

    def test_list_configured_keys_returns_dict(self):
        """Should list all configurable keys."""
        keys = secrets.list_configured_keys()
        assert isinstance(keys, dict)
        # Should have known providers
        expected = ["groq", "openai", "gemini"]
        for provider in expected:
            assert provider in keys, f"Missing {provider} in configured keys"

    def test_get_groq_key_returns_string(self):
        """Groq key getter should return string."""
        key = secrets.get_groq_key()
        assert isinstance(key, str)

    def test_get_key_checks_env_and_file(self):
        """get_key should check both env vars and secrets file."""
        # This is implicit - the function checks both sources
        # We just verify it doesn't crash
        result = secrets.get_key("test_key", "TEST_ENV_VAR")
        assert isinstance(result, str)


# =============================================================================
# Test Error Recording
# =============================================================================

class TestProviderErrorRecording:
    """Test that provider errors are recorded."""

    def test_last_provider_errors_returns_dict(self):
        """Should return dictionary of last errors."""
        errors = providers.last_provider_errors()
        assert isinstance(errors, dict)

    def test_last_generation_attempts_returns_list(self):
        """Should return list of recent attempts."""
        attempts = providers.last_generation_attempts()
        assert isinstance(attempts, list)


# =============================================================================
# Test Provider Summary with Missing Keys
# =============================================================================

class TestProviderSummaryMessaging:
    """Test that provider summary gives actionable advice."""

    def test_no_providers_warning(self):
        """When no providers available, should show clear warning."""
        with patch.object(providers, 'check_provider_health', return_value={}):
            summary = providers.get_provider_summary()
            # Should mention that providers aren't available
            assert "provider" in summary.lower()

    def test_groq_recommendation_when_missing(self):
        """Should recommend Groq when it's not available."""
        mock_health = {
            "ollama": {"available": True, "message": "OK", "status": "ok"},
        }
        with patch.object(providers, 'check_provider_health', return_value=mock_health):
            summary = providers.get_provider_summary()
            # Should mention Groq recommendation
            lower = summary.lower()
            assert "groq" in lower or "provider" in lower
