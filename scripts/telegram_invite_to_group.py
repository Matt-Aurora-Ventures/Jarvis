#!/usr/bin/env python3
"""
Invite a user/bot to a Telegram group/supergroup using a Telethon *user* session.

Why:
- Telegram Bot API cannot join groups by itself.
- Many "Chat not found" errors come from bots not being members of the target group.

Usage:
  python scripts/telegram_invite_to_group.py --chat-id -1003408655098 --username @TGTOKEN_BUY_BOT

Auth:
- Uses TELEGRAM_API_ID / TELEGRAM_API_HASH from env or .env
- Uses the existing Telethon session under ~/.telegram_dl/
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from telethon import TelegramClient
from telethon.tl.functions.channels import InviteToChannelRequest


BASE = Path.home() / ".telegram_dl"
BASE.mkdir(parents=True, exist_ok=True)
SESSION_PATH = BASE / "session"  # Telethon will use session.session on disk

API_ID = os.getenv("TELEGRAM_API_ID")
API_HASH = os.getenv("TELEGRAM_API_HASH")

# Optional .env support
for p in [Path(".env"), Path.home() / ".env"]:
    if p.exists():
        for line in p.read_text().splitlines():
            if line.strip().startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            if k.strip() == "TELEGRAM_API_ID" and not API_ID:
                API_ID = v.strip()
            if k.strip() == "TELEGRAM_API_HASH" and not API_HASH:
                API_HASH = v.strip()


def _require_auth() -> None:
    if not API_ID or not API_HASH:
        raise SystemExit("Missing TELEGRAM_API_ID / TELEGRAM_API_HASH in env or .env")


async def _run(chat_id: int, username: str) -> dict:
    _require_auth()
    username = username.strip()
    if username and not username.startswith("@"):
        username = "@" + username

    client = TelegramClient(str(SESSION_PATH), int(API_ID), API_HASH)
    await client.connect()
    try:
        # Always use the existing *user* session (do not attempt bot_token auth here).
        await client.start()

        chat = await client.get_entity(chat_id)
        user = await client.get_entity(username)

        res = await client(InviteToChannelRequest(chat, [user]))
        return {"ok": True, "chat_id": chat_id, "username": username, "result": str(res)[:5000]}
    finally:
        await client.disconnect()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--chat-id", type=int, required=True)
    ap.add_argument("--username", type=str, required=True, help="Username to invite (bot or user), e.g. @my_bot")
    args = ap.parse_args()

    import asyncio

    try:
        out = asyncio.run(_run(args.chat_id, args.username))
        print(json.dumps(out, indent=2))
        return 0
    except Exception as e:
        print(json.dumps({"ok": False, "error": str(e)}, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

