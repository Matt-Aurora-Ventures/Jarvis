#!/usr/bin/env python3
"""
Position Monitor - Actively watch price and exit at TP/SL
Monitors every 10 seconds to avoid holding the bag
"""

import asyncio
import requests
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core import solana_wallet
from scripts.savage_swap import execute_swap

# Active position tracking
POSITION_FILE = Path(__file__).parent.parent / "data" / "active_position.json"

async def get_current_price(mint):
    """Get current price from DexScreener."""
    try:
        resp = requests.get(f"https://api.dexscreener.com/latest/dex/tokens/{mint}", timeout=5)
        data = resp.json()
        
        if data.get("pairs"):
            # Get first Solana pair
            for pair in data["pairs"]:
                if pair.get("chainId") == "solana":
                    return float(pair.get("priceUsd", 0))
        return None
    except:
        return None


async def check_and_exit_position():
    """Check position and exit if TP/SL hit."""
    
    # Load position
    if not POSITION_FILE.exists():
        return False
    
    import json
    pos = json.loads(POSITION_FILE.read_text())
    
    mint = pos["mint"]
    symbol = pos["symbol"]
    entry_price = pos["entry_price"]
    quantity = pos["quantity"]
    tp_price = pos["tp_price"]
    sl_price = pos["sl_price"]
    entry_time = pos["entry_time"]
    
    # Get current price
    current_price = await get_current_price(mint)
    
    if not current_price:
        print(f"⚠️  Cannot get price for {symbol}", flush=True)
        return False
    
    # Calculate P&L
    pnl_pct = ((current_price - entry_price) / entry_price) * 100
    time_held = (time.time() - entry_time) / 60  # minutes
    
    print(f"📊 {symbol}: ${current_price:.8f} ({pnl_pct:+.2f}%) | Held: {time_held:.1f}min", flush=True)
    
    # Check exit conditions
    should_exit = False
    exit_reason = ""
    
    if current_price >= tp_price:
        should_exit = True
        exit_reason = "TAKE_PROFIT"
    elif current_price <= sl_price:
        should_exit = True
        exit_reason = "STOP_LOSS"
    elif time_held > 30:  # Max 30 min hold
        should_exit = True
        exit_reason = "TIME_STOP"
    
    if should_exit:
        print(f"\n🚨 EXITING: {exit_reason}", flush=True)
        print(f"   Entry: ${entry_price:.8f}", flush=True)
        print(f"   Current: ${current_price:.8f}", flush=True)
        print(f"   P&L: {pnl_pct:+.2f}%", flush=True)
        
        # Execute sell
        kp = solana_wallet.load_keypair()
        
        result = await execute_swap(
            input_token=mint,
            output_token="SOL",
            amount_usd=quantity,  # Sell all
            keypair=kp,
            slippage_bps=500,  # 5% slippage for quick exit
        )
        
        if result.success:
            print(f"✅ EXIT SUCCESS!", flush=True)
            print(f"   Got: {result.output_amount:.6f} SOL", flush=True)
            print(f"   Signature: {result.signature}", flush=True)
            
            # Clear position
            POSITION_FILE.unlink()
            return True
        else:
            print(f"❌ Exit failed: {result.error}", flush=True)
            return False
    
    return False


async def monitor_loop():
    """Main monitoring loop."""
    print("👀 Position Monitor Started", flush=True)
    print("Checking every 10 seconds for TP/SL...\n", flush=True)
    
    while True:
        if POSITION_FILE.exists():
            exited = await check_and_exit_position()
            if exited:
                print("\n✅ Position closed, waiting for next entry...\n", flush=True)
        
        await asyncio.sleep(10)  # Check every 10 seconds


if __name__ == "__main__":
    try:
        asyncio.run(monitor_loop())
    except KeyboardInterrupt:
        print("\n⚠️  Monitor stopped", flush=True)
