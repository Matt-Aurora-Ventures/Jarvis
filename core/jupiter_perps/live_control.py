"""Shared live-trading control state for standalone/runtime processes.

This module provides a small file-backed control plane used by:
1. watchdog (choose dry-run vs live runner launch),
2. execution service (enforce live arm + guardrails),
3. control API/UI (operator actions).

State is JSON and updated atomically.
"""

from __future__ import annotations

import json
import os
import secrets
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _default_state_path() -> Path:
    runtime_dir = os.environ.get("JARVIS_RALPH_RUNTIME_DIR", "").strip()
    if runtime_dir:
        return Path(runtime_dir) / "control_state.json"
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA") or (Path.home() / "AppData" / "Local"))
        return base / "Jarvis" / "ralph_wiggum" / "control_state.json"
    base = Path(os.environ.get("XDG_STATE_HOME") or (Path.home() / ".local" / "state"))
    return base / "jarvis" / "ralph_wiggum" / "control_state.json"


@dataclass(frozen=True)
class LiveControlConfig:
    state_path: Path
    arm_prepare_ttl_seconds: int = 120
    arm_live_duration_seconds: int = 3600
    max_trades_per_day: int = 40
    daily_loss_limit_usd: float = 500.0
    public_beta_mode: bool = True

    @classmethod
    def from_env(cls, state_path: str = "") -> LiveControlConfig:
        path = Path(state_path) if state_path else _default_state_path()
        return cls(
            state_path=path,
            arm_prepare_ttl_seconds=max(30, int(os.environ.get("PERPS_ARM_PREPARE_TTL_SECONDS", "120"))),
            arm_live_duration_seconds=max(60, int(os.environ.get("PERPS_ARM_LIVE_DURATION_SECONDS", "3600"))),
            max_trades_per_day=max(1, int(os.environ.get("PERPS_MAX_TRADES_PER_DAY", "40"))),
            daily_loss_limit_usd=max(1.0, float(os.environ.get("PERPS_DAILY_LOSS_LIMIT_USD", "500.0"))),
            public_beta_mode=_env_bool("VANGUARD_PUBLIC_BETA_MODE", True),
        )


