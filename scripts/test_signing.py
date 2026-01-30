#!/usr/bin/env python3
"""Test bags.fm signing flow"""
import asyncio
import os
import sys

async def test():
    import importlib.util
    spec = importlib.util.spec_from_file_location("bags_client", "/root/clawd/Jarvis/core/trading/bags_client.py")
    bags_module = importlib.util.module_from_spec(spec)
    
    class MockSecrets:
        @staticmethod
        def get_key(name, env_var):
            return os.environ.get(env_var)
    
    sys.modules["core.secrets"] = MockSecrets
    spec.loader.exec_module(bags_module)
    
    BagsAPIClient = bags_module.BagsAPIClient
    bags = BagsAPIClient()
    
    SOL_MINT = "So11111111111111111111111111111111111111112"
    TEST_TOKEN = "FsXJHch6cj9TyZGm1kfMwt8S8oATCEr6ccqWFp3Xpump"
    TREASURY_WALLET = "BFhTj4TGKC77C7s3HLnLbCiVd6dXQSqGvtD8sJY5egVR"
    
    print("Testing signing flow with venv...")
    
    quote = await bags.get_quote_raw(SOL_MINT, TEST_TOKEN, 0.001, slippage_bps=200)
    if not quote:
        print("Failed to get quote")
        return
    
    in_amt = quote.get('inAmount')
    out_amt = quote.get('outAmount')
    print(f"Quote OK: {in_amt} -> {out_amt}")
    
    import httpx
    swap_request = {"userPublicKey": TREASURY_WALLET, "quoteResponse": quote}
    headers = {"Content-Type": "application/json", "x-api-key": os.environ.get("BAGS_API_KEY")}
    
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            "https://public-api-v2.bags.fm/api/v1/trade/swap",
            json=swap_request,
            headers=headers
        )
        swap_result = response.json()
    
    if not swap_result.get("success"):
        print(f"Swap API error: {swap_result}")
        return
    
    swap_tx_base58 = swap_result.get("response", {}).get("swapTransaction")
    print(f"Got swap tx ({len(swap_tx_base58)} chars)")
    
    import base58
    from solders.transaction import VersionedTransaction
    
    keypair = await bags._load_keypair("/root/clawd/Jarvis/data/treasury_keypair.json")
    if not keypair:
        print("Failed to load keypair")
        return
    
    pubkey = str(keypair.pubkey())[:8]
    print(f"Loaded keypair: {pubkey}...")
    
    tx_bytes = base58.b58decode(swap_tx_base58)
    tx = VersionedTransaction.from_bytes(tx_bytes)
    print("Decoded tx")
    
    message_bytes = bytes(tx.message)
    signature = keypair.sign_message(message_bytes)
    signed_tx = VersionedTransaction.populate(tx.message, [signature])
    signed_tx_bytes = bytes(signed_tx)
    print(f"Signed tx: {len(signed_tx_bytes)} bytes")
    
    print("\n✅ SUCCESS: Signing flow works!")

if __name__ == "__main__":
    asyncio.run(test())
