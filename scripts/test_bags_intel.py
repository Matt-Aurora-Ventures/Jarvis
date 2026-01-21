#!/usr/bin/env python3
"""Test script for Bags Intel Bitquery connection."""

import asyncio
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

# Load env files (tg_bot/.env has main credentials, root .env has bitquery)
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(project_root, "tg_bot", ".env"))  # Main credentials
load_dotenv(os.path.join(project_root, ".env"))  # Bitquery key


async def test_bitquery_connection():
    """Test Bitquery WebSocket connection."""
    import json
    import websockets

    api_key = os.environ.get("BITQUERY_API_KEY")
    if not api_key:
        print("ERROR: BITQUERY_API_KEY not set in environment")
        return False

    print(f"API Key: {api_key[:20]}...{api_key[-10:]}")
    print("\nTesting Bitquery WebSocket connection...")

    ws_url = "wss://streaming.bitquery.io/graphql"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        async with websockets.connect(
            ws_url,
            additional_headers=headers,
            subprotocols=["graphql-ws"],
            ping_interval=30,
            ping_timeout=10,
        ) as ws:
            # Init connection
            await ws.send(json.dumps({"type": "connection_init", "payload": {}}))
            response = await asyncio.wait_for(ws.recv(), timeout=10)
            data = json.loads(response)

            if data.get("type") == "connection_ack":
                print("SUCCESS: Connected to Bitquery WebSocket!")
                print(f"Response: {data}")

                # Try a simple subscription to verify it works
                test_query = """
                subscription TestConnection {
                  Solana {
                    Blocks(limit: {count: 1}) {
                      Block {
                        Slot
                        Time
                      }
                    }
                  }
                }
                """

                await ws.send(json.dumps({
                    "id": "test",
                    "type": "subscribe",
                    "payload": {"query": test_query}
                }))

                print("\nWaiting for first block event (10s timeout)...")
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=10)
                    msg_data = json.loads(msg)
                    print(f"Received: {json.dumps(msg_data, indent=2)[:500]}")
                    return True
                except asyncio.TimeoutError:
                    print("No block event within 10s (normal for streaming)")
                    return True
            else:
                print(f"FAILED: Connection not acknowledged: {data}")
                return False

    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {e}")
        return False


async def test_dexscreener():
    """Test DexScreener API (used as fallback)."""
    import aiohttp

    print("\n" + "="*50)
    print("Testing DexScreener API...")

    # Test with a known token
    test_mint = "So11111111111111111111111111111111111111112"  # Wrapped SOL
    url = f"https://api.dexscreener.com/latest/dex/tokens/{test_mint}"

    async with aiohttp.ClientSession() as session:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            if resp.status == 200:
                data = await resp.json()
                pairs = data.get("pairs", [])
                print(f"SUCCESS: DexScreener returned {len(pairs)} pairs for WSOL")
                if pairs:
                    print(f"Top pair: {pairs[0].get('dexId')} - ${pairs[0].get('priceUsd', 'N/A')}")
                return True
            else:
                print(f"FAILED: DexScreener returned {resp.status}")
                return False


async def test_config():
    """Test bags_intel config loading."""
    print("\n" + "="*50)
    print("Testing Bags Intel config...")

    try:
        from bots.bags_intel.config import load_config
        config = load_config()

        print(f"Bitquery API Key: {'SET' if config.bitquery_api_key else 'NOT SET'}")
        print(f"Telegram Token: {'SET' if config.telegram_bot_token else 'NOT SET'}")
        print(f"Telegram Chat: {config.telegram_chat_id or 'NOT SET'}")
        print(f"Twitter Bearer: {'SET' if config.twitter_bearer_token else 'NOT SET'}")
        print(f"xAI API Key: {'SET' if config.xai_api_key else 'NOT SET'}")
        print(f"Min MCap: ${config.min_graduation_mcap:,.0f}")
        print(f"Min Score: {config.min_score_to_report}")
        print(f"Is Configured: {config.is_configured}")

        return True
    except Exception as e:
        print(f"ERROR: {e}")
        return False


async def main():
    print("="*50)
    print("BAGS INTEL CONNECTION TEST")
    print("="*50)

    results = []

    # Test config
    results.append(("Config", await test_config()))

    # Test DexScreener
    results.append(("DexScreener", await test_dexscreener()))

    # Test Bitquery
    results.append(("Bitquery", await test_bitquery_connection()))

    print("\n" + "="*50)
    print("RESULTS")
    print("="*50)
    for name, passed in results:
        status = "PASS" if passed else "FAIL"
        print(f"  {name}: {status}")

    all_passed = all(r[1] for r in results)
    print("\n" + ("ALL TESTS PASSED!" if all_passed else "SOME TESTS FAILED"))
    return all_passed


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
