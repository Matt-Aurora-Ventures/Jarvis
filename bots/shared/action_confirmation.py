"""Human-in-the-loop action confirmation for bots."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone
from enum import Enum, IntEnum
from pathlib import Path
from typing import Any, Dict
from uuid import uuid4


class RiskLevel(IntEnum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


class ActionType(str, Enum):
    TRADING = "trading"
    INFRASTRUCTURE = "infrastructure"
    PUBLISHING = "publishing"
    API_KEYS = "api_keys"
    MEMORY_MUTATION = "memory_mutation"


RISK_MATRIX: Dict[ActionType, Dict[str, Any]] = {
    ActionType.TRADING: {
        "auto_threshold": 50.0,
        "critical_actions": {"leverage", "margin", "liquidation"},
    },
    ActionType.INFRASTRUCTURE: {
        "low_ops": {"read", "status", "list"},
        "high_ops": {"delete", "destroy", "drop"},
    },
    ActionType.PUBLISHING: {
        "low_ops": {"draft", "preview"},
        "high_ops": {"public_post", "publish"},
    },
    ActionType.API_KEYS: {
        "high_ops": {"create", "rotate", "delete"},
    },
    ActionType.MEMORY_MUTATION: {},
}


class ActionConfirmation:
    def __init__(
        self,
        data_dir: str | Path | None = None,
        bot_name: str | None = None,
        telegram_bot: Any = None,
        admin_chat_id: str | None = None,
    ):
        self.bot_name = bot_name or "unknown"
        self.telegram_bot = telegram_bot
        self.admin_chat_id = admin_chat_id

        self.data_dir = Path(data_dir) if data_dir is not None else Path("/root/clawdbots/handoffs/confirmations")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.history_file = self.data_dir / "approval_history.json"

        self.pending: Dict[str, Dict[str, Any]] = {}
        self._pending_events: Dict[str, asyncio.Event] = {}
        self.history = self._load_history()

    def _load_history(self) -> list[Dict[str, Any]]:
        if not self.history_file.exists():
            return []
        try:
            payload = json.loads(self.history_file.read_text(encoding="utf-8"))
            return payload if isinstance(payload, list) else []
        except Exception:
            return []

    def _persist_history(self) -> None:
        self.history_file.write_text(json.dumps(self.history, indent=2), encoding="utf-8")

    def _log_action(
        self,
        action_type: ActionType,
        description: str,
        agent_name: str,
        decision: str,
    ) -> None:
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action_type": action_type.value,
            "description": description,
            "agent": agent_name,
            "decision": decision,
        }
        self.history.append(entry)
        self.history = self.history[-500:]
        self._persist_history()

    def assess_risk(self, action_type: ActionType, details: Dict[str, Any]) -> RiskLevel:
        details = details or {}
        if action_type == ActionType.TRADING:
            amount = float(details.get("amount_usd", 0.0) or 0.0)
            action = str(details.get("action", "")).lower()
            if action in RISK_MATRIX[ActionType.TRADING]["critical_actions"]:
                return RiskLevel.CRITICAL
            if amount > RISK_MATRIX[ActionType.TRADING]["auto_threshold"]:
                return RiskLevel.HIGH
            return RiskLevel.LOW

        if action_type == ActionType.INFRASTRUCTURE:
            op = str(details.get("operation", "")).lower()
            if op in RISK_MATRIX[ActionType.INFRASTRUCTURE]["high_ops"]:
                return RiskLevel.HIGH
            if op in RISK_MATRIX[ActionType.INFRASTRUCTURE]["low_ops"]:
                return RiskLevel.LOW
            return RiskLevel.MEDIUM

        if action_type == ActionType.PUBLISHING:
            op = str(details.get("operation", "")).lower()
            if op in RISK_MATRIX[ActionType.PUBLISHING]["high_ops"]:
                return RiskLevel.HIGH
            if op in RISK_MATRIX[ActionType.PUBLISHING]["low_ops"]:
                return RiskLevel.LOW
            return RiskLevel.MEDIUM

        if action_type == ActionType.API_KEYS:
            op = str(details.get("operation", "")).lower()
            if op in RISK_MATRIX[ActionType.API_KEYS]["high_ops"]:
                return RiskLevel.HIGH
            return RiskLevel.MEDIUM

        return RiskLevel.MEDIUM

    async def request_approval(
        self,
        action_type: ActionType,
        description: str,
        agent_name: str,
        risk_level: RiskLevel,
        send_fn,
        chat_id: int,
        timeout: float = 30.0,
    ) -> bool:
        if risk_level in (RiskLevel.LOW, RiskLevel.MEDIUM):
            self._log_action(action_type, description, agent_name, "auto_approved")
            return True

        approval_id = uuid4().hex[:8]
        event = asyncio.Event()
        self._pending_events[approval_id] = event
        self.pending[approval_id] = {
            "action_type": action_type.value,
            "description": description,
            "agent": agent_name,
            "risk": risk_level.name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "approved": False,
            "decision": None,
            "required": 2 if risk_level == RiskLevel.CRITICAL else 1,
            "approvals": 0,
            "responders": [],
            "chat_id": chat_id,
            "send_fn": send_fn,
        }

        await send_fn(chat_id, f"APPROVAL REQUIRED [{risk_level.name}] {description} ({approval_id})")

        try:
            await asyncio.wait_for(event.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            self.pending.pop(approval_id, None)
            self._pending_events.pop(approval_id, None)
            self._log_action(action_type, description, agent_name, "timeout_denied")
            return False

        pending = self.pending.get(approval_id)
        if not pending:
            return False

        approved = bool(pending.get("approved"))
        decision = "approved" if approved else "denied"
        self._log_action(action_type, description, agent_name, decision)
        self.pending.pop(approval_id, None)
        self._pending_events.pop(approval_id, None)
        return approved

    def handle_response(self, approval_id: str, approved: bool, user_id: int) -> bool:
        pending = self.pending.get(approval_id)
        if pending is None:
            return False

        if not approved:
            pending["approved"] = False
            pending["decision"] = "denied"
            event = self._pending_events.get(approval_id)
            if event:
                event.set()
            return True

        pending["approvals"] += 1
        pending["responders"].append(user_id)

        if pending["approvals"] >= pending["required"]:
            pending["approved"] = True
            pending["decision"] = "approved"
            event = self._pending_events.get(approval_id)
            if event:
                event.set()
        elif pending["required"] == 2:
            # Critical flows require explicit second confirmation.
            pending["decision"] = "awaiting_second_confirmation"
            send_fn = pending.get("send_fn")
            chat_id = pending.get("chat_id")
            if send_fn is not None and chat_id is not None:
                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(
                        send_fn(chat_id, f"SECOND APPROVAL REQUIRED {pending['description']} ({approval_id})")
                    )
                except RuntimeError:
                    pass
        return True

    # Backwards-compatible names used by older callers.
    def get_risk_level(self, action: str) -> RiskLevel:
        action_l = action.lower()
        if any(k in action_l for k in ("transfer", "withdraw", "reboot")):
            return RiskLevel.CRITICAL
        if any(k in action_l for k in ("buy", "sell", "deploy", "delete")):
            return RiskLevel.HIGH
        if any(k in action_l for k in ("read", "status", "draft", "update")):
            return RiskLevel.MEDIUM
        return RiskLevel.LOW

    async def request_confirmation(self, action: str, details: str = "", timeout_minutes: int = 30) -> Dict[str, Any]:
        risk = self.get_risk_level(action)
        decision = risk in (RiskLevel.LOW, RiskLevel.MEDIUM)
        return {
            "id": uuid4().hex[:8],
            "bot": self.bot_name,
            "action": action,
            "details": details,
            "risk_level": risk.name.lower(),
            "status": "approved" if decision else "pending",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=timeout_minutes)).isoformat(),
            "approved_by": "auto" if decision else None,
            "approved_at": datetime.now(timezone.utc).isoformat() if decision else None,
        }
