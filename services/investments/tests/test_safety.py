"""Tests for the 5-layer safety system."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.investments.safety import SafetySystem


@pytest.fixture
def mock_db():
    pool = AsyncMock()
    pool.fetchrow = AsyncMock(return_value=None)
    pool.fetch = AsyncMock(return_value=[])
    return pool


@pytest.fixture
def mock_redis():
    rds = AsyncMock()
    rds.get = AsyncMock(return_value=None)
    rds.set = AsyncMock(return_value=True)
    rds.delete = AsyncMock()
    rds.publish = AsyncMock()
    return rds


@pytest.fixture
def safety(mock_db, mock_redis):
    return SafetySystem(mock_db, mock_redis)


# ── Portfolio Guard ──────────────────────────────────────────────────────


class TestPortfolioGuard:
    @pytest.mark.asyncio
    async def test_valid_rebalance_passes(self, safety):
        ok, msg = await safety.check_portfolio_limits(
            proposed_weights={"ALVA": 0.10, "WETH": 0.25, "USDC": 0.30, "cbBTC": 0.20, "AERO": 0.15},
            current_weights={"ALVA": 0.10, "WETH": 0.30, "USDC": 0.25, "cbBTC": 0.20, "AERO": 0.15},
        )
        assert ok is True
        assert msg == ""

    @pytest.mark.asyncio
    async def test_single_token_exceeds_30pct(self, safety):
        ok, msg = await safety.check_portfolio_limits(
            proposed_weights={"ALVA": 0.10, "WETH": 0.50, "USDC": 0.40},
            current_weights={"ALVA": 0.10, "WETH": 0.25, "USDC": 0.65},
        )
        assert ok is False
        assert "WETH" in msg
        assert "30%" in msg

    @pytest.mark.asyncio
    async def test_alva_below_5pct_minimum(self, safety):
        ok, msg = await safety.check_portfolio_limits(
            proposed_weights={"ALVA": 0.02, "WETH": 0.28, "USDC": 0.30, "cbBTC": 0.20, "AERO": 0.20},
            current_weights={"ALVA": 0.10, "WETH": 0.25, "USDC": 0.30, "cbBTC": 0.20, "AERO": 0.15},
        )
        assert ok is False
        assert "ALVA" in msg
        assert "5%" in msg

    @pytest.mark.asyncio
    async def test_total_change_exceeds_25pct(self, safety):
        # All tokens under 30% individually, but total rebalance > 25%
        # WETH: 0.30→0.03 = 0.27, USDC: 0.03→0.30 = 0.27, sum=0.54, /2=0.27 > 0.25
        ok, msg = await safety.check_portfolio_limits(
            proposed_weights={"ALVA": 0.10, "WETH": 0.03, "USDC": 0.30, "cbBTC": 0.30, "AERO": 0.27},
            current_weights={"ALVA": 0.10, "WETH": 0.30, "USDC": 0.03, "cbBTC": 0.30, "AERO": 0.27},
        )
        assert ok is False
        assert "change" in msg.lower()

    @pytest.mark.asyncio
    async def test_too_many_token_changes(self, safety):
        ok, msg = await safety.check_portfolio_limits(
            proposed_weights={
                "ALVA": 0.10, "NEW1": 0.10, "NEW2": 0.10,
                "NEW3": 0.10, "NEW4": 0.10, "NEW5": 0.10,
            },
            current_weights={
                "ALVA": 0.10, "OLD1": 0.10, "OLD2": 0.10,
                "OLD3": 0.10, "OLD4": 0.10, "OLD5": 0.10,
            },
            max_rebalance_change_pct=1.0,  # Disable change limit for this test
        )
        assert ok is False
        assert "token changes" in msg.lower()


# ── Kill Switch ──────────────────────────────────────────────────────────


class TestKillSwitch:
    @pytest.mark.asyncio
    async def test_not_killed_by_default(self, safety, mock_redis):
        mock_redis.get.return_value = None
        assert await safety.is_killed() is False

    @pytest.mark.asyncio
    async def test_killed_when_flag_set(self, safety, mock_redis):
        mock_redis.get.return_value = b"true"
        assert await safety.is_killed() is True

    @pytest.mark.asyncio
    async def test_activate_sets_flag(self, safety, mock_redis):
        await safety.activate_kill_switch("test reason")
        mock_redis.set.assert_called_once_with("inv:kill_switch", "true")

    @pytest.mark.asyncio
    async def test_deactivate_clears_flag(self, safety, mock_redis):
        await safety.deactivate_kill_switch()
        mock_redis.set.assert_called_once_with("inv:kill_switch", "false")


# ── Idempotency Guard ───────────────────────────────────────────────────


class TestIdempotencyGuard:
    @pytest.mark.asyncio
    async def test_first_call_succeeds(self, safety, mock_redis):
        mock_redis.set.return_value = True
        assert await safety.check_idempotency("cycle:2026-02-19") is True

    @pytest.mark.asyncio
    async def test_duplicate_call_blocked(self, safety, mock_redis):
        mock_redis.set.return_value = None  # nx=True returns None when key exists
        assert await safety.check_idempotency("cycle:2026-02-19") is False

    @pytest.mark.asyncio
    async def test_clear_allows_retry(self, safety, mock_redis):
        await safety.clear_idempotency("cycle:2026-02-19")
        mock_redis.delete.assert_called_once_with("inv:idempotency:cycle:2026-02-19")


# ── Bridge Limiter ───────────────────────────────────────────────────────


class TestBridgeLimiter:
    @pytest.mark.asyncio
    async def test_small_bridge_passes(self, safety, mock_db):
        mock_db.fetchrow.return_value = {"total": 0.0}
        ok, msg = await safety.check_bridge_limits(100.0)
        assert ok is True

    @pytest.mark.asyncio
    async def test_single_bridge_exceeds_limit(self, safety, mock_db):
        ok, msg = await safety.check_bridge_limits(15_000.0)
        assert ok is False
        assert "10000" in msg

    @pytest.mark.asyncio
    async def test_daily_bridge_exceeds_limit(self, safety, mock_db):
        mock_db.fetchrow.return_value = {"total": 45_000.0}
        ok, msg = await safety.check_bridge_limits(8_000.0)
        assert ok is False
        assert "50000" in msg
