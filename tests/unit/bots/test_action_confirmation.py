"""
Tests for the Action Confirmation System (Phase 9.12).

Human-in-the-loop approval workflow for high-risk ClawdBot actions.
"""

import asyncio
import json
import os
import tempfile
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from bots.shared.action_confirmation import (
    ActionConfirmation,
    ActionType,
    RiskLevel,
    RISK_MATRIX,
)


@pytest.fixture
def tmp_data_dir(tmp_path):
    return str(tmp_path)


@pytest.fixture
def confirmation(tmp_data_dir):
    return ActionConfirmation(data_dir=tmp_data_dir)


class TestRiskLevel:
    def test_risk_levels_ordering(self):
        assert RiskLevel.LOW.value < RiskLevel.MEDIUM.value
        assert RiskLevel.MEDIUM.value < RiskLevel.HIGH.value
        assert RiskLevel.HIGH.value < RiskLevel.CRITICAL.value

    def test_all_risk_levels_exist(self):
        assert hasattr(RiskLevel, "LOW")
        assert hasattr(RiskLevel, "MEDIUM")
        assert hasattr(RiskLevel, "HIGH")
        assert hasattr(RiskLevel, "CRITICAL")


class TestActionType:
    def test_all_action_types_exist(self):
        assert ActionType.TRADING.value == "trading"
        assert ActionType.INFRASTRUCTURE.value == "infrastructure"
        assert ActionType.PUBLISHING.value == "publishing"
        assert ActionType.API_KEYS.value == "api_keys"
        assert ActionType.MEMORY_MUTATION.value == "memory_mutation"


class TestRiskMatrix:
    def test_risk_matrix_has_all_action_types(self):
        assert ActionType.TRADING in RISK_MATRIX
        assert ActionType.INFRASTRUCTURE in RISK_MATRIX
        assert ActionType.PUBLISHING in RISK_MATRIX
        assert ActionType.API_KEYS in RISK_MATRIX

    def test_trading_has_auto_threshold(self):
        assert "auto_threshold" in RISK_MATRIX[ActionType.TRADING]
        assert RISK_MATRIX[ActionType.TRADING]["auto_threshold"] == 50.0


class TestAssessRisk:
    def test_trading_below_threshold_is_low(self, confirmation):
        risk = confirmation.assess_risk(ActionType.TRADING, {"amount_usd": 10.0})
        assert risk == RiskLevel.LOW

    def test_trading_above_threshold_is_high(self, confirmation):
        risk = confirmation.assess_risk(ActionType.TRADING, {"amount_usd": 100.0})
        assert risk == RiskLevel.HIGH

    def test_trading_high_risk_action_is_critical(self, confirmation):
        risk = confirmation.assess_risk(
            ActionType.TRADING, {"action": "leverage", "amount_usd": 10.0}
        )
        assert risk == RiskLevel.CRITICAL

    def test_infra_read_is_low(self, confirmation):
        risk = confirmation.assess_risk(
            ActionType.INFRASTRUCTURE, {"operation": "read"}
        )
        assert risk == RiskLevel.LOW

    def test_infra_delete_is_high(self, confirmation):
        risk = confirmation.assess_risk(
            ActionType.INFRASTRUCTURE, {"operation": "delete"}
        )
        assert risk == RiskLevel.HIGH

    def test_publishing_draft_is_low(self, confirmation):
        risk = confirmation.assess_risk(
            ActionType.PUBLISHING, {"operation": "draft"}
        )
        assert risk == RiskLevel.LOW

    def test_publishing_public_post_is_high(self, confirmation):
        risk = confirmation.assess_risk(
            ActionType.PUBLISHING, {"operation": "public_post"}
        )
        assert risk == RiskLevel.HIGH

    def test_api_keys_create_is_high(self, confirmation):
        risk = confirmation.assess_risk(
            ActionType.API_KEYS, {"operation": "create"}
        )
        assert risk == RiskLevel.HIGH

    def test_unknown_details_defaults_to_medium(self, confirmation):
        risk = confirmation.assess_risk(
            ActionType.MEMORY_MUTATION, {}
        )
        assert risk == RiskLevel.MEDIUM