class LiveControlState:
    """File-backed runtime control for live mode arming and daily guardrails."""

    def __init__(self, config: LiveControlConfig | None = None) -> None:
        self._config = config or LiveControlConfig.from_env()
        self._path = self._config.state_path
        self._path.parent.mkdir(parents=True, exist_ok=True)
        if not self._path.exists():
            self._write_state(self._new_state())

    @property
    def path(self) -> Path:
        return self._path

    def _new_state(self) -> dict[str, Any]:
        now = int(time.time())
        day_ordinal = time.gmtime(now).tm_yday + (time.gmtime(now).tm_year * 1000)
        return {
            "version": 1,
            "updated_at": now,
            "mode": {
                "desired_live": False,
                "public_beta_mode": self._config.public_beta_mode,
            },
            "arm": {
                "stage": "disarmed",   # disarmed | prepared | armed
                "challenge": "",
                "prepared_at": 0,
                "expires_at": 0,
                "armed_at": 0,
                "armed_by": "",
                "last_reason": "init",
            },
            "limits": {
                "max_trades_per_day": self._config.max_trades_per_day,
                "daily_loss_limit_usd": self._config.daily_loss_limit_usd,
            },
            "stats": {
                "day_ordinal": day_ordinal,
                "trades_today": 0,
                "realized_pnl_today": 0.0,
                "last_trade_at": 0,
            },
        }

    def _read_state(self) -> dict[str, Any]:
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            if isinstance(data, dict) and "mode" in data and "arm" in data:
                self._rollover_day(data)
                self._auto_expire_if_needed(data)
                return data
        except Exception:
            pass

        data = self._new_state()
        self._write_state(data)
        return data

    def _write_state(self, data: dict[str, Any]) -> None:
        data["updated_at"] = int(time.time())
        tmp = self._path.with_suffix(f"{self._path.suffix}.tmp")
        payload = json.dumps(data, sort_keys=True, separators=(",", ":"))
        tmp.write_text(payload, encoding="utf-8")
        tmp.replace(self._path)

    def _day_ordinal(self) -> int:
        now = time.gmtime()
        return now.tm_yday + (now.tm_year * 1000)

    def _rollover_day(self, data: dict[str, Any]) -> None:
        stats = data.setdefault("stats", {})
        today = self._day_ordinal()
        if int(stats.get("day_ordinal", 0)) == today:
            return
        stats["day_ordinal"] = today
        stats["trades_today"] = 0
        stats["realized_pnl_today"] = 0.0

    def _auto_expire_if_needed(self, data: dict[str, Any]) -> None:
        arm = data.setdefault("arm", {})
        mode = data.setdefault("mode", {})
        now = int(time.time())
        expires_at = int(arm.get("expires_at", 0) or 0)
        if arm.get("stage") == "prepared" and expires_at > 0 and now >= expires_at:
            arm["stage"] = "disarmed"
            arm["challenge"] = ""
            arm["last_reason"] = "prepare_expired"
            mode["desired_live"] = False
            self._write_state(data)
            return
        if arm.get("stage") == "armed" and expires_at > 0 and now >= expires_at:
            self._set_disarmed(data, reason="arm_expired")
            self._write_state(data)

    def _set_disarmed(self, data: dict[str, Any], reason: str) -> None:
        arm = data.setdefault("arm", {})
        mode = data.setdefault("mode", {})
        arm["stage"] = "disarmed"
        arm["challenge"] = ""
        arm["prepared_at"] = 0
        arm["armed_at"] = 0
        arm["expires_at"] = 0
        arm["last_reason"] = reason
        mode["desired_live"] = False

    def snapshot(self) -> dict[str, Any]:
        return self._read_state()

    def public_snapshot(self) -> dict[str, Any]:
        data = self._read_state()
        mode = data.get("mode", {})
        arm = data.get("arm", {})
        limits = data.get("limits", {})
        stats = data.get("stats", {})
        return {
            "updated_at": data.get("updated_at", 0),
            "desired_live": bool(mode.get("desired_live", False)),
            "arm_stage": arm.get("stage", "unknown"),
            "arm_expires_at": int(arm.get("expires_at", 0) or 0),
            "public_beta_mode": bool(mode.get("public_beta_mode", True)),
            "limits": {
                "max_trades_per_day": int(limits.get("max_trades_per_day", 0) or 0),
                "daily_loss_limit_usd": float(limits.get("daily_loss_limit_usd", 0.0) or 0.0),
            },
            "stats": {
                "trades_today": int(stats.get("trades_today", 0) or 0),
                "realized_pnl_today": float(stats.get("realized_pnl_today", 0.0) or 0.0),
                "last_trade_at": int(stats.get("last_trade_at", 0) or 0),
            },
            "last_reason": arm.get("last_reason", ""),
        }

    def is_live_desired(self) -> bool:
        data = self._read_state()
        mode = data.get("mode", {})
        arm = data.get("arm", {})
        return bool(mode.get("desired_live", False) and arm.get("stage") == "armed")

    def prepare_arm(self, actor: str = "operator") -> dict[str, Any]:
        data = self._read_state()
        challenge = secrets.token_urlsafe(18)
        now = int(time.time())
        expires_at = now + self._config.arm_prepare_ttl_seconds
        arm = data.setdefault("arm", {})
        mode = data.setdefault("mode", {})

        arm["stage"] = "prepared"
        arm["challenge"] = challenge
        arm["prepared_at"] = now
        arm["expires_at"] = expires_at
        arm["armed_at"] = 0
        arm["armed_by"] = actor
        arm["last_reason"] = "prepare_arm"
        mode["desired_live"] = False

        self._write_state(data)
        return {
            "ok": True,
            "challenge": challenge,
            "expires_at": expires_at,
            "actor": actor,
        }

    def confirm_arm(
        self,
        challenge: str,
        actor: str = "operator",
        phrase: str = "",
        required_phrase: str = "",
    ) -> tuple[bool, str, dict[str, Any]]:
        data = self._read_state()
        arm = data.setdefault("arm", {})

        if arm.get("stage") != "prepared":
            return False, "arm_not_prepared", self.public_snapshot()
        if int(arm.get("expires_at", 0) or 0) < int(time.time()):
            self._set_disarmed(data, reason="prepare_expired")
            self._write_state(data)
            return False, "prepare_expired", self.public_snapshot()
        if not challenge or challenge != arm.get("challenge", ""):
            return False, "challenge_mismatch", self.public_snapshot()
        if required_phrase and phrase != required_phrase:
            return False, "confirmation_phrase_mismatch", self.public_snapshot()

        now = int(time.time())
        arm["stage"] = "armed"
        arm["challenge"] = ""
        arm["armed_at"] = now
        arm["armed_by"] = actor
        arm["expires_at"] = now + self._config.arm_live_duration_seconds
        arm["last_reason"] = "armed"
        data.setdefault("mode", {})["desired_live"] = True

        self._write_state(data)
        return True, "armed", self.public_snapshot()

    def disarm(self, reason: str = "operator_disarm", actor: str = "operator") -> dict[str, Any]:
        data = self._read_state()
        self._set_disarmed(data, reason=reason)
        data.setdefault("arm", {})["armed_by"] = actor
        self._write_state(data)
        return self.public_snapshot()

    def set_limits(
        self,
        *,
        max_trades_per_day: int | None = None,
        daily_loss_limit_usd: float | None = None,
    ) -> dict[str, Any]:
        data = self._read_state()
        limits = data.setdefault("limits", {})
        if max_trades_per_day is not None:
            limits["max_trades_per_day"] = max(1, int(max_trades_per_day))
        if daily_loss_limit_usd is not None:
            limits["daily_loss_limit_usd"] = max(1.0, float(daily_loss_limit_usd))
        self._write_state(data)
        return self.public_snapshot()

    def can_open_position(self) -> tuple[bool, str]:
        data = self._read_state()
        mode = data.get("mode", {})
        arm = data.get("arm", {})
        stats = data.get("stats", {})
        limits = data.get("limits", {})

        if not bool(mode.get("desired_live", False)):
            return False, "live_mode_not_armed"
        if arm.get("stage") != "armed":
            return False, f"arm_stage_{arm.get('stage', 'unknown')}"

        max_trades = int(limits.get("max_trades_per_day", self._config.max_trades_per_day) or 0)
        daily_loss = float(limits.get("daily_loss_limit_usd", self._config.daily_loss_limit_usd) or 0.0)
        trades_today = int(stats.get("trades_today", 0) or 0)
        realized_pnl_today = float(stats.get("realized_pnl_today", 0.0) or 0.0)

        if max_trades > 0 and trades_today >= max_trades:
            self._set_disarmed(data, reason="max_trades_per_day_reached")
            self._write_state(data)
            return False, "max_trades_per_day_reached"

        if daily_loss > 0 and realized_pnl_today <= -daily_loss:
            self._set_disarmed(data, reason="daily_loss_limit_breached")
            self._write_state(data)
            return False, "daily_loss_limit_breached"

        return True, "ok"

    def record_open_position(self) -> dict[str, Any]:
        data = self._read_state()
        stats = data.setdefault("stats", {})
        stats["trades_today"] = int(stats.get("trades_today", 0) or 0) + 1
        stats["last_trade_at"] = int(time.time())
        self._write_state(data)
        return self.public_snapshot()

    def record_realized_pnl(self, pnl_usd: float) -> dict[str, Any]:
        data = self._read_state()
        stats = data.setdefault("stats", {})
        stats["realized_pnl_today"] = float(stats.get("realized_pnl_today", 0.0) or 0.0) + float(pnl_usd)

        limits = data.get("limits", {})
        daily_loss_limit = float(limits.get("daily_loss_limit_usd", self._config.daily_loss_limit_usd) or 0.0)
        if daily_loss_limit > 0 and float(stats["realized_pnl_today"]) <= -daily_loss_limit:
            self._set_disarmed(data, reason="daily_loss_limit_breached")

        self._write_state(data)
        return self.public_snapshot()

