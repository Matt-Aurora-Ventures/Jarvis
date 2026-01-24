"""Jarvis CLI actions commands."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from core.ai_runtime.config import AIRuntimeConfig
from core.harness.aggregate import aggregate_actions
from core.harness.decision_gate import DecisionGate
from core.harness.journal import ActionJournal
from core.harness.validators import get_kill_switch_status, set_kill_switch_status


def _pending_actions_path() -> Path:
    config = AIRuntimeConfig.from_env()
    return Path(config.log_path).parent / "pending_actions.json"


def _update_supervisor_pending(action_id: str, status: str) -> bool:
    path = _pending_actions_path()
    if not path.exists():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    updated = False
    for item in data:
        if item.get("id") == action_id:
            item["status"] = status
            updated = True
    if updated:
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return updated


def cmd_actions_list(_: argparse.Namespace) -> int:
    payload = aggregate_actions()
    pending = payload["pending"]
    print("Pending Actions:")
    for section, items in pending.items():
        print(f"- {section} ({len(items)})")
        for item in items:
            print(f"  • {item['action_id']} | {item['summary']} [{item['status']}]")
    return 0


def cmd_actions_status(args: argparse.Namespace) -> int:
    journal = ActionJournal.from_env()
    events = journal.iter_events(action_id=args.action_id)
    if not events:
        print(f"No journal events for {args.action_id}")
        return 0
    for event in events:
        print(f"{event.timestamp} {event.type} by {event.actor}")
    return 0


def cmd_actions_approve(args: argparse.Namespace) -> int:
    gate = DecisionGate()
    ok = gate.approve(args.action_id, actor=args.actor, note=args.note or "")
    if not ok:
        print("Approval blocked (kill switch active).")
        return 1
    _update_supervisor_pending(args.action_id, "approved")
    print(f"Approved {args.action_id}")
    return 0


def cmd_actions_reject(args: argparse.Namespace) -> int:
    gate = DecisionGate()
    gate.reject(args.action_id, actor=args.actor, reason=args.reason or "")
    _update_supervisor_pending(args.action_id, "rejected")
    print(f"Rejected {args.action_id}")
    return 0


def cmd_actions_journal(args: argparse.Namespace) -> int:
    journal = ActionJournal.from_env()
    events = journal.summarize_recent(limit=args.tail)
    for event in events:
        print(f"{event.timestamp} {event.type} {event.action_id}")
    return 0


def cmd_actions_kill(args: argparse.Namespace) -> int:
    if args.mode == "status":
        active, source = get_kill_switch_status()
        label = "on" if active else "off"
        print(f"Kill switch: {label} ({source or 'local'})")
        return 0
    set_kill_switch_status(args.mode == "on")
    print(f"Kill switch set to {args.mode}")
    return 0


def register_actions_subparser(subparsers: argparse._SubParsersAction) -> None:
    actions_parser = subparsers.add_parser("actions", help="Manage pending actions.")
    actions_sub = actions_parser.add_subparsers(dest="actions_command", required=True)

    list_parser = actions_sub.add_parser("list", help="List pending actions.")
    list_parser.set_defaults(func=cmd_actions_list)

    status_parser = actions_sub.add_parser("status", help="Show action journal history.")
    status_parser.add_argument("action_id")
    status_parser.set_defaults(func=cmd_actions_status)

    approve_parser = actions_sub.add_parser("approve", help="Approve an action.")
    approve_parser.add_argument("action_id")
    approve_parser.add_argument("--actor", default="user")
    approve_parser.add_argument("--note", default="")
    approve_parser.set_defaults(func=cmd_actions_approve)

    reject_parser = actions_sub.add_parser("reject", help="Reject an action.")
    reject_parser.add_argument("action_id")
    reject_parser.add_argument("--actor", default="user")
    reject_parser.add_argument("--reason", default="")
    reject_parser.set_defaults(func=cmd_actions_reject)

    journal_parser = actions_sub.add_parser("journal", help="Show recent journal events.")
    journal_parser.add_argument("--tail", type=int, default=20)
    journal_parser.set_defaults(func=cmd_actions_journal)

    kill_parser = actions_sub.add_parser("kill", help="Toggle kill switch.")
    kill_parser.add_argument("mode", choices=["on", "off", "status"])
    kill_parser.set_defaults(func=cmd_actions_kill)
