#!/usr/bin/env python3
"""
Send a message to Telegram private group
"""

import requests
import sys
import os
from pathlib import Path

# Load .env if available
env_path = Path(__file__).parent.parent / "tg_bot" / ".env"
if env_path.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(env_path)
    except ImportError:
        # Manually load .env if python-dotenv not available
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()

# Get bot token and chat ID
BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
CHAT_ID = os.environ.get('TELEGRAM_BROADCAST_CHAT_ID')

if not BOT_TOKEN or not CHAT_ID:
    print("ERROR: Missing credentials")
    print("Set TELEGRAM_BOT_TOKEN and TELEGRAM_BROADCAST_CHAT_ID in tg_bot/.env")
    sys.exit(1)

message = """🚀 JARVIS DEPLOYED - THE GLOW-UP IS REAL (BUT WE'RE STILL COOKING)

24 HOURS. 25 COMMITS. ONE AUTONOMOUS SYSTEM LIVE ON VPS.

What Happened:
✅ Built 5 universal deployment scripts (1,400+ lines)
✅ Eliminated hardcoded credentials (security audit passed)
✅ Deployed autonomous modules to Hostinger VPS (72.61.7.126)
✅ Started supervisor + validation loop
✅ 47+ proof files collected locally
✅ 6/6 tests passing continuously

The Architecture:
🔹 Moderation Layer: Toxicity detection + auto-actions
🔹 Learning Layer: Engagement analysis
🔹 Vibe Coding: Sentiment-driven regime adaptation
🔹 Autonomous Manager: Makes decisions without human input

🔐 Security Fixes:
Eliminated all hardcoded passwords. VPS credentials now safely stored in .env (gitignored, not committed). Every deployment script validates credentials before running.

⚠️ CURRENT STATUS - SYSTEM IN PROGRESS (NOT FULLY OPERATIONAL YET)

The autonomous system is deployed and running, but we're currently:
⏳ Validating all components end-to-end
⏳ Collecting continuous proof of autonomous decision-making
⏳ Monitoring for 24+ hours to hit 2,880+ proof files
⏳ Working on final verification before full production status

What you're seeing NOW:
✅ Local validation loop: Running continuously
✅ VPS deployment: Complete
✅ Tests passing: 6/6
✅ Live autonomous decisions: Every 30 seconds

What's NEXT:
🔜 24-hour proof collection (currently running)
🔜 Final performance verification
🔜 Password rotation in production
🔜 Full operational status after validation complete

The Vibe:
We didn't just build it. We shipped it. We're proving it works. And it's gonna be *chef's kiss* when we flip it fully live.

Status: DEPLOYED & VALIDATING. Not 100% yet, but we're getting there. 🤖📊"""

url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
payload = {
    "chat_id": CHAT_ID,
    "text": message,
    "parse_mode": "HTML"
}

try:
    response = requests.post(url, json=payload)
    if response.status_code == 200:
        print("[OK] Message sent to private group!")
        result = response.json()
        if result.get("ok"):
            print(f"[SUCCESS] Message ID: {result.get('result', {}).get('message_id')}")
        else:
            print(f"[WARNING] Response: {result}")
    else:
        print(f"[FAILED] Failed to send message")
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text}")
        sys.exit(1)
except Exception as e:
    print(f"[ERROR] {e}")
    sys.exit(1)
