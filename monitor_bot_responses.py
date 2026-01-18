#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Monitor bot responses to test messages
Tracks messages sent and waits for responses
Useful for testing Dexter without SSH access
"""

import os
import requests
import json
import time
from datetime import datetime
from collections import defaultdict

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
_admin_ids = os.getenv("TELEGRAM_ADMIN_IDS", "")
ADMIN_USER_ID = int(_admin_ids.split(",")[0]) if _admin_ids else 0

if not TELEGRAM_BOT_TOKEN or not ADMIN_USER_ID:
    raise SystemExit("Missing TELEGRAM_BOT_TOKEN or TELEGRAM_ADMIN_IDS in environment")

# Finance test questions
TEST_QUESTIONS = [
    ("Is SOL bullish?", 5),  # Expected response time in seconds
    ("What's the BTC sentiment?", 8),
    ("Should I buy ETH?", 8),
]

def send_message(msg):
    """Send message to admin."""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": ADMIN_USER_ID,
        "text": msg
    }
    response = requests.post(url, json=payload, timeout=10)
    data = response.json()

    if data.get('ok'):
        return data['result']['message_id']
    return None

def get_latest_updates():
    """Get latest messages."""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
    response = requests.get(url, timeout=10)
    data = response.json()

    if data.get('ok'):
        return data.get('result', [])
    return []

def count_dexter_keywords(text):
    """Count finance keywords in response."""
    keywords = {
        "sentiment", "bullish", "bearish", "confidence",
        "grok", "price", "volume", "analysis", "recommendation"
    }
    text_lower = text.lower()
    found = [kw for kw in keywords if kw in text_lower]
    return found

def monitor_responses(test_count=3):
    """Send test messages and monitor for responses."""
    print("=" * 70)
    print("[MONITOR] BOT RESPONSE MONITORING")
    print("=" * 70)
    print()

    results = {
        "sent": 0,
        "received": 0,
        "dexter_responses": 0,
        "tests": []
    }

    for i, (question, expected_wait) in enumerate(TEST_QUESTIONS[:test_count], 1):
        print(f"[TEST {i}/{test_count}] Testing: '{question}'")

        # Send message
        msg_id = send_message(question)
        if not msg_id:
            print(f"  [ERROR] Failed to send message")
            continue

        results["sent"] += 1
        print(f"  [SENT] Message ID: {msg_id}")
        sent_time = time.time()

        # Get current message count before sending
        before_updates = get_latest_updates()
        initial_count = len(before_updates)

        # Wait for response
        print(f"  [WAIT] Waiting for response (max {expected_wait}s)...")
        response_found = False
        response_text = None

        for wait_sec in range(expected_wait):
            time.sleep(1)
            updates = get_latest_updates()

            if len(updates) > initial_count:
                # New message received
                response_found = True
                response_msg = updates[-1]

                if 'message' in response_msg:
                    response_text = response_msg['message'].get('text', '')
                    elapsed = time.time() - sent_time

                    print(f"  [RESPONSE] Received in {elapsed:.1f}s")
                    print(f"  [TEXT] {response_text[:100]}...")

                    # Check for Dexter keywords
                    keywords = count_dexter_keywords(response_text)
                    if keywords:
                        results["dexter_responses"] += 1
                        print(f"  [DEXTER] Found keywords: {', '.join(keywords)}")
                    else:
                        print(f"  [INFO] No Dexter keywords detected")

                    results["received"] += 1
                    break

        if not response_found:
            print(f"  [TIMEOUT] No response after {expected_wait}s")

        results["tests"].append({
            "question": question,
            "sent": msg_id is not None,
            "received": response_found,
            "response": response_text
        })

        # Wait between tests
        if i < test_count:
            time.sleep(2)
        print()

    # Summary
    print("=" * 70)
    print("[SUMMARY] MONITORING RESULTS")
    print("=" * 70)
    print()
    print(f"Messages Sent: {results['sent']}")
    print(f"Responses Received: {results['received']}")
    print(f"Dexter Responses: {results['dexter_responses']}")
    print()

    if results["received"] > 0:
        success_rate = (results["received"] / results["sent"]) * 100
        print(f"Success Rate: {success_rate:.0f}%")

        if results["dexter_responses"] > 0:
            dexter_rate = (results["dexter_responses"] / results["received"]) * 100
            print(f"Dexter Trigger Rate: {dexter_rate:.0f}%")

    print()
    print("=" * 70)

    if results["received"] == results["sent"] and results["dexter_responses"] > 0:
        print("[STATUS] Monitoring SUCCESSFUL - Dexter responding!")
        return True
    else:
        print("[STATUS] Monitoring showed issues - manual review needed")
        return False

if __name__ == "__main__":
    try:
        success = monitor_responses()
        exit(0 if success else 1)
    except Exception as e:
        print(f"[ERROR] {e}")
        exit(1)
