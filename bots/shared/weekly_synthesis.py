#!/usr/bin/env python3
"""Weekly Kaizen Synthesis - runs via cron Sunday 08:00 UTC."""

import os
import sys

sys.path.insert(0, "/root/clawdbots")

import requests

from bots.shared.kaizen import Kaizen

TOKEN = os.environ.get("CLAWDMATT_TOKEN", "")
CHAT_ID = os.environ.get("TELEGRAM_ADMIN_CHAT_ID", "")

if not TOKEN:
    token_file = "/root/clawdbots/tokens.env"
    if os.path.exists(token_file):
        for line in open(token_file):
            line = line.strip()
            if line.startswith("CLAWDMATT_TOKEN="):
                TOKEN = line.split("=", 1)[1].strip().strip('"').strip("'")
            elif line.startswith("TELEGRAM_ADMIN_CHAT_ID="):
                CHAT_ID = line.split("=", 1)[1].strip().strip('"').strip("'")


def main():
    if not TOKEN or not CHAT_ID:
        print("Missing CLAWDMATT_TOKEN or TELEGRAM_ADMIN_CHAT_ID")
        sys.exit(1)

    kaizen = Kaizen()
    report = kaizen.weekly_report()

    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    resp = requests.post(url, json={
        "chat_id": CHAT_ID,
        "text": f"📊 {report}",
        "parse_mode": "HTML",
    }, timeout=10)
    print(f"Sent: {resp.status_code}")


if __name__ == "__main__":
    main()
