"""
Send DMs from Aurora_Ventures using Twitter API (tweepy)
More reliable than browser automation
"""
import os
import sys
import asyncio
from pathlib import Path
from dotenv import load_dotenv

# Load environment - check for Aurora credentials
env_file = Path(__file__).parent.parent / "bots" / "twitter" / ".env"
load_dotenv(env_file)

# Check if we have Aurora credentials
AURORA_API_KEY = os.getenv("AURORA_API_KEY") or os.getenv("X_API_KEY")
AURORA_API_SECRET = os.getenv("AURORA_API_SECRET") or os.getenv("X_API_SECRET")
AURORA_ACCESS_TOKEN = os.getenv("AURORA_ACCESS_TOKEN") or os.getenv("X_ACCESS_TOKEN")
AURORA_ACCESS_SECRET = os.getenv("AURORA_ACCESS_SECRET") or os.getenv("X_ACCESS_TOKEN_SECRET")

# Target accounts
ACCOUNTS = ["bixbysol", "findingmeta", "spidercrypto0x"]

# The pitch message
PITCH_MESSAGE = """Hey! Someone in my community recommended I reach out to you - a few people mentioned your name when I was talking about what I'm building.

I wanted to introduce myself and share a bit about my project. No pressure at all, but if you're interested in learning more, let me know.

So here's what I'm working on:

Jarvis started as a crypto product because crypto is where it was born—and where the infrastructure already exists to do things no other industry can do yet.

In its first phase, Jarvis lives natively on Solana. That's intentional. Solana offers a uniquely rich, fully on-chain environment with transparent analytics, high-frequency data, and a diverse set of assets—crypto, pre-stocks, synthetic stocks, leverage, and complex financial instruments—all operating in real time. Jarvis launches with a strong trading and analytics context, built around a tokenized ecosystem, where everything is verifiable, composable, and autonomous by design. This is the proving ground.

But Jarvis is much bigger than a trading product.

At its core, Jarvis is a context engine.

The inspiration is simple: the Iron Man version of Jarvis—the system that quietly upgrades your life. Something that knows you across all of your devices. Something that understands your preferences, your habits, your annoyances, your goals—without you having to configure it, prompt it, or learn how to use it.

We're moving into a world filled with smart devices, smart vehicles, robots, and fragmented AI services. Right now, every AI tool exists in isolation. You have to manage them. Learn them. Orchestrate them. Jarvis flips that model.

Jarvis tracks context across all of your devices and environments, unifying these fragmented AI services into a single operational layer. Instead of you adapting to software, the software adapts to you. It installs things before you even realize you need them. It simplifies AI for people who don't want to become power users, don't want to learn technical workflows, or simply want results without friction.

In that sense, Jarvis levels the playing field. It becomes an operating system for intelligence itself—making advanced AI accessible to the "little guy," not just engineers or specialists.

Technically, Jarvis is designed to be:
• Free
• Self-upgrading
• Always migrating toward the most powerful, compact models available
• Running on a new LLaMA-based node architecture, now made viable through free access to advanced models via Claude

Over time, Jarvis evolves beyond assistance into autonomy.

It doesn't just analyze markets—it trades them. Completely autonomously. On-chain. Transparent. First on Solana, then across other ecosystems. The goal is simple but profound: Jarvis should be able to generate value for its users while they sleep, continuously improving itself, learning from outcomes, and compounding intelligence and capital simultaneously.

Jarvis is not just an app.
It's not just an AI.
It's not just a trading system.

It's a persistent, personal context engine—one that unifies intelligence, automation, finance, and daily life into a single system that quietly works in the background, upgrading itself and upgrading you.

If this sounds interesting, here's where you can learn more:
• https://x.com/kr8tivai
• www.jarvislife.io
• github.com/Matt-Aurora-Ventures/Jarvis

Would love to connect and hear your thoughts! 🚀"""


def send_dm_via_tweepy(client, username: str, message: str) -> bool:
    """Send DM using tweepy (Twitter API v2 events endpoint)"""
    try:
        # Get user ID first
        user = client.get_user(username=username)
        if not user or not user.data:
            print(f"  [-] Could not find user @{username}")
            return False

        user_id = user.data.id

        # Create DM event (v2 API)
        # Note: Requires elevated access for DM creation
        response = client.create_direct_message(
            participant_id=user_id,
            text=message
        )

        if response:
            print(f"  [+] DM sent to @{username} (ID: {user_id})")
            return True
        else:
            print(f"  [-] Failed to send DM to @{username}")
            return False

    except Exception as e:
        error_msg = str(e)
        if "403" in error_msg or "Forbidden" in error_msg:
            print(f"  [-] API access insufficient - DMs require elevated access")
        elif "429" in error_msg:
            print(f"  [-] Rate limit hit - wait before retrying")
        else:
            print(f"  [-] Error sending to @{username}: {error_msg}")
        return False


def main():
    """Main function"""
    print("=" * 70)
    print("AURORA VENTURES - OUTREACH DMs (via Twitter API)")
    print("=" * 70)

    if not all([AURORA_API_KEY, AURORA_API_SECRET, AURORA_ACCESS_TOKEN, AURORA_ACCESS_SECRET]):
        print("\n[-] Missing Aurora Twitter API credentials!")
        print("\nNeed to add to bots/twitter/.env:")
        print("  AURORA_API_KEY=...")
        print("  AURORA_API_SECRET=...")
        print("  AURORA_ACCESS_TOKEN=...")
        print("  AURORA_ACCESS_SECRET=...")
        print("\nOr configure them in your Twitter Developer Portal")
        print("NOTE: Sending DMs requires Elevated API access (not Free tier)")
        return

    try:
        import tweepy
    except ImportError:
        print("\n[-] tweepy not installed")
        print("Run: pip install tweepy")
        return

    # Initialize Twitter client for Aurora account
    print(f"\n[*] Connecting to Twitter API...")
    client = tweepy.Client(
        consumer_key=AURORA_API_KEY,
        consumer_secret=AURORA_API_SECRET,
        access_token=AURORA_ACCESS_TOKEN,
        access_token_secret=AURORA_ACCESS_SECRET
    )

    # Verify auth
    try:
        me = client.get_me()
        if me and me.data:
            print(f"  [+] Authenticated as @{me.data.username}")
            if me.data.username.lower() != "aurora_ventures":
                    print(f"  [!] Warning: Expected @Aurora_Ventures but got @{me.data.username}")
        else:
            print("  [-] Authentication failed")
            return
    except Exception as e:
        print(f"  [-] Auth error: {e}")
        return

    print(f"\n[*] Targets: {', '.join('@' + a for a in ACCOUNTS)}")
    print(f"\n[*] Message length: {len(PITCH_MESSAGE)} characters")
    print(f"\n{'=' * 70}\n")

    # Send DMs
    results = []
    for i, username in enumerate(ACCOUNTS, 1):
        print(f"[{i}/{len(ACCOUNTS)}] Sending to @{username}...")
        success = send_dm_via_tweepy(client, username, PITCH_MESSAGE)
        results.append((username, success))

        # Rate limit protection
        if i < len(ACCOUNTS):
            import time
            print("  [*] Waiting 3 seconds...\n")
            time.sleep(3)

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    successful = sum(1 for _, s in results if s)
    print(f"[+] Sent: {successful}/{len(results)}")
    print(f"[-] Failed: {len(results) - successful}/{len(results)}\n")

    for username, success in results:
        status = "[+]" if success else "[-]"
        print(f"  {status} @{username}")

    print("\n" + "=" * 70)


if __name__ == "__main__":
    main()
