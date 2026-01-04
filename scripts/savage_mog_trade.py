#!/usr/bin/env python3
"""
SAVAGE ARTHUR HAYNES - Trade Execution Script
==============================================

$20 → $1M Challenge - MOG (Mog Coin) Trade

Target: MOG on Solana (Raydium)
Direction: LONG
Entry: $20 USD
Conviction: 0.85 (Strong momentum + X sentiment)

This script:
1. Creates exit intent with TP ladder + SL
2. Persists intent to disk BEFORE trade execution
3. Generates Jupiter swap transaction
"""

import json
import time
import uuid
from pathlib import Path
from datetime import datetime

# Trade Parameters - SAVAGE MODE
TRADE_CONFIG = {
    "strategy": "LUT_MICRO_ALPHA",
    "target_asset": "MOG",
    "token_mint": "26VfKb7jjtdEdvfovoBijScoZmJbWWasFZkgfUD5w7cy",  # MOG on Solana
    "direction": "LONG",
    "chain": "solana",
    "dex": "raydium",
    
    # Entry
    "allocation_usd": 20.00,
    "entry_price": 0.0000003366,  # Current price from DexScreener
    
    # Sentiment/Conviction
    "sentiment_score": 0.85,
    "conviction_reasoning": "MOG +22% in 24h, +11% in 6h. $42K volume on Solana. $131M FDV = established, not a rug. X mentions rising with meme season narrative.",
    
    # Exit Plan (Aggressive for momentum play)
    "tp1_pct": 0.50,   # +50% take 60%
    "tp1_size": 0.60,
    "tp2_pct": 1.00,   # +100% take 25%
    "tp2_size": 0.25,
    "tp3_pct": 2.00,   # +200% runner 15%
    "tp3_size": 0.15,
    "sl_pct": 0.15,    # -15% stop (tight for momentum)
    "time_stop_minutes": 90,
    
    # Execution
    "execution_style": "AGGRESSIVE",
    "paper_mode": True,  # Set to False for live trading
}

def calculate_quantity(allocation_usd: float, entry_price: float) -> float:
    """Calculate token quantity from USD allocation."""
    return allocation_usd / entry_price

def create_exit_intent(config: dict) -> dict:
    """Create exit intent for the trade."""
    entry_price = config["entry_price"]
    quantity = calculate_quantity(config["allocation_usd"], entry_price)
    now = time.time()
    
    intent = {
        "id": str(uuid.uuid4())[:8],
        "position_id": f"savage-{str(uuid.uuid4())[:8]}",
        "position_type": "spot",
        "token_mint": config["token_mint"],
        "symbol": config["target_asset"],
        "entry_price": entry_price,
        "entry_timestamp": now,
        "original_quantity": quantity,
        "remaining_quantity": quantity,
        "status": "active",
        
        # Take Profits
        "take_profits": [
            {
                "level": 1,
                "price": entry_price * (1 + config["tp1_pct"]),
                "size_pct": config["tp1_size"] * 100,
                "filled": False,
            },
            {
                "level": 2,
                "price": entry_price * (1 + config["tp2_pct"]),
                "size_pct": config["tp2_size"] * 100,
                "filled": False,
            },
            {
                "level": 3,
                "price": entry_price * (1 + config["tp3_pct"]),
                "size_pct": config["tp3_size"] * 100,
                "filled": False,
            },
        ],
        
        # Stop Loss
        "stop_loss": {
            "price": entry_price * (1 - config["sl_pct"]),
            "size_pct": 100.0,
            "adjusted": False,
            "original_price": entry_price * (1 - config["sl_pct"]),
        },
        
        # Time Stop
        "time_stop": {
            "deadline_timestamp": now + (config["time_stop_minutes"] * 60),
            "action": "exit_fully",
            "triggered": False,
        },
        
        # Trailing Stop (activates after TP1)
        "trailing_stop": {
            "active": False,
            "trail_pct": 0.20,  # 20% trail after TP1
            "highest_price": entry_price,
            "current_stop": 0.0,
        },
        
        "is_paper": config["paper_mode"],
        "notes": config["conviction_reasoning"],
        "created_at": datetime.now().isoformat(),
    }
    
    return intent

