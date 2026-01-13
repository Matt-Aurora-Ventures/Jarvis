"""Verify TP/SL orders for last purchase from blockchain."""
import asyncio
import os
import sys
import json
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Load env
env_path = Path(__file__).resolve().parents[1] / "tg_bot" / ".env"
for line in env_path.read_text().splitlines():
    if line.strip() and not line.startswith('#') and '=' in line:
        k, v = line.split('=', 1)
        os.environ.setdefault(k.strip(), v.strip().strip('\"'))

async def verify_last_purchase():
    import aiohttp
    
    # Load positions and orders
    positions = json.loads(Path("data/treasury_scorekeeper.json").read_text())
    orders = json.loads(Path("data/limit_orders.json").read_text())
    
    # Get last position (most recent)
    pos_list = list(positions.get("positions", {}).values())
    if not pos_list:
        print("No positions found")
        return
    
    # Sort by opened_at to get most recent
    last_pos = sorted(pos_list, key=lambda x: x.get("opened_at", ""))[-1]
    
    print("=" * 60)
    print("LAST PURCHASE VERIFICATION")
    print("=" * 60)
    print(f"\nToken: {last_pos['symbol']}")
    print(f"Mint: {last_pos['token_mint']}")
    print(f"Entry Price: ${last_pos['entry_price']:.8f}")
    print(f"Entry Amount: {last_pos['entry_amount_tokens']:.6f} tokens")
    print(f"Entry SOL: {last_pos['entry_amount_sol']:.6f} SOL")
    print(f"Opened: {last_pos['opened_at']}")
    print(f"Entry TX: {last_pos['tx_signature_entry']}")
    
    # TP/SL info
    print(f"\n--- TP/SL Orders ---")
    print(f"Take Profit: ${last_pos['take_profit_price']:.8f} (+{((last_pos['take_profit_price']/last_pos['entry_price'])-1)*100:.1f}%)")
    print(f"Stop Loss: ${last_pos['stop_loss_price']:.8f} ({((last_pos['stop_loss_price']/last_pos['entry_price'])-1)*100:.1f}%)")
    
    tp_order = orders.get(last_pos.get('tp_order_id', ''))
    sl_order = orders.get(last_pos.get('sl_order_id', ''))
    
    print(f"\nTP Order ID: {last_pos.get('tp_order_id')} - Status: {tp_order.get('status') if tp_order else 'NOT FOUND'}")
    print(f"SL Order ID: {last_pos.get('sl_order_id')} - Status: {sl_order.get('status') if sl_order else 'NOT FOUND'}")
    
    # Verify entry TX on Solana
    print(f"\n--- Blockchain Verification ---")
    
    async with aiohttp.ClientSession() as session:
        # 1. Verify entry transaction
        tx_sig = last_pos['tx_signature_entry']
        print(f"\nChecking TX: {tx_sig[:20]}...")
        
        helius_key = os.environ.get('HELIUS_API_KEY', '')
        if helius_key:
            url = f"https://api.helius.xyz/v0/transactions/?api-key={helius_key}"
            try:
                async with session.post(url, json={"transactions": [tx_sig]}) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data and len(data) > 0:
                            tx = data[0]
                            print(f"TX Status: CONFIRMED")
                            print(f"TX Type: {tx.get('type', 'unknown')}")
                            print(f"Fee: {tx.get('fee', 0) / 1e9:.6f} SOL")
                            if tx.get('timestamp'):
                                from datetime import datetime
                                ts = datetime.fromtimestamp(tx['timestamp'])
                                print(f"Timestamp: {ts}")
                        else:
                            print("TX not found in Helius response")
                    else:
                        print(f"Helius API error: {resp.status}")
            except Exception as e:
                print(f"Helius error: {e}")
        
        # 2. Get current token price from DexScreener
        token_mint = last_pos['token_mint']
        print(f"\nChecking current price...")
        
        try:
            async with session.get(f"https://api.dexscreener.com/latest/dex/tokens/{token_mint}") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    pairs = data.get("pairs", [])
                    if pairs:
                        pair = pairs[0]
                        current_price = float(pair.get("priceUsd", 0))
                        entry_price = last_pos['entry_price']
                        tp_price = last_pos['take_profit_price']
                        sl_price = last_pos['stop_loss_price']
                        
                        pnl_pct = ((current_price / entry_price) - 1) * 100
                        
                        print(f"\nCurrent Price: ${current_price:.8f}")
                        print(f"Entry Price: ${entry_price:.8f}")
                        print(f"Current P&L: {pnl_pct:+.2f}%")
                        
                        print(f"\n--- TP/SL Status ---")
                        
                        # Check TP
                        if current_price >= tp_price:
                            print(f"[!] TAKE PROFIT SHOULD TRIGGER: ${current_price:.8f} >= ${tp_price:.8f}")
                        else:
                            distance_to_tp = ((tp_price / current_price) - 1) * 100
                            print(f"[OK] TP not hit yet. Distance: +{distance_to_tp:.1f}% to go")
                        
                        # Check SL
                        if current_price <= sl_price:
                            print(f"[!] STOP LOSS SHOULD TRIGGER: ${current_price:.8f} <= ${sl_price:.8f}")
                        else:
                            distance_to_sl = ((current_price / sl_price) - 1) * 100
                            print(f"[OK] SL not hit. Buffer: {distance_to_sl:.1f}% above SL")
                        
                        # Liquidity check
                        liq = pair.get("liquidity", {}).get("usd", 0)
                        print(f"\nLiquidity: ${liq:,.0f}")
                        if liq < 10000:
                            print("[WARN] Low liquidity - exit may be difficult")
                    else:
                        print("Token not found on DexScreener")
                else:
                    print(f"DexScreener error: {resp.status}")
        except Exception as e:
            print(f"Price check error: {e}")
        
        # 3. Check token balance on chain
        treasury_addr = os.environ.get('TREASURY_WALLET_ADDRESS', 'BFhTj4TGcXaiVxjCH82d2NDqpDjQxMrQMQJXKRWnqSwQ')
        print(f"\nChecking wallet token balance...")
        
        try:
            rpc_url = os.environ.get('HELIUS_RPC_URL', f"https://mainnet.helius-rpc.com/?api-key={helius_key}")
            async with session.post(rpc_url, json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getTokenAccountsByOwner",
                "params": [
                    treasury_addr,
                    {"mint": token_mint},
                    {"encoding": "jsonParsed"}
                ]
            }) as resp:
                data = await resp.json()
                accounts = data.get("result", {}).get("value", [])
                if accounts:
                    info = accounts[0].get("account", {}).get("data", {}).get("parsed", {}).get("info", {})
                    balance = float(info.get("tokenAmount", {}).get("uiAmount", 0))
                    print(f"On-Chain Balance: {balance:.6f} tokens")
                    
                    expected = last_pos['entry_amount_tokens']
                    if abs(balance - expected) < 0.01:
                        print("[OK] Balance matches position")
                    else:
                        print(f"[WARN] Balance mismatch: expected {expected:.6f}")
                else:
                    print("[WARN] No token account found - may have been sold")
        except Exception as e:
            print(f"Balance check error: {e}")

    print("\n" + "=" * 60)
    print("VERIFICATION COMPLETE")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(verify_last_purchase())
