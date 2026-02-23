#!/usr/bin/env python3
"""
Telegram DM + group healthcheck for the KR8TIV ClawdBots.

Sends a "reply exactly: pong <token>" message to each bot in:
- DM
- The shared public group

Then polls Telegram until each bot replies with the expected token.

Usage:
  python scripts/telegram_bot_healthcheck.py
  python scripts/telegram_bot_healthcheck.py --group-id -5003286623 --timeout 90
"""

import argparse
import asyncio
import os
import time
from dataclasses import dataclass
from pathlib import Path

from telethon import TelegramClient


BASE = Path.home() / ".telegram_dl"
BASE.mkdir(parents=True, exist_ok=True)
SESSION_PATH = BASE / "session"


def _load_dotenv():
    # Minimal .env support (same behavior as scripts/telegram_fetch.py)
    api_id = os.getenv("TELEGRAM_API_ID")
    api_hash = os.getenv("TELEGRAM_API_HASH")
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    for p in [Path(".env"), Path.home() / ".env"]:
        if not p.exists():
            continue
        for line in p.read_text().splitlines():
            if line.strip().startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k = k.strip()
            v = v.strip()
            if k == "TELEGRAM_API_ID" and not api_id:
                api_id = v
            if k == "TELEGRAM_API_HASH" and not api_hash:
                api_hash = v
            if k == "TELEGRAM_BOT_TOKEN" and not bot_token:
                bot_token = v

    if bot_token and bot_token.strip().lower() in ("disable", "disabled", "none", "no", "false"):
        bot_token = None
    return api_id, api_hash, bot_token


@dataclass(frozen=True)
class BotTarget:
    name: str
    username: str  # @username


DEFAULT_BOTS = [
    BotTarget(name="jarvis", username="@ClawdJarvis_87772_bot"),
    BotTarget(name="friday", username="@ClawdFriday_bot"),
    BotTarget(name="matt", username="@ClawdMatt_bot"),
    BotTarget(name="yoda", username="@yoda_kr8tiv_bot"),
    BotTarget(name="squishy", username="@McSquishington_bot"),
]


async def _ensure_started(client: TelegramClient, bot_token: str | None):
    if bot_token:
        await client.start(bot_token=bot_token)
    else:
        await client.start()


async def _resolve_entity(client: TelegramClient, chat):
    if isinstance(chat, int):
        return await client.get_entity(chat)
    return chat


async def _wait_for_search(
    client: TelegramClient,
    chat,
    query: str,
    timeout_s: int,
    poll_s: float = 2.0,
) -> bool:
    deadline = time.time() + timeout_s
    chat_ent = await _resolve_entity(client, chat)
    while time.time() < deadline:
        msgs = await client.get_messages(chat_ent, search=query, limit=1)
        if msgs:
            return True
        await asyncio.sleep(poll_s)
    return False


async def run(group_id: int, timeout_s: int) -> int:
    api_id, api_hash, bot_token = _load_dotenv()
    if not api_id or not api_hash:
        raise SystemExit("Missing TELEGRAM_API_ID / TELEGRAM_API_HASH in env or .env")

    token_ts = time.strftime("%Y%m%dT%H%M%S", time.gmtime())
    client = TelegramClient(str(SESSION_PATH), int(api_id), api_hash)

    dm_results: dict[str, bool] = {}
    group_results: dict[str, bool] = {}

    async with client:
        await _ensure_started(client, bot_token)

        # Send pings (DM + group)
        for b in DEFAULT_BOTS:
            tok = f"{b.name}-{token_ts}"
            await client.send_message(b.username, f"healthcheck: reply exactly: pong {tok}")

        for b in DEFAULT_BOTS:
            tok = f"{b.name}g-{token_ts}"
            await client.send_message(group_id, f"{b.username} healthcheck: reply exactly: pong {tok}")

        # Wait for responses
        for b in DEFAULT_BOTS:
            tok = f"{b.name}-{token_ts}"
            dm_results[b.name] = await _wait_for_search(client, b.username, f"pong {tok}", timeout_s)

        for b in DEFAULT_BOTS:
            tok = f"{b.name}g-{token_ts}"
            group_results[b.name] = await _wait_for_search(client, group_id, f"pong {tok}", timeout_s)

    ok = all(dm_results.values()) and all(group_results.values())

    # Print a compact status table (no secrets).
    print("telegram_healthcheck")
    for b in DEFAULT_BOTS:
        print(f"- {b.name}: dm={'OK' if dm_results[b.name] else 'FAIL'} group={'OK' if group_results[b.name] else 'FAIL'}")

    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--group-id", type=int, default=-5003286623)
    ap.add_argument("--timeout", type=int, default=90)
    args = ap.parse_args()
    raise SystemExit(asyncio.run(run(args.group_id, args.timeout)))


if __name__ == "__main__":
    main()
