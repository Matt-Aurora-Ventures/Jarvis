#!/usr/bin/env python3
"""Test script to debug Solana transaction signing for Jupiter swaps."""

import base64
import asyncio
import aiohttp
import json
from pathlib import Path
from solders.keypair import Keypair
from solders.transaction import VersionedTransaction
from solana.rpc.async_api import AsyncClient
from solana.rpc.types import TxOpts

SOLANA_RPC = "https://api.mainnet-beta.solana.com"

async def test_swap():
    # Load wallet
    wallet_path = Path.home() / '.lifeos' / 'wallets' / 'phantom_trading_wallet.json'
    data = json.loads(wallet_path.read_text())
    kp = Keypair.from_bytes(bytes(data))
    print(f'Wallet: {kp.pubkey()}')
    
    # Get quote
    params = {
        'inputMint': 'So11111111111111111111111111111111111111112',
        'outputMint': '9BB6NFEcjBCtnNLFko2FqVQBq8HHM13kCyYcdQbgpump',
        'amount': '5000000',  # 0.005 SOL
        'slippageBps': 200,
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.get('https://public.jupiterapi.com/quote', params=params) as resp:
            quote = await resp.json()
            out_amount = int(quote.get('outAmount', 0)) / 1e6
            print(f'Quote: {out_amount:.2f} FARTCOIN')
        
        # Get swap transaction
        payload = {
            'quoteResponse': quote,
            'userPublicKey': str(kp.pubkey()),
            'wrapAndUnwrapSol': True,
            'dynamicComputeUnitLimit': True,
            'prioritizationFeeLamports': 'auto',
        }
        
        async with session.post('https://public.jupiterapi.com/swap', json=payload) as resp:
            if resp.status != 200:
                print(f'Swap API error: {await resp.text()}')
                return
            swap_data = await resp.json()
            swap_tx_b64 = swap_data.get('swapTransaction')
            print(f'Swap TX received: {len(swap_tx_b64)} chars')
            
            # Decode the transaction
            tx_bytes = base64.b64decode(swap_tx_b64)
            tx = VersionedTransaction.from_bytes(tx_bytes)
            print(f'TX parsed, has {len(tx.signatures)} placeholder signature(s)')
            
            # Create new signed transaction with our keypair
            # The transaction from Jupiter has a placeholder signature
            # We need to create a fresh signed version
            signed_tx = VersionedTransaction(tx.message, [kp])
            print(f'Signed TX created with signature: {str(signed_tx.signatures[0])[:20]}...')
            
            # Send to Solana
            print('Sending to Solana...')
            async with AsyncClient(SOLANA_RPC) as client:
                result = await client.send_transaction(
                    signed_tx,
                    opts=TxOpts(skip_preflight=True, max_retries=3),
                )
                print(f'Result: {result}')
                
                if result.value:
                    sig = str(result.value)
                    print(f'\n✅ SUCCESS!')
                    print(f'   Signature: {sig}')
                    print(f'   https://solscan.io/tx/{sig}')
                else:
                    print(f'❌ Failed: {result}')

if __name__ == '__main__':
    asyncio.run(test_swap())
