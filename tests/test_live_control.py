from __future__ import annotations

from pathlib import Path

from core.jupiter_perps.live_control import LiveControlConfig, LiveControlState


def _make_state(tmp_path: Path) -> LiveControlState:
    cfg = LiveControlConfig(
        state_path=tmp_path / "control_state.json",
        arm_prepare_ttl_seconds=120,
        arm_live_duration_seconds=600,
        max_trades_per_day=2,
        daily_loss_limit_usd=100.0,
        public_beta_mode=True,
    )
    return LiveControlState(cfg)


def test_prepare_confirm_disarm_flow(tmp_path: Path) -> None:
    state = _make_state(tmp_path)

    prepared = state.prepare_arm(actor="tester")
    assert prepared["ok"] is True
    challenge = prepared["challenge"]

    ok, reason, snapshot = state.confirm_arm(
        challenge=challenge,
        actor="tester",
        phrase="ARM_LIVE_TRADING",
        required_phrase="ARM_LIVE_TRADING",
    )
    assert ok is True
    assert reason == "armed"
    assert snapshot["desired_live"] is True

    disarmed = state.disarm(reason="test_done", actor="tester")
    assert disarmed["desired_live"] is False
    assert disarmed["arm_stage"] == "disarmed"


def test_trade_and_loss_guardrails(tmp_path: Path) -> None:
    state = _make_state(tmp_path)
    challenge = state.prepare_arm(actor="tester")["challenge"]
    ok, _, _ = state.confirm_arm(
        challenge=challenge,
        actor="tester",
        phrase="ARM_LIVE_TRADING",
        required_phrase="ARM_LIVE_TRADING",
    )
    assert ok is True

    allowed, reason = state.can_open_position()
    assert allowed is True
    assert reason == "ok"

    state.record_open_position()
    state.record_open_position()
    allowed, reason = state.can_open_position()
    assert allowed is False
    assert reason == "max_trades_per_day_reached"


def test_daily_loss_limit_disarms(tmp_path: Path) -> None:
    state = _make_state(tmp_path)
    challenge = state.prepare_arm(actor="tester")["challenge"]
    ok, _, _ = state.confirm_arm(
        challenge=challenge,
        actor="tester",
        phrase="ARM_LIVE_TRADING",
        required_phrase="ARM_LIVE_TRADING",
    )
    assert ok is True

    state.record_realized_pnl(-150.0)
    snap = state.public_snapshot()
    assert snap["desired_live"] is False
    assert snap["last_reason"] == "daily_loss_limit_breached"
