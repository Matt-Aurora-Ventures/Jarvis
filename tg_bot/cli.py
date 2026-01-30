"""
Jarvis Telegram Bot CLI

Control your Telegram bot from the command line.

Usage:
    python cli.py start          # Start the bot
    python cli.py status         # Check bot status
    python cli.py getid          # Instructions to get your Telegram ID
    python cli.py setid <id>     # Set your admin ID
    python cli.py test           # Test API connections
    python cli.py send <msg>     # Send message to yourself (requires admin ID)
    python cli.py digest         # Generate and print a digest
    python cli.py costs          # Show API costs
"""

import argparse
import asyncio
import os
import sys
from pathlib import Path

# Load .env file
def load_env():
    """Load environment from .env file."""
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    if value and value not in ("", "None"):
                        os.environ[key] = value
        print(f"Loaded config from {env_path}")
    else:
        print(f"No .env file found at {env_path}")

# Load env before other imports
load_env()

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from tg_bot.config import get_config, reload_config


def cmd_start(args):
    """Start the Telegram bot."""
    print("\n" + "=" * 50)
    print("Starting Jarvis Telegram Bot...")
    print("=" * 50)

    config = get_config()

    if not config.telegram_token:
        print("\nERROR: TELEGRAM_BOT_TOKEN not set in .env")
        return 1

    if not config.admin_ids:
        print("\nWARNING: No admin ID set!")
        print("Run: python cli.py getid")
        print("Then: python cli.py setid YOUR_ID")

    # Import and run bot
    from tg_bot.bot import main
    main()


def cmd_status(args):
    """Check configuration and API status."""
    config = get_config()

    print("\n" + "=" * 50)
    print("JARVIS BOT STATUS")
    print("=" * 50)

    print(f"\nTelegram Token: {'[OK] Set' if config.telegram_token else '[X] Missing'}")
    print(f"Admin IDs: {config.admin_ids if config.admin_ids else '[X] Not set'}")
    print(f"Grok API: {'[OK] Set' if config.has_grok() else '[X] Missing'}")
    print(f"Birdeye API: {'[OK] Set' if config.birdeye_api_key else '[X] Missing'}")
    print(f"Claude API: {'[OK] Set' if config.has_claude() else '[-] Optional'}")

    # Check core modules
    print("\nData Sources:")
    try:
        from tg_bot.services.signal_service import get_signal_service
        service = get_signal_service()
        sources = service.get_available_sources()
        for src in sources:
            print(f"  [OK] {src}")
        if not sources:
            print("  [X] No sources available")
    except Exception as e:
        print(f"  [X] Error loading: {e}")

    print()


def cmd_getid(args):
    """Show instructions to get Telegram user ID."""
    print("\n" + "=" * 50)
    print("HOW TO GET YOUR TELEGRAM USER ID")
    print("=" * 50)
    print("""
1. Open Telegram on your phone or desktop

2. Search for: @userinfobot

3. Start a chat and send any message

4. The bot will reply with your info:

   Id: 123456789  <-- This is your user ID
   First: YourName
   Lang: en

5. Copy the Id number and run:

   python cli.py setid 123456789

That's it! You'll then be the admin of your bot.
""")


def cmd_setid(args):
    """Set admin ID in .env file."""
    if not args.user_id:
        print("Usage: python cli.py setid YOUR_USER_ID")
        print("Example: python cli.py setid 123456789")
        return 1

    user_id = args.user_id

    # Validate it's a number
    if not user_id.isdigit():
        print(f"ERROR: '{user_id}' is not a valid user ID (must be numbers only)")
        return 1

    env_path = Path(__file__).parent / ".env"

    if not env_path.exists():
        print(f"ERROR: .env file not found at {env_path}")
        return 1

    # Read current content
    with open(env_path) as f:
        content = f.read()

    # Update or add TELEGRAM_ADMIN_IDS
    if "TELEGRAM_ADMIN_IDS=" in content:
        lines = content.split("\n")
        new_lines = []
        for line in lines:
            if line.startswith("TELEGRAM_ADMIN_IDS="):
                new_lines.append(f"TELEGRAM_ADMIN_IDS={user_id}")
            else:
                new_lines.append(line)
        content = "\n".join(new_lines)
    else:
        content += f"\nTELEGRAM_ADMIN_IDS={user_id}\n"

    # Write back
    with open(env_path, "w") as f:
        f.write(content)

    print(f"\n[OK] Admin ID set to: {user_id}")
    print("\nYou can now start the bot with:")
    print("  python cli.py start")


