#!/usr/bin/env python3
"""
Detailed Solana position analysis and bot recommendations.
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

# Known token mints
KNOWN_TOKENS = {
    "9BB6NFEcjBCtnNLFko2FqVQBq8HHM13kCyYcdQbgpump": "FARTCOIN",
    "EPjFWdd5AufLSTmTGcvCH43VCUAUAiJ2V3Y8GCGWHtBvK": "USDC",
    "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB": "USDT",
    "DezXAZ8z1PNUaovzBq8xvXK3WXrLLGPaVtS2LzJihKJ9": "Bonk",
    "So11111111111111111111111111111111111111112": "SOL"
}

async def analyze_positions():
    """Analyze positions and provide bot recommendations."""
    
    print("=" * 70)
    print("SOLANA POSITION ANALYSIS & BOT RECOMMENDATIONS")
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
        # Get SOL balance
        balance = await client.get_balance(pubkey)
        sol_balance = balance.value / 1e9
        sol_usd = sol_balance * 134.5  # Approximate SOL price
        print(f"💰 SOL Balance: {sol_balance:.6f} SOL (${sol_usd:.2f})")
        
        # Get token accounts
        from solana.rpc.types import TokenAccountOpts
        
        token_accounts = await client.get_token_accounts_by_owner_json_parsed(
            pubkey,
            TokenAccountOpts(program_id=Pubkey.from_string("TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"))
        )
        
        print(f"\n📊 Token Positions: {len(token_accounts.value)}")
        print("-" * 50)
        
        positions = []
        total_usd = sol_usd
        
        for account_info in token_accounts.value:
            account_data = account_info.account.data.parsed
            info = account_data['info']
            
            mint = info['mint']
            balance = float(info['tokenAmount']['uiAmount'])
            decimals = info['tokenAmount']['decimals']
            
            if balance > 0:
                symbol = KNOWN_TOKENS.get(mint, mint[:8] + "...")
                
                # Estimate USD value (rough estimates)
                if symbol == "FARTCOIN":
                    usd_value = balance * 0.3585
                elif symbol == "USDC":
                    usd_value = balance
                elif symbol == "USDT":
                    usd_value = balance
                elif symbol == "Bonk":
                    usd_value = balance * 0.000012
                else:
                    usd_value = 0  # Unknown token
                
                total_usd += usd_value
                
                positions.append({
                    'symbol': symbol,
                    'mint': mint,
                    'balance': balance,
                    'usd_value': usd_value,
                    'decimals': decimals
                })
                
                print(f"  {symbol:<12}: {balance:>12,.6f}  (${usd_value:>8.2f})")
        
        print("-" * 50)
        print(f"{'Total':<12}: {'':>12}  (${total_usd:>8.2f})")
        
        # Analysis and recommendations
        print("\n🔍 POSITION ANALYSIS")
        print("=" * 50)
        
        # Check for issues
        issues = []
        
        if sol_balance < 0.01:
            issues.append("Low SOL balance - may cause transaction failures")
        
        # Check for small positions
        small_positions = [p for p in positions if 0 < p['usd_value'] < 1]
        if small_positions:
            issues.append(f"Found {len(small_positions)} positions worth less than $1")
        
        # Check for high decimal tokens
        high_decimal = [p for p in positions if p['decimals'] > 10]
        if high_decimal:
            issues.append(f"Found {len(high_decimal)} high-decimal tokens (potential dust)")
        
        if issues:
            print("⚠️  Issues Found:")
            for issue in issues:
                print(f"  - {issue}")
        else:
            print("✅ No critical issues detected")
        
        # Bot recommendations
        print("\n🤖 BOT RECOMMENDATIONS")
        print("=" * 50)
        
        print("\n1. SCALPING BOT (for high-frequency trades):")
        print("   - Best for: FARTCOIN (high volatility)")
        print("   - Strategy: Micro-arbitrage on price fluctuations")
        print("   - Required: 0.005 SOL for fees")
        
        print("\n2. DCA BOT (Dollar Cost Averaging):")
        print("   - Best for: Accumulating positions over time")
        print("   - Strategy: Buy fixed amounts at intervals")
        print("   - Good for: VOLATILE tokens like FARTCOIN")
        
        print("\n3. SWING TRADING BOT:")
        print("   - Best for: Medium-term holds (days-weeks)")
        print("   - Strategy: Technical analysis based entries/exits")
        print("   - Works with: All positions")
        
        print("\n4. ARBITRAGE BOT:")
        print("   - Requires: Multiple exchanges or DEXs")
        print("   - Strategy: Price difference exploitation")
        print("   - High profit potential but requires monitoring")
        
        print("\n5. LIQUIDATION HUNTING BOT:")
        print("   - Strategy: Monitor liquidation events")
        print("   - High risk/reward")
        print("   - Requires: Real-time data feeds")
        
        # Transaction optimization tips
        print("\n⚡ TRANSACTION OPTIMIZATION")
        print("=" * 50)
        print("1. Use priority fees for faster execution")
        print("2. Batch multiple operations in one transaction")
        print("3. Trade during off-peak hours for lower fees")
        print("4. Keep 0.01 SOL minimum for emergency transactions")
        print("5. Use Jupiter aggregator for best DEX rates")
        
        # Error prevention
        print("\n🛡️ ERROR PREVENTION")
        print("=" * 50)
        print("1. Always check slippage tolerance")
        print("2. Verify token addresses before trading")
        print("3. Use stop-losses to limit downside")
        print("4. Monitor gas fees during network congestion")
        print("5. Keep backup of wallet seed phrase")
        
        # Next steps
        print("\n📋 NEXT STEPS")
        print("=" * 50)
        print("1. Set up API keys for real-time data")
        print("2. Choose 1-2 bot strategies to start")
        print("3. Paper trade first to test strategies")
        print("4. Start with small position sizes")
        print("5. Monitor and adjust parameters")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await client.close()

if __name__ == "__main__":
    asyncio.run(analyze_positions())
