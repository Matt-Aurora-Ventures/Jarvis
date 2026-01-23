"""Golden snapshot tests for demo and key Telegram commands."""

from __future__ import annotations

import json
import os
from pathlib import Path

from tests.demo_golden.harness import generate_golden, run_case


CASES = [
    "start_admin",
    "help_admin",
    "dashboard_empty",
    "positions_sample",
    "report_simple",
    "trade_ticket",
    "close_position",
    "demo_main",
    "demo_positions",
    "demo_buy_prompt",
    "demo_buy_confirm",
    "demo_sell_all_confirm",
    "demo_sell_position",
    "demo_refresh",
    "demo_learning",
]


def _golden_dir() -> Path:
    return Path(__file__).resolve().parent / "golden"


def test_demo_golden_snapshots():
    golden_dir = _golden_dir()
    if os.environ.get("UPDATE_GOLDEN") == "1":
        generate_golden(golden_dir, CASES)

    missing = [case for case in CASES if not (golden_dir / f"{case}.json").exists()]
    assert not missing, f"Missing golden files: {missing}"

    for case in CASES:
        expected = json.loads((golden_dir / f"{case}.json").read_text(encoding="utf-8"))
        result = run_case(case)
        payload = {
            "text": result.text,
            "parse_mode": result.parse_mode,
            "keyboard": result.keyboard,
        }
        assert payload == expected, f"Golden mismatch for {case}"
