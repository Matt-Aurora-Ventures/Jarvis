import asyncio
import aiohttp
import json
import os

for line in open('tg_bot/.env').read().splitlines():
    if '=' in line and not line.startswith('#'):
        k, v = line.split('=', 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"'))

BUY_TX = 'pzxW3iTLpgNsRFkG4VCY2XUpjCd3uodtDCsdvrQkEWxawGLf6m8UEXZFVueeP6KmTpctSY5Zg3cnhY1CHKwprS3'
SELL_TX = '3uUT5ag39NdyxRkUgoJkm3VYfUTaZZSuQx61ABqPdLY8BhjtkVxbwQHbG4yYYVxDHjZ8RbQteJJTRchP5tJ39eh1'
TREASURY = 'BFhTj4TGKC77C7s3HLnLbCiVd6dXQSqGvtD8sJY5egVR'

async def check():
    async with aiohttp.ClientSession() as s:
        # Check TX statuses
        print("Checking transaction statuses...")
        async with s.post('https://api.mainnet-beta.solana.com', json={
            'jsonrpc': '2.0', 'id': 1,
            'method': 'getSignatureStatuses',
            'params': [[BUY_TX, SELL_TX], {'searchTransactionHistory': True}]
        }) as r:
            result = await r.json()
            print("Raw result:", json.dumps(result, indent=2))
            
        # Check balance
        print("\nChecking balance...")
        async with s.post('https://api.mainnet-beta.solana.com', json={
            'jsonrpc': '2.0', 'id': 1,
            'method': 'getBalance',
            'params': [TREASURY]
        }) as r:
            result = await r.json()
            lamports = result.get('result', {}).get('value', 0)
            print(f"Balance: {lamports / 1e9:.6f} SOL")

asyncio.run(check())
