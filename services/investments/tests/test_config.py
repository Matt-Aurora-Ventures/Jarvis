"""Tests for InvestmentConfig validation and defaults."""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from services.investments.config import InvestmentConfig


class TestConfigDefaults:
    def test_dry_run_defaults_true(self):
        with patch.dict(os.environ, {}, clear=True):
            cfg = InvestmentConfig()
            assert cfg.dry_run is True

    def test_default_port(self):
        with patch.dict(os.environ, {}, clear=True):
            cfg = InvestmentConfig()
            assert cfg.api_port == 8770

    def test_default_basket_id(self):
        with patch.dict(os.environ, {}, clear=True):
            cfg = InvestmentConfig()
            assert cfg.basket_id == "alpha"

    def test_safety_limit_defaults(self):
        cfg = InvestmentConfig()
        assert cfg.max_single_token_pct == 0.30
        assert cfg.max_rebalance_change_pct == 0.25
        assert cfg.max_daily_cumulative_pct == 0.40
        assert cfg.min_token_liquidity_usd == 50_000.0
        assert cfg.max_daily_bridge_usd == 50_000.0
        assert cfg.bridge_threshold_usd == 50.0
        assert cfg.bridge_max_gas_gwei == 5.0


class TestConfigValidation:
    def test_missing_all_keys(self):
        with patch.dict(os.environ, {}, clear=True):
            cfg = InvestmentConfig()
            missing = cfg.validate()
            assert "XAI_API_KEY" in missing
            assert "ANTHROPIC_API_KEY" in missing
            assert "OPENAI_API_KEY" in missing

    def test_live_mode_requires_wallet(self):
        with patch.dict(os.environ, {
            "XAI_API_KEY": "test",
            "ANTHROPIC_API_KEY": "test",
            "OPENAI_API_KEY": "test",
            "DRY_RUN": "false",
        }, clear=True):
            cfg = InvestmentConfig()
            missing = cfg.validate()
            assert any("MANAGEMENT_WALLET_KEY" in m for m in missing)
            assert any("BASKET_ADDRESS" in m for m in missing)

    def test_dry_run_needs_fewer_keys(self):
        with patch.dict(os.environ, {
            "XAI_API_KEY": "test",
            "ANTHROPIC_API_KEY": "test",
            "OPENAI_API_KEY": "test",
            "DRY_RUN": "true",
        }, clear=True):
            cfg = InvestmentConfig()
            missing = cfg.validate()
            assert missing == []

    def test_env_override(self):
        with patch.dict(os.environ, {
            "INVESTMENT_API_PORT": "9999",
            "BASKET_ID": "beta",
        }, clear=True):
            cfg = InvestmentConfig()
            assert cfg.api_port == 9999
            assert cfg.basket_id == "beta"


class TestConfigModels:
    def test_default_models(self):
        cfg = InvestmentConfig()
        assert cfg.grok_sentiment_model == "grok-4-1-fast-non-reasoning"
        assert cfg.grok_trader_model == "grok-4-1-fast-non-reasoning"
        assert cfg.claude_risk_model == "claude-sonnet-4-6"
        assert cfg.chatgpt_macro_model == "gpt-4o"
