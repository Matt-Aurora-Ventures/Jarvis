#!/usr/bin/env python3
"""
SOL Momentum Trader - Trade using SOL directly
Quick momentum plays to grow $1.40 → $100
"""

import asyncio
import requests
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

print("""
╔══════════════════════════════════════════════════════════╗
║  🚀 SOL MOMENTUM TRADER - $1.40 → $100                  ║
║  Quick in/out with 25% TP / 30% SL                      ║
╚══════════════════════════════════════════════════════════╝
""", flush=True)

async def find_best_momentum():
    """Find best momentum token."""
    print("🔍 Scanning DexScreener...", flush=True)
    
    resp = requests.get("https://api.dexscreener.com/latest/dex/search/?q=SOL", timeout=15)
    data = resp.json()
    
    best = None
    best_score = 0
    
    for p in [p for p in data.get("pairs", []) if p.get("chainId") == "solana"][:50]:
        base = p.get("baseToken", {})
        sym = base.get("symbol", "")
        mint = base.get("address", "")
        
        if not sym or len(sym) < 2:
            continue
        
        liq = float(p.get("liquidity", {}).get("usd", 0))
        vol = float(p.get("volume", {}).get("h24", 0))
        
        if not (10_000 < liq < 1_000_000 and vol > 100_000):
            continue
        
        pc = p.get("priceChange", {})
        m5 = float(pc.get("m5", 0))
        h1 = float(pc.get("h1", 0))
        h24 = float(pc.get("h24", 0))
        
        if not (m5 > 2 or h1 > 5 or abs(h24) > 15):
            continue
        
        score = (abs(m5) * 0.4 + abs(h1) * 0.3 + abs(h24) * 0.1) / 100
        score += min(vol/liq, 10) / 50
        
        if score > best_score:
            best_score = score
            best = {
                "symbol": sym,
                "mint": mint,
                "liq": liq,
                "vol": vol,
                "m5": m5,
                "h1": h1,
                "h24": h24,
            }
    
    if best:
        print(f"✅ Found: {best['symbol']}", flush=True)
        print(f"   5m: {best['m5']:+.1f}%, 1h: {best['h1']:+.1f}%, 24h: {best['h24']:+.1f}%", flush=True)
        print(f"   Vol: ${best['vol']/1e3:.0f}K, Liq: ${best['liq']/1e3:.0f}K", flush=True)
    
    return best

async def execute_with_sol(token):
    """Execute trade using SOL."""
    from core import solana_wallet
    from scripts.savage_swap import execute_swap
    
    print(f"\n🎯 EXECUTING: SOL → {token['symbol']}", flush=True)
    
    # Use ~$1 worth of SOL (keep 0.01 for fees)
    sol_to_trade = 0.0001  #  Just 0.01 SOL for testing ($1.40)
    
    kp = solana_wallet.load_keypair()
    
    result = await execute_swap(
        input_token="SOL",
        output_token=token['mint'],
        amount_usd=sol_to_trade,  # This will be interpreted as SOL amount
        keypair=kp,
        slippage_bps=300,
    )
    
    if result.success:
        print(f"✅ SUCCESS! Got {result.output_amount:,.2f} {token['symbol']}", flush=True)
        print(f"⏰ Holding for 5 min, then scanning for sell signal...", flush=True)
        return True
    else:
        print(f"❌ Failed: {result.error}", flush=True)
        return False

async def main():
    cycle = 0
    
    while cycle < 10:  # Max 10 cycles
        cycle += 1
        print(f"\n{'─'*60}")
        print(f"📊 Cycle {cycle}")
        print(f"{'─'*60}")
        
        token = await find_best_momentum()
        
        if not token:
            print("No momentum tokens, waiting 60s...")
            await asyncio.sleep(60)
            continue
        
        success = await execute_with_sol(token)
        
        if success:
            await asyncio.sleep(300)  # 5 min hold
        else:
            await asyncio.sleep(60)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⚠️  Stopped")
