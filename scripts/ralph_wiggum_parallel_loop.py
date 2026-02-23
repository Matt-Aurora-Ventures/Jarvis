#!/usr/bin/env python3
"""Wrapper harness for the canonical Jupiter Perps runner."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


def default_lock_file() -> str:
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA") or (Path.home() / "AppData" / "Local"))
        return str(base / "Jarvis" / "ralph_wiggum" / "runner.lock")
    base = Path(os.environ.get("XDG_STATE_HOME") or (Path.home() / ".local" / "state"))
    return str(base / "jarvis" / "ralph_wiggum" / "runner.lock")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Ralph Wiggum wrapper for core.jupiter_perps.runner")
    parser.add_argument("--dry-run", action="store_true", default=True)
    parser.add_argument("--runtime-seconds", type=int, default=0)
    parser.add_argument("--reconcile-interval-seconds", type=int, default=10)
    parser.add_argument("--heartbeat-seconds", type=int, default=5)
    parser.add_argument("--max-queue-size", type=int, default=256)
    parser.add_argument("--lock-file", type=str, default=default_lock_file())
    parser.add_argument("--control-state-path", type=str, default=os.environ.get("PERPS_CONTROL_STATE_PATH", ""))
    parser.add_argument("--idl-path", type=str, default="")
    parser.add_argument("--expected-idl-hash", type=str, default="")
    parser.add_argument("--db-dsn", type=str, default=os.environ.get("PERPS_DB_DSN", ""))
    parser.add_argument("--wallet-address", type=str, default=os.environ.get("PERPS_WALLET_ADDRESS", ""))
    parser.add_argument("--rpc-url", type=str, default=os.environ.get("HELIUS_RPC_URL", "https://api.mainnet-beta.solana.com"))
    parser.add_argument("--disable-macro", action="store_true", default=False)
    parser.add_argument("--enable-ai-bridge", action="store_true", default=False)
    return parser


def main() -> int:
    args = build_parser().parse_args()

    cmd = [
        sys.executable,
        "-m",
        "core.jupiter_perps.runner",
        "--runtime-seconds",
        str(args.runtime_seconds),
        "--reconcile-interval-seconds",
        str(args.reconcile_interval_seconds),
        "--heartbeat-seconds",
        str(args.heartbeat_seconds),
        "--max-queue-size",
        str(args.max_queue_size),
        "--lock-file",
        args.lock_file,
        "--control-state-path",
        args.control_state_path,
        "--db-dsn",
        args.db_dsn,
        "--wallet-address",
        args.wallet_address,
        "--rpc-url",
        args.rpc_url,
    ]

    if args.dry_run:
        cmd.append("--dry-run")
    if args.idl_path:
        cmd.extend(["--idl-path", args.idl_path])
    if args.expected_idl_hash:
        cmd.extend(["--expected-idl-hash", args.expected_idl_hash])
    if args.disable_macro:
        cmd.append("--disable-macro")
    if not args.enable_ai_bridge:
        cmd.append("--disable-ai-bridge")

    repo_root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env.setdefault("JARVIS_CORE_MINIMAL_IMPORTS", "1")
    env.setdefault("PERPS_AI_MODE", "disabled")
    return subprocess.call(cmd, cwd=repo_root, env=env)


if __name__ == "__main__":
    raise SystemExit(main())
