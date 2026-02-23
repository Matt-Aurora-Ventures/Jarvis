"""Tests for orchestrator pipeline logic (mocked agents).

The orchestrator has heavy imports (redis, asyncpg, anthropic, openai, httpx).
We mock sys.modules so tests run without these installed.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Patch heavy dependencies before importing orchestrator
_MOCK_MODULES = [
    "asyncpg",
    "redis", "redis.asyncio",
    "anthropic",
    "openai",
    "httpx",
]
for _mod in _MOCK_MODULES:
    if _mod not in sys.modules:
        sys.modules[_mod] = MagicMock()

from services.investments.orchestrator import Orchestrator  # noqa: E402


@pytest.fixture
def mock_cfg():
    cfg = MagicMock()
    cfg.dry_run = True
    cfg.basket_id = "alpha"
    cfg.xai_api_key = "test"
    cfg.anthropic_api_key = "test"
    cfg.openai_api_key = "test"
    cfg.birdeye_api_key = "test"
    cfg.grok_sentiment_model = "grok-test"
    cfg.grok_trader_model = "grok-test"
    cfg.claude_risk_model = "claude-test"
    cfg.chatgpt_macro_model = "gpt-test"
    cfg.base_rpc_url = ""
    cfg.management_wallet_key = ""
    cfg.basket_address = ""
    return cfg


class TestBasketState:
    @pytest.mark.asyncio
    async def test_dry_run_reads_mock_json(self, mock_cfg):
        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        orch = Orchestrator(mock_cfg, mock_db, mock_redis)
        basket = await orch._get_basket_state()

        assert "tokens" in basket
        assert "nav_usd" in basket
        assert basket["nav_usd"] > 0
        assert "ALVA" in basket["tokens"]

    @pytest.mark.asyncio
    async def test_dry_run_fallback_when_no_json(self, mock_cfg, tmp_path):
        """When mock_basket.json doesn't exist, uses hardcoded defaults."""
        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        orch = Orchestrator(mock_cfg, mock_db, mock_redis)

        # Patch the path to a non-existent location
        with patch.object(Path, "exists", return_value=False):
            basket = await orch._get_basket_state()
            assert "ALVA" in basket["tokens"]
            assert basket["nav_usd"] == 200.0


class TestExecuteDecision:
    @pytest.mark.asyncio
    async def test_hold_returns_none(self, mock_cfg):
        mock_db = AsyncMock()
        mock_redis = AsyncMock()
        orch = Orchestrator(mock_cfg, mock_db, mock_redis)

        result = await orch._execute_decision(
            {"action": "HOLD"},
            {"ALVA": 0.10},
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_dry_run_rebalance_returns_fake_hash(self, mock_cfg):
        mock_db = AsyncMock()
        mock_redis = AsyncMock()
        orch = Orchestrator(mock_cfg, mock_db, mock_redis)

        result = await orch._execute_decision(
            {"action": "REBALANCE", "final_weights": {"ALVA": 0.10}},
            {"ALVA": 0.10},
        )
        assert result.startswith("0x_dry_run_")


class TestCycleGates:
    @pytest.mark.asyncio
    async def test_kill_switch_blocks_cycle(self, mock_cfg):
        mock_db = AsyncMock()
        mock_redis = AsyncMock()
        orch = Orchestrator(mock_cfg, mock_db, mock_redis)
        orch.safety.is_killed = AsyncMock(return_value=True)

        result = await orch.run_cycle()
        assert result["status"] == "killed"

    @pytest.mark.asyncio
    async def test_loss_limiter_blocks_cycle(self, mock_cfg):
        mock_db = AsyncMock()
        mock_redis = AsyncMock()
        orch = Orchestrator(mock_cfg, mock_db, mock_redis)
        orch.safety.is_killed = AsyncMock(return_value=False)
        orch.safety.check_loss_limits = AsyncMock(return_value=(False, "NAV dropped 20%"))

        result = await orch.run_cycle()
        assert result["status"] == "loss_halt"

    @pytest.mark.asyncio
    async def test_idempotency_blocks_duplicate(self, mock_cfg):
        mock_db = AsyncMock()
        mock_redis = AsyncMock()
        orch = Orchestrator(mock_cfg, mock_db, mock_redis)
        orch.safety.is_killed = AsyncMock(return_value=False)
        orch.safety.check_loss_limits = AsyncMock(return_value=(True, ""))
        orch.safety.check_idempotency = AsyncMock(return_value=False)

        result = await orch.run_cycle()
        assert result["status"] == "already_ran"
