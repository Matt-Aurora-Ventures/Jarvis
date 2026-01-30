#!/usr/bin/env python3
"""
Test bags.fm swap execution.
Performs a small test swap to verify the integration works.
"""

import asyncio
import os
import sys

# Add parent dirs to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.trading.bags_client import get_bags_client


async def main():
    # SOL mint address
    SOL_MINT = "So11111111111111111111111111111111111111112"
    
    # Test token (BAGS)
    BAGS_MINT = "U1zc8QpnrQ3HBJUBrWFYWbQTLzNsCpPgZNegWXdBAGS"
    
    # Treasury wallet
    TREASURY = "BFhTj4TGKC77C7s3HLnLbCiVd6dXQSqGvtD8sJY5egVR"
    
    # Small test amount (0.001 SOL = ~$0.20)
    TEST_AMOUNT = 0.001
    
    client = get_bags_client()
    
    print(f"Testing bags.fm swap integration...")
    print(f"  From: {TEST_AMOUNT} SOL")
    print(f"  To: BAGS token")
    print(f"  Wallet: {TREASURY[:8]}...")
    print()
    
    # Check if TREASURY_PASSWORD is set
    if not os.getenv("TREASURY_PASSWORD"):
        print("❌ TREASURY_PASSWORD not set in environment")
        print("   Add it to /root/clawd/Jarvis/tg_bot/.env")
        return
    
    # Test quote first
    print("1. Getting quote...")
    quote = await client.get_quote_raw(SOL_MINT, BAGS_MINT, TEST_AMOUNT)
    if quote:
        out_amount = int(quote.get("outAmount", 0)) / 1e9
        print(f"   ✅ Quote received: {TEST_AMOUNT} SOL -> {out_amount:.4f} BAGS")
    else:
        print("   ❌ Failed to get quote")
        return
    
    # Confirm before executing
    confirm = input("\n2. Execute swap? (yes/no): ").strip().lower()
    if confirm != "yes":
        print("   Aborted")
        return
    
    print("3. Executing swap...")
    result = await client.swap(
        from_token=SOL_MINT,
        to_token=BAGS_MINT,
        amount=TEST_AMOUNT,
        wallet_address=TREASURY,
        keypair_path="/root/clawd/Jarvis/data/treasury_keypair.json"
    )
    
    if result.success:
        print(f"   ✅ Swap successful!")
        print(f"   TX: {result.tx_hash}")
        print(f"   Out: {result.to_amount:.4f} BAGS")
    else:
        print(f"   ❌ Swap failed: {result.error}")


if __name__ == "__main__":
    asyncio.run(main())
