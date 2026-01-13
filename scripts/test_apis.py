"""Test LunarCrush and CryptoPanic APIs."""
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

# Load env from bots/twitter/.env
env_path = Path(__file__).parent.parent / "bots" / "twitter" / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        if line.strip() and not line.startswith('#') and '=' in line:
            k, v = line.split('=', 1)
            os.environ.setdefault(k.strip(), v.strip())

async def test():
    print("=== Testing APIs ===")
    print(f"LUNARCRUSH_API_KEY set: {bool(os.getenv('LUNARCRUSH_API_KEY'))}")
    print(f"CRYPTOPANIC_API_KEY set: {bool(os.getenv('CRYPTOPANIC_API_KEY'))}")
    
    # Test LunarCrush
    print("\n--- LunarCrush ---")
    try:
        from core.data.lunarcrush_api import get_lunarcrush
        lc = get_lunarcrush()
        sentiment = await lc.get_market_sentiment()
        if sentiment:
            print(f"Market mood: {sentiment.get('market_mood')}")
            print(f"Galaxy score: {sentiment.get('avg_galaxy_score')}")
        else:
            print("No data returned")
    except Exception as e:
        print(f"Error: {e}")
    
    # Test CryptoPanic
    print("\n--- CryptoPanic ---")
    try:
        from core.data.cryptopanic_api import get_cryptopanic
        cp = get_cryptopanic()
        news = await cp.get_news_sentiment()
        if news:
            print(f"News mood: {news.get('market_mood')}")
            print(f"Bullish: {news.get('bullish_count')}, Bearish: {news.get('bearish_count')}")
        else:
            print("No data returned (need API key)")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test())
