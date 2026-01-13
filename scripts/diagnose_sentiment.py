#!/usr/bin/env python3
"""
Diagnose sentiment bot issues.
"""

import os
import sys
import asyncio
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Manual .env loading
def load_env_manual():
    possible_paths = [
        project_root / ".env",
        project_root / "tg_bot" / ".env",
    ]
    for env_path in possible_paths:
        if not env_path.exists():
            continue
        try:
            content = env_path.read_text(encoding='utf-8')
        except UnicodeDecodeError:
            try:
                content = env_path.read_text(encoding='utf-16')
            except:
                content = env_path.read_text(encoding='latin-1')
        for line in content.splitlines():
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, _, value = line.partition('=')
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and value and key not in os.environ:
                    os.environ[key] = value
        print(f"[OK] Loaded env from: {env_path}")
        return
    print("[WARN] No .env file found!")

load_env_manual()

# Check required env vars
print("\n=== Environment Check ===")
token = os.getenv("TELEGRAM_BOT_TOKEN")
xai_key = os.getenv("XAI_API_KEY")
chat_id = os.getenv("TELEGRAM_BROADCAST_CHAT_ID") or os.getenv("TELEGRAM_BUY_BOT_CHAT_ID")

print(f"TELEGRAM_BOT_TOKEN: {'[OK] Set' if token else '[MISSING]'}")
print(f"XAI_API_KEY: {'[OK] Set' if xai_key else '[MISSING]'}")
print(f"CHAT_ID: {chat_id if chat_id else '[MISSING]'}")

if not all([token, xai_key, chat_id]):
    print("\n[ERROR] Missing required environment variables!")
    sys.exit(1)


async def test_dexscreener():
    """Test DexScreener API connectivity."""
    print("\n=== Testing DexScreener API ===")
    import aiohttp

    try:
        async with aiohttp.ClientSession() as session:
            url = "https://api.dexscreener.com/token-boosts/top/v1"
            async with session.get(url, timeout=10) as resp:
                print(f"Status: {resp.status}")
                if resp.status == 200:
                    data = await resp.json()
                    solana_tokens = [t for t in data if t.get("chainId") == "solana"]
                    print(f"[OK] Got {len(solana_tokens)} Solana tokens from trending")
                    if solana_tokens:
                        print(f"    First token: {solana_tokens[0].get('tokenAddress', 'unknown')[:20]}...")
                else:
                    print(f"[ERROR] Bad response: {await resp.text()}")
    except Exception as e:
        print(f"[ERROR] DexScreener failed: {e}")


async def test_grok_api():
    """Test Grok API connectivity."""
    print("\n=== Testing Grok (xAI) API ===")
    import aiohttp

    try:
        async with aiohttp.ClientSession() as session:
            url = "https://api.x.ai/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {xai_key}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": "grok-3-mini",
                "messages": [{"role": "user", "content": "Say 'OK' if you can hear me."}],
                "max_tokens": 10
            }
            async with session.post(url, headers=headers, json=payload, timeout=15) as resp:
                print(f"Status: {resp.status}")
                if resp.status == 200:
                    data = await resp.json()
                    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                    print(f"[OK] Grok responded: {content}")
                else:
                    error_text = await resp.text()
                    print(f"[ERROR] Grok API error: {error_text[:200]}")
    except Exception as e:
        print(f"[ERROR] Grok API failed: {e}")


async def test_sentiment_generator():
    """Test the full SentimentReportGenerator."""
    print("\n=== Testing SentimentReportGenerator ===")

    try:
        from bots.buy_tracker.sentiment_report import SentimentReportGenerator
        print("[OK] SentimentReportGenerator imported successfully")
    except ImportError as e:
        print(f"[ERROR] Failed to import SentimentReportGenerator: {e}")
        return

    import aiohttp

    try:
        generator = SentimentReportGenerator(
            bot_token=token,
            chat_id=chat_id,
            xai_api_key=xai_key,
            interval_minutes=30,
        )
        print("[OK] Generator created")

        # Create session
        generator._session = aiohttp.ClientSession()
        print("[OK] Session created")

        try:
            # Test getting trending tokens
            print("\nFetching trending tokens...")
            tokens = await generator._get_trending_tokens(limit=5)
            print(f"[OK] Got {len(tokens)} trending tokens:")
            for t in tokens:
                print(f"    - {t.symbol}: ${t.price_usd:.6f} ({t.change_24h:+.1f}% 24h)")

            if tokens:
                # Test Grok scoring on first token
                print("\nTesting Grok token scoring...")
                await generator._get_grok_token_scores([tokens[0]])
                print(f"[OK] Grok score for {tokens[0].symbol}: {tokens[0].grok_score:.2f}")
                print(f"    Verdict: {tokens[0].grok_verdict}")
                print(f"    Reasoning: {tokens[0].grok_reasoning[:100]}...")

            # Try generating the full report
            print("\nGenerating and posting full report...")
            await generator.generate_and_post_report()
            print("[OK] Report generated and posted!")

        finally:
            await generator._session.close()

    except Exception as e:
        import traceback
        print(f"[ERROR] Generator test failed: {e}")
        traceback.print_exc()


async def main():
    print("=" * 50)
    print("JARVIS Sentiment Bot Diagnostic")
    print("=" * 50)

    await test_dexscreener()
    await test_grok_api()
    await test_sentiment_generator()

    print("\n" + "=" * 50)
    print("Diagnostic complete!")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
