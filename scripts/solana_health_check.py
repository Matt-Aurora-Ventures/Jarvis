#!/usr/bin/env python3
"""
Comprehensive Solana account analysis and position checker.
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
import base58
import json

async def check_account_health():
    """Check wallet health and identify potential issues."""
    
    print("=" * 70)
    print("SOLANA ACCOUNT HEALTH CHECK")
    print("=" * 70)
    
    # Load wallet
    wallet_path = Path.home() / '.lifeos' / 'wallets' / 'phantom_trading_wallet.json'
    if not wallet_path.exists():
        print(f"❌ Wallet file not found at {wallet_path}")
        return
    
    with open(wallet_path) as f:
        wallet_data = json.load(f)
    
    if isinstance(wallet_data, list):
        keypair = Keypair.from_bytes(bytes(wallet_data))
    else:
        keypair = Keypair.from_bytes(base58.b58decode(wallet_data))
    
    pubkey = keypair.pubkey()
    print(f"Wallet: {pubkey}")
    
    # Connect to Solana
    client = AsyncClient("https://api.mainnet-beta.solana.com")
    
    try:
        # Get basic account info
        balance = await client.get_balance(pubkey)
        sol_balance = balance.value / 1e9
        print(f"\n💰 SOL Balance: {sol_balance:.6f} SOL")
        
        # Get token accounts
        from solana.rpc.types import TokenAccountOpts
        from solders.pubkey import Pubkey
        
        token_accounts = await client.get_token_accounts_by_owner_json_parsed(
            pubkey,
            TokenAccountOpts(program_id=Pubkey.from_string("TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"))
        )
        
        print(f"\n📊 Token Accounts: {len(token_accounts.value)}")
        
        # Check each token
        issues = []
        tokens = []
        
        for account_info in token_accounts.value:
            account_data = account_info.account.data.parsed
            info = account_data['info']
            
            mint = info['mint']
            balance = int(info['tokenAmount']['amount'])
            decimals = info['tokenAmount']['decimals']
            ui_amount = balance / (10 ** decimals)
            
            if ui_amount > 0:
                tokens.append({
                    'mint': mint,
                    'balance': ui_amount,
                    'decimals': decimals
                })
                
                # Check for potential issues
                if balance == 0 and ui_amount > 0:
                    issues.append(f"Zero balance with positive UI amount for {mint}")
                
                if decimals > 10:
                    issues.append(f"High decimal token detected: {mint} ({decimals} decimals)")
        
        # Display tokens
        if tokens:
            print("\n🪙 Token Positions:")
            for token in sorted(tokens, key=lambda x: x['balance'], reverse=True)[:10]:
                print(f"  {token['mint'][:8]}...: {token['balance']:.6f}")
        else:
            print("\n⚠️  No token positions found")
        
        # Check for SOLANA program accounts
        try:
            program_accounts = await client.get_program_accounts(
                pubkey,
                commitment="confirmed"
            )
            
            print(f"\n🔧 Program Accounts: {len(program_accounts.value) if program_accounts else 0}")
        except Exception:
            print("\n🔧 Program Accounts: Unable to fetch")
        
        # Check recent transactions
        signatures = await client.get_signatures_for_address(
            pubkey,
            limit=5,
            commitment="confirmed"
        )
        
        if signatures.value:
            print("\n📜 Recent Transactions:")
            for sig in signatures.value:
                print(f"  {sig.signature[:8]}... - {sig.confirmation_status}")
        
        # Check rent exemption
        min_balance = await client.get_minimum_balance_for_rent_exemption(165)  # Standard token account size
        if sol_balance * 1e9 < min_balance:
            issues.append(f"Insufficient SOL for rent exemption (need {min_balance/1e9:.6f} SOL)")
        
        # Report issues
        if issues:
            print("\n⚠️  Issues Found:")
            for issue in issues:
                print(f"  - {issue}")
        else:
            print("\n✅ No critical issues detected")
        
        # Recommendations
        print("\n💡 Recommendations:")
        print("  1. Keep at least 0.01 SOL for transaction fees")
        print("  2. Consider consolidating small token balances")
        print("  3. Monitor for stuck transactions")
        print("  4. Use priority fees for faster execution")
        
    except Exception as e:
        print(f"\n❌ Error checking account: {e}")
    finally:
        await client.close()

if __name__ == "__main__":
    asyncio.run(check_account_health())
