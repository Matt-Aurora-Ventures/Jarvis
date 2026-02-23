#!/usr/bin/env python3
"""
Validate ClawdBot Telegram tokens (no secrets printed).

Reads tokens from:
- repo-root tokens.env (preferred), or
- /root/clawdbots/tokens.env (VPS default), or
- environment variables (override).

Calls Telegram getMe for each bot token and prints the resolved @username.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import requests


DEFAULT_VARS = [
    "CLAWDJARVIS_BOT_TOKEN",
    "CLAWDFRIDAY_BOT_TOKEN",
    "CLAWDMATT_BOT_TOKEN",  # user renamed to "Arsenal" but env var kept for compat
    "CLAWDYODA_BOT_TOKEN",
    "CLAWDSQUISHY_BOT_TOKEN",
]


def _load_tokens_env(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    out: dict[str, str] = {}
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip()
    return out


def _find_tokens_env() -> Path | None:
    repo_root = Path(__file__).resolve().parents[1]
    cand = repo_root / "tokens.env"
    if cand.exists():
        return cand
    cand = Path("/root/clawdbots/tokens.env")
    if cand.exists():
        return cand
    return None


def _get_me(token: str) -> tuple[bool, str]:
    try:
        resp = requests.get(f"https://api.telegram.org/bot{token}/getMe", timeout=10)
        data = resp.json()
        if not data.get("ok"):
            return False, str(data.get("description") or "Unknown error")
        result = data.get("result") or {}
        username = result.get("username") or "unknown"
        first_name = result.get("first_name") or "unknown"
        return True, f"@{username} ({first_name})"
    except Exception as e:
        return False, str(e)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--vars", nargs="*", default=DEFAULT_VARS, help="Token env vars to validate")
    args = ap.parse_args()

    tokens_env = _find_tokens_env()
    env_kv = _load_tokens_env(tokens_env) if tokens_env else {}

    ok_all = True
    if tokens_env:
        print(f"tokens_env: {tokens_env}")
    else:
        print("tokens_env: (not found)")

    for k in args.vars:
        token = os.getenv(k) or env_kv.get(k, "")
        if not token:
            print(f"- {k}: MISSING")
            ok_all = False
            continue
        ok, msg = _get_me(token)
        if ok:
            print(f"- {k}: OK {msg}")
        else:
            print(f"- {k}: INVALID ({msg})")
            ok_all = False

    return 0 if ok_all else 1


if __name__ == "__main__":
    raise SystemExit(main())

