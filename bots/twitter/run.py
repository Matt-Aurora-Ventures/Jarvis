"""
JARVIS Twitter Bot Runner
Start the bot with this script
"""

import os
import sys
import asyncio
import argparse
import logging
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from dotenv import load_dotenv

# Load environment variables
env_path = Path(__file__).parent / ".env"
if env_path.exists():
    load_dotenv(env_path)
else:
    # Try parent directories
    for parent in [Path(__file__).parent.parent, Path(__file__).parent.parent.parent]:
        env_file = parent / ".env"
        if env_file.exists():
            load_dotenv(env_file)
            break

from bots.twitter.bot import JarvisTwitterBot, BotConfig
from bots.twitter.config import BotConfiguration, print_env_template, check_config


def setup_logging(verbose: bool = False):
    """Configure logging"""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s | %(name)s | %(levelname)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )


async def run_bot(args):
    """Run the Twitter bot"""
    config = BotConfig(
        timezone_offset=args.timezone
    )

    bot = JarvisTwitterBot(config=config)
    await bot.start()


async def post_once(args):
    """Post a single tweet and exit"""
    from bots.twitter.twitter_client import TwitterClient
    from bots.twitter.grok_client import GrokClient
    from bots.twitter.content import ContentGenerator
    from bots.twitter.personality import JarvisPersonality

    twitter = TwitterClient()
    if not twitter.connect():
        print("Failed to connect to Twitter")
        return

    grok = GrokClient()
    personality = JarvisPersonality()
    content_gen = ContentGenerator(grok, personality)

    content = await content_gen.generate_scheduled_content(args.hour)
    if content:
        result = await twitter.post_tweet(content.text)
        if result.success:
            print(f"Tweet posted: {result.url}")
        else:
            print(f"Failed: {result.error}")
    else:
        print("No content generated")

    await content_gen.close()


async def test_content(args):
    """Test content generation without posting"""
    from bots.twitter.grok_client import GrokClient
    from bots.twitter.content import ContentGenerator
    from bots.twitter.personality import JarvisPersonality

    grok = GrokClient()
    personality = JarvisPersonality()
    content_gen = ContentGenerator(grok, personality)

    print("\n" + "=" * 50)
    print("Testing content generation")
    print("=" * 50)

    # Test each content type
    types = [
        ("Morning Report", content_gen.generate_morning_report),
        ("Token Spotlight", content_gen.generate_token_spotlight),
        ("Stock Picks", content_gen.generate_stock_picks_tweet),
        ("Macro Update", content_gen.generate_macro_update),
        ("Commodities", content_gen.generate_commodities_tweet),
        ("Grok Insight", content_gen.generate_grok_insight),
        ("Evening Wrap", content_gen.generate_evening_wrap)
    ]

    for name, generator in types:
        print(f"\n--- {name} ---")
        try:
            content = await generator()
            print(f"Type: {content.content_type}")
            print(f"Mood: {content.mood.value}")
            print(f"Text ({len(content.text)} chars):")
            print(content.text)
            print(f"Include image: {content.should_include_image}")
        except Exception as e:
            print(f"Error: {e}")

    await content_gen.close()
    print("\n" + "=" * 50)
    print("Content test complete")


def main():
    parser = argparse.ArgumentParser(
        description="JARVIS Twitter Bot",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run.py                     Start the bot
  python run.py --timezone -5       Start with EST timezone
  python run.py post --hour 8       Post morning report
  python run.py test                Test content generation
  python run.py config              Check configuration
  python run.py env                 Print env template
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Run command (default)
    run_parser = subparsers.add_parser("run", help="Run the bot (default)")
    run_parser.add_argument("--timezone", type=int, default=0, help="Timezone offset from UTC")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Verbose logging")

    # Post command
    post_parser = subparsers.add_parser("post", help="Post a single tweet")
    post_parser.add_argument("--hour", type=int, default=8, help="Hour to simulate (8, 10, 12, 14, 16, 18, 20)")

    # Test command
    test_parser = subparsers.add_parser("test", help="Test content generation")

    # Config command
    config_parser = subparsers.add_parser("config", help="Check configuration")

    # Env command
    env_parser = subparsers.add_parser("env", help="Print environment template")

    # Default args
    parser.add_argument("--timezone", type=int, default=0, help="Timezone offset from UTC")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose logging")

    args = parser.parse_args()

    # Setup logging
    setup_logging(getattr(args, "verbose", False))

    # Handle commands
    if args.command == "env":
        print_env_template()
        return

    if args.command == "config":
        check_config()
        return

    if args.command == "test":
        asyncio.run(test_content(args))
        return

    if args.command == "post":
        asyncio.run(post_once(args))
        return

    # Default: run the bot
    print("""
    ╔═══════════════════════════════════════════════════╗
    ║                                                   ║
    ║        JARVIS Twitter Bot                         ║
    ║        Chrome Humanoid AI                         ║
    ║                                                   ║
    ╚═══════════════════════════════════════════════════╝
    """)

    if not check_config():
        print("\nPlease fix configuration before running")
        print("Run: python run.py env")
        return

    asyncio.run(run_bot(args))


if __name__ == "__main__":
    main()
