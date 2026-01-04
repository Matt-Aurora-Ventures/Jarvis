#!/usr/bin/env python3
"""Check wallet status including token balances."""

import asyncio
import json
from pathlib import Path
from solders.keypair import Keypair
from solana.rpc.async_api import AsyncClient

SOLANA_RPC = "https://api.mainnet-beta.solana.com"
FARTCOIN_MINT = "9BB6NFEcjBCtnNLFko2FqVQBq8HHM13kCyYcdQbgpump"

async def check_wallet():
    # Load wallet
    wallet_path = Path.home() / '.lifeos' / 'wallets' / 'phantom_trading_wallet.json'
    data = json.loads(wallet_path.read_text())
    kp = Keypair.from_bytes(bytes(data))
    pubkey = kp.pubkey()
    
    print(f"Wallet: {pubkey}")
    print("=" * 60)
    
    async with AsyncClient(SOLANA_RPC) as client:
        # Get SOL balance
        balance = await client.get_balance(pubkey)
        sol_balance = balance.value / 1e9
        sol_usd = sol_balance * 134.5  # Approximate SOL price
        print(f"SOL Balance: {sol_balance:.6f} SOL (${sol_usd:.2f})")
        
        # Get token accounts
        from solana.rpc.types import TokenAccountOpts
        from solders.pubkey import Pubkey
        
        token_accounts = await client.get_token_accounts_by_owner(
            pubkey,
            TokenAccountOpts(program_id=Pubkey.from_string("TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"))
        )
        
        print(f"\nToken Accounts: {len(token_accounts.value)}")
        for ta in token_accounts.value:
            account_data = ta.account.data
            # Parse the token account data
            # Token account data: mint (32) + owner (32) + amount (8) + ...
            if hasattr(account_data, 'parsed'):
                parsed = account_data.parsed
                info = parsed.get('info', {})
                mint = info.get('mint', 'Unknown')
                amount = float(info.get('tokenAmount', {}).get('uiAmount', 0))
                decimals = info.get('tokenAmount', {}).get('decimals', 0)
                
                if amount > 0:
                    if mint == FARTCOIN_MINT:
                        fart_usd = amount * 0.3585
                        print(f"  FARTCOIN: {amount:.4f} (${fart_usd:.2f})")
                    else:
                        print(f"  {mint[:20]}...: {amount}")

asyncio.run(check_wallet())