class TestRequestApproval:
    @pytest.mark.asyncio
    async def test_low_risk_auto_approves(self, confirmation):
        send_fn = AsyncMock()
        result = await confirmation.request_approval(
            action_type=ActionType.TRADING,
            description="Buy 1 SOL token",
            agent_name="ClawdJarvis",
            risk_level=RiskLevel.LOW,
            send_fn=send_fn,
            chat_id=12345,
        )
        assert result is True
        send_fn.assert_not_called()

    @pytest.mark.asyncio
    async def test_medium_risk_auto_approves_with_log(self, confirmation):
        send_fn = AsyncMock()
        result = await confirmation.request_approval(
            action_type=ActionType.INFRASTRUCTURE,
            description="Read config",
            agent_name="ClawdJarvis",
            risk_level=RiskLevel.MEDIUM,
            send_fn=send_fn,
            chat_id=12345,
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_high_risk_sends_approval_message(self, confirmation):
        send_fn = AsyncMock()

        # Pre-approve so it doesn't timeout
        async def approve_soon():
            await asyncio.sleep(0.05)
            for aid in list(confirmation.pending.keys()):
                confirmation.handle_response(aid, True, 99999)

        task = asyncio.create_task(approve_soon())

        result = await confirmation.request_approval(
            action_type=ActionType.INFRASTRUCTURE,
            description="Delete old logs",
            agent_name="ClawdJarvis",
            risk_level=RiskLevel.HIGH,
            send_fn=send_fn,
            chat_id=12345,
            timeout=2,
        )
        await task
        assert result is True
        send_fn.assert_called_once()
        call_args = send_fn.call_args
        assert "APPROVAL REQUIRED" in call_args[0][1]

    @pytest.mark.asyncio
    async def test_high_risk_denied(self, confirmation):
        send_fn = AsyncMock()

        async def deny_soon():
            await asyncio.sleep(0.05)
            for aid in list(confirmation.pending.keys()):
                confirmation.handle_response(aid, False, 99999)

        task = asyncio.create_task(deny_soon())

        result = await confirmation.request_approval(
            action_type=ActionType.INFRASTRUCTURE,
            description="Delete production data",
            agent_name="ClawdJarvis",
            risk_level=RiskLevel.HIGH,
            send_fn=send_fn,
            chat_id=12345,
            timeout=2,
        )
        await task
        assert result is False

    @pytest.mark.asyncio
    async def test_timeout_denies(self, confirmation):
        send_fn = AsyncMock()
        result = await confirmation.request_approval(
            action_type=ActionType.API_KEYS,
            description="Rotate API key",
            agent_name="ClawdJarvis",
            risk_level=RiskLevel.HIGH,
            send_fn=send_fn,
            chat_id=12345,
            timeout=0.1,
        )
        assert result is False


class TestHandleResponse:
    def test_approve_valid_id(self, confirmation):
        confirmation.pending["abc123"] = {
            "action_type": "trading",
            "description": "test",
            "agent": "Jarvis",
            "risk": "HIGH",
            "timestamp": "2026-01-01T00:00:00Z",
        }
        result = confirmation.handle_response("abc123", True, 99999)
        assert result is True
        assert "abc123" not in confirmation.pending

    def test_deny_valid_id(self, confirmation):
        confirmation.pending["abc123"] = {
            "action_type": "trading",
            "description": "test",
            "agent": "Jarvis",
            "risk": "HIGH",
            "timestamp": "2026-01-01T00:00:00Z",
        }
        result = confirmation.handle_response("abc123", False, 99999)
        assert result is True
        assert "abc123" not in confirmation.pending

    def test_invalid_id_returns_false(self, confirmation):
        result = confirmation.handle_response("nonexistent", True, 99999)
        assert result is False


class TestPersistence:
    def test_history_saved_to_disk(self, confirmation, tmp_data_dir):
        confirmation._log_action(
            ActionType.TRADING, "test trade", "Jarvis", "approved"
        )
        history_file = Path(tmp_data_dir) / "approval_history.json"
        assert history_file.exists()
        data = json.loads(history_file.read_text())
        assert len(data) > 0

    def test_history_loads_on_init(self, tmp_data_dir):
        # Write some history
        history_file = Path(tmp_data_dir) / "approval_history.json"
        history_file.write_text(json.dumps([
            {"action": "test", "decision": "approved", "timestamp": "2026-01-01"}
        ]))
        conf = ActionConfirmation(data_dir=tmp_data_dir)
        assert len(conf.history) == 1


class TestCriticalRisk:
    @pytest.mark.asyncio
    async def test_critical_sends_double_confirm(self, confirmation):
        send_fn = AsyncMock()

        async def approve_twice():
            await asyncio.sleep(0.05)
            for aid in list(confirmation.pending.keys()):
                confirmation.handle_response(aid, True, 99999)
            await asyncio.sleep(0.05)
            for aid in list(confirmation.pending.keys()):
                confirmation.handle_response(aid, True, 99999)

        task = asyncio.create_task(approve_twice())

        result = await confirmation.request_approval(
            action_type=ActionType.TRADING,
            description="Leverage trade 500 SOL",
            agent_name="ClawdJarvis",
            risk_level=RiskLevel.CRITICAL,
            send_fn=send_fn,
            chat_id=12345,
            timeout=2,
        )
        await task
        assert result is True
        # Should have sent 2 messages (initial + confirmation)
        assert send_fn.call_count == 2
