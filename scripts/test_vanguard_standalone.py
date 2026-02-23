#!/usr/bin/env python3
"""Run a deterministic standalone dry-run smoke test for Vanguard."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Standalone Vanguard smoke test")
    parser.add_argument("--runtime-seconds", type=int, default=12)
    parser.add_argument("--heartbeat-seconds", type=int, default=2)
    parser.add_argument("--reconcile-interval-seconds", type=int, default=10)
    parser.add_argument("--runtime-dir", default="")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    repo_root = Path(__file__).resolve().parents[1]
    runtime_dir = (
        Path(args.runtime_dir)
        if args.runtime_dir
        else Path(tempfile.gettempdir()) / "jarvis-vanguard-standalone"
    )
    runtime_dir.mkdir(parents=True, exist_ok=True)
    lock_dir = Path(tempfile.gettempdir()) / "jarvis-vanguard-locks"
    lock_dir.mkdir(parents=True, exist_ok=True)
    lock_file = lock_dir / f"runner-{os.getpid()}.lock"
    control_state_path = runtime_dir / "control_state.json"
    try:
        lock_file.unlink(missing_ok=True)
    except OSError:
        pass

    cmd = [
        sys.executable,
        "scripts/ralph_wiggum_parallel_loop.py",
        "--dry-run",
        "--runtime-seconds",
        str(args.runtime_seconds),
        "--heartbeat-seconds",
        str(args.heartbeat_seconds),
        "--reconcile-interval-seconds",
        str(args.reconcile_interval_seconds),
        "--lock-file",
        str(lock_file),
        "--control-state-path",
        str(control_state_path),
    ]

    env = os.environ.copy()
    env.setdefault("JARVIS_CORE_MINIMAL_IMPORTS", "1")
    env.setdefault("PERPS_AI_MODE", "disabled")
    env.setdefault("JARVIS_RALPH_RUNTIME_DIR", str(runtime_dir))
    env.setdefault("PYTHONDONTWRITEBYTECODE", "1")
    env.setdefault("PYTHONPYCACHEPREFIX", str(Path(tempfile.gettempdir()) / "jarvis_pycache"))

    print("Running standalone Vanguard smoke test:")
    print(" ".join(cmd))
    print(f"Runtime dir: {runtime_dir}")
    completed = subprocess.run(cmd, cwd=repo_root, env=env, check=False)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
