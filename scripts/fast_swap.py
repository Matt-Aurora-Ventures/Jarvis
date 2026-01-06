#!/usr/bin/env python3
"""
Fast Swap - Simplified Jupiter swap without slow token lookups
"""

import asyncio
import aiohttp
import base64
from solders.keypair import Keypair
from solders.transaction import VersionedTransaction

JUPITER_QUOTE = "https://quote-api.jup.ag/v6/quote"
JUPITER_SWAP = "https://quote-api.jup.ag/v6/swap"

async def fast_swap(
    input_mint: str,
    output_mint: str,
    amount_lamports: int,
    keypair: Keypair,
    slippage_bps: int = 300,
):
    """Execute Jupiter swap quickly."""
    
    print(f"🔄 Swapping {amount_lamports/1e9:.6f} tokens", flush=True)
    
    # Get quote
    async with aiohttp.ClientSession() as session:
        params = {
            "inputMint": input_mint,
            "outputMint": output_mint,
            "amount": str(amount_lamports),
            "slippageBps": str(slippage_bps),
        }
        
        async with session.get(JUPITER_QUOTE, params=params, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            if resp.status != 200:
                return {"success": False, "error": f"Quote failed: {resp.status}"}
            
            quote = await resp.json()
        
        # Get swap transaction
        payload = {
            "quoteResponse": quote,
            "userPublicKey": str(keypair.pubkey()),
            "wrapAndUnwrapSol": True,
            "dynamicComputeUnitLimit": True,
            "prioritizationFeeLamports": "auto",
        }
        
        async with session.post(JUPITER_SWAP, json=payload, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            if resp.status != 200:
                return {"success": False, "error": f"Swap TX failed: {resp.status}"}
            
            data = await resp.json()
            swap_tx = data.get("swapTransaction")
        
        if not swap_tx:
            return {"success": False, "error": "No swap transaction"}
        
        # Sign and send
        print("✍️  Signing...", flush=True)
        tx_bytes = base64.b64decode(swap_tx)
        tx = VersionedTransaction.from_bytes(tx_bytes)
        signed_tx = VersionedTransaction(tx.message, [keypair])
        
        print("📤 Sending...", flush=True)
        
        # Send directly to RPC
        from solana.rpc.async_api import AsyncClient
        
        async with AsyncClient("https://api.mainnet-beta.solana.com") as client:
            result = await client.send_transaction(signed_tx)
            
            if result.value:
                sig = str(result.value)
                print(f"✅ Sent: {sig}", flush=True)
                
                # Wait for confirmation
                await asyncio.sleep(2)
                
                return {
                    "success": True,
                    "signature": sig,
                    "output": int(quote.get("outAmount", 0)),
                }
            else:
                return {"success": False, "error": "Send failed"}


if __name__ == "__main__":
    # Test
    from core import solana_wallet
    
    async def test():
        kp = solana_wallet.load_keypair()
        
        # SOL mint
        sol_mint = "So11111111111111111111111111111111111111112"
        # Test mint (replace with actual)
        test_mint = "9BB6NFEcjBCtnNLFko2FqVQBq8HHM13kCyYcdQbgpump"
        
        result = await fast_swap(
            sol_mint,
            test_mint,
            int(0.001 * 1e9),  # 0.001 SOL
            kp,
            500
        )
        
        print(f"Result: {result}")
    
    asyncio.run(test())
