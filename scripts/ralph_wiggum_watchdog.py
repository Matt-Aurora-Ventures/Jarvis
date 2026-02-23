#!/usr/bin/env python3
"""Watchdog loop for nonstop Ralph Wiggum runner restarts."""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path


def write_log(path: Path, message: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {message}\n"
    with path.open("a", encoding="utf-8") as handle:
        handle.write(line)


def is_stop_requested(stop_file: Path) -> bool:
    return stop_file.exists()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ralph Wiggum watchdog")
    parser.add_argument("--python-exe", required=True)
    parser.add_argument("--runtime-dir", default=".runtime/ralph_wiggum")
    parser.add_argument("--control-state-path", default="")
    parser.add_argument("--restart-delay-seconds", type=int, default=3)
    parser.add_argument("--reconcile-interval-seconds", type=int, default=10)
    parser.add_argument("--heartbeat-seconds", type=int, default=5)
    parser.add_argument("--max-queue-size", type=int, default=256)
    parser.add_argument("--dry-run", action="store_true", default=True)
    return parser.parse_args()


def is_live_requested(control_state_path: Path) -> bool:
    try:
        data = json.loads(control_state_path.read_text(encoding="utf-8"))
        mode = data.get("mode", {})
        arm = data.get("arm", {})
        return bool(mode.get("desired_live", False) and arm.get("stage") == "armed")
    except Exception:
        return False


def _env_flag(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def main() -> int:
    args = parse_args()

    runtime_dir = Path(args.runtime_dir)
    runtime_dir.mkdir(parents=True, exist_ok=True)

    supervisor_pid = runtime_dir / "watchdog.pid"
    runner_pid = runtime_dir / "runner.pid"
    stop_file = runtime_dir / "watchdog.stop"
    control_state_path = Path(args.control_state_path) if args.control_state_path else runtime_dir / "control_state.json"
    watchdog_log = runtime_dir / "watchdog.log"

    if stop_file.exists():
        stop_file.unlink()

    supervisor_pid.write_text(str(os.getpid()), encoding="utf-8")

    stop_requested = False
    force_dry_run = args.dry_run and (not _env_flag("PERPS_ALLOW_LIVE_ON_ARM", True))

    def _signal_handler(_sig: int, _frame: object) -> None:
        nonlocal stop_requested
        stop_requested = True

    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    write_log(watchdog_log, "watchdog_start")

    try:
        while not stop_requested and not is_stop_requested(stop_file):
            stamp = time.strftime("%Y%m%d")
            stdout_log = runtime_dir / f"runner_stdout_{stamp}.log"
            stderr_log = runtime_dir / f"runner_stderr_{stamp}.log"
            desired_live = is_live_requested(control_state_path)
            launch_dry_run = (not desired_live) or force_dry_run

            cmd = [
                args.python_exe,
                "-u",
                "scripts/ralph_wiggum_parallel_loop.py",
                "--runtime-seconds",
                "0",
                "--reconcile-interval-seconds",
                str(args.reconcile_interval_seconds),
                "--heartbeat-seconds",
                str(args.heartbeat_seconds),
                "--max-queue-size",
                str(args.max_queue_size),
                "--lock-file",
                str(runtime_dir / "runner.lock"),
                "--control-state-path",
                str(control_state_path),
            ]

            if launch_dry_run:
                cmd.append("--dry-run")

            write_log(
                watchdog_log,
                f"runner_start mode={'LIVE' if not launch_dry_run else 'DRY_RUN'} cmd={' '.join(cmd)}",
            )
            with stdout_log.open("a", encoding="utf-8") as out_handle, stderr_log.open(
                "a", encoding="utf-8"
            ) as err_handle:
                child_env = os.environ.copy()
                child_env.setdefault("PYTHONDONTWRITEBYTECODE", "1")
                child_env.setdefault("JARVIS_CORE_MINIMAL_IMPORTS", "1")
                if "PERPS_AI_MODE" not in child_env:
                    child_env["PERPS_AI_MODE"] = "disabled"
                process = subprocess.Popen(cmd, stdout=out_handle, stderr=err_handle, env=child_env)
                runner_pid.write_text(str(process.pid), encoding="utf-8")
                while process.poll() is None:
                    if stop_requested or is_stop_requested(stop_file):
                        try:
                            process.terminate()
                        except Exception:
                            pass
                        break

                    live_now = is_live_requested(control_state_path)
                    dry_run_now = (not live_now) or force_dry_run
                    if dry_run_now != launch_dry_run:
                        write_log(
                            watchdog_log,
                            "mode_change_detected restarting_runner "
                            f"from={'LIVE' if not launch_dry_run else 'DRY_RUN'} "
                            f"to={'LIVE' if not dry_run_now else 'DRY_RUN'}",
                        )
                        try:
                            process.terminate()
                            process.wait(timeout=20)
                        except Exception:
                            try:
                                process.kill()
                            except Exception:
                                pass
                        break
                    time.sleep(2)
                return_code = process.wait()

            write_log(watchdog_log, f"runner_exit code={return_code}")
            runner_pid.unlink(missing_ok=True)

            if stop_requested or is_stop_requested(stop_file):
                break

            time.sleep(max(1, args.restart_delay_seconds))

    finally:
        runner_pid.unlink(missing_ok=True)
        supervisor_pid.unlink(missing_ok=True)
        write_log(watchdog_log, "watchdog_stop")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
