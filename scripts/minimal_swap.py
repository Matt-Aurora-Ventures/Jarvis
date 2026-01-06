#!/usr/bin/env python3
"""
MINIMAL Solana Swap - No complex dependencies, just works
"""

import asyncio
import aiohttp
import base64
import json
from pathlib import Path

# Direct imports only
from solders.keypair import Keypair
from solders.transaction import VersionedTransaction
from solana.rpc.async_api import AsyncClient

JUPITER_QUOTE = "https://public.jupiterapi.com/quote"
JUPITER_SWAP = "https://public.jupiterapi.com/swap"
RPC = "https://api.mainnet-beta.solana.com"

SOL = "So11111111111111111111111111111111111111112"
USDC = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"


def load_keypair():
    """Load keypair directly without core module."""
    wallet_path = Path.home() / '.lifeos' / 'wallets' / 'phantom_trading_wallet.json'
    data = json.loads(wallet_path.read_text())
    return Keypair.from_bytes(bytes(data))


async def swap(input_mint: str, output_mint: str, amount_lamports: int, slippage_bps: int = 300):
    """
    Execute a swap with minimal dependencies.
    Returns: (success, signature_or_error)
    """
    kp = load_keypair()
    
    print(f"Swapping {amount_lamports} lamports...", flush=True)
    
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
        # 1. Get quote
        params = {
            "inputMint": input_mint,
            "outputMint": output_mint,
            "amount": str(amount_lamports),
            "slippageBps": str(slippage_bps),
        }
        
        print("Getting quote...", flush=True)
        async with session.get(JUPITER_QUOTE, params=params) as resp:
            if resp.status != 200:
                return False, f"Quote failed: {resp.status}"
            quote = await resp.json()
        
        out_amount = int(quote.get("outAmount", 0))
        print(f"Quote: {out_amount} output tokens", flush=True)
        
        # 2. Get swap transaction
        payload = {
            "quoteResponse": quote,
            "userPublicKey": str(kp.pubkey()),
            "wrapAndUnwrapSol": True,
            "dynamicComputeUnitLimit": True,
            "prioritizationFeeLamports": "auto",
        }
        
        print("Building transaction...", flush=True)
        async with session.post(JUPITER_SWAP, json=payload) as resp:
            if resp.status != 200:
                text = await resp.text()
                return False, f"Swap TX failed: {resp.status} - {text[:100]}"
            data = await resp.json()
        
        swap_tx = data.get("swapTransaction")
        if not swap_tx:
            return False, "No swap transaction returned"
        
        # 3. Sign
        print("Signing...", flush=True)
        tx_bytes = base64.b64decode(swap_tx)
        tx = VersionedTransaction.from_bytes(tx_bytes)
        signed_tx = VersionedTransaction(tx.message, [kp])
        
        # 4. Send directly to RPC
        print("Sending to Solana...", flush=True)
        async with AsyncClient(RPC) as client:
            try:
                result = await client.send_transaction(signed_tx)
                
                if result.value:
                    sig = str(result.value)
                    print(f"✅ Sent: {sig[:20]}...", flush=True)
                    
                    # Wait briefly for confirmation
                    await asyncio.sleep(3)
                    
                    # Check status
                    status = await client.get_signature_statuses([sig])
                    if status.value and status.value[0]:
                        if status.value[0].err:
                            return False, f"TX error: {status.value[0].err}"
                        print("✅ Confirmed!", flush=True)
                    
                    return True, sig
                else:
                    return False, "No signature returned"
                    
            except Exception as e:
                return False, f"Send error: {str(e)[:100]}"


async def test():
    """Test with a tiny swap: 0.001 SOL -> USDC"""
    print("\n" + "="*50)
    print("MINIMAL SWAP TEST")
    print("="*50 + "\n")
    
    # Check balance first
    async with AsyncClient(RPC) as client:
        kp = load_keypair()
        bal = await client.get_balance(kp.pubkey())
        sol = bal.value / 1e9
        print(f"Balance: {sol:.6f} SOL (${sol * 138:.2f})")
    
    if sol < 0.01:
        print("❌ Not enough SOL")
        return
    
    # Try swap: 0.001 SOL -> USDC
    amount = int(0.001 * 1e9)  # 0.001 SOL in lamports
    
    success, result = await swap(SOL, USDC, amount, 300)
    
    if success:
        print(f"\n✅ SUCCESS!")
        print(f"Signature: {result}")
        print(f"Explorer: https://solscan.io/tx/{result}")
    else:
        print(f"\n❌ FAILED: {result}")


if __name__ == "__main__":
    asyncio.run(test())
