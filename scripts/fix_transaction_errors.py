#!/usr/bin/env python3
"""
Solana transaction error checker and fixer.
"""

import sys
import os
import asyncio
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from solana.rpc.async_api import AsyncClient
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.signature import Signature
import base58
import json

async def check_and_fix_errors():
    """Check for common transaction errors and provide fixes."""
    
    print("=" * 70)
    print("SOLANA TRANSACTION ERROR CHECKER & FIXER")
    print("=" * 70)
    
    # Load wallet
    wallet_path = Path.home() / '.lifeos' / 'wallets' / 'phantom_trading_wallet.json'
    with open(wallet_path) as f:
        wallet_data = json.load(f)
    
    keypair = Keypair.from_bytes(bytes(wallet_data))
    pubkey = keypair.pubkey()
    
    print(f"Wallet: {pubkey}")
    print()
    
    # Connect to Solana
    client = AsyncClient("https://api.mainnet-beta.solana.com")
    
    try:
        # Check 1: SOL Balance
        print("1️⃣  CHECKING SOL BALANCE")
        print("-" * 40)
        balance = await client.get_balance(pubkey)
        sol_balance = balance.value / 1e9
        
        if sol_balance < 0.01:
            print(f"⚠️  LOW SOL: {sol_balance:.6f} SOL")
            print("   FIX: Add more SOL for transactions (minimum 0.01 SOL recommended)")
        else:
            print(f"✅ SOL Balance: {sol_balance:.6f} SOL - Sufficient for transactions")
        
        # Check 2: Rent Exemption
        print("\n2️⃣  CHECKING RENT EXEMPTION")
        print("-" * 40)
        min_balance_resp = await client.get_minimum_balance_for_rent_exemption(165)
        min_balance = min_balance_resp.value
        if sol_balance * 1e9 < min_balance * 2:  # Need 2x for safety
            print(f"⚠️  May not have enough for rent exemption")
            print(f"   Required: {min_balance/1e9:.6f} SOL per account")
            print("   FIX: Keep extra SOL for creating new accounts")
        else:
            print("✅ Sufficient SOL for rent exemption")
        
        # Check 3: Recent Failed Transactions
        print("\n3️⃣  CHECKING RECENT TRANSACTIONS")
        print("-" * 40)
        signatures = await client.get_signatures_for_address(
            pubkey,
            limit=10,
            commitment="confirmed"
        )
        
        failed_txs = []
        for sig_info in signatures.value:
            if sig_info.err:
                failed_txs.append(sig_info)
        
        if failed_txs:
            print(f"⚠️  Found {len(failed_txs)} failed transactions:")
            for tx in failed_txs[:3]:
                sig_str = str(tx.signature)
                print(f"   - {sig_str[:8]}...: {tx.err}")
            
            print("\n   Common fixes:")
            print("   - Increase compute budget")
            print("   - Add priority fee")
            print("   - Check token account exists")
            print("   - Verify sufficient balance")
        else:
            print("✅ No failed transactions in recent history")
        
        # Check 4: Token Account Issues
        print("\n4️⃣  CHECKING TOKEN ACCOUNTS")
        print("-" * 40)
        from solana.rpc.types import TokenAccountOpts
        
        token_accounts = await client.get_token_accounts_by_owner_json_parsed(
            pubkey,
            TokenAccountOpts(program_id=Pubkey.from_string("TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"))
        )
        
        zero_balance_accounts = []
        for account_info in token_accounts.value:
            account_data = account_info.account.data.parsed
            info = account_data['info']
            balance = float(info['tokenAmount']['uiAmount'])
            
            if balance == 0:
                zero_balance_accounts.append(account_info.pubkey)
        
        if zero_balance_accounts:
            print(f"⚠️  Found {len(zero_balance_accounts)} empty token accounts")
            print("   These accounts consume rent (0.00089088 SOL each)")
            print("   FIX: Close empty accounts to reclaim rent")
            print("   Command: solana account <account_pubkey> --close <recipient>")
        else:
            print("✅ No empty token accounts found")
        
        # Check 5: Network Congestion
        print("\n5️⃣  CHECKING NETWORK STATUS")
        print("-" * 40)
        recent_performance = await client.get_recent_performance_samples(1)
        if recent_performance.value:
            sample = recent_performance.value[0]
            tps = sample.num_transactions / sample.sample_period_secs
            print(f"Current TPS: {tps:.0f}")
            
            if tps > 3000:
                print("⚠️  High network congestion")
                print("   FIX: Use higher priority fees")
                print("   Recommended: 10000-50000 lamports priority fee")
            else:
                print("✅ Network congestion is normal")
        
        # Generate fixes script
        print("\n🔧 AUTOMATED FIXES")
        print("=" * 50)
        
        fixes = []
        
        if sol_balance < 0.01:
            fixes.append("Add SOL to wallet (minimum 0.01 SOL)")
        
        if zero_balance_accounts:
            fixes.append(f"Close {len(zero_balance_accounts)} empty token accounts")
        
        if failed_txs:
            fixes.append("Review failed transactions and adjust parameters")
        
        if not fixes:
            print("✅ No fixes needed - wallet is healthy!")
        else:
            print("Recommended fixes:")
            for i, fix in enumerate(fixes, 1):
                print(f"  {i}. {fix}")
        
        # Transaction tips
        print("\n💡 FLAWLESS TRANSACTION TIPS")
        print("=" * 50)
        print("1. Always use recent blockhash")
        print("2. Set appropriate compute limit (200000 for simple tx)")
        print("3. Add priority fee during congestion (10000+ lamports)")
        print("4. Verify account exists before transaction")
        print("5. Check token decimals for amount calculations")
        print("6. Use Jupiter aggregator for token swaps")
        print("7. Set slippage to 1-3% for volatile tokens")
        print("8. Keep buffer SOL for unexpected fees")
        
        # Example transaction parameters
        print("\n📝 RECOMMENDED TRANSACTION PARAMETERS")
        print("=" * 50)
        print("For normal transactions:")
        print("  - Compute Budget: 200000 compute units")
        print("  - Priority Fee: 10000 lamports (adjust for congestion)")
        print("  - Slippage: 1% (stablecoins) to 3% (memecoins)")
        print()
        print("For complex transactions:")
        print("  - Compute Budget: 1000000 compute units")
        print("  - Priority Fee: 50000+ lamports")
        print("  - Pre-flight: Always check simulation")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await client.close()

if __name__ == "__main__":
    asyncio.run(check_and_fix_errors())
