#!/usr/bin/env python3
"""
Simple Momentum Trader - Find and execute on momentum plays
Quick in, quick out with 25% TP / 30% SL
"""

import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

TARGET = 100.0
TP_PCT = 0.25  # 25% take profit
SL_PCT = 0.30  # 30% stop loss


async def get_usdc_balance():
    """Get actual USDC balance from wallet."""
    from solana.rpc.async_api import AsyncClient
    from core import solana_wallet, solana_execution
    
    kp = solana_wallet.load_keypair()
    endpoints = solana_execution.load_solana_rpc_endpoints()
    
    usdc_mint = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
    
    async with AsyncClient(endpoints[0].url) as client:
        try:
            resp = await client.get_token_accounts_by_owner(
                kp.pubkey(),
                {"mint": usdc_mint},
            )
            if resp.value:
                for item in resp.value:
                    amount = float(item.account.data.parsed["info"]["tokenAmount"]["uiAmount"] or 0)
                    if amount > 0:
                        return amount
        except:
            pass
    return 0.0


async def find_momentum_token():
    """Find best momentum token from DexScreener."""
    import requests
    
    print("🔍 Scanning DexScreener...", flush=True)
    
    resp = requests.get("https://api.dexscreener.com/latest/dex/search/?q=SOL", timeout=15)
    if not resp.ok:
        return None
    
    data = resp.json()
    pairs = data.get("pairs", [])
    
    best_score = 0
    best_token = None
    
    for p in [p for p in pairs if p.get("chainId") == "solana"][:50]:
        base = p.get("baseToken", {})
        symbol = base.get("symbol", "")
        mint = base.get("address", "")
        
        if not symbol or len(symbol) < 2:
            continue
        
        liq = float(p.get("liquidity", {}).get("usd", 0))
        vol = float(p.get("volume", {}).get("h24", 0))
        price = float(p.get("priceUsd", 0))
        
        # Filters
        if not (10_000 < liq < 1_000_000):
            continue
        if vol < 100_000:
            continue
        
        # Get momentum
        pc = p.get("priceChange", {})
        m5 = float(pc.get("m5", 0))
        h1 = float(pc.get("h1", 0))
        h6 = float(pc.get("h6", 0))
        h24 = float(pc.get("h24", 0))
        
        # Need momentum
        if not (m5 > 2 or h1 > 5 or h6 > 10 or abs(h24) > 15):
            continue
        
        # Score
        score = (abs(m5) * 0.4 + abs(h1) * 0.3 + abs(h6) * 0.2 + abs(h24) * 0.1) / 100
        score += min(vol/liq, 10) / 50  # Activity bonus
        
        if score > best_score:
            best_score = score
            best_token = {
                "symbol": symbol,
                "mint": mint,
                "price": price,
                "liq": liq,
                "vol": vol,
                "m5": m5,
                "h1": h1,
                "h24": h24,
                "score": score,
            }
    
    return best_token


async def execute_trade(token, amount_usd):
    """Execute trade on token."""
    from core import solana_wallet
    from scripts.savage_swap import execute_swap
    
    print(f"\n🎯 TRADING {token['symbol']}", flush=True)
    print(f"   Amount: ${amount_usd:.2f}", flush=True)
    print(f"   Momentum: 5m={token['m5']:+.1f}%, 1h={token['h1']:+.1f}%, 24h={token['h24']:+.1f}%", flush=True)
    print(f"   Vol: ${token['vol']/1e3:.0f}K, Liq: ${token['liq']/1e3:.0f}K", flush=True)
    
    kp = solana_wallet.load_keypair()
    
    result = await execute_swap(
        input_token="USDC",
        output_token=token['mint'],
        amount_usd=amount_usd,
        keypair=kp,
        slippage_bps=300,  # 3% slippage for volatile tokens
    )
    
    if result.success:
        print(f"✅ SUCCESS!", flush=True)
        print(f"   Got: {result.output_amount:,.2f} {token['symbol']}", flush=True)
        print(f"   Entry: ${token['price']:.8f}", flush=True)
        print(f"   TP: ${token['price'] * (1 + TP_PCT):.8f} (+25%)", flush=True)
        print(f"   SL: ${token['price'] * (1 - SL_PCT):.8f} (-30%)", flush=True)
        return True
    else:
        print(f"❌ Failed: {result.error}", flush=True)
        return False


async def main():
    print(f"""
{'='*60}
🚀 SIMPLE MOMENTUM TRADER
{'='*60}
Target: ${TARGET}
Take Profit: +{TP_PCT*100:.0f}%
Stop Loss: -{SL_PCT*100:.0f}%
{'='*60}
""", flush=True)
    
    cycle = 0
    
    while True:
        cycle += 1
        
        # Get balance
        balance = await get_usdc_balance()
        print(f"\n--- Cycle {cycle} ---", flush=True)
        print(f"USDC Balance: ${balance:.2f}", flush=True)
        
        if balance >= TARGET:
            print(f"\n🎉 TARGET REACHED: ${balance:.2f}", flush=True)
            break
        
        if balance < 1:
            print("❌ Insufficient USDC", flush=True)
            break
        
        # Find token
        token = await find_momentum_token()
        
        if not token:
            print("No momentum tokens found, waiting 60s...", flush=True)
            await asyncio.sleep(60)
            continue
        
        print(f"Found: {token['symbol']} (score: {token['score']:.2f})", flush=True)
        
        # Execute
        success = await execute_trade(token, balance)
        
        if success:
            # Wait for price movement (monitor in another window)
            print("\n⏰ Waiting 5 minutes for momentum play...", flush=True)
            await asyncio.sleep(300)
        else:
            await asyncio.sleep(60)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Stopped", flush=True)
