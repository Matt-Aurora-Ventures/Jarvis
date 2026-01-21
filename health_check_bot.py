#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Minimal bot health check for test harness.

Validates that a Telegram bot token is present and well-formed.
Skips network calls to keep tests deterministic in CI environments.
"""

import os
import sys


def _find_token() -> str:
    for key in (
        "TELEGRAM_BOT_TOKEN",
        "JARVIS_TELEGRAM_TOKEN",
        "PUBLIC_BOT_TOKEN",
    ):
        value = os.environ.get(key)
        if value:
            return value
    return ""


def main() -> int:
    token = _find_token()
    if not token:
        print("[WARN] No Telegram token configured. Skipping live health check.")
        return 0

    if ":" not in token or len(token) < 10:
        print("[FAIL] Telegram token present but malformed.")
        return 1

    print("[PASS] Telegram token detected (format OK).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
