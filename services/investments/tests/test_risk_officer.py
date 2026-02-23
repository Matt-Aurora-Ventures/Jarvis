"""Tests for Risk Officer hard-limit logic (no LLM calls)."""

from __future__ import annotations

import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Patch anthropic before importing risk_officer
if "anthropic" not in sys.modules:
    sys.modules["anthropic"] = MagicMock()

from services.investments.consensus.risk_officer import RiskOfficer  # noqa: E402


@pytest.fixture
def officer():
    return RiskOfficer(api_key="test-key")


class TestHardLimits:
    @pytest.mark.asyncio
    async def test_hold_auto_approved(self, officer):
        result = await officer.evaluate(
            proposed_action="HOLD",
            proposed_weights={"ALVA": 0.10, "WETH": 0.25},
            current_weights={"ALVA": 0.10, "WETH": 0.25},
            basket_nav_usd=200.0,
            token_liquidities={"ALVA": 200_000, "WETH": 5_000_000},
            risk_report={},
            daily_changes_so_far_pct=0.0,
        )
        assert result["approved"] is True
        assert result["risk_violations"] == []

    @pytest.mark.asyncio
    async def test_single_token_over_30pct_vetoed(self, officer):
        result = await officer.evaluate(
            proposed_action="REBALANCE",
            proposed_weights={"ALVA": 0.10, "WETH": 0.50, "USDC": 0.40},
            current_weights={"ALVA": 0.10, "WETH": 0.25, "USDC": 0.65},
            basket_nav_usd=200.0,
            token_liquidities={"ALVA": 200_000, "WETH": 5_000_000, "USDC": 50_000_000},
            risk_report={},
            daily_changes_so_far_pct=0.0,
        )
        assert result["approved"] is False
        assert any("WETH" in v for v in result["risk_violations"])

    @pytest.mark.asyncio
    async def test_rebalance_change_exceeds_25pct_vetoed(self, officer):
        result = await officer.evaluate(
            proposed_action="REBALANCE",
            proposed_weights={"ALVA": 0.10, "WETH": 0.60, "USDC": 0.30},
            current_weights={"ALVA": 0.10, "WETH": 0.20, "USDC": 0.70},
            basket_nav_usd=200.0,
            token_liquidities={"ALVA": 200_000, "WETH": 5_000_000, "USDC": 50_000_000},
            risk_report={},
            daily_changes_so_far_pct=0.0,
        )
        assert result["approved"] is False
        assert any("change" in v.lower() for v in result["risk_violations"])

    @pytest.mark.asyncio
    async def test_low_liquidity_vetoed(self, officer):
        result = await officer.evaluate(
            proposed_action="REBALANCE",
            proposed_weights={"ALVA": 0.10, "SHITCOIN": 0.20, "USDC": 0.70},
            current_weights={"ALVA": 0.10, "SHITCOIN": 0.15, "USDC": 0.75},
            basket_nav_usd=200.0,
            token_liquidities={"ALVA": 200_000, "SHITCOIN": 5_000, "USDC": 50_000_000},
            risk_report={},
            daily_changes_so_far_pct=0.0,
        )
        assert result["approved"] is False
        assert any("liquidity" in v.lower() for v in result["risk_violations"])

    @pytest.mark.asyncio
    async def test_daily_cumulative_exceeded(self, officer):
        result = await officer.evaluate(
            proposed_action="REBALANCE",
            proposed_weights={"ALVA": 0.10, "WETH": 0.30, "USDC": 0.60},
            current_weights={"ALVA": 0.10, "WETH": 0.25, "USDC": 0.65},
            basket_nav_usd=200.0,
            token_liquidities={"ALVA": 200_000, "WETH": 5_000_000, "USDC": 50_000_000},
            risk_report={},
            daily_changes_so_far_pct=0.38,  # Already used 38% of 40% daily budget
        )
        assert result["approved"] is False
        assert any("cumulative" in v.lower() for v in result["risk_violations"])

    @pytest.mark.asyncio
    async def test_valid_rebalance_passes_hard_limits(self, officer):
        """Valid small rebalance passes hard limits. LLM call will fail but
        the officer gracefully defaults to approved=True on LLM failure."""
        # Force the LLM call to raise so we hit the except branch
        officer.client.messages.create = AsyncMock(side_effect=Exception("mock"))
        result = await officer.evaluate(
            proposed_action="REBALANCE",
            proposed_weights={"ALVA": 0.10, "WETH": 0.28, "USDC": 0.30, "cbBTC": 0.17, "AERO": 0.15},
            current_weights={"ALVA": 0.10, "WETH": 0.25, "USDC": 0.30, "cbBTC": 0.20, "AERO": 0.15},
            basket_nav_usd=200.0,
            token_liquidities={"ALVA": 200_000, "WETH": 5_000_000, "USDC": 50_000_000, "cbBTC": 10_000_000, "AERO": 500_000},
            risk_report={},
            daily_changes_so_far_pct=0.0,
        )
        # LLM fails gracefully → defaults to approved
        assert result["approved"] is True
