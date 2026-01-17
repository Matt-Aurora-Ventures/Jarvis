"""
Run Jarvis Autonomous Twitter Bot

This script starts the fully autonomous Twitter posting engine.
Posts hourly with variety in content types.

Usage:
    python run_autonomous.py              # Run continuously
    python run_autonomous.py --test       # Test content generation
    python run_autonomous.py --once       # Post once and exit
    python run_autonomous.py --status     # Show engine status
"""

import asyncio
import argparse
import logging
import os
import sys
from pathlib import Path

# Setup
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load env
env_path = Path(__file__).parent / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        if line.strip() and not line.startswith('#') and '=' in line:
            k, v = line.split('=', 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"'))


async def test_generation():
    """Test all content generators."""
    from bots.twitter.autonomous_engine import get_autonomous_engine
    
    engine = get_autonomous_engine()
    
    try:
        print("\n" + "="*60)
        print("JARVIS AUTONOMOUS TWITTER - CONTENT TEST")
        print("="*60)
        
        print("\n--- Market Update ---")
        draft = await engine.generate_market_update()
        if draft:
            print(f"Content: {draft.content}")
            print(f"Cashtags: {draft.cashtags}")
            print(f"Contract: {draft.contract_address}")
        else:
            print("Failed to generate")
        
        print("\n--- Trending Token ---")
        draft = await engine.generate_trending_token_call()
        if draft:
            print(f"Content: {draft.content}")
            print(f"Category: {draft.category}")
        else:
            print("Failed to generate")
        
        print("\n--- Agentic Thought ---")
        draft = await engine.generate_agentic_thought()
        if draft:
            print(f"Content: {draft.content}")
        else:
            print("Failed to generate")
        
        print("\n--- Hourly Update ---")
        draft = await engine.generate_hourly_update()
        if draft:
            print(f"Content: {draft.content}")
        else:
            print("Failed to generate")
            
        print("\n--- Quote Tweet ---")
        draft = await engine.generate_quote_tweet()
        if draft:
            print(f"Content: {draft.content}")
            print(f"Quote ID: {draft.quote_tweet_id}")
        else:
            print("Skipped (no candidates or error)")
            
        print("\n--- Autonomous Thread ---")
        thread = await engine.generate_autonomous_thread()
        if thread:
            print(f"Topic: {thread.topic}")
            print(f"Tweets: {len(thread.tweets)}")
            for t in thread.tweets:
                print(f"[{t.position}] {t.content[:50]}...")
        else:
            print("Failed to generate")
        
        print("\n" + "="*60)
        print("TEST COMPLETE")
        print("="*60)
    finally:
        if hasattr(engine, 'cleanup'):
            await engine.cleanup()


async def post_once():
    """Post a single tweet."""
    from bots.twitter.autonomous_engine import get_autonomous_engine
    
    engine = get_autonomous_engine()
    engine._last_post_time = 0  # Force immediate post
    
    try:
        print("\nGenerating and posting tweet...")
        tweet_id = await engine.run_once()
        
        if tweet_id:
            print(f"SUCCESS: Posted tweet {tweet_id}")
            print(f"URL: https://x.com/Jarvis_lifeos/status/{tweet_id}")
        else:
            print("FAILED: No tweet posted")
    finally:
        if hasattr(engine, 'cleanup'):
            await engine.cleanup()


async def show_status():
    """Show engine status."""
    from bots.twitter.autonomous_engine import get_autonomous_engine
    
    engine = get_autonomous_engine()
    
    try:
        status = engine.get_status()
        
        print("\n" + "="*60)
        print("JARVIS AUTONOMOUS TWITTER - STATUS")
        print("="*60)
        print(f"Running: {status['running']}")
        print(f"Post Interval: {status['post_interval']}s ({status['post_interval']//60} min)")
        print(f"Total Tweets: {status['total_tweets']}")
        print(f"Today's Tweets: {status['today_tweets']}")
        print(f"\nBy Category:")
        for cat, count in status.get('by_category', {}).items():
            print(f"  {cat}: {count}")
        print(f"\nImage Params:")
        for k, v in status.get('image_params', {}).items():
            print(f"  {k}: {v}")
        print("="*60)
    finally:
        if hasattr(engine, 'cleanup'):
            await engine.cleanup()


async def run_continuously():
    """Run the autonomous engine continuously with vibe coding support."""
    from bots.twitter.autonomous_engine import get_autonomous_engine
    from bots.twitter.x_claude_cli_handler import get_x_claude_cli_handler
    from core.secrets import validate_required_keys, print_key_status

    # Validate API keys before starting
    print("\n" + "="*60)
    print("JARVIS AUTONOMOUS TWITTER ENGINE")
    print("="*60)

    print("\nChecking API keys...")
    print_key_status()

    success, missing = validate_required_keys(["anthropic", "grok", "twitter"])
    if not success:
        print(f"\nWARNING: Missing required API keys: {', '.join(missing)}")
        print("Some features may be limited.")
    else:
        print("All required keys configured.")

    engine = get_autonomous_engine()
    cli_handler = get_x_claude_cli_handler()

    print(f"\nPosting interval: {engine._post_interval}s")
    print("Vibe coding: ENABLED (@aurora_ventures can code via mentions)")
    print("Press Ctrl+C to stop")
    print("="*60 + "\n")

    try:
        # Run both the engine and CLI monitor concurrently
        await asyncio.gather(
            engine.run(),
            cli_handler.run(),
            return_exceptions=True
        )
    except KeyboardInterrupt:
        print("\nStopping engine...")
    except Exception as e:
        print(f"\n[ERROR] Engine crashed: {e}")
        import traceback
        traceback.print_exc()
        # Notify via Telegram if possible
        try:
            import aiohttp
            import os
            token = os.getenv("TG_BOT_TOKEN")
            chat_id = os.getenv("TG_CHAT_ID")
            if token and chat_id:
                async with aiohttp.ClientSession() as session:
                    await session.post(
                        f"https://api.telegram.org/bot{token}/sendMessage",
                        json={"chat_id": chat_id, "text": f"JARVIS X ENGINE CRASHED: {str(e)[:200]}"}
                    )
        except Exception:
            pass
    finally:
        engine.stop()
        cli_handler.stop()
        if hasattr(engine, 'cleanup'):
            await engine.cleanup()



def main():
    parser = argparse.ArgumentParser(description="Jarvis Autonomous Twitter Bot")
    parser.add_argument("--test", action="store_true", help="Test content generation")
    parser.add_argument("--once", action="store_true", help="Post once and exit")
    parser.add_argument("--status", action="store_true", help="Show engine status")
    parser.add_argument("--interval", type=int, default=3600, help="Post interval in seconds")
    
    args = parser.parse_args()

    # Start metrics server (best-effort)
    try:
        from core.monitoring.metrics import start_metrics_server
        start_metrics_server()
    except Exception as exc:
        logger.warning(f"Metrics server unavailable: {exc}")
    
    if args.test:
        asyncio.run(test_generation())
    elif args.once:
        asyncio.run(post_once())
    elif args.status:
        asyncio.run(show_status())
    else:
        # Set interval if provided
        if args.interval != 3600:
            from bots.twitter.autonomous_engine import get_autonomous_engine
            engine = get_autonomous_engine()
            engine.set_post_interval(args.interval)
        
        asyncio.run(run_continuously())


if __name__ == "__main__":
    main()
