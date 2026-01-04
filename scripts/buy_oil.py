#!/usr/bin/env python3
"""Buy OIL token - $5 worth"""
import asyncio
import base64
import json
from pathlib import Path
import aiohttp
from solders.keypair import Keypair
from solders.transaction import VersionedTransaction

OIL = '5LS3ips7jWxfuVHzoMzKzp3cCwjH9zmrtYXmYBVGpump'
SOL = 'So11111111111111111111111111111111111111112'
AMOUNT = 37000000  # 0.037 SOL (~$5)

async def buy():
    wallet_path = Path.home() / '.lifeos' / 'wallets' / 'phantom_trading_wallet.json'
    kp = Keypair.from_bytes(bytes(json.loads(wallet_path.read_text())))
    print('🛢️ OIL PURCHASE - $5 worth')
    print(f'   Wallet: {str(kp.pubkey())}')
    
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=60)) as session:
        # Get quote
        params = {
            'inputMint': SOL,
            'outputMint': OIL,
            'amount': str(AMOUNT),
            'slippageBps': 500,
        }
        async with session.get('https://public.jupiterapi.com/quote', params=params) as resp:
            quote = await resp.json()
            if 'error' in quote:
                print(f'❌ Quote error: {quote}')
                return
            out = int(quote.get('outAmount', 0))
            print(f'   Quote: {out:,} OIL')
        
        # Get swap transaction
        payload = {
            'quoteResponse': quote,
            'userPublicKey': str(kp.pubkey()),
            'wrapAndUnwrapSol': True,
            'dynamicComputeUnitLimit': True,
            'prioritizationFeeLamports': 'auto',
        }
        async with session.post('https://public.jupiterapi.com/swap', json=payload) as resp:
            swap_data = await resp.json()
            swap_tx = swap_data.get('swapTransaction')
            if not swap_tx:
                print(f'❌ Swap error: {swap_data}')
                return
        
        # Sign transaction
        tx_bytes = base64.b64decode(swap_tx)
        tx = VersionedTransaction.from_bytes(tx_bytes)
        signed_tx = VersionedTransaction(tx.message, [kp])
        
        # Send via RPC
        rpc_payload = {
            'jsonrpc': '2.0',
            'id': 1,
            'method': 'sendTransaction',
            'params': [
                base64.b64encode(bytes(signed_tx)).decode('utf-8'),
                {'encoding': 'base64', 'skipPreflight': True, 'maxRetries': 3}
            ]
        }
        print('   📤 Sending transaction...')
        async with session.post('https://api.mainnet-beta.solana.com', json=rpc_payload) as resp:
            result = await resp.json()
            if 'result' in result:
                sig = result['result']
                print(f'\n🛢️ OIL PURCHASED!')
                print(f'   Signature: {sig}')
                print(f'   https://solscan.io/tx/{sig}')
            else:
                print(f'❌ RPC Error: {result}')

if __name__ == '__main__':
    asyncio.run(buy())
