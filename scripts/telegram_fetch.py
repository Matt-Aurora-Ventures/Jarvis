#!/usr/bin/env python3
"""
Telegram fetch helper for monitoring ClawdBots group.

Usage:
  python scripts/telegram_fetch.py setup
  python scripts/telegram_fetch.py list
  python scripts/telegram_fetch.py recent --limit 50
  python scripts/telegram_fetch.py search "query"
  python scripts/telegram_fetch.py unread
  python scripts/telegram_fetch.py send --chat "@username" --text "hi"

Auth:
- Requires TELEGRAM_API_ID and TELEGRAM_API_HASH in env or .env
- Creates/uses session file in ~/.telegram_dl/ (local)
"""

import os
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime, timedelta

try:
    from telethon import TelegramClient
    from telethon.errors import FloodWaitError
except Exception as e:
    print("Telethon not installed. Run: pip install telethon")
    raise

BASE = Path.home() / ".telegram_dl"
BASE.mkdir(parents=True, exist_ok=True)
SESSION_PATH = BASE / "session"

API_ID = os.getenv("TELEGRAM_API_ID")
API_HASH = os.getenv("TELEGRAM_API_HASH")
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Optional .env support
ENV_PATHS = [Path(".env"), Path.home() / ".env"]
for p in ENV_PATHS:
    if p.exists():
        for line in p.read_text().splitlines():
            if line.strip().startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            if k.strip() == "TELEGRAM_API_ID" and not API_ID:
                API_ID = v.strip()
            if k.strip() == "TELEGRAM_API_HASH" and not API_HASH:
                API_HASH = v.strip()
            if k.strip() == "TELEGRAM_BOT_TOKEN" and not BOT_TOKEN:
                BOT_TOKEN = v.strip()

# Allow explicit disabling of bot mode via env override
if BOT_TOKEN and BOT_TOKEN.strip().lower() in ("disable", "disabled", "none", "no", "false"):
    BOT_TOKEN = None


def require_auth():
    if not API_ID or not API_HASH:
        print("Missing TELEGRAM_API_ID / TELEGRAM_API_HASH in env or .env")
        sys.exit(1)


def make_client():
    require_auth()
    return TelegramClient(str(SESSION_PATH), int(API_ID), API_HASH)


async def ensure_started(client: TelegramClient):
    if BOT_TOKEN:
        await client.start(bot_token=BOT_TOKEN)
    else:
        await client.start()


def cmd_setup(_args):
    require_auth()
    print("Auth configured. Session path:", SESSION_PATH)
    print("Run any command to login interactively if session not present.")


def cmd_list(args):
    client = make_client()
    async def run():
        await client.connect()
        try:
            await ensure_started(client)
            dialogs = await client.get_dialogs(limit=args.limit)
            out = []
            for d in dialogs:
                out.append({"id": d.id, "name": d.name, "unread": d.unread_count, "is_group": d.is_group})
            print(json.dumps(out, indent=2))
        finally:
            await client.disconnect()
    client.loop.run_until_complete(run())


def resolve_chat(client, args):
    if args.chat_id:
        return int(args.chat_id)
    if args.chat:
        return args.chat
    return None


def cmd_recent(args):
    client = make_client()
    async def run():
        await client.connect()
        try:
            await ensure_started(client)
            chat = resolve_chat(client, args)
            msgs = await client.get_messages(chat, limit=args.limit) if chat else []
            out = []
            for m in reversed(msgs):
                out.append({"id": m.id, "date": m.date.isoformat() if m.date else None, "text": m.text})
            print(json.dumps(out, indent=2))
        finally:
            await client.disconnect()
    client.loop.run_until_complete(run())


def cmd_search(args):
    client = make_client()
    async def run():
        await client.connect()
        try:
            await ensure_started(client)
            chat = resolve_chat(client, args)
            results = await client.get_messages(chat, search=args.query, limit=args.limit) if chat else []
            out = []
            for m in reversed(results):
                out.append({"id": m.id, "date": m.date.isoformat() if m.date else None, "text": m.text})
            print(json.dumps(out, indent=2))
        finally:
            await client.disconnect()
    client.loop.run_until_complete(run())


def cmd_unread(args):
    client = make_client()
    async def run():
        await client.connect()
        try:
            await ensure_started(client)
            dialogs = await client.get_dialogs(limit=200)
            out = []
            for d in dialogs:
                if d.unread_count:
                    out.append({"id": d.id, "name": d.name, "unread": d.unread_count})
            print(json.dumps(out, indent=2))
        finally:
            await client.disconnect()
    client.loop.run_until_complete(run())


def cmd_send(args):
    client = make_client()
    async def run():
        await client.connect()
        try:
            await ensure_started(client)
            target = args.chat or args.chat_id
            msg = await client.send_message(target, args.text)
            print(json.dumps({"ok": True, "id": msg.id, "date": msg.date.isoformat()}, indent=2))
        finally:
            await client.disconnect()
    client.loop.run_until_complete(run())


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd")

    sub.add_parser("setup")

    p_list = sub.add_parser("list")
    p_list.add_argument("--limit", type=int, default=50)

    p_recent = sub.add_parser("recent")
    p_recent.add_argument("--chat", type=str, default=None)
    p_recent.add_argument("--chat-id", dest="chat_id", type=str, default=None)
    p_recent.add_argument("--limit", type=int, default=50)

    p_search = sub.add_parser("search")
    p_search.add_argument("query", type=str)
    p_search.add_argument("--chat", type=str, default=None)
    p_search.add_argument("--chat-id", dest="chat_id", type=str, default=None)
    p_search.add_argument("--limit", type=int, default=50)

    sub.add_parser("unread")

    p_send = sub.add_parser("send")
    p_send.add_argument("--chat", type=str, default=None)
    p_send.add_argument("--chat-id", dest="chat_id", type=str, default=None)
    p_send.add_argument("--text", type=str, required=True)

    args = p.parse_args()
    if args.cmd == "setup":
        cmd_setup(args)
    elif args.cmd == "list":
        cmd_list(args)
    elif args.cmd == "recent":
        cmd_recent(args)
    elif args.cmd == "search":
        cmd_search(args)
    elif args.cmd == "unread":
        cmd_unread(args)
    elif args.cmd == "send":
        cmd_send(args)
    else:
        p.print_help()


if __name__ == "__main__":
    main()
