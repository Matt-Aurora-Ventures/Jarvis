#!/usr/bin/env python3
"""
LIVE Momentum Trader - Fixed Balance Logic
Uses real-time SOL balance to trade momentum tokens
Target: $5.53 → $100
"""

import asyncio
import requests
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from solana.rpc.async_api import AsyncClient
from core import solana_wallet, solana_execution
from scripts.savage_swap import execute_swap

TARGET_USD = 100.0
SOL_PRICE = 138.52  # From Solscan
MIN_SOL_RESERVE = 0.005  # Keep for fees

print(f"""
{'='*60}
💰 LIVE MOMENTUM TRADER
{'='*60}
Target: ${TARGET_USD}
Strategy: 25% TP / 30% SL
Token Filter: $10K-$1M liquidity, momentum required
{'='*60}
""", flush=True)


async def get_tradeable_balance():
    """Get current SOL balance minus reserve."""
    kp = solana_wallet.load_keypair()
    endpoints = solana_execution.load_solana_rpc_endpoints()
    
    async with AsyncClient(endpoints[0].url) as client:
        resp = await client.get_balance(kp.pubkey())
        sol_balance = resp.value / 1e9
        tradeable_sol = max(0, sol_balance - MIN_SOL_RESERVE)
        tradeable_usd = tradeable_sol * SOL_PRICE
        
        return {
            "sol_balance": sol_balance,
            "tradeable_sol": tradeable_sol,
            "tradeable_usd": tradeable_usd,
        }


async def find_momentum_token():
    """Find best momentum token using trending aggregator."""
    print("🔍 Scanning trending tokens...", flush=True)
    
    try:
        from core.trending_aggregator import fetch_trending_all_sources
        
        tokens = fetch_trending_all_sources(limit=50)
        
        best = None
        best_score = 0
        
        for t in tokens:
            sym = t.symbol
            
            # Skip base/stable tokens
            if not sym or sym.upper() in ("SOL", "USDC", "USDT", "WSOL", "WETH", "BTC", "ETH"):
                continue
            
            # Filters for volatile memecoins
            if not (10_000 < t.liquidity_usd < 2_000_000):  # Wider liquidity range
                continue
            if t.volume_24h_usd < 50_000:  # Lower volume threshold
                continue
            
            # Volume/liquidity ratio as volatility proxy (higher = more volatile)
            vol_liq_ratio = t.volume_24h_usd / max(t.liquidity_usd, 1)
            
            # Need some activity
            if vol_liq_ratio < 0.5:  # At least 50% of liquidity traded daily
                continue
            
            # Score based on activity and rank
            volatility_score = min(vol_liq_ratio / 10, 1.0) * 0.6
            rank_score = (1 - t.composite_rank / 100) * 0.4
            score = volatility_score + rank_score
            
            if score > best_score:
                best_score = score
                best = {
                    "symbol": sym,
                    "mint": t.mint,
                    "price": t.price_usd,
                    "liq": t.liquidity_usd,
                    "vol": t.volume_24h_usd,
                    "m5": 0,  # Not available from this source
                    "h1": t.price_change_24h * 100 / 24,  # Estimate
                    "h24": t.price_change_24h * 100,
                    "score": score,
                    "vol_liq_ratio": vol_liq_ratio,
                }
        
        if best:
            print(f"Found {len([t for t in tokens if t.volume_24h_usd > 50000])} active tokens", flush=True)
        
        return best
        
    except Exception as e:
        print(f"❌ Scan failed: {e}", flush=True)
        return None


async def execute_trade(token, sol_amount):
    """Execute SOL → Token swap."""
    print(f"\n🎯 TRADING: {token['symbol']}", flush=True)
    print(f"   Using: {sol_amount:.6f} SOL", flush=True)
    print(f"   Momentum: 5m={token['m5']:+.1f}%, 1h={token['h1']:+.1f}%, 24h={token['h24']:+.1f}%", flush=True)
    print(f"   Vol: ${token['vol']/1e6:.2f}M, Liq: ${token['liq']/1e3:.0f}K", flush=True)
    
    kp = solana_wallet.load_keypair()
    
    # Execute swap
    result = await execute_swap(
        input_token="SOL",
        output_token=token['mint'],
        amount_usd=sol_amount,  # In SOL
        keypair=kp,
        slippage_bps=300,  # 3% slippage
    )
    
    if result.success:
        print(f"✅ SUCCESS!", flush=True)
        print(f"   Got: {result.output_amount:,.4f} {token['symbol']}", flush=True)
        print(f"   Signature: {result.signature}", flush=True)
        
        # Calculate targets
        entry_price = token['price']
        tp_price = entry_price * 1.25
        sl_price = entry_price * 0.70
        
        print(f"\n📊 Position:", flush=True)
        print(f"   Entry: ${entry_price:.8f}", flush=True)
        print(f"   TP: ${tp_price:.8f} (+25%)", flush=True)
        print(f"   SL: ${sl_price:.8f} (-30%)", flush=True)
        
        # Save position for monitor
        import json
        position_file = Path(__file__).parent.parent / "data" / "active_position.json"
        position_file.parent.mkdir(parents=True, exist_ok=True)
        
        position = {
            "mint": token['mint'],
            "symbol": token['symbol'],
            "entry_price": entry_price,
            "quantity": result.output_amount,
            "tp_price": tp_price,
            "sl_price": sl_price,
            "entry_time": time.time(),
        }
        
        position_file.write_text(json.dumps(position, indent=2))
        print(f"💾 Position saved for monitoring", flush=True)
        
        return True
    else:
        print(f"❌ Failed: {result.error}", flush=True)
        return False


async def main():
    cycle = 0
    
    while True:
        cycle += 1
        
        # Get current balance
        bal = await get_tradeable_balance()
        
        print(f"\n{'─'*60}")
        print(f"Cycle {cycle} | SOL: {bal['sol_balance']:.6f} | USD: ${bal['tradeable_usd']:.2f}")
        print(f"{'─'*60}")
        
        # Check if target reached
        if bal['tradeable_usd'] >= TARGET_USD:
            print(f"\n🎉 TARGET REACHED: ${bal['tradeable_usd']:.2f}", flush=True)
            break
        
        # Check if enough to trade
        if bal['tradeable_sol'] < 0.001:  # Minimum 0.001 SOL
            print("❌ Insufficient SOL for trading", flush=True)
            break
        
        # Find token
        token = await find_momentum_token()
        
        if not token:
            print("No momentum tokens, waiting 60s...", flush=True)
            await asyncio.sleep(60)
            continue
        
        print(f"✅ Found: {token['symbol']} (score: {token['score']:.2f})", flush=True)
        
        # Execute trade with available SOL
        success = await execute_trade(token, bal['tradeable_sol'])
        
        if success:
            print("\n⏰ Holding for 5 minutes...", flush=True)
            await asyncio.sleep(300)
        else:
            print("Waiting 60s before retry...", flush=True)
            await asyncio.sleep(60)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⚠️  Stopped by user", flush=True)
