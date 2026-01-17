#!/usr/bin/env python3
"""Get current market snapshot for tweet drafting."""

import asyncio
import aiohttp

async def get_market_data():
    async with aiohttp.ClientSession() as session:
        # Get BTC/SOL prices
        try:
            url = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,solana,ethereum&vs_currencies=usd&include_24hr_change=true"
            async with session.get(url, timeout=10) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    print("=== MAJOR COINS ===")
                    btc = data.get("bitcoin", {})
                    sol = data.get("solana", {})
                    eth = data.get("ethereum", {})
                    print(f"BTC: ${btc.get('usd', 0):,.0f} ({btc.get('usd_24h_change', 0):+.1f}%)")
                    print(f"ETH: ${eth.get('usd', 0):,.0f} ({eth.get('usd_24h_change', 0):+.1f}%)")
                    print(f"SOL: ${sol.get('usd', 0):,.0f} ({sol.get('usd_24h_change', 0):+.1f}%)")
        except Exception as e:
            print(f"CoinGecko error: {e}")

        # Get trending Solana tokens
        print("\n=== TRENDING SOLANA ===")
        try:
            async with session.get("https://api.dexscreener.com/token-boosts/top/v1", timeout=10) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    solana_tokens = [t for t in data if t.get("chainId") == "solana"][:8]
                    for t in solana_tokens:
                        addr = t.get("tokenAddress", "")
                        try:
                            async with session.get(f"https://api.dexscreener.com/latest/dex/tokens/{addr}", timeout=5) as pr:
                                if pr.status == 200:
                                    pd = await pr.json()
                                    pairs = pd.get("pairs", [])
                                    if pairs:
                                        p = pairs[0]
                                        sym = p.get("baseToken", {}).get("symbol", "???")
                                        price = float(p.get("priceUsd", 0) or 0)
                                        change = p.get("priceChange", {}).get("h24", 0) or 0
                                        mcap = p.get("marketCap", 0) or p.get("fdv", 0) or 0
                                        vol = p.get("volume", {}).get("h24", 0) or 0
                                        print(f"{sym}: ${price:.6f} ({change:+.0f}%) | MC: ${mcap/1000:.0f}K | Vol: ${vol/1000:.0f}K")
                        except Exception:  # noqa: BLE001 - intentional catch-all
                            pass
                        await asyncio.sleep(0.1)
        except Exception as e:
            print(f"DexScreener error: {e}")

        # Fear & Greed
        print("\n=== SENTIMENT ===")
        try:
            async with session.get("https://api.alternative.me/fng/", timeout=5) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    fng = data.get("data", [{}])[0]
                    print(f"Fear & Greed: {fng.get('value', 'N/A')} ({fng.get('value_classification', 'N/A')})")
        except Exception as e:
            print(f"FNG error: {e}")

asyncio.run(get_market_data())
