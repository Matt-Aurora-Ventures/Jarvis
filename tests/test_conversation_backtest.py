#!/usr/bin/env python3
"""
Tests for the conversation backtesting harness.
"""

import json
import unittest
from pathlib import Path
from unittest.mock import patch

from core import conversation_backtest

FIXTURE_PATH = (
    Path(__file__).resolve().parents[0] / "fixtures" / "backtests" / "sample_conversation.json"
)


class TestConversationBacktest(unittest.TestCase):
    """Validate scenario loading and evaluation."""

    def setUp(self):
        self.scenarios = conversation_backtest.load_scenarios_from_file(FIXTURE_PATH)

    def test_scenario_load(self):
        """Ensure fixture loads into typed objects."""
        self.assertEqual(len(self.scenarios), 1)
        scenario = self.scenarios[0]
        self.assertEqual(scenario.name, "basic_productivity_flow")
        self.assertEqual(len(scenario.turns), 2)
        self.assertIn("smoke", scenario.tags)

    @patch("core.conversation.generate_response")
    def test_run_backtest_pass(self, mock_generate):
        """Happy path: mock conversation returns keyword-containing responses."""
        mock_generate.side_effect = [
            "Here is your plan with clear priority order.",
            "The first practical step is to open your task list.",
        ]

        results = conversation_backtest.run_backtests(self.scenarios, default_latency_ms=100)
        self.assertEqual(len(results), 1)
        result = results[0]
        self.assertTrue(result.passed)
        self.assertLessEqual(result.avg_latency_ms, 1000)  # patched responses should be instant
        self.assertEqual(mock_generate.call_count, 2)

    @patch("core.conversation.generate_response")
    def test_run_backtest_detects_keyword_failures(self, mock_generate):
        """Ensure missing keywords appear in failure reasons."""
        mock_generate.side_effect = [
            "This response lacks magic words.",
            "Still missing expectations.",
        ]

        results = conversation_backtest.run_backtests(self.scenarios, default_latency_ms=100)
        result = results[0]
        self.assertFalse(result.passed)
        self.assertGreater(len(result.failure_reasons), 0)
        # Ensure the first missing keyword is reported
        self.assertIn("Missing keyword", result.failure_reasons[0])


if __name__ == "__main__":
    unittest.main()
