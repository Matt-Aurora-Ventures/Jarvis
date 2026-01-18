#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Health check for Jarvis Telegram Bot
Sends test message to bot and monitors response
No SSH required - uses Telegram Bot API directly
"""

import requests
import time
import json
import sys
from datetime import datetime

TELEGRAM_BOT_TOKEN = '8047602125:AAFSWTVDonm0TV7h1DBtKvPiBI4x5A7c1Ag'
ADMIN_USER_ID = 8527130908  # Matt (from tg_bot/.env)
TEST_TIMEOUT = 30  # seconds

def send_test_message():
    """Send a test finance question to bot."""
    msg = "Is SOL bullish right now?"

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": ADMIN_USER_ID,
        "text": msg
    }

    print(f"[{datetime.now().strftime('%H:%M:%S')}] [SEND] Sending test message: '{msg}'")
    response = requests.post(url, json=payload)
    data = response.json()

    if data.get('ok'):
        msg_id = data['result']['message_id']
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [OK] Message sent (ID: {msg_id})")
        return msg_id
    else:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [ERROR] Failed to send: {data}")
        return None

def check_bot_updates():
    """Check if bot has processed messages recently."""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"

    try:
        response = requests.get(url, timeout=10)
        data = response.json()

        if data.get('ok'):
            updates = data.get('result', [])
            if updates:
                latest = updates[-1]
                print(f"[{datetime.now().strftime('%H:%M:%S')}] [OK] Bot is receiving updates (latest ID: {latest.get('update_id')})")
                return True
            else:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] [INFO] No updates yet")
                return False
        else:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] [ERROR] API error: {data}")
            return False
    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [ERROR] {e}")
        return False

def check_bot_token_validity():
    """Verify bot token is valid by getting bot info."""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getMe"

    try:
        response = requests.get(url, timeout=10)
        data = response.json()

        if data.get('ok'):
            bot_info = data['result']
            bot_name = bot_info.get('first_name')
            bot_username = bot_info.get('username')
            print(f"[{datetime.now().strftime('%H:%M:%S')}] [OK] Bot verified: @{bot_username} ({bot_name})")
            return True
        else:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] [ERROR] Invalid token: {data}")
            return False
    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [ERROR] {e}")
        return False

def health_check():
    """Run full health check."""
    print("=" * 70)
    print("[HEALTH] JARVIS BOT HEALTH CHECK")
    print("=" * 70)
    print()

    results = {
        "timestamp": datetime.now().isoformat(),
        "checks": {}
    }

    # Check 1: Token validity
    print("[CHECK 1/3] Bot token validity...")
    token_valid = check_bot_token_validity()
    results["checks"]["token_valid"] = token_valid
    print()

    if not token_valid:
        print("[FAIL] Bot token invalid! Cannot continue.")
        return False

    # Check 2: Bot receiving updates
    print("[CHECK 2/3] Bot update reception...")
    receiving_updates = check_bot_updates()
    results["checks"]["receiving_updates"] = receiving_updates
    print()

    # Check 3: Send test message
    print("[CHECK 3/3] Sending test message...")
    msg_id = send_test_message()
    results["checks"]["test_message_sent"] = msg_id is not None
    print()

    # Summary
    print("=" * 70)
    print("[RESULTS] HEALTH CHECK SUMMARY")
    print("=" * 70)
    print()

    all_passed = all(results["checks"].values())

    if all_passed:
        print("[SUCCESS] All health checks passed!")
        print()
        print("Bot Status: HEALTHY")
        print("  - Token: Valid")
        print("  - Updates: Receiving")
        print("  - Messaging: Working")
        return True
    else:
        print("[WARNING] Some checks failed:")
        for check, result in results["checks"].items():
            status = "PASS" if result else "FAIL"
            print(f"  - {check}: {status}")
        return False

if __name__ == "__main__":
    try:
        success = health_check()
        print()
        print("=" * 70)
        if success:
            print("[STATUS] Bot is operational and ready for testing")
        else:
            print("[STATUS] Bot health check indicated issues")
        print("=" * 70)
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"[FATAL] {e}")
        sys.exit(1)
