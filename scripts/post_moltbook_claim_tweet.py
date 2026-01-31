#!/usr/bin/env python3
"""Post Moltbook verification tweet"""
import asyncio
import sys
import os
from pathlib import Path

# Add parent directory to path to import from bots/
sys.path.insert(0, str(Path(__file__).parent.parent))

from bots.twitter.twitter_client import TwitterClient

async def main():
    """Post the Moltbook verification tweet"""
    tweet_text = """I'm claiming my AI agent "ClawdMatt" on @moltbook 🦞

Verification: shell-WZ96"""

    print("[OK] Initializing Twitter client...")
    client = TwitterClient()

    if not client.connect():
        print("[ERROR] Failed to connect to Twitter", file=sys.stderr)
        sys.exit(1)

    print(f"[OK] Connected as @{client.username}")
    print(f"[OK] Posting verification tweet...")

    result = await client.post_tweet(tweet_text, sync_to_telegram=False)

    if result.success:
        print(f"[OK] Tweet posted successfully!")
        print(f"[OK] URL: {result.url}")
        print(f"[OK] Tweet ID: {result.tweet_id}")
        print()
        print("[OK] Now complete the claim on Moltbook:")
        print("     1. Click 'Verify on Twitter' on the claim page")
        print("     2. Paste the tweet URL when prompted")
        print("     3. Complete the verification")
    else:
        print(f"[ERROR] Failed to post tweet: {result.error}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
