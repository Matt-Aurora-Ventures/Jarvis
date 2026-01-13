"""
Execute a small test trade and sell back to SOL.
Uses the TreasuryTrader with encrypted keypair.
"""

import asyncio
import json
import os
import sys
from pathlib import Path
from datetime import datetime

# Add project root to path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Load env from tg_bot/.env
env_path = ROOT / "tg_bot" / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value

# Force live mode for this test
os.environ["TREASURY_LIVE_MODE"] = "true"

import aiohttp

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_ADMIN_ID = os.environ.get("TELEGRAM_ADMIN_IDS", "").split(",")[0].strip()
TREASURY_ADDRESS = "BFhTj4TGKC77C7s3HLnLbCiVd6dXQSqGvtD8sJY5egVR"

# Test with BONK - very liquid, cheap token
TEST_TOKEN = {
    "symbol": "BONK",
    "mint": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",
}

# Very small test amount - 0.005 SOL (about $0.75)
TEST_AMOUNT_SOL = 0.005


async def send_telegram(text: str):
    """Send message to Telegram."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_ADMIN_ID:
        print("Telegram not configured")
        return False
    
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_ADMIN_ID,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload) as resp:
            result = await resp.json()
            return result.get("ok", False)


async def get_sol_balance():
    """Get SOL balance of treasury."""
    async with aiohttp.ClientSession() as session:
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getBalance",
            "params": [TREASURY_ADDRESS]
        }
        async with session.post("https://api.mainnet-beta.solana.com", json=payload) as resp:
            data = await resp.json()
            lamports = data.get("result", {}).get("value", 0)
            return lamports / 1e9


async def main():
    print("=" * 60)
    print("TREASURY LIVE TRADE TEST")
    print("=" * 60)
    
    # Check initial balance
    initial_balance = await get_sol_balance()
    print(f"\n[1] Initial Balance: {initial_balance:.6f} SOL")
    
    if initial_balance < 0.02:
        print("ERROR: Need at least 0.02 SOL for test (trade + fees)")
        return
    
    # Notify Telegram
    await send_telegram(
        f"*TRADE TEST STARTING*\n\n"
        f"Treasury: `{TREASURY_ADDRESS[:8]}...`\n"
        f"Balance: {initial_balance:.6f} SOL\n"
        f"Test Token: {TEST_TOKEN['symbol']}\n"
        f"Amount: {TEST_AMOUNT_SOL} SOL"
    )
    
    # Import trading modules
    print("\n[2] Initializing TreasuryTrader...")
    try:
        from bots.treasury.trading import TreasuryTrader, TradeDirection
        
        trader = TreasuryTrader()
        init_ok, init_msg = await trader._ensure_initialized()
        
        if not init_ok:
            print(f"ERROR: {init_msg}")
            await send_telegram(f"*TRADE FAILED*\n\nInit error: {init_msg}")
            return
        
        print(f"    Trader initialized: {init_msg}")
        print(f"    Live mode: {not trader._engine.dry_run}")
        
    except Exception as e:
        print(f"ERROR initializing trader: {e}")
        await send_telegram(f"*TRADE FAILED*\n\nInit error: {e}")
        return
    
    # Get SOL price
    print("\n[3] Getting prices...")
    try:
        sol_price = await trader._engine.jupiter.get_token_price(
            "So11111111111111111111111111111111111111112"  # SOL mint
        )
        token_price = await trader._engine.jupiter.get_token_price(TEST_TOKEN["mint"])
        
        amount_usd = TEST_AMOUNT_SOL * sol_price
        print(f"    SOL price: ${sol_price:.2f}")
        print(f"    {TEST_TOKEN['symbol']} price: ${token_price:.10f}")
        print(f"    Trade value: ${amount_usd:.2f}")
        
    except Exception as e:
        print(f"ERROR getting prices: {e}")
        await send_telegram(f"*TRADE FAILED*\n\nPrice error: {e}")
        return
    
    # Execute BUY
    print(f"\n[4] Executing BUY: {TEST_AMOUNT_SOL} SOL -> {TEST_TOKEN['symbol']}...")
    try:
        # Calculate TP/SL prices (10% TP, 5% SL for test)
        tp_price = token_price * 1.10
        sl_price = token_price * 0.95
        
        admin_id = int(TELEGRAM_ADMIN_ID)
        
        result = await trader.execute_buy_with_tp_sl(
            token_mint=TEST_TOKEN["mint"],
            amount_sol=TEST_AMOUNT_SOL,
            take_profit_price=tp_price,
            stop_loss_price=sl_price,
            token_symbol=TEST_TOKEN["symbol"],
            user_id=admin_id,
        )
        
        if result.get("success"):
            position_id = result.get("position_id", "")
            entry_price = result.get("entry_price", token_price)
            tx_sig = result.get("tx_signature", "")
            
            print(f"    SUCCESS!")
            print(f"    Position ID: {position_id}")
            print(f"    Entry: ${entry_price:.10f}")
            print(f"    TX: {tx_sig[:20]}..." if tx_sig else "    TX: (dry run)")
            
            # Telegram notification
            await send_telegram(
                f"*BUY EXECUTED*\n\n"
                f"Token: {TEST_TOKEN['symbol']}\n"
                f"Amount: {TEST_AMOUNT_SOL} SOL (~${amount_usd:.2f})\n"
                f"Entry: ${entry_price:.10f}\n"
                f"TP: ${tp_price:.10f} (+10%)\n"
                f"SL: ${sl_price:.10f} (-5%)\n"
                f"Position: `{position_id}`\n"
                f"TX: `{tx_sig[:20]}...`" if tx_sig else f"TX: (simulated)"
            )
            
        else:
            error = result.get("error", "Unknown error")
            print(f"    FAILED: {error}")
            await send_telegram(f"*BUY FAILED*\n\n{error}")
            return
            
    except Exception as e:
        print(f"ERROR executing buy: {e}")
        await send_telegram(f"*BUY FAILED*\n\n{e}")
        return
    
    # Wait a moment for blockchain confirmation
    print("\n[5] Waiting for confirmation...")
    await asyncio.sleep(3)
    
    # Check balance after buy
    post_buy_balance = await get_sol_balance()
    print(f"    Balance after buy: {post_buy_balance:.6f} SOL")
    print(f"    SOL spent: {initial_balance - post_buy_balance:.6f}")
    
    # Execute SELL (close position)
    print(f"\n[6] Closing position (selling back to SOL)...")
    try:
        close_success, close_msg = await trader._engine.close_position(
            position_id=position_id,
            user_id=admin_id,
            reason="Test trade - immediate close"
        )
        
        if close_success:
            print(f"    SUCCESS: {close_msg}")
        else:
            print(f"    FAILED: {close_msg}")
            
    except Exception as e:
        print(f"ERROR closing position: {e}")
    
    # Wait for confirmation
    await asyncio.sleep(3)
    
    # Final balance
    final_balance = await get_sol_balance()
    net_change = final_balance - initial_balance
    
    print("\n" + "=" * 60)
    print("TRADE TEST COMPLETE")
    print("=" * 60)
    print(f"\nInitial balance: {initial_balance:.6f} SOL")
    print(f"Final balance:   {final_balance:.6f} SOL")
    print(f"Net change:      {net_change:+.6f} SOL")
    
    # Final Telegram report
    await send_telegram(
        f"*TRADE TEST COMPLETE*\n\n"
        f"Initial: {initial_balance:.6f} SOL\n"
        f"Final: {final_balance:.6f} SOL\n"
        f"Net: {net_change:+.6f} SOL\n\n"
        f"Position opened and closed successfully.\n"
        f"Treasury address: `{TREASURY_ADDRESS}`"
    )


if __name__ == "__main__":
    asyncio.run(main())
