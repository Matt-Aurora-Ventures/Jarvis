#!/usr/bin/env python3
"""
Print basic Telethon entity info for one or more chat IDs/user IDs.

This is useful for verifying bot @usernames when dialogs have duplicate names
in Telegram (e.g., multiple "ClawdJarvis" chats).

Usage:
  python scripts/telegram_entity_info.py --id 8582341584 --id 7864180473
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from telethon import TelegramClient


def _load_env() -> tuple[str, str]:
    api_id = os.getenv("TELEGRAM_API_ID")
    api_hash = os.getenv("TELEGRAM_API_HASH")

    for p in (Path(".env"), Path.home() / ".env"):
        if not p.exists():
            continue
        for line in p.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k = k.strip()
            v = v.strip().strip('"').strip("'")
            if k == "TELEGRAM_API_ID" and not api_id:
                api_id = v
            if k == "TELEGRAM_API_HASH" and not api_hash:
                api_hash = v

    if not api_id or not api_hash:
        raise SystemExit("Missing TELEGRAM_API_ID / TELEGRAM_API_HASH in env or .env")
    return api_id, api_hash


async def _run(ids: list[int]) -> int:
    api_id, api_hash = _load_env()
    session_path = Path.home() / ".telegram_dl" / "session"
    client = TelegramClient(str(session_path), int(api_id), api_hash)

    await client.connect()
    try:
        await client.start()  # user session
        for i in ids:
            ent = await client.get_entity(i)
            name = getattr(ent, "title", None) or " ".join(
                [p for p in [getattr(ent, "first_name", None), getattr(ent, "last_name", None)] if p]
            )
            username = getattr(ent, "username", None)
            is_bot = getattr(ent, "bot", None)
            print(f"{i}\t{type(ent).__name__}\t{name or ''}\t@{username if username else ''}\tbot={is_bot}")
        return 0
    finally:
        await client.disconnect()


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--id", dest="ids", action="append", required=True, help="Chat/user ID (numeric). May repeat.")
    args = p.parse_args()

    ids = [int(x) for x in args.ids]
    import asyncio

    return asyncio.run(_run(ids))


if __name__ == "__main__":
    raise SystemExit(main())

