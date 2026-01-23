#!/usr/bin/env python3
"""
Continuous Telegram audit loop.

Runs a focused test suite for Telegram bots (/demo + treasury + handlers)
on a schedule. Intended for long-running monitoring on VPS.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path


DEFAULT_TESTS = [
    ["python", "-m", "pytest", "tests/demo_golden", "-q"],
    [
        "python",
        "-m",
        "pytest",
        "tests/unit/test_telegram_handlers.py",
        "tests/unit/test_telegram_ui.py",
        "tests/unit/test_tg_quick_command.py",
        "tests/unit/test_tg_ui_command_framework.py",
        "tests/unit/test_tg_ui_inline_buttons.py",
        "tests/unit/test_tg_ui_interactive_menus.py",
        "tests/unit/test_tg_ui_watchlist.py",
        "-q",
    ],
    ["python", "-m", "pytest", "tests/unit/test_demo_admin_only.py", "-q"],
    ["python", "-m", "pytest", "tests/unit/test_demo_swap_fallback.py", "-q"],
    ["python", "-m", "pytest", "tests/unit/test_demo_hub_sections.py", "-q"],
    ["python", "-m", "pytest", "tests/unit/test_demo_exit_triggers.py", "-q"],
]


def _log(line: str, log_path: Path | None) -> None:
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    message = f"[{timestamp}] {line}"
    print(message, flush=True)
    if log_path:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(message + "\n")


def _run(cmd: list[str], log_path: Path | None) -> int:
    _log("Running: " + " ".join(cmd), log_path)
    result = subprocess.run(cmd, check=False)
    if result.returncode == 0:
        _log("PASS", log_path)
    else:
        _log(f"FAIL (code={result.returncode})", log_path)
    return result.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description="Continuous Telegram audit loop")
    parser.add_argument("--interval", type=int, default=300, help="Seconds between runs")
    parser.add_argument("--max-iterations", type=int, default=0, help="Stop after N iterations (0=forever)")
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    parser.add_argument("--stop-on-failure", action="store_true", help="Exit immediately on failure")
    parser.add_argument("--log", default="logs/telegram_audit_loop.log", help="Log file path")
    args = parser.parse_args()

    log_path = Path(args.log) if args.log else None
    iteration = 0
    while True:
        iteration += 1
        _log(f"=== Telegram Audit Iteration {iteration} ===", log_path)
        failed = False
        for cmd in DEFAULT_TESTS:
            rc = _run(cmd, log_path)
            if rc != 0:
                failed = True
                if args.stop_on_failure:
                    return rc
        if args.once or (args.max_iterations and iteration >= args.max_iterations):
            return 1 if failed else 0
        _log(f"Sleeping {args.interval}s before next run", log_path)
        time.sleep(args.interval)


if __name__ == "__main__":
    raise SystemExit(main())
