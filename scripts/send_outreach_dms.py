"""
Send outreach DMs from Aurora_Ventures account
Uses Puppeteer to control the active Chrome session where Aurora_Ventures is logged in
"""
import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


# Target accounts
ACCOUNTS = [
    "bixbysol",
    "findingmeta",
    "spidercrypto0x"
]

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


async def send_dm_via_browser(username: str, message: str) -> bool:
    """
    Send a DM using the active browser session
    """
    try:
        from mcp__puppeteer__puppeteer_connect_active_tab import mcp__puppeteer__puppeteer_connect_active_tab
        from mcp__puppeteer__puppeteer_navigate import mcp__puppeteer__puppeteer_navigate
        from mcp__puppeteer__puppeteer_click import mcp__puppeteer__puppeteer_click
        from mcp__puppeteer__puppeteer_fill import mcp__puppeteer__puppeteer_fill

        print(f"\n[→] Sending DM to @{username}...")

        # Navigate to DM compose page
        dm_url = f"https://x.com/messages/compose?recipient_id={username}"
        await mcp__puppeteer__puppeteer_navigate({"url": dm_url})

        # Wait a bit for page to load
        await asyncio.sleep(2)

        # Find and fill the message box
        # X uses a contenteditable div for DM composition
        message_selectors = [
            '[data-testid="dmComposerTextInput"]',
            '[aria-label="Message"]',
            '.DraftEditor-editorContainer',
            '[contenteditable="true"][role="textbox"]'
        ]

        filled = False
        for selector in message_selectors:
            try:
                await mcp__puppeteer__puppeteer_fill({
                    "selector": selector,
                    "value": message
                })
                filled = True
                print(f"  ✓ Message composed")
                break
            except Exception as e:
                continue

        if not filled:
            print(f"  ✗ Could not find message input field")
            return False

        # Wait a moment
        await asyncio.sleep(1)

        # Click send button
        send_selectors = [
            '[data-testid="dmComposerSendButton"]',
            '[aria-label="Send"]',
            'button[type="button"]:has-text("Send")'
        ]

        sent = False
        for selector in send_selectors:
            try:
                await mcp__puppeteer__puppeteer_click({"selector": selector})
                sent = True
                print(f"  ✓ DM sent to @{username}!")
                break
            except Exception:
                continue

        if not sent:
            print(f"  ✗ Could not find send button")
            return False

        # Wait before next DM
        await asyncio.sleep(3)
        return True

    except Exception as e:
        print(f"  ✗ Error sending DM to @{username}: {e}")
        return False


async def main():
    """Main outreach function"""
    print("=" * 60)
    print("AURORA VENTURES → OUTREACH DMs")
    print("=" * 60)
    print(f"\nTargets: {', '.join('@' + a for a in ACCOUNTS)}")
    print(f"\nMessage preview:\n{'-' * 60}")
    print(PITCH_MESSAGE[:200] + "..." if len(PITCH_MESSAGE) > 200 else PITCH_MESSAGE)
    print(f"{'-' * 60}\n")

    # Connect to active Chrome session
    print("[→] Connecting to active Chrome session...")
    try:
        from mcp__puppeteer__puppeteer_connect_active_tab import mcp__puppeteer__puppeteer_connect_active_tab

        # Try to connect to X tab (if already open)
        await mcp__puppeteer__puppeteer_connect_active_tab({
            "targetUrl": "https://x.com"
        })
        print("  ✓ Connected to X session")
    except Exception as e:
        print(f"  ! Connection attempt: {e}")
        print("  → Make sure X is open in Chrome with Aurora_Ventures logged in")
        return

    # Send DMs to each account
    results = []
    for username in ACCOUNTS:
        success = await send_dm_via_browser(username, PITCH_MESSAGE)
        results.append((username, success))

        # Respectful delay between sends
        if username != ACCOUNTS[-1]:  # Not the last one
            print(f"  ⏱ Waiting 5 seconds before next DM...")
            await asyncio.sleep(5)

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    successful = sum(1 for _, success in results if success)
    print(f"✓ Sent: {successful}/{len(results)}")
    print(f"✗ Failed: {len(results) - successful}/{len(results)}\n")

    for username, success in results:
        status = "✓" if success else "✗"
        print(f"  {status} @{username}")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