def persist_intent(intent: dict) -> bool:
    """Persist exit intent to disk BEFORE trade execution."""
    trading_dir = Path.home() / ".lifeos" / "trading"
    trading_dir.mkdir(parents=True, exist_ok=True)
    intents_file = trading_dir / "exit_intents.json"
    
    # Load existing intents
    intents = []
    if intents_file.exists():
        try:
            intents = json.loads(intents_file.read_text())
        except json.JSONDecodeError:
            intents = []
    
    # Add new intent
    intents.append(intent)
    
    # Persist
    intents_file.write_text(json.dumps(intents, indent=2))
    return True

def print_trade_summary(config: dict, intent: dict):
    """Print trade execution summary."""
    entry = config["entry_price"]
    quantity = calculate_quantity(config["allocation_usd"], entry)
    
    print("\n" + "=" * 60)
    print("🔥 SAVAGE ARTHUR HAYNES - TRADE EXECUTION 🔥")
    print("=" * 60)
    print(f"\n📊 ASSET: {config['target_asset']} ({config['chain'].upper()})")
    print(f"📈 DIRECTION: {config['direction']}")
    print(f"💰 ALLOCATION: ${config['allocation_usd']:.2f} USD")
    print(f"💵 ENTRY PRICE: ${entry:.10f}")
    print(f"📦 QUANTITY: {quantity:,.0f} tokens")
    print(f"🎯 CONVICTION: {config['sentiment_score']:.0%}")
    print(f"\n📝 REASONING: {config['conviction_reasoning']}")
    
    print("\n" + "-" * 60)
    print("📍 EXIT PLAN:")
    print("-" * 60)
    
    for tp in intent["take_profits"]:
        pct_gain = ((tp["price"] / entry) - 1) * 100
        print(f"  TP{tp['level']}: ${tp['price']:.10f} (+{pct_gain:.0f}%) - Sell {tp['size_pct']:.0f}%")
    
    sl = intent["stop_loss"]
    sl_pct = ((sl["price"] / entry) - 1) * 100
    print(f"  SL: ${sl['price']:.10f} ({sl_pct:.0f}%)")
    print(f"  TIME STOP: {config['time_stop_minutes']} minutes")
    
    print("\n" + "-" * 60)
    print("📁 EXIT INTENT PERSISTED TO DISK")
    print(f"  ID: {intent['id']}")
    print(f"  Position: {intent['position_id']}")
    print(f"  File: ~/.lifeos/trading/exit_intents.json")
    print("-" * 60)
    
    if config["paper_mode"]:
        print("\n⚠️  PAPER MODE - No real funds used")
    else:
        print("\n🚨 LIVE MODE - Real funds will be used!")
    
    print("\n" + "=" * 60)

def main():
    """Execute the trade."""
    print("\n🚀 Initializing SAVAGE trade execution...")
    
    # Create exit intent
    intent = create_exit_intent(TRADE_CONFIG)
    
    # CRITICAL: Persist intent BEFORE trade execution
    if persist_intent(intent):
        print("✅ Exit intent persisted to disk")
    else:
        print("❌ FAILED to persist intent - ABORTING")
        return
    
    # Print summary
    print_trade_summary(TRADE_CONFIG, intent)
    
    # Generate Jupiter swap URL for manual execution
    print("\n🔗 JUPITER SWAP URL:")
    print(f"https://jup.ag/swap/USDC-{TRADE_CONFIG['token_mint']}")
    
    print("\n✅ Trade setup complete. Execute swap via Jupiter or Phantom.")
    
    return intent

if __name__ == "__main__":
    main()
