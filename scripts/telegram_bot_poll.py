#!/usr/bin/env python3
"""
Telegram Bot API monitor (no Telegram API ID/HASH required).
Reads BOT_TOKEN from env or tokens.env, then polls getUpdates.
"""
import os, json, time
from pathlib import Path
import requests

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    # fallback to tokens.env next to repo or cwd
    for p in [Path("tokens.env"), Path("./tokens.env")]:
        if p.exists():
            for line in p.read_text().splitlines():
                if line.strip().startswith("#") or "=" not in line:
                    continue
                k,v = line.split("=",1)
                if k.strip().endswith("_BOT_TOKEN"):
                    # prefer ClawdMatt/Friday/Jarvis tokens if present
                    if k.strip() in ("CLAWDMATT_BOT_TOKEN","CLAWDFRIDAY_BOT_TOKEN","CLAWDJARVIS_BOT_TOKEN"):
                        TOKEN = v.strip(); break
            if TOKEN:
                break

if not TOKEN:
    raise SystemExit("Missing TELEGRAM_BOT_TOKEN or CLAWD*_BOT_TOKEN in env/tokens.env")

API = f"https://api.telegram.org/bot{TOKEN}"

def get_updates(offset=None, limit=50, timeout=10):
    params = {"timeout": timeout, "limit": limit}
    if offset:
        params["offset"] = offset
    r = requests.get(f"{API}/getUpdates", params=params, timeout=timeout+5)
    r.raise_for_status()
    return r.json()

if __name__ == "__main__":
    print("Bot API monitor started.")
    offset = None
    while True:
        data = get_updates(offset=offset)
        if data.get("ok"):
            for u in data.get("result", []):
                offset = u["update_id"] + 1
                print(json.dumps(u, ensure_ascii=False))
        time.sleep(1)
