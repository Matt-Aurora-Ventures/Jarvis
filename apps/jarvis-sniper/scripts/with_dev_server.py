#!/usr/bin/env python3
"""
Start the Jarvis Sniper Next.js dev server, wait until it's *actually* serving HTTP,
run a command, then tear down the whole process tree.

Why this exists:
- Generic "start server + wait for port" helpers often leave orphan child processes on
  Windows (npm -> node), causing flaky tests and false "port ready" signals.
- Next dev server startup can be "port open" before the app is render-ready.
"""

from __future__ import annotations

import argparse
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path


def repo_root() -> Path:
  # jarvis-sniper/scripts/with_dev_server.py -> jarvis-sniper/
  return Path(__file__).resolve().parents[1]


def which_npm() -> str:
  npm = shutil.which("npm.cmd") or shutil.which("npm")
  return npm or "npm"


def port_is_open(host: str, port: int) -> bool:
  try:
    with socket.create_connection((host, port), timeout=1):
      return True
  except OSError:
    return False


def wait_for_http(base_url: str, timeout_s: int) -> None:
  start = time.time()
  last_err: Exception | None = None

  url = f"{base_url.rstrip('/')}/"
  while time.time() - start < timeout_s:
    try:
      req = urllib.request.Request(url, headers={"User-Agent": "jarvis-sniper-smoke"})
      with urllib.request.urlopen(req, timeout=5) as resp:
        # We accept any HTTP response. We just need the server to consistently speak HTTP.
        _ = resp.status
        return
    except Exception as exc:  # noqa: BLE001 - we want to surface the last failure
      last_err = exc
      time.sleep(0.5)

  raise RuntimeError(f"Timed out waiting for HTTP at {url}: {last_err!r}")


def kill_process_tree(proc: subprocess.Popen[bytes] | subprocess.Popen[str]) -> None:
  if proc.poll() is not None:
    return

  if sys.platform.startswith("win"):
    # Kill the process *and* its children (npm -> node -> workers).
    subprocess.run(
      ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
      stdout=subprocess.DEVNULL,
      stderr=subprocess.DEVNULL,
      check=False,
    )
    return

  proc.terminate()
  try:
    proc.wait(timeout=8)
  except subprocess.TimeoutExpired:
    proc.kill()
    proc.wait(timeout=8)


def main() -> int:
  parser = argparse.ArgumentParser(description="Run a command with Jarvis Sniper dev server running")
  parser.add_argument("--host", default="127.0.0.1")
  parser.add_argument("--port", type=int, default=3001)
  parser.add_argument("--timeout", type=int, default=180, help="Timeout (seconds) for server HTTP readiness")
  parser.add_argument("--no-clean-next", action="store_true", help="Do not delete .next before starting dev server")
  parser.add_argument("--npm-script", default="dev", help="npm script to start the server (default: dev)")
  parser.add_argument("--log", default=".jarvis-cache/devserver.log", help="Path (relative to jarvis-sniper/) for server logs")
  parser.add_argument("command", nargs=argparse.REMAINDER, help="Command to run after server is ready (prefix with --)")
  args = parser.parse_args()

  cmd = args.command
  if cmd and cmd[0] == "--":
    cmd = cmd[1:]
  if not cmd:
    print("Error: no command specified. Example: python scripts/with_dev_server.py -- python scripts/smoke-mobile-playwright.py")
    return 2

  root = repo_root()
  base_url = os.environ.get("JARVIS_URL", f"http://{args.host}:{args.port}").rstrip("/")

  if port_is_open(args.host, args.port):
    print(f"Error: {args.host}:{args.port} is already in use. Stop the existing process and retry.")
    return 2

  if not args.no_clean_next:
    next_dir = root / ".next"
    if next_dir.exists():
      shutil.rmtree(next_dir, ignore_errors=True)

  log_path = root / args.log
  log_path.parent.mkdir(parents=True, exist_ok=True)
  npm = which_npm()

  # Start dev server and pipe logs to a file (keeps parent output clean, avoids pipe deadlocks).
  env = os.environ.copy()

  with log_path.open("w", encoding="utf-8", errors="replace") as logf:
    proc = subprocess.Popen(  # noqa: S603,S607 - intended dev tooling command
      [npm, "run", args.npm_script],
      cwd=str(root),
      env=env,
      stdout=logf,
      stderr=subprocess.STDOUT,
    )

    try:
      wait_for_http(base_url, timeout_s=args.timeout)
      env2 = env.copy()
      env2["JARVIS_URL"] = base_url
      result = subprocess.run(cmd, cwd=str(root), env=env2)  # noqa: S603 - intended dev tooling command
      return int(result.returncode or 0)
    finally:
      kill_process_tree(proc)


if __name__ == "__main__":
  raise SystemExit(main())
