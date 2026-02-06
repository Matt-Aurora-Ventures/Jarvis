#!/usr/bin/env python3
"""
Run multiple internal subagents in parallel (operator tool).

Examples:
  python scripts/run_subagents.py --session "ops:telegram-fixit" \
    --task "Summarize last 48h Telegram errors and propose fixes" \
    --task "Audit model/provider config for invalid IDs" \
    --task "Propose watchdog + healthcheck tuning"

  python scripts/run_subagents.py --session "ops:triage" --spec .planning/subagents_spec.json

This script only writes artifacts under `data/subagents/<session>/`.
It does not change code or deploy anything.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

from core.agents.orchestration import SubagentOrchestrator


def _load_spec(path: Path) -> List[Dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and "tasks" in data and isinstance(data["tasks"], list):
        return list(data["tasks"])
    if isinstance(data, list):
        return list(data)
    raise SystemExit("Spec must be a list of task objects, or {\"tasks\": [...]} JSON")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--session", required=True, type=str, help="Session ID (used for grouping artifacts)")
    ap.add_argument("--task", action="append", default=[], help="Task description (repeatable)")
    ap.add_argument("--spec", type=str, default=None, help="Path to JSON spec of tasks")
    ap.add_argument("--max-workers", type=int, default=4)
    ap.add_argument("--timeout", type=int, default=600, help="Total seconds to wait for completion")
    args = ap.parse_args()

    tasks: List[Dict[str, Any]] = []
    if args.spec:
        tasks.extend(_load_spec(Path(args.spec)))
    for t in args.task or []:
        if t.strip():
            tasks.append({"description": t.strip()})

    if not tasks:
        raise SystemExit("No tasks provided. Use --task or --spec.")

    orch = SubagentOrchestrator(session_id=args.session, max_workers=args.max_workers)
    orch.spawn_many(tasks)
    orch.gather(timeout_seconds=args.timeout)
    orch.shutdown()

    print(str(orch.out_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

