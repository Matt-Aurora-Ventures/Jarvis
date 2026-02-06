"""Tests for bots.shared.action_confirmation module."""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path
from datetime import datetime, timedelta

# Patch CONFIRMATIONS_DIR before import to use tmp dir
import bots.shared.action_confirmation as mod


@pytest.fixture(autouse=True)
def patch_confirmations_dir(tmp_path, monkeypatch):
    """Redirect file-based storage to tmp_path."""
    monkeypatch.setattr(mod, "CONFIRMATIONS_DIR", tmp_path)
    return tmp_path


@pytest.fixture
def confirmation(tmp_path):
    ac = mod.ActionConfirmation(bot_name="TestBot")
    ac.pending_file = tmp_path / "pending.json"
    ac.history_file = tmp_path / "history.json"
    return ac


class TestRiskLevel:
    def test_all_levels_exist(self):
        assert mod.RiskLevel.LOW.value == "low"
        assert mod.RiskLevel.MEDIUM.value == "medium"
        assert mod.RiskLevel.HIGH.value == "high"
        assert mod.RiskLevel.CRITICAL.value == "critical"


class TestGetRiskLevel:
    def test_exact_match(self, confirmation):
        assert confirmation.get_risk_level("buy_token") == mod.RiskLevel.HIGH
        assert confirmation.get_risk_level("transfer_sol") == mod.RiskLevel.CRITICAL
        assert confirmation.get_risk_level("restart_service") == mod.RiskLevel.MEDIUM

    def test_keyword_match(self, confirmation):
        assert confirmation.get_risk_level("deploy code to server") == mod.RiskLevel.HIGH

    def test_unknown_action_low(self, confirmation):
        assert confirmation.get_risk_level("check_status") == mod.RiskLevel.LOW


class TestRequestConfirmation:
    @pytest.mark.asyncio
    async def test_low_risk_auto_approves(self, confirmation):
        result = await confirmation.request_confirmation("check_status")
        assert result["status"] == "auto_approved"
        assert result["approved_by"] == "auto"

    @pytest.mark.asyncio
    async def test_medium_risk_auto_approves(self, confirmation):
        result = await confirmation.request_confirmation("restart_service")
        assert result["status"] == "auto_approved"

    @pytest.mark.asyncio
    async def test_high_risk_pending(self, confirmation):
        result = await confirmation.request_confirmation("buy_token", "Buy 100 SOL")
        assert result["status"] == "pending"
        assert result["approved_by"] is None

    @pytest.mark.asyncio
    async def test_high_risk_sends_telegram(self, confirmation):
        confirmation.telegram_bot = MagicMock()
        confirmation.telegram_bot.send_message = AsyncMock()
        confirmation.admin_chat_id = "123"

        result = await confirmation.request_confirmation("buy_token", "Buy SOL")
        confirmation.telegram_bot.send_message.assert_called_once()
        msg = confirmation.telegram_bot.send_message.call_args[1]["text"]
        assert "APPROVAL" in msg
        assert result["id"] in msg

    @pytest.mark.asyncio
    async def test_critical_risk_pending(self, confirmation):
        result = await confirmation.request_confirmation("transfer_sol")
        assert result["status"] == "pending"


class TestApproveAndDeny:
    @pytest.mark.asyncio
    async def test_approve_pending(self, confirmation):
        result = await confirmation.request_confirmation("buy_token")
        cid = result["id"]
        assert confirmation.approve(cid) is True
        assert confirmation.is_approved(cid) is False  # moved to archive, no longer in pending

    @pytest.mark.asyncio
    async def test_deny_pending(self, confirmation):
        result = await confirmation.request_confirmation("buy_token")
        cid = result["id"]
        assert confirmation.deny(cid) is True
        assert confirmation.is_approved(cid) is False

    def test_approve_nonexistent(self, confirmation):
        assert confirmation.approve("nonexistent") is False

    def test_deny_nonexistent(self, confirmation):
        assert confirmation.deny("nonexistent") is False


class TestGetPending:
    @pytest.mark.asyncio
    async def test_lists_pending(self, confirmation):
        await confirmation.request_confirmation("buy_token")
        await confirmation.request_confirmation("sell_token")
        pending = confirmation.get_pending()
        assert len(pending) == 2

    @pytest.mark.asyncio
    async def test_approved_removed_from_pending(self, confirmation):
        result = await confirmation.request_confirmation("buy_token")
        confirmation.approve(result["id"])
        assert len(confirmation.get_pending()) == 0


class TestPersistence:
    @pytest.mark.asyncio
    async def test_history_persisted(self, confirmation):
        result = await confirmation.request_confirmation("buy_token")
        confirmation.approve(result["id"])
        history = json.loads(confirmation.history_file.read_text())
        assert len(history) == 1
        assert history[0]["status"] == "approved"

    @pytest.mark.asyncio
    async def test_pending_persisted(self, confirmation):
        await confirmation.request_confirmation("buy_token")
        data = json.loads(confirmation.pending_file.read_text())
        assert len(data) == 1

    @pytest.mark.asyncio
    async def test_history_capped_at_200(self, confirmation):
        # Write 201 entries to history
        entries = [{"id": str(i), "status": "approved"} for i in range(201)]
        confirmation.history_file.write_text(json.dumps(entries))
        # Archive one more
        confirmation._archive({"id": "new", "status": "approved"})
        history = json.loads(confirmation.history_file.read_text())
        assert len(history) == 200
