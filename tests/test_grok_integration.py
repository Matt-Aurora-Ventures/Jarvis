#!/usr/bin/env python3
"""
Test Grok (X.AI) integration and sentiment analysis.
"""

import unittest
import sys
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core import providers, secrets, config
from core import x_sentiment


class TestGrokIntegration(unittest.TestCase):
    """Test Grok provider integration."""

    def test_grok_key_function_exists(self):
        """Test that get_grok_key function exists in secrets."""
        self.assertTrue(hasattr(secrets, 'get_grok_key'))

    def test_grok_config_exists(self):
        """Test that Grok is in config."""
        cfg = config.load_config()
        providers_cfg = cfg.get("providers", {})
        self.assertIn("grok", providers_cfg)
        grok_cfg = providers_cfg["grok"]
        self.assertIn("model", grok_cfg)
        self.assertIn("enabled", grok_cfg)

    def test_grok_client_function_exists(self):
        """Test that _grok_client function exists in providers."""
        self.assertTrue(hasattr(providers, '_grok_client'))

    def test_grok_ask_function_exists(self):
        """Test that _ask_grok function exists in providers."""
        self.assertTrue(hasattr(providers, '_ask_grok'))

    def test_grok_in_provider_rankings(self):
        """Test that Grok is in PROVIDER_RANKINGS."""
        grok_providers = [p for p in providers.PROVIDER_RANKINGS if p["provider"] == "grok"]
        self.assertGreater(len(grok_providers), 0, "Grok should be in PROVIDER_RANKINGS")

    def test_grok_in_health_check(self):
        """Test that Grok appears in provider health check."""
        health = providers.check_provider_health()
        self.assertIn("grok", health)

    def test_sentiment_module_imports(self):
        """Test that x_sentiment module imports successfully."""
        self.assertTrue(hasattr(x_sentiment, 'analyze_sentiment'))
        self.assertTrue(hasattr(x_sentiment, 'analyze_trend'))
        self.assertTrue(hasattr(x_sentiment, 'analyze_crypto_sentiment'))

    def test_grok_availability_check(self):
        """Test Grok availability check (will be False without API key)."""
        # This should not raise an error
        available = x_sentiment._is_grok_available()
        self.assertIsInstance(available, bool)


class TestGrokSentiment(unittest.TestCase):
    """Test Grok sentiment analysis (requires API key)."""

    def test_sentiment_analysis_without_key(self):
        """Test sentiment analysis gracefully handles missing API key."""
        # Should return None if Grok is not configured
        result = x_sentiment.analyze_sentiment("Test tweet about crypto")
        # Either None (no key) or SentimentResult (key configured)
        self.assertTrue(result is None or hasattr(result, 'sentiment'))

    def test_trend_analysis_without_key(self):
        """Test trend analysis gracefully handles missing API key."""
        result = x_sentiment.analyze_trend("Bitcoin")
        # Either None (no key) or TrendAnalysis (key configured)
        self.assertTrue(result is None or hasattr(result, 'sentiment'))

    def test_crypto_sentiment_without_key(self):
        """Test crypto sentiment gracefully handles missing API key."""
        result = x_sentiment.analyze_crypto_sentiment("BTC")
        # Either None (no key) or dict (key configured)
        self.assertTrue(result is None or isinstance(result, dict))

    def test_sentiment_summary_empty(self):
        """Test sentiment summary with empty results."""
        summary = x_sentiment.get_sentiment_summary([])
        self.assertEqual(summary["total"], 0)
        self.assertEqual(summary["positive"], 0)
        self.assertEqual(summary["avg_confidence"], 0.0)


if __name__ == '__main__':
    unittest.main()
