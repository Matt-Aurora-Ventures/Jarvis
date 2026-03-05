"""Startup and scheduler safety tests for the investment service."""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.investments.config import InvestmentConfig
from services.investments.main import _verify_schema_compatibility
from services.investments.scheduler import create_scheduler


def _make_scheduler_orchestrator(cfg: InvestmentConfig) -> MagicMock:
    orch = MagicMock()
    orch.cfg = cfg
    orch.db = AsyncMock()
    orch.reflection = AsyncMock()
    return orch


class TestSchedulerSafety:
    def test_scheduler_defaults_disable_bridge_and_staking_jobs(self):
        with patch.dict(os.environ, {}, clear=True):
            cfg = InvestmentConfig()

        scheduler = create_scheduler(_make_scheduler_orchestrator(cfg))
        job_ids = {job.id for job in scheduler.get_jobs()}
        assert "daily_investment_cycle" in job_ids
        assert "nav_snapshot" in job_ids
        assert "reflection_check" in job_ids
        assert "bridge_fee_check" not in job_ids
        assert "bridge_advance" not in job_ids
        assert "staking_deposit" not in job_ids

    def test_scheduler_enables_bridge_and_staking_jobs_when_configured(self):
        with patch.dict(
            os.environ,
            {
                "ENABLE_BRIDGE_AUTOMATION": "true",
                "ENABLE_STAKING_AUTOMATION": "true",
            },
            clear=True,
        ):
            cfg = InvestmentConfig()

        scheduler = create_scheduler(_make_scheduler_orchestrator(cfg))
        job_ids = {job.id for job in scheduler.get_jobs()}
        assert "bridge_fee_check" in job_ids
        assert "bridge_advance" in job_ids
        assert "staking_deposit" in job_ids


class TestSchemaCompatibility:
    @pytest.mark.asyncio
    async def test_verify_schema_detects_missing_decision_columns(self):
        conn = AsyncMock()
        conn.fetch.return_value = [
            {"table_name": "inv_decisions", "column_name": "basket_id"},
            {"table_name": "inv_decisions", "column_name": "action"},
            {"table_name": "inv_nav_snapshots", "column_name": "basket_id"},
            {"table_name": "inv_reflections", "column_name": "decision_id"},
            {"table_name": "inv_bridge_jobs", "column_name": "state"},
        ]

        with pytest.raises(RuntimeError, match="inv_decisions"):
            await _verify_schema_compatibility(conn)

    @pytest.mark.asyncio
    async def test_verify_schema_accepts_expected_runtime_shape(self):
        conn = AsyncMock()
        conn.fetch.return_value = [
            {"table_name": "inv_decisions", "column_name": "basket_id"},
            {"table_name": "inv_decisions", "column_name": "trigger_type"},
            {"table_name": "inv_decisions", "column_name": "previous_weights"},
            {"table_name": "inv_decisions", "column_name": "basket_nav_usd"},
            {"table_name": "inv_decisions", "column_name": "risk_approved"},
            {"table_name": "inv_decisions", "column_name": "trader_confidence"},
            {"table_name": "inv_decisions", "column_name": "trader_reasoning"},
            {"table_name": "inv_nav_snapshots", "column_name": "basket_id"},
            {"table_name": "inv_nav_snapshots", "column_name": "ts"},
            {"table_name": "inv_nav_snapshots", "column_name": "nav_usd"},
            {"table_name": "inv_reflections", "column_name": "decision_id"},
            {"table_name": "inv_reflections", "column_name": "data"},
            {"table_name": "inv_reflections", "column_name": "calibration_hint"},
            {"table_name": "inv_bridge_jobs", "column_name": "state"},
            {"table_name": "inv_bridge_jobs", "column_name": "amount_usdc"},
            {"table_name": "inv_bridge_jobs", "column_name": "amount_raw"},
        ]

        await _verify_schema_compatibility(conn)