def cmd_test(args):
    """Test API connections."""
    print("\n" + "=" * 50)
    print("TESTING API CONNECTIONS")
    print("=" * 50)

    config = get_config()

    # Test Telegram
    print("\n1. Telegram Bot API...")
    if config.telegram_token:
        try:
            import requests
            resp = requests.get(
                f"https://api.telegram.org/bot{config.telegram_token}/getMe",
                timeout=10
            )
            data = resp.json()
            if data.get("ok"):
                bot = data["result"]
                print(f"   [OK] Connected as @{bot.get('username')}")
            else:
                print(f"   [X] Error: {data.get('description')}")
        except Exception as e:
            print(f"   [X] Failed: {e}")
    else:
        print("   [X] No token set")

    # Test Grok
    print("\n2. Grok/xAI API...")
    if config.has_grok():
        try:
            import requests
            resp = requests.post(
                "https://api.x.ai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {config.grok_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "grok-4",
                    "messages": [{"role": "user", "content": "Say 'test ok' in 2 words"}],
                    "max_tokens": 10,
                },
                timeout=30
            )
            if resp.status_code == 200:
                print("   [OK] Grok API connected")
            else:
                print(f"   [X] Error {resp.status_code}: {resp.text[:100]}")
        except Exception as e:
            print(f"   [X] Failed: {e}")
    else:
        print("   [X] No XAI_API_KEY set")

    # Test Birdeye
    print("\n3. Birdeye API...")
    if config.birdeye_api_key:
        try:
            import requests
            resp = requests.get(
                "https://public-api.birdeye.so/defi/price?address=So11111111111111111111111111111111111111112",
                headers={"X-API-KEY": config.birdeye_api_key},
                timeout=10
            )
            if resp.status_code == 200:
                data = resp.json()
                if data.get("success"):
                    price = data.get("data", {}).get("value", 0)
                    print(f"   [OK] Connected (SOL = ${price:.2f})")
                else:
                    print("   [X] API returned error")
            else:
                print(f"   [X] Error {resp.status_code}")
        except Exception as e:
            print(f"   [X] Failed: {e}")
    else:
        print("   [-] Not configured (optional)")

    print()


def cmd_send(args):
    """Send a test message to yourself."""
    if not args.message:
        print("Usage: python cli.py send 'Your message here'")
        return 1

    config = get_config()

    if not config.telegram_token:
        print("ERROR: No Telegram token set")
        return 1

    if not config.admin_ids:
        print("ERROR: No admin ID set. Run: python cli.py setid YOUR_ID")
        return 1

    import requests

    admin_id = list(config.admin_ids)[0]
    message = args.message

    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{config.telegram_token}/sendMessage",
            json={
                "chat_id": admin_id,
                "text": message,
                "parse_mode": "Markdown",
            },
            timeout=10
        )
        data = resp.json()
        if data.get("ok"):
            print(f"[OK] Message sent to {admin_id}")
        else:
            print(f"[X] Error: {data.get('description')}")
            if "chat not found" in str(data.get("description", "")).lower():
                print("\nYou need to start a chat with your bot first!")
                print("1. Find your bot on Telegram (search for its username)")
                print("2. Click 'Start' or send /start")
                print("3. Try this command again")
    except Exception as e:
        print(f"[X] Failed: {e}")


def cmd_costs(args):
    """Show API cost report."""
    try:
        from tg_bot.services.cost_tracker import get_tracker
        tracker = get_tracker()
        print(tracker.get_cost_report())
    except Exception as e:
        print(f"Error: {e}")


def cmd_digest(args):
    """Generate and print a digest."""
    print("Generating digest...")

    async def run():
        try:
            from tg_bot.services.signal_service import get_signal_service
            from tg_bot.services import digest_formatter as fmt

            service = get_signal_service()
            signals = await service.get_trending_tokens(limit=5)

            if signals:
                print(fmt.format_hourly_digest(signals, title="CLI Digest"))
            else:
                print("No signals available. Check /status for issues.")
        except Exception as e:
            print(f"Error: {e}")

    asyncio.run(run())


def main():
    parser = argparse.ArgumentParser(
        description="Jarvis Telegram Bot CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python cli.py start          Start the bot
  python cli.py getid          How to get your Telegram ID
  python cli.py setid 123456   Set your admin ID
  python cli.py test           Test all API connections
  python cli.py send "Hello"   Send yourself a message
  python cli.py costs          Show API usage costs
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # start
    subparsers.add_parser("start", help="Start the Telegram bot")

    # status
    subparsers.add_parser("status", help="Check configuration status")

    # getid
    subparsers.add_parser("getid", help="Instructions to get your Telegram ID")

    # setid
    setid_parser = subparsers.add_parser("setid", help="Set your admin ID")
    setid_parser.add_argument("user_id", nargs="?", help="Your Telegram user ID")

    # test
    subparsers.add_parser("test", help="Test API connections")

    # send
    send_parser = subparsers.add_parser("send", help="Send a message to yourself")
    send_parser.add_argument("message", nargs="?", help="Message to send")

    # costs
    subparsers.add_parser("costs", help="Show API cost report")

    # digest
    subparsers.add_parser("digest", help="Generate a digest")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    commands = {
        "start": cmd_start,
        "status": cmd_status,
        "getid": cmd_getid,
        "setid": cmd_setid,
        "test": cmd_test,
        "send": cmd_send,
        "costs": cmd_costs,
        "digest": cmd_digest,
    }

    if args.command in commands:
        commands[args.command](args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
